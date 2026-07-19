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


if __name__ == "__main__":
	unittest.main()
