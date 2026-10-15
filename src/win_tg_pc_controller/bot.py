from __future__ import annotations

import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram import Update
from telegram.error import NetworkError, TelegramError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .apps import LaunchApp, load_apps
from .config import AppConfig, load_config
from .handlers.common import LANGUAGE_STORE_KEY, SCREENSHOT_TIMER_KEY, language_store_of
from .handlers.router import handle_callback, handle_text, language_command, start
from .i18n import DEFAULT_LANGUAGE, Language, t
from .language_store import LanguageStore
from .screenshot import capture_screenshot
from .screenshot_timer import ScreenshotTimer
from .security import ConfirmationStore


LOGGER = logging.getLogger(__name__)
STARTUP_RETRY_INITIAL_DELAY_SECONDS = 5.0
STARTUP_RETRY_MAX_DELAY_SECONDS = 60.0
LOG_FILE = Path("logs") / "bot.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3


def _owner_language(application: Application) -> Language:
    config: AppConfig = application.bot_data["config"]
    return language_store_of(application.bot_data).get(config.allowed_user_id) or DEFAULT_LANGUAGE


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    if isinstance(error, (NetworkError, TimedOut)):
        LOGGER.warning(
            "Telegram network error while processing update. "
            "Check connection to https://api.telegram.org, VPN/proxy/firewall. Error: %s",
            error,
        )
        return
    LOGGER.exception("Unhandled bot error", exc_info=error)


async def notify_online(application: Application) -> None:
    config: AppConfig = application.bot_data["config"]
    await application.bot.send_message(
        chat_id=config.allowed_user_id,
        text=t(_owner_language(application), "startup.online"),
    )


async def initialize_with_retries(application: Application, retries: int) -> None:
    delay = STARTUP_RETRY_INITIAL_DELAY_SECONDS
    attempt = 0
    while True:
        try:
            await application.initialize()
            return
        except NetworkError as exc:
            attempt += 1
            if retries != -1 and attempt > retries:
                raise
            LOGGER.warning(
                "Telegram API is unreachable during startup (attempt %s), retrying in %.0f s: %s",
                attempt,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, STARTUP_RETRY_MAX_DELAY_SECONDS)


async def start_polling(application: Application, config: AppConfig) -> None:
    if application.updater is None:
        raise RuntimeError("Telegram updater is not configured")

    def error_callback(exc: TelegramError) -> None:
        application.create_task(application.process_error(error=exc, update=None))

    await initialize_with_retries(application, config.telegram_bootstrap_retries)
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        bootstrap_retries=config.telegram_bootstrap_retries,
        timeout=int(config.telegram_timeout_seconds),
        error_callback=error_callback,
    )
    await application.start()
    try:
        await notify_online(application)
    except TelegramError as exc:
        LOGGER.warning("Failed to send startup notification: %s", exc)


async def run_polling(application: Application, config: AppConfig) -> None:
    try:
        await start_polling(application, config)
        await asyncio.Event().wait()
    finally:
        timer: ScreenshotTimer | None = application.bot_data.get(SCREENSHOT_TIMER_KEY)
        if timer is not None:
            timer.stop()
        if application.updater is not None and application.updater.running:
            await application.updater.stop()
        if application.running:
            await application.stop()
        await application.shutdown()


def _load_apps_for_startup(config: AppConfig) -> dict[str, LaunchApp]:
    try:
        return load_apps(config.apps_file)
    except (OSError, ValueError):
        LOGGER.exception(
            "Failed to load %s, starting with an empty application list. "
            "Fix the file; it is not overwritten until then.",
            config.apps_file,
        )
        return {}


def build_application(config: AppConfig) -> Application:
    apps = _load_apps_for_startup(config)
    app = (
        Application.builder()
        .token(config.telegram_bot_token)
        .connect_timeout(config.telegram_timeout_seconds)
        .read_timeout(config.telegram_timeout_seconds)
        .write_timeout(config.telegram_timeout_seconds)
        .pool_timeout(config.telegram_timeout_seconds)
        .build()
    )
    app.bot_data["config"] = config
    app.bot_data[LANGUAGE_STORE_KEY] = LanguageStore(config.user_settings_file)
    app.bot_data["confirmations"] = ConfirmationStore(config.confirmation_ttl_seconds)
    app.bot_data["apps"] = apps

    async def send_timed_screenshot(monitor_id: int) -> None:
        await app.bot.send_photo(
            chat_id=config.allowed_user_id,
            photo=await asyncio.to_thread(capture_screenshot, monitor_id),
        )

    async def report_timer_failure(exc: Exception) -> None:
        LOGGER.warning("Auto-screenshot timer stopped: %s", exc)
        await app.bot.send_message(
            chat_id=config.allowed_user_id,
            text=t(_owner_language(app), "timer.failed"),
        )

    app.bot_data[SCREENSHOT_TIMER_KEY] = ScreenshotTimer(send_timed_screenshot, report_timer_failure)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(handle_error)
    return app


def setup_logging(log_file: Path = LOG_FILE) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
    ]
    # pythonw.exe (autostart) has no console: sys.stderr is None there.
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def run() -> None:
    setup_logging()
    try:
        config = load_config()
        app = build_application(config)
    except Exception:
        LOGGER.exception("Failed to start Windows Telegram PC Controller")
        raise
    LOGGER.info("Starting Windows Telegram PC Controller")
    try:
        asyncio.run(run_polling(app, config))
    except TimedOut:
        LOGGER.error(
            "Telegram API timed out. Check internet access to https://api.telegram.org, "
            "VPN/proxy/firewall settings, and TELEGRAM_BOT_TOKEN."
        )
        raise
    except NetworkError:
        LOGGER.error(
            "Telegram network error. Check internet access to https://api.telegram.org, "
            "VPN/proxy/firewall settings, and TELEGRAM_BOT_TOKEN."
        )
        raise
    except Exception:
        LOGGER.exception("Windows Telegram PC Controller stopped with an error")
        raise
