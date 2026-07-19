"""Stdlib-only portable restore API (copied into each backup archive under ``_backupseeker/embed/``).

``PortableRestoreContext`` exposes the default file-copy + registry pipeline. Mechanical
(``.py``) plugins can wrap or replace it via ``GamePlugin.portable_restore(ctx)``.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

BUNDLE_FORMAT = 1


def _strip_wrapping_quotes(s: str) -> str:
	t = (s or "").strip()
	if len(t) >= 2 and ((t[0] == t[-1] == '"') or (t[0] == t[-1] == "'")):
		return t[1:-1].strip()
	return t


def expand_contracted(path_str: str) -> Path:
	if not path_str:
		return Path("")
	expanded = os.path.expandvars(path_str)
	expanded = os.path.expanduser(expanded)
	return Path(expanded)


def is_safe_relative_path(rel_posix: str) -> bool:
	if not rel_posix or rel_posix.startswith(("/", "\\")):
		return False
	for seg in Path(rel_posix.replace("\\", "/").replace("/", os.sep)).parts:
		if seg == "..":
			return False
	if os.name == "nt":
		parts = rel_posix.replace("\\", "/").split("/", 1)
		if parts and len(parts[0]) == 2 and parts[0][1] == ":":
			return False
	return True


def roots_from_bundle(bundle: dict[str, Any]) -> dict[str, str]:
	out: dict[str, str] = {}
	for r in bundle.get("roots") or []:
		if not isinstance(r, dict):
			continue
		sk = r.get("sanitized_key")
		cp = r.get("contracted_save_path")
		if isinstance(sk, str) and isinstance(cp, str) and cp.strip():
			out[sk] = cp.strip()
	for sk in bundle.get("keys") or []:
		if not isinstance(sk, str) or sk in out:
			continue
		for r in bundle.get("roots") or []:
			if isinstance(r, dict) and r.get("sanitized_key") == sk:
				cp = r.get("contracted_save_path")
				if isinstance(cp, str) and cp.strip():
					out[sk] = cp.strip()
					break
	return out


def prompt_yes(question: str) -> bool:
	try:
		return input(question).strip().lower() in ("y", "yes")
	except EOFError:
		return False


def restore_registry(bundle: dict[str, Any]) -> None:
	reg = bundle.get("registry_export")
	if not isinstance(reg, dict):
		return
	try:
		import winreg  # type: ignore
	except ImportError:
		print("Registry restore requires Windows.", file=sys.stderr)
		return

	entries = reg.get("entries")
	if not isinstance(entries, list):
		return

	for item in entries:
		if not isinstance(item, dict):
			continue
		hive_s = item.get("hive")
		subkey = item.get("subkey")
		val_name = item.get("value_name")
		win_type = item.get("win_type")
		val_data = item.get("data")
		if (
			not isinstance(hive_s, str)
			or not isinstance(subkey, str)
			or not isinstance(val_name, str)
			or win_type not in ("REG_SZ", "REG_EXPAND_SZ", "REG_DWORD")
		):
			continue
		hkey = getattr(winreg, hive_s, None)
		if hkey is None:
			continue
		try:
			with winreg.CreateKeyEx(hkey, subkey, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
				if win_type == "REG_DWORD" and isinstance(val_data, int):
					winreg.SetValueEx(key, val_name, 0, winreg.REG_DWORD, val_data)
				elif isinstance(val_data, str):
					reg_t = winreg.REG_EXPAND_SZ if win_type == "REG_EXPAND_SZ" else winreg.REG_SZ
					winreg.SetValueEx(key, val_name, 0, reg_t, val_data)
		except OSError as e:
			print(f"warning: registry write failed ({subkey}\\{val_name}): {e}", file=sys.stderr)


class PortableRestoreContext:
	"""Bundled restore: JSON snapshot uses only this class; mechanical plugins receive it for customization."""

	def __init__(self, bundle: dict[str, Any], backup_root: Path, embed_dir: Path) -> None:
		self.bundle = bundle
		self.backup_root = backup_root
		self.embed_dir = embed_dir

	def collect_restore_inputs(self, plugin: Any) -> dict[str, str]:
		"""Prompt for ``plugin.restore_input_specs()`` via stdin (no CLI args)."""

		try:
			from BackupSeeker.plugins.prompt_validation import validate_restore_input
		except ImportError:

			def validate_restore_input(kind: str, raw: str, validations):  # noqa: ANN001
				vals = {str(v).strip().lower() for v in (validations or ()) if str(v).strip()}
				s = (raw or "").strip()
				if "optional" in vals and not s:
					return True, ""
				if ("must" in vals or "required" in vals) and not s:
					return False, "Required."
				if (kind or "") == "existing_directory":
					if not s:
						return False, "Enter a folder path."
					candidate = Path(s)
					if not candidate.is_dir():
						return False, "Not an existing folder."
				return True, ""

		specs_fn = getattr(plugin, "restore_input_specs", None)
		specs = specs_fn() if callable(specs_fn) else []
		if not specs:
			return {}
		out: dict[str, str] = {}
		for spec in specs:
			key = getattr(spec, "key", "") or ""
			prompt = getattr(spec, "prompt", "") or ""
			kind = getattr(spec, "kind", "existing_directory") or "existing_directory"
			example = getattr(spec, "example", "") or ""
			vals = tuple(getattr(spec, "validations", ()) or ())
			if not key:
				continue
			while True:
				try:
					msg = prompt
					ex = example.strip() if isinstance(example, str) else ""
					if ex:
						msg = f"{prompt}\n(e.g. {ex})" if prompt.strip() else f"(e.g. {ex})"
					raw = input(f"{msg}\n> ")
				except EOFError:
					raw = ""
				line = _strip_wrapping_quotes(raw)
				ok, err = validate_restore_input(str(kind), line, vals)
				if ok:
					out[key] = line
					break
				print(err or "Invalid input.", file=sys.stderr)
		return out

	def apply_bundle_root_paths(self, overrides: dict[str, str]) -> None:
		"""Replace ``contracted_save_path`` on bundle roots whose ``sanitized_key`` is in ``overrides``."""

		if not overrides:
			return
		roots = self.bundle.get("roots")
		if not isinstance(roots, list):
			return
		for r in roots:
			if not isinstance(r, dict):
				continue
			sk = r.get("sanitized_key")
			if not isinstance(sk, str) or sk not in overrides:
				continue
			cp = overrides[sk]
			if isinstance(cp, str) and cp.strip():
				r["contracted_save_path"] = cp.strip()

	def run_default_file_and_registry(self) -> None:
		"""Standard pipeline: prompt per root, copy trees, optional registry."""

		pl = self.bundle.get("plugin") if isinstance(self.bundle.get("plugin"), dict) else {}
		clear_first = bool(pl.get("clear_folder_on_restore", True))

		key_to_contracted = roots_from_bundle(self.bundle)
		if not key_to_contracted:
			print("Bundle has no save roots.", file=sys.stderr)
			return

		gm = self.bundle.get("game") if isinstance(self.bundle.get("game"), dict) else {}
		title = gm.get("display_name") if isinstance(gm.get("display_name"), str) else "backup"
		print(f"BackupSeeker portable restore — {title}")
		print(f"Backup folder: {self.backup_root}")
		print()

		for sk, contracted in sorted(key_to_contracted.items()):
			dest = expand_contracted(contracted)
			src_dir = self.backup_root / sk
			if not src_dir.is_dir():
				print(f"[{sk}] skip — folder not in archive: {sk}/")
				continue

			if dest.exists() and any(dest.iterdir()):
				if not prompt_yes(
					f"[{sk}] Destination already contains data:\n  {dest}\n"
					f"Overwrite existing files there? [y/N]: "
				):
					print(f"[{sk}] skipped.")
					continue

			if clear_first and dest.exists():
				shutil.rmtree(dest)
			dest.mkdir(parents=True, exist_ok=True)

			n = 0
			for dirpath, _, filenames in os.walk(src_dir):
				for fn in filenames:
					full = Path(dirpath) / fn
					try:
						rel = full.relative_to(src_dir).as_posix()
					except ValueError:
						continue
					if not is_safe_relative_path(rel):
						print(f"warning: skipped unsafe path {rel}")
						continue
					out_path = dest / rel.replace("/", os.sep)
					out_path.parent.mkdir(parents=True, exist_ok=True)
					shutil.copy2(full, out_path)
					n += 1
			print(f"[{sk}] restored {n} file(s) -> {dest}")

		reg = self.bundle.get("registry_export")
		if isinstance(reg, dict) and reg.get("entries") and sys.platform.startswith("win"):
			print()
			if prompt_yes("Apply exported registry values from this backup? [y/N]: "):
				restore_registry(self.bundle)


def load_bundle_from_seeker_dir(seeker_dir: Path) -> dict[str, Any] | None:
	p = seeker_dir / "bundle.json"
	if not p.is_file():
		return None
	try:
		data = json.loads(p.read_text(encoding="utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError):
		return None
	if not (isinstance(data, dict) and data.get("format") == BUNDLE_FORMAT):
		return None
	return data


def run_json_only_restore(bundle: dict[str, Any], backup_root: Path, embed_dir: Path) -> None:
	PortableRestoreContext(bundle, backup_root, embed_dir).run_default_file_and_registry()
