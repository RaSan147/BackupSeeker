from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "20510"


class StalkerClearSkyPlugin(GamePlugin):
	"""S.T.A.L.K.E.R.: Clear Sky - Windows save locations.

	Supports official Steam, GOG, DODI, and retail installations.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "stalker_clear_sky"

	@property
	def game_name(self) -> str:
		return "S.T.A.L.K.E.R.: Clear Sky"

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
					"%PUBLIC%/Documents/STALKER-STCS/savedgames",
					"%PUBLIC%/Documents/stalker-stcs/savedgames",
					"%USERPROFILE%/Documents/STALKER-STCS/savedgames",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [StalkerClearSkyPlugin]
