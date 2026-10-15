import asyncio
import datetime as dt

import pytest

from win_tg_pc_controller.power_timer import PowerSchedule, PowerTimer, validate_delay_minutes


SECONDS_PER_MINUTE = 0.01


def _recording_timer(events: list[str], fail: bool = False) -> PowerTimer:
    async def run_action(action: str) -> None:
        events.append(f"run:{action}")
        if fail:
            raise RuntimeError("boom")

    async def warn(schedule: PowerSchedule) -> None:
        events.append(f"warn:{schedule.action}")

    async def report_failure(schedule: PowerSchedule, exc: Exception) -> None:
        events.append(f"failed:{schedule.action}:{exc}")

    return PowerTimer(run_action, warn, report_failure, seconds_per_minute=SECONDS_PER_MINUTE)


@pytest.mark.parametrize("value", ["0", "1441", "abc", "1.5"])
def test_validate_delay_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_delay_minutes(value)


def test_validate_delay_accepts_range_bounds() -> None:
    assert validate_delay_minutes("1") == 1
    assert validate_delay_minutes("1440") == 1440


def test_timer_warns_then_runs_action() -> None:
    events: list[str] = []

    async def scenario() -> PowerTimer:
        timer = _recording_timer(events)
        timer.start("shutdown", 3)
        await asyncio.sleep(SECONDS_PER_MINUTE * 6)
        return timer

    timer = asyncio.run(scenario())

    assert events == ["warn:shutdown", "run:shutdown"]
    assert timer.schedule is None


def test_one_minute_timer_runs_without_warning() -> None:
    events: list[str] = []

    async def scenario() -> None:
        _recording_timer(events).start("sleep", 1)
        await asyncio.sleep(SECONDS_PER_MINUTE * 4)

    asyncio.run(scenario())

    assert events == ["run:sleep"]


def test_cancel_prevents_action() -> None:
    events: list[str] = []

    async def scenario() -> bool:
        timer = _recording_timer(events)
        timer.start("shutdown", 2)
        cancelled = timer.cancel()
        await asyncio.sleep(SECONDS_PER_MINUTE * 5)
        return cancelled

    assert asyncio.run(scenario()) is True
    assert events == []


def test_cancel_without_schedule_reports_nothing_cancelled() -> None:
    async def scenario() -> bool:
        return _recording_timer([]).cancel()

    assert asyncio.run(scenario()) is False


def test_new_schedule_replaces_previous_one() -> None:
    events: list[str] = []

    async def scenario() -> None:
        timer = _recording_timer(events)
        timer.start("shutdown", 1)
        timer.start("sleep", 1)
        await asyncio.sleep(SECONDS_PER_MINUTE * 4)

    asyncio.run(scenario())

    assert events == ["run:sleep"]


def test_action_failure_is_reported() -> None:
    events: list[str] = []

    async def scenario() -> None:
        _recording_timer(events, fail=True).start("sleep", 1)
        await asyncio.sleep(SECONDS_PER_MINUTE * 4)

    asyncio.run(scenario())

    assert events == ["run:sleep", "failed:sleep:boom"]


def test_unknown_action_is_rejected() -> None:
    async def scenario() -> None:
        _recording_timer([]).start("reboot", 5)

    with pytest.raises(ValueError, match="Unknown timer action"):
        asyncio.run(scenario())


def test_remaining_minutes_rounds_up() -> None:
    now = dt.datetime(2026, 10, 15, 12, 0, 0)
    schedule = PowerSchedule("shutdown", 30, now + dt.timedelta(minutes=29, seconds=1))

    assert schedule.remaining_minutes(now) == 30
    assert schedule.remaining_minutes(now + dt.timedelta(hours=1)) == 0
