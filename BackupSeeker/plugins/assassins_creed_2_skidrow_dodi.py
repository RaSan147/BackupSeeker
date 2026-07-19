from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import PROMPT_WHEN_NO_CANDIDATE, SAVE_KIND_DIRECTORY


class AssassinsCreed2SkidrowDodiPlugin(GamePlugin):
	r"""Assassin's Creed II — SKIDROW/DODI saves under ``storage\SKIDROW\4`` relative to install.

	Profile pin: same key as directory ``id`` / ``prompt.input_key`` (``path_0``). Effective
	save root = pin + ``pin_relative_segments`` (see :mod:`~BackupSeeker.plugins.save_sources`).
	"""

	version: str = "1.0.0"

	_install_prompt = "Install folder (contains storage)."

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "path_0",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PROGRAMFILES(X86)%/Steam/steamapps/common/Assassin's Creed 2/storage/SKIDROW/4",
					"%PROGRAMFILES%/Steam/steamapps/common/Assassin's Creed 2/storage/SKIDROW/4",
					"%PROGRAMFILES(X86)%/Steam/steamapps/common/Assassins Creed II/storage/SKIDROW/4",
					"%PROGRAMFILES%/Steam/steamapps/common/Assassins Creed II/storage/SKIDROW/4",
					"%USERPROFILE%/Saved Games/Assassins Creed 2",
				],
				"pin_relative_segments": ["storage", "SKIDROW", "4"],
				"prompt": {
					"when": PROMPT_WHEN_NO_CANDIDATE,
					"input_key": "path_0",
					"message": self._install_prompt,
					"input_kind": "existing_directory",
					"example": r"D:\Games\Assassins Creed II",
					"editor_label": "Install folder",
					"editor_placeholder": "Contains storage (game install folder)",
				},
			},
		]

	@property
	def game_id(self) -> str:
		return "assassins_creed_2_skidrow_dodi"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed II SKIDROW DODI"

	@property
	def icon(self) -> str:
		return "🏛️"

	@property
	def poster(self) -> str:
		return (
			"https://upload.wikimedia.org/wikipedia/en/thumb/7/77/"
			"Assassins_Creed_2_Box_Art.JPG/250px-Assassins_Creed_2_Box_Art.JPG"
		)

	def extra_readme_lines(self) -> List[str]:
		return [
			r"Saves live at <install>\storage\SKIDROW\4 — pin install folder at path_0 when prompted.",
		]


def get_plugins():
	return auto_get_plugins()
