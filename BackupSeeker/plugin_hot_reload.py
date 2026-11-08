"""Filesystem watcher that hot-reloads plugins while the app is running."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal

if TYPE_CHECKING:
	from .plugin_manager import PluginManager

logger = logging.getLogger(__name__)

_WATCH_SUFFIXES = {".py", ".json", ".jsonc"}
_WATCH_NAMES = {"games.jsonc", "plugin_index.json"}


class PluginHotReloader(QObject):
	"""Watch ``plugins/`` and debounce hot reloads into :class:`PluginManager`."""

	reload_finished = pyqtSignal(object)

	def __init__(self, manager: PluginManager, *, debounce_ms: int = 750) -> None:
		super().__init__()
		self._manager = manager
		self._plugins_dir = Path(manager.plugins_dir)
		self._watcher = QFileSystemWatcher(self)
		self._debounce = QTimer(self)
		self._debounce.setSingleShot(True)
		# Editors often do write → rename → directory touch; keep this above that burst.
		self._debounce.setInterval(max(300, debounce_ms))
		self._debounce.timeout.connect(self._run_reload)
		self._watcher.fileChanged.connect(self._on_fs_event)
		self._watcher.directoryChanged.connect(self._on_fs_event)
		self._active = False
		self._pending_reason = "filesystem change"
		self._reloading = False
		self._reload_queued = False
		self._suppress_fs = False

	def start(self) -> None:
		"""Begin watching plugin sources."""

		if self._active:
			return
		self._active = True
		self._refresh_watched_paths()
		if self._plugins_dir.exists():
			dir_key = str(self._plugins_dir)
			if dir_key not in self._watcher.directories():
				self._watcher.addPath(dir_key)

	def stop(self) -> None:
		"""Stop filesystem watching."""

		self._active = False
		self._debounce.stop()
		self._reload_queued = False
		for path in list(self._watcher.files()):
			self._watcher.removePath(path)
		for path in list(self._watcher.directories()):
			self._watcher.removePath(path)

	def reload_now(self, *, reason: str = "manual") -> object:
		"""Run an immediate hot reload (used by the Reload Plugins button)."""

		self._pending_reason = reason
		self._debounce.stop()
		self._reload_queued = False
		return self._run_reload()

	def _is_plugin_source(self, path: str) -> bool:
		p = Path(path)
		if path == str(self._plugins_dir) or p.is_dir():
			return True
		name = p.name
		if name in _WATCH_NAMES:
			return True
		if name.startswith("."):
			return False
		if "__pycache__" in p.parts:
			return False
		return p.suffix.lower() in _WATCH_SUFFIXES

	def _on_fs_event(self, path: str) -> None:
		if not self._active or self._suppress_fs:
			return
		if not self._is_plugin_source(path):
			return

		self._pending_reason = "filesystem change"
		p = Path(path)

		# Directory membership changed (new/deleted plugin file).
		if path == str(self._plugins_dir) or p.is_dir():
			self._refresh_watched_paths()
		else:
			# Windows drops watches after atomic replace — re-arm quietly.
			if p.exists() and path not in self._watcher.files():
				self._watcher.blockSignals(True)
				try:
					self._watcher.addPath(path)
				finally:
					self._watcher.blockSignals(False)

		if self._reloading:
			# Coalesce bursts that arrive while a reload is already running.
			self._reload_queued = True
			return
		self._debounce.start()

	def _refresh_watched_paths(self) -> None:
		"""Track each plugin ``.py`` and JSON index file (QFileSystemWatcher is non-recursive)."""

		if not self._plugins_dir.exists():
			return
		desired: set[str] = set()
		for py_file in self._plugins_dir.rglob("*.py"):
			if "__pycache__" in py_file.parts:
				continue
			desired.add(str(py_file.resolve()))
		for name in _WATCH_NAMES:
			p = self._plugins_dir / name
			if p.exists():
				desired.add(str(p.resolve()))

		current = set(self._watcher.files())
		self._watcher.blockSignals(True)
		try:
			for path in current - desired:
				self._watcher.removePath(path)
			for path in desired - current:
				self._watcher.addPath(path)
		finally:
			self._watcher.blockSignals(False)

	def _run_reload(self) -> object:
		from .plugin_manager import PluginLoadReport

		if self._reloading:
			self._reload_queued = True
			return self._manager.last_load_report

		reason = self._pending_reason
		logger.info("Hot-reloading plugins (%s)", reason)
		self._reloading = True
		self._suppress_fs = True
		self._debounce.stop()
		try:
			try:
				report = self._manager.reload_plugins(hot=True)
			except Exception:
				logger.exception("reload_plugins() itself crashed — keeping old state")
				report = self._manager.last_load_report
			if not isinstance(report, PluginLoadReport):
				report = self._manager.last_load_report
			self.reload_finished.emit(report)
			return report
		finally:
			# Re-arm watches after atomic saves without scheduling another reload.
			try:
				self._refresh_watched_paths()
			except Exception:
				logger.debug("Failed refreshing watched plugin paths", exc_info=True)
			self._reloading = False
			self._suppress_fs = False
			if self._reload_queued and self._active:
				self._reload_queued = False
				self._pending_reason = "filesystem change (coalesced)"
				self._debounce.start()
