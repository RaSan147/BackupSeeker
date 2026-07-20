from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class BaldursGate3Plugin(GamePlugin):
	"""Baldur's Gate 3 — save game locations."""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "baldurs_gate_3"

	@property
	def game_name(self) -> str:
		return "Baldur's Gate 3"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "save_folder",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/Larian Studios/Baldur's Gate 3/PlayerProfiles",
				],
			},
		]

	@property
	def icon(self) -> str:
		return "🎲"

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/1086940/capsule_616x353.jpg"

	@property
	def is_disabled(self) -> bool:
		"""DISABLED: This plugin is currently untested."""
		return True


def get_plugins():
	return auto_get_plugins()
