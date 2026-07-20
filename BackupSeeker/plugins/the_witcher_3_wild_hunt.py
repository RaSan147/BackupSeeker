from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class TheWitcher3WildHuntPlugin(GamePlugin):
	"""The Witcher 3: Wild Hunt — save game locations.

	Saves are located in the user's Documents folder.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "the_witcher_3_wild_hunt"

	@property
	def game_name(self) -> str:
		return "The Witcher 3: Wild Hunt"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "save_folder",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/The Witcher 3/gamesaves",
				],
			},
		]

	@property
	def icon(self) -> str:
		return "🐺"

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/292030/capsule_616x353.jpg"

	@property
	def is_disabled(self) -> bool:
		"""DISABLED: This plugin is currently untested."""
		return True


def get_plugins():
	return auto_get_plugins()
