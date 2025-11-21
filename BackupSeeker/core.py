"""Core logic for BackupSeeker Game Save Manager.

This module is a cleaned-up, importable version of the single-file
implementation in `gemini.py`. It exposes reusable building blocks
without any GUI wiring so other tools can call into it.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List


class PathUtils:
	"""Robust path manipulation and environment variable handling."""

	@staticmethod
	def clean_input_path(raw_path: str) -> str:
		if not raw_path:
			return ""
		clean = raw_path.strip()
		if clean.lower().startswith("file:///"):
			clean = clean[8:]
		elif clean.lower().startswith("file://"):
			clean = clean[7:]
		return os.path.normpath(clean)

	@staticmethod
	def expand(path_str: str) -> Path:
		if not path_str:
			return Path("")
		expanded = os.path.expandvars(path_str)
		expanded = os.path.expanduser(expanded)
		return Path(expanded)

	@staticmethod
	def contract(abs_path: str) -> str:
		if not abs_path:
			return ""

		abs_path = os.path.abspath(abs_path)

		env_vars: Dict[str, str] = {}
		for key, value in os.environ.items():
			if len(value) > 3 and os.path.exists(value):
				env_vars[key] = os.path.abspath(value)

		sorted_vars = sorted(env_vars.items(), key=lambda item: len(item[1]), reverse=True)
		norm_abs_path = os.path.normcase(abs_path)

		for var_name, var_path in sorted_vars:
			norm_var_path = os.path.normcase(var_path)
			if norm_abs_path.startswith(norm_var_path):
				remaining = abs_path[len(var_path) :]
				if not remaining:
					return f"%{var_name}%" if platform.system() == "Windows" else f"${var_name}"
				if remaining.startswith(os.sep):
					clean_remaining = remaining.lstrip(os.sep)
					if platform.system() == "Windows":
						return os.path.join(f"%{var_name}%", clean_remaining)
					return os.path.join(f"${var_name}", clean_remaining)
		return abs_path


@dataclass
class GameProfile:
	id: str = ""
	name: str = ""
	save_path: str = ""
	file_patterns: List[str] = None
	use_compression: bool = True
	clear_folder_on_restore: bool = True
	plugin_id: str = ""
	# Optional icon field for future use
	icon: str = ""  # Can be path to icon file or emoji

	def __post_init__(self) -> None:
		if self.file_patterns is None:
			self.file_patterns = ["*"]
		# Ensure icon is always a string, not None
		if self.icon is None:
			self.icon = ""

	def to_dict(self) -> dict:
		data = asdict(self)
		data.pop("file_patterns", None)
		# Convert icon to empty string if None
		if data.get("icon") is None:
			data["icon"] = ""
		return data

	@classmethod
	def from_dict(cls, data: dict) -> "GameProfile":
		raw_path = data.get("save_path", "")
		# If path still contains an accidental absolute prefix before an
		# env var (e.g. "C:\\...\\%PUBLIC%\\..."), strip that prefix so
		# only the portable contracted form remains.
		if "%" in raw_path or "$" in raw_path:
			idx = min([i for i in [raw_path.find("%"), raw_path.find("$")] if i != -1])
			raw_path = raw_path[idx:]
		if raw_path and not raw_path.startswith(("%", "$")):
			save_path = PathUtils.contract(raw_path)
		else:
			save_path = raw_path

		# Handle icon field safely
		icon = data.get("icon", "")
		if icon is None:
			icon = ""

		return cls(
			id=data.get("id", ""),
			name=data.get("name", ""),
			save_path=save_path,
			use_compression=data.get("use_compression", True),
			clear_folder_on_restore=data.get("clear_folder_on_restore", True),
			plugin_id=data.get("plugin_id", ""),
			icon=icon
		)


class ConfigManager:
	def __init__(self, app_dir: Path | None = None) -> None:
		self.app_dir = app_dir or Path(os.path.dirname(os.path.abspath(__file__)))
		self.config_path = self.app_dir / "gsm_config.json"
		# Backup location settings
		# backup_location_mode: "cwd" | "fixed"
		# backup_fixed_path: user-chosen absolute path when mode == "fixed"
		self.backup_location_mode: str = "cwd"
		self.backup_fixed_path: str = ""
		self.backup_root = Path.cwd() / "backups"

		self.games: Dict[str, GameProfile] = {}
		self.theme: str = "system"
		self.window_geometry: str | None = None
		self.table_widths: List[int] = []

		self.backup_root.mkdir(parents=True, exist_ok=True)
		self.load_config()
		# Re-evaluate backup root after loading config settings.
		self.update_backup_root()
		self.backup_root.mkdir(parents=True, exist_ok=True)

	def update_backup_root(self) -> None:
		"""Update backup_root based on current mode/path settings."""
		if self.backup_location_mode == "fixed" and self.backup_fixed_path:
			p = PathUtils.expand(self.backup_fixed_path)
			self.backup_root = p
		else:
			self.backup_root = Path.cwd() / "backups"

	def set_backup_mode_cwd(self) -> None:
		self.backup_location_mode = "cwd"
		self.backup_fixed_path = ""
		self.update_backup_root()
		self.backup_root.mkdir(parents=True, exist_ok=True)
		self.save_config()

	def set_backup_mode_fixed(self, fixed_path: str) -> None:
		self.backup_location_mode = "fixed"
		self.backup_fixed_path = fixed_path
		self.update_backup_root()
		self.backup_root.mkdir(parents=True, exist_ok=True)
		self.save_config()


	def add_game_from_plugin(self, plugin_data: dict) -> str:
		"""Add a game profile originating from a plugin detection result."""
		profile = GameProfile(
			id=f"plugin_{plugin_data['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
			name=plugin_data["name"],
			save_path=plugin_data["save_path"],
			use_compression=plugin_data.get("use_compression", True),
			clear_folder_on_restore=plugin_data.get("clear_folder_on_restore", True),
			plugin_id=plugin_data.get("plugin_id", plugin_data.get("id", "")),
			icon=plugin_data.get("icon", ""),
		)
		self.games[profile.id] = profile
		self.save_config()
		return profile.id

	def load_config(self) -> None:
		if not self.config_path.exists():
			return
		try:
			with open(self.config_path, "r", encoding="utf-8") as f:
				data = json.load(f)

			self.games.clear()
			for game_data in data.get("games", []):
				profile = GameProfile.from_dict(game_data)
				self.games[profile.id] = profile

			self.theme = data.get("theme", "system")
			wg = data.get("window_geometry")
			self.window_geometry = wg if isinstance(wg, str) and wg else None
			self.table_widths = data.get("table_widths", [])
			# New backup location fields (fallbacks if missing)
			self.backup_location_mode = data.get("backup_location_mode", self.backup_location_mode)
			self.backup_fixed_path = data.get("backup_fixed_path", self.backup_fixed_path)
		except json.JSONDecodeError:
			logging.error("Config file is corrupted. Renaming and starting fresh.")
			try:
				bad_file = self.config_path.with_suffix(".json.corrupted")
				shutil.move(self.config_path, bad_file)
			except Exception:
				logging.error("Failed to rename corrupted config file.")
			self.games = {}
		except Exception as e:
			logging.error(f"Config load failed: {e}")

	def save_config(self) -> None:
		data = {
			"games": [p.to_dict() for p in self.games.values()],
			"theme": self.theme,
			"window_geometry": self.window_geometry,
			"table_widths": self.table_widths,
			"backup_location_mode": self.backup_location_mode,
			"backup_fixed_path": self.backup_fixed_path,
			"last_updated": datetime.now().isoformat(),
		}
		tmp_path = self.config_path.with_suffix(".tmp")
		try:
			with open(tmp_path, "w", encoding="utf-8") as f:
				json.dump(data, f, indent=2)
				f.flush()
				try:
					os.fsync(f.fileno())
				except Exception as e:
					logging.debug(f"fsync failed: {e}")
			tmp_path.replace(self.config_path)
		except Exception as e:
			logging.error(f"Config save failed: {e}")

	def get_game_backup_dir(self, game_name: str) -> Path:
		d = self.backup_root / game_name
		d.mkdir(parents=True, exist_ok=True)
		return d

	def get_safety_backup_dir(self, game_name: str) -> Path:
		d = self.backup_root / game_name / "Safety"
		d.mkdir(parents=True, exist_ok=True)
		return d


def run_backup(profile: GameProfile, config: ConfigManager) -> Path:
	"""Perform a backup for the given profile (no plugin hooks here).

	UI code can wrap this with plugin pre/post hooks if desired.
	"""

	source_path = PathUtils.expand(profile.save_path)
	if not source_path.exists():
		raise FileNotFoundError(f"Source path not found: {source_path}")

	dest_dir = config.get_game_backup_dir(profile.name)
	timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	dest_zip = dest_dir / f"{profile.name}_{timestamp}.zip"

	files_to_zip: List[Path] = []
	for root, _, files in os.walk(source_path):
		for file in files:
			files_to_zip.append(Path(root) / file)

	if not files_to_zip:
		raise RuntimeError("Folder is empty.")

	compression = zipfile.ZIP_DEFLATED if profile.use_compression else zipfile.ZIP_STORED

	with zipfile.ZipFile(dest_zip, "w", compression) as zf:
		for file_path in files_to_zip:
			rel_path = file_path.relative_to(source_path)
			zf.write(file_path, rel_path)

	return dest_zip


def run_restore(profile: GameProfile, config: ConfigManager, backup_file: Path, clear_first: bool) -> None:
	"""Restore a backup for the given profile (no plugin hooks here)."""

	target_path = PathUtils.expand(profile.save_path)

	if target_path.exists() and any(target_path.iterdir()):
		safety_dir = config.get_safety_backup_dir(profile.name)
		timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		safety_zip = safety_dir / f"SAFETY_{timestamp}.zip"
		shutil.make_archive(str(safety_zip.with_suffix("")), "zip", target_path)

	if clear_first and target_path.exists():
		shutil.rmtree(target_path)
		target_path.mkdir(parents=True, exist_ok=True)
	elif not target_path.exists():
		target_path.mkdir(parents=True, exist_ok=True)

	with zipfile.ZipFile(backup_file, "r") as zf:
		zf.extractall(target_path)

