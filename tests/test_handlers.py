import asyncio
import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import win_tg_pc_controller.handlers.screenshots as screenshots_module
from win_tg_pc_controller.apps import LaunchApp
from win_tg_pc_controller.config import AppConfig
from win_tg_pc_controller.handlers import router
from win_tg_pc_controller.handlers.apps import app_launch_menu, apps_menu
from win_tg_pc_controller.handlers.clipboard import clipboard_menu
from win_tg_pc_controller.handlers.common import (
    back_only_menu,
    cancel_menu,
    confirm_menu,
    home_only_menu,
    main_menu,
)
from win_tg_pc_controller.handlers.controls import controls_menu
from win_tg_pc_controller.handlers.power import delay_menu, format_due_time, power_timer_menu, warning_menu
from win_tg_pc_controller.handlers.processes import process_results_menu, processes_menu
from win_tg_pc_controller.handlers.screenshots import (
    screenshot_menu,
    screenshot_timer_menu,
    screenshot_timer_monitor_menu,
)
from win_tg_pc_controller.power_timer import PowerSchedule, PowerTimer
from win_tg_pc_controller.processes import ProcessCandidate
from win_tg_pc_controller.screenshot import MonitorInfo
from win_tg_pc_controller.screenshot_timer import ScreenshotSchedule
from win_tg_pc_controller.security import ConfirmationStore


def _has_cyrillic(text: str) -> bool:
    return any("а" <= char.lower() <= "я" or char.lower() == "ё" for char in text)


def test_english_menus_have_no_cyrillic(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        screenshots_module,
        "list_monitors",
        lambda: [MonitorInfo(0, 3840, 1080, 0, 0, is_all=True), MonitorInfo(1, 1920, 1080, 0, 0)],
    )
    apps = {"tool": LaunchApp("tool", "Tool", tmp_path / "tool.exe")}
    process = ProcessCandidate(pid=1, name="tool.exe", exe="", cmdline="")
    menus = [
        main_menu("en"),
        back_only_menu("en"),
        home_only_menu("en"),
        cancel_menu("en", "menu:main"),
        confirm_menu("en", "clipboard:clear", "menu:clipboard"),
        controls_menu("en"),
        apps_menu("en", apps),
        app_launch_menu("en", "tool"),
        processes_menu("en"),
        process_results_menu("en", [process]),
        clipboard_menu("en"),
        screenshot_menu("en"),
        screenshot_timer_menu("en", ScreenshotSchedule(1, 5)),
        screenshot_timer_monitor_menu("en"),
        power_timer_menu("en", PowerSchedule("sleep", 30, dt.datetime.now())),
        delay_menu("en", "shutdown"),
        warning_menu("en"),
    ]

    labels = [button.text for menu in menus for row in menu.inline_keyboard for button in row]

    assert [label for label in labels if _has_cyrillic(label)] == []


@pytest.mark.parametrize(
    ("language", "expected_title", "expected_button"),
    [("en", "📋 <b>Clipboard</b>", "👁 Show"), ("ru", "📋 <b>Буфер обмена</b>", "👁 Показать")],
)
def test_callback_renders_menu_in_stored_language(
    tmp_path: Path, language: str, expected_title: str, expected_button: str
) -> None:
    config = AppConfig(
        telegram_bot_token="123:token",
        allowed_user_id=123,
        apps_file=tmp_path / "apps.json",
        user_settings_file=tmp_path / "user_settings.json",
    )
    message = SimpleNamespace(text="menu", edit_text=AsyncMock(), reply_text=AsyncMock())
    query = SimpleNamespace(data="menu:clipboard", message=message, answer=AsyncMock(), from_user=SimpleNamespace(id=123))
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=123), effective_message=message)
    context = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "config": config,
                "confirmations": ConfirmationStore(30),
                "language_store": SimpleNamespace(get=lambda _user_id: language),
            }
        ),
        user_data={},
    )

    asyncio.run(router.handle_callback(update, context))

    text = message.edit_text.await_args.args[0]
    markup = message.edit_text.await_args.kwargs["reply_markup"]
    assert text == expected_title
    assert markup.inline_keyboard[0][0].text == expected_button


def _callback_context(tmp_path: Path, language: str = "en", **bot_data) -> SimpleNamespace:
    config = AppConfig(
        telegram_bot_token="123:token",
        allowed_user_id=123,
        apps_file=tmp_path / "apps.json",
        user_settings_file=tmp_path / "user_settings.json",
    )
    return SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "config": config,
                "confirmations": ConfirmationStore(30),
                "language_store": SimpleNamespace(get=lambda _user_id: language),
                **bot_data,
            }
        ),
        user_data={},
    )


def _callback_update(data: str) -> tuple[SimpleNamespace, SimpleNamespace]:
    message = SimpleNamespace(text="menu", edit_text=AsyncMock(), reply_text=AsyncMock())
    query = SimpleNamespace(data=data, message=message, answer=AsyncMock(), from_user=SimpleNamespace(id=123))
    update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=123), effective_message=message)
    return update, message


def test_power_timer_starts_only_after_confirmation(tmp_path: Path) -> None:
    fired: list[str] = []

    async def run_action(action: str) -> None:
        fired.append(action)

    async def scenario() -> tuple[PowerSchedule | None, PowerSchedule | None, list[str]]:
        timer = PowerTimer(run_action, AsyncMock(), AsyncMock())
        context = _callback_context(tmp_path, power_timer=timer)

        update, message = _callback_update("ptimer:delay:shutdown:30")
        await router.handle_callback(update, context)
        before_confirm = timer.schedule
        prompt = message.edit_text.await_args.args[0]

        update, message = _callback_update("confirm:ptimer:start:shutdown:30")
        await router.handle_callback(update, context)
        after_confirm = timer.schedule
        result = message.edit_text.await_args.args[0]
        timer.cancel()
        return before_confirm, after_confirm, [prompt, result]

    before_confirm, after_confirm, texts = asyncio.run(scenario())

    assert before_confirm is None
    assert after_confirm is not None
    assert (after_confirm.action, after_confirm.minutes) == ("shutdown", 30)
    assert "shutdown in 30 min" in texts[0]
    assert texts[1].startswith("✅ Timer set: shutdown at")
    assert fired == []


def test_power_timer_cancel_from_warning(tmp_path: Path) -> None:
    async def scenario() -> tuple[PowerSchedule | None, str]:
        timer = PowerTimer(AsyncMock(), AsyncMock(), AsyncMock())
        timer.start("sleep", 30)
        context = _callback_context(tmp_path, power_timer=timer)
        update, message = _callback_update("ptimer:cancel")
        await router.handle_callback(update, context)
        return timer.schedule, message.edit_text.await_args.args[0]

    schedule, text = asyncio.run(scenario())

    assert schedule is None
    assert text == "✅ Timer cancelled."


def test_power_timer_rejects_unknown_action(tmp_path: Path) -> None:
    async def scenario() -> str:
        context = _callback_context(tmp_path, power_timer=PowerTimer(AsyncMock(), AsyncMock(), AsyncMock()))
        update, message = _callback_update("ptimer:delay:reboot:30")
        await router.handle_callback(update, context)
        return message.edit_text.await_args.args[0]

    assert "Unknown timer action" in asyncio.run(scenario())


def test_format_due_time_includes_date_for_tomorrow() -> None:
    now = dt.datetime(2026, 10, 15, 23, 30)

    assert format_due_time(dt.datetime(2026, 10, 15, 23, 50), now) == "23:50"
    assert format_due_time(dt.datetime(2026, 10, 16, 0, 10), now) == "16.10 00:10"


def test_power_timer_custom_minutes_request_confirmation(tmp_path: Path) -> None:
    async def scenario() -> tuple[list[str], PowerSchedule | None, bool]:
        timer = PowerTimer(AsyncMock(), AsyncMock(), AsyncMock())
        context = _callback_context(tmp_path, power_timer=timer)
        update, _message = _callback_update("ptimer:custom:sleep")
        await router.handle_callback(update, context)

        replies: list[str] = []
        for text in ["abc", "45"]:
            message = SimpleNamespace(text=text, reply_text=AsyncMock())
            text_update = SimpleNamespace(
                callback_query=None,
                effective_user=SimpleNamespace(id=123),
                effective_message=message,
            )
            await router.handle_text(text_update, context)
            replies.append(message.reply_text.await_args.args[0])
        confirmed = context.application.bot_data["confirmations"].confirm(123, "ptimer:start:sleep:45")
        return replies, timer.schedule, confirmed

    replies, schedule, confirmed = asyncio.run(scenario())

    assert replies[0] == "❌ Send a whole number from 1 to 1440."
    assert "sleep in 45 min" in replies[1]
    assert schedule is None
    assert confirmed
