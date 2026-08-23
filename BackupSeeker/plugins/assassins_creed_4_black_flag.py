from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "242050"
_UBISOFT_STEAM_ID = "437"
_UBISOFT_ORIGINAL_ID = "273"


class AssassinsCreed4BlackFlagPlugin(GamePlugin):
	r"""Assassin's Creed IV: Black Flag - Windows save locations.

	Supports official Steam, Ubisoft Connect, Orbit, Reloaded, 3DM, and Goldberg emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "assassins_creed_4_black_flag"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed IV: Black Flag"

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
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Ubisoft\Launcher\Installs\{_UBISOFT_STEAM_ID}",
				"value_name": "InstallDir",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Ubisoft\Launcher\Installs\{_UBISOFT_ORIGINAL_ID}",
				"value_name": "InstallDir",
			},
			{
				"id": "orbit_reloaded",
				"label": "Orbit / Reloaded Crack Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PROGRAMDATA%/Orbit/437",
					"%PROGRAMDATA%/Orbit/273",
					"%PROGRAMDATA%/Orbit/442",
				],
			},
			{
				"id": "goldberg_uplay",
				"label": "Goldberg UplayEmu Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					self.get_goldberg_uplay_path(_UBISOFT_STEAM_ID),
					self.get_goldberg_uplay_path(_UBISOFT_ORIGINAL_ID),
				],
			},
			{
				"id": "steam_emulators",
				"label": "Steam Emulator Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": self.get_all_steam_save_paths(_STEAM_APP_ID),
			},
			{
				"id": "documents_saves",
				"label": "Documents / Settings",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Assassin's Creed IV Black Flag",
				],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Game Launcher / Connect Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": (
					self.get_ubisoft_save_paths(_UBISOFT_STEAM_ID)
					+ self.get_ubisoft_save_paths(_UBISOFT_ORIGINAL_ID)
				),
			},
		]

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/242050/capsule_616x353.jpg"

	def extra_readme_lines(self) -> list[str]:
		return [
			r"Ubisoft Connect saves: %LOCALAPPDATA%\Ubisoft Game Launcher\savegames\<AccountID>\437 (Steam) or 273 (Uplay)",
			r"Orbit / Reloaded saves: %PROGRAMDATA%\Orbit\437 or %PROGRAMDATA%\Orbit\273",
			r"Goldberg UplayEmu saves: %APPDATA%\Goldberg UplayEmu Saves\437 (or 273)",
		]


def get_plugins():
	return auto_get_plugins()
