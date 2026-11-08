from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "1817070"


class SpidermanRemasteredPlugin(GamePlugin):
	"""Marvel's Spider-Man Remastered - Windows save locations.

	Supports official Steam, Epic Games, FLT, RUNE, Goldberg, DODI/CODEX, and GSE.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "marvels_spider_man_remastered"

	@property
	def game_name(self) -> str:
		return "Marvel's Spider-Man Remastered"

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
					"%USERPROFILE%/Documents/Marvel's Spider-Man Remastered",
					"%ONEDRIVE%/Documents/Marvel's Spider-Man Remastered",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
