from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "1785570"


class TheGenesisOrderPlugin(GamePlugin):
	"""The Genesis Order - Windows save locations.

	Supports official Steam, itch.io, FitGirl repack, and standalone NW.js versions.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "the_genesis_order"

	@property
	def game_name(self) -> str:
		return "The Genesis Order"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "user_data_saves",
				"label": "LocalAppData User Data / NW.js Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/The Genesis Order",
					"%LOCALAPPDATA%/TheGenesisOrder",
					"%LOCALAPPDATA%/User Data",
				],
			},
		]

		candidates = self.find_smart_install_candidates(
			folder_names=["The Genesis Order", "TheGenesisOrder"],
			exe_names=["The Genesis Order.exe", "Game.exe", "nw.exe"],
			steam_app_id=_STEAM_APP_ID,
		)
		game_paths: list[str] = []
		for cand in candidates:
			p_save = cand / "www" / "save"
			if p_save.exists() and p_save.is_dir():
				game_paths.append(str(p_save))

		if game_paths:
			sources.append({
				"id": "game_folder_saves",
				"label": "Game Folder www/save",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": game_paths,
			})

		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [TheGenesisOrderPlugin]
