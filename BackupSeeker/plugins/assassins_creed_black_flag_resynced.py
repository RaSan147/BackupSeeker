from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "3751950"
_UBISOFT_RESYNCED_STEAM_ID = "66088"
_UBISOFT_RESYNCED_UBI_ID = "65043"


class AssassinsCreedBlackFlagResyncedPlugin(GamePlugin):
	r"""Assassin's Creed: Black Flag Resynced - Windows save locations.

	Supports Ubisoft Connect, Steam releases, voices38 crack, and Goldberg UplayEmu.
	Save path references verified for official and Resynced builds.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "assassins_creed_black_flag_resynced"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed: Black Flag Resynced"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		return [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Ubisoft\Launcher\Installs\{_UBISOFT_RESYNCED_STEAM_ID}",
				"value_name": "InstallDir",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Ubisoft\Launcher\Installs\{_UBISOFT_RESYNCED_UBI_ID}",
				"value_name": "InstallDir",
			},
			{
				"id": "goldberg_uplay_voices38",
				"label": "voices38 Crack / Goldberg UplayEmu Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					self.get_goldberg_uplay_path(_UBISOFT_RESYNCED_STEAM_ID),
					self.get_goldberg_uplay_path(_UBISOFT_RESYNCED_UBI_ID),
				],
			},
			{
				"id": "steam_emulators",
				"label": "Steam Emulator Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": self.get_all_steam_save_paths(_STEAM_APP_ID),
			},
			{
				"id": "resynced_uplay_appdata",
				"label": "Resynced Local Storage & Manifests",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/Ubisoft/Assassin's Creed Black Flag Resynced",
				],
			},
			{
				"id": "documents_config",
				"label": "Documents / My Games Settings & Data",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/My Games/Assassin's Creed Black Flag Resynced",
				],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Game Launcher / Connect Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": (
					self.get_ubisoft_save_paths(_UBISOFT_RESYNCED_STEAM_ID)
					+ self.get_ubisoft_save_paths(_UBISOFT_RESYNCED_UBI_ID)
				),
			},
		]

	@property
	def poster(self) -> str:
		return "https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/3751950/9b046115b1663a4be2b252712328e4f6c162da68/header.jpg"

	def extra_readme_lines(self) -> list[str]:
		return [
			r"voices38 / Goldberg UplayEmu saves: %APPDATA%\Goldberg UplayEmu Saves\66088 (or 65043)",
			r"Resynced local storage & manifests: %LOCALAPPDATA%\Ubisoft\Assassin's Creed Black Flag Resynced",
			r"Ubisoft Connect saves: %LOCALAPPDATA%\Ubisoft Game Launcher\savegames\<AccountID>\66088 (or 65043)",
			r"Settings & config: %USERPROFILE%\Documents\My Games\Assassin's Creed Black Flag Resynced",
		]


def get_plugins():
	return auto_get_plugins()
