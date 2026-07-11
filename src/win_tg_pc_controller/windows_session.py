from __future__ import annotations

import ctypes
import getpass
import os
import platform
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class WindowsSessionInfo:
    user: str
    is_windows: bool
    is_admin: bool | None
    process_id: int
    process_session_id: int | None
    active_console_session_id: int | None
    desktop_accessible: bool | None
    explorer_sessions: tuple[int, ...]
    note: str | None = None

    @property
    def is_active_user_session(self) -> bool | None:
        if self.process_session_id is None or self.active_console_session_id is None:
            return None
        return self.process_session_id == self.active_console_session_id


def _process_session_id(pid: int) -> int | None:
    try:
        session_id = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.ProcessIdToSessionId(  # type: ignore[attr-defined]
            ctypes.c_ulong(pid),
            ctypes.byref(session_id),
        )
    except OSError:
        return None
    if not ok:
        return None
    return int(session_id.value)


def _active_console_session_id() -> int | None:
    try:
        value = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()  # type: ignore[attr-defined]
    except OSError:
        return None
    if value == 0xFFFFFFFF:
        return None
    return int(value)


def _is_admin() -> bool | None:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except OSError:
        return None


def _desktop_accessible() -> bool | None:
    # DESKTOP_READOBJECTS | DESKTOP_WRITEOBJECTS is enough to detect whether the
    # process can open the current input desktop without trying to switch it.
    desired_access = 0x0001 | 0x0080
    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        desktop = user32.OpenInputDesktop(0, False, desired_access)
    except OSError:
        return None
    if not desktop:
        return False
    user32.CloseDesktop(desktop)
    return True


def _explorer_sessions() -> tuple[int, ...]:
    sessions: set[int] = set()
    for process in psutil.process_iter(["pid", "name"]):
        try:
            if (process.info.get("name") or "").lower() != "explorer.exe":
                continue
            session_id = _process_session_id(int(process.info["pid"]))
            if session_id is not None:
                sessions.add(session_id)
        except (psutil.Error, OSError, TypeError, ValueError):
            continue
    return tuple(sorted(sessions))


def collect_windows_session_info() -> WindowsSessionInfo:
    pid = os.getpid()
    try:
        user = psutil.Process(pid).username()
    except psutil.Error:
        user = getpass.getuser()

    if platform.system() != "Windows":
        return WindowsSessionInfo(
            user=user,
            is_windows=False,
            is_admin=None,
            process_id=pid,
            process_session_id=None,
            active_console_session_id=None,
            desktop_accessible=None,
            explorer_sessions=(),
            note="not Windows",
        )

    return WindowsSessionInfo(
        user=user,
        is_windows=True,
        is_admin=_is_admin(),
        process_id=pid,
        process_session_id=_process_session_id(pid),
        active_console_session_id=_active_console_session_id(),
        desktop_accessible=_desktop_accessible(),
        explorer_sessions=_explorer_sessions(),
    )


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


def format_windows_session(info: WindowsSessionInfo) -> str:
    explorer = ", ".join(str(session_id) for session_id in info.explorer_sessions) or "none"
    lines = [
        "Windows session",
        f"User: {info.user}",
        f"PID: {info.process_id}",
        f"Admin: {_yes_no(info.is_admin)}",
        f"Bot session: {info.process_session_id if info.process_session_id is not None else 'unknown'}",
        f"Active console session: {info.active_console_session_id if info.active_console_session_id is not None else 'unknown'}",
        f"Bot in active session: {_yes_no(info.is_active_user_session)}",
        f"Desktop accessible: {_yes_no(info.desktop_accessible)}",
        f"Explorer sessions: {explorer}",
    ]
    if info.note:
        lines.append(f"Note: {info.note}")
    return "\n".join(lines)


def screenshot_unavailable_reason(info: WindowsSessionInfo) -> str | None:
    if not info.is_windows:
        return None
    if info.is_active_user_session is False:
        return (
            "бот запущен не в активной пользовательской сессии. "
            "Используйте AutoLogon + install_user_autostart.bat, чтобы бот запускался после входа пользователя."
        )
    if info.desktop_accessible is False:
        return (
            "рабочий стол недоступен. Обычно это значит, что Windows заблокирована, "
            "открыт secure desktop/UAC или удаленный доступ переключил сессию."
        )
    return None
