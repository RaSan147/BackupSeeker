# Made from final changes from deepseek

"""Launcher wrapper for BackupSeeker.

To avoid native Qt crashes that can occur when mixing import-time GUI
initialization across different module load contexts, prefer launching
the Fluent-mode UI in a separate Python process. This keeps the GUI in a
clean interpreter instance while preserving the existing module entry.
"""

import os
import subprocess
import sys
import traceback

if __name__ == "__main__":
	try:
		from BackupSeeker.main import run_app

		raise SystemExit(run_app())
	except Exception:
		traceback.print_exc()
		# raise SystemExit(rc)