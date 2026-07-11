from __future__ import annotations

import ctypes
import os
import platform
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class ProcessCandidate:
    pid: int
    name: str
    exe: str
    cmdline: str


DENIED_PIDS = {0, 4}


def _safe_join_cmdline(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    if isinstance(value, tuple):
        return " ".join(str(part) for part in value)
    return ""


def search_processes(query: str, limit: int = 10) -> list[ProcessCandidate]:
    needle = query.strip().casefold()
    if len(needle) < 2:
        return []

    matches: list[ProcessCandidate] = []
    for process in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            info = process.info
            name = str(info.get("name") or "")
            exe = str(info.get("exe") or "")
            cmdline = _safe_join_cmdline(info.get("cmdline"))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        haystack = " ".join([name, exe, cmdline]).casefold()
        if needle not in haystack:
            continue
        matches.append(
            ProcessCandidate(
                pid=int(info["pid"]),
                name=name or "unknown",
                exe=exe,
                cmdline=cmdline,
            )
        )
        if len(matches) >= limit:
            break
    return matches


def describe_process(candidate: ProcessCandidate) -> str:
    location = candidate.exe or candidate.cmdline or "path unavailable"
    if len(location) > 80:
        location = location[:77] + "..."
    return f"{candidate.name} | PID {candidate.pid}\n{location}"


def can_terminate_process(pid: int) -> tuple[bool, str | None]:
    if pid in DENIED_PIDS:
        return False, "system process is protected"
    if pid == os.getpid():
        return False, "refusing to terminate bot process"
    try:
        process = psutil.Process(pid)
        process.name()
    except psutil.NoSuchProcess:
        return False, "process no longer exists"
    except psutil.AccessDenied:
        return False, "access denied"
    return True, None


def process_candidate_from_pid(pid: int) -> ProcessCandidate:
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess as exc:
        raise RuntimeError("process no longer exists") from exc
    try:
        name = process.name()
    except psutil.AccessDenied:
        name = "access denied"
    except psutil.NoSuchProcess as exc:
        raise RuntimeError("process no longer exists") from exc
    try:
        exe = process.exe()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        exe = ""
    try:
        cmdline = _safe_join_cmdline(process.cmdline())
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        cmdline = ""
    return ProcessCandidate(pid=pid, name=name or "unknown", exe=exe, cmdline=cmdline)


def get_foreground_process() -> ProcessCandidate:
    if platform.system() != "Windows":
        raise RuntimeError("foreground process lookup is only supported on Windows")

    window = ctypes.windll.user32.GetForegroundWindow()
    if not window:
        raise RuntimeError("no foreground window")

    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
    process_id = int(pid.value)
    allowed, reason = can_terminate_process(process_id)
    if not allowed:
        raise RuntimeError(reason or "process cannot be terminated")
    return process_candidate_from_pid(process_id)


def terminate_process(pid: int, timeout_seconds: float = 3.0) -> None:
    allowed, reason = can_terminate_process(pid)
    if not allowed:
        raise RuntimeError(reason or "process cannot be terminated")
    try:
        process = psutil.Process(pid)
        process.terminate()
        process.wait(timeout=timeout_seconds)
    except psutil.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=timeout_seconds)
        except psutil.AccessDenied as exc:
            raise RuntimeError("access denied while force killing process") from exc
        except psutil.NoSuchProcess:
            return
    except psutil.AccessDenied as exc:
        raise RuntimeError("access denied while terminating process") from exc
    except psutil.NoSuchProcess:
        return
    except PermissionError as exc:
        raise RuntimeError("access denied while terminating process") from exc


def wait_for_process_exit(pid: int, timeout_seconds: float = 3.0) -> bool:
    try:
        process = psutil.Process(pid)
        process.wait(timeout=timeout_seconds)
        return True
    except psutil.TimeoutExpired:
        return False
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return False
