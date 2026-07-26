from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 1440


@dataclass(frozen=True)
class ScreenshotSchedule:
    monitor_id: int
    interval_minutes: int


def validate_interval_minutes(value: str) -> int:
    try:
        minutes = int(value)
    except ValueError as exc:
        raise ValueError("invalid screenshot interval") from exc
    if minutes < MIN_INTERVAL_MINUTES or minutes > MAX_INTERVAL_MINUTES:
        raise ValueError("invalid screenshot interval")
    return minutes


class ScreenshotTimer:
    def __init__(
        self,
        send_screenshot: Callable[[int], Awaitable[None]],
        report_failure: Callable[[Exception], Awaitable[None]],
    ) -> None:
        self._send_screenshot = send_screenshot
        self._report_failure = report_failure
        self._schedule: ScreenshotSchedule | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def schedule(self) -> ScreenshotSchedule | None:
        return self._schedule

    def start(self, monitor_id: int, interval_minutes: int) -> ScreenshotSchedule:
        self.stop()
        schedule = ScreenshotSchedule(monitor_id, interval_minutes)
        self._schedule = schedule
        self._task = asyncio.create_task(self._run(schedule))
        return schedule

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        self._task = None
        self._schedule = None

    async def _run(self, schedule: ScreenshotSchedule) -> None:
        try:
            while True:
                await self._send_screenshot(schedule.monitor_id)
                await asyncio.sleep(schedule.interval_minutes * 60)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self._schedule == schedule:
                self._task = None
                self._schedule = None
                await self._report_failure(exc)
