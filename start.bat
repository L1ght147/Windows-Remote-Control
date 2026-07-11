@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment was not found.
    echo Run install.bat first.
    pause
    exit /b 1
)

if not exist ".env" (
    echo ERROR: .env was not found.
    echo Run install.bat first, then edit .env with your bot token and user id.
    pause
    exit /b 1
)

set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m win_tg_pc_controller

echo.
echo Bot stopped.
pause
