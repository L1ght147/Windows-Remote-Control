import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import win_tg_pc_controller.bot as bot_module
from win_tg_pc_controller.config import AppConfig
from win_tg_pc_controller.bot import (
    _edit_or_reply,
    _handle_screenshot,
    _localized_markup,
    app_launch_menu,
    home_only_menu,
    main_menu,
    screenshot_menu,
)


def test_screenshot_home_button_is_localized() -> None:
    menu = _localized_markup("en", home_only_menu())

    button = menu.inline_keyboard[0][0]
    assert button.text == "\U0001f3e0 Main menu"
    assert button.callback_data == "menu:main"


def test_app_menu_has_localized_delete_button() -> None:
    menu = _localized_markup("en", app_launch_menu("tool"))

    button = next(
        button
        for row in menu.inline_keyboard
        for button in row
        if button.callback_data == "app:delete:tool"
    )
    assert button.text == "\U0001f5d1 Delete"
    assert all(
        button.callback_data != "cancel:menu:apps"
        for row in menu.inline_keyboard
        for button in row
    )


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


def test_screenshot_menu_includes_auto_screenshot_button(monkeypatch) -> None:
    monkeypatch.setattr(bot_module, "list_monitors", lambda: [])

    menu = screenshot_menu()

    assert any(
        button.callback_data == "timer:menu"
        for row in menu.inline_keyboard
        for button in row
    )
    assert all(
        button.callback_data != "timer:menu"
        for row in main_menu().inline_keyboard
        for button in row
    )


def test_notify_online_sends_localized_startup_message(monkeypatch, tmp_path) -> None:
    config = AppConfig(
        telegram_bot_token="token",
        allowed_user_id=123,
        apps_file=tmp_path / "apps.json",
        user_settings_file=tmp_path / "user_settings.json",
    )
    application = SimpleNamespace(
        bot_data={"config": config},
        bot=SimpleNamespace(send_message=AsyncMock()),
    )
    monkeypatch.setattr(bot_module, "_stored_language", lambda _user_id: "en")

    asyncio.run(bot_module.notify_online(application))

    application.bot.send_message.assert_awaited_once_with(chat_id=123, text="🟢 PC online")


def test_start_polling_notifies_only_after_application_starts(monkeypatch, tmp_path) -> None:
    config = AppConfig(
        telegram_bot_token="token",
        allowed_user_id=123,
        apps_file=tmp_path / "apps.json",
        user_settings_file=tmp_path / "user_settings.json",
    )
    calls: list[str] = []
    polling_kwargs: dict[str, object] = {}

    async def initialize() -> None:
        calls.append("initialize")

    async def start_polling(**kwargs) -> None:
        calls.append("polling")
        polling_kwargs.update(kwargs)

    async def start() -> None:
        calls.append("start")

    async def notify(_application) -> None:
        calls.append("notify")

    application = SimpleNamespace(
        initialize=initialize,
        updater=SimpleNamespace(start_polling=start_polling),
        start=start,
    )
    monkeypatch.setattr(bot_module, "notify_online", notify)

    asyncio.run(bot_module.start_polling(application, config))

    assert calls == ["initialize", "polling", "start", "notify"]
    assert callable(polling_kwargs["error_callback"])


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
