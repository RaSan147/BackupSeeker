"""Entry point for BackupSeeker Game Save Manager.

This mirrors the behavior of running `gemini.py` directly, but uses the
modular `BackupSeeker` package so it can evolve independently.
"""

from .ui import run_app


if __name__ == "__main__":
	raise SystemExit(run_app())

