from __future__ import annotations

from typing import Any

from .base import GamePlugin
from .save_sources import SAVE_KIND_DIRECTORY

_STEAM_APP_ID = "1985820"

class CallOfDutyVanguardPlugin(GamePlugin):
	"""Call of Duty: Vanguard - Windows save locations.

	Supports official Battle.net and DODI repack campaign saves.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "1.0.0"

	@property
	def game_id(self) -> str:
		return "call_of_duty_vanguard"

	@property
	def game_name(self) -> str:
		return "Call of Duty: Vanguard"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		return [
			{
				"id": "documents_vanguard",
				"label": "Documents COD Vanguard Players",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": [
					"%USERPROFILE%/Documents/Call of Duty Vanguard/players",
					"%USERPROFILE%/Documents/Call of Duty Vanguard",
					"%ONEDRIVE%/Documents/Call of Duty Vanguard/players",
				],
			},
		]

	@property
	def poster(self) -> str:
		return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{_STEAM_APP_ID}/capsule_616x353.jpg"


EXPORT = [CallOfDutyVanguardPlugin]
