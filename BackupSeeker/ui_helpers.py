"""UI helpers for theme detection and related utilities.

Provides a robust `is_app_dark()` function that prefers qfluentwidgets
helpers, falls back to qfluentwidgets config, and finally uses the
QApplication palette lightness as a safe fallback.
"""
from __future__ import annotations

# qfluentwidgets exposes isDarkTheme at package level in many installs
from qfluentwidgets import isDarkTheme as _qfw_is_dark  # type: ignore

# Try importing config helpers directly (some installs expose this)
from qfluentwidgets.common.config import Theme, qconfig  # type: ignore
from qfluentwidgets.common.config import (
    isDarkTheme as _qfw_cfg_is_dark,  # type: ignore
)


# PyQt imports
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication



def is_app_dark() -> bool:
    for fn in (_qfw_is_dark, _qfw_cfg_is_dark):
        if callable(fn):
            try:
                return bool(fn())
            except Exception:
                pass

    if qconfig is not None and Theme is not None:
        theme = getattr(qconfig, "theme", None)
        if theme in (Theme.DARK, Theme.LIGHT):
            return theme == Theme.DARK

    app = QApplication.instance() if QApplication is not None else None
    if app is not None:
        return app.palette().color(QPalette.ColorRole.Window).lightness() < 128

    return False
