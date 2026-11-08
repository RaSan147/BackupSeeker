from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "2668510"


class RedDeadRedemptionPlugin(GamePlugin):
	"""Red Dead Redemption (PC) - Windows save locations.

	Supports official Steam, Rockstar Games Launcher, RZOR, FLT, and Goldberg Social Club emulators.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "red_dead_redemption"

	@property
	def game_name(self) -> str:
		return "Red Dead Redemption"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "rockstar_documents",
				"label": "Rockstar Games Documents Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Rockstar Games/Red Dead Redemption/Profiles",
					"%USERPROFILE%/Documents/Rockstar Games/Red Dead Redemption",
					"%ONEDRIVE%/Documents/Rockstar Games/Red Dead Redemption/Profiles",
				],
			},
			{
				"id": "goldberg_social_club",
				"label": "Goldberg Social Club Emu Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					self.get_goldberg_social_club_path("Red Dead Redemption"),
				],
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> list[str]:
		base = f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}"
		return [
			f"{base}/capsule_616x353.jpg",
			f"{base}/header.jpg",
			f"{base}/library_hero.jpg",
		]


EXPORT = [RedDeadRedemptionPlugin]
