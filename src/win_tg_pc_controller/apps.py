from __future__ import annotations

import json
import os
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


APP_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
ALLOWED_APP_EXTENSIONS = {".exe", ".bat", ".lnk"}


@dataclass(frozen=True)
class LaunchApp:
    id: str
    title: str
    path: Path


def make_app_id(title: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", title.strip().lower()).strip("-")
    return normalized[:32] or "app"


def _validate_app(raw: object) -> LaunchApp:
    if not isinstance(raw, dict):
        raise ValueError("Each app must be an object")

    app_id = raw.get("id")
    title = raw.get("title")
    app_path = raw.get("path")

    if not isinstance(app_id, str) or not APP_ID_RE.fullmatch(app_id):
        raise ValueError("App id must match [A-Za-z0-9_-]{1,32}")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"App {app_id} title must be a non-empty string")
    if not isinstance(app_path, str) or not app_path.strip():
        raise ValueError(f"App {app_id} path must be a non-empty string")

    path = Path(app_path.strip()).expanduser()
    if path.suffix.lower() not in ALLOWED_APP_EXTENSIONS:
        raise ValueError(f"App {app_id} must be .exe, .bat, or .lnk")
    if not path.exists():
        raise ValueError(f"App {app_id} path does not exist")

    return LaunchApp(id=app_id, title=title.strip(), path=path)


def load_apps(path: Path) -> dict[str, LaunchApp]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise ValueError("apps.json must contain a JSON array")

    apps: dict[str, LaunchApp] = {}
    seen_titles: set[str] = set()
    for item in raw:
        app = _validate_app(item)
        title_key = app.title.casefold()
        if app.id in apps:
            raise ValueError(f"Duplicate app id: {app.id}")
        if title_key in seen_titles:
            raise ValueError(f"Duplicate app title: {app.title}")
        apps[app.id] = app
        seen_titles.add(title_key)
    return apps


def save_apps(path: Path, apps: dict[str, LaunchApp]) -> None:
    payload = [
        {"id": app.id, "title": app.title, "path": str(app.path)}
        for app in apps.values()
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def add_app(path: Path, title: str, app_path: str) -> LaunchApp:
    apps = load_apps(path)
    base_id = make_app_id(title)
    app_id = base_id
    counter = 2
    while app_id in apps:
        suffix = f"-{counter}"
        app_id = f"{base_id[: 32 - len(suffix)]}{suffix}"
        counter += 1

    app = _validate_app({"id": app_id, "title": title, "path": app_path})
    if any(existing.title.casefold() == app.title.casefold() for existing in apps.values()):
        raise ValueError(f"Duplicate app title: {app.title}")
    apps[app.id] = app
    save_apps(path, apps)
    return app


def delete_app(path: Path, app_id: str) -> LaunchApp:
    apps = load_apps(path)
    app = apps.pop(app_id, None)
    if app is None:
        raise ValueError(f"Unknown app id: {app_id}")
    save_apps(path, apps)
    return app


def _run_app_as_admin(app: LaunchApp) -> None:
    if platform.system() != "Windows":
        raise RuntimeError("admin launch is only supported on Windows")
    try:
        os.startfile(str(app.path), "runas")  # type: ignore[attr-defined]
    except OSError as exc:
        raise RuntimeError(f"failed to start app as administrator: {exc}") from exc


def run_app(app: LaunchApp, as_admin: bool = False) -> None:
    if as_admin:
        _run_app_as_admin(app)
        return
    if app.path.suffix.lower() in {".bat", ".lnk"}:
        try:
            os.startfile(str(app.path))  # type: ignore[attr-defined]
        except OSError as exc:
            raise RuntimeError(f"failed to start app: {exc}") from exc
        return
    try:
        subprocess.Popen([str(app.path)], shell=False)
    except OSError as exc:
        raise RuntimeError(f"failed to start app: {exc}") from exc
