"""Validate user input for declarative ``prompt.validations`` on ``save_sources`` directory entries."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Sequence, Tuple

from ..core import PathUtils


def normalize_validations(raw: Any) -> Tuple[str, ...]:
	"""Normalize ``prompt.validations`` from string, comma-string, or list into lowercase tags."""

	if raw is None:
		return ()
	if isinstance(raw, str):
		t = raw.strip()
		if not t:
			return ()
		parts = [p.strip().lower() for p in t.replace(",", " ").split() if p.strip()]
		return tuple(dict.fromkeys(parts))
	if isinstance(raw, (list, tuple)):
		out: list[str] = []
		for x in raw:
			s = str(x).strip().lower()
			if s:
				out.append(s)
		return tuple(dict.fromkeys(out))
	return ()


def validate_restore_input(kind: str, raw: str, validations: Sequence[str]) -> Tuple[bool, str]:
	"""Return ``(ok, error_message)``. Empty ``error_message`` means success with nothing to show."""

	vals = {str(v).strip().lower() for v in validations if str(v).strip()}
	s = (raw or "").strip()

	optional = "optional" in vals
	must = ("must" in vals) or ("required" in vals)

	if optional and not s:
		return True, ""

	if must and not s:
		return False, "This field is required."

	if kind == "existing_directory":
		if not s:
			return False, "Enter an existing folder path."
		try:
			clean = PathUtils.clean_input_path(s)
			if not clean:
				return False, "Enter an existing folder path."
			exp = PathUtils.expand(clean)
		except (OSError, ValueError, KeyError):
			return False, "Could not resolve that path."
		try:
			if not exp.is_dir():
				return False, "That path is not an existing folder."
		except OSError:
			return False, "Could not access that folder."
		return True, ""

	if not s:
		return True, ""

	type_tags = [t for t in ("int", "decimal", "string") if t in vals]
	if "int" in type_tags:
		try:
			int(s, 10)
		except ValueError:
			return False, "Enter a whole number (integer)."
	elif "decimal" in type_tags:
		try:
			Decimal(s.replace(",", "."))
		except (InvalidOperation, ValueError):
			return False, "Enter a decimal number."
	elif "string" in type_tags:
		pass

	return True, ""
