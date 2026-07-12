import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import win_tg_pc_controller.bot as bot_module
from win_tg_pc_controller.bot import (
    _edit_or_reply,
    _handle_screenshot,
    _localized_markup,
    home_only_menu,
)


def test_screenshot_home_button_is_localized() -> None:
    menu = _localized_markup("en", home_only_menu())

    button = menu.inline_keyboard[0][0]
    assert button.text == "\U0001f3e0 Main menu"
    assert button.callback_data == "menu:main"


def test_screenshot_reply_has_home_button(monkeypatch) -> None:
    message = SimpleNamespace(reply_photo=AsyncMock())
    query = SimpleNamespace(message=message)
    update = SimpleNamespace()
    monkeypatch.setattr(bot_module, "_language", lambda _update: "en")
    monkeypatch.setattr(bot_module, "capture_screenshot_png", lambda _monitor_id: b"png")

    asyncio.run(_handle_screenshot(update, query, "1"))

    arguments = message.reply_photo.await_args.kwargs
    button = arguments["reply_markup"].inline_keyboard[0][0]
    assert arguments["photo"] == b"png"
    assert button.text == "\U0001f3e0 Main menu"
    assert button.callback_data == "menu:main"


def test_main_menu_callback_from_photo_replies_with_new_message(monkeypatch) -> None:
    message = SimpleNamespace(
        text=None,
        reply_text=AsyncMock(),
        edit_text=AsyncMock(),
    )
    update = SimpleNamespace(
        callback_query=SimpleNamespace(message=message),
        effective_message=message,
    )
    monkeypatch.setattr(bot_module, "_language", lambda _update: "en")

    asyncio.run(_edit_or_reply(update, "Main", home_only_menu()))

    message.reply_text.assert_awaited_once()
    message.edit_text.assert_not_awaited()
