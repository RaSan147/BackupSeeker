from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class AssassinsCreedRevelationsPlugin(GamePlugin):
	r"""Assassin's Creed Revelations — Theta / Orbit saves under %APPDATA%.

	Use the Revelations Orbit profile folder only (not all of ``Theta``), so
	detection does not match unrelated repacks that reuse ``%APPDATA%\\Theta``.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "assassins_creed_revelations"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed Revelations"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "path_0",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": ["%APPDATA%/Theta/Orbit/40"],
			},
		]

	@property
	def icon(self) -> str:
		return "🔱"

	@property
	def poster(self) -> str:
		return (
			"https://upload.wikimedia.org/wikipedia/en/thumb/d/d9/"
			"Assassins_Creed_Revelations_Cover.jpg/250px-Assassins_Creed_Revelations_Cover.jpg"
		)

	def extra_readme_lines(self) -> List[str]:
		return [
			r"Revelations Orbit saves: %APPDATA%\Theta\Orbit\40 (*.save).",
		]


def get_plugins():
	return auto_get_plugins()
