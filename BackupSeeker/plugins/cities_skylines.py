from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "255710"


class CitiesSkylinesPlugin(GamePlugin):
	"""Cities: Skylines - save game locations.

	Supports Steam, Epic Games Store, and emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "cities_skylines"

	@property
	def game_name(self) -> str:
		return "Cities: Skylines"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "colossal_order_saves",
				"label": "Colossal Order Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/Colossal Order/Cities_Skylines/Saves",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/255710/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
