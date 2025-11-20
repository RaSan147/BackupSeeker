from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path
from typing import Dict, List

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
						self.available_plugins[plugin.game_id] = plugin
			except Exception:
				# Silently ignore plugin import errors so broken third-party
				# plugins don't crash the whole app. If you need to debug a
				# failing plugin, run the app from the command line to see
				# the exception traceback.
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
						self.available_plugins[plugin.game_id] = plugin
					except Exception:
						continue
		except Exception:
			return

	def detect_games(self) -> List[Dict]:
		detected: List[Dict] = []
		for plugin in self.available_plugins.values():
			if plugin.is_detected():
				detected.append(plugin.to_profile())
		return detected

