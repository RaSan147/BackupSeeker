from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class HeavyRainPlugin(GamePlugin):
	"""Heavy Rain — save game locations.

	Saves are located in the user's Saved Games folder (with alternative folder name for Japanese version).
	Supports OneDrive documents and Saved Games redirections.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "heavy_rain"

	@property
	def game_name(self) -> str:
		return "Heavy Rain"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "save_folder",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Saved Games/HeavyRain",
					"%USERPROFILE%/Saved Games/HeavyRainJP",
					"%USERPROFILE%/OneDrive/Saved Games/HeavyRain",
					"%USERPROFILE%/OneDrive/Saved Games/HeavyRainJP",
					"%USERPROFILE%/Documents/HeavyRain",
					"%USERPROFILE%/Documents/HeavyRainJP",
					"%USERPROFILE%/OneDrive/Documents/HeavyRain",
					"%USERPROFILE%/OneDrive/Documents/HeavyRainJP",
				],
			},
		]

	@property
	def icon(self) -> str:
		return "🌧️"

	@property
	def poster(self) -> str:
		return "https://upload.wikimedia.org/wikipedia/en/c/c1/Heavy_Rain_Cover_Art.jpg"


def get_plugins():
	return auto_get_plugins()
