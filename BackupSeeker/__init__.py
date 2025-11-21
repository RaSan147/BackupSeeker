"""BackupSeeker package with proper imports."""

import os
import sys

# Add the current directory to Python path so imports work
# sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .core import ConfigManager, GameProfile, PathUtils, run_backup, run_restore
from .plugin_manager import PluginManager

__all__ = [
    "ConfigManager", 
    "GameProfile", 
    "PathUtils", 
    "run_backup", 
    "run_restore",
    "PluginManager"
]