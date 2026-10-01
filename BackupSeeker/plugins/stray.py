from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS


class StrayPlugin(GamePlugin):
	"""Stray - Windows save locations.

	Supports official Steam, native Unreal / GOG, CODEX, DODI, Goldberg, GSE, RUNE, and FLT.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.1.0"

	@property
	def game_id(self) -> str:
		return "stray"

	@property
	def game_name(self) -> str:
		return "Stray"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 1332010",
				"value_name": "InstallLocation",
			},
			{
				"id": "unreal_native",
				"label": "Unreal / GOG Native Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/Hk_project/Saved/SaveGames",
				],
			},
		]

		# Smart, non-bruteforce detection for moved SSD / portable installations
		candidates = self.find_smart_install_candidates(
			folder_names=["Stray", "stray", "Hk_project"],
			exe_names=["Stray.exe", "Stray-Win64-Shipping.exe"],
			steam_app_id="1332010",
		)
		portable_paths: list[str] = []
		for cand in candidates:
			p_save = cand / "Hk_project" / "Saved" / "SaveGames"
			if p_save.exists() and p_save.is_dir():
				portable_paths.append(str(p_save))
			p_goldberg = cand / "steam_settings" / "saves"
			if p_goldberg.exists() and p_goldberg.is_dir():
				portable_paths.append(str(p_goldberg))

		if portable_paths:
			sources.append({
				"id": "portable_ssd",
				"label": "Portable SSD / Game Folder Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": portable_paths,
			})

		sources.extend(self.get_named_steam_emulator_sources("1332010"))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/1332010/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
