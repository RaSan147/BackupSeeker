"""Rebuild backup ``.zip`` archives with current portable CLI, embed runtime, and embedded plugin sources."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .bundle import is_valid_bundle_dict
from .constants import (
	BACKUP_BUNDLE_PATH,
	MAX_BUNDLE_JSON_BYTES,
	PORTABLE_CONTRACT_EMBED_PATH,
	PORTABLE_LOADER_EMBED_PATH,
	RESTORE_CLI_PATH,
	ZIP_README_PATH,
)
from .packaging import (
	build_archive_readme,
	build_restore_cli_script,
	embedded_plugin_arc_path,
	read_portable_embed_sources,
)

logger = logging.getLogger(__name__)


@dataclass
class ZipUpgradeResult:
	path: Path
	action: str  # "skipped" | "updated" | "error"
	detail: str = ""


def _discover_pkg_root(explicit: Optional[Path]) -> Path:
	if explicit is not None:
		p = explicit.resolve()
		if (p / "BackupSeeker" / "archive" / "packaging.py").is_file():
			return p
		raise FileNotFoundError(f"Not a BackupSeeker repo root: {p}")
	here = Path.cwd()
	for base in [here, *here.parents]:
		if (base / "BackupSeeker" / "archive" / "packaging.py").is_file():
			return base
	raise FileNotFoundError("Could not find BackupSeeker package (pass --pkg-root).")


def _extra_readme_from_bundle(data: Dict[str, Any]) -> Optional[List[str]]:
	pl = data.get("plugin")
	if not isinstance(pl, dict):
		return None
	raw = pl.get("extra_readme_lines")
	if isinstance(raw, list) and raw:
		return [str(x).strip() for x in raw if str(x).strip()]
	return None


def upgrade_backup_zip(
	path: Path,
	*,
	pkg_root: Path,
	dry_run: bool = False,
) -> ZipUpgradeResult:
	"""Rewrite ``_backupseeker/*`` from the live tree and re-embed plugin ``.py`` from repo.

	Preserves all ZIP members outside ``_backupseeker/`` (save folders). Bundle JSON is not
	transformed; archives must already use ``plugin.save_sources`` (format 1).
	"""

	p = path.resolve()
	if not p.is_file():
		return ZipUpgradeResult(p, "error", "not a file")
	if p.suffix.lower() != ".zip":
		return ZipUpgradeResult(p, "skipped", "not a .zip")

	try:
		with zipfile.ZipFile(p, "r") as zin:
			try:
				bi = zin.getinfo(BACKUP_BUNDLE_PATH)
			except KeyError:
				return ZipUpgradeResult(p, "skipped", "no " + BACKUP_BUNDLE_PATH)
			if bi.file_size > MAX_BUNDLE_JSON_BYTES or bi.file_size < 2:
				return ZipUpgradeResult(p, "error", "bundle.json size out of bounds")
			raw = zin.read(BACKUP_BUNDLE_PATH)
			preserve_infos = [
				zi
				for zi in zin.infolist()
				if not zi.filename.endswith("/") and not zi.filename.startswith("_backupseeker/")
			]
	except (zipfile.BadZipFile, OSError) as ex:
		return ZipUpgradeResult(p, "error", str(ex))

	try:
		data = json.loads(raw.decode("utf-8"))
	except (UnicodeDecodeError, json.JSONDecodeError) as ex:
		return ZipUpgradeResult(p, "error", f"bundle JSON: {ex}")

	if not isinstance(data, dict) or not is_valid_bundle_dict(data):
		return ZipUpgradeResult(p, "skipped", "invalid bundle (need format 1 + plugin.save_sources)")

	pl_snap = data.get("plugin") if isinstance(data.get("plugin"), dict) else {}
	gm = data.get("game") if isinstance(data.get("game"), dict) else {}

	gid = ""
	if pl_snap:
		gid = str(pl_snap.get("game_id") or "").strip()
	if not gid:
		gid = str(gm.get("plugin_id") or "").strip()

	kind = str(pl_snap.get("_kind") or pl_snap.get("plugin_kind") or "").strip()

	plugins_dir = pkg_root / "BackupSeeker" / "plugins"
	embed_arcname: Optional[str] = None
	embed_py_source: Optional[str] = None
	if kind == "mechanical_python" and gid:
		pp = plugins_dir / f"{gid}.py"
		if pp.is_file():
			try:
				embed_py_source = pp.read_text(encoding="utf-8")
				embed_arcname = embedded_plugin_arc_path(gid)
			except OSError as ex:
				return ZipUpgradeResult(p, "error", f"read plugin {pp}: {ex}")

	reg = data.get("registry_export")
	has_registry = isinstance(reg, dict) and bool(reg.get("entries"))

	try:
		pc_text, pl_text = read_portable_embed_sources()
	except OSError as ex:
		return ZipUpgradeResult(p, "error", f"read embed sources: {ex}")

	cli_src = build_restore_cli_script(
		embedded_plugin_arcname=embed_arcname,
		has_registry_export=has_registry,
	)
	readme_text = build_archive_readme(data, extra_lines=_extra_readme_from_bundle(data))
	out_bundle = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

	if dry_run:
		return ZipUpgradeResult(p, "updated", "would rewrite _backupseeker + bundle + plugin embed")

	tmp: Optional[Path] = None
	try:
		nf = tempfile.NamedTemporaryFile(delete=False, suffix=".zip", dir=p.parent)
		nf.close()
		tmp = Path(nf.name)
	except OSError as ex:
		return ZipUpgradeResult(p, "error", f"temp file: {ex}")

	try:
		with zipfile.ZipFile(p, "r") as zin, zipfile.ZipFile(
			tmp,
			"w",
			compression=zipfile.ZIP_DEFLATED,
			strict_timestamps=False,
		) as zout:
			zout.writestr(BACKUP_BUNDLE_PATH, out_bundle)
			zout.writestr(ZIP_README_PATH, readme_text.encode("utf-8"))
			zout.writestr(RESTORE_CLI_PATH, cli_src.encode("utf-8"))
			zout.writestr(PORTABLE_CONTRACT_EMBED_PATH, pc_text.encode("utf-8"))
			zout.writestr(PORTABLE_LOADER_EMBED_PATH, pl_text.encode("utf-8"))
			if embed_arcname and embed_py_source is not None:
				zout.writestr(embed_arcname, embed_py_source.encode("utf-8"))

			for zi in preserve_infos:
				with zin.open(zi) as rf:
					zout.writestr(zi, rf.read())
	except Exception as ex:
		logger.exception("Failed rebuilding %s", p)
		if tmp is not None and tmp.exists():
			tmp.unlink(missing_ok=True)
		return ZipUpgradeResult(p, "error", str(ex))

	try:
		tmp.replace(p)
	except OSError as ex:
		if tmp.exists():
			tmp.unlink(missing_ok=True)
		return ZipUpgradeResult(p, "error", f"replace: {ex}")

	detail_parts = ["portable CLI + embed", "bundle rewritten (same content, canonical JSON)"]
	if embed_arcname:
		detail_parts.append(f"plugin {gid}")
	return ZipUpgradeResult(p, "updated", "; ".join(detail_parts))


def upgrade_zip_tree(root: Path, *, pkg_root: Path, dry_run: bool = False) -> List[ZipUpgradeResult]:
	out: List[ZipUpgradeResult] = []
	for zp in sorted(root.rglob("*.zip")):
		out.append(upgrade_backup_zip(zp, pkg_root=pkg_root, dry_run=dry_run))
	return out


def main(argv: Optional[List[str]] = None) -> int:
	logging.basicConfig(level=logging.INFO)
	ap = argparse.ArgumentParser(
		description="Upgrade BackupSeeker backup ZIPs: latest restore_cli.py, embed/, re-embedded plugin .py from repo.",
	)
	ap.add_argument(
		"paths",
		nargs="*",
		type=Path,
		help="ZIP files or directories (default: ./backups if it exists)",
	)
	ap.add_argument("--pkg-root", type=Path, default=None, help="Repo root containing BackupSeeker/ (auto-detected).")
	ap.add_argument("--dry-run", action="store_true", help="Report actions without writing.")
	ns = ap.parse_args(argv)

	try:
		pkg_root = _discover_pkg_root(ns.pkg_root)
	except FileNotFoundError as e:
		print(str(e), file=sys.stderr)
		return 2

	targets: List[Path] = []
	if ns.paths:
		targets.extend(ns.paths)
	else:
		for name in ("backups", "Backups"):
			candidate = Path.cwd() / name
			if candidate.is_dir():
				targets.append(candidate)
				break
		else:
			print("No backups/ folder; pass zip paths or directories.", file=sys.stderr)
			return 2

	results: List[ZipUpgradeResult] = []
	for t in targets:
		t = t.resolve()
		if t.is_file() and t.suffix.lower() == ".zip":
			results.append(upgrade_backup_zip(t, pkg_root=pkg_root, dry_run=ns.dry_run))
		elif t.is_dir():
			results.extend(upgrade_zip_tree(t, pkg_root=pkg_root, dry_run=ns.dry_run))
		else:
			print(f"Skip (not zip/dir): {t}", file=sys.stderr)

	for r in results:
		print(f"{r.action:10} {r.path}")
		if r.detail:
			print(f"           {r.detail}")

	errs = [r for r in results if r.action == "error"]
	return 1 if errs else 0


if __name__ == "__main__":
	raise SystemExit(main())
