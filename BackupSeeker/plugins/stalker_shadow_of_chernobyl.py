from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "4500"


class StalkerShadowOfChernobylPlugin(GamePlugin):
	"""S.T.A.L.K.E.R.: Shadow of Chernobyl - Windows save locations.

	Supports official Steam, GOG, DODI, and retail installations.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "stalker_shadow_of_chernobyl"

	@property
	def game_name(self) -> str:
		return "S.T.A.L.K.E.R.: Shadow of Chernobyl"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "public_documents_saves",
				"label": "Public Documents Saved Games",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PUBLIC%/Documents/stalker-shoc/savedgames",
					"%PUBLIC%/Documents/STALKER-SHOC/savedgames",
					"%USERPROFILE%/Documents/stalker-shoc/savedgames",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [StalkerShadowOfChernobylPlugin]
