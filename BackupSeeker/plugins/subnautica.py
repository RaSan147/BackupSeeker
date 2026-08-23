from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core import PathUtils
from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "264710"


class SubnauticaPlugin(GamePlugin):
	"""Subnautica - save game locations.

	Supports Steam, Epic Games Store, Unity LocalLow layout, and installation folder saves.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "subnautica"

	@property
	def game_name(self) -> str:
		return "Subnautica"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		install_save_paths: list[str] = []
		steam_inst = self.get_steam_app_install_path(_STEAM_APP_ID)
		if steam_inst:
			install_save_paths.append(PathUtils.contract(str(steam_inst / "SNAppData" / "SavedGames")))
		epic_inst = self.get_epic_install_path("Subnautica")
		if epic_inst:
			install_save_paths.append(PathUtils.contract(str(epic_inst / "SNAppData" / "SavedGames")))
		install_save_paths.extend([
			"%PROGRAMFILES(x86)%/Steam/steamapps/common/Subnautica/SNAppData/SavedGames",
			"%PROGRAMFILES%/Steam/steamapps/common/Subnautica/SNAppData/SavedGames",
		])

		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "unity_locallow_saves",
				"label": "Unity LocalLow Saved Games",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/AppData/LocalLow/Unknown Worlds/Subnautica/Subnautica/SavedGames",
				],
			},
			{
				"id": "install_dir_saves",
				"label": "Game Installation Saved Games (SNAppData)",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": install_save_paths,
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/264710/capsule_616x353.jpg"

	def is_detected(self) -> bool:
		if super().is_detected():
			return True
		unity_installed = self.is_unity_game_installed("Unknown Worlds", "Subnautica")
		if unity_installed is not None:
			return unity_installed
		return False

	def get_detected_install_path(self) -> Path | None:
		reg_path = super().get_detected_install_path()
		if reg_path is not None and reg_path.exists():
			return reg_path
		return self.get_unity_install_path_from_log("Unknown Worlds", "Subnautica")


def get_plugins():
	return auto_get_plugins()
