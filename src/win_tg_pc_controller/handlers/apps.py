from __future__ import annotations

from html import escape

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..apps import LaunchApp, add_app, delete_app, load_apps, run_app
from ..i18n import Language, t
from .common import (
    INPUT_STATE_KEY,
    button,
    cancel_menu,
    config_of,
    confirm_menu,
    confirmations_of,
    edit_or_reply,
    reply,
)


def apps_menu(language: Language, apps: dict[str, LaunchApp]) -> InlineKeyboardMarkup:
    rows = [
        [button(f"{'🚀' if app.path.exists() else '⚠️'} {app.title}", f"app:run:{app.id}")]
        for app in apps.values()
    ]
    rows.append([button(t(language, "menu.add"), "app:add")])
    rows.append([button(t(language, "menu.back"), "menu:main")])
    return InlineKeyboardMarkup(rows)


def app_launch_menu(language: Language, app_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button(t(language, "menu.run"), f"confirm:app:run:{app_id}")],
            [button(t(language, "menu.run_admin"), f"confirm:app:run_admin:{app_id}")],
            [button(t(language, "menu.delete"), f"app:delete:{app_id}")],
            [button(t(language, "menu.back"), "menu:apps")],
        ]
    )


def apps_of(context: ContextTypes.DEFAULT_TYPE) -> dict[str, LaunchApp]:
    return context.application.bot_data["apps"]


def _reload_apps(context: ContextTypes.DEFAULT_TYPE) -> dict[str, LaunchApp]:
    apps = load_apps(config_of(context).apps_file)
    context.application.bot_data["apps"] = apps
    return apps


async def show_apps(update: Update, context: ContextTypes.DEFAULT_TYPE, language: Language) -> None:
    apps = apps_of(context)
    text = t(language, "title.apps")
    if not apps:
        text += t(language, "apps.empty")
    await edit_or_reply(update, text, apps_menu(language, apps))


async def handle_app(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    data: str,
) -> None:
    confirmations = confirmations_of(context)
    if data == "app:add":
        context.user_data[INPUT_STATE_KEY] = {"type": "add_app_title"}
        await edit_or_reply(update, t(language, "apps.add_prompt"), cancel_menu(language, "menu:apps"))
        return

    if data.startswith("app:delete:"):
        app = apps_of(context).get(data.removeprefix("app:delete:"))
        if app is None:
            await edit_or_reply(update, t(language, "apps.not_found"), apps_menu(language, apps_of(context)))
            return
        confirmations.request(update.callback_query.from_user.id, f"app:delete:{app.id}")
        await edit_or_reply(
            update,
            t(language, "apps.delete_confirm", title=escape(app.title), path=escape(str(app.path))),
            confirm_menu(language, f"app:delete:{app.id}", "menu:apps"),
        )
        return

    if data.startswith("app:run:"):
        app = apps_of(context).get(data.removeprefix("app:run:"))
        if app is None:
            await edit_or_reply(update, t(language, "apps.not_found"), apps_menu(language, apps_of(context)))
            return
        confirmations.request_any(
            update.callback_query.from_user.id,
            [f"app:run:{app.id}", f"app:run_admin:{app.id}"],
        )
        await edit_or_reply(
            update,
            t(language, "apps.confirm", title=escape(app.title), path=escape(str(app.path))),
            app_launch_menu(language, app.id),
        )


async def handle_add_title_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    text: str,
) -> None:
    if not text:
        await reply(update, t(language, "apps.title_empty"), apps_menu(language, apps_of(context)))
        return
    context.user_data[INPUT_STATE_KEY] = {"type": "add_app_path", "title": text}
    await reply(update, t(language, "apps.enter_path", title=escape(text)), cancel_menu(language, "menu:apps"))


async def handle_add_path_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    state: dict,
    text: str,
) -> None:
    try:
        app = add_app(config_of(context).apps_file, state["title"], text)
        apps = _reload_apps(context)
    except ValueError as exc:
        await reply(
            update,
            t(language, "apps.add_failed", error=escape(str(exc))),
            cancel_menu(language, "menu:apps"),
        )
        return
    context.user_data.pop(INPUT_STATE_KEY, None)
    await reply(update, t(language, "apps.added", title=escape(app.title)), apps_menu(language, apps))


async def delete_confirmed_app(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    app_id: str,
) -> None:
    try:
        app = delete_app(config_of(context).apps_file, app_id)
    except ValueError:
        apps = _reload_apps(context)
        await edit_or_reply(update, t(language, "apps.not_found"), apps_menu(language, apps))
        return
    apps = _reload_apps(context)
    await edit_or_reply(update, t(language, "apps.deleted", title=escape(app.title)), apps_menu(language, apps))


async def run_confirmed_app(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    app_id: str,
    as_admin: bool,
) -> None:
    apps = apps_of(context)
    app = apps.get(app_id)
    if app is None:
        await edit_or_reply(update, t(language, "apps.not_found"), apps_menu(language, apps))
        return
    run_app(app, as_admin=as_admin)
    mode = t(language, "apps.mode_admin" if as_admin else "apps.mode_normal")
    await edit_or_reply(
        update,
        t(language, "apps.started", mode=mode, title=escape(app.title)),
        apps_menu(language, apps),
    )
