from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "204100"


class MaxPayne3Plugin(GamePlugin):
	"""Max Payne 3 - Windows save locations.

	Supports official Steam, Rockstar Games Launcher, SuperDex, Reloaded, and Goldberg.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "max_payne_3"

	@property
	def game_name(self) -> str:
		return "Max Payne 3"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "rockstar_documents",
				"label": "Rockstar Games Documents Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Rockstar Games/Max Payne 3/Profiles",
					"%USERPROFILE%/Documents/Rockstar Games/Max Payne 3",
					"%ONEDRIVE%/Documents/Rockstar Games/Max Payne 3/Profiles",
				],
			},
			{
				"id": "goldberg_social_club",
				"label": "Goldberg Social Club Emu Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					self.get_goldberg_social_club_path("Max Payne 3"),
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
