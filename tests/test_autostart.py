from pathlib import Path


def test_autostart_task_uses_pythonw_without_cmd_wrapper() -> None:
    script = Path("install_user_autostart.bat").read_text(encoding="utf-8")

    assert 'set "PYTHONW_EXE=%PROJECT_DIR%.venv\\Scripts\\pythonw.exe"' in script
    assert 'set "LAUNCHER=%PROJECT_DIR%run_autostart.pyw"' in script
    assert 'schtasks /Create' in script
    assert '/TR "\\"%PYTHONW_EXE%\\" \\"%LAUNCHER%\\""' in script
    assert "%ComSpec%" not in script
    assert "--run" not in script
