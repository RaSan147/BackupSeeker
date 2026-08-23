from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "767420"
_UBISOFT_ID = "5183"


class AssassinsCreed3RemasteredPlugin(GamePlugin):
	"""Assassin's Creed III Remastered - Windows save locations.

	Supports official releases, Ubisoft Connect, and CODEX/DODI repacks.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.1.0"

	@property
	def game_id(self) -> str:
		return "assassins_creed_3_remastered"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed III Remastered"

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
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Ubisoft\Launcher\Installs\{_UBISOFT_ID}",
				"value_name": "InstallDir",
			},
			{
				"id": "codex_uplay",
				"label": "CODEX / DODI uPlay Emulated Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": ["%PUBLIC%/Documents/uPlay/CODEX/Saves/AssassinsCreedIIIRemastered"],
			},
			{
				"id": "documents_saves",
				"label": "Documents / Saved Games",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Assassin's Creed III Remastered/Saves",
					"%USERPROFILE%/Saved Games/Assassin's Creed III Remastered",
				],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Connect Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": self.get_ubisoft_save_paths(_UBISOFT_ID),
			},
		]

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/911400/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
