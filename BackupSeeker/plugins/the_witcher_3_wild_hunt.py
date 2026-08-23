from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "292030"
_GOG_ID_STD = "1207664643"
_GOG_ID_GOTY = "1495134320"


class TheWitcher3WildHuntPlugin(GamePlugin):
	"""The Witcher 3: Wild Hunt - save game locations.

	Supports Steam, GOG (Standard & GOTY), Epic Games Store, and emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "the_witcher_3_wild_hunt"

	@property
	def game_name(self) -> str:
		return "The Witcher 3: Wild Hunt"

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
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\GOG.com\Games\{_GOG_ID_STD}",
				"value_name": "path",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\GOG.com\Games\{_GOG_ID_GOTY}",
				"value_name": "path",
			},
			{
				"id": "documents_gamesaves",
				"label": "Documents Game Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/The Witcher 3/gamesaves",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/292030/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
