"""Central poster download + UI refresh orchestration."""

from __future__ import annotations

import logging
from typing import Callable, Dict

from PyQt6.QtCore import QTimer

from ..plugin_manager import PluginManager

logger = logging.getLogger(__name__)

RefreshTarget = Callable[[str | None], None]

_STAGGER_MS = 400


class PosterRefreshCoordinator:
	"""Queue plugin poster downloads and notify UI pages when assets arrive."""

	def __init__(self, plugin_manager: PluginManager) -> None:
		self._pm = plugin_manager
		self._targets: list[RefreshTarget] = []

	def register(self, target: RefreshTarget) -> None:
		if target not in self._targets:
			self._targets.append(target)

	def kick_loads(self, games: Dict[str, object]) -> None:
		"""Hydrate cached posters immediately; only stagger network fetches for missing files."""

		plugins = self._unique_plugins(games)
		pending: list[object] = []

		for plugin in plugins:
			if self._pm.hydrate_plugin_from_cache(plugin):
				pending.append(plugin)

		self._notify(None)

		if not pending:
			return

		for index, plugin in enumerate(pending):
			QTimer.singleShot(
				index * _STAGGER_MS,
				lambda p=plugin: self._pm.ensure_plugin_visual_assets(
					p,
					on_complete=lambda g=p: self._notify(
						(getattr(g, "game_id", "") or "").strip() or None
					),
				),
			)

	def on_assets_ready(self, plugin: object) -> None:
		gid = (getattr(plugin, "game_id", "") or "").strip() or None
		QTimer.singleShot(0, lambda: self._notify(gid))

	def _unique_plugins(self, games: Dict[str, object]) -> list[object]:
		seen: set[str] = set()
		plugins: list[object] = []
		for profile in games.values():
			pid = (getattr(profile, "plugin_id", "") or "").strip()
			if not pid or pid in seen:
				continue
			seen.add(pid)
			plugin = self._pm.available_plugins.get(pid)
			if plugin is not None:
				plugins.append(plugin)
		return plugins

	def _notify(self, plugin_game_id: str | None) -> None:
		for target in self._targets:
			try:
				target(plugin_game_id)
			except Exception:
				logger.exception("Poster refresh target failed for %r", plugin_game_id)
