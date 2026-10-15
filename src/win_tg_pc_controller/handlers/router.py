from __future__ import annotations

import asyncio
import logging
from html import escape

from telegram import Update
from telegram.ext import ContextTypes

from ..i18n import Language, LocalizedError, is_supported_language, t
from ..status import collect_status, format_status
from . import apps, clipboard, controls, processes, screenshots
from .common import (
    INPUT_STATE_KEY,
    back_only_menu,
    confirmations_of,
    edit_or_reply,
    is_allowed,
    language_of,
    language_store_of,
    main_menu,
    reject,
    reply,
    show_language_selection,
    show_main,
    stored_language,
    user_id,
)


LOGGER = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update, context):
        await reject(update)
        return
    context.user_data.pop(INPUT_STATE_KEY, None)
    language = stored_language(context, update)
    if language is None:
        await show_language_selection(update, language_of(context, update))
        return
    await show_main(update, language)


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update, context):
        await reject(update)
        return
    context.user_data.pop(INPUT_STATE_KEY, None)
    confirmations_of(context).cancel(user_id(update))
    await show_language_selection(update, language_of(context, update))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update, context):
        await reject(update)
        return

    language = stored_language(context, update)
    if language is None:
        await show_language_selection(update, language_of(context, update))
        return

    state = context.user_data.get(INPUT_STATE_KEY)
    text = (update.effective_message.text or "").strip()
    if not state:
        await reply(update, t(language, "input.use_menu"), main_menu(language))
        return

    state_type = state["type"]
    if state_type == "add_app_title":
        await apps.handle_add_title_input(update, context, language, text)
    elif state_type == "add_app_path":
        await apps.handle_add_path_input(update, context, language, state, text)
    elif state_type == "process_search":
        await processes.handle_search_input(update, context, language, text)
    elif state_type == "clipboard_set":
        await clipboard.handle_set_input(update, context, language, text)
    elif state_type == "screenshot_timer_interval":
        await screenshots.handle_timer_interval_input(update, context, language, state, text)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    if not is_allowed(update, context):
        await reject(update)
        return

    await query.answer()
    data = query.data or ""
    if data.startswith("language:"):
        selected_language = data.removeprefix("language:")
        if not is_supported_language(selected_language):
            await show_language_selection(update, language_of(context, update))
            return
        language_store_of(context.application.bot_data).set(query.from_user.id, selected_language)
        context.user_data.pop(INPUT_STATE_KEY, None)
        confirmations_of(context).cancel(query.from_user.id)
        await show_main(update, selected_language)
        return

    language = stored_language(context, update)
    if language is None:
        await show_language_selection(update, language_of(context, update))
        return

    try:
        await _route_callback(update, context, language, data)
    except LocalizedError as exc:
        LOGGER.info("Callback rejected: %s", exc)
        await edit_or_reply(update, f"❌ {escape(exc.localized(language))}", main_menu(language))
    except (RuntimeError, ValueError) as exc:
        LOGGER.info("Callback rejected: %s", exc)
        await edit_or_reply(update, f"❌ {escape(str(exc))}", main_menu(language))
    except Exception:
        LOGGER.exception("Callback failed")
        await edit_or_reply(update, t(language, "callback.failed"), main_menu(language))


async def _route_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    data: str,
) -> None:
    if data == "menu:main":
        context.user_data.pop(INPUT_STATE_KEY, None)
        await show_main(update, language)
    elif data == "menu:status":
        await _show_status(update, language)
    elif data == "menu:screenshot":
        await screenshots.show_screenshot_menu(update, language)
    elif data == "menu:controls":
        await controls.show_controls(update, language)
    elif data == "menu:apps":
        await apps.show_apps(update, context, language)
    elif data == "menu:processes":
        await processes.show_processes(update, language)
    elif data == "menu:clipboard":
        await clipboard.show_clipboard(update, language)
    elif data.startswith("timer:"):
        await screenshots.handle_screenshot_timer(update, context, language, data)
    elif data.startswith("shot:"):
        await screenshots.handle_screenshot(update, context, language, data.removeprefix("shot:"))
    elif data.startswith("action:"):
        await controls.handle_action(update, context, language, data.removeprefix("action:"))
    elif data.startswith("confirm:"):
        await _handle_confirmation(update, context, language, data.removeprefix("confirm:"))
    elif data.startswith("app:"):
        await apps.handle_app(update, context, language, data)
    elif data.startswith("proc:"):
        await processes.handle_process(update, context, language, data)
    elif data.startswith("clipboard:"):
        await clipboard.handle_clipboard(update, context, language, data)
    elif data.startswith("cancel:"):
        context.user_data.pop(INPUT_STATE_KEY, None)
        confirmations_of(context).cancel(update.callback_query.from_user.id)
        await _route_cancel(update, context, language, data.removeprefix("cancel:"))
    else:
        await edit_or_reply(update, t(language, "callback.unknown"), main_menu(language))


async def _show_status(update: Update, language: Language) -> None:
    status = await asyncio.to_thread(collect_status)
    await edit_or_reply(
        update,
        f"{t(language, 'title.status')}\n<pre>{escape(format_status(status))}</pre>",
        back_only_menu(language),
    )


async def _route_cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    target: str,
) -> None:
    if target == "menu:apps":
        await apps.show_apps(update, context, language)
    elif target == "menu:processes":
        await processes.show_processes(update, language)
    elif target == "menu:controls":
        await controls.show_controls(update, language)
    elif target == "menu:clipboard":
        await clipboard.show_clipboard(update, language)
    elif target == "timer:menu":
        await screenshots.show_screenshot_timer(update, context, language)
    else:
        await show_main(update, language)


async def _handle_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    action: str,
) -> None:
    current_user_id = user_id(update)
    if current_user_id is None:
        await edit_or_reply(update, "Access denied", main_menu(language))
        return
    if not confirmations_of(context).confirm(current_user_id, action):
        await edit_or_reply(update, t(language, "confirmation.expired"), main_menu(language))
        return
    if action.startswith("action:"):
        await controls.run_confirmed_action(update, language, action.removeprefix("action:"))
    elif action.startswith("proc:kill:"):
        await processes.kill_confirmed_process(update, language, action)
    elif action.startswith("app:delete:"):
        await apps.delete_confirmed_app(update, context, language, action.removeprefix("app:delete:"))
    elif action.startswith("app:run_admin:"):
        await apps.run_confirmed_app(update, context, language, action.removeprefix("app:run_admin:"), as_admin=True)
    elif action.startswith("app:run:"):
        await apps.run_confirmed_app(update, context, language, action.removeprefix("app:run:"), as_admin=False)
    elif action == "clipboard:clear":
        await clipboard.clear_confirmed_clipboard(update, language)
    else:
        await edit_or_reply(update, t(language, "confirmation.unknown"), main_menu(language))
