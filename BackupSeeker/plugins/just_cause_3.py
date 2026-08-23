from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "225540"


class JustCause3Plugin(GamePlugin):
	"""Just Cause 3 - Windows save locations.

	Supports official Steam, Square Enix Documents layout, CPY, CODEX, and other emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.1.0"

	@property
	def game_id(self) -> str:
		return "just_cause_3"

	@property
	def game_name(self) -> str:
		return "Just Cause 3"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "square_enix_docs",
				"label": "Square Enix Documents Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Square Enix/Just Cause 3/Saves",
					"%USERPROFILE%/Documents/My Games/Just Cause 3/Saves",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/225540/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
