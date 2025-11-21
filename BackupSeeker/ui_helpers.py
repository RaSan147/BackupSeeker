"""UI helpers for theme detection and related utilities.

Provides a robust `is_app_dark()` function that prefers qfluentwidgets
helpers, falls back to qfluentwidgets config, and finally uses the
QApplication palette lightness as a safe fallback.
"""
from __future__ import annotations

from typing import Optional

try:
    # qfluentwidgets exposes isDarkTheme at package level in many installs
    from qfluentwidgets import isDarkTheme as _qfw_is_dark  # type: ignore
except Exception:
    _qfw_is_dark = None

try:
    # Try importing config helpers directly (some installs expose this)
    from qfluentwidgets.common.config import isDarkTheme as _qfw_cfg_is_dark  # type: ignore
    from qfluentwidgets.common.config import qconfig, Theme  # type: ignore
except Exception:
    _qfw_cfg_is_dark = None
    qconfig = None
    Theme = None

try:
    # PyQt imports
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPalette
except Exception:
    QApplication = None
    QPalette = None


def is_app_dark() -> bool:
    """Return True when the application is in dark mode.

    Detection order:
    1. `qfluentwidgets.isDarkTheme()` if available.
    2. `qfluentwidgets.common.config.isDarkTheme()` or resolved `qconfig.theme`.
    3. `QApplication` palette lightness fallback (window color lightness < 128).
    4. Default: False (light).
    """
    try:
        if _qfw_is_dark is not None:
            try:
                return bool(_qfw_is_dark())
            except Exception:
                pass

        if _qfw_cfg_is_dark is not None:
            try:
                return bool(_qfw_cfg_is_dark())
            except Exception:
                pass

        # If qconfig exists and has a theme attribute, try to resolve AUTO
        if qconfig is not None and Theme is not None:
            try:
                t = getattr(qconfig, 'theme', None)
                if t is not None:
                    if t == Theme.DARK:
                        return True
                    if t == Theme.LIGHT:
                        return False
                    # AUTO or unknown: fall through to palette
            except Exception:
                pass

        # Last-resort: use QApplication palette lightness
        if QApplication is not None:
            app = QApplication.instance()
            if app is not None:
                try:
                    pal = app.palette()
                    bg = pal.color(QPalette.ColorRole.Window)
                    # QColor.lightness() -> 0..255, lower means darker
                    try:
                        lightness = bg.lightness()
                        return lightness < 128
                    except Exception:
                        # If QColor doesn't have lightness, approximate via RGB
                        r = bg.red() / 255.0
                        g = bg.green() / 255.0
                        b = bg.blue() / 255.0
                        lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
                        return lum < 0.5
                except Exception:
                    pass

    except Exception:
        pass

    return False
