"""Entry point for BackupSeeker Game Save Manager.

By default the project now launches the Fluent-mode UI. The legacy
`run_app` remains available in `BackupSeeker.ui` but `main` prefers the
Fluent launcher when present.
"""
import traceback

try:
	from .ui_fluent import run_modern_fluent_app as run_app
except Exception:
	traceback.print_exc()
	print("Warning: Failed to launch Fluent UI mode; falling back to original UI.")
	# Fallback to the original UI runner if Fluent launcher fails for any reason
	from .ui import run_app as run_app


if __name__ == "__main__":
	raise SystemExit(run_app())

