from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class AssassinsCreed3Plugin(GamePlugin):
	"""Assassin's Creed III Remastered CODEX/DODI plugin."""
	
	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "ac3_remastered"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed III Remastered CODEX DODI"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "path_0",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": ["%PUBLIC%/Documents/uPlay/CODEX/Saves/AssassinsCreedIIIRemastered"],
			},
		]

	@property
	def icon(self) -> str:
		return "⚔️"  # Swords emoji fits the theme

	@property
	def poster(self) -> str:
		return "https://upload.wikimedia.org/wikipedia/en/2/29/Assassin%27s_Creed_III_Game_Cover.jpg"


def get_plugins():
	"""Use auto_get_plugins() for cleaner auto-discovery."""
	return auto_get_plugins()

