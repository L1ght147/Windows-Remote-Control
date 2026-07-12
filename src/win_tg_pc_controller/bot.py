from __future__ import annotations

import logging
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .actions import DANGEROUS_ACTIONS, run_control_action
from .apps import LaunchApp, add_app, delete_app, load_apps, run_app
from .clipboard import clear_clipboard, format_clipboard_text, get_clipboard_text, set_clipboard_text
from .config import AppConfig, load_config
from .i18n import DEFAULT_LANGUAGE, Language, is_supported_language, localize_text
from .language_store import LanguageStore
from .processes import ProcessCandidate, describe_process, get_foreground_process, search_processes, terminate_process
from .screenshot import capture_screenshot_png, list_monitors
from .security import ConfirmationStore, is_allowed_user
from .status import collect_status, format_status


LOGGER = logging.getLogger(__name__)
INPUT_STATE_KEY = "input_state"
PROCESS_RESULTS_KEY = "process_results"
LANGUAGE_STORE: LanguageStore | None = None


def _language_store() -> LanguageStore:
    if LANGUAGE_STORE is None:
        raise RuntimeError("language store is not initialized")
    return LANGUAGE_STORE


def _stored_language(user_id: int | None) -> Language | None:
    if user_id is None:
        return None
    return _language_store().get(user_id)


def _language(update: Update) -> Language:
    return _stored_language(_user_id(update)) or DEFAULT_LANGUAGE


def _localized_markup(language: Language, reply_markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
    if reply_markup is None or language == "ru":
        return reply_markup
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(localize_text(language, button.text), callback_data=button.callback_data)
                for button in row
            ]
            for row in reply_markup.inline_keyboard
        ]
    )


def language_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[_button("Русский", "language:ru"), _button("English", "language:en")]]
    )


def _button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_button("🖥 Статус", "menu:status"), _button("📸 Скриншот", "menu:screenshot")],
            [_button("⚙️ Управление", "menu:controls"), _button("🚀 Запуск программ", "menu:apps")],
            [_button("🛑 Завершить процесс", "menu:processes"), _button("📋 Буфер обмена", "menu:clipboard")],
        ]
    )


def back_menu(parent: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_button("⬅️ Назад", parent), _button("🏠 Главное меню", "menu:main")]])


def back_only_menu(parent: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_button("⬅️ Назад", parent)]])


def home_only_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_button("\U0001f3e0 \u0413\u043b\u0430\u0432\u043d\u043e\u0435 \u043c\u0435\u043d\u044e", "menu:main")]])


def controls_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_button("🔒 Заблокировать", "action:lock"), _button("🌙 Сон", "action:sleep")],
            [_button("🔁 Перезагрузка", "action:reboot"), _button("⏻ Выключить", "action:shutdown")],
            [_button("⬅️ Назад", "menu:main")],
        ]
    )


def confirm_menu(action: str, cancel_to: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_button("✅ Подтвердить", f"confirm:{action}"), _button("❌ Отмена", f"cancel:{cancel_to}")],
            [_button("⬅️ Назад", cancel_to)],
        ]
    )


def screenshot_menu() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for monitor in list_monitors():
        if monitor.is_all:
            text = f"🖼 Все мониторы ({monitor.width}x{monitor.height})"
        else:
            text = f"📺 Монитор {monitor.id}: {monitor.width}x{monitor.height}"
        rows.append([_button(text, f"shot:{monitor.id}")])
    rows.append([_button("⬅️ Назад", "menu:main")])
    return InlineKeyboardMarkup(rows)


def apps_menu(apps: dict[str, LaunchApp]) -> InlineKeyboardMarkup:
    rows = [[_button(f"🚀 {app.title}", f"app:run:{app.id}")] for app in apps.values()]
    rows.append([_button("➕ Добавить", "app:add")])
    rows.append([_button("⬅️ Назад", "menu:main")])
    return InlineKeyboardMarkup(rows)


def app_launch_menu(app_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_button("▶️ Запустить", f"confirm:app:run:{app_id}")],
            [_button("🛡 Запустить от администратора", f"confirm:app:run_admin:{app_id}")],
            [_button("\U0001f5d1 \u0423\u0434\u0430\u043b\u0438\u0442\u044c", f"app:delete:{app_id}")],
            [_button("⬅️ Назад", "menu:apps")],
        ]
    )


def processes_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_button("🎯 Текущий в фокусе", "proc:foreground")],
            [_button("🔎 Найти процесс", "proc:search")],
            [_button("⬅️ Назад", "menu:main")],
        ]
    )


def clipboard_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_button("👁 Показать", "clipboard:show"), _button("✏️ Заменить", "clipboard:set")],
            [_button("🧹 Очистить", "clipboard:clear")],
            [_button("⬅️ Назад", "menu:main")],
        ]
    )


def process_results_menu(results: list[ProcessCandidate]) -> InlineKeyboardMarkup:
    rows = [
        [_button(f"🛑 {candidate.name} | PID {candidate.pid}", f"proc:pick:{candidate.pid}")]
        for candidate in results
    ]
    rows.append([_button("🔎 Новый поиск", "proc:search")])
    rows.append([_button("⬅️ Назад", "menu:processes")])
    return InlineKeyboardMarkup(rows)


def _user_id(update: Update) -> int | None:
    if update.effective_user is None:
        return None
    return update.effective_user.id


async def _reject(update: Update) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer("Access denied", show_alert=True)
        return
    if update.effective_message is not None:
        await update.effective_message.reply_text("Access denied")


def _allowed(update: Update, config: AppConfig) -> bool:
    return is_allowed_user(_user_id(update), config.allowed_user_id)


async def _edit_or_reply(update: Update, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    language = _language(update)
    text = localize_text(language, text)
    reply_markup = _localized_markup(language, reply_markup)
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


async def _reply(update: Update, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    language = _language(update)
    text = localize_text(language, text)
    reply_markup = _localized_markup(language, reply_markup)
    if update.effective_message is not None:
        await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def _show_main(update: Update) -> None:
    await _edit_or_reply(update, "🖥 <b>Windows Telegram PC Controller</b>", main_menu())


async def _show_language_selection(update: Update) -> None:
    await _edit_or_reply(update, "🌐 <b>Выберите язык / Choose a language</b>", language_menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: AppConfig = context.application.bot_data["config"]
    if not _allowed(update, config):
        await _reject(update)
        return
    context.user_data.pop(INPUT_STATE_KEY, None)
    if _stored_language(_user_id(update)) is None:
        await _show_language_selection(update)
        return
    await _show_main(update)


async def language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: AppConfig = context.application.bot_data["config"]
    if not _allowed(update, config):
        await _reject(update)
        return
    context.user_data.pop(INPUT_STATE_KEY, None)
    context.application.bot_data["confirmations"].cancel(_user_id(update))
    await _show_language_selection(update)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: AppConfig = context.application.bot_data["config"]
    if not _allowed(update, config):
        await _reject(update)
        return

    if _stored_language(_user_id(update)) is None:
        await _show_language_selection(update)
        return

    state = context.user_data.get(INPUT_STATE_KEY)
    text = (update.effective_message.text or "").strip()
    if not state:
        await _reply(update, "Используй меню:", main_menu())
        return

    if state["type"] == "add_app_title":
        if not text:
            await _reply(update, "Название не должно быть пустым.", apps_menu(_apps(context)))
            return
        context.user_data[INPUT_STATE_KEY] = {"type": "add_app_path", "title": text}
        await _reply(
            update,
            f"🚀 Название: <b>{escape(text)}</b>\nТеперь отправь полный путь к .exe, .bat или .lnk.",
            InlineKeyboardMarkup([[_button("❌ Отмена", "cancel:menu:apps")]]),
        )
        return

    if state["type"] == "add_app_path":
        title = state["title"]
        try:
            app = add_app(config.apps_file, title, text)
            context.application.bot_data["apps"] = load_apps(config.apps_file)
            context.user_data.pop(INPUT_STATE_KEY, None)
            await _reply(
                update,
                f"✅ Добавлено: <b>{escape(app.title)}</b>",
                apps_menu(_apps(context)),
            )
        except ValueError as exc:
            await _reply(
                update,
                f"❌ Не удалось добавить программу: {escape(str(exc))}",
                InlineKeyboardMarkup([[_button("❌ Отмена", "cancel:menu:apps")]]),
            )
        return

    if state["type"] == "process_search":
        results = search_processes(text)
        context.user_data.pop(INPUT_STATE_KEY, None)
        context.user_data[PROCESS_RESULTS_KEY] = {candidate.pid: candidate for candidate in results}
        if not results:
            await _reply(update, "Ничего не найдено.", processes_menu())
            return
        await _reply(
            update,
            "🛑 <b>Найденные процессы</b>\nВыбери процесс для завершения:",
            process_results_menu(results),
        )
        return

    if state["type"] == "clipboard_set":
        try:
            set_clipboard_text(text)
            context.user_data.pop(INPUT_STATE_KEY, None)
            await _reply(update, "✅ Буфер обмена обновлен.", clipboard_menu())
        except RuntimeError as exc:
            await _reply(
                update,
                f"❌ Буфер обмена недоступен: {escape(str(exc))}",
                clipboard_menu(),
            )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config: AppConfig = context.application.bot_data["config"]
    confirmations: ConfirmationStore = context.application.bot_data["confirmations"]

    query = update.callback_query
    if query is None:
        return

    if not _allowed(update, config):
        await _reject(update)
        return

    await query.answer()
    data = query.data or ""
    if data.startswith("language:"):
        selected_language = data.removeprefix("language:")
        if not is_supported_language(selected_language):
            await _show_language_selection(update)
            return
        _language_store().set(query.from_user.id, selected_language)
        context.user_data.pop(INPUT_STATE_KEY, None)
        confirmations.cancel(query.from_user.id)
        await _show_main(update)
        return
    if _stored_language(_user_id(update)) is None:
        await _show_language_selection(update)
        return

    try:
        if data == "menu:main":
            context.user_data.pop(INPUT_STATE_KEY, None)
            await _show_main(update)
        elif data == "menu:status":
            await _edit_or_reply(update, f"🖥 <b>Статус ПК</b>\n<pre>{escape(format_status(collect_status()))}</pre>", back_only_menu())
        elif data == "menu:screenshot":
            await _edit_or_reply(update, "📸 <b>Выбери монитор для скриншота</b>", screenshot_menu())
        elif data == "menu:controls":
            await _edit_or_reply(update, "⚙️ <b>Управление ПК</b>", controls_menu())
        elif data == "menu:apps":
            await _show_apps(update, context)
        elif data == "menu:processes":
            await _edit_or_reply(update, "🛑 <b>Завершить процесс</b>", processes_menu())
        elif data == "menu:clipboard":
            await _edit_or_reply(update, "📋 <b>Буфер обмена</b>", clipboard_menu())
        elif data.startswith("shot:"):
            await _handle_screenshot(update, query, data.removeprefix("shot:"))
        elif data.startswith("action:"):
            await _handle_action(update, query, confirmations, _user_id(update), data.removeprefix("action:"))
        elif data.startswith("confirm:"):
            await _handle_confirmation(update, context, confirmations, _user_id(update), data.removeprefix("confirm:"))
        elif data.startswith("app:"):
            await _handle_app(update, context, confirmations, data)
        elif data.startswith("proc:"):
            await _handle_process(update, context, confirmations, data)
        elif data.startswith("clipboard:"):
            await _handle_clipboard(update, context, confirmations, data)
        elif data.startswith("cancel:"):
            context.user_data.pop(INPUT_STATE_KEY, None)
            confirmations.cancel(query.from_user.id)
            await _route_cancel(update, context, data.removeprefix("cancel:"))
        else:
            await _edit_or_reply(update, "Неизвестное действие.", main_menu())
    except (RuntimeError, ValueError) as exc:
        LOGGER.info("Callback rejected: %s", exc)
        await _edit_or_reply(update, f"❌ {escape(str(exc))}", main_menu())
    except Exception:
        LOGGER.exception("Callback failed")
        await _edit_or_reply(update, "❌ Действие не выполнено.", main_menu())


def _apps(context: ContextTypes.DEFAULT_TYPE) -> dict[str, LaunchApp]:
    return context.application.bot_data["apps"]


async def _show_apps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    apps = _apps(context)
    text = "🚀 <b>Запуск программ</b>"
    if not apps:
        text += "\nСписок пока пуст. Нажми «Добавить»."
    await _edit_or_reply(update, text, apps_menu(apps))


async def _route_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str) -> None:
    if target == "menu:apps":
        await _edit_or_reply(update, "🚀 <b>Запуск программ</b>", apps_menu(_apps(context)))
    elif target == "menu:processes":
        await _edit_or_reply(update, "🛑 <b>Завершить процесс</b>", processes_menu())
    elif target == "menu:controls":
        await _edit_or_reply(update, "⚙️ <b>Управление ПК</b>", controls_menu())
    elif target == "menu:clipboard":
        await _edit_or_reply(update, "📋 <b>Буфер обмена</b>", clipboard_menu())
    else:
        await _show_main(update)


async def _handle_screenshot(update: Update, query, monitor_id_text: str) -> None:
    monitor_id = int(monitor_id_text)
    reply_markup = _localized_markup(_language(update), home_only_menu())
    await query.message.reply_photo(
        photo=capture_screenshot_png(monitor_id),
        reply_markup=reply_markup,
    )


async def _handle_action(update: Update, query, confirmations: ConfirmationStore, user_id: int | None, action: str) -> None:
    if action == "cancel":
        if user_id is not None:
            confirmations.cancel(user_id)
        await _show_main(update)
        return
    if action in DANGEROUS_ACTIONS:
        confirmations.request(query.from_user.id, f"action:{action}")
        await _edit_or_reply(update, f"⚠️ <b>Подтвердить действие:</b> {escape(action)}?", confirm_menu(f"action:{action}", "menu:controls"))
        return
    run_control_action(action)
    await _edit_or_reply(update, f"✅ Выполнено: {escape(action)}", controls_menu())


async def _handle_confirmation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    confirmations: ConfirmationStore,
    user_id: int | None,
    action: str,
) -> None:
    if user_id is None:
        await _edit_or_reply(update, "Access denied", main_menu())
        return
    if not confirmations.confirm(user_id, action):
        await _edit_or_reply(update, "⏱ Подтверждение истекло или не найдено.", main_menu())
        return
    if action.startswith("action:"):
        control_action = action.removeprefix("action:")
        run_control_action(control_action)
        await _edit_or_reply(update, f"✅ Выполнено: {escape(control_action)}", main_menu())
        return
    if action.startswith("proc:kill:"):
        pid = int(action.removeprefix("proc:kill:"))
        terminate_process(pid)
        await _edit_or_reply(update, f"✅ Процесс PID {pid} завершен.", processes_menu())
        return
    if action.startswith("app:delete:"):
        app_id = action.removeprefix("app:delete:")
        await _delete_confirmed_app(update, context, app_id)
        return
    if action.startswith("app:run_admin:"):
        app_id = action.removeprefix("app:run_admin:")
        await _run_confirmed_app(update, context, app_id, as_admin=True)
        return
    if action.startswith("app:run:"):
        app_id = action.removeprefix("app:run:")
        await _run_confirmed_app(update, context, app_id, as_admin=False)
        return
    if action == "clipboard:clear":
        clear_clipboard()
        await _edit_or_reply(update, "✅ Буфер обмена очищен.", clipboard_menu())
        return
    await _edit_or_reply(update, "Неизвестное подтверждение.", main_menu())


async def _handle_app(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    confirmations: ConfirmationStore,
    data: str,
) -> None:
    if data == "app:add":
        context.user_data[INPUT_STATE_KEY] = {"type": "add_app_title"}
        await _edit_or_reply(
            update,
            "➕ <b>Добавление программы</b>\nОтправь название программы следующим сообщением.",
            InlineKeyboardMarkup([[_button("❌ Отмена", "cancel:menu:apps")]]),
        )
        return

    if data.startswith("app:delete:"):
        app_id = data.removeprefix("app:delete:")
        app = _apps(context).get(app_id)
        if app is None:
            await _edit_or_reply(update, "\u041f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430.", apps_menu(_apps(context)))
            return
        confirmations.request(update.callback_query.from_user.id, f"app:delete:{app.id}")
        await _edit_or_reply(
            update,
            (
                "\u26a0\ufe0f <b>\u0423\u0434\u0430\u043b\u0438\u0442\u044c \u043f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0443 \u0438\u0437 \u0441\u043f\u0438\u0441\u043a\u0430?</b>\n"
                f"<b>{escape(app.title)}</b>\n"
                f"<pre>{escape(str(app.path))}</pre>\n"
                "\u0424\u0430\u0439\u043b \u043d\u0430 \u0434\u0438\u0441\u043a\u0435 \u0443\u0434\u0430\u043b\u0435\u043d \u043d\u0435 \u0431\u0443\u0434\u0435\u0442."
            ),
            confirm_menu(f"app:delete:{app.id}", "menu:apps"),
        )
        return

    if data.startswith("app:run:"):
        app_id = data.removeprefix("app:run:")
        app = _apps(context).get(app_id)
        if app is None:
            await _edit_or_reply(update, "Программа не найдена.", apps_menu(_apps(context)))
            return
        confirmations.request_any(
            update.callback_query.from_user.id,
            [f"app:run:{app.id}", f"app:run_admin:{app.id}"],
        )
        await _edit_or_reply(
            update,
            (
                "⚠️ <b>Запустить программу?</b>\n"
                f"<b>{escape(app.title)}</b>\n"
                f"<pre>{escape(str(app.path))}</pre>"
            ),
            app_launch_menu(app.id),
        )


async def _delete_confirmed_app(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    app_id: str,
) -> None:
    config: AppConfig = context.application.bot_data["config"]
    try:
        app = delete_app(config.apps_file, app_id)
    except ValueError:
        context.application.bot_data["apps"] = load_apps(config.apps_file)
        await _edit_or_reply(update, "\u041f\u0440\u043e\u0433\u0440\u0430\u043c\u043c\u0430 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430.", apps_menu(_apps(context)))
        return
    context.application.bot_data["apps"] = load_apps(config.apps_file)
    await _edit_or_reply(
        update,
        f"\u2705 \u0423\u0434\u0430\u043b\u0435\u043d\u043e \u0438\u0437 \u0441\u043f\u0438\u0441\u043a\u0430: <b>{escape(app.title)}</b>",
        apps_menu(_apps(context)),
    )


async def _run_confirmed_app(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    app_id: str,
    as_admin: bool,
) -> None:
    apps = _apps(context)
    app = apps.get(app_id)
    if app is None:
        await _edit_or_reply(update, "Программа не найдена.", apps_menu(apps))
        return
    run_app(app, as_admin=as_admin)
    mode = "от администратора" if as_admin else "обычно"
    await _edit_or_reply(
        update,
        f"✅ Запущено ({mode}): <b>{escape(app.title)}</b>",
        apps_menu(apps),
    )


async def _handle_process(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    confirmations: ConfirmationStore,
    data: str,
) -> None:
    if data == "proc:foreground":
        candidate = get_foreground_process()
        confirmations.request(update.callback_query.from_user.id, f"proc:kill:{candidate.pid}")
        await _edit_or_reply(
            update,
            f"⚠️ <b>Завершить текущий процесс в фокусе?</b>\n<pre>{escape(describe_process(candidate))}</pre>",
            confirm_menu(f"proc:kill:{candidate.pid}", "menu:processes"),
        )
        return

    if data == "proc:search":
        context.user_data[INPUT_STATE_KEY] = {"type": "process_search"}
        await _edit_or_reply(
            update,
            "🔎 <b>Поиск процесса</b>\nОтправь часть имени процесса или пути следующим сообщением.",
            InlineKeyboardMarkup([[_button("❌ Отмена", "cancel:menu:processes")]]),
        )
        return

    if data.startswith("proc:pick:"):
        pid = int(data.removeprefix("proc:pick:"))
        results: dict[int, ProcessCandidate] = context.user_data.get(PROCESS_RESULTS_KEY, {})
        candidate = results.get(pid)
        if candidate is None:
            await _edit_or_reply(update, "Процесс больше не найден в результатах поиска.", processes_menu())
            return
        confirmations.request(update.callback_query.from_user.id, f"proc:kill:{pid}")
        await _edit_or_reply(
            update,
            f"⚠️ <b>Завершить процесс?</b>\n<pre>{escape(describe_process(candidate))}</pre>",
            confirm_menu(f"proc:kill:{pid}", "menu:processes"),
        )


async def _handle_clipboard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    confirmations: ConfirmationStore,
    data: str,
) -> None:
    if data == "clipboard:show":
        text = format_clipboard_text(get_clipboard_text(), _language(update))
        await _edit_or_reply(
            update,
            f"📋 <b>Буфер обмена</b>\n<pre>{escape(text)}</pre>",
            clipboard_menu(),
        )
        return

    if data == "clipboard:set":
        context.user_data[INPUT_STATE_KEY] = {"type": "clipboard_set"}
        await _edit_or_reply(
            update,
            "✏️ <b>Заменить буфер обмена</b>\nОтправь новый текст следующим сообщением.",
            InlineKeyboardMarkup([[_button("❌ Отмена", "cancel:menu:clipboard")]]),
        )
        return

    if data == "clipboard:clear":
        confirmations.request(update.callback_query.from_user.id, "clipboard:clear")
        await _edit_or_reply(
            update,
            "⚠️ <b>Очистить буфер обмена?</b>",
            confirm_menu("clipboard:clear", "menu:clipboard"),
        )


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


def build_application(config: AppConfig) -> Application:
    apps = load_apps(config.apps_file)
    app = (
        Application.builder()
        .token(config.telegram_bot_token)
        .connect_timeout(config.telegram_timeout_seconds)
        .read_timeout(config.telegram_timeout_seconds)
        .write_timeout(config.telegram_timeout_seconds)
        .pool_timeout(config.telegram_timeout_seconds)
        .build()
    )
    global LANGUAGE_STORE
    LANGUAGE_STORE = LanguageStore(config.user_settings_file)
    app.bot_data["config"] = config
    app.bot_data["language_store"] = LANGUAGE_STORE
    app.bot_data["confirmations"] = ConfirmationStore(config.confirmation_ttl_seconds)
    app.bot_data["apps"] = apps
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(handle_error)
    return app


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    config = load_config()
    app = build_application(config)
    LOGGER.info("Starting Windows Telegram PC Controller")
    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            bootstrap_retries=config.telegram_bootstrap_retries,
            timeout=int(config.telegram_timeout_seconds),
        )
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
