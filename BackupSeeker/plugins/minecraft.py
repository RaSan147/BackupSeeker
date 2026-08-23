from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class MinecraftPlugin(GamePlugin):
	"""Minecraft - save game locations.

	Supports Java Edition, Bedrock (Windows Store) Edition, and modded launchers.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "minecraft"

	@property
	def game_name(self) -> str:
		return "Minecraft"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		return [
			{
				"id": "minecraft_java_saves",
				"label": "Minecraft Java Edition Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%APPDATA%/.minecraft/saves",
				],
			},
			{
				"id": "minecraft_bedrock_worlds",
				"label": "Minecraft Bedrock (UWP) Worlds",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/Packages/Microsoft.MinecraftUWP_8wekyb3d8bbwe/LocalState/games/com.mojang/minecraftWorlds",
				],
			},
		]

	@property
	def poster(self) -> str:
		return "https://images.igdb.com/igdb/image/upload/t_screenshot_big/sc66m7.jpg"


def get_plugins():
	return auto_get_plugins()
