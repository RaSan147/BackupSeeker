from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "960910"


class HeavyRainPlugin(GamePlugin):
	"""Heavy Rain - save game locations.

	Supports Steam, Epic Games Store, and regional variants.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "heavy_rain"

	@property
	def game_name(self) -> str:
		return "Heavy Rain"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "saved_games_heavy_rain",
				"label": "Saved Games / Documents",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Saved Games/HeavyRain",
					"%USERPROFILE%/Saved Games/HeavyRainJP",
					"%USERPROFILE%/Documents/HeavyRain",
					"%USERPROFILE%/Documents/HeavyRainJP",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/960910/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
