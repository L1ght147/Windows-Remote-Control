from pathlib import Path
import os
import sys


PROJECT_DIR = Path(__file__).resolve().parent
# Task Scheduler starts the task in %windir%\system32; config.json, apps.json
# and logs are resolved relative to the project directory.
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR / "src"))

from win_tg_pc_controller.__main__ import main


main()
