from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class CoffinOfAndyAndLeyleyPlugin(GamePlugin):
	"""The Coffin of Andy and Leyley — save game locations.

	Saves are located in the user's Local AppData folder under CoffinAndyLeyley.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "the_coffin_of_andy_and_leyley"

	@property
	def game_name(self) -> str:
		return "The Coffin of Andy and Leyley"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "save_folder",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": ["%APPDATA%/CoffinAndyLeyley"],
			},
		]

	@property
	def icon(self) -> str:
		return "⚰️"

	@property
	def poster(self) -> str:
		return "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2378900/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
