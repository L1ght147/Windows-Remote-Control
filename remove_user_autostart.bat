@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "TASK_NAME=WindowsTelegramPCControllerUser"

echo Removing Windows Telegram PC Controller user autostart...
echo.

schtasks /Query /TN "%TASK_NAME%" >nul 2>nul
if errorlevel 1 (
    echo User autostart task was not found.
    echo Nothing to remove.
    echo.
    pause
    exit /b 0
)

schtasks /Delete /TN "%TASK_NAME%" /F
if errorlevel 1 (
    echo.
    echo ERROR: Failed to remove scheduled task.
    echo Try running this file as Administrator.
    pause
    exit /b 1
)

echo.
echo User autostart removed.
echo.
pause
