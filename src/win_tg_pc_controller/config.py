from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    telegram_bot_token: str
    allowed_user_id: int
    apps_file: Path
    confirmation_ttl_seconds: int = 30
    telegram_timeout_seconds: float = 30.0
    telegram_bootstrap_retries: int = -1


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _int_value(name: str, value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _float_value(name: str, value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc


def load_config(config_path: str | Path = "config.json") -> AppConfig:
    load_dotenv()

    path = Path(config_path)
    raw = _read_json(path)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured")

    allowed_user_id = os.getenv("ALLOWED_USER_ID", raw.get("allowed_user_id"))
    if allowed_user_id is None:
        raise ValueError("ALLOWED_USER_ID or config.allowed_user_id is required")

    apps_file = Path(str(raw.get("apps_file", "apps.json")))
    if not apps_file.is_absolute():
        apps_file = path.parent / apps_file

    confirmation_ttl = _int_value(
        "confirmation_ttl_seconds", raw.get("confirmation_ttl_seconds", 30)
    )
    telegram_timeout = _float_value(
        "telegram_timeout_seconds", raw.get("telegram_timeout_seconds", 30)
    )
    telegram_bootstrap_retries = _int_value(
        "telegram_bootstrap_retries", raw.get("telegram_bootstrap_retries", -1)
    )

    if confirmation_ttl < 5 or confirmation_ttl > 300:
        raise ValueError("confirmation_ttl_seconds must be between 5 and 300")
    if telegram_timeout < 5 or telegram_timeout > 300:
        raise ValueError("telegram_timeout_seconds must be between 5 and 300")
    if telegram_bootstrap_retries < -1:
        raise ValueError("telegram_bootstrap_retries must be -1 or greater")

    return AppConfig(
        telegram_bot_token=token,
        allowed_user_id=_int_value("allowed_user_id", allowed_user_id),
        apps_file=apps_file,
        confirmation_ttl_seconds=confirmation_ttl,
        telegram_timeout_seconds=telegram_timeout,
        telegram_bootstrap_retries=telegram_bootstrap_retries,
    )
