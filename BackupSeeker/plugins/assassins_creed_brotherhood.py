from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class AssassinsCreedBrotherhoodPlugin(GamePlugin):
	"""Assassin's Creed Brotherhood — Windows Saved Games folder (matches common Uplay/retail layout)."""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "assassins_creed_brotherhood"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed Brotherhood"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "path_0",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": ["%USERPROFILE%/Saved Games/Assassin's Creed Brotherhood"],
			},
		]

	@property
	def icon(self) -> str:
		return "🦅"

	@property
	def poster(self) -> str:
		return (
			"https://upload.wikimedia.org/wikipedia/en/thumb/2/2a/"
			"Assassins_Creed_brotherhood_cover.jpg/250px-Assassins_Creed_brotherhood_cover.jpg"
		)


def get_plugins():
	return auto_get_plugins()
