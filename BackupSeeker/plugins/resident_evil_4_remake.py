from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "2050650"


class ResidentEvil4RemakePlugin(GamePlugin):
	"""Resident Evil 4 (Remake, 2023) - Windows save locations.

	Supports official Steam, EMPRESS, DODI, RUNE, GSE/Hydra, and Goldberg emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "resident_evil_4_remake"

	@property
	def game_name(self) -> str:
		return "Resident Evil 4 (Remake)"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID, "remote/win64_save"))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
