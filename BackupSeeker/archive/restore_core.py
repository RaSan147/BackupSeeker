"""Pure helpers shared by core restore and the embedded CLI (keep CLI copy in sync)."""

from __future__ import annotations

import os
from pathlib import Path


def is_safe_zip_member_rest(rest: str) -> bool:
	"""Reject ZIP slip / absolute paths for the path after ``sanitized_key/``."""

	if not rest:
		return False
	rest_norm = rest.replace("\\", "/").strip()
	if rest_norm.startswith("/"):
		return False
	first = rest_norm.split("/", 1)[0]
	if os.name == "nt" and len(first) == 2 and first[1] == ":":
		return False
	for seg in Path(rest_norm.replace("/", os.sep)).parts:
		if seg == "..":
			return False
	return True
