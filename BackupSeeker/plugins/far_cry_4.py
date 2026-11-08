from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "298110"
_UBISOFT_IDS = ["856", "420"]


class FarCry4Plugin(GamePlugin):
	"""Far Cry 4 - Windows save locations.

	Supports official Steam, Ubisoft Connect, PULS3, RELOADED, Orbit, CODEX, and Goldberg.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "far_cry_4"

	@property
	def game_name(self) -> str:
		return "Far Cry 4"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "orbit_puls3_saves",
				"label": "Orbit / PULS3 Crack Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PROGRAMDATA%/Orbit/856",
					"%PROGRAMDATA%/Orbit/420",
				],
			},
			{
				"id": "codex_saves",
				"label": "CODEX Repack Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PUBLIC%/Documents/uPlay/CODEX/Saves/FarCry4",
				],
			},
			{
				"id": "documents_profile",
				"label": "Documents Profile Settings",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/My Games/Far Cry 4",
					"%ONEDRIVE%/Documents/My Games/Far Cry 4",
				],
			},
			{
				"id": "goldberg_uplay",
				"label": "Goldberg UplayEmu Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					self.get_goldberg_uplay_path("856"),
					self.get_goldberg_uplay_path("420"),
				],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Connect Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": (
					self.get_ubisoft_save_paths("856")
					+ self.get_ubisoft_save_paths("420")
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
