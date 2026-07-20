from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class MinecraftPlugin(GamePlugin):
	"""Minecraft — save game locations.

	Saves are located under AppData/Roaming/.minecraft/saves.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "minecraft"

	@property
	def game_name(self) -> str:
		return "Minecraft"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "save_folder",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%APPDATA%/.minecraft/saves",
				],
			},
		]

	@property
	def icon(self) -> str:
		return "⛏️"

	@property
	def poster(self) -> str:
		return "https://upload.wikimedia.org/wikipedia/en/5/51/Minecraft_cover_art.jpg"

	@property
	def is_disabled(self) -> bool:
		"""DISABLED: This plugin is currently untested."""
		return True


def get_plugins():
	return auto_get_plugins()
