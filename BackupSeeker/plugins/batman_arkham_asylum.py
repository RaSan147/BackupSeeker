from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "35140"


class BatmanArkhamAsylumPlugin(GamePlugin):
	"""Batman: Arkham Asylum (GOTY Edition) - Windows save locations.

	Supports official Steam, GOG, KaOs, PROPHET, and other emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "batman_arkham_asylum"

	@property
	def game_name(self) -> str:
		return "Batman: Arkham Asylum"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "documents_square_enix",
				"label": "Documents Square Enix Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Square Enix/Batman Arkham Asylum GOTY/SaveData",
					"%USERPROFILE%/Documents/Square Enix/Batman Arkham Asylum GOTY",
					"%USERPROFILE%/Documents/Square Enix/Batman Arkham Asylum/SaveData",
				],
			},
			{
				"id": "documents_wb_games",
				"label": "Documents WB Games Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/WB Games/Batman Arkham Asylum GOTY/SaveData",
					"%USERPROFILE%/Documents/WB Games/Batman Arkham Asylum GOTY",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [BatmanArkhamAsylumPlugin]
