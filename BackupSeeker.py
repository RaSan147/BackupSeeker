# Made from final changes from deepseek

"""Launcher wrapper for BackupSeeker.

To avoid native Qt crashes that can occur when mixing import-time GUI
initialization across different module load contexts, prefer launching
the Fluent-mode UI in a separate Python process. This keeps the GUI in a
clean interpreter instance while preserving the existing module entry.
"""

import traceback
import os
import sys
from pathlib import Path

# Determine the app's root folder (works for both .py and frozen .exe)
if getattr(sys, 'frozen', False):
    app_dir = Path(sys.executable).resolve().parent
else:
    app_dir = Path(__file__).resolve().parent

# Force the current working directory to the app folder
os.chdir(app_dir)

if __name__ == "__main__":
	try:
		from BackupSeeker.main import run_app

		raise SystemExit(run_app())
	except Exception:
		traceback.print_exc()
		# raise SystemExit(rc)