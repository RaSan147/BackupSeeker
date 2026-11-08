from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "33320"
_UBISOFT_ID = "11"


class PrinceOfPersiaForgottenSandsPlugin(GamePlugin):
	"""Prince of Persia: The Forgotten Sands - Windows save locations.

	Supports official Steam, Ubisoft Connect, DODI, Orbit, CODEX, and Goldberg.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "prince_of_persia_forgotten_sands"

	@property
	def game_name(self) -> str:
		return "Prince of Persia: The Forgotten Sands"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		return [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "orbit_saves",
				"label": "Orbit Crack Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					rf"%PROGRAMDATA%/Orbit/{_UBISOFT_ID}",
				],
			},
			{
				"id": "codex_saves",
				"label": "CODEX Repack Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PUBLIC%/Documents/uPlay/CODEX/Saves/PrinceOfPersiaTheForgottenSands",
				],
			},
			{
				"id": "goldberg_uplay",
				"label": "Goldberg UplayEmu Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					self.get_goldberg_uplay_path(_UBISOFT_ID),
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
