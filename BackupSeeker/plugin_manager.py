from __future__ import annotations

import importlib
import logging
import json
import pkgutil
from pathlib import Path
from typing import Dict, List
import shutil
import urllib.request
import urllib.parse

from .plugins.base import GamePlugin, plugin_from_json


class PluginManager:
	"""Loads code-based and JSON-described game plugins.

	This manager discovers plugin modules under `plugins/` and reads a
	`games.jsonc` file for data-driven plugins. It normalizes imports so
	that the package folder can be renamed without breaking relative
	imports inside plugins.
	"""

	def __init__(self, base_dir: Path) -> None:
		self.base_dir = base_dir
		self.plugins_dir = base_dir / "plugins"
		self.available_plugins: Dict[str, GamePlugin] = {}
		# directory to store downloaded/copied plugin assets (images)
		self.data_dir = Path(base_dir) / "data"
		self.data_dir.mkdir(parents=True, exist_ok=True)
		self.load_plugins()

	def load_plugins(self) -> None:
		self.available_plugins.clear()
		self._load_code_plugins()
		self._load_json_plugins()

	def get_plugin_for_profile(self, plugin_id: str | None) -> GamePlugin | None:
		if not plugin_id:
			return None
		return self.available_plugins.get(plugin_id)

	def _load_code_plugins(self) -> None:
		if not self.plugins_dir.exists():
			return
		for finder, name, ispkg in pkgutil.iter_modules([str(self.plugins_dir)]):
			if name.startswith("__"):
				continue
			try:
				# Import as a proper package submodule so relative imports work,
				# but resolve the current package name dynamically so the folder
				# can be renamed without breaking.
				pkg_name = __package__.rsplit(".", 1)[0]  # e.g. "BackupSeeker"
				full_name = f"{pkg_name}.plugins.{name}"
				module = importlib.import_module(full_name)
				if hasattr(module, "get_plugins"):
					plugins = module.get_plugins()
					for plugin in plugins:
						# process plugin icon (may copy/download into data dir)
						try:
							self._process_plugin_icon(plugin)
						except Exception:
							logging.exception(f"Failed processing icon for plugin {plugin.game_id}")
						self.available_plugins[plugin.game_id] = plugin
			except Exception:
				# Log plugin import errors at debug level; don't crash the app.
				logging.exception(f"Failed importing plugin module {name}")
				continue

	def _load_json_plugins(self) -> None:
		jsonc_path = self.plugins_dir / "games.jsonc"
		if not jsonc_path.exists():
			return
		try:
			# Strip simple // comments for JSONC-like support
			lines = []
			for line in jsonc_path.read_text(encoding="utf-8").splitlines():
				stripped = line.lstrip()
				if stripped.startswith("//"):
					continue
				lines.append(line)
			data = json.loads("\n".join(lines))
			if isinstance(data, list):
				for entry in data:
					try:
						plugin = plugin_from_json(entry)
						try:
							self._process_plugin_icon(plugin)
						except Exception:
							logging.exception(f"Failed processing icon for plugin {plugin.game_id}")
						self.available_plugins[plugin.game_id] = plugin
					except Exception:
						logging.exception(f"Failed constructing plugin from entry: {entry}")
						continue
		except Exception:
			logging.exception("Failed loading JSON plugins")
			return

	def detect_games(self) -> List[Dict]:
		detected: List[Dict] = []
		for plugin in self.available_plugins.values():
			if plugin.is_detected():
				detected.append(plugin.to_profile())
		return detected

	def _process_plugin_icon(self, plugin: GamePlugin) -> None:
		"""Ensure plugin.icon is available under the `data/` folder.

		Behaviors:
		- If `plugin.icon` is an HTTP(S) URL, download it into `data/` and
		  set `plugin._saved_icon` to the saved path string.
		- If `plugin.icon` is a local file path (exists on disk but not under
		  `data/`), copy it into `data/` and set `_saved_icon`.
		- If `plugin.icon` already points inside `data/`, leave as-is and set `_saved_icon`.
		- If empty or appears to be an emoji, leave `_saved_icon` empty.

		Also record original source in `plugin._icon_source` for future updates.
		"""
		icon = getattr(plugin, "icon", "") or ""
		plugin._icon_source = icon
		plugin._saved_icon = ""
		if not icon:
			return
		icon = str(icon)
		# URL
		if icon.lower().startswith(("http://", "https://")):
			try:
				parsed = urllib.parse.urlparse(icon)
				fn = Path(parsed.path).name or f"{plugin.game_id}.img"
				dest = self.data_dir / f"plugin_{plugin.game_id}_{fn}"
				# download (overwrite existing)
				urllib.request.urlretrieve(icon, str(dest))
				plugin._saved_icon = str(dest)
				return
			except Exception:
				logging.exception(f"Failed to download icon for {plugin.game_id} from {icon}")
				return
		# Local path
		p = Path(icon)
		if p.exists():
			try:
				# if already inside data dir, keep as-is
				if self.data_dir in p.parents or p.resolve() == self.data_dir:
					plugin._saved_icon = str(p)
					return
				# copy to data dir
				dest = self.data_dir / f"plugin_{plugin.game_id}_{p.name}"
				shutil.copy2(str(p), str(dest))
				plugin._saved_icon = str(dest)
				return
			except Exception:
				logging.exception(f"Failed to copy plugin icon for {plugin.game_id} from {p}")
				return
		# otherwise: unknown format (emoji or id) - leave as-is
		return

