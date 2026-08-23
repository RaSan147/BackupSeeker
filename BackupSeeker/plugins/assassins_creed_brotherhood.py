from __future__ import annotations

from typing import Any

from ..core import PathUtils
from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "48190"
_UBISOFT_ID = "9"


class AssassinsCreedBrotherhoodPlugin(GamePlugin):
	"""Assassin's Creed Brotherhood - Windows save locations.

	Supports official Steam, Ubisoft Connect, and SKIDROW/repack layouts.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "assassins_creed_brotherhood"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed Brotherhood"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		skidrow_paths: list[str] = []
		steam_inst = self.get_steam_app_install_path(_STEAM_APP_ID)
		if steam_inst:
			skidrow_paths.append(PathUtils.contract(str(steam_inst / "storage" / "SKIDROW" / "9")))
		ubi_inst = self.get_ubisoft_install_path(_UBISOFT_ID)
		if ubi_inst:
			skidrow_paths.append(PathUtils.contract(str(ubi_inst / "storage" / "SKIDROW" / "9")))
		skidrow_paths.extend([
			"%PROGRAMFILES(X86)%/Steam/steamapps/common/Assassin's Creed Brotherhood/storage/SKIDROW/9",
			"%PROGRAMFILES%/Steam/steamapps/common/Assassin's Creed Brotherhood/storage/SKIDROW/9",
		])

		return [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Ubisoft\Launcher\Installs\{_UBISOFT_ID}",
				"value_name": "InstallDir",
			},
			{
				"id": "saved_games",
				"label": "Windows Saved Games",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": ["%USERPROFILE%/Saved Games/Assassin's Creed Brotherhood"],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Connect Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": self.get_ubisoft_save_paths(_UBISOFT_ID),
			},
			{
				"id": "skidrow_storage",
				"label": "SKIDROW / Repack Storage Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": skidrow_paths,
			},
		]

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/48190/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
