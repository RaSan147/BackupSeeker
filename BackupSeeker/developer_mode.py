"""Developer mode: hot plugin reload, verbose logging, and manual refresh hooks."""

from __future__ import annotations

import logging
import os
from typing import Iterable

from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

_DEV_LOGGER_NAMES = (
	"BackupSeeker",
	"BackupSeeker.plugin_manager",
	"BackupSeeker.plugin_hot_reload",
	"BackupSeeker.plugin_runtime",
	"BackupSeeker.ui_fluent",
	"BackupSeeker.core",
)


def is_developer_mode(config: object | None) -> bool:
	"""True when config flag or ``BACKUPSEEKER_DEV`` env enables developer mode."""

	if _env_developer_mode():
		return True
	if config is None:
		return False
	return bool(getattr(config, "developer_mode", False))


def _env_developer_mode() -> bool:
	env = (os.environ.get("BACKUPSEEKER_DEV") or "").strip().lower()
	return env in ("1", "true", "yes", "on")


def developer_mode_status_text(config: object | None) -> str:
	"""Human-readable developer mode status for the settings page."""

	if _env_developer_mode():
		return "Hot reload: active (BACKUPSEEKER_DEV) | Logging: DEBUG"
	if is_developer_mode(config):
		return "Hot reload: watching plugins/ | Logging: DEBUG"
	return "Hot reload: off | Logging: normal"


def apply_log_verbosity(*, enabled: bool) -> None:
	"""Raise or lower log verbosity for plugin/UI subsystems."""

	level = logging.DEBUG if enabled else logging.WARNING
	for name in _DEV_LOGGER_NAMES:
		logging.getLogger(name).setLevel(level)
	if enabled:
		logger.debug("Developer mode logging enabled (DEBUG for %s)", ", ".join(_DEV_LOGGER_NAMES))
	else:
		logger.info("Developer mode logging disabled")


def set_dev_widgets_visible(enabled: bool, widgets: Iterable[QWidget]) -> None:
	for widget in widgets:
		try:
			widget.setVisible(enabled)
		except Exception:
			pass


def dev_toast_duration_ms(*, enabled: bool, normal_ms: int = 4000, dev_ms: int = 12000) -> int:
	return dev_ms if enabled else normal_ms
