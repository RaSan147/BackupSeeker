from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY


class StrayCodexDodiPlugin(GamePlugin):
	"""Stray CODEX / DODI repack plugin.

	DODI Steam releases usually ship with the CODEX Steam emulator (`steam_codex`).
	Some installs write Unreal saves under Local AppData (`unreal_hk`).
	Both roots are backed up — empty emu folders no longer cause a failed backup.
	"""

	version: str = "1.1.0"

	@property
	def game_id(self) -> str:
		return "stray_codex_dodi"

	@property
	def game_name(self) -> str:
		return "Stray CODEX DODI"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "steam_codex",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [self.get_codex_path("1332010")],
			},
			{
				"id": "unreal_hk",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": ["%LOCALAPPDATA%/Hk_project/Saved/SaveGames"],
			},
		]

	@property
	def icon(self) -> str:
		return "🐈"

	@property
	def poster(self) -> str:
		return "https://upload.wikimedia.org/wikipedia/en/thumb/f/f1/Stray_cover_art.jpg/250px-Stray_cover_art.jpg"


def get_plugins():
	return auto_get_plugins()
