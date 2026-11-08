from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "13600"
_GOG_ID = "1207658753"


class PrinceOfPersiaSandsOfTimePlugin(GamePlugin):
	"""Prince of Persia: The Sands of Time - Windows save locations.

	Supports official Steam, GOG, and retail installations.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "prince_of_persia_sands_of_time"

	@property
	def game_name(self) -> str:
		return "Prince of Persia: The Sands of Time"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\GOG.com\Games\{_GOG_ID}",
				"value_name": "PATH",
			},
			{
				"id": "virtual_store_saves",
				"label": "VirtualStore Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/VirtualStore/Program Files (x86)/Ubisoft/Prince of Persia The Sands of Time/Profiles",
					"%LOCALAPPDATA%/VirtualStore/Program Files/Ubisoft/Prince of Persia The Sands of Time/Profiles",
					"%LOCALAPPDATA%/VirtualStore/Program Files (x86)/GOG.com/Prince of Persia The Sands of Time/Profiles",
				],
			},
		]

		candidates = self.find_smart_install_candidates(
			folder_names=["Prince of Persia The Sands of Time", "Prince of Persia - The Sands of Time", "POP The Sands of Time"],
			exe_names=["POP.EXE", "PrinceOfPersia.exe"],
			steam_app_id=_STEAM_APP_ID,
			gog_id=_GOG_ID,
		)
		game_paths: list[str] = []
		for cand in candidates:
			p_prof = cand / "Profiles"
			if p_prof.exists() and p_prof.is_dir():
				game_paths.append(str(p_prof))
			p_save = cand / "Save"
			if p_save.exists() and p_save.is_dir():
				game_paths.append(str(p_save))

		if game_paths:
			sources.append({
				"id": "game_folder_saves",
				"label": "Game Folder Profiles/Save",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": game_paths,
			})

		return sources

	@property
	def poster(self) -> str:
		return f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/13600/header.jpg"


def get_plugins():
	return auto_get_plugins()
