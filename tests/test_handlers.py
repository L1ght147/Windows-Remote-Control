import asyncio
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
from win_tg_pc_controller.handlers.processes import process_results_menu, processes_menu
from win_tg_pc_controller.handlers.screenshots import (
    screenshot_menu,
    screenshot_timer_menu,
    screenshot_timer_monitor_menu,
)
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
