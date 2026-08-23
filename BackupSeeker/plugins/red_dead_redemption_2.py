from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "1174180"


class RedDeadRedemption2Plugin(GamePlugin):
	"""Red Dead Redemption 2 - save game locations.

	Supports Rockstar Games Launcher, Steam, Epic Games Store, and emulated releases.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "red_dead_redemption_2"

	@property
	def game_name(self) -> str:
		return "Red Dead Redemption 2"

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
				"key_path": r"HKEY_LOCAL_MACHINE\SOFTWARE\Rockstar Games\Red Dead Redemption 2",
				"value_name": "InstallFolder",
			},
			{
				"id": "rockstar_profiles",
				"label": "Rockstar Games Profiles (Steam / Epic / Retail)",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Rockstar Games/Red Dead Redemption 2/Profiles",
				],
			},
			{
				"id": "goldberg_sc",
				"label": "Goldberg Social Club Emulator Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%APPDATA%/Goldberg SocialClubEmu Saves/RDR2",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/1174180/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
