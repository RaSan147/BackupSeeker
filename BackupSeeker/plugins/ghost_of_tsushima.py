from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "2215430"


class GhostOfTsushimaPlugin(GamePlugin):
	"""Ghost of Tsushima DIRECTOR'S CUT - Windows save locations.

	Supports official Steam, Epic Games, RUNE, Goldberg, DODI/CODEX, and GSE emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "ghost_of_tsushima"

	@property
	def game_name(self) -> str:
		return "Ghost of Tsushima DIRECTOR'S CUT"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "documents_saves",
				"label": "Documents Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Ghost of Tsushima DIRECTOR'S CUT",
					"%ONEDRIVE%/Documents/Ghost of Tsushima DIRECTOR'S CUT",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [GhostOfTsushimaPlugin]
