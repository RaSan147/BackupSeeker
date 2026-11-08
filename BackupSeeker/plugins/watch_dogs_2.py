from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "447040"
_UBISOFT_IDS = ["2688", "3619"]


class WatchDogs2Plugin(GamePlugin):
	"""Watch Dogs 2 - Windows save locations.

	Supports official Steam, Ubisoft Connect, FitGirl, CPY, CODEX, and Goldberg emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "watch_dogs_2"

	@property
	def game_name(self) -> str:
		return "Watch Dogs 2"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "documents_watch_dogs_2",
				"label": "Documents Profile Settings",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/My Games/Watch_Dogs 2",
					"%ONEDRIVE%/Documents/My Games/Watch_Dogs 2",
				],
			},
			{
				"id": "cpy_saves",
				"label": "CPY / FitGirl Repack Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/CPY_SAVES/Player/2688",
					"%USERPROFILE%/Documents/CPY_SAVES/Player/3619",
				],
			},
			{
				"id": "goldberg_uplay",
				"label": "Goldberg UplayEmu Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					self.get_goldberg_uplay_path("2688"),
					self.get_goldberg_uplay_path("3619"),
				],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Connect Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": (
					self.get_ubisoft_save_paths("2688")
					+ self.get_ubisoft_save_paths("3619")
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
