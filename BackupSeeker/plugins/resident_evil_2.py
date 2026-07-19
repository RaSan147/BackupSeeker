from __future__ import annotations

from typing import Any, Dict, List

from .base import GamePlugin, auto_get_plugins
from .save_sources import (
	CANDIDACY_NO_CANDIDATE_THIS_OR_IDS,
	PROMPT_WHEN_NO_CANDIDATE,
	SAVE_KIND_DIRECTORY,
)

_STEAM_APP_ID = "883710"


class ResidentEvil2Plugin(GamePlugin):
	"""Resident Evil 2 (2019) — Windows save locations.

	Hydra / GSE (Goldberg fork) uses ``%APPDATA%/GSE Saves/<appid>``.
	CODEX/DODI repacks use Public Documents. Vanilla Goldberg uses
	``Goldberg SteamEmu Saves``. Official Steam keeps saves under
	``userdata/<steam id>/883710/remote/win64_save`` — pin when prompted.
	"""

	version: str = "1.1.0"

	_steam_save_prompt = (
		"Steam save folder (win64_save inside userdata/883710/remote)."
	)

	@property
	def game_id(self) -> str:
		return "resident_evil_2_2019"

	@property
	def game_name(self) -> str:
		return "Resident Evil 2 (2019)"

	@property
	def save_sources(self) -> List[Dict[str, Any]]:
		return [
			{
				"id": "gse_saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [f"%APPDATA%/GSE Saves/{_STEAM_APP_ID}"],
			},
			{
				"id": "steam_codex",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [self.get_codex_path(_STEAM_APP_ID)],
			},
			{
				"id": "goldberg_emu",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					f"%APPDATA%/Goldberg SteamEmu Saves/{_STEAM_APP_ID}/remote",
				],
			},
			{
				"id": "steam_userdata",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [],
				"prompt": {
					"when": PROMPT_WHEN_NO_CANDIDATE,
					"candidacy": CANDIDACY_NO_CANDIDATE_THIS_OR_IDS,
					"candidacy_any_of_ids": ["gse_saves", "steam_codex", "goldberg_emu"],
					"input_key": "steam_userdata",
					"message": self._steam_save_prompt,
					"input_kind": "existing_directory",
					"example": (
						r"C:\Program Files (x86)\Steam\userdata\12345678"
						r"\883710\remote\win64_save"
					),
					"editor_label": "Steam save folder",
					"editor_placeholder": "win64_save (userdata/883710/remote)",
				},
			},
		]

	@property
	def icon(self) -> str:
		return "🧟"

	@property
	def poster(self) -> str:
		return (
			"https://upload.wikimedia.org/wikipedia/en/f/fd/Resident_Evil_2_Remake.jpg"
		)

	def extra_readme_lines(self) -> List[str]:
		return [
			"Hydra/GSE: %APPDATA%/GSE Saves/883710 (includes remote/win64_save)",
			"CODEX/DODI: %PUBLIC%/Documents/Steam/CODEX/883710/remote",
			"Goldberg: %APPDATA%/Goldberg SteamEmu Saves/883710/remote",
			"Steam: userdata/<id>/883710/remote/win64_save — pin at steam_userdata when prompted.",
		]


def get_plugins():
	return auto_get_plugins()
