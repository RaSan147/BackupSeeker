from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "13530"
_GOG_ID = "1207658755"


class PrinceOfPersiaTheTwoThronesPlugin(GamePlugin):
	"""Prince of Persia: The Two Thrones - Windows save locations.

	Supports official Steam, GOG, KaOs, and retail installations.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "prince_of_persia_the_two_thrones"

	@property
	def game_name(self) -> str:
		return "Prince of Persia: The Two Thrones"

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
				"id": "programdata_profiles",
				"label": "ProgramData POP3Profiles",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PROGRAMDATA%/POP3Profiles",
					"%ALLUSERSPROFILE%/POP3Profiles",
					"%USERPROFILE%/Application Data/POP3Profiles",
				],
			},
			{
				"id": "virtual_store_saves",
				"label": "VirtualStore Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/VirtualStore/Program Files (x86)/Ubisoft/Prince of Persia The Two Thrones",
					"%LOCALAPPDATA%/VirtualStore/Program Files/Ubisoft/Prince of Persia The Two Thrones",
				],
			},
		]

		candidates = self.find_smart_install_candidates(
			folder_names=["Prince of Persia The Two Thrones", "Prince of Persia - The Two Thrones", "POP The Two Thrones"],
			exe_names=["PrinceOfPersia.exe"],
			steam_app_id=_STEAM_APP_ID,
			gog_id=_GOG_ID,
		)
		game_paths: list[str] = []
		for cand in candidates:
			p_prof = cand / "POP3Profiles"
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
	def poster(self) -> list[str]:
		base = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}"
		return [
			f"{base}/capsule_616x353.jpg",
			f"{base}/header.jpg",
		]


EXPORT = [PrinceOfPersiaTheTwoThronesPlugin]
