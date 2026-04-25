from __future__ import annotations

try:
	import winreg
except Exception:  # pragma: no cover - non-Windows environments
	winreg = None
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
import inspect
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, Tuple

import logging

from ..core import PathUtils, zip_sanitized_key
from .prompt_validation import normalize_validations
from .save_sources import (
	CANDIDACY_ALWAYS,
	CANDIDACY_NO_CANDIDATE_THIS_OR_IDS,
	PROMPT_WHEN_NO_CANDIDATE,
	SAVE_KIND_DIRECTORY,
	flatten_locations_from_sources,
	flatten_paths_from_sources,
	registry_pairs_from_sources,
	sources_from_plugin_dict,
)

if TYPE_CHECKING:
	from ..core import GameProfile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RestoreInputSpec:
	"""Declarative prompts for bundled portable restore (stdin) or GUI restore/backup."""

	key: str
	prompt: str
	kind: str = "existing_directory"
	example: str = ""
	label: str = ""
	validations: Tuple[str, ...] = ()
	candidacy: str = PROMPT_WHEN_NO_CANDIDATE
	candidacy_any_of_ids: Tuple[str, ...] = ()


class GamePlugin(ABC):
	"""Base class for all game plugins.

	Subclass this to describe a game's save locations and optional
	lifecycle hooks. Implement required properties and override hooks
	if specialized behavior is needed during backup/restore.
	"""

	version: str = "1.0.0"  # Plugin version for tracking updates

	@property
	@abstractmethod
	def game_id(self) -> str:
		"""Unique identifier for the game."""

	# Runtime-populated fields for plugin asset management. Declared here
	# so static analyzers know these attributes exist when PluginManager
	# assigns to them (e.g. `_saved_icon` and `_icon_source`).
	_saved_icon: str = ""
	_icon_source: str = ""
	_saved_poster: str = ""
	_poster_source: str = ""
	# Set True after PluginManager has run download/copy for icon+poster (lazy).
	_visual_assets_loaded: bool = False

	@property
	@abstractmethod
	def game_name(self) -> str:
		"""Display name for the game."""

	@property
	@abstractmethod
	def save_sources(self) -> List[Dict[str, Any]]:
		"""Declarative list of dicts: directory roots, registry probes, optional prompts.

		See :mod:`BackupSeeker.plugins.save_sources`. Derived APIs:
		:meth:`save_locations`, :meth:`save_paths`, :meth:`registry_keys`.
		"""

	@property
	def save_locations(self) -> List[Tuple[str, str]]:
		"""Flattened ``(logical id, contracted path)`` from ``directory`` sources only."""

		return flatten_locations_from_sources(self.save_sources)

	@property
	def save_paths(self) -> List[str]:
		"""All directory candidate paths in schema order."""

		return flatten_paths_from_sources(self.save_sources)

	@property
	def file_patterns(self) -> List[str]:
		return ["*"]

	@property
	def registry_keys(self) -> List[Tuple[str, str]]:
		return registry_pairs_from_sources(self.save_sources)

	@property
	def backup_registry_values(self) -> bool:
		"""When True, export ``registry_keys`` values into the archive bundle (opt-in)."""

		return False

	@property
	def zip_key_aliases(self) -> Dict[str, str]:
		"""Optional logical_key → short tag for ZIP folder names (passed through ``sanitize_location_key``)."""

		return {}

	@property
	def backup_exclude_globs(self) -> List[str]:
		"""Glob patterns (relative POSIX paths) excluded from backup walks."""

		return []

	@property
	def clear_folder_on_restore(self) -> bool:
		"""If True, each save root is removed before unpack. If False, merge (ZIP overwrites paths only)."""

		return True

	def save_detection_groups(self) -> List[Tuple[str, List[str]]]:
		"""``(logical_key, paths…)`` — one group per ``directory`` source ``id``."""

		order: List[str] = []
		buckets: Dict[str, List[str]] = {}
		for lk, p in self.save_locations:
			s = (p or "").strip()
			if not s:
				continue
			if lk not in buckets:
				order.append(lk)
				buckets[lk] = []
			buckets[lk].append(s)
		return [(k, buckets[k]) for k in order]

	def iter_detection_contracted_paths(self) -> List[str]:
		"""Flatten :meth:`save_detection_groups` (same order as grouped ``save_locations``)."""

		out: List[str] = []
		for _, plist in self.save_detection_groups():
			out.extend(plist)
		return out

	def save_candidate_root_exists(self) -> bool:
		"""True if any contracted candidate exists as a directory (skip optional install-dir prompts)."""

		for contracted in self.iter_detection_contracted_paths():
			if self._contracted_dir_exists(contracted):
				return True
		return False

	def _contracted_dir_exists(self, contracted: str) -> bool:
		try:
			p = PathUtils.expand(contracted)
		except (OSError, ValueError, KeyError):
			return False
		try:
			return p.exists() and p.is_dir()
		except OSError:
			return False

	def _contracted_save_root_from_pin_entry(self, entry: Dict[str, Any], raw_pin: str) -> Optional[str]:
		"""Expand a user-entered contracted path pin to the effective save root.

		If ``directory`` entry includes ``pin_relative_segments`` (POSIX-ish names under the pin),
		those segments are appended to the expanded pin root. Otherwise the pin is the save root.

		The pin itself must resolve to an existing directory.
		"""

		clean = PathUtils.clean_input_path(raw_pin or "")
		if not clean:
			return None
		try:
			base = PathUtils.expand(clean)
		except (OSError, ValueError, KeyError):
			return None
		try:
			if not base.is_dir():
				return None
		except OSError:
			return None

		segs_raw = entry.get("pin_relative_segments")
		dest: Path
		if isinstance(segs_raw, list) and segs_raw:
			parts = [str(x).strip() for x in segs_raw if str(x).strip()]
			dest = base
			for part in parts:
				dest = dest / part
			try:
				dest = dest.resolve(strict=False)
			except (OSError, ValueError):
				dest = Path(base)
				for part in parts:
					dest = dest / part
		else:
			try:
				dest = base.resolve(strict=False)
			except (OSError, ValueError):
				dest = base

		try:
			return PathUtils.contract(str(dest))
		except Exception:
			return None

	@property
	def icon(self) -> str:
		"""Optional icon for the game (emoji or path to icon file)."""
		return ""  # Default empty string

	@property
	def poster(self) -> str:
		"""Optional poster image for the game (URL or path to image file)."""
		return ""  # Default empty string

	# --- Optional lifecycle hooks (override as needed) ---

	def preprocess_backup(self, profile_data: Dict) -> Dict:
		"""Hook called before a backup starts.

		Can mutate and return a new profile dict (e.g. tweak save_path
		or patterns), or just return the original.
		"""

		return profile_data

	def postprocess_backup(self, result_data: Dict) -> Dict:
		"""Hook called after a backup finishes successfully.

		Can add metadata, verify results, etc.
		"""

		return result_data

	def preprocess_restore(self, profile_data: Dict) -> Dict:
		"""Hook called before restore starts."""

		return profile_data

	def postprocess_restore(self, result_data: Dict) -> Dict:
		"""Hook called after restore completes."""

		return result_data

	def is_detected(self) -> bool:
		"""Return True if the game appears installed on the current system.

		Detection uses two strategies:
		- Presence of configured registry keys (Windows only, checked first)
		- Existence of any `save_paths` after expansion
		"""
		# Check registry first as it's often more definitive of an active install
		if self._check_registry():
			return True
		
		# Check paths (group order when :meth:`save_detection_groups` is set)
		for path in self.iter_detection_contracted_paths():
			try:
				expanded = PathUtils.expand(path)
				if expanded.exists():
					return True
			except (OSError, ValueError, KeyError):
				# Handle malformed paths or unresolvable environment variables
				continue
		return False

	def _check_registry(self) -> bool:
		"""Check if the game is installed via registry keys (Windows only).
		
		Returns False silently if:
		- winreg is unavailable (non-Windows)
		- registry keys are not configured
		- keys don't exist (normal for uninstalled games)
		"""
		if winreg is None:
			return False
		
		for key_path, value_name in self.registry_keys:
			try:
				# Map string to HKEY constants (e.g., "HKEY_LOCAL_MACHINE" -> winreg.HKEY_LOCAL_MACHINE)
				hkey_str, _, sub_key = key_path.partition('\\')
				hkey = (
					winreg.HKEY_CLASSES_ROOT if hkey_str == "HKEY_CLASSES_ROOT"
					else winreg.HKEY_LOCAL_MACHINE if hkey_str == "HKEY_LOCAL_MACHINE"
					else winreg.HKEY_USERS if hkey_str == "HKEY_USERS"
					else winreg.HKEY_CURRENT_CONFIG if hkey_str == "HKEY_CURRENT_CONFIG"
					else winreg.HKEY_CURRENT_USER
				)
				
				with winreg.OpenKey(hkey, sub_key) as key:
					install_path, _ = winreg.QueryValueEx(key, value_name)
					if install_path and Path(install_path).exists():
						return True
			except (FileNotFoundError, OSError, AttributeError, TypeError):
				# Normal behavior: key or value doesn't exist, or invalid format
				# Use debug level to avoid log spam during normal discovery
				continue
		
		return False

	def get_detected_path(self) -> Optional[str]:
		"""Return the first `save_paths` entry that exists on disk, or None.

		The returned value is the *contracted* form (e.g. contains environment
		variables). The UI uses this to pre-fill new profiles.
		
		Safely handles malformed environment variables by skipping paths
		that can't be expanded.
		"""
		paths = self.iter_detection_contracted_paths()
		for path in paths:
			try:
				expanded = PathUtils.expand(path)
				if expanded.exists():
					return path
			except (OSError, ValueError, KeyError):
				# Skip paths with unresolvable environment variables
				continue
		
		# Fallback to first path even if it doesn't exist
		return paths[0] if paths else None

	def get_detected_paths(self) -> List[str]:
		"""Return all `save_paths` entries that exist on disk.
		
		Useful for games that split saves across multiple locations.
		Returns contracted form paths (with environment variables).
		"""
		detected = []
		for path in self.iter_detection_contracted_paths():
			try:
				expanded = PathUtils.expand(path)
				if expanded.exists():
					detected.append(path)
			except (OSError, ValueError, KeyError):
				# Skip paths with unresolvable environment variables
				continue
		return detected

	@staticmethod
	def get_codex_path(app_id: str) -> str:
		"""Generate CODEX save path for a game given its Steam AppID.
		
		Example:
			get_codex_path("1332010") -> "%PUBLIC%/Documents/Steam/CODEX/1332010/remote"
		"""
		return f"%PUBLIC%/Documents/Steam/CODEX/{app_id}/remote"

	def to_profile(self) -> Dict:
		"""Return fields for adding a profile; config stores only references.

		Display metadata lives on the plugin; persisted rows keep ``plugin_id``
		and ``plugin_version``. Save paths always come from the plugin at runtime.
		"""
		return {
			"plugin_id": self.game_id,
			"plugin_version": self.version,
		}

	@property
	def plugin_kind(self) -> str:
		"""``mechanical_python`` (code module) vs ``json_snapshot`` (``games.jsonc``)."""

		return "mechanical_python"

	def mechanical_finalize_bundle(self, bundle: Dict[str, Any]) -> Dict[str, Any]:
		"""Optional last edit to the bundle dict before write (metadata, extra keys)."""

		return bundle

	def mechanical_collect_archive_rows(
		self,
		profile_dict: Dict[str, Any],
		*,
		patterns: List[str],
		exclude_globs: List[str],
	) -> Optional[List[Tuple[str, Path, Path]]]:
		"""Return ``None`` for default directory walk; else explicit archive rows."""

		return None

	def _prompt_mode(self, pr: Mapping[str, Any]) -> str:
		m = str(pr.get("candidacy") or "").strip()
		if m:
			return m
		m = str(pr.get("when") or "").strip()
		return m or PROMPT_WHEN_NO_CANDIDATE

	def _directory_entry_has_disk_candidate(self, entry: Dict[str, Any]) -> bool:
		paths = [str(x).strip() for x in (entry.get("paths") or []) if str(x).strip()]
		return bool(paths) and any(self._contracted_dir_exists(p) for p in paths)

	def _should_omit_restore_prompt(self, entry: Dict[str, Any], pr: Mapping[str, Any]) -> bool:
		"""True → skip this prompt in :meth:`restore_input_specs` (disk / policy satisfied)."""

		mode = self._prompt_mode(pr)
		if mode == CANDIDACY_ALWAYS:
			return False
		if mode == CANDIDACY_NO_CANDIDATE_THIS_OR_IDS:
			if self._directory_entry_has_disk_candidate(entry):
				return True
			raw_ids = pr.get("candidacy_any_of_ids") or pr.get("or_directory_ids") or []
			if isinstance(raw_ids, str):
				raw_ids = [raw_ids]
			for oid in [str(x).strip() for x in raw_ids if str(x).strip()]:
				for e2 in self.save_sources:
					if str(e2.get("id") or "").strip() != oid:
						continue
					if e2.get("kind") != SAVE_KIND_DIRECTORY:
						continue
					if self._directory_entry_has_disk_candidate(e2):
						return True
			return False
		if mode in (PROMPT_WHEN_NO_CANDIDATE, "no_candidate_exists"):
			return self._directory_entry_has_disk_candidate(entry)
		return False

	def _restore_spec_from_prompt_entry(self, entry: Dict[str, Any], pr: Mapping[str, Any]) -> Optional[RestoreInputSpec]:
		if not isinstance(pr, dict):
			return None
		ik = str(pr.get("input_key") or "").strip()
		msg = str(pr.get("message") or "").strip()
		if not ik or not msg:
			return None
		kind = str(pr.get("input_kind") or "existing_directory").strip()
		ex = str(pr.get("example") or "").strip()
		lb = str(pr.get("label") or "").strip()
		vals = normalize_validations(pr.get("validations"))
		cm = self._prompt_mode(pr)
		raw_ids = pr.get("candidacy_any_of_ids") or pr.get("or_directory_ids") or []
		if isinstance(raw_ids, str):
			raw_ids = [raw_ids]
		c_any = tuple(str(x).strip() for x in raw_ids if str(x).strip())
		return RestoreInputSpec(
			key=ik,
			prompt=msg,
			kind=kind,
			example=ex,
			label=lb,
			validations=vals,
			candidacy=cm,
			candidacy_any_of_ids=c_any,
		)

	def restore_input_specs(self) -> List[RestoreInputSpec]:
		"""Prompts from ``directory`` entries subject to ``prompt.candidacy`` / ``prompt.when``."""

		specs: List[RestoreInputSpec] = []
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			pr = entry.get("prompt")
			if not isinstance(pr, dict):
				continue
			spec = self._restore_spec_from_prompt_entry(entry, pr)
			if spec is None:
				continue
			if self._should_omit_restore_prompt(entry, pr):
				continue
			specs.append(spec)
		return specs

	def restore_input_specs_for_review(self) -> List[RestoreInputSpec]:
		"""Same definitions as :meth:`restore_input_specs`, but ignores on-disk omit rules (GUI review)."""

		specs: List[RestoreInputSpec] = []
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			pr = entry.get("prompt")
			if not isinstance(pr, dict):
				continue
			spec = self._restore_spec_from_prompt_entry(entry, pr)
			if spec is None:
				continue
			specs.append(spec)
		return specs

	def primary_path_editor_hints(self) -> Optional[Tuple[str, str]]:
		"""Optional ``(heading, placeholder)`` for the profile-editor path row from ``save_sources`` prompts."""

		pk_raw = self.profile_primary_input_key()
		pk = pk_raw.strip() if isinstance(pk_raw, str) else ""
		if not pk:
			return None
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			pr = entry.get("prompt")
			if not isinstance(pr, dict):
				continue
			if str(pr.get("input_key") or "").strip() != pk:
				continue
			lb = str(pr.get("editor_label") or "").strip()
			ph = str(pr.get("editor_placeholder") or "").strip()
			if lb and ph:
				return (lb, ph)
		return None

	def profile_primary_input_key(self) -> Optional[str]:
		"""First ``prompt.input_key`` under a ``directory`` entry (persisted as ``plugin_inputs[input_key]``).

		Use the same string as that entry's ``id`` when the profile pins a folder for that root.
		"""

		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			pr = entry.get("prompt")
			if not isinstance(pr, dict):
				continue
			ik = str(pr.get("input_key") or "").strip()
			if ik:
				return ik
		return None

	def profile_restore_input_values(self, profile: GameProfile) -> Dict[str, str]:
		"""Values for ``restore_input_specs`` keys stored on the profile (single primary pin by default)."""

		pk_raw = self.profile_primary_input_key()
		pk = pk_raw.strip() if isinstance(pk_raw, str) else ""
		if not pk:
			return {}
		pi = getattr(profile, "plugin_inputs", None) or {}
		raw = (pi.get(pk) or "").strip()
		return {pk: raw} if raw else {}

	def persist_restore_input_value(self, profile: GameProfile, key: str, value: str) -> None:
		"""Store interactive/GUI values under :attr:`GameProfile.plugin_inputs`."""

		clean = PathUtils.clean_input_path(value or "")
		contracted = PathUtils.contract(clean) if clean else ""
		if contracted:
			profile.plugin_inputs[key] = contracted
		else:
			profile.plugin_inputs.pop(key, None)

	def save_locations_for_profile(self, profile: GameProfile) -> Optional[List[Tuple[str, str]]]:
		"""Derive save roots from ``plugin_inputs`` using ``directory`` ``id`` keys and optional ``pin_relative_segments``."""

		pi = getattr(profile, "plugin_inputs", None) or {}
		out: List[Tuple[str, str]] = []
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			eid = str(entry.get("id") or "").strip() or "path_0"
			raw = (pi.get(eid) or "").strip()
			if not raw:
				continue
			cp = self._contracted_save_root_from_pin_entry(entry, raw)
			if cp:
				out.append((eid, cp))
		return out if out else None

	def bundle_root_overrides_from_restore_inputs(self, inputs: Mapping[str, str]) -> Optional[Dict[str, str]]:
		"""Map bundle ZIP ``sanitized_key`` → contracted save root from stdin/GUI inputs (declarative)."""

		out: Dict[str, str] = {}
		for entry in self.save_sources:
			if entry.get("kind") != SAVE_KIND_DIRECTORY:
				continue
			eid = str(entry.get("id") or "").strip() or "path_0"
			raw = (inputs.get(eid) or "").strip()
			if not raw:
				continue
			cp = self._contracted_save_root_from_pin_entry(entry, raw)
			if not cp:
				continue
			sk = zip_sanitized_key(eid, self)
			out[sk] = cp
		return out if out else None

	def portable_restore(self, ctx: Any) -> None:
		"""Portable extract-and-restore only: optional stdin inputs, then default file + registry prompts."""

		specs = self.restore_input_specs()
		inputs = ctx.collect_restore_inputs(self) if specs else {}
		overrides = self.bundle_root_overrides_from_restore_inputs(inputs) if specs else None
		if overrides:
			ctx.apply_bundle_root_paths(overrides)
		ctx.run_default_file_and_registry()

	def mechanical_after_app_restore(self, info: Dict[str, Any]) -> None:
		"""Called after a successful GUI restore (files + optional registry)."""

		pass

	def to_snapshot_dict(self) -> Dict[str, Any]:
		"""JSON-safe subset embedded in bundle.json (no executable hook code)."""

		return {
			"game_id": self.game_id,
			"version": self.version,
			"_kind": self.plugin_kind,
			"save_sources": list(self.save_sources),
			"file_patterns": list(self.file_patterns),
			"clear_folder_on_restore": self.clear_folder_on_restore,
			"backup_registry_values": bool(self.backup_registry_values),
			"zip_key_aliases": dict(self.zip_key_aliases or {}),
			"backup_exclude_globs": list(self.backup_exclude_globs or []),
		}

	def extra_readme_lines(self) -> List[str]:
		"""Extra lines appended to archive README (short plugin-specific notes)."""

		return []


def plugin_from_json(data: Dict) -> GamePlugin:
	"""Create a simple data-driven plugin from a JSONC-like descriptor.

	Requires ``save_sources`` (list of dicts); see :mod:`BackupSeeker.plugins.save_sources`.
	"""

	class JsonGamePlugin(GamePlugin):
		def __init__(self, d: Dict) -> None:
			self._data = d

		@property
		def plugin_kind(self) -> str:
			return "json_snapshot"

		@property
		def version(self) -> str:
			return str(self._data.get("version", "1.0.0"))

		@property
		def game_id(self) -> str:
			return self._data["id"]

		@property
		def game_name(self) -> str:
			return self._data["name"]

		@property
		def save_sources(self) -> List[Dict[str, Any]]:
			return sources_from_plugin_dict(self._data)

		@property
		def file_patterns(self) -> List[str]:
			return self._data.get("file_patterns", ["*"])

		@property
		def backup_registry_values(self) -> bool:
			return bool(self._data.get("backup_registry_values", False))

		@property
		def zip_key_aliases(self) -> Dict[str, str]:
			raw = self._data.get("zip_key_aliases")
			return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}

		@property
		def backup_exclude_globs(self) -> List[str]:
			raw = self._data.get("backup_exclude_globs")
			return [str(x) for x in raw] if isinstance(raw, list) else []

		@property
		def clear_folder_on_restore(self) -> bool:
			return bool(self._data.get("clear_folder_on_restore", True))

		@property
		def icon(self) -> str:
			return self._data.get("icon", "")

		def extra_readme_lines(self) -> List[str]:
			raw = self._data.get("readme_extra_lines")
			if isinstance(raw, list):
				return [str(x) for x in raw if str(x).strip()]
			return []

	return JsonGamePlugin(data)


def auto_get_plugins():
	"""Auto-discover and return all GamePlugin subclasses in the calling module.
	
	Use in plugin files instead of manually implementing get_plugins():
	
		# In my_game_plugin.py
		class MyGamePlugin(GamePlugin):
			...
		
		# No need for get_plugins() anymore!
		get_plugins = auto_get_plugins
	"""
	frame = inspect.currentframe()
	if frame is None or frame.f_back is None:
		return []
	
	caller_module_name = frame.f_back.f_globals['__name__']
	caller_locals = frame.f_back.f_locals
	
	# Find all GamePlugin subclasses defined in the caller's module
	plugins = [
		cls() for cls in GamePlugin.__subclasses__()
		if cls.__module__ == caller_module_name
	]
	
	return plugins

