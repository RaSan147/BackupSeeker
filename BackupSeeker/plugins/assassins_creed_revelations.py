from __future__ import annotations

from typing import Any

from ..core import PathUtils
from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "201870"
_UBISOFT_ID = "40"


class AssassinsCreedRevelationsPlugin(GamePlugin):
	r"""Assassin's Creed Revelations - Windows save locations.

	Supports official Steam, Ubisoft Connect, and Theta / Orbit / SKIDROW repacks.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "assassins_creed_revelations"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed Revelations"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		skidrow_paths: list[str] = []
		steam_inst = self.get_steam_app_install_path(_STEAM_APP_ID)
		if steam_inst:
			skidrow_paths.append(PathUtils.contract(str(steam_inst / "storage" / "SKIDROW" / "40")))
		ubi_inst = self.get_ubisoft_install_path(_UBISOFT_ID)
		if ubi_inst:
			skidrow_paths.append(PathUtils.contract(str(ubi_inst / "storage" / "SKIDROW" / "40")))
		skidrow_paths.extend([
			"%PROGRAMFILES(X86)%/Steam/steamapps/common/Assassin's Creed Revelations/storage/SKIDROW/40",
			"%PROGRAMFILES%/Steam/steamapps/common/Assassin's Creed Revelations/storage/SKIDROW/40",
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
				"id": "orbit_theta",
				"label": "Orbit / Theta Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": ["%APPDATA%/Theta/Orbit/40"],
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
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/201870/capsule_616x353.jpg"

	def extra_readme_lines(self) -> list[str]:
		return [
			r"Revelations Orbit saves: %APPDATA%\Theta\Orbit\40 (*.save).",
			r"Ubisoft Connect saves: %LOCALAPPDATA%\Ubisoft Game Launcher\savegames\<AccountID>\40",
		]


def get_plugins():
	return auto_get_plugins()
