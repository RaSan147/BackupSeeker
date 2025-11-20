"""BackupSeeker Game Save Manager package.

Provides a modular core API plus Qt UI, and a lightweight
plugin system for automatic game detection.
"""

from .core import ConfigManager, GameProfile, PathUtils, run_backup, run_restore

__all__ = [
	"ConfigManager",
	"GameProfile",
	"PathUtils",
	"run_backup",
	"run_restore",
]

