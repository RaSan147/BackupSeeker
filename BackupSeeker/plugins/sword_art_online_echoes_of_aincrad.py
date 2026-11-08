from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "2244210"


class SwordArtOnlineEchoesOfAincradPlugin(GamePlugin):
	"""Sword Art Online: Echoes of Aincrad - save game locations.

	Saves (.sav files) are located in %LOCALAPPDATA%/EchoesofAincrad/Saved/SaveGames.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "sword_art_online_echoes_of_aincrad"

	@property
	def game_name(self) -> str:
		return "Sword Art Online: Echoes of Aincrad"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "unreal_saved_games",
				"label": "Unreal Engine SaveGames",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/EchoesofAincrad/Saved/SaveGames",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2244210/25fb6350451b21ca824562c8d1eebe89091347cc/header.jpg"


EXPORT = [SwordArtOnlineEchoesOfAincradPlugin]
