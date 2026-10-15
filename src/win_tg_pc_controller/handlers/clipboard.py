from __future__ import annotations

from html import escape

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..clipboard import clear_clipboard, format_clipboard_text, get_clipboard_text, set_clipboard_text
from ..i18n import Language, t
from .common import (
    INPUT_STATE_KEY,
    button,
    cancel_menu,
    confirm_menu,
    confirmations_of,
    edit_or_reply,
    reply,
)


def clipboard_menu(language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button(t(language, "menu.show"), "clipboard:show"), button(t(language, "menu.replace"), "clipboard:set")],
            [button(t(language, "menu.clear"), "clipboard:clear")],
            [button(t(language, "menu.back"), "menu:main")],
        ]
    )


async def show_clipboard(update: Update, language: Language) -> None:
    await edit_or_reply(update, t(language, "title.clipboard"), clipboard_menu(language))


async def handle_clipboard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    data: str,
) -> None:
    if data == "clipboard:show":
        text = format_clipboard_text(get_clipboard_text(), language)
        await edit_or_reply(
            update,
            f"{t(language, 'title.clipboard')}\n<pre>{escape(text)}</pre>",
            clipboard_menu(language),
        )
        return

    if data == "clipboard:set":
        context.user_data[INPUT_STATE_KEY] = {"type": "clipboard_set"}
        await edit_or_reply(update, t(language, "clipboard.set_prompt"), cancel_menu(language, "menu:clipboard"))
        return

    if data == "clipboard:clear":
        confirmations_of(context).request(update.callback_query.from_user.id, "clipboard:clear")
        await edit_or_reply(
            update,
            t(language, "clipboard.clear_confirm"),
            confirm_menu(language, "clipboard:clear", "menu:clipboard"),
        )


async def handle_set_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    text: str,
) -> None:
    try:
        set_clipboard_text(text)
    except RuntimeError as exc:
        await reply(update, t(language, "clipboard.unavailable", error=escape(str(exc))), clipboard_menu(language))
        return
    context.user_data.pop(INPUT_STATE_KEY, None)
    await reply(update, t(language, "clipboard.updated"), clipboard_menu(language))


async def clear_confirmed_clipboard(update: Update, language: Language) -> None:
    clear_clipboard()
    await edit_or_reply(update, t(language, "clipboard.cleared"), clipboard_menu(language))
