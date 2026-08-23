from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import (
	CANDIDACY_NO_CANDIDATE_THIS_OR_IDS,
	PROMPT_WHEN_NO_CANDIDATE,
	SAVE_KIND_DIRECTORY,
	SAVE_KIND_REGISTRY_WINDOWS,
)

_STEAM_APP_ID = "883710"


class ResidentEvil2Plugin(GamePlugin):
	"""Resident Evil 2 (2019) - Windows save locations.

	Hydra / GSE (Goldberg fork) uses ``%APPDATA%/GSE Saves/<appid>``.
	CODEX/DODI repacks use Public Documents. Vanilla Goldberg uses
	``Goldberg SteamEmu Saves``. Official Steam keeps saves under
	``userdata/<steam id>/883710/remote/win64_save``.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.1.0"

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
	def save_sources(self) -> list[dict[str, Any]]:
		steam_paths = self.get_steam_userdata_paths(_STEAM_APP_ID, "remote/win64_save")
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "steam_userdata",
				"label": "Steam Official (win64_save)",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": steam_paths,
				"prompt": {
					"when": PROMPT_WHEN_NO_CANDIDATE,
					"candidacy": CANDIDACY_NO_CANDIDATE_THIS_OR_IDS,
					"candidacy_any_of_ids": ["gse_saves", "steam_codex", "goldberg_emu"],
					"input_key": "steam_userdata",
					"message": self._steam_save_prompt,
					"input_kind": "existing_directory",
					"example": r"C:\Program Files (x86)\Steam\userdata\12345678\883710\remote\win64_save",
					"editor_label": "Steam save folder",
					"editor_placeholder": "win64_save (userdata/883710/remote)",
				},
			},
			{
				"id": "gse_saves",
				"label": "GSE / Hydra Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [f"%APPDATA%/GSE Saves/{_STEAM_APP_ID}"],
			},
			{
				"id": "steam_codex",
				"label": "CODEX / DODI Repack",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [self.get_codex_path(_STEAM_APP_ID)],
			},
			{
				"id": "tenoke",
				"label": "TENOKE Repack",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [self.get_tenoke_path(_STEAM_APP_ID), f"{self.get_tenoke_path(_STEAM_APP_ID)}/remote"],
			},
			{
				"id": "goldberg_emu",
				"label": "Goldberg Steam Emulator",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					f"%APPDATA%/Goldberg SteamEmu Saves/{_STEAM_APP_ID}/remote",
				],
			},
			{
				"id": "rune",
				"label": "RUNE Repack",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [self.get_rune_path(_STEAM_APP_ID, "remote/win64_save"), self.get_rune_path(_STEAM_APP_ID)],
			},
			{
				"id": "flt",
				"label": "FairLight (FLT) Repack",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [self.get_flt_path(_STEAM_APP_ID, "remote/win64_save"), self.get_flt_path(_STEAM_APP_ID)],
			},
		]
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/883710/capsule_616x353.jpg"

	def extra_readme_lines(self) -> list[str]:
		return [
			"Hydra/GSE: %APPDATA%/GSE Saves/883710 (includes remote/win64_save)",
			"CODEX/DODI: %PUBLIC%/Documents/Steam/CODEX/883710/remote",
			"Goldberg: %APPDATA%/Goldberg SteamEmu Saves/883710/remote",
			"Steam: userdata/<id>/883710/remote/win64_save - pin at steam_userdata when prompted.",
		]


def get_plugins():
	return auto_get_plugins()
