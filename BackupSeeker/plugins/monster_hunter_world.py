from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class MonsterHunterWorldPlugin(GamePlugin):
	"""Monster Hunter: World — save game locations."""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "monster_hunter_world"

	@property
	def game_name(self) -> str:
		return "Monster Hunter: World"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "save_folder",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PROGRAMFILES(x86)%/Steam/userdata/*/582010/remote",
				],
			},
		]

	@property
	def icon(self) -> str:
		return "🦖"

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/582010/capsule_616x353.jpg"

	@property
	def is_disabled(self) -> bool:
		"""DISABLED: This plugin is currently untested."""
		return True


def get_plugins():
	return auto_get_plugins()
