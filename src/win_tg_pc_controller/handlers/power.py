from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..i18n import Language, t
from ..power_timer import TIMER_ACTIONS, WARNING_LEAD_MINUTES, PowerSchedule, PowerTimer, validate_delay_minutes
from .common import (
    INPUT_STATE_KEY,
    POWER_TIMER_KEY,
    button,
    cancel_menu,
    confirm_menu,
    confirmations_of,
    edit_or_reply,
    reply,
)


DELAY_PRESETS_MINUTES = (15, 30, 60, 120)


def power_timer_of(context: ContextTypes.DEFAULT_TYPE) -> PowerTimer:
    return context.application.bot_data[POWER_TIMER_KEY]


def action_name(language: Language, action: str) -> str:
    return t(language, f"power.action_{action}")


def format_due_time(due_at: dt.datetime, now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now()
    if due_at.date() == now.date():
        return due_at.strftime("%H:%M")
    return due_at.strftime("%d.%m %H:%M")


def describe_schedule(language: Language, schedule: PowerSchedule) -> str:
    return t(
        language,
        "power.active",
        action=action_name(language, schedule.action),
        time=format_due_time(schedule.due_at),
        minutes=schedule.remaining_minutes(),
    )


def _delay_label(language: Language, minutes: int) -> str:
    if minutes % 60 == 0:
        return t(language, "power.delay_hours", hours=minutes // 60)
    return t(language, "power.delay_minutes", minutes=minutes)


def power_timer_menu(language: Language, schedule: PowerSchedule | None) -> InlineKeyboardMarkup:
    rows = [
        [button(t(language, "menu.timer_shutdown"), "ptimer:pick:shutdown")],
        [button(t(language, "menu.timer_sleep"), "ptimer:pick:sleep")],
    ]
    if schedule is not None:
        rows.append([button(t(language, "menu.timer_cancel"), "ptimer:cancel")])
    rows.append([button(t(language, "menu.back"), "menu:controls")])
    return InlineKeyboardMarkup(rows)


def delay_menu(language: Language, action: str) -> InlineKeyboardMarkup:
    presets = [button(_delay_label(language, minutes), f"ptimer:delay:{action}:{minutes}") for minutes in DELAY_PRESETS_MINUTES]
    return InlineKeyboardMarkup(
        [
            presets[:2],
            presets[2:],
            [button(t(language, "menu.custom_delay"), f"ptimer:custom:{action}")],
            [button(t(language, "menu.back"), "ptimer:menu")],
        ]
    )


def warning_menu(language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[button(t(language, "menu.timer_cancel"), "ptimer:cancel")]])


def _status_text(language: Language, schedule: PowerSchedule | None) -> str:
    status = t(language, "power.inactive") if schedule is None else describe_schedule(language, schedule)
    return f"{t(language, 'power.title')}\n{status}"


async def show_power_timer(update: Update, context: ContextTypes.DEFAULT_TYPE, language: Language) -> None:
    schedule = power_timer_of(context).schedule
    await edit_or_reply(update, _status_text(language, schedule), power_timer_menu(language, schedule))


def _require_action(action: str) -> str:
    if action not in TIMER_ACTIONS:
        raise ValueError(f"Unknown timer action: {action}")
    return action


async def _request_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    action: str,
    minutes: int,
    send: Callable[[Update, str, InlineKeyboardMarkup | None], Awaitable[None]],
) -> None:
    confirm_action = f"ptimer:start:{action}:{minutes}"
    confirmations_of(context).request(update.effective_user.id, confirm_action)
    text = t(language, "power.confirm", action=action_name(language, action), minutes=minutes)
    current = power_timer_of(context).schedule
    if current is not None:
        text += "\n" + t(language, "power.replaces", current=describe_schedule(language, current))
    await send(update, text, confirm_menu(language, confirm_action, "ptimer:menu"))


async def handle_power_timer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    data: str,
) -> None:
    if data == "ptimer:menu":
        await show_power_timer(update, context, language)
        return

    if data == "ptimer:cancel":
        cancelled = power_timer_of(context).cancel()
        text = t(language, "power.cancelled" if cancelled else "power.nothing_to_cancel")
        await edit_or_reply(update, text, power_timer_menu(language, None))
        return

    if data.startswith("ptimer:pick:"):
        action = _require_action(data.removeprefix("ptimer:pick:"))
        await edit_or_reply(
            update,
            t(language, "power.select_delay", action=action_name(language, action)),
            delay_menu(language, action),
        )
        return

    if data.startswith("ptimer:custom:"):
        action = _require_action(data.removeprefix("ptimer:custom:"))
        context.user_data[INPUT_STATE_KEY] = {"type": "power_timer_minutes", "action": action}
        await edit_or_reply(update, t(language, "power.enter_minutes"), cancel_menu(language, "ptimer:menu"))
        return

    if data.startswith("ptimer:delay:"):
        action_text, _, minutes_text = data.removeprefix("ptimer:delay:").partition(":")
        action = _require_action(action_text)
        minutes = validate_delay_minutes(minutes_text)
        await _request_confirmation(update, context, language, action, minutes, edit_or_reply)


async def handle_minutes_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    state: dict,
    text: str,
) -> None:
    try:
        minutes = validate_delay_minutes(text)
    except ValueError:
        await reply(update, t(language, "power.invalid_minutes"), cancel_menu(language, "ptimer:menu"))
        return
    context.user_data.pop(INPUT_STATE_KEY, None)
    await _request_confirmation(update, context, language, state["action"], minutes, reply)


async def start_confirmed_timer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    confirm_action: str,
) -> None:
    action_text, _, minutes_text = confirm_action.removeprefix("ptimer:start:").partition(":")
    schedule = power_timer_of(context).start(_require_action(action_text), validate_delay_minutes(minutes_text))
    text = t(
        language,
        "power.started",
        action=action_name(language, schedule.action),
        time=format_due_time(schedule.due_at),
    )
    if schedule.minutes > WARNING_LEAD_MINUTES:
        text += "\n" + t(language, "power.warning_note")
    await edit_or_reply(update, text, power_timer_menu(language, schedule))
