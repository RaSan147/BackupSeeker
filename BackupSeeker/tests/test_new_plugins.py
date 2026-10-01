import unittest
from pathlib import Path

from BackupSeeker.plugin_manager import PluginManager
from BackupSeeker.plugins.assassins_creed_4_black_flag import (
	AssassinsCreed4BlackFlagPlugin,
)
from BackupSeeker.plugins.assassins_creed_black_flag_resynced import (
	AssassinsCreedBlackFlagResyncedPlugin,
)
from BackupSeeker.plugins.baldurs_gate_3 import BaldursGate3Plugin
from BackupSeeker.plugins.base import GamePlugin
from BackupSeeker.plugins.cities_skylines import CitiesSkylinesPlugin
from BackupSeeker.plugins.cyberpunk_2077 import Cyberpunk2077Plugin
from BackupSeeker.plugins.dark_souls_3 import DarkSouls3Plugin
from BackupSeeker.plugins.elden_ring import EldenRingPlugin
from BackupSeeker.plugins.euro_truck_simulator_2 import EuroTruckSimulator2Plugin
from BackupSeeker.plugins.fallout_4 import Fallout4Plugin
from BackupSeeker.plugins.five_hearts_under_one_roof import FiveHeartsUnderOneRoofPlugin
from BackupSeeker.plugins.grand_theft_auto_v import GrandTheftAutoVPlugin
from BackupSeeker.plugins.hades import HadesPlugin
from BackupSeeker.plugins.hollow_knight import HollowKnightPlugin
from BackupSeeker.plugins.minecraft import MinecraftPlugin
from BackupSeeker.plugins.monster_hunter_world import MonsterHunterWorldPlugin
from BackupSeeker.plugins.red_dead_redemption_2 import RedDeadRedemption2Plugin
from BackupSeeker.plugins.sekiro import SekiroPlugin
from BackupSeeker.plugins.skyrim import SkyrimPlugin
from BackupSeeker.plugins.slay_the_spire import SlayTheSpirePlugin
from BackupSeeker.plugins.stardew_valley import StardewValleyPlugin
from BackupSeeker.plugins.stray import StrayPlugin
from BackupSeeker.plugins.subnautica import SubnauticaPlugin
from BackupSeeker.plugins.sword_art_online_echoes_of_aincrad import (
	SwordArtOnlineEchoesOfAincradPlugin,
)
from BackupSeeker.plugins.terraria import TerrariaPlugin

# Direct imports for all 20 new plugins
from BackupSeeker.plugins.the_witcher_3_wild_hunt import TheWitcher3WildHuntPlugin


class TestNewPlugins(unittest.TestCase):
	def test_steam_and_emulator_path_helpers(self) -> None:
		stray = StrayPlugin()
		paths = stray.get_all_steam_save_paths("1332010")
		self.assertTrue(any("CODEX" in p for p in paths))
		self.assertTrue(any("TENOKE" in p for p in paths))
		self.assertTrue(any("Goldberg SteamEmu Saves" in p for p in paths))
		self.assertTrue(any("GSE Saves" in p for p in paths))
		self.assertTrue(any("RUNE" in p for p in paths))
		self.assertTrue(any("FLT" in p for p in paths))
		self.assertTrue(any("EMPRESS" in p for p in paths))
		self.assertTrue(any("CPY_SAVES" in p for p in paths))

	def test_steam_library_and_manifest_parser(self) -> None:
		stray = StrayPlugin()
		# get_steam_library_paths should return a list of Paths
		libs = stray.get_steam_library_paths()
		self.assertIsInstance(libs, list)

	def test_unity_player_log_helpers(self) -> None:
		fh = FiveHeartsUnderOneRoofPlugin()
		# Non-existent company/product should safely return None
		self.assertIsNone(fh.get_unity_install_path_from_log("NonExistentCompany", "NonExistentProduct"))
		self.assertIsNone(fh.is_unity_game_installed("NonExistentCompany", "NonExistentProduct"))

	def test_unified_plugins_registered(self) -> None:
		pm = PluginManager(Path("BackupSeeker"))
		self.assertIn("stray", pm.available_plugins)
		self.assertIn("assassins_creed_2", pm.available_plugins)
		self.assertIn("assassins_creed_3_remastered", pm.available_plugins)
		self.assertIn("assassins_creed_4_black_flag", pm.available_plugins)
		self.assertIn("assassins_creed_black_flag_resynced", pm.available_plugins)
		self.assertIn("just_cause_3", pm.available_plugins)
		self.assertIn("five_hearts_under_one_roof", pm.available_plugins)

		ac4_plugin = pm.available_plugins["assassins_creed_4_black_flag"]
		self.assertEqual(ac4_plugin.game_name, "Assassin's Creed IV: Black Flag")
		self.assertEqual(ac4_plugin.game_id, "assassins_creed_4_black_flag")

		resynced_plugin = pm.available_plugins["assassins_creed_black_flag_resynced"]
		self.assertEqual(resynced_plugin.game_name, "Assassin's Creed: Black Flag Resynced")
		self.assertEqual(resynced_plugin.game_id, "assassins_creed_black_flag_resynced")

		stray_plugin = pm.available_plugins["stray"]
		self.assertEqual(stray_plugin.game_name, "Stray")
		self.assertEqual(stray_plugin.game_id, "stray")

		fh_plugin = pm.available_plugins["five_hearts_under_one_roof"]
		self.assertEqual(fh_plugin.game_name, "Five Hearts Under One Roof")
		self.assertEqual(fh_plugin.game_id, "five_hearts_under_one_roof")

	def test_all_new_plugins_disabled_and_valid(self) -> None:
		pm = PluginManager(Path("BackupSeeker"))
		
		# Map of expected ID to plugin class instance
		new_plugins = {
			"the_witcher_3_wild_hunt": TheWitcher3WildHuntPlugin(),
			"cyberpunk_2077": Cyberpunk2077Plugin(),
			"elden_ring": EldenRingPlugin(),
			"grand_theft_auto_5": GrandTheftAutoVPlugin(),
			"red_dead_redemption_2": RedDeadRedemption2Plugin(),
			"hades": HadesPlugin(),
			"skyrim": SkyrimPlugin(),
			"fallout_4": Fallout4Plugin(),
			"minecraft": MinecraftPlugin(),
			"stardew_valley": StardewValleyPlugin(),
			"baldurs_gate_3": BaldursGate3Plugin(),
			"monster_hunter_world": MonsterHunterWorldPlugin(),
			"terraria": TerrariaPlugin(),
			"slay_the_spire": SlayTheSpirePlugin(),
			"euro_truck_simulator_2": EuroTruckSimulator2Plugin(),
			"cities_skylines": CitiesSkylinesPlugin(),
			"sekiro": SekiroPlugin(),
			"dark_souls_3": DarkSouls3Plugin(),
			"hollow_knight": HollowKnightPlugin(),
			"subnautica": SubnauticaPlugin(),
			"sword_art_online_echoes_of_aincrad": SwordArtOnlineEchoesOfAincradPlugin(),
			"five_hearts_under_one_roof": FiveHeartsUnderOneRoofPlugin(),
			"assassins_creed_4_black_flag": AssassinsCreed4BlackFlagPlugin(),
			"assassins_creed_black_flag_resynced": AssassinsCreedBlackFlagResyncedPlugin(),
		}

		for game_id, plugin in new_plugins.items():
			with self.subTest(game_id=game_id):
				if plugin.is_disabled:
					self.assertNotIn(game_id, pm.available_plugins)
				else:
					self.assertIn(game_id, pm.available_plugins)
				
				# Verify properties are correct
				self.assertIsInstance(plugin, GamePlugin)
				self.assertEqual(plugin.game_id, game_id)
				self.assertTrue(len(plugin.game_name) > 0)
				self.assertTrue(plugin.poster.startswith("http"))
				self.assertTrue(len(plugin.save_sources) > 0)

	def test_smart_crack_and_install_detection(self) -> None:
		import tempfile
		from BackupSeeker.plugins.base import GamePlugin

		with tempfile.TemporaryDirectory() as td:
			game_dir = Path(td)
			# Test Goldberg signature
			(game_dir / "steam_settings").mkdir()
			(game_dir / "steam_settings" / "local_save.txt").write_text("1")
			res = GamePlugin.detect_crack_signatures(game_dir)
			self.assertTrue(res["detected"])
			self.assertEqual(res["crack_name"], "Goldberg Steam Emulator")
			self.assertTrue(res["is_portable"])

			# Test CODEX / TENOKE signature
			(game_dir / "steam_settings" / "local_save.txt").unlink()
			(game_dir / "steam_settings").rmdir()
			emu_ini = game_dir / "steam_emu.ini"
			emu_ini.write_text("[Settings]\nUserName=TENOKE\nAppId=1332010\n")
			res_tenoke = GamePlugin.detect_crack_signatures(game_dir)
			self.assertTrue(res_tenoke["detected"])
			self.assertEqual(res_tenoke["crack_name"], "TENOKE Repack")

		# Verify new emulators are included in get_all_steam_save_paths
		stray = StrayPlugin()
		paths = stray.get_all_steam_save_paths("1332010")
		self.assertTrue(any("Nemirtingas" in p for p in paths))
		self.assertTrue(any("SmartSteamEmu" in p for p in paths))
		self.assertTrue(any("OnlineFix" in p for p in paths))


if __name__ == "__main__":
	unittest.main()
