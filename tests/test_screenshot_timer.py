import asyncio

import pytest

from win_tg_pc_controller.screenshot_timer import ScreenshotTimer, validate_interval_minutes


def test_validate_interval_minutes_accepts_configured_bounds() -> None:
    assert validate_interval_minutes("1") == 1
    assert validate_interval_minutes("1440") == 1440


@pytest.mark.parametrize("value", ["", "0", "1441", "1.5", "one"])
def test_validate_interval_minutes_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_interval_minutes(value)


def test_timer_replaces_previous_schedule() -> None:
    async def scenario() -> None:
        sent: list[int] = []
        delivered = asyncio.Event()

        async def send_screenshot(monitor_id: int) -> None:
            sent.append(monitor_id)
            delivered.set()

        async def report_failure(_exc: Exception) -> None:
            raise AssertionError("timer should not fail")

        timer = ScreenshotTimer(send_screenshot, report_failure)
        timer.start(monitor_id=1, interval_minutes=1)
        timer.start(monitor_id=2, interval_minutes=5)

        await asyncio.wait_for(delivered.wait(), timeout=0.1)
        assert sent == [2]
        assert timer.schedule is not None
        assert timer.schedule.monitor_id == 2
        assert timer.schedule.interval_minutes == 5

        timer.stop()
        await asyncio.sleep(0)

    asyncio.run(scenario())


def test_timer_reports_failure_and_stops() -> None:
    async def scenario() -> None:
        failures: list[str] = []
        reported = asyncio.Event()

        async def send_screenshot(_monitor_id: int) -> None:
            raise RuntimeError("desktop unavailable")

        async def report_failure(exc: Exception) -> None:
            failures.append(str(exc))
            reported.set()

        timer = ScreenshotTimer(send_screenshot, report_failure)
        timer.start(monitor_id=1, interval_minutes=1)

        await asyncio.wait_for(reported.wait(), timeout=0.1)
        assert failures == ["desktop unavailable"]
        assert timer.schedule is None

    asyncio.run(scenario())
