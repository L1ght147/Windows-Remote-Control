import os

import pytest

import win_tg_pc_controller.processes as processes_module
from win_tg_pc_controller.processes import ProcessCandidate, can_terminate_process, describe_process, search_processes


def test_search_processes_requires_at_least_two_chars() -> None:
    assert search_processes("p") == []


def test_describe_process_truncates_long_location() -> None:
    candidate = ProcessCandidate(
        pid=123,
        name="example.exe",
        exe="C:\\" + ("very-long\\" * 20) + "example.exe",
        cmdline="",
    )

    text = describe_process(candidate)

    assert "example.exe | PID 123" in text
    assert "..." in text


def test_can_terminate_rejects_protected_pids() -> None:
    allowed, reason = can_terminate_process(0)

    assert not allowed
    assert reason == "system process is protected"


def test_can_terminate_rejects_own_process() -> None:
    allowed, reason = can_terminate_process(os.getpid())

    assert not allowed
    assert reason == "refusing to terminate bot process"


def test_terminate_process_converts_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float) -> None:
            raise processes_module.psutil.AccessDenied(pid=self.pid)

    monkeypatch.setattr(processes_module, "can_terminate_process", lambda pid: (True, None))
    monkeypatch.setattr(processes_module.psutil, "Process", FakeProcess)

    with pytest.raises(RuntimeError, match="access denied while terminating process"):
        processes_module.terminate_process(123)
