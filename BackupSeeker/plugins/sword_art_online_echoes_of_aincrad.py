from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class SwordArtOnlineEchoesOfAincradPlugin(GamePlugin):
	"""Sword Art Online: Echoes of Aincrad — save game locations.

	Saves (.sav files) are located in %LOCALAPPDATA%/EchoesofAincrad/Saved/SaveGames.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "sword_art_online_echoes_of_aincrad"

	@property
	def game_name(self) -> str:
		return "Sword Art Online: Echoes of Aincrad"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "save_folder",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/EchoesofAincrad/Saved/SaveGames",
				],
			},
		]

	@property
	def icon(self) -> str:
		return "⚔️"

	@property
	def poster(self) -> str:
		return "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2244210/25fb6350451b21ca824562c8d1eebe89091347cc/header.jpg"


def get_plugins():
	return auto_get_plugins()
