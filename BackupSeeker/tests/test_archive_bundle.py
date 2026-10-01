"""Tests for archive format 1 bundle read/write helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from BackupSeeker.archive.bundle import build_bundle, read_bundle_from_zip
from BackupSeeker.archive.constants import BACKUP_BUNDLE_PATH
from BackupSeeker.archive.format_registry import CURRENT_ARCHIVE_FORMAT


class TestBundleFormat1(unittest.TestCase):
	def test_build_and_read_roundtrip(self) -> None:
		body = build_bundle(
			created_at="2026-01-01T00:00:00",
			profile_id="p1",
			display_name="Test Game",
			plugin_id="test_game",
			plugin_version="1.0",
			file_patterns=["*"],
			manifest_keys=["save"],
			logical_keys_map={"save": "save"},
			roots=[
				{
					"logical_key": "save",
					"sanitized_key": "save",
					"contracted_save_path": "%USERPROFILE%/Saves",
					"included_in_archive": True,
					"files_in_backup": 1,
				}
			],
			plugin_snapshot={
				"game_id": "test_game",
				"save_sources": [
					{
						"id": "path_0",
						"kind": "directory",
						"paths": ["%USERPROFILE%/Saves"],
					}
				],
			},
			registry_export=None,
		)
		raw = json.dumps(body).encode("utf-8")
		with tempfile.TemporaryDirectory() as td:
			zp = Path(td) / "t.zip"
			with zipfile.ZipFile(zp, "w") as zf:
				zf.writestr(BACKUP_BUNDLE_PATH, raw)
			out = read_bundle_from_zip(zp)
			self.assertIsNotNone(out)
			assert out is not None
			self.assertEqual(out.get("format"), CURRENT_ARCHIVE_FORMAT)
			self.assertEqual(out["game"]["plugin_id"], "test_game")

	def test_gather_archive_rows_deduplication(self) -> None:
		import os
		import time

		from BackupSeeker.core import GameProfile, _gather_archive_rows
		from BackupSeeker.plugins.base import GamePlugin

		with tempfile.TemporaryDirectory() as td:
			td_path = Path(td)
			dir1 = td_path / "dir1"
			dir2 = td_path / "dir2"
			dir1.mkdir()
			dir2.mkdir()

			# Create files in both directories.
			# file1.txt will be duplicate, but we'll make dir2/file1.txt newer.
			f1_d1 = dir1 / "file1.txt"
			f1_d2 = dir2 / "file1.txt"
			f1_d1.write_text("old content")
			f1_d2.write_text("new content")

			# Set mtimes explicitly
			os.utime(f1_d1, (time.time() - 100, time.time() - 100))
			os.utime(f1_d2, (time.time(), time.time()))

			# Create another file only in dir1
			f2_d1 = dir1 / "file2.txt"
			f2_d1.write_text("only in dir1")

			# Let's create a custom plugin that defines two separate save_sources that alias to the same ZIP key
			class MockPlugin(GamePlugin):
				game_id = "mock_game"
				game_name = "Mock Game"
				save_sources = [
					{
						"id": "save_folder_1",
						"kind": "directory",
						"paths": [str(dir1)],
					},
					{
						"id": "save_folder_2",
						"kind": "directory",
						"paths": [str(dir2)],
					}
				]
				zip_key_aliases = {
					"save_folder_1": "save_folder",
					"save_folder_2": "save_folder",
				}
				icon = "🎮"
				poster = "http://example.com/poster.jpg"

			plugin = MockPlugin()
			profile = GameProfile(
				id="mock_profile",
				plugin_id="mock_game",
			)

			# Run _gather_archive_rows
			rows, hints, root_diags = _gather_archive_rows(profile, plugin, allow_empty_mechanical_fallback=True)

			# Let's check rows. It should only have 2 unique arcnames:
			# 'save_folder/file1.txt' and 'save_folder/file2.txt'.
			# And for 'save_folder/file1.txt', it should point to dir2/file1.txt (newer)
			arcnames = {f"{key}/{rel.as_posix()}": fpath for key, fpath, rel in rows}
			self.assertEqual(len(rows), 2)
			self.assertIn("save_folder/file1.txt", arcnames)
			self.assertIn("save_folder/file2.txt", arcnames)

			# Verify that the file from dir2 (newer) was kept
			self.assertEqual(arcnames["save_folder/file1.txt"], f1_d2)
			self.assertEqual(arcnames["save_folder/file2.txt"], f2_d1)

	def test_gather_archive_rows_same_directory(self) -> None:
		from BackupSeeker.core import GameProfile, _gather_archive_rows
		from BackupSeeker.plugins.base import GamePlugin

		with tempfile.TemporaryDirectory() as td:
			td_path = Path(td)
			dir1 = td_path / "dir1"
			dir1.mkdir()

			f1 = dir1 / "file1.txt"
			f1.write_text("hello")

			# Same directory listed twice
			class MockPluginSame(GamePlugin):
				game_id = "mock_game_same"
				game_name = "Mock Game Same"
				save_sources = [
					{
						"id": "save_folder",
						"kind": "directory",
						"paths": [str(dir1), str(dir1)], # Same directory twice
					}
				]
				icon = "🎮"
				poster = "http://example.com/poster.jpg"

			plugin = MockPluginSame()
			profile = GameProfile(
				id="mock_profile_same",
				plugin_id="mock_game_same",
			)

			rows, hints, root_diags = _gather_archive_rows(profile, plugin, allow_empty_mechanical_fallback=True)

			# It should only contain 1 row, and walked only once (verified by only 1 file in rows)
			self.assertEqual(len(rows), 1)
			self.assertEqual(rows[0][1], f1)

	def test_wildcard_path_backup_and_restore(self) -> None:
		from BackupSeeker.core import ConfigManager, GameProfile, PathUtils, run_backup, run_restore, verify_save_locations_report
		from BackupSeeker.plugins.base import GamePlugin

		self.assertTrue(PathUtils.has_wildcard("C:/Users/*/AppData"))
		self.assertTrue(PathUtils.has_wildcard("C:/Users/?/AppData"))
		self.assertFalse(PathUtils.has_wildcard("C:/Users/test/AppData"))

		with tempfile.TemporaryDirectory() as td:
			base = Path(td)
			acc1_saves = base / "savegames" / "user_alpha" / "12345"
			acc2_saves = base / "savegames" / "user_beta" / "12345"
			acc1_saves.mkdir(parents=True)
			acc2_saves.mkdir(parents=True)

			(acc1_saves / "slot1.sav").write_text("save_data_1")
			(acc2_saves / "slot2.sav").write_text("save_data_2")

			wildcard_pattern = f"{base.as_posix()}/savegames/*/12345"

			class WildcardPlugin(GamePlugin):
				game_id = "wildcard_game"
				game_name = "Wildcard Game"
				save_sources = [
					{
						"id": "ubi_saves",
						"kind": "directory",
						"paths": [wildcard_pattern],
					}
				]

			plug = WildcardPlugin()
			prof = GameProfile(id="wildcard_prof", plugin_id="wildcard_game")
			cfg = ConfigManager()
			cfg.config_dir = base / "config"
			cfg.backups_dir = base / "backups"

			rep = verify_save_locations_report(prof, plug)
			self.assertGreaterEqual(len(rep["locations"]), 2)

			dest_zip = base / "backup.zip"
			run_backup(prof, cfg, plug, dest_zip=dest_zip)
			self.assertTrue(dest_zip.exists())

			# Test restore into cleared directories
			run_restore(prof, cfg, dest_zip, plug, clear_first=True)
			self.assertTrue((acc1_saves / "slot1.sav").exists())


if __name__ == "__main__":
	unittest.main()
