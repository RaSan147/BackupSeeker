from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID_SE = "489830"
_STEAM_APP_ID_LE = "72850"
_GOG_ID = "1711230643"


class SkyrimPlugin(GamePlugin):
	"""The Elder Scrolls V: Skyrim - save game locations.

	Supports Legendary Edition, Special Edition (SE), Anniversary Edition (AE), GOG, and Microsoft Store.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "skyrim"

	@property
	def game_name(self) -> str:
		return "The Elder Scrolls V: Skyrim"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID_SE}",
				"value_name": "InstallLocation",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID_LE}",
				"value_name": "InstallLocation",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\GOG.com\Games\{_GOG_ID}",
				"value_name": "path",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": r"HKEY_LOCAL_MACHINE\SOFTWARE\Bethesda Softworks\Skyrim Special Edition",
				"value_name": "Installed Path",
			},
			{
				"id": "skyrim_se_ae",
				"label": "Skyrim Special / Anniversary Edition",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/My Games/Skyrim Special Edition/Saves",
					"%USERPROFILE%/Documents/My Games/Skyrim Special Edition GOG/Saves",
					"%USERPROFILE%/Documents/My Games/Skyrim Special Edition MS/Saves",
				],
			},
			{
				"id": "skyrim_legendary",
				"label": "Skyrim Legendary / Original Edition",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/My Games/Skyrim/Saves",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID_SE))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/489830/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
