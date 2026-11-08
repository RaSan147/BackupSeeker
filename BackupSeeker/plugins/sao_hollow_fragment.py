from __future__ import annotations

from typing import Any

from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "638650"


class SAOHollowFragmentPlugin(GamePlugin):
	"""Sword Art Online: Hollow Fragment - Windows save locations.

	Supports official Steam, FitGirl, CODEX, Goldberg, and GSE emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "sao_hollow_fragment"

	@property
	def game_name(self) -> str:
		return "Sword Art Online: Hollow Fragment"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "localappdata_sao_hf",
				"label": "LocalAppData SAO HF Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%LOCALAPPDATA%/BANDAI NAMCO Entertainment/SAO HF",
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
