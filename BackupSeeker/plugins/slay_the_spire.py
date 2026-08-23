from __future__ import annotations

from typing import Any

from ..core import PathUtils
from .base import GamePlugin, auto_get_plugins
from .save_sources import SAVE_KIND_DIRECTORY, SAVE_KIND_REGISTRY_WINDOWS

_STEAM_APP_ID = "646570"
_GOG_ID = "2092305886"


class SlayTheSpirePlugin(GamePlugin):
	"""Slay the Spire - save game locations.

	Saves are stored in the ``preferences`` and ``runs`` folders within the game installation
	directory, as well as Steam userdata.
	Save path references verified on PCGamingWiki.
	"""

	version: str = "2.0.0"

	@property
	def game_id(self) -> str:
		return "slay_the_spire"

	@property
	def game_name(self) -> str:
		return "Slay the Spire"

	@property
	def save_sources(self) -> list[dict[str, Any]]:
		pref_paths: list[str] = []
		steam_inst = self.get_steam_app_install_path(_STEAM_APP_ID)
		if steam_inst:
			pref_paths.append(PathUtils.contract(str(steam_inst / "preferences")))
			pref_paths.append(PathUtils.contract(str(steam_inst / "runs")))
		gog_inst = self.get_gog_install_path(_GOG_ID)
		if gog_inst:
			pref_paths.append(PathUtils.contract(str(gog_inst / "preferences")))
			pref_paths.append(PathUtils.contract(str(gog_inst / "runs")))
		pref_paths.extend([
			"%PROGRAMFILES(X86)%/Steam/steamapps/common/SlayTheSpire/preferences",
			"%PROGRAMFILES%/Steam/steamapps/common/SlayTheSpire/preferences",
		])

		sources: list[dict[str, Any]] = [
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {_STEAM_APP_ID}",
				"value_name": "InstallLocation",
			},
			{
				"kind": SAVE_KIND_REGISTRY_WINDOWS,
				"key_path": rf"HKEY_LOCAL_MACHINE\SOFTWARE\GOG.com\Games\{_GOG_ID}",
				"value_name": "path",
			},
			{
				"id": "preferences_folder",
				"label": "Game Preferences & Runs",
				"kind": SAVE_KIND_DIRECTORY,
				"paths": pref_paths,
			},
		]
		sources.extend(self.get_named_steam_emulator_sources(_STEAM_APP_ID))
		return sources

	@property
	def poster(self) -> str:
		return "https://cdn.cloudflare.steamstatic.com/steam/apps/646570/capsule_616x353.jpg"


def get_plugins():
	return auto_get_plugins()
