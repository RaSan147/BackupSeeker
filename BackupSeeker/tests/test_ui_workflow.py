import os
import unittest

from PyQt6.QtWidgets import QApplication

from BackupSeeker.core import GameProfile
from BackupSeeker.ui_fluent import ModernBackupSeekerWindow

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestUIWorkflow(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.app = QApplication.instance() or QApplication([])

	def setUp(self):
		self.win = ModernBackupSeekerWindow()
		self.win.show()

	def test_library_and_store_navigation(self):
		# Initial state is Library
		self.assertTrue(self.win.library_interface.isVisible())
		self.assertFalse(self.win.store_interface.isVisible())

		# Switch to Store
		self.win._show_interface("store")
		self.assertFalse(self.win.library_interface.isVisible())
		self.assertTrue(self.win.store_interface.isVisible())

		# Switch to Settings
		self.win._show_interface("settings")
		self.assertFalse(self.win.store_interface.isVisible())
		self.assertTrue(self.win.settings_interface.isVisible())

		# Switch back to Library
		self.win._show_interface("library")
		self.assertTrue(self.win.library_interface.isVisible())

	def test_game_profile_flow(self):
		# Pick first available game plugin or profile
		plugins = list(self.win.plugin_manager.plugins.values())
		self.assertTrue(len(plugins) > 0, "Expected at least 1 supported game plugin")

		plug = plugins[0]
		prof = GameProfile(
			id=plug.game_id,
			name=plug.game_name,
			plugin_id=plug.game_id,
		)

		# Open game profile from store
		self.win.open_game_profile(prof, source="store")
		self.assertTrue(self.win.profile_interface.isVisible())
		self.assertEqual(self.win.profile_interface.source_view, "store")

		# Navigate back
		self.win.back_from_game_profile()
		self.assertTrue(self.win.store_interface.isVisible())

		# Open game profile from library
		self.win.open_game_profile(prof, source="library")
		self.assertTrue(self.win.profile_interface.isVisible())
		self.assertEqual(self.win.profile_interface.source_view, "library")

		# Navigate back
		self.win.back_from_game_profile()
		self.assertTrue(self.win.library_interface.isVisible())

	def test_profile_detail_scan_executables_and_layout(self):
		plugins = list(self.win.plugin_manager.plugins.values())
		plug = plugins[0]
		prof = GameProfile(
			id=plug.game_id,
			name=plug.game_name,
			plugin_id=plug.game_id,
			executable_path="C:\\Windows\\System32\\cmd.exe",
		)
		self.win.open_game_profile(prof, source="library")
		pi = self.win.profile_interface

		# Switch to Game Settings and Executable tab
		pi._switch_tab("game_info")
		self.assertTrue(pi.info_tab_widget.isVisible())
		self.assertFalse(pi.backups_tab_widget.isVisible())

		# Trigger auto-detect
		pi._on_scan_executables()
		# Executable list should be visible and properly sized
		self.assertTrue(pi.discovered_exe_label.isVisible())
		self.assertTrue(pi.discovered_exe_list.isVisible())
		self.assertGreater(pi.discovered_exe_list.height(), 30)

	def test_verify_save_dialog(self):
		from BackupSeeker.ui_fluent.verify_dialog import VerifySaveDialog
		plugins = list(self.win.plugin_manager.plugins.values())
		plug = plugins[0]
		prof = GameProfile(
			id=plug.game_id,
			name=plug.game_name,
			plugin_id=plug.game_id,
		)
		dlg = VerifySaveDialog(prof, plug, self.win.config, self.win)
		self.assertIsNotNone(dlg.scroll_area)
		self.assertIsNotNone(dlg.overall_badge)
		self.assertIsNotNone(dlg.card_paths)
		self.assertIsNotNone(dlg.card_files)
		self.assertIsNotNone(dlg.card_detect)
		# Test refresh
		dlg._load_report()
		self.assertTrue(dlg.title_label.text().startswith("Save Verification:"))


if __name__ == "__main__":
	unittest.main()


