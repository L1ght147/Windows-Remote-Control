@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "TASK_NAME=WindowsTelegramPCControllerUser"
set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%.venv\Scripts\python.exe"

if /I "%~1"=="--run" (
    cd /d "%PROJECT_DIR%"
    set "PYTHONPATH=%PROJECT_DIR%src"
    "%PYTHON_EXE%" -m win_tg_pc_controller
    exit /b %ERRORLEVEL%
)

echo Installing Windows Telegram PC Controller user autostart...
echo.

if not exist "%PYTHON_EXE%" (
    echo ERROR: Virtual environment was not found.
    echo Run install.bat first.
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%.env" (
    echo ERROR: .env was not found.
    echo Run install.bat first, then edit .env with your bot token and user id.
    pause
    exit /b 1
)

if not exist "%PROJECT_DIR%config.json" (
    echo ERROR: config.json was not found.
    echo Run install.bat first.
    pause
    exit /b 1
)

schtasks /Create /TN "%TASK_NAME%" /SC ONLOGON /F /TR "%ComSpec% /d /c call ^"%PROJECT_DIR%install_user_autostart.bat^" --run"
set "CREATE_ERROR=%ERRORLEVEL%"

if not "%CREATE_ERROR%"=="0" (
    echo.
    echo ERROR: Failed to create scheduled task.
    echo Try running this file as Administrator if Windows blocks task creation.
    pause
    exit /b %CREATE_ERROR%
)

echo.
echo User autostart installed.
echo Task name: %TASK_NAME%
echo The bot will start after Windows logs into this user.
echo This task does not request elevated administrator privileges.
echo.
echo If screenshots still do not work, open PC Status in Telegram and check Windows session.
echo.
echo For remote reboot recovery, use Windows AutoLogon together with this task.
echo To remove user autostart, run remove_user_autostart.bat.
echo.
pause
