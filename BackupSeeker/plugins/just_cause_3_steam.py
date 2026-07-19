from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class JustCause3SteamPlugin(GamePlugin):
	"""Just Cause 3 — Steam / retail Windows saves.

	Local profile data lives under the user Documents tree (Square Enix layout).
	Steam Cloud uses per-account userdata folders; this plugin targets the shared
	on-disk save location used by the Steam build.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "just_cause_3_steam"

	@property
	def game_name(self) -> str:
		return "Just Cause 3 (Steam)"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "path_0",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Square Enix/Just Cause 3/Saves",
					"%USERPROFILE%/Documents/My Games/Just Cause 3/Saves",
				],
			},
		]

	@property
	def icon(self) -> str:
		return "🪂"

	@property
	def poster(self) -> str:
		return "https://upload.wikimedia.org/wikipedia/en/thumb/f/f2/Just_Cause_3_cover_art.jpg/250px-Just_Cause_3_cover_art.jpg"


def get_plugins():
	return auto_get_plugins()
