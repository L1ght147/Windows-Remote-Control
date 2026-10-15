from __future__ import annotations

import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..i18n import Language, t
from ..screenshot import MonitorInfo, capture_screenshot, list_monitors
from ..screenshot_timer import ScreenshotSchedule, ScreenshotTimer, validate_interval_minutes
from .common import (
    INPUT_STATE_KEY,
    SCREENSHOT_TIMER_KEY,
    button,
    cancel_menu,
    edit_or_reply,
    home_only_menu,
    reply,
)


def _monitor_label(language: Language, monitor: MonitorInfo) -> str:
    if monitor.is_all:
        return t(language, "menu.all_monitors", width=monitor.width, height=monitor.height)
    return t(language, "menu.monitor", id=monitor.id, width=monitor.width, height=monitor.height)


def screenshot_menu(language: Language) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [button(_monitor_label(language, monitor), f"shot:{monitor.id}")] for monitor in list_monitors()
    ]
    rows.append([button(t(language, "menu.timer"), "timer:menu")])
    rows.append([button(t(language, "menu.back"), "menu:main")])
    return InlineKeyboardMarkup(rows)


def screenshot_timer_menu(language: Language, schedule: ScreenshotSchedule | None) -> InlineKeyboardMarkup:
    rows = [[button(t(language, "menu.configure"), "timer:start")]]
    if schedule is not None:
        rows.append([button(t(language, "menu.stop"), "timer:stop")])
    rows.append([button(t(language, "menu.back"), "menu:screenshot")])
    return InlineKeyboardMarkup(rows)


def screenshot_timer_monitor_menu(language: Language) -> InlineKeyboardMarkup:
    rows = [
        [button(_monitor_label(language, monitor), f"timer:monitor:{monitor.id}")] for monitor in list_monitors()
    ]
    rows.append([button(t(language, "menu.back"), "timer:menu")])
    return InlineKeyboardMarkup(rows)


def screenshot_timer(context: ContextTypes.DEFAULT_TYPE) -> ScreenshotTimer:
    return context.application.bot_data[SCREENSHOT_TIMER_KEY]


async def show_screenshot_menu(update: Update, language: Language) -> None:
    await edit_or_reply(update, t(language, "title.screenshot"), screenshot_menu(language))


async def handle_screenshot(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    monitor_id_text: str,
) -> None:
    query = update.callback_query
    monitor_id = int(monitor_id_text)
    screenshot = await asyncio.to_thread(capture_screenshot, monitor_id)
    await context.bot.send_photo(
        chat_id=query.message.chat_id,
        photo=screenshot,
        reply_markup=home_only_menu(language),
    )
    await query.message.delete()


async def show_screenshot_timer(update: Update, context: ContextTypes.DEFAULT_TYPE, language: Language) -> None:
    schedule = screenshot_timer(context).schedule
    if schedule is None:
        status = t(language, "timer.inactive")
    else:
        status = t(
            language,
            "timer.active",
            monitor_id=schedule.monitor_id,
            minutes=schedule.interval_minutes,
        )
    await edit_or_reply(
        update,
        f"{t(language, 'timer.title')}\n{status}",
        screenshot_timer_menu(language, schedule),
    )


async def handle_screenshot_timer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    data: str,
) -> None:
    if data == "timer:menu":
        await show_screenshot_timer(update, context, language)
        return
    if data == "timer:start":
        await edit_or_reply(
            update,
            t(language, "timer.select_monitor"),
            screenshot_timer_monitor_menu(language),
        )
        return
    if data == "timer:stop":
        screenshot_timer(context).stop()
        context.user_data.pop(INPUT_STATE_KEY, None)
        await edit_or_reply(
            update,
            t(language, "timer.stopped"),
            screenshot_timer_menu(language, None),
        )
        return
    if data.startswith("timer:monitor:"):
        monitor_id = int(data.removeprefix("timer:monitor:"))
        context.user_data[INPUT_STATE_KEY] = {
            "type": "screenshot_timer_interval",
            "monitor_id": monitor_id,
        }
        await edit_or_reply(
            update,
            t(language, "timer.enter_interval"),
            cancel_menu(language, "timer:menu"),
        )


async def handle_timer_interval_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    state: dict,
    text: str,
) -> None:
    try:
        interval_minutes = validate_interval_minutes(text)
    except ValueError:
        await reply(
            update,
            t(language, "timer.invalid_interval"),
            cancel_menu(language, "timer:menu"),
        )
        return
    schedule = screenshot_timer(context).start(state["monitor_id"], interval_minutes)
    context.user_data.pop(INPUT_STATE_KEY, None)
    await reply(
        update,
        t(
            language,
            "timer.started",
            monitor_id=schedule.monitor_id,
            minutes=schedule.interval_minutes,
        ),
        screenshot_timer_menu(language, schedule),
    )
