from __future__ import annotations

try:
	import winreg
except Exception:  # pragma: no cover - non-Windows environments
	winreg = None
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import logging

from ..core import PathUtils


class GamePlugin(ABC):
	"""Base class for all game plugins.

	Subclass this to describe a game's save locations and optional
	lifecycle hooks. Implement required properties and override hooks
	if specialized behavior is needed during backup/restore.
	"""

	@property
	@abstractmethod
	def game_id(self) -> str:
		"""Unique identifier for the game."""

	# Runtime-populated fields for plugin asset management. Declared here
	# so static analyzers know these attributes exist when PluginManager
	# assigns to them (e.g. `_saved_icon` and `_icon_source`).
	_saved_icon: str = ""
	_icon_source: str = ""

	@property
	@abstractmethod
	def game_name(self) -> str:
		"""Display name for the game."""

	@property
	@abstractmethod
	def save_paths(self) -> List[str]:
		"""List of possible save paths (contracted form)."""

	@property
	def file_patterns(self) -> List[str]:
		return ["*"]

	@property
	def registry_keys(self) -> List[Tuple[str, str]]:
		return []

	@property
	def icon(self) -> str:
		"""Optional icon for the game (emoji or path to icon file)."""
		return ""  # Default empty string

	# --- Optional lifecycle hooks (override as needed) ---

	def preprocess_backup(self, profile_data: Dict) -> Dict:
		"""Hook called before a backup starts.

		Can mutate and return a new profile dict (e.g. tweak save_path
		or patterns), or just return the original.
		"""

		return profile_data

	def postprocess_backup(self, result_data: Dict) -> Dict:
		"""Hook called after a backup finishes successfully.

		Can add metadata, verify results, etc.
		"""

		return result_data

	def preprocess_restore(self, profile_data: Dict) -> Dict:
		"""Hook called before restore starts."""

		return profile_data

	def postprocess_restore(self, result_data: Dict) -> Dict:
		"""Hook called after restore completes."""

		return result_data

	def is_detected(self) -> bool:
		"""Return True if the game appears installed on the current system.

		Detection uses two strategies:
		- Existence of any `save_paths` after expansion
		- Presence of configured registry keys (Windows only)
		"""
		for path in self.save_paths:
			expanded = PathUtils.expand(path)
			if expanded.exists():
				return True
		# Fall back to registry-based detection (if configured)
		return self._check_registry()

	def _check_registry(self) -> bool:
		# If winreg isn't available (non-Windows), skip registry checks
		if winreg is None:
			return False
		for key_path, value_name in self.registry_keys:
			try:
				if key_path.startswith("HKEY_LOCAL_MACHINE"):
					key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path.replace("HKEY_LOCAL_MACHINE\\", ""))
				else:
					key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path.replace("HKEY_CURRENT_USER\\", ""))
				install_path, _ = winreg.QueryValueEx(key, value_name)
				winreg.CloseKey(key)
				if install_path and Path(install_path).exists():
					return True
			except Exception:
				logging.exception(f"Registry check failed for {key_path} -> {value_name}")
				continue
		return False

	def get_detected_path(self) -> Optional[str]:
		"""Return the first `save_paths` entry that exists on disk, or None.

		The returned value is the *contracted* form (e.g. contains environment
		variables). The UI uses this to pre-fill new profiles.
		"""
		for path in self.save_paths:
			expanded = PathUtils.expand(path)
			if expanded.exists():
				return path
		return None

	def to_profile(self) -> Dict:
		"""Return a serializable profile dict suitable for ConfigManager.

		The profile keys follow the app's internal profile schema and
		are used by the UI when adding a plugin-provided profile.
		"""
		return {
			"id": f"plugin_{self.game_id}",
			"name": self.game_name,
			"save_path": self.get_detected_path() or self.save_paths[0],
			"file_patterns": self.file_patterns,
			"use_compression": True,
			"clear_folder_on_restore": True,
			"plugin_id": self.game_id,
			"icon": self.icon,
		}


def plugin_from_json(data: Dict) -> GamePlugin:
	"""Create a simple data-driven plugin from a JSONC-like descriptor.

	Expected keys: id, name, save_paths, file_patterns?, registry_keys?
	"""

	class JsonGamePlugin(GamePlugin):
		def __init__(self, d: Dict) -> None:
			self._data = d

		@property
		def game_id(self) -> str:
			return self._data["id"]

		@property
		def game_name(self) -> str:
			return self._data["name"]

		@property
		def save_paths(self) -> List[str]:
			return self._data.get("save_paths", [])

		@property
		def file_patterns(self) -> List[str]:
			return self._data.get("file_patterns", ["*"])

		@property
		def registry_keys(self) -> List[Tuple[str, str]]:
			return self._data.get("registry_keys", [])

		@property
		def icon(self) -> str:
			return self._data.get("icon", "")

	return JsonGamePlugin(data)

