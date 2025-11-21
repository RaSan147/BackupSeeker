"""Shared UI helpers for BackupSeeker."""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path
from typing import Union


def _quote(path: Path) -> str:
    try:
        return shlex.quote(str(path))
    except Exception:
        return str(path)


def open_path_in_explorer(target: Union[Path, str]) -> None:
    """Open a folder (or the parent of a file) in the platform file explorer."""
    path = Path(target)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    folder = path if path.is_dir() else path.parent
    folder_str = str(folder)

    if sys.platform.startswith("win"):
        os.startfile(folder_str)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        os.system(f"open {_quote(folder)}")
    else:
        os.system(f"xdg-open {_quote(folder)}")


def confirm_action(parent, title: str, message: str) -> bool:
    """Show a confirmation prompt (prefer qfluent if available)."""
    try:
        from qfluentwidgets import MessageBox
        fn = getattr(MessageBox, "question", None)
        if callable(fn):
            res = fn(parent, title, message, parent=parent)
            from PyQt6.QtWidgets import QMessageBox as _QMB
            return res == _QMB.StandardButton.Yes
    except Exception:
        pass

    from PyQt6.QtWidgets import QMessageBox

    res = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return res == QMessageBox.StandardButton.Yes
