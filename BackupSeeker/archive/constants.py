"""Paths and version constants for BackupSeeker archives."""

from __future__ import annotations

from .format_registry import CURRENT_ARCHIVE_FORMAT as BUNDLE_FORMAT_VERSION

BACKUP_DIR_PREFIX = "_backupseeker/"
BACKUP_BUNDLE_PATH = "_backupseeker/bundle.json"
ZIP_README_PATH = "_backupseeker/README.txt"
RESTORE_CLI_PATH = "_backupseeker/restore_cli.py"
EMBEDDED_PLUGIN_PREFIX = "_backupseeker/embed/"
PORTABLE_CONTRACT_EMBED_PATH = "_backupseeker/embed/portable_contract.py"
PORTABLE_LOADER_EMBED_PATH = "_backupseeker/embed/portable_loader.py"

MAX_BUNDLE_JSON_BYTES = 512 * 1024
