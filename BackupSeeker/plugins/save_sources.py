"""Declarative ``save_sources`` schema for :class:`~BackupSeeker.plugins.base.GamePlugin`.

Each entry is a JSON-serializable dict: directory roots (with alternatives), optional
prompts when no path exists, and Windows registry probes for detection.
For a ``directory`` entry, optional ``pin_relative_segments`` names path segments
appended to the user-pinned folder (same ``id`` as ``prompt.input_key``) to form the
actual save root (e.g. install folder + ``["storage","SKIDROW","4"]``).
For a ``directory`` entry, the ``prompt`` object may include ``example`` (a sample
path string) shown next to the main ``message`` in the GUI and portable stdin flow.
Optional ``editor_label`` / ``editor_placeholder`` customize the profile-editor path row.

``prompt.validations``: list (or comma-separated string) of tags —
``must`` / ``required``, ``optional``, ``string``, ``int``, ``decimal``
(applied after ``input_kind``, e.g. folder path vs text).

``prompt.candidacy`` (defaults with ``prompt.when``): ``no_candidate_exists`` (skip prompt if any
local ``paths`` exists), ``no_candidate_this_or_ids`` (skip if this entry **or**
``candidacy_any_of_ids`` has a candidate), ``always`` (never skip—always prompt until filled).

``prompt.candidacy_any_of_ids``: list of other ``directory`` ``id`` values for OR semantics.

Bundle snapshots embed ``save_sources`` only (no legacy ``save_locations`` / ``registry_keys`` keys).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

SAVE_KIND_DIRECTORY = "directory"
SAVE_KIND_REGISTRY_WINDOWS = "registry_windows"

PROMPT_WHEN_NO_CANDIDATE = "no_candidate_exists"
CANDIDACY_NO_CANDIDATE_THIS_OR_IDS = "no_candidate_this_or_ids"
CANDIDACY_ALWAYS = "always"


def flatten_locations_from_sources(sources: Sequence[Dict[str, Any]]) -> List[Tuple[str, str]]:
	"""Expand ``directory`` entries to ``(id, contracted_path)`` rows (alternatives repeat ``id``)."""

	out: List[Tuple[str, str]] = []
	for entry in sources:
		if entry.get("kind") != SAVE_KIND_DIRECTORY:
			continue
		eid = str(entry.get("id") or "").strip() or "path_0"
		for p in entry.get("paths") or []:
			ps = str(p).strip()
			if ps:
				out.append((eid, ps))
	return out


def flatten_paths_from_sources(sources: Sequence[Dict[str, Any]]) -> List[str]:
	return [p for _, p in flatten_locations_from_sources(sources)]


def registry_pairs_from_sources(sources: Sequence[Dict[str, Any]]) -> List[Tuple[str, str]]:
	out: List[Tuple[str, str]] = []
	for entry in sources:
		if entry.get("kind") != SAVE_KIND_REGISTRY_WINDOWS:
			continue
		kp = str(entry.get("key_path") or "").strip()
		vn = str(entry.get("value_name") or "").strip()
		if kp and vn:
			out.append((kp, vn))
	return out


def sources_from_plugin_dict(data: Dict[str, Any]) -> List[Dict[str, Any]]:
	"""Normalize JSON(C) ``save_sources`` into validated entries."""

	raw = data.get("save_sources")
	if not isinstance(raw, list) or not raw:
		return []
	return [_normalize_source_entry(e) for e in raw if isinstance(e, dict)]


def _normalize_source_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
	kind = str(entry.get("kind") or SAVE_KIND_DIRECTORY).strip() or SAVE_KIND_DIRECTORY
	base: Dict[str, Any] = {"kind": kind}
	eid = str(entry.get("id") or "").strip()
	if eid:
		base["id"] = eid
	if kind == SAVE_KIND_DIRECTORY:
		paths = entry.get("paths")
		if isinstance(paths, list):
			base["paths"] = [str(x).strip() for x in paths if str(x).strip()]
		else:
			base["paths"] = []
		pr_seg = entry.get("pin_relative_segments")
		if isinstance(pr_seg, list) and pr_seg:
			base["pin_relative_segments"] = [str(x).strip() for x in pr_seg if str(x).strip()]
		if "optional" in entry:
			base["optional"] = bool(entry["optional"])
		pr = entry.get("prompt")
		if isinstance(pr, dict) and pr:
			base["prompt"] = dict(pr)
	elif kind == SAVE_KIND_REGISTRY_WINDOWS:
		base["key_path"] = str(entry.get("key_path") or "").strip()
		base["value_name"] = str(entry.get("value_name") or "").strip()
	return base

