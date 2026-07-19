from __future__ import annotations

import logging
import subprocess
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from qfluentwidgets import FluentTranslator, Theme, setTheme

from ..core import ConfigManager
from ..developer_mode import apply_log_verbosity, is_developer_mode
from .main_window import ModernBackupSeekerWindow


def run_modern_fluent_app() -> int:
	try:
		cfg = ConfigManager()
		apply_log_verbosity(enabled=is_developer_mode(cfg))

		QApplication.setHighDpiScaleFactorRoundingPolicy(
			Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
		)

		app = QApplication(sys.argv)
		app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

		translator = FluentTranslator()
		app.installTranslator(translator)

		try:
			cfg = ConfigManager()
			if (cfg.theme or "").lower() == "dark":
				setTheme(Theme.DARK)
			elif (cfg.theme or "").lower() == "light":
				setTheme(Theme.LIGHT)
			else:
				setTheme(Theme.AUTO)
		except Exception:
			setTheme(Theme.AUTO)

		window = ModernBackupSeekerWindow()
		window.show()

		return app.exec()

	except Exception as e:
		import traceback as _tb

		_tb.print_exc()

		msg = f"A fatal error occurred in the Fluent UI:\n{e}\n\nWould you like to restart the application?"
		confirmed = False
		try:
			from PyQt6.QtWidgets import QMessageBox as _QMB

			ans = _QMB.question(
				None,
				"Fluent UI Error",
				msg,
				_QMB.StandardButton.Yes | _QMB.StandardButton.No,
			)
			confirmed = ans == _QMB.StandardButton.Yes
		except Exception:
			confirmed = False

		if confirmed:
			try:
				subprocess.Popen([sys.executable] + sys.argv)
			except Exception:
				pass

		return 1
