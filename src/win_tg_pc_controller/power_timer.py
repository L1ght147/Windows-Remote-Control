from __future__ import annotations

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


LOGGER = logging.getLogger(__name__)
TIMER_ACTIONS = ("shutdown", "sleep")
MIN_DELAY_MINUTES = 1
MAX_DELAY_MINUTES = 1440
WARNING_LEAD_MINUTES = 1


@dataclass(frozen=True)
class PowerSchedule:
    action: str
    minutes: int
    due_at: dt.datetime

    def remaining_minutes(self, now: dt.datetime | None = None) -> int:
        seconds = (self.due_at - (now or dt.datetime.now())).total_seconds()
        return max(0, -int(-seconds // 60))


def validate_delay_minutes(value: str) -> int:
    try:
        minutes = int(value)
    except ValueError as exc:
        raise ValueError("invalid timer delay") from exc
    if minutes < MIN_DELAY_MINUTES or minutes > MAX_DELAY_MINUTES:
        raise ValueError("invalid timer delay")
    return minutes


class PowerTimer:
    """Runs one delayed shutdown or sleep; a new schedule replaces the old one.

    The schedule lives in the bot process: it is lost if the bot stops.
    """

    def __init__(
        self,
        run_action: Callable[[str], Awaitable[None]],
        warn: Callable[[PowerSchedule], Awaitable[None]],
        report_failure: Callable[[PowerSchedule, Exception], Awaitable[None]],
        seconds_per_minute: float = 60,
    ) -> None:
        self._run_action = run_action
        self._warn = warn
        self._report_failure = report_failure
        self._seconds_per_minute = seconds_per_minute
        self._schedule: PowerSchedule | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def schedule(self) -> PowerSchedule | None:
        return self._schedule

    def start(self, action: str, minutes: int) -> PowerSchedule:
        if action not in TIMER_ACTIONS:
            raise ValueError(f"Unknown timer action: {action}")
        self.cancel()
        schedule = PowerSchedule(action, minutes, dt.datetime.now() + dt.timedelta(minutes=minutes))
        self._schedule = schedule
        self._task = asyncio.create_task(self._run(schedule))
        return schedule

    def cancel(self) -> bool:
        cancelled = self._schedule is not None
        if self._task is not None:
            self._task.cancel()
        self._task = None
        self._schedule = None
        return cancelled

    async def _run(self, schedule: PowerSchedule) -> None:
        minute = self._seconds_per_minute
        if schedule.minutes > WARNING_LEAD_MINUTES:
            await asyncio.sleep((schedule.minutes - WARNING_LEAD_MINUTES) * minute)
            try:
                await self._warn(schedule)
            except Exception:
                # A failed warning must not cancel the shutdown itself.
                LOGGER.warning("Failed to send power timer warning", exc_info=True)
            await asyncio.sleep(WARNING_LEAD_MINUTES * minute)
        else:
            await asyncio.sleep(schedule.minutes * minute)

        if self._schedule != schedule:
            return
        self._task = None
        self._schedule = None
        try:
            await self._run_action(schedule.action)
        except Exception as exc:
            await self._report_failure(schedule, exc)
