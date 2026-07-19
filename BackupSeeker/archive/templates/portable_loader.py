#!/usr/bin/env python3
"""Loads embedded mechanical plugins with minimal ``BackupSeeker`` stubs; stdlib only."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _install_minimal_backupseeker_stubs() -> None:
	"""Allow ``from BackupSeeker.plugins.base import GamePlugin, RestoreInputSpec`` inside embedded plugin files."""

	import re as _re

	def _sanitize_location_key(key: str) -> str:
		s = _re.sub(r"[^a-zA-Z0-9_-]+", "_", (key or "").strip())
		s = (s[:64] if len(s) > 64 else s) if s else "loc"
		return s or "loc"

	def _zip_sanitized_key(logical_key: str, plugin=None) -> str:  # noqa: ANN001
		return _sanitize_location_key(logical_key)

	def _flatten_loc(sources):  # noqa: ANN001
		out = []
		for e in sources:
			if e.get("kind") != "directory":
				continue
			eid = str(e.get("id") or "").strip() or "path_0"
			for p in e.get("paths") or []:
				ps = str(p).strip()
				if ps:
					out.append((eid, ps))
		return out

	def _reg_pairs(sources):  # noqa: ANN001
		rp = []
		for e in sources:
			if e.get("kind") != "registry_windows":
				continue
			kp = str(e.get("key_path") or "").strip()
			vn = str(e.get("value_name") or "").strip()
			if kp and vn:
				rp.append((kp, vn))
		return rp

	SAVE_KIND_DIRECTORY = "directory"
	PROMPT_WHEN_NO_CANDIDATE = "no_candidate_exists"

	core = types.ModuleType("BackupSeeker.core")

	class PathUtils:
		_shell_folders_cache = {}

		@classmethod
		def get_windows_shell_folder(cls, name: str, default_fallback: str) -> str:
			import os as _os
			if name in cls._shell_folders_cache:
				return cls._shell_folders_cache[name]

			val = None
			try:
				import winreg as _winreg
				reg_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
				with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, reg_path) as key:
					raw_val, _ = _winreg.QueryValueEx(key, name)
					val = _os.path.expandvars(raw_val)
			except Exception:
				pass

			if not val:
				val = _os.path.expandvars(default_fallback)

			cls._shell_folders_cache[name] = val
			return val

		@classmethod
		def expand(cls, path_str: str):
			import os as _os
			from pathlib import Path as _P
			import platform as _platform
			import re as _re

			if not path_str:
				return _P("")

			if _platform.system() == "Windows":
				norm_path = path_str.replace("\\", "/")
				mappings = [
					(r"^%USERPROFILE%/(?:OneDrive/)?Documents", "Personal", "%USERPROFILE%/Documents"),
					(r"^%USERPROFILE%/(?:OneDrive/)?Saved Games", "{4C5C2F52-7905-46D2-9598-E73F28247014}", "%USERPROFILE%/Saved Games"),
					(r"^%USERPROFILE%/(?:OneDrive/)?Desktop", "Desktop", "%USERPROFILE%/Desktop"),
					(r"^%USERPROFILE%/(?:OneDrive/)?Pictures", "My Pictures", "%USERPROFILE%/Pictures"),
					(r"^%USERPROFILE%/(?:OneDrive/)?Music", "My Music", "%USERPROFILE%/Music"),
					(r"^%USERPROFILE%/(?:OneDrive/)?Videos", "My Video", "%USERPROFILE%/Videos"),
				]
				for pattern, reg_name, fallback in mappings:
					if _re.match(pattern, norm_path, _re.IGNORECASE):
						real_path = cls.get_windows_shell_folder(reg_name, fallback)
						path_str = _re.sub(pattern, real_path.replace("\\", "/"), norm_path, flags=_re.IGNORECASE)
						break

			e = _os.path.expandvars(path_str)
			e = _os.path.expanduser(e)
			return _P(e)

		@staticmethod
		def contract(abs_path: str) -> str:
			import os as _os

			if not abs_path:
				return ""
			return _os.path.abspath(abs_path)

	core.PathUtils = PathUtils
	core.zip_sanitized_key = _zip_sanitized_key

	base_mod = types.ModuleType("BackupSeeker.plugins.base")
	base_mod.SAVE_KIND_DIRECTORY = SAVE_KIND_DIRECTORY
	base_mod.PROMPT_WHEN_NO_CANDIDATE = PROMPT_WHEN_NO_CANDIDATE

	class RestoreInputSpec:
		def __init__(
			self,
			key: str = "",
			prompt: str = "",
			kind: str = "existing_directory",
			example: str = "",
			label: str = "",
			validations=None,
			candidacy: str = "",
			candidacy_any_of_ids=None,
		) -> None:
			self.key = key
			self.prompt = prompt
			self.kind = kind
			self.example = example
			self.label = label
			self.validations = validations or ()
			self.candidacy = candidacy or PROMPT_WHEN_NO_CANDIDATE
			self.candidacy_any_of_ids = tuple(candidacy_any_of_ids or ())

	class GamePlugin:
		@property
		def save_locations(self):  # noqa: ANN001
			return _flatten_loc(self.save_sources)

		@property
		def save_paths(self):  # noqa: ANN001
			return [p for _, p in self.save_locations]

		@property
		def registry_keys(self):  # noqa: ANN001
			return _reg_pairs(self.save_sources)

		def save_detection_groups(self):  # noqa: ANN001
			order = []
			buckets = {}
			for lk, p in self.save_locations:
				s = (p or "").strip()
				if not s:
					continue
				if lk not in buckets:
					order.append(lk)
					buckets[lk] = []
				buckets[lk].append(s)
			return [(k, buckets[k]) for k in order]

		def iter_detection_contracted_paths(self):  # noqa: ANN001
			out = []
			for _, plist in self.save_detection_groups():
				out.extend(plist)
			return out

		def save_candidate_root_exists(self):  # noqa: ANN001
			for contracted in self.iter_detection_contracted_paths():
				try:
					p = PathUtils.expand(contracted)
					if p.exists() and p.is_dir():
						return True
				except Exception:
					continue
			return False

		def restore_input_specs(self):  # noqa: ANN001
			specs = []
			for entry in self.save_sources:
				if entry.get("kind") != SAVE_KIND_DIRECTORY:
					continue
				pr = entry.get("prompt")
				if not isinstance(pr, dict):
					continue
				if str(pr.get("when") or "").strip() != PROMPT_WHEN_NO_CANDIDATE:
					continue
				paths = [str(x).strip() for x in (entry.get("paths") or []) if str(x).strip()]
				ok = False
				for p in paths:
					try:
						x = PathUtils.expand(p)
						if x.exists() and x.is_dir():
							ok = True
							break
					except Exception:
						pass
				if ok:
					continue
				ik = str(pr.get("input_key") or "").strip()
				msg = str(pr.get("message") or "").strip()
				if not ik or not msg:
					continue
				kind = str(pr.get("input_kind") or "existing_directory")
				ex = str(pr.get("example") or "").strip()
				lb = str(pr.get("label") or "").strip()
				specs.append(
					RestoreInputSpec(
						key=ik,
						prompt=msg,
						kind=kind,
						example=ex,
						label=lb,
						validations=(),
						candidacy=PROMPT_WHEN_NO_CANDIDATE,
						candidacy_any_of_ids=(),
					)
				)
			return specs

		def restore_input_specs_for_review(self):  # noqa: ANN001
			specs = []
			for entry in self.save_sources:
				if entry.get("kind") != SAVE_KIND_DIRECTORY:
					continue
				pr = entry.get("prompt")
				if not isinstance(pr, dict):
					continue
				if str(pr.get("when") or "").strip() != PROMPT_WHEN_NO_CANDIDATE:
					continue
				ik = str(pr.get("input_key") or "").strip()
				msg = str(pr.get("message") or "").strip()
				if not ik or not msg:
					continue
				kind = str(pr.get("input_kind") or "existing_directory")
				ex = str(pr.get("example") or "").strip()
				lb = str(pr.get("label") or "").strip()
				specs.append(
					RestoreInputSpec(
						key=ik,
						prompt=msg,
						kind=kind,
						example=ex,
						label=lb,
						validations=(),
						candidacy=PROMPT_WHEN_NO_CANDIDATE,
						candidacy_any_of_ids=(),
					)
				)
			return specs

		def profile_restore_input_values(self, profile):  # noqa: ANN001
			return {}

		def persist_restore_input_value(self, profile, key: str, value: str) -> None:  # noqa: ANN001
			pass

		def save_locations_for_profile(self, profile):  # noqa: ANN001
			return None

		def bundle_root_overrides_from_restore_inputs(self, inputs):  # noqa: ANN001
			return None

		def portable_restore(self, ctx) -> None:  # noqa: ANN001
			specs = self.restore_input_specs()
			inputs = ctx.collect_restore_inputs(self) if specs else {}
			overrides = self.bundle_root_overrides_from_restore_inputs(inputs) if specs else None
			if overrides:
				ctx.apply_bundle_root_paths(overrides)
			ctx.run_default_file_and_registry()

	plugins_pkg = types.ModuleType("BackupSeeker.plugins")
	pkg = types.ModuleType("BackupSeeker")

	pkg.__path__ = []  # type: ignore[attr-defined]
	plugins_pkg.__path__ = []  # type: ignore[attr-defined]

	sys.modules.setdefault("BackupSeeker", pkg)
	sys.modules.setdefault("BackupSeeker.core", core)
	sys.modules.setdefault("BackupSeeker.plugins", plugins_pkg)
	sys.modules.setdefault("BackupSeeker.plugins.base", base_mod)
	base_mod.GamePlugin = GamePlugin
	base_mod.RestoreInputSpec = RestoreInputSpec


def _find_plugin_py(embed_dir: Path) -> Path | None:
	for p in sorted(embed_dir.glob("plugin_*.py")):
		return p
	return None


def _load_plugin_module(embed_dir: Path, py_file: Path) -> object:
	_install_minimal_backupseeker_stubs()
	name = "BackupSeeker.plugins." + py_file.stem
	spec = importlib.util.spec_from_file_location(name, py_file)
	if spec is None or spec.loader is None:
		raise RuntimeError(f"Cannot load {py_file}")
	mod = importlib.util.module_from_spec(spec)
	mod.__package__ = "BackupSeeker.plugins"
	sys.modules[name] = mod
	spec.loader.exec_module(mod)
	return mod


def main() -> int:
	from portable_contract import PortableRestoreContext, load_bundle_from_seeker_dir, run_json_only_restore

	embed_dir = Path(__file__).resolve().parent
	seeker_dir = embed_dir.parent
	backup_root = seeker_dir.parent

	bundle = load_bundle_from_seeker_dir(seeker_dir)
	if bundle is None:
		print(
			"Missing or invalid bundle.json in _backupseeker/.\n"
			"Extract the full backup .zip, then run restore_cli.py.",
			file=sys.stderr,
		)
		return 1

	pl = bundle.get("plugin") if isinstance(bundle.get("plugin"), dict) else {}
	kind = pl.get("_kind", "json_snapshot")

	plugin_py = _find_plugin_py(embed_dir)
	if kind == "mechanical_python" and plugin_py is not None:
		try:
			mod = _load_plugin_module(embed_dir, plugin_py)
		except Exception as ex:
			print(f"Warning: could not load embedded plugin ({ex}); using JSON snapshot restore.", file=sys.stderr)
			run_json_only_restore(bundle, backup_root, embed_dir)
			print("Done.")
			return 0

		get_plugins = getattr(mod, "get_plugins", None)
		if not callable(get_plugins):
			print("Embedded module has no get_plugins(); using default restore.", file=sys.stderr)
			run_json_only_restore(bundle, backup_root, embed_dir)
			print("Done.")
			return 0

		try:
			plugins = get_plugins()
		except Exception as ex:
			print(f"Warning: get_plugins() failed ({ex}); using JSON snapshot restore.", file=sys.stderr)
			run_json_only_restore(bundle, backup_root, embed_dir)
			print("Done.")
			return 0

		if not plugins:
			run_json_only_restore(bundle, backup_root, embed_dir)
			print("Done.")
			return 0

		ctx = PortableRestoreContext(bundle, backup_root, embed_dir)
		try:
			plugins[0].portable_restore(ctx)
		except Exception as ex:
			print(f"portable_restore failed: {ex}", file=sys.stderr)
			return 1
	else:
		run_json_only_restore(bundle, backup_root, embed_dir)

	print()
	print("Done.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
