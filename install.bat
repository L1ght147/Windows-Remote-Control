@echo off
setlocal

cd /d "%~dp0"

echo Installing Windows Telegram PC Controller...
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found in PATH.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
    echo Make sure "Add python.exe to PATH" is enabled.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment already exists.
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

if not exist "config.json" (
    copy "config.example.json" "config.json" >nul
    echo Created config.json
) else (
    echo config.json already exists.
)

if not exist "apps.json" (
    copy "apps.example.json" "apps.json" >nul
    echo Created apps.json
) else (
    echo apps.json already exists.
)

if not exist ".env" (
    (
        echo TELEGRAM_BOT_TOKEN=PUT_YOUR_BOT_TOKEN_HERE
        echo ALLOWED_USER_ID=PUT_YOUR_TELEGRAM_USER_ID_HERE
    ) > ".env"
    echo Created .env template
) else (
    echo .env already exists.
)

echo.
echo Installation complete.
echo Edit .env before first start:
echo   TELEGRAM_BOT_TOKEN=token from BotFather
echo   ALLOWED_USER_ID=your numeric Telegram user id
echo.
echo Start options:
echo   start.bat - run manually.
echo   install_user_autostart.bat - autostart after Windows user logon.
echo.
echo If your Windows user has a password and you need the bot after remote reboot,
echo configure Microsoft Sysinternals Autologon first:
echo   https://learn.microsoft.com/en-us/sysinternals/downloads/autologon
echo This project never asks for or stores your Windows password.
echo.
pause
