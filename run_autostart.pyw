from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from win_tg_pc_controller.__main__ import main


main()
