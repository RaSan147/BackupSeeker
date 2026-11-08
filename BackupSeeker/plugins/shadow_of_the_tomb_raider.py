from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "750920"


class ShadowOfTheTombRaiderPlugin(GamePlugin):
	"""Shadow of the Tomb Raider: Definitive Edition - Windows save locations.

	Supports official Steam, Epic Games, DODI, CPY, CODEX, Goldberg, and GSE.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "shadow_of_the_tomb_raider"

	@property
	def game_name(self) -> str:
		return "Shadow of the Tomb Raider"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "documents_sotr",
				"label": "Documents Shadow of the Tomb Raider Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Shadow of the Tomb Raider",
					"%ONEDRIVE%/Documents/Shadow of the Tomb Raider",
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
