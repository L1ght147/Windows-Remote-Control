from __future__ import annotations

from html import escape

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..actions import DANGEROUS_ACTIONS, run_control_action
from ..i18n import Language, t
from .common import button, confirm_menu, confirmations_of, edit_or_reply, main_menu, show_main, user_id


def controls_menu(language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button(t(language, "menu.lock"), "action:lock"), button(t(language, "menu.sleep"), "action:sleep")],
            [button(t(language, "menu.reboot"), "action:reboot"), button(t(language, "menu.shutdown"), "action:shutdown")],
            [button(t(language, "menu.power_timer"), "ptimer:menu")],
            [button(t(language, "menu.back"), "menu:main")],
        ]
    )


async def show_controls(update: Update, language: Language) -> None:
    await edit_or_reply(update, t(language, "title.controls"), controls_menu(language))


async def handle_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    action: str,
) -> None:
    confirmations = confirmations_of(context)
    current_user_id = user_id(update)
    if action == "cancel":
        if current_user_id is not None:
            confirmations.cancel(current_user_id)
        await show_main(update, language)
        return
    if action in DANGEROUS_ACTIONS:
        confirmations.request(update.callback_query.from_user.id, f"action:{action}")
        await edit_or_reply(
            update,
            t(language, "action.confirm", action=escape(action)),
            confirm_menu(language, f"action:{action}", "menu:controls"),
        )
        return
    run_control_action(action)
    await edit_or_reply(update, t(language, "action.done", action=escape(action)), controls_menu(language))


async def run_confirmed_action(update: Update, language: Language, action: str) -> None:
    run_control_action(action)
    await edit_or_reply(update, t(language, "action.done", action=escape(action)), main_menu(language))
