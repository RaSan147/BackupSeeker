from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "374320"


class DarkSouls3Plugin(GamePlugin):
	"""Dark Souls III - save game locations.

	Supports official Steam, CODEX, Goldberg, GSE, RUNE, and other emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "dark_souls_3"

	@property
	def game_name(self) -> str:
		return "Dark Souls III"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "appdata_darksouls3",
				"label": "Dark Souls III AppData Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%APPDATA%/DarkSoulsIII",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [DarkSouls3Plugin]
