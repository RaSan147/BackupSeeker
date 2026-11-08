from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "1643320"


class Stalker2HeartOfChornobylPlugin(GamePlugin):
	"""S.T.A.L.K.E.R. 2: Heart of Chornobyl - Windows save locations.

	Supports official Steam, Xbox/Game Pass, GOG, DODI, RUNE, and GSE emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "stalker_2_heart_of_chornobyl"

	@property
	def game_name(self) -> str:
		return "S.T.A.L.K.E.R. 2: Heart of Chornobyl"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "localappdata_stalker2",
				"label": "LocalAppData Stalker 2 Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/Stalker2/Saved/SaveGames",
					"%LOCALAPPDATA%/Stalker2/Saved",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [Stalker2HeartOfChornobylPlugin]
