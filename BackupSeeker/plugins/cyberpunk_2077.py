from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "1091500"
_GOG_ID = "1423049311"


class Cyberpunk2077Plugin(GamePlugin):
	"""Cyberpunk 2077 - save game locations.

	Saves are located in Saved Games across Steam, GOG, Epic, and repacks.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "cyberpunk_2077"

	@property
	def game_name(self) -> str:
		return "Cyberpunk 2077"

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
				"id": "saved_games",
				"label": "CD Projekt Red Saved Games",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Saved Games/CD Projekt Red/Cyberpunk 2077",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/1091500/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
