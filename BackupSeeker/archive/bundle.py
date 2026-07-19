"""Canonical ``bundle.json`` schema (archive format version 1)."""

from __future__ import annotations

import json
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .constants import (
	BACKUP_BUNDLE_PATH,
	BUNDLE_FORMAT_VERSION,
	MAX_BUNDLE_JSON_BYTES,
)

JsonDict = Dict[str, Any]


def build_bundle(
	*,
	created_at: str,
	profile_id: str,
	display_name: str,
	plugin_id: str,
	plugin_version: str,
	file_patterns: List[str],
	manifest_keys: List[str],
	logical_keys_map: Dict[str, str],
	roots: List[JsonDict],
	plugin_snapshot: JsonDict,
	registry_export: JsonDict | None,
	app_extra: JsonDict | None = None,
) -> JsonDict:
	"""Assemble the bundle.json body for archive format version 1."""

	body: JsonDict = {
		"format": BUNDLE_FORMAT_VERSION,
		"created_at": created_at,
		"profile_id": (profile_id or "").strip(),
		"game": {
			"display_name": display_name,
			"plugin_id": (plugin_id or "").strip(),
			"plugin_version": (plugin_version or "").strip(),
		},
		"file_patterns": list(file_patterns),
		"keys": sorted(set(manifest_keys)),
		"logical_keys": dict(logical_keys_map),
		"roots": roots,
		"plugin": plugin_snapshot,
		"app": {"name": "BackupSeeker", "bundle_format": BUNDLE_FORMAT_VERSION},
	}
	if registry_export is not None:
		body["registry_export"] = registry_export
	if app_extra:
		body["app"] = {**body["app"], **app_extra}
	return body


def is_valid_bundle_dict(data: JsonDict | None) -> bool:
	if not isinstance(data, dict):
		return False
	fmt = data.get("format")
	if fmt != BUNDLE_FORMAT_VERSION:
		return False
	keys = data.get("keys")
	if not isinstance(keys, list) or not keys or not all(isinstance(x, str) for x in keys):
		return False
	lk = data.get("logical_keys")
	if lk is not None and (
		not isinstance(lk, dict) or not all(isinstance(k, str) for k in lk.keys())
	):
		return False
	pl = data.get("plugin")
	if not isinstance(pl, dict):
		return False
	ss = pl.get("save_sources")
	if not isinstance(ss, list) or not ss:
		return False
	return True


def read_bundle_from_zip(
	zip_path: Path,
	*,
	max_bytes: int = MAX_BUNDLE_JSON_BYTES,
) -> JsonDict | None:
	try:
		with zipfile.ZipFile(zip_path, "r") as zf:
			try:
				info = zf.getinfo(BACKUP_BUNDLE_PATH)
			except KeyError:
				return None
			if info.file_size > max_bytes or info.file_size < 2:
				logging.warning("Bundle in %s: size %s out of bounds", zip_path, info.file_size)
				return None
			raw = zf.read(BACKUP_BUNDLE_PATH)
	except (zipfile.BadZipFile, OSError) as ex:
		logging.debug("Cannot read bundle from %s: %s", zip_path, ex)
		return None

	try:
		data = json.loads(raw.decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError) as ex:
		logging.debug("Invalid bundle JSON in %s: %s", zip_path, ex)
		return None

	if not isinstance(data, dict) or not is_valid_bundle_dict(data):
		return None
	return data


def logical_keys_from_bundle(bundle: JsonDict) -> Dict[str, str]:
	"""sanitized_key -> logical_key."""

	out: Dict[str, str] = {}
	lk = bundle.get("logical_keys")
	if isinstance(lk, dict):
		for sk, logical in lk.items():
			if isinstance(sk, str) and isinstance(logical, str):
				out[sk] = logical
	for sk in bundle.get("keys") or []:
		if isinstance(sk, str) and sk not in out:
			out[sk] = sk
	return out


def bundle_roots_contracted(bundle: JsonDict) -> List[Tuple[str, str]]:
	"""Pairs (sanitized_key, contracted_save_path) from bundle roots[]."""

	out: List[Tuple[str, str]] = []
	roots = bundle.get("roots")
	if not isinstance(roots, list):
		return out
	for r in roots:
		if not isinstance(r, dict):
			continue
		sk = r.get("sanitized_key")
		cp = r.get("contracted_save_path")
		if isinstance(sk, str) and isinstance(cp, str) and cp.strip():
			out.append((sk, cp.strip()))
	return out
