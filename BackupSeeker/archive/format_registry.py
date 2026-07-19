"""On-disk archive `format` version and optional in-process upgrades.

Archives use ``_backupseeker/bundle.json`` with ``format`` **1** — the only value
this build reads or writes.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

JsonDict = Dict[str, Any]

# Only this format is accepted for restore and metadata.
CURRENT_ARCHIVE_FORMAT: int = 1

# Optional labels for diagnostics or UI (not a changelog).
FORMAT_NOTES: Dict[int, str] = {
	1: "Keyed backup bundle (``_backupseeker/bundle.json``).",
}

# When a newer format is introduced: map source ``format`` -> callable(bundle) -> bundle.
UPGRADERS: Dict[int, Callable[[JsonDict], JsonDict]] = {}


class UnsupportedArchiveFormat(ValueError):
	"""Raised when ``bundle.json`` has a ``format`` other than :data:`CURRENT_ARCHIVE_FORMAT`."""

	def __init__(self, found: int, path: str = "") -> None:
		self.found = found
		self.path = path
		msg = f"Unsupported archive format {found!r} (only {CURRENT_ARCHIVE_FORMAT} is supported)"
		if path:
			msg = f"{msg}: {path}"
		super().__init__(msg)


def parse_format(bundle: Any) -> int:
	"""Return ``format`` from a bundle dict, or 0 if missing/invalid."""

	if not isinstance(bundle, dict):
		return 0
	f = bundle.get("format")
	if isinstance(f, int) and f > 0:
		return f
	if isinstance(f, str) and f.isdigit():
		return int(f)
	return 0


def assert_bundle_supported(bundle: JsonDict, *, path: str = "") -> None:
	"""Require :data:`CURRENT_ARCHIVE_FORMAT` for restore and UI metadata."""

	n = parse_format(bundle)
	if n != CURRENT_ARCHIVE_FORMAT:
		raise UnsupportedArchiveFormat(n, path=path)
