from __future__ import annotations

import ctypes
import platform
import subprocess


DANGEROUS_ACTIONS = {"sleep", "reboot", "shutdown"}


def _require_windows() -> None:
    if platform.system() != "Windows":
        raise RuntimeError("This action is only supported on Windows")


def lock_workstation() -> None:
    _require_windows()
    result = ctypes.windll.user32.LockWorkStation()
    if result == 0:
        raise RuntimeError("LockWorkStation failed")


def sleep_pc() -> None:
    _require_windows()
    subprocess.run(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        check=True,
        shell=False,
    )


def reboot_pc() -> None:
    _require_windows()
    subprocess.run(["shutdown.exe", "/r", "/t", "0"], check=True, shell=False)


def shutdown_pc() -> None:
    _require_windows()
    subprocess.run(["shutdown.exe", "/s", "/t", "0"], check=True, shell=False)


def run_control_action(action: str) -> None:
    if action == "lock":
        lock_workstation()
    elif action == "sleep":
        sleep_pc()
    elif action == "reboot":
        reboot_pc()
    elif action == "shutdown":
        shutdown_pc()
    else:
        raise ValueError(f"Unknown action: {action}")
