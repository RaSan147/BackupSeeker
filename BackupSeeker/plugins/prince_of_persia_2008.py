from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "19980"


class PrinceOfPersia2008Plugin(GamePlugin):
	"""Prince of Persia (2008) - Windows save locations.

	Supports official Steam, GOG, DODI, and retail installations.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "prince_of_persia_2008"

	@property
	def game_name(self) -> str:
		return "Prince of Persia (2008)"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		return [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "localappdata_pop",
				"label": "LocalAppData Prince of Persia Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/Ubisoft/Prince of Persia",
					"%USERPROFILE%/Saved Games/Prince of Persia",
					"%USERPROFILE%/Documents/Prince of Persia",
				],
			},
		]

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
