"""Filesystem watcher that hot-reloads plugins while the app is running."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QFileSystemWatcher, QTimer, pyqtSignal

if TYPE_CHECKING:
	from .plugin_manager import PluginLoadReport, PluginManager

logger = logging.getLogger(__name__)


class PluginHotReloader(QObject):
	"""Watch ``plugins/`` and debounce hot reloads into :class:`PluginManager`."""

	reload_finished = pyqtSignal(object)

	def __init__(self, manager: PluginManager, *, debounce_ms: int = 450) -> None:
		super().__init__()
		self._manager = manager
		self._plugins_dir = Path(manager.plugins_dir)
		self._watcher = QFileSystemWatcher(self)
		self._debounce = QTimer(self)
		self._debounce.setSingleShot(True)
		self._debounce.setInterval(max(150, debounce_ms))
		self._debounce.timeout.connect(self._run_reload)
		self._watcher.fileChanged.connect(self._on_fs_event)
		self._watcher.directoryChanged.connect(self._on_fs_event)
		self._active = False
		self._pending_reason = "filesystem change"

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
		for path in list(self._watcher.files()):
			self._watcher.removePath(path)
		for path in list(self._watcher.directories()):
			self._watcher.removePath(path)

	def reload_now(self, *, reason: str = "manual") -> object:
		"""Run an immediate hot reload (used by the Reload Plugins button)."""

		self._pending_reason = reason
		self._debounce.stop()
		return self._run_reload()

	def _on_fs_event(self, _path: str) -> None:
		if not self._active:
			return
		self._pending_reason = "filesystem change"
		self._refresh_watched_paths()
		self._debounce.start()

	def _refresh_watched_paths(self) -> None:
		"""Track each plugin ``.py`` and JSON index file (QFileSystemWatcher is non-recursive)."""

		if not self._plugins_dir.exists():
			return
		desired: set[str] = set()
		for py_file in self._plugins_dir.rglob("*.py"):
			desired.add(str(py_file.resolve()))
		for name in ("games.jsonc", "plugin_index.json"):
			p = self._plugins_dir / name
			if p.exists():
				desired.add(str(p.resolve()))

		current = set(self._watcher.files())
		for path in current - desired:
			self._watcher.removePath(path)
		for path in desired - current:
			self._watcher.addPath(path)

	def _run_reload(self) -> object:
		from .plugin_manager import PluginLoadReport

		reason = self._pending_reason
		logger.info("Hot-reloading plugins (%s)", reason)
		report = self._manager.reload_plugins(hot=True)
		if not isinstance(report, PluginLoadReport):
			report = self._manager.last_load_report
		self.reload_finished.emit(report)
		return report
