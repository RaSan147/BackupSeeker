"""Unified archive metadata from ``bundle.json`` (format version 1 only)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal

from .bundle import read_bundle_from_zip
from .constants import BUNDLE_FORMAT_VERSION
from .format_registry import parse_format

JsonDict = Dict[str, Any]


@dataclass
class ArchiveMetadata:
	"""Normalized view for UI and restore."""

	source: Literal["bundle"]
	format: int
	raw: JsonDict
	created_at: str | None
	profile_id: str
	game_display: str
	plugin_id: str
	plugin_version: str
	keys: List[str]
	logical_keys: Dict[str, str]
	roots: List[JsonDict]
	has_registry_export: bool


def read_archive_metadata(zip_path: Path) -> ArchiveMetadata | None:
	bundle = read_bundle_from_zip(zip_path)
	if bundle is None:
		return None
	return _metadata_from_bundle(bundle)


def _metadata_from_bundle(bundle: JsonDict) -> ArchiveMetadata:
	gm = bundle.get("game") if isinstance(bundle.get("game"), dict) else {}
	display = ""
	if isinstance(gm.get("display_name"), str):
		display = gm.get("display_name") or ""
	pid = ""
	if isinstance(gm.get("plugin_id"), str):
		pid = gm.get("plugin_id") or ""
	pv = ""
	if isinstance(gm.get("plugin_version"), str):
		pv = gm.get("plugin_version") or ""

	lk: Dict[str, str] = {}
	raw_lk = bundle.get("logical_keys")
	if isinstance(raw_lk, dict):
		for sk, logical in raw_lk.items():
			if isinstance(sk, str) and isinstance(logical, str):
				lk[sk] = logical

	keys_raw = bundle.get("keys")
	keys = [str(x) for x in keys_raw] if isinstance(keys_raw, list) else []
	for sk in keys:
		lk.setdefault(sk, sk)

	roots = bundle.get("roots")
	roots_list: List[JsonDict] = [r for r in roots if isinstance(r, dict)] if isinstance(roots, list) else []

	ca = bundle.get("created_at")
	created = ca if isinstance(ca, str) else None
	pi = bundle.get("profile_id")
	prof_id = pi.strip() if isinstance(pi, str) else ""

	reg = bundle.get("registry_export")
	has_reg = isinstance(reg, dict) and bool(reg.get("entries"))

	fmt = parse_format(bundle) or BUNDLE_FORMAT_VERSION

	return ArchiveMetadata(
		source="bundle",
		format=fmt,
		raw=bundle,
		created_at=created,
		profile_id=prof_id,
		game_display=display,
		plugin_id=pid,
		plugin_version=pv,
		keys=keys,
		logical_keys=lk,
		roots=roots_list,
		has_registry_export=has_reg,
	)


def summarize_archive_metadata(meta: ArchiveMetadata | None, *, zip_path: Path) -> Dict[str, str]:
	"""Short strings for backup tables."""

	if meta is None:
		return {
			"status": "invalid",
			"format_display": "?",
			"summary": "No archive metadata",
			"tooltip": str(zip_path.name),
		}

	fmt_display = str(int(meta.format))
	gm_guess = meta.game_display[:40] + ("…" if len(meta.game_display) > 40 else "")
	plugin_id = meta.plugin_id

	n_roots = 0
	n_included = 0
	for r in meta.roots:
		if isinstance(r, dict):
			n_roots += 1
			if r.get("included_in_archive"):
				n_included += 1

	parts: List[str] = []
	if meta.game_display:
		parts.append(gm_guess)
	elif plugin_id:
		parts.append(plugin_id)
	parts.append(f"fmt {fmt_display}")
	if meta.source == "bundle":
		parts.append("bundle")
	if n_roots:
		parts.append(f"{n_included}/{n_roots} roots")
	elif meta.keys:
		parts.append(f"{len(meta.keys)} key(s)")

	summary = " · ".join(parts)
	ca = meta.created_at or ""
	tooltip_lines = [summary, zip_path.name]
	if ca:
		tooltip_lines.insert(1, f"created: {ca}")
	if meta.has_registry_export:
		tooltip_lines.append("includes registry export")

	return {
		"status": "ok",
		"format_display": fmt_display,
		"summary": summary[:120],
		"tooltip": "\n".join(tooltip_lines),
	}
