"""Core logic for BackupSeeker Game Save Manager.

This module is a cleaned-up, importable version of the single-file
implementation in `gemini.py`. It exposes reusable building blocks
without any GUI wiring so other tools can call into it.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import platform
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

try:
	import winreg
except Exception:  # pragma: no cover
	winreg = None

if winreg is not None:
	_WINREG_HKEY_BY_NAME: Dict[str, Any] = {
		"HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
		"HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
		"HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
		"HKEY_USERS": winreg.HKEY_USERS,
		"HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
	}
else:
	_WINREG_HKEY_BY_NAME = {}

from . import archive as _archive_ns
from . import plugin_runtime as _pr
from .archive.constants import (
	BACKUP_BUNDLE_PATH,
	PORTABLE_CONTRACT_EMBED_PATH,
	PORTABLE_LOADER_EMBED_PATH,
	RESTORE_CLI_PATH,
	ZIP_README_PATH,
)
from .archive.restore_core import is_safe_zip_member_rest
from .registry_win import export_registry_entries

# Single ZIP member uncompressed size guard (restore / UI probe).
MAX_RESTORE_ENTRY_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
CONFIG_FORMAT_VERSION = 1


def _normalize_ui_view_value(raw: object, default: str = "list") -> str:
	"""Normalize persisted list/cards toggle to 'list' or 'cards'."""

	s = str(raw).strip().lower() if raw is not None else ""
	if s in ("cards", "card"):
		return "cards"
	if s == "list":
		return "list"
	if s.startswith("c"):
		return "cards"
	return default if default in ("list", "cards") else "list"


def log_and_reraise(ctx: str, *, likely_cause: str | None = None) -> None:
	"""Emit a full traceback with context, optional root-cause hint; re-raises the active exception."""
	hint = f"\nLikely cause: {likely_cause}" if likely_cause else ""
	logging.error(
		"%s\n%s%s\n%s",
		"!" * 72,
		ctx,
		hint,
		"!" * 72,
		exc_info=True,
	)
	raise


def sanitize_backup_filename_component(label: str, *, max_len: int = 80) -> str:
	"""Safe fragment for backup .zip filenames (Windows-safe, no trailing dots/spaces)."""

	s = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", (label or "").strip())
	s = re.sub(r"_+", "_", s).strip(" ._")
	if not s:
		s = "backup"
	return s[:max_len]


def _manifest_roots_from_profile(
	profile: GameProfile,
	plugin: object | None,
	*,
	manifest_keys: set[str],
	key_to_logical: Dict[str, str],
	archive_rows: List[Tuple[str, Path, Path]],
) -> List[Dict[str, Any]]:
	"""Build ``roots`` entries for format 4 (one row per configured save root)."""

	count_by_sk: Dict[str, int] = {}
	for sk, _, _ in archive_rows:
		count_by_sk[sk] = count_by_sk.get(sk, 0) + 1

	roots_out: List[Dict[str, Any]] = []
	for logical_key, contracted in profile.effective_save_locations(plugin):
		sk = zip_sanitized_key(logical_key, plugin)
		logical = key_to_logical.get(sk, logical_key)
		roots_out.append(
			{
				"logical_key": logical,
				"sanitized_key": sk,
				"contracted_save_path": contracted,
				"included_in_archive": sk in manifest_keys,
				"files_in_backup": int(count_by_sk.get(sk, 0)),
			}
		)
	return roots_out


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


def sanitize_location_key(key: str) -> str:
	"""Stable folder name inside backup ZIP archives."""
	s = re.sub(r"[^a-zA-Z0-9_-]+", "_", (key or "").strip())
	s = (s[:64] if len(s) > 64 else s) if s else "loc"
	return s or "loc"


def zip_sanitized_key(logical_key: str, plugin: object | None) -> str:
	"""ZIP root folder name for a logical save root (optional per-plugin aliases)."""

	p = _pr.as_game_plugin(plugin)
	aliases = p.zip_key_aliases if p is not None else None
	if isinstance(aliases, dict):
		raw = aliases.get(logical_key)
		if isinstance(raw, str) and raw.strip():
			return sanitize_location_key(raw.strip())
	return sanitize_location_key(logical_key)


def path_matches_file_patterns(rel_posix: str, patterns: List[str]) -> bool:
	if not patterns:
		return True
	name = Path(rel_posix).name
	for pat in patterns:
		if fnmatch.fnmatch(name, pat):
			return True
		if fnmatch.fnmatch(rel_posix.replace("\\", "/"), pat):
			return True
	return False


_SKIP_WALK_DIRS = frozenset(
	{
		".git",
		"__pycache__",
		"node_modules",
		".svn",
		".hg",
	}
)


def _relative_excluded(rel_posix: str, exclude_globs: List[str]) -> bool:
	for pat in exclude_globs:
		if fnmatch.fnmatch(rel_posix, pat) or fnmatch.fnmatch(Path(rel_posix).name, pat):
			return True
	return False


def collect_files_under(
	root: Path,
	patterns: List[str],
	*,
	exclude_globs: List[str] | None = None,
) -> List[Path]:
	"""All files under root matching glob-style patterns; optional glob excludes (e.g. ``**/cache/**``)."""
	out: List[Path] = []
	excl = list(exclude_globs) if exclude_globs else []
	try:
		root_r = root.resolve()
	except OSError:
		return out
	if not root_r.exists():
		return out
	for dirpath, dirnames, filenames in os.walk(root_r):
		dirnames[:] = [d for d in dirnames if d not in _SKIP_WALK_DIRS]
		for fn in filenames:
			full = Path(dirpath) / fn
			try:
				rel = full.relative_to(root_r).as_posix()
			except ValueError:
				continue
			if excl and _relative_excluded(rel, excl):
				continue
			if path_matches_file_patterns(rel, patterns):
				out.append(full)
	out.sort(key=lambda p: str(p))
	return out


def verify_save_locations_report(profile: GameProfile, plugin: object | None) -> Dict[str, Any]:
	"""Structured status for UI: folders, file counts, optional registry hints."""
	patterns = profile.effective_file_patterns(plugin)
	locs = profile.effective_save_locations(plugin)
	location_rows: List[Dict[str, Any]] = []
	for logical_key, contracted in locs:
		root = PathUtils.expand(contracted)
		exists = root.exists()
		nfiles = 0
		if exists:
			try:
				nfiles = len(collect_files_under(root.resolve(), patterns))
			except OSError:
				nfiles = 0
		location_rows.append(
			{
				"logical_key": logical_key,
				"contracted_path": contracted,
				"expanded_path": str(root),
				"exists": exists,
				"file_count": nfiles,
				"has_data": nfiles > 0,
			}
		)

	reg_rows: List[Dict[str, Any]] = []
	pg = _pr.as_game_plugin(plugin)
	rk_list = list(pg.registry_keys) if pg is not None and pg.registry_keys else []

	if rk_list and winreg is not None:
		for key_path, value_name in rk_list:
			ok = False
			val_disp = ""
			try:
				hkey_str, _, sub_key = key_path.partition("\\")
				hkey = _WINREG_HKEY_BY_NAME.get(hkey_str, winreg.HKEY_CURRENT_USER)
				with winreg.OpenKey(hkey, sub_key) as key:
					install_path, _ = winreg.QueryValueEx(key, value_name)
					ok = bool(install_path and Path(str(install_path)).exists())
					val_disp = str(install_path)[:200]
			except OSError:
				val_disp = "(not found)"
			except Exception as ex:
				val_disp = str(ex)[:120]
			reg_rows.append(
				{
					"key_path": key_path,
					"value_name": value_name,
					"present_and_valid": ok,
					"detail": val_disp,
				}
			)
	elif rk_list:
		for key_path, value_name in rk_list:
			reg_rows.append(
				{
					"key_path": key_path,
					"value_name": value_name,
					"present_and_valid": False,
					"detail": "registry checks require Windows",
				}
			)

	detected = False
	pg2 = _pr.as_game_plugin(plugin)
	if pg2 is not None:
		try:
			detected = bool(pg2.is_detected())
		except Exception:
			detected = False

	return {
		"locations": location_rows,
		"registry": reg_rows,
		"plugin_is_detected": detected,
	}


def _stored_path_field_from_profile_dict(raw_path: object) -> str:
	"""Normalize a ``save_path`` string loaded from JSON for manual profiles."""

	if not isinstance(raw_path, str):
		return ""
	raw = raw_path.strip()
	if not raw:
		return ""
	if "%" in raw or "$" in raw:
		idx = min([i for i in [raw.find("%"), raw.find("$")] if i != -1])
		raw = raw[idx:]
	if raw.startswith(("%", "$")):
		return raw
	return PathUtils.contract(raw)


def _plugin_inputs_dict_from_json(data: dict) -> Dict[str, str]:
	"""Parse ``plugin_inputs`` from persisted profile JSON."""

	out: Dict[str, str] = {}
	raw_pi = data.get("plugin_inputs")
	if not isinstance(raw_pi, dict):
		return out
	for k, v in raw_pi.items():
		ks = str(k).strip()
		if not ks:
			continue
		cv = _stored_path_field_from_profile_dict(v)
		if cv:
			out[ks] = cv
	return out


@dataclass
class GameProfile:
	"""Persisted profile.

	Plugin-backed rows (`plugin_id` set) store minimal fields on disk; display
	name, icons, and default save paths come from the plugin at runtime.
	Named user pins live in ``plugin_inputs`` (keys match ``prompt.input_key``
	and usually the ``directory`` entry ``id``); the profile editor path row maps
	via :meth:`GamePlugin.profile_primary_input_key` (see :mod:`BackupSeeker.plugins.base`).
	"""

	id: str = ""
	name: str = ""  # Manual profile title; for plugin-backed rows optional cache of plugin display name
	save_path: str = ""
	plugin_inputs: Dict[str, str] = field(default_factory=dict)
	file_patterns: List[str] | None = None
	plugin_id: str = ""
	plugin_version: str = ""
	icon: str = ""  # Manual profiles only; plugin profiles use plugin assets
	poster: str = ""

	def __post_init__(self) -> None:
		if self.file_patterns is None:
			self.file_patterns = ["*"]
		if self.plugin_inputs is None:
			self.plugin_inputs = {}
		if self.icon is None:
			self.icon = ""
		if self.poster is None:
			self.poster = ""

	def editor_primary_path_display(self, plugin: object | None) -> str:
		"""Initial text for the profile editor path row."""

		if not self.plugin_id:
			return (self.save_path or "").strip()
		if plugin is None:
			return ""
		pk_fn = getattr(plugin, "profile_primary_input_key", None)
		key_raw = pk_fn() if callable(pk_fn) else None
		key = key_raw.strip() if isinstance(key_raw, str) else ""
		if key:
			return (self.plugin_inputs.get(key) or "").strip()
		return ""

	def apply_editor_primary_path(self, plugin: object | None, raw_path: str) -> None:
		"""Persist the editor path row (manual: ``save_path``; plugin: ``plugin_inputs``)."""

		clean = PathUtils.clean_input_path(raw_path or "")
		contracted = PathUtils.contract(clean) if clean else ""
		if not self.plugin_id:
			self.save_path = contracted
			return
		pk_fn = getattr(plugin, "profile_primary_input_key", None)
		key_raw = pk_fn() if callable(pk_fn) else None
		key = key_raw.strip() if isinstance(key_raw, str) else ""
		if key:
			if contracted:
				self.plugin_inputs[key] = contracted
			else:
				self.plugin_inputs.pop(key, None)

	def resolved_name(self, plugin: object | None) -> str:
		if self.plugin_id:
			pg = _pr.as_game_plugin(plugin)
			if pg is not None:
				gn = pg.game_name
				if isinstance(gn, str) and gn.strip():
					return gn.strip()
			fallback = (self.name or "").strip()
			if fallback:
				return fallback
			return (self.plugin_id or "").strip() or "Game"
		return (self.name or "").strip()

	def effective_save_locations(self, plugin: object | None) -> List[Tuple[str, str]]:
		"""Return (logical_key, contracted_path) pairs for backup/restore.

		Plugin-backed profiles normally use roots from the plugin. Plugins may
		override via ``save_locations_for_profile(self)`` when optional pins in
		``plugin_inputs`` resolve concrete paths.
		"""
		if self.plugin_id and plugin is not None:
			pg = _pr.as_game_plugin(plugin)
			if pg is not None:
				fn = getattr(pg, "save_locations_for_profile", None)
				if callable(fn):
					try:
						resolved = fn(self)
					except Exception:
						resolved = None
					if isinstance(resolved, list) and resolved:
						return resolved
			pairs: List[Tuple[str, str]] = []
			if pg is not None:
				seq = pg.save_locations
				if seq is not None and isinstance(seq, list):
					for item in seq:
						if isinstance(item, (tuple, list)) and len(item) >= 2:
							k, p = str(item[0]).strip(), str(item[1]).strip()
							if p:
								pairs.append((k or "loc", p))
			if pairs:
				return pairs
			if pg is not None:
				paths = pg.save_paths
				if isinstance(paths, list) and paths:
					return [(f"path_{i}", p) for i, p in enumerate(paths)]
			return []
		sp = (self.save_path or "").strip()
		return [("profile", sp)] if sp else []

	def effective_save_path(self, plugin: object | None) -> str:
		"""Short hint for hooks; UI should prefer ``verify_save_locations_report``."""
		locs = self.effective_save_locations(plugin)
		if self.plugin_id:
			n = len(locs)
			return f"{n} save root(s) — run Verify for status" if n else ""
		if not locs:
			return ""
		if len(locs) == 1:
			return locs[0][1]
		return "; ".join(f"{k}: {p}" for k, p in locs)

	def effective_file_patterns(self, plugin: object | None) -> List[str]:
		fp = self.file_patterns if self.file_patterns is not None else ["*"]
		if self.plugin_id and plugin is not None and fp == ["*"]:
			pg = _pr.as_game_plugin(plugin)
			got = pg.file_patterns if pg is not None else None
			if isinstance(got, list) and got:
				return list(got)
		return fp

	def as_operation_dict(self, plugin: object | None) -> Dict:
		pv = (self.plugin_version or "").strip()
		if not pv and plugin is not None:
			pg = _pr.as_game_plugin(plugin)
			v = pg.version if pg is not None else ""
			if isinstance(v, str):
				pv = v.strip()
		return {
			"id": self.id,
			"name": self.resolved_name(plugin),
			"save_path": self.effective_save_path(plugin),
			"save_locations": self.effective_save_locations(plugin),
			"file_patterns": self.effective_file_patterns(plugin),
			"plugin_id": self.plugin_id,
			"plugin_version": pv,
		}

	def to_dict(self) -> Dict[str, Any]:
		common: Dict[str, Any] = {
			"id": self.id,
		}
		if self.plugin_id:
			out = {**common, "plugin_id": self.plugin_id}
			if (self.plugin_version or "").strip():
				out["plugin_version"] = self.plugin_version
			if (self.name or "").strip():
				out["name"] = self.name.strip()
			pi = self.plugin_inputs or {}
			if pi:
				out["plugin_inputs"] = dict(pi)
			fps = self.file_patterns if self.file_patterns is not None else ["*"]
			if fps != ["*"]:
				out["file_patterns"] = fps
			return out
		out = {
			**common,
			"name": self.name,
			"save_path": self.save_path,
			"icon": self.icon or "",
			"poster": self.poster or "",
		}
		fps = self.file_patterns if self.file_patterns is not None else ["*"]
		if fps != ["*"]:
			out["file_patterns"] = fps
		return out

	@classmethod
	def from_dict(cls, data: dict) -> "GameProfile":
		plugin_id_early = (data.get("plugin_id") or "").strip()
		if plugin_id_early:
			save_path = ""
			plugin_inputs = _plugin_inputs_dict_from_json(data)
		else:
			save_path = _stored_path_field_from_profile_dict(data.get("save_path", ""))
			plugin_inputs = {}

		icon = data.get("icon", "") or ""
		poster = data.get("poster", "") or ""

		fp = data.get("file_patterns")
		if not isinstance(fp, list) or not fp:
			fp = ["*"]

		return cls(
			id=data.get("id", ""),
			name=data.get("name", ""),
			save_path=save_path if isinstance(save_path, str) else "",
			plugin_inputs=plugin_inputs,
			file_patterns=fp,
			plugin_id=plugin_id_early,
			plugin_version=data.get("plugin_version", ""),
			icon=icon,
			poster=poster,
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
		self.config_format_version: int = CONFIG_FORMAT_VERSION
		# List vs cards view (per surface), values: "list" | "cards"
		self.ui_view_dashboard_profiles: str = "list"
		self.ui_view_profiles_management: str = "list"
		self.ui_view_backups_management: str = "list"
		self.ui_view_restore_dialog: str = "list"

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
		pid = plugin_data.get("plugin_id") or plugin_data.get("id", "")
		if not pid:
			raise ValueError("plugin_data must include plugin_id")
		profile = GameProfile(
			id=f"plugin_{pid}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
			name="",
			save_path="",
			plugin_id=pid,
			plugin_version=str(plugin_data.get("plugin_version", "") or ""),
			icon="",
			poster="",
		)
		self.games[profile.id] = profile
		self.save_config()
		return profile.id

	def sync_plugin_versions_from(self, plugin_manager: object | None) -> None:
		"""Align stored plugin_version and display name cache with loaded plugins."""
		if plugin_manager is None:
			return
		from .plugin_manager import PluginManager

		if not isinstance(plugin_manager, PluginManager):
			return
		for prof in self.games.values():
			if not prof.plugin_id:
				continue
			plug = plugin_manager.get_plugin_for_profile(prof.plugin_id)
			if plug is None:
				continue
			ver = plug.version
			if isinstance(ver, str) and ver.strip():
				prof.plugin_version = ver.strip()
			gn = plug.game_name
			if isinstance(gn, str) and gn.strip():
				prof.name = gn.strip()

	def load_config(self) -> None:
		if not self.config_path.exists():
			return
		try:
			with open(self.config_path, "r", encoding="utf-8") as f:
				raw = f.read()
			data = json.loads(raw)
		except json.JSONDecodeError:
			bad_file = self.config_path.with_suffix(".json.corrupted")
			if self.config_path.exists():
				shutil.move(self.config_path, bad_file)
			log_and_reraise(
				f"gsm_config.json is invalid JSON (moved aside to {bad_file.name}).",
				likely_cause="Broken JSON from hand edits, truncated write, or disk glitch.",
			)

		self.games.clear()
		for game_data in data.get("games", []):
			profile = GameProfile.from_dict(game_data)
			self.games[profile.id] = profile

		self.theme = data.get("theme", "system")
		wg = data.get("window_geometry")
		self.window_geometry = wg if isinstance(wg, str) and wg else None
		self.table_widths = data.get("table_widths", [])
		self.backup_location_mode = data.get("backup_location_mode", self.backup_location_mode)
		self.backup_fixed_path = data.get("backup_fixed_path", self.backup_fixed_path)
		cfv = data.get("config_format_version", 1)
		self.config_format_version = int(cfv) if isinstance(cfv, int) else 1

		# Per-page list / cards — load before format migration ``save_config`` preserves them.
		uv = data.get("ui_views")
		if isinstance(uv, dict):
			self.ui_view_dashboard_profiles = _normalize_ui_view_value(
				uv.get("dashboard_profiles"), self.ui_view_dashboard_profiles
			)
			self.ui_view_profiles_management = _normalize_ui_view_value(
				uv.get("profiles_management"), self.ui_view_profiles_management
			)
			self.ui_view_backups_management = _normalize_ui_view_value(
				uv.get("backups_management"), self.ui_view_backups_management
			)
			self.ui_view_restore_dialog = _normalize_ui_view_value(
				uv.get("restore_dialog"), self.ui_view_restore_dialog
			)

		if self.config_format_version != CONFIG_FORMAT_VERSION:
			for prof in self.games.values():
				if prof.plugin_id:
					prof.save_path = ""
					prof.plugin_inputs = {}
			self.config_format_version = CONFIG_FORMAT_VERSION
			self.save_config()

	def save_config(self) -> None:
		data = {
			"games": [p.to_dict() for p in self.games.values()],
			"theme": self.theme,
			"window_geometry": self.window_geometry,
			"table_widths": self.table_widths,
			"backup_location_mode": self.backup_location_mode,
			"backup_fixed_path": self.backup_fixed_path,
			"config_format_version": CONFIG_FORMAT_VERSION,
			"last_updated": datetime.now().isoformat(),
			"ui_views": {
				"dashboard_profiles": self.ui_view_dashboard_profiles,
				"profiles_management": self.ui_view_profiles_management,
				"backups_management": self.ui_view_backups_management,
				"restore_dialog": self.ui_view_restore_dialog,
			},
		}
		tmp_path = self.config_path.with_suffix(".tmp")
		try:
			with open(tmp_path, "w", encoding="utf-8") as f:
				json.dump(data, f, indent=2)
				f.flush()
				os.fsync(f.fileno())
			tmp_path.replace(self.config_path)
		except Exception:
			log_and_reraise(
				f"Cannot write config to {self.config_path}",
				likely_cause="Insufficient permissions, disk full, antivirus lock, or read-only location.",
			)

	def get_game_backup_dir(self, folder_component: str) -> Path:
		"""Per-game folder under :attr:`backup_root` (``folder_component`` is sanitized)."""

		safe = sanitize_backup_filename_component(folder_component)
		d = self.backup_root / safe
		d.mkdir(parents=True, exist_ok=True)
		return d

	def get_safety_backup_dir(self, folder_component: str) -> Path:
		"""``Safety`` subfolder for pre-restore ZIPs (``folder_component`` is sanitized)."""

		safe = sanitize_backup_filename_component(folder_component)
		d = self.backup_root / safe / "Safety"
		d.mkdir(parents=True, exist_ok=True)
		return d

	def backup_dir_for_profile(self, profile: GameProfile, plugin: object | None) -> Path:
		"""Same directory ``run_backup`` writes into for this profile + plugin resolution."""

		return self.get_game_backup_dir(profile.resolved_name(plugin))

	def safety_backup_dir_for_profile(self, profile: GameProfile, plugin: object | None) -> Path:
		"""Safety ZIP folder paired with :meth:`backup_dir_for_profile`."""

		return self.get_safety_backup_dir(profile.resolved_name(plugin))


def clear_before_restore(plugin: object | None) -> bool:
	"""Delete each save root before unpacking (`run_restore`). Manual profiles default to True."""

	return _pr.clear_folder_on_restore(plugin)


def restore_confirmation_details(
	profile: GameProfile,
	plugin: object | None,
	config: ConfigManager,
) -> Dict[str, Any]:
	"""Facts for UI copy: wipe vs merge, and whether safety ZIPs are written per root."""

	label = profile.resolved_name(plugin)
	clear_first = clear_before_restore(plugin)
	locs = profile.effective_save_locations(plugin)
	safety_folder = config.safety_backup_dir_for_profile(profile, plugin)
	roots: List[Dict[str, Any]] = []
	for logical_key, contracted in locs:
		dest = PathUtils.expand(contracted)
		has_files = False
		if dest.exists():
			has_files = any(dest.iterdir())
		roots.append(
			{
				"logical_key": logical_key,
				"expanded_path": str(dest),
				"has_existing_files": has_files,
				"safety_zip_first": has_files,
			}
		)

	return {
		"game_label": label,
		"clear_before_unpack": clear_first,
		"safety_folder_display": str(safety_folder),
		"roots": roots,
		"any_safety_zip": any(r["safety_zip_first"] for r in roots),
		"policy_from_plugin": bool(plugin is not None and (profile.plugin_id or "").strip()),
	}


def _gather_archive_rows(
	profile: GameProfile,
	plugin: object | None,
	*,
	allow_empty_mechanical_fallback: bool,
) -> Tuple[List[Tuple[str, Path, Path]], List[str], List[str]]:
	"""Try ``mechanical_collect_archive_rows``, else walk each configured root."""

	patterns = profile.effective_file_patterns(plugin)
	locs = profile.effective_save_locations(plugin)
	if not locs:
		return [], [], []

	exclude_globs: List[str] = []
	if plugin is not None:
		raw_ex = _pr.backup_exclude_globs(plugin)
		if raw_ex:
			exclude_globs = [str(x) for x in raw_ex]

	mechanical: List[Tuple[str, Path, Path]] | None = None
	if plugin is not None:
		try:
			raw = _pr.mechanical_collect_archive_rows(
				plugin,
				profile.as_operation_dict(plugin),
				patterns=patterns,
				exclude_globs=exclude_globs,
			)
			if isinstance(raw, list):
				mechanical = cast(List[Tuple[str, Path, Path]], raw)
		except Exception:
			logging.exception(
				"mechanical_collect_archive_rows failed for %r",
				_pr.plugin_log_id(plugin),
			)

	if mechanical:
		return mechanical, [], []

	if mechanical is not None and not allow_empty_mechanical_fallback:
		raise RuntimeError("mechanical_collect_archive_rows returned no files.")

	archive_rows: List[Tuple[str, Path, Path]] = []
	hints: List[str] = []
	root_diagnostics: List[str] = []
	for logical_key, contracted in locs:
		key = zip_sanitized_key(logical_key, plugin)
		root = PathUtils.expand(contracted)
		hints.append(f"{logical_key}->{contracted}")
		if not root.exists():
			root_diagnostics.append(
				f"{logical_key}: folder does not exist ({contracted})"
			)
			continue
		try:
			files = collect_files_under(root, patterns, exclude_globs=exclude_globs)
			root_res = root.resolve()
		except OSError:
			continue
		for fpath in files:
			try:
				rel = fpath.relative_to(root_res)
			except ValueError:
				continue
			archive_rows.append((key, fpath, rel))
		if not files:
			pat_hint = ", ".join(patterns) if patterns else "*"
			root_diagnostics.append(
				f"{logical_key}: folder exists but no files matched patterns [{pat_hint}] ({contracted})"
			)

	return archive_rows, hints, root_diagnostics


def _plugin_snapshot_and_registry(plugin: object | None) -> Tuple[Dict[str, Any], Dict[str, Any] | None]:
	snapshot = _pr.call_to_snapshot_dict(plugin)
	if plugin is None:
		return snapshot, None
	pairs = _pr.registry_export_pairs(plugin)
	if not pairs:
		return snapshot, None
	reg = export_registry_entries(pairs)
	return (snapshot, reg) if isinstance(reg, dict) and reg.get("entries") else (snapshot, None)


def _finalize_bundle_body(plugin: object | None, body: Dict[str, Any]) -> Dict[str, Any]:
	if plugin is None:
		return body
	try:
		out = _pr.mechanical_finalize_bundle(plugin, body)
		return cast(Dict[str, Any], out) if isinstance(out, dict) else body
	except Exception:
		logging.exception("mechanical_finalize_bundle failed for %r", _pr.plugin_log_id(plugin))
		return body


def run_backup(
	profile: GameProfile,
	config: ConfigManager,
	plugin: object | None = None,
	*,
	relaxed: bool = False,
	dest_zip: Path | None = None,
	bundle_app_extra: Dict[str, Any] | None = None,
) -> Path | None:
	"""Backup all configured save roots into one ZIP (bundle.json format 1 + README + portable restore_cli).

	:param relaxed: If True, use the same collection rules but do not raise when nothing is found
		(missing roots / empty mechanical result falls back to walking; still no rows → return ``None``).
	:param dest_zip: Output path; default is under :meth:`ConfigManager.backup_dir_for_profile`.
	:param bundle_app_extra: Merged into the bundle ``app`` section (e.g. safety checkpoint metadata).
	"""

	from .archive.bundle import build_bundle
	from .archive.packaging import (
		build_archive_readme,
		build_restore_cli_script,
		embedded_plugin_arc_path,
		read_portable_embed_sources,
		resolve_plugin_source_for_embed,
	)

	label = profile.resolved_name(plugin)
	locs = profile.effective_save_locations(plugin)
	if not locs:
		if relaxed:
			return None
		raise FileNotFoundError("No save locations configured for this profile.")

	bmf = _archive_ns.constants.BUNDLE_FORMAT_VERSION
	timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	base_name = sanitize_backup_filename_component(label)
	if dest_zip is None:
		dest_zip = config.backup_dir_for_profile(profile, plugin) / f"{base_name}_{timestamp}_bsmf{bmf}.zip"
	compression = zipfile.ZIP_DEFLATED

	archive_rows, hints, root_diagnostics = _gather_archive_rows(
		profile, plugin, allow_empty_mechanical_fallback=relaxed
	)

	if not archive_rows:
		if relaxed:
			return None
		detail = (
			"; ".join(root_diagnostics)
			if root_diagnostics
			else f"Configured: {' | '.join(hints)}"
		)
		raise RuntimeError(
			"No save files found in any configured location. "
			f"{detail}"
		)

	key_to_logical: Dict[str, str] = {zip_sanitized_key(k, plugin): k for k, _ in locs}
	manifest_keys_sorted = sorted({str(k) for k, _, _ in archive_rows})
	logical_keys_map = {sk: key_to_logical.get(sk, sk) for sk in manifest_keys_sorted}
	roots = _manifest_roots_from_profile(
		profile,
		plugin,
		manifest_keys=set(manifest_keys_sorted),
		key_to_logical=key_to_logical,
		archive_rows=archive_rows,
	)

	created_at = datetime.now().isoformat(timespec="seconds")
	snapshot, registry_export = _plugin_snapshot_and_registry(plugin)

	app_extra: Dict[str, Any] = {"generator": "run_backup"}
	if bundle_app_extra:
		app_extra.update(bundle_app_extra)

	bundle_body = _finalize_bundle_body(
		plugin,
		build_bundle(
			created_at=created_at,
			profile_id=(profile.id or "").strip(),
			display_name=profile.resolved_name(plugin),
			plugin_id=(profile.plugin_id or "").strip(),
			plugin_version=str(profile.as_operation_dict(plugin).get("plugin_version") or ""),
			file_patterns=list(profile.effective_file_patterns(plugin)),
			manifest_keys=list(manifest_keys_sorted),
			logical_keys_map=logical_keys_map,
			roots=roots,
			plugin_snapshot=snapshot,
			registry_export=registry_export,
			app_extra=app_extra,
		),
	)

	extra_lines: List[str] = []
	if plugin is not None:
		extra_lines = _pr.extra_readme_lines(plugin)

	readme_text = build_archive_readme(bundle_body, extra_lines=extra_lines or None)

	embed_arcname: str | None = None
	embed_py_source: str | None = None
	if plugin is not None:
		psrc = resolve_plugin_source_for_embed(plugin)
		if psrc is not None:
			try:
				embed_py_source = psrc.read_text(encoding="utf-8")
				embed_arcname = embedded_plugin_arc_path(_pr.embed_arc_basename(plugin))
			except OSError:
				logging.exception("Could not read plugin source for embed: %s", psrc)

	cli_src = build_restore_cli_script(
		embedded_plugin_arcname=embed_arcname,
		has_registry_export=bool(registry_export),
	)

	pc_text, pl_text = read_portable_embed_sources()

	with zipfile.ZipFile(dest_zip, "w", compression) as zf:
		zf.writestr(BACKUP_BUNDLE_PATH, json.dumps(bundle_body, indent=2))
		zf.writestr(ZIP_README_PATH, readme_text)
		zf.writestr(RESTORE_CLI_PATH, cli_src)
		zf.writestr(PORTABLE_CONTRACT_EMBED_PATH, pc_text)
		zf.writestr(PORTABLE_LOADER_EMBED_PATH, pl_text)
		if embed_arcname and embed_py_source is not None:
			zf.writestr(embed_arcname, embed_py_source)
		for key, full_path, rel in archive_rows:
			arcname = f"{key}/{rel.as_posix()}"
			zf.write(full_path, arcname)

	return dest_zip


def _unique_expand_roots(locs: List[Tuple[str, str]]) -> List[Path]:
	seen: set[str] = set()
	out: List[Path] = []
	for _, contracted in locs:
		try:
			p = PathUtils.expand(contracted).resolve()
		except Exception:
			continue
		key = str(p)
		if key not in seen:
			seen.add(key)
			out.append(p)
	return out


def run_restore(
	profile: GameProfile,
	config: ConfigManager,
	backup_file: Path,
	clear_first: bool,
	plugin: object | None = None,
	*,
	restore_registry: bool | None = None,
) -> None:
	"""Restore from a bundle archive (``bundle.json`` format 1 only)."""

	from .archive.metadata import read_archive_metadata
	from .registry_win import import_registry_entries

	locs = profile.effective_save_locations(plugin)
	if not locs:
		raise FileNotFoundError("No save locations configured for this profile.")

	meta = read_archive_metadata(backup_file)
	if meta is None:
		raise RuntimeError(
			f"This backup archive is missing a valid bundle ({BACKUP_BUNDLE_PATH}, format {_archive_ns.constants.BUNDLE_FORMAT_VERSION})."
		)

	raw = meta.raw
	gm = raw.get("game")
	if isinstance(gm, dict) and isinstance(gm.get("plugin_id"), str):
		arch_pid = gm["plugin_id"].strip()
		if arch_pid and (profile.plugin_id or "").strip() and arch_pid != (profile.plugin_id or "").strip():
			logging.warning(
				"Restore: archive plugin_id %r differs from profile %r — using current profile paths",
				arch_pid,
				(profile.plugin_id or "").strip(),
			)

	map_sk_to_contracted: Dict[str, str] = {}
	for logical_key, contracted in locs:
		map_sk_to_contracted[zip_sanitized_key(logical_key, plugin)] = contracted

	bmf = _archive_ns.constants.BUNDLE_FORMAT_VERSION
	ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	base_name = sanitize_backup_filename_component(profile.resolved_name(plugin))
	run_backup(
		profile,
		config,
		plugin,
		relaxed=True,
		dest_zip=config.safety_backup_dir_for_profile(profile, plugin)
		/ f"SAFETY_{base_name}_{ts}_bsmf{bmf}.zip",
		bundle_app_extra={
			"generator": "run_restore_safety_checkpoint",
			"safety_checkpoint_format": bmf,
		},
	)

	for dest in _unique_expand_roots(locs):
		if clear_first and dest.exists():
			shutil.rmtree(dest)
		dest.mkdir(parents=True, exist_ok=True)

	with zipfile.ZipFile(backup_file, "r") as zf:
		for info in zf.infolist():
			name = info.filename
			if not name or name.endswith("/"):
				continue
			n = name.replace("\\", "/")
			if n.startswith("_backupseeker/"):
				continue
			parts = n.split("/", 1)
			if len(parts) < 2:
				continue
			sk, rest = parts[0], parts[1]
			if not is_safe_zip_member_rest(rest):
				logging.warning("Skipping unsafe archive path in %s: %s", backup_file, name)
				continue
			contracted = map_sk_to_contracted.get(sk)
			if not contracted:
				continue
			if info.file_size > MAX_RESTORE_ENTRY_UNCOMPRESSED_BYTES:
				raise RuntimeError(
					f"Refusing to extract oversized entry ({info.file_size} bytes): {name!r}"
				)
			dest_root = PathUtils.expand(contracted)
			out_path = dest_root / rest.replace("/", os.sep)
			out_path.parent.mkdir(parents=True, exist_ok=True)
			with zf.open(info) as src, open(out_path, "wb") as dst:
				shutil.copyfileobj(src, dst)

	do_reg = restore_registry
	if do_reg is None:
		do_reg = bool(meta.has_registry_export and platform.system() == "Windows")

	reg_done = False
	if do_reg and meta.has_registry_export:
		import_registry_entries(raw.get("registry_export"))
		reg_done = True

	if plugin is not None:
		try:
			_pr.mechanical_after_app_restore(
				plugin,
				{
					"backup_file": backup_file,
					"profile": profile.as_operation_dict(plugin),
					"registry_restored": reg_done,
					"raw_bundle": raw,
				},
			)
		except Exception:
			logging.exception(
				"mechanical_after_app_restore failed for %r",
				_pr.plugin_log_id(plugin),
			)


from .archive.metadata import read_archive_metadata, summarize_archive_metadata
