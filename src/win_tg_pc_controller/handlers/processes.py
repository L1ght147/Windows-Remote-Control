from __future__ import annotations

import asyncio
from html import escape

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..i18n import Language, t
from ..processes import ProcessCandidate, describe_process, get_foreground_process, search_processes, terminate_process
from .common import (
    INPUT_STATE_KEY,
    PROCESS_RESULTS_KEY,
    button,
    cancel_menu,
    confirm_menu,
    confirmations_of,
    edit_or_reply,
    reply,
)


def processes_menu(language: Language) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [button(t(language, "menu.foreground"), "proc:foreground")],
            [button(t(language, "menu.search"), "proc:search")],
            [button(t(language, "menu.back"), "menu:main")],
        ]
    )


def process_results_menu(language: Language, results: list[ProcessCandidate]) -> InlineKeyboardMarkup:
    rows = [
        [button(f"🛑 {candidate.name} | PID {candidate.pid}", f"proc:pick:{candidate.pid}")]
        for candidate in results
    ]
    rows.append([button(t(language, "menu.new_search"), "proc:search")])
    rows.append([button(t(language, "menu.back"), "menu:processes")])
    return InlineKeyboardMarkup(rows)


def kill_action(candidate: ProcessCandidate) -> str:
    create_time = "" if candidate.create_time is None else repr(candidate.create_time)
    return f"proc:kill:{candidate.pid}:{create_time}"


def parse_kill_action(action: str) -> tuple[int, float | None]:
    pid_text, _, create_time_text = action.removeprefix("proc:kill:").partition(":")
    return int(pid_text), float(create_time_text) if create_time_text else None


async def show_processes(update: Update, language: Language) -> None:
    await edit_or_reply(update, t(language, "title.processes"), processes_menu(language))


async def handle_process(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    data: str,
) -> None:
    confirmations = confirmations_of(context)
    if data == "proc:foreground":
        candidate = get_foreground_process()
        action = kill_action(candidate)
        confirmations.request(update.callback_query.from_user.id, action)
        await edit_or_reply(
            update,
            t(language, "process.foreground_confirm", process=escape(describe_process(candidate))),
            confirm_menu(language, action, "menu:processes"),
        )
        return

    if data == "proc:search":
        context.user_data[INPUT_STATE_KEY] = {"type": "process_search"}
        await edit_or_reply(update, t(language, "process.search_prompt"), cancel_menu(language, "menu:processes"))
        return

    if data.startswith("proc:pick:"):
        pid = int(data.removeprefix("proc:pick:"))
        results: dict[int, ProcessCandidate] = context.user_data.get(PROCESS_RESULTS_KEY, {})
        candidate = results.get(pid)
        if candidate is None:
            await edit_or_reply(update, t(language, "process.result_expired"), processes_menu(language))
            return
        action = kill_action(candidate)
        confirmations.request(update.callback_query.from_user.id, action)
        await edit_or_reply(
            update,
            t(language, "process.confirm", process=escape(describe_process(candidate))),
            confirm_menu(language, action, "menu:processes"),
        )


async def handle_search_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    language: Language,
    text: str,
) -> None:
    results = await asyncio.to_thread(search_processes, text)
    context.user_data.pop(INPUT_STATE_KEY, None)
    context.user_data[PROCESS_RESULTS_KEY] = {candidate.pid: candidate for candidate in results}
    if not results:
        await reply(update, t(language, "process.none"), processes_menu(language))
        return
    await reply(update, t(language, "process.results"), process_results_menu(language, results))


async def kill_confirmed_process(update: Update, language: Language, action: str) -> None:
    pid, create_time = parse_kill_action(action)
    await asyncio.to_thread(terminate_process, pid, create_time)
    await edit_or_reply(update, t(language, "process.terminated", pid=pid), processes_menu(language))
