from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "1086940"
_GOG_ID = "1456460669"


class BaldursGate3Plugin(GamePlugin):
	"""Baldur's Gate 3 - save game locations.

	Supports Steam, GOG, and emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "baldurs_gate_3"

	@property
	def game_name(self) -> str:
		return "Baldur's Gate 3"

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
				"id": "larian_profiles",
				"label": "Larian Studios PlayerProfiles",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/Larian Studios/Baldur's Gate 3/PlayerProfiles",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/1086940/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
