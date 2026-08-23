from __future__ import annotations

from typing import Any

from ..core import PathUtils
from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "1222140"


class DetroitBecomeHumanPlugin(GamePlugin):
	"""Detroit: Become Human - save game locations.

	Supports Steam, Epic Games Store, STOVE Store, and repacks.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "detroit_become_human"

	@property
	def game_name(self) -> str:
		return "Detroit: Become Human"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "saved_games_global",
				"label": "Saved Games (Steam / Epic / Repacks)",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Saved Games/Quantic Dream/Detroit Become Human",
					"%USERPROFILE%/Documents/Quantic Dream/Detroit Become Human",
				],
			},
			{
				"id": "saved_games_stove",
				"label": "STOVE Store Platform Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Saved Games/Quantic Dream/DETROITPC_IND",
					"%USERPROFILE%/Documents/Quantic Dream/DETROITPC_IND",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/945360/capsule_616x353.jpg"

	def is_detected(self) -> bool:
		"""Check standard save paths, Steam/Epic installs, and STOVE Store indicators."""
		if super().is_detected():
			return True

		if self.get_epic_install_path("DetroitBecomeHuman") is not None:
			return True

		for path in [
			"%LOCALAPPDATA%/STOVE/GameManifest/DETROITPC_IND_6.json",
			"%LOCALAPPDATA%/STOVEPCSDK3/logs/DETROITPC_IND",
		]:
			try:
				expanded = PathUtils.expand(path)
				if expanded.exists():
					return True
			except Exception:
				pass
		return False


def get_plugins():
	return auto_get_plugins()
