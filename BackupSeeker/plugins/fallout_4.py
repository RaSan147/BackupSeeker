from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "377160"
_GOG_ID = "1998527297"


class Fallout4Plugin(GamePlugin):
	"""Fallout 4 - save game locations.

	Supports Steam, GOG, Microsoft Store / PC Game Pass, and emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "fallout_4"

	@property
	def game_name(self) -> str:
		return "Fallout 4"

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
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": r"HKEY_LOCAL_MACHINE\SOFTWARE\Bethesda Softworks\Fallout4",
				"value_name": "Installed Path",
			},
			{
				"id": "fallout4_saves",
				"label": "Fallout 4 Saves (Steam / GOG / MS Store)",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/My Games/Fallout4/Saves",
					"%USERPROFILE%/Documents/My Games/Fallout4 GOG/Saves",
					"%USERPROFILE%/Documents/My Games/Fallout4 MS/Saves",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/377160/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
