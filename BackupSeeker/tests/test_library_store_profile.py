import unittest

from BackupSeeker.core import GameProfile


class TestGameProfileExecutables(unittest.TestCase):
	def test_profile_executable_serialization(self):
		prof = GameProfile(
			id="custom_game_1",
			name="Custom Game",
			save_path="%USERPROFILE%/Documents/MyGame",
			executable_path="C:/Games/MyGame/Game.exe",
		)
		d = prof.to_dict()
		self.assertEqual(d.get("executable_path"), "C:/Games/MyGame/Game.exe")

		loaded = GameProfile.from_dict(d)
		self.assertEqual(loaded.executable_path, "C:/Games/MyGame/Game.exe")
		self.assertEqual(loaded.name, "Custom Game")

	def test_plugin_profile_executable_serialization(self):
		prof = GameProfile(
			id="detroit_become_human",
			plugin_id="detroit_become_human",
			executable_path="D:/Detroit/DetroitBecomeHuman.exe",
		)
		d = prof.to_dict()
		self.assertEqual(d.get("executable_path"), "D:/Detroit/DetroitBecomeHuman.exe")
		loaded = GameProfile.from_dict(d)
		self.assertEqual(loaded.executable_path, "D:/Detroit/DetroitBecomeHuman.exe")
		self.assertEqual(loaded.plugin_id, "detroit_become_human")


if __name__ == "__main__":
	unittest.main()
