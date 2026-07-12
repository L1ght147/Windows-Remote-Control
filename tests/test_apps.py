from pathlib import Path

import pytest

import win_tg_pc_controller.apps as apps_module
from win_tg_pc_controller.apps import _validate_app, add_app, delete_app, load_apps, run_app


def test_rejects_unknown_app_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "notes.txt"
    file_path.write_text("nope", encoding="utf-8")

    with pytest.raises(ValueError, match=".exe, .bat, or .lnk"):
        _validate_app({"id": "notes", "title": "Notes", "path": str(file_path)})


def test_rejects_missing_app_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        _validate_app({"id": "missing", "title": "Missing", "path": str(tmp_path / "missing.exe")})


def test_add_app_persists_whitelist_entry(tmp_path: Path) -> None:
    exe_path = tmp_path / "tool.exe"
    exe_path.write_bytes(b"")
    apps_path = tmp_path / "apps.json"

    app = add_app(apps_path, "My Tool", str(exe_path))
    apps = load_apps(apps_path)

    assert app.id == "my-tool"
    assert apps["my-tool"].title == "My Tool"


def test_rejects_duplicate_app_title(tmp_path: Path) -> None:
    exe_path = tmp_path / "tool.exe"
    exe_path.write_bytes(b"")
    apps_path = tmp_path / "apps.json"

    add_app(apps_path, "My Tool", str(exe_path))
    with pytest.raises(ValueError, match="Duplicate app title"):
        add_app(apps_path, "my tool", str(exe_path))


def test_delete_app_persists_removal(tmp_path: Path) -> None:
    first_path = tmp_path / "first.exe"
    second_path = tmp_path / "second.exe"
    first_path.write_bytes(b"")
    second_path.write_bytes(b"")
    apps_path = tmp_path / "apps.json"
    first = add_app(apps_path, "First", str(first_path))
    second = add_app(apps_path, "Second", str(second_path))

    removed = delete_app(apps_path, first.id)
    apps = load_apps(apps_path)

    assert removed == first
    assert first.id not in apps
    assert first_path.exists()
    assert apps[second.id] == second


def test_delete_app_rejects_unknown_id_without_changing_file(tmp_path: Path) -> None:
    exe_path = tmp_path / "tool.exe"
    exe_path.write_bytes(b"")
    apps_path = tmp_path / "apps.json"
    app = add_app(apps_path, "Tool", str(exe_path))

    with pytest.raises(ValueError, match="Unknown app id"):
        delete_app(apps_path, "missing")

    assert load_apps(apps_path) == {app.id: app}


def test_admin_launch_is_windows_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe_path = tmp_path / "tool.exe"
    exe_path.write_bytes(b"")
    app = _validate_app({"id": "tool", "title": "Tool", "path": str(exe_path)})

    monkeypatch.setattr(apps_module.platform, "system", lambda: "Linux")

    with pytest.raises(RuntimeError, match="admin launch is only supported on Windows"):
        run_app(app, as_admin=True)
