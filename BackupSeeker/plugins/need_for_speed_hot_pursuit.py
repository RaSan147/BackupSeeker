from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "47870"
_STEAM_REMASTERED_APP_ID = "1328660"


class NeedForSpeedHotPursuitPlugin(GamePlugin):
	"""Need for Speed: Hot Pursuit (2010 / Remastered) - Windows save locations.

	Supports official EA / Steam, ElAmigos, Reloaded, and DODI repacks.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "need_for_speed_hot_pursuit"

	@property
	def game_name(self) -> str:
		return "Need for Speed: Hot Pursuit"

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
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_REMASTERED_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"id": "criterion_saves",
				"label": "Documents Criterion Games Saves",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Criterion Games/Need for Speed(TM) Hot Pursuit",
					"%USERPROFILE%/Documents/Criterion Games/Need for Speed(TM) Hot Pursuit Remastered",
					"%ONEDRIVE%/Documents/Criterion Games/Need for Speed(TM) Hot Pursuit",
					"%ONEDRIVE%/Documents/Criterion Games/Need for Speed(TM) Hot Pursuit Remastered",
				],
			},
		]

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [NeedForSpeedHotPursuitPlugin]
