from __future__ import annotations

"""Thin launcher: embedded body is prefixed at zip build time."""


import sys
from pathlib import Path


def main() -> int:
	embed = Path(__file__).resolve().parent / "embed"
	sys.path.insert(0, str(embed))
	from portable_loader import main as loader_main  # noqa: PLC0415

	return loader_main()


if __name__ == "__main__":
	raise SystemExit(main())
