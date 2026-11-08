from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "243470"
_UBISOFT_IDS = ["274", "541"]


class WatchDogsPlugin(GamePlugin):
	"""Watch Dogs - Windows save locations.

	Supports official Steam, Ubisoft Connect, KaOs, RELOADED, Orbit, and Goldberg emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "watch_dogs"

	@property
	def game_name(self) -> str:
		return "Watch Dogs"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "documents_watch_dogs",
				"label": "Documents Profile Settings",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/My Games/Watch_Dogs",
					"%ONEDRIVE%/Documents/My Games/Watch_Dogs",
				],
			},
			{
				"id": "orbit_saves",
				"label": "Orbit Crack Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PROGRAMDATA%/Orbit/274",
					"%PROGRAMDATA%/Orbit/541",
				],
			},
			{
				"id": "goldberg_uplay",
				"label": "Goldberg UplayEmu Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					self.get_goldberg_uplay_path("274"),
					self.get_goldberg_uplay_path("541"),
				],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Connect Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": (
					self.get_ubisoft_save_paths("274")
					+ self.get_ubisoft_save_paths("541")
				),
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
