from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class RedDeadRedemption2Plugin(GamePlugin):
	"""Red Dead Redemption 2 — save game locations.

	Saves are located under Documents/Rockstar Games/Red Dead Redemption 2/Profiles.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "red_dead_redemption_2"

	@property
	def game_name(self) -> str:
		return "Red Dead Redemption 2"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "save_folder",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Rockstar Games/Red Dead Redemption 2/Profiles",
				],
			},
		]

	@property
	def icon(self) -> str:
		return "🤠"

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/1174180/capsule_616x353.jpg"

	@property
	def is_disabled(self) -> bool:
		"""DISABLED: This plugin is currently untested."""
		return True


def get_plugins():
	return auto_get_plugins()
