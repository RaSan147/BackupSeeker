from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "367520"
_GOG_ID = "1341052601"


class HollowKnightPlugin(GamePlugin):
	"""Hollow Knight - save game locations.

	Supports Steam, GOG, Unity Player.log detection, and emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "hollow_knight"

	@property
	def game_name(self) -> str:
		return "Hollow Knight"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\GOG.com\Games\{_GOG_ID}",
				"value_name": "path",
			},
			{
				"id": "team_cherry_saves",
				"label": "Team Cherry Unity LocalLow Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/AppData/LocalLow/Team Cherry/Hollow Knight",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/367520/capsule_616x353.jpg"

	def is_detected(self) -> bool:
		if self._check_registry():
			return True
		unity_installed = self.is_unity_game_installed("Team Cherry", "Hollow Knight")
		if unity_installed is not None:
			return unity_installed
		return super().is_detected()

	def get_detected_install_path(self) -> Path | None:
		reg_path = super().get_detected_install_path()
		if reg_path is not None and reg_path.exists():
			return reg_path
		return self.get_unity_install_path_from_log("Team Cherry", "Hollow Knight")


def get_plugins():
	return auto_get_plugins()
