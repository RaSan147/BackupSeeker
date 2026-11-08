from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "1715130"


class CrysisRemasteredPlugin(GamePlugin):
	"""Crysis Remastered - Windows save locations.

	Supports official Steam, Epic Games, DODI, and CPY emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "crysis_remastered"

	@property
	def game_name(self) -> str:
		return "Crysis Remastered"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		return [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "saved_games_crysis",
				"label": "Saved Games Crysis Remastered",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Saved Games/CrysisRemastered/Save Games",
					"%USERPROFILE%/Saved Games/CrysisRemastered",
				],
			},
		]

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
