from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "227300"


class EuroTruckSimulator2Plugin(GamePlugin):
	"""Euro Truck Simulator 2 - save game locations.

	Supports standard profiles, Steam Cloud profiles, and emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "euro_truck_simulator_2"

	@property
	def game_name(self) -> str:
		return "Euro Truck Simulator 2"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "ets2_profiles",
				"label": "Documents ETS2 Profiles",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Euro Truck Simulator 2/profiles",
					"%USERPROFILE%/Documents/Euro Truck Simulator 2/steam_profiles",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/227300/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
