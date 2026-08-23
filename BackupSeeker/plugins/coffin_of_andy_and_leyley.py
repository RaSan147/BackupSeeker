from __future__ import annotations

from typing import Any

from ..core import PathUtils
from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "2378900"


class CoffinOfAndyAndLeyleyPlugin(GamePlugin):
	"""The Coffin of Andy and Leyley - save game locations.

	Saves are located in AppData or the game installation save folder.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "the_coffin_of_andy_and_leyley"

	@property
	def game_name(self) -> str:
		return "The Coffin of Andy and Leyley"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		install_paths: list[str] = []
		steam_inst = self.get_steam_app_install_path(_STEAM_APP_ID)
		if steam_inst:
			install_paths.append(PathUtils.contract(str(steam_inst / "www" / "save")))
			install_paths.append(PathUtils.contract(str(steam_inst / "save")))

		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "appdata_coffin",
				"label": "AppData Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%APPDATA%/CoffinAndyLeyley",
					"%LOCALAPPDATA%/CoffinAndyLeyley",
					*install_paths,
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/2378900/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
