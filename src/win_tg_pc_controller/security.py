from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


def is_allowed_user(user_id: int | None, allowed_user_id: int) -> bool:
    return user_id == allowed_user_id


@dataclass
class PendingAction:
    actions: tuple[str, ...]
    expires_at: float


class ConfirmationStore:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._pending: dict[int, PendingAction] = {}

    def request(self, user_id: int, action: str) -> None:
        self.request_any(user_id, [action])

    def request_any(self, user_id: int, actions: list[str]) -> None:
        self._pending[user_id] = PendingAction(
            actions=tuple(actions),
            expires_at=monotonic() + self._ttl_seconds,
        )

    def confirm(self, user_id: int, action: str) -> bool:
        pending = self._pending.pop(user_id, None)
        if pending is None:
            return False
        if action not in pending.actions:
            return False
        return pending.expires_at >= monotonic()

    def cancel(self, user_id: int) -> bool:
        return self._pending.pop(user_id, None) is not None
