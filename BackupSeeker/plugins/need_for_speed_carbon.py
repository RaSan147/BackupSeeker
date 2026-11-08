from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class NeedForSpeedCarbonPlugin(GamePlugin):
	"""Need for Speed: Carbon - Windows save locations.

	Supports retail and remastered DODI repacks.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "need_for_speed_carbon"

	@property
	def game_name(self) -> str:
		return "Need for Speed: Carbon"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		return [
			{
				"id": "documents_nfs_carbon",
				"label": "Documents NFS Carbon Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/NFS Carbon",
					"%ONEDRIVE%/Documents/NFS Carbon",
					"%APPDATA%/NFS Carbon",
				],
			},
		]

	@property
	def poster(self) -> str:
		return "https://upload.wikimedia.org/wikipedia/en/2/2a/Need_for_Speed_Carbon_Coverart.jpg"


def get_plugins():
	return auto_get_plugins()
