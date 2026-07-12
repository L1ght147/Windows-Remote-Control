# Windows Telegram PC Controller

Windows Telegram PC Controller is a Telegram bot for controlled remote access to
a Windows user session. It exposes a small set of operational actions, restricts
access to one Telegram user, and requires explicit confirmation before running
high-impact commands.

The project is intended for personal administration of a trusted Windows PC. It
doesn't bypass Windows security boundaries, UAC, the lock screen, or remote
desktop session isolation.

## Features

- Show PC status: online state, CPU, RAM, disk `C:`, uptime, battery, LAN IP,
  and Windows session diagnostics.
- Capture screenshots from a selected monitor when the bot runs in the active
  user session and the desktop is accessible.
- Lock, sleep, reboot, and shut down the PC.
- Require confirmation for sleep, reboot, shutdown, process termination,
  clipboard clearing, and application launch.
- Restrict all bot commands to the configured `ALLOWED_USER_ID`.
- Launch allowlisted `.exe`, `.bat`, and `.lnk` files from `apps.json`.
- Add new launch entries from Telegram after path and extension validation.
- Launch applications normally or through the Windows UAC administrator prompt.
- Search running processes, inspect the foreground process, and terminate a
  selected process after confirmation.
- View, replace, and clear the text clipboard from the **Буфер обмена** menu.

## Security model

The bot uses a deliberately narrow trust model:

- Only the Telegram user whose numeric ID matches `ALLOWED_USER_ID` can use the
  bot.
- Dangerous operations are guarded by short-lived confirmations.
- Application launch is limited to entries that pass validation and are stored
  in `apps.json`.
- Process termination refuses protected system PIDs and the bot's own process.
- Administrator application launch uses the normal Windows UAC prompt. The bot
  doesn't provide credentials or suppress UAC.
- Clipboard contents aren't written to application logs.
- Windows credentials aren't requested, stored, or transmitted by this project.

Keep the bot token, `.env`, `config.json`, and `apps.json` private. Anyone who
gets the bot token and matches the configured Telegram user ID can control the
machine through the exposed actions.

## Requirements

- Windows.
- Python 3.11 or newer.
- A Telegram bot token from BotFather.
- Your numeric Telegram user ID.
- Network access to `https://api.telegram.org`.

Most runtime features require an interactive Windows user session. Screenshots,
clipboard access, foreground-window detection, and application launch can fail
when Windows is locked, UAC secure desktop is active, or the bot runs in a
different session from the active console.

## Installation

For a standard Windows setup, run the installer script from the repository root:

```bat
install.bat
```

The script:

1. Creates `.venv` if it doesn't exist.
2. Installs dependencies from `requirements.txt`.
3. Creates `config.json` from `config.example.json` if needed.
4. Creates `apps.json` from `apps.example.json` if needed.
5. Creates a `.env` template if needed.

Edit `.env` before the first start:

```text
TELEGRAM_BOT_TOKEN=123456:your_bot_token
ALLOWED_USER_ID=123456789
```

`ALLOWED_USER_ID` can also be set in `config.json`, but the environment variable
takes precedence.

## Run the bot

After installation and configuration, start the bot manually:

```bat
start.bat
```

You can also run it directly from an activated virtual environment:

```powershell
$env:PYTHONPATH="src"
python -m win_tg_pc_controller
```

The package also exposes a console script when installed as a Python package:

```powershell
win-tg-pc-controller
```

## Language

On the first `/start`, the bot asks you to choose Russian or English. The choice is saved locally in `user_settings.json` and remains active after a restart. Send `/language` at any time to choose a different language.

## Autostart after Windows logon

For reliable remote reboot recovery, use Windows AutoLogon together with the
user-logon scheduled task.

1. Configure AutoLogon with the official
   [Microsoft Sysinternals AutoLogon tool][autologon].
2. Run:

   ```bat
   install_user_autostart.bat
   ```

The script creates a scheduled task named `WindowsTelegramPCControllerUser`.
The task starts the bot after Windows logs into the current user and doesn't
request elevated administrator privileges.

Remove the scheduled task with:

```bat
remove_user_autostart.bat
```

## Remote access notes

Some remote access tools and RDP modes lock, log off, or switch the local
Windows session when you connect or disconnect. In those states, Windows can
show the password screen or UAC secure desktop, and desktop capture can fail.

When screenshots don't work, open **Статус** in Telegram and inspect the
`Windows session` block. For screenshots to work, the bot usually needs:

- `Bot in active session: yes`.
- `Desktop accessible: yes`.

If those values are wrong, check the remote access tool for settings such as
lock on disconnect, log off on disconnect, privacy mode, or secure desktop
handling.

Avoid launching applications as administrator unless you can see and approve the
UAC prompt in the current remote session.

## Configuration

`config.json` supports these fields:

- `allowed_user_id`: numeric Telegram user ID allowed to use the bot. This
  value is ignored when `ALLOWED_USER_ID` is set in the environment.
- `apps_file`: path to the application allowlist JSON file. Relative paths are
  resolved from the `config.json` directory.
- `confirmation_ttl_seconds`: confirmation timeout in seconds. Valid range:
  `5` to `300`.
- `telegram_timeout_seconds`: Telegram API timeout in seconds. Valid range:
  `5` to `300`.
- `telegram_bootstrap_retries`: startup retry count for Telegram polling. Use
  `-1` to retry indefinitely.

`apps.json` must contain an array of application entries:

```json
[
  {
    "id": "notepad",
    "title": "Notepad",
    "path": "C:\\Windows\\System32\\notepad.exe"
  }
]
```

Each entry must include:

- `id`: callback-safe identifier matching `[A-Za-z0-9_-]{1,32}`.
- `title`: non-empty label shown in Telegram.
- `path`: existing path to an `.exe`, `.bat`, or `.lnk` file.

Entries must have unique IDs and case-insensitive unique titles.

## Troubleshooting

If startup fails with `telegram.error.TimedOut` or another Telegram network
error, check:

- Internet access from the Windows machine.
- Access to `https://api.telegram.org`.
- VPN, proxy, and firewall rules.
- The value of `TELEGRAM_BOT_TOKEN`.

If screenshots, clipboard operations, foreground-process detection, or
application launch fail, confirm that the bot is running in the logged-in user
session and that the desktop isn't locked.

## Development

Install the package with development dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Run the test suite:

```powershell
pytest
```

The tests focus on configuration-adjacent logic, application validation,
confirmation handling, process safeguards, status formatting, clipboard text
formatting, and Windows session diagnostics.

[autologon]: https://learn.microsoft.com/en-us/sysinternals/downloads/autologon
