from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "368500"
_UBISOFT_ID = "1875"


class AssassinsCreedSyndicatePlugin(GamePlugin):
	"""Assassin's Creed Syndicate - Windows save locations.

	Supports official Steam, Ubisoft Connect, DODI, CODEX, Orbit, and Goldberg emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "assassins_creed_syndicate"

	@property
	def game_name(self) -> str:
		return "Assassin's Creed Syndicate"

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
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Ubisoft\Launcher\Installs\{_UBISOFT_ID}",
				"value_name": "InstallDir",
			},
			{
				"id": "codex_dodi_saves",
				"label": "CODEX / DODI Repack Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%PUBLIC%/Documents/uPlay/CODEX/Saves/AssassinsCreedSyndicate",
				],
			},
			{
				"id": "orbit_saves",
				"label": "Orbit Crack Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					rf"%PROGRAMDATA%/Orbit/{_UBISOFT_ID}",
				],
			},
			{
				"id": "goldberg_uplay",
				"label": "Goldberg UplayEmu Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					self.get_goldberg_uplay_path(_UBISOFT_ID),
				],
			},
			{
				"id": "ubisoft_connect",
				"label": "Ubisoft Connect Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": self.get_ubisoft_save_paths(_UBISOFT_ID),
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [AssassinsCreedSyndicatePlugin]
