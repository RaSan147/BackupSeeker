from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import (
	SAVE_KIND_DIRECTORY,
	SAVE_KIND_REGISTRY_WINDOWS,
)

_STEAM_APP_ID = "3021100"


class FiveHeartsUnderOneRoofPlugin(GamePlugin):
	"""Five Hearts Under One Roof (5 Hearts Under 1 Roof / MilkGame) - save game locations.

	Primary saves (userdata.sav, choices, and gallery unlocks) are stored in Unity LocalLow:
	``%USERPROFILE%/AppData/LocalLow/Storytaco/MilkGame``.
	Supports official Steam, Goldberg, GSE, CODEX/DODI, RUNE, and FLT emulators.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "five_hearts_under_one_roof"

	@property
	def game_name(self) -> str:
		return "Five Hearts Under One Roof"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 3021100",
				"value_name": "InstallLocation",
			},
			{
				"id": "storytaco_milkgame_saves",
				"label": "Main Save Data (SavesDir)",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/AppData/LocalLow/Storytaco/MilkGame/SavesDir",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def backup_exclude_globs(self) -> list[str]:
		return ["*.log"]

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/3021100/capsule_616x353.jpg"

	def is_detected(self) -> bool:
		"""Check if Five Hearts Under One Roof is currently installed.

		Verifies:
		1. Steam uninstaller registry key if installed via Steam.
		2. Unity Player.log install path if game was run.
		3. Fallback to standard save directory detection.
		"""
		if self._check_registry():
			return True

		unity_installed = self.is_unity_game_installed("Storytaco", "MilkGame")
		if unity_installed is not None:
			return unity_installed

		return super().is_detected()

	def get_detected_install_path(self) -> Path | None:
		"""Return install path from registry or Unity Player.log."""
		reg_path = super().get_detected_install_path()
		if reg_path is not None and reg_path.exists():
			return reg_path
		return self.get_unity_install_path_from_log("Storytaco", "MilkGame")

	def extra_readme_lines(self) -> list[str]:
		return [
			r"Main Game Saves: %USERPROFILE%\AppData\LocalLow\Storytaco\MilkGame (SavesDir\userdata.sav)",
			r"Steam / Emulator Saves: AppID 3021100",
		]


def get_plugins():
	return auto_get_plugins()

