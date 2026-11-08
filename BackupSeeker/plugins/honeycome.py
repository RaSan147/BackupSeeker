from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "2543370"


class HoneyComePlugin(GamePlugin):
	"""HoneyCome - Windows save locations.

	Supports ILLGAMES official and FitGirl repack installations.
	Save path references verified on ILLGAMES documentation.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "honeycome"

	@property
	def game_name(self) -> str:
		return "HoneyCome"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "documents_honeycome",
				"label": "Documents HoneyCome Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/ILLGAMES/HoneyCome",
					"%USERPROFILE%/Documents/HoneyCome",
				],
			},
		]

		candidates = self.find_smart_install_candidates(
			folder_names=["HoneyCome", "HoneyCome_FitGirl", "HoneyCome_Trial"],
			exe_names=["HoneyCome.exe"],
			steam_app_id=_STEAM_APP_ID,
		)
		game_paths: list[str] = []
		for cand in candidates:
			p_save = cand / "UserData" / "save"
			if p_save.exists() and p_save.is_dir():
				game_paths.append(str(p_save))

		if game_paths:
			sources.append({
				"id": "game_folder_userdata_save",
				"label": "Game Folder UserData/save",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": game_paths,
			})

		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [HoneyComePlugin]
