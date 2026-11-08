from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "241560"
_UBISOFT_ID = "413"


class TheCrewPlugin(GamePlugin):
	"""The Crew - Windows save and config locations.

	Supports official Steam, Ubisoft Connect, ElAmigos, and community server emulator saves.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "the_crew"

	@property
	def game_name(self) -> str:
		return "The Crew"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		return [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "documents_the_crew",
				"label": "Documents The Crew Settings & Cache",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/The Crew",
					"%ONEDRIVE%/Documents/The Crew",
				],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Connect Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": self.get_ubisoft_save_paths(_UBISOFT_ID),
			},
		]

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
