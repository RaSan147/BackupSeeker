from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class DetroitBecomeHumanPlugin(GamePlugin):
	"""Detroit: Become Human — save game locations.

	Saves are located in the user's Saved Games folder.
	Both the official Steam version and common repacks share this path structure.
	"""

	version: str = "1.1.0"

	@property
	def game_id(self) -> str:
		return "detroit_become_human"

	@property
	def game_name(self) -> str:
		return "Detroit: Become Human"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "save_folder",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Saved Games/Quantic Dream/Detroit Become Human",
					"%USERPROFILE%/Documents/Quantic Dream/Detroit Become Human",
					"%USERPROFILE%/Saved Games/Quantic Dream/DETROITPC_IND",
					"%USERPROFILE%/Documents/Quantic Dream/DETROITPC_IND",
				],
			},
		]

	@property
	def icon(self) -> str:
		return "🤖"

	@property
	def poster(self) -> str:
		return "https://upload.wikimedia.org/wikipedia/en/e/ee/Detroit_Become_Human.jpg"

	@property
	def is_disabled(self) -> bool:
		"""DISABLED: This plugin is currently disabled as it is untested on the STOVE store platform."""
		return True

	def is_detected(self) -> bool:
		"""Check standard save paths and STOVE Store installation indicators."""
		if super().is_detected():
			return True

		# Check STOVE Store manifest or installation logs
		try:
			from ..core import PathUtils
			for path in [
				"%LOCALAPPDATA%/STOVE/GameManifest/DETROITPC_IND_6.json",
				"%LOCALAPPDATA%/STOVEPCSDK3/logs/DETROITPC_IND",
			]:
				expanded = PathUtils.expand(path)
				if expanded.exists():
					return True
		except Exception:
			pass
		return False


def get_plugins():
	return auto_get_plugins()
