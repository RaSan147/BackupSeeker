from __future__ import annotations

from typing import List

from .base import GamePlugin


class AssassinsCreed3Plugin(GamePlugin):
	@property
	def game_id(self) -> str:
		return "ac3_remastered"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed III Remastered CODEX DODI"

	@property
	def save_paths(self) -> List[str]:
		return [
			"%PUBLIC%\\Documents\\uPlay\\CODEX\\Saves\\AssassinsCreedIIIRemastered",
		]

	@property
	def icon(self) -> str:
		return "⚔️"  # Add an emoji icon

def get_plugins():
	return [AssassinsCreed3Plugin()]

