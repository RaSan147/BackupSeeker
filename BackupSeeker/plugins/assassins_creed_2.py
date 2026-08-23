from __future__ import annotations

from typing import Any

from ..core import PathUtils
from .base import GamePlugin, auto_get_plugins
from .save_sources import (
	PROMPT_WHEN_NO_CANDIDATE,
	SAVE_KIND_DIRECTORY,
	SAVE_KIND_REGISTRY_WINDOWS,
)

_STEAM_APP_ID = "33230"
_UBISOFT_ID = "4"


class AssassinsCreed2Plugin(GamePlugin):
	r"""Assassin's Creed II - Windows save locations.

	Supports official Steam, Ubisoft Connect, SKIDROW, DODI, and custom installations.
	Save path references verified on PCGamingWiki and scene release NFOs.
	"""

	version: str = "2.1.0"

	_install_prompt = "Install folder (contains storage)."

	@property
	def game_id(self) -> str:
		return "assassins_creed_2"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed II"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		skidrow_paths: list[str] = []
		steam_inst = self.get_steam_app_install_path(_STEAM_APP_ID)
		if steam_inst:
			skidrow_paths.append(PathUtils.contract(str(steam_inst / "storage" / "SKIDROW" / "4")))
		ubi_inst = self.get_ubisoft_install_path(_UBISOFT_ID)
		if ubi_inst:
			skidrow_paths.append(PathUtils.contract(str(ubi_inst / "storage" / "SKIDROW" / "4")))
		skidrow_paths.extend([
			"%PROGRAMFILES(X86)%/Steam/steamapps/common/Assassin's Creed 2/storage/SKIDROW/4",
			"%PROGRAMFILES%/Steam/steamapps/common/Assassin's Creed 2/storage/SKIDROW/4",
			"%PROGRAMFILES(X86)%/Steam/steamapps/common/Assassins Creed II/storage/SKIDROW/4",
			"%PROGRAMFILES%/Steam/steamapps/common/Assassins Creed II/storage/SKIDROW/4",
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
				"id": "steam_skidrow",
				"label": "Steam Common / SKIDROW Repack",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": skidrow_paths,
				"pin_relative_segments": ["storage", "SKIDROW", "4"],
				"prompt": {
					"when": PROMPT_WHEN_NO_CANDIDATE,
					"input_key": "steam_skidrow",
					"message": self._install_prompt,
					"input_kind": "existing_directory",
					"example": r"D:\Games\Assassins Creed II",
					"editor_label": "Install folder",
					"editor_placeholder": "Contains storage (game install folder)",
				},
			},
			{
				"id": "saved_games",
				"label": "Windows Saved Games",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Saved Games/Assassins Creed 2",
					"%USERPROFILE%/Saved Games/Assassin's Creed 2",
				],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Game Launcher Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": self.get_ubisoft_save_paths(_UBISOFT_ID),
			},
		]

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/33230/capsule_616x353.jpg"

	def extra_readme_lines(self) -> list[str]:
		return [
			r"Saves live at <install>\storage\SKIDROW\4 - pin install folder at steam_skidrow when prompted.",
			r"Ubisoft Connect saves: %LOCALAPPDATA%\Ubisoft Game Launcher\savegames\<AccountID>\4",
		]


def get_plugins():
	return auto_get_plugins()
