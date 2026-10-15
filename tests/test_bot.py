import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import InvalidToken, NetworkError

import win_tg_pc_controller.bot as bot_module
from win_tg_pc_controller.apps import LaunchApp
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


def test_screenshot_replaces_monitor_menu_with_home_button(monkeypatch) -> None:
    message = SimpleNamespace(chat_id=123, delete=AsyncMock())
    query = SimpleNamespace(message=message)
    update = SimpleNamespace()
    context = SimpleNamespace(bot=SimpleNamespace(send_photo=AsyncMock()))
    monkeypatch.setattr(bot_module, "_language", lambda _update: "en")
    monkeypatch.setattr(bot_module, "capture_screenshot_png", lambda _monitor_id: b"png")

    asyncio.run(_handle_screenshot(update, context, query, "1"))

    arguments = context.bot.send_photo.await_args.kwargs
    assert arguments["chat_id"] == 123
    button = arguments["reply_markup"].inline_keyboard[0][0]
    assert arguments["photo"] == b"png"
    assert button.text == "\U0001f3e0 Main menu"
    assert button.callback_data == "menu:main"
    message.delete.assert_awaited_once()


def test_screenshot_capture_failure_keeps_monitor_menu(monkeypatch) -> None:
    message = SimpleNamespace(chat_id=123, delete=AsyncMock())
    query = SimpleNamespace(message=message)
    update = SimpleNamespace()
    context = SimpleNamespace(bot=SimpleNamespace(send_photo=AsyncMock()))
    monkeypatch.setattr(bot_module, "_language", lambda _update: "en")
    monkeypatch.setattr(
        bot_module,
        "capture_screenshot_png",
        lambda _monitor_id: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )

    with pytest.raises(RuntimeError, match="unavailable"):
        asyncio.run(_handle_screenshot(update, context, query, "1"))

    context.bot.send_photo.assert_not_awaited()
    message.delete.assert_not_awaited()


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


def _config(tmp_path, **overrides) -> AppConfig:
    values = {
        "telegram_bot_token": "123:token",
        "allowed_user_id": 123,
        "apps_file": tmp_path / "apps.json",
        "user_settings_file": tmp_path / "user_settings.json",
    }
    values.update(overrides)
    return AppConfig(**values)


def test_initialize_retries_network_errors(monkeypatch) -> None:
    attempts: list[int] = []

    async def initialize() -> None:
        attempts.append(1)
        if len(attempts) < 3:
            raise NetworkError("offline")

    monkeypatch.setattr(bot_module, "STARTUP_RETRY_INITIAL_DELAY_SECONDS", 0)
    application = SimpleNamespace(initialize=initialize)

    asyncio.run(bot_module.initialize_with_retries(application, retries=-1))

    assert len(attempts) == 3


def test_initialize_stops_after_configured_retries(monkeypatch) -> None:
    initialize = AsyncMock(side_effect=NetworkError("offline"))
    monkeypatch.setattr(bot_module, "STARTUP_RETRY_INITIAL_DELAY_SECONDS", 0)
    application = SimpleNamespace(initialize=initialize)

    with pytest.raises(NetworkError):
        asyncio.run(bot_module.initialize_with_retries(application, retries=2))

    assert initialize.await_count == 3


def test_initialize_does_not_retry_invalid_token(monkeypatch) -> None:
    initialize = AsyncMock(side_effect=InvalidToken())
    monkeypatch.setattr(bot_module, "STARTUP_RETRY_INITIAL_DELAY_SECONDS", 0)
    application = SimpleNamespace(initialize=initialize)

    with pytest.raises(InvalidToken):
        asyncio.run(bot_module.initialize_with_retries(application, retries=-1))

    assert initialize.await_count == 1


def test_start_polling_survives_startup_notification_failure(monkeypatch, tmp_path) -> None:
    application = SimpleNamespace(
        initialize=AsyncMock(),
        updater=SimpleNamespace(start_polling=AsyncMock()),
        start=AsyncMock(),
    )
    monkeypatch.setattr(bot_module, "notify_online", AsyncMock(side_effect=NetworkError("offline")))

    asyncio.run(bot_module.start_polling(application, _config(tmp_path)))

    application.start.assert_awaited_once()


def test_build_application_survives_broken_apps_file(tmp_path) -> None:
    apps_path = tmp_path / "apps.json"
    apps_path.write_text("{not json", encoding="utf-8")

    application = bot_module.build_application(_config(tmp_path))

    assert application.bot_data["apps"] == {}
    assert apps_path.read_text(encoding="utf-8") == "{not json"


def test_apps_menu_marks_missing_app(tmp_path) -> None:
    existing_path = tmp_path / "tool.exe"
    existing_path.write_bytes(b"")
    apps = {
        "tool": LaunchApp("tool", "Tool", existing_path),
        "gone": LaunchApp("gone", "Gone", tmp_path / "gone.exe"),
    }

    menu = bot_module.apps_menu(apps)

    assert menu.inline_keyboard[0][0].text == "🚀 Tool"
    assert menu.inline_keyboard[1][0].text == "⚠️ Gone"


def test_setup_logging_writes_to_file(tmp_path) -> None:
    log_file = tmp_path / "logs" / "bot.log"
    root = logging.getLogger()
    previous_handlers = root.handlers[:]
    previous_level = root.level
    try:
        bot_module.setup_logging(log_file)
        logging.getLogger("test").info("hello log")
        for handler in root.handlers:
            handler.flush()
        assert "hello log" in log_file.read_text(encoding="utf-8")
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = previous_handlers
        root.setLevel(previous_level)
