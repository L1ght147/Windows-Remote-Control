from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ..config import AppConfig
from ..i18n import DEFAULT_LANGUAGE, Language, t
from ..language_store import LanguageStore
from ..security import ConfirmationStore, is_allowed_user


INPUT_STATE_KEY = "input_state"
PROCESS_RESULTS_KEY = "process_results"
SCREENSHOT_TIMER_KEY = "screenshot_timer"
LANGUAGE_STORE_KEY = "language_store"


def button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def main_menu(language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button(t(language, "menu.status"), "menu:status"), button(t(language, "menu.screenshot"), "menu:screenshot")],
            [button(t(language, "menu.controls"), "menu:controls"), button(t(language, "menu.apps"), "menu:apps")],
            [button(t(language, "menu.processes"), "menu:processes"), button(t(language, "menu.clipboard"), "menu:clipboard")],
        ]
    )


def language_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[button("Русский", "language:ru"), button("English", "language:en")]])


def back_only_menu(language: Language, parent: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[button(t(language, "menu.back"), parent)]])


def home_only_menu(language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[button(t(language, "menu.home"), "menu:main")]])


def cancel_menu(language: Language, target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[button(t(language, "menu.cancel"), f"cancel:{target}")]])


def confirm_menu(language: Language, action: str, cancel_to: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button(t(language, "menu.confirm"), f"confirm:{action}"), button(t(language, "menu.cancel"), f"cancel:{cancel_to}")],
            [button(t(language, "menu.back"), cancel_to)],
        ]
    )


def user_id(update: Update) -> int | None:
    if update.effective_user is None:
        return None
    return update.effective_user.id


def config_of(context: ContextTypes.DEFAULT_TYPE) -> AppConfig:
    return context.application.bot_data["config"]


def confirmations_of(context: ContextTypes.DEFAULT_TYPE) -> ConfirmationStore:
    return context.application.bot_data["confirmations"]


def language_store_of(bot_data: dict) -> LanguageStore:
    return bot_data[LANGUAGE_STORE_KEY]


def stored_language(context: ContextTypes.DEFAULT_TYPE, update: Update) -> Language | None:
    current_user_id = user_id(update)
    if current_user_id is None:
        return None
    return language_store_of(context.application.bot_data).get(current_user_id)


def language_of(context: ContextTypes.DEFAULT_TYPE, update: Update) -> Language:
    return stored_language(context, update) or DEFAULT_LANGUAGE


def is_allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    return is_allowed_user(user_id(update), config_of(context).allowed_user_id)


async def reject(update: Update) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer("Access denied", show_alert=True)
        return
    if update.effective_message is not None:
        await update.effective_message.reply_text("Access denied")


async def edit_or_reply(update: Update, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    query = update.callback_query
    if query is not None and query.message is not None:
        if query.message.text is None:
            await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            return
        try:
            await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            return
        except BadRequest as exc:
            if "Message is not modified" in str(exc):
                return
            raise
    if update.effective_message is not None:
        await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def reply(update: Update, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    if update.effective_message is not None:
        await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def show_main(update: Update, language: Language) -> None:
    await edit_or_reply(update, t(language, "title.main"), main_menu(language))


async def show_language_selection(update: Update, language: Language) -> None:
    await edit_or_reply(update, t(language, "language.choose"), language_menu())
