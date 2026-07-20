import unittest
from pathlib import Path

from BackupSeeker.plugin_manager import PluginManager
from BackupSeeker.plugins.base import GamePlugin

# Direct imports for all 20 new plugins
from BackupSeeker.plugins.the_witcher_3_wild_hunt import TheWitcher3WildHuntPlugin
from BackupSeeker.plugins.cyberpunk_2077 import Cyberpunk2077Plugin
from BackupSeeker.plugins.elden_ring import EldenRingPlugin
from BackupSeeker.plugins.grand_theft_auto_v import GrandTheftAutoVPlugin
from BackupSeeker.plugins.red_dead_redemption_2 import RedDeadRedemption2Plugin
from BackupSeeker.plugins.hades import HadesPlugin
from BackupSeeker.plugins.skyrim import SkyrimPlugin
from BackupSeeker.plugins.fallout_4 import Fallout4Plugin
from BackupSeeker.plugins.minecraft import MinecraftPlugin
from BackupSeeker.plugins.stardew_valley import StardewValleyPlugin

from BackupSeeker.plugins.baldurs_gate_3 import BaldursGate3Plugin
from BackupSeeker.plugins.monster_hunter_world import MonsterHunterWorldPlugin
from BackupSeeker.plugins.terraria import TerrariaPlugin
from BackupSeeker.plugins.slay_the_spire import SlayTheSpirePlugin
from BackupSeeker.plugins.euro_truck_simulator_2 import EuroTruckSimulator2Plugin
from BackupSeeker.plugins.cities_skylines import CitiesSkylinesPlugin
from BackupSeeker.plugins.sekiro import SekiroPlugin
from BackupSeeker.plugins.dark_souls_3 import DarkSouls3Plugin
from BackupSeeker.plugins.hollow_knight import HollowKnightPlugin
from BackupSeeker.plugins.subnautica import SubnauticaPlugin
from BackupSeeker.plugins.sword_art_online_echoes_of_aincrad import (
	SwordArtOnlineEchoesOfAincradPlugin,
)


class TestNewPlugins(unittest.TestCase):
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
		}

		for game_id, plugin in new_plugins.items():
			with self.subTest(game_id=game_id):
				# Verify they are correctly registered or not registered in the active plugin registry depending on is_disabled
				if plugin.is_disabled:
					self.assertNotIn(game_id, pm.available_plugins)
				else:
					self.assertIn(game_id, pm.available_plugins)
				
				# Verify properties are correct
				self.assertIsInstance(plugin, GamePlugin)
				self.assertEqual(plugin.game_id, game_id)
				self.assertTrue(len(plugin.game_name) > 0)
				self.assertTrue(len(plugin.icon) > 0)
				self.assertTrue(plugin.poster.startswith("http"))
				self.assertTrue(len(plugin.save_sources) > 0)


if __name__ == "__main__":
	unittest.main()
