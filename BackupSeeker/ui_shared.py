"""Shared UI helpers for BackupSeeker."""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, Union

from .plugins.base import GamePlugin, RestoreInputSpec
from .plugins.prompt_validation import validate_restore_input

if TYPE_CHECKING:
	from .core import ConfigManager, GameProfile

_DEFAULT_ENSURE_MSG = "Select folder."
_DEFAULT_RETRY_MSG = "Fix path below."
_DEFAULT_FIELD_PLACEHOLDER = "Paste or browse…"
_DEFAULT_BROWSE_DIALOG_TITLE = "Select folder"
_DEFAULT_LINE_EDIT_PLACEHOLDER = "Browse or paste…"

_PLUGIN_INPUT_DIALOG_QSS_ID = "PluginInputDialog"
_PLUGIN_INPUT_EXAMPLE_LABEL_ID = "PluginInputExampleLabel"


def _plugin_input_dialog_stylesheet() -> str:
	"""QSS aligned with Fluent ``AdaptiveThemeStyles`` so the modal matches dark/light."""

	from .ui_helpers import is_app_dark

	dark = is_app_dark()
	if dark:
		panel_bg = "rgba(0, 0, 0, 0.64)"
		panel_border = "rgba(255, 255, 255, 0.12)"
		text_primary = "#f3f3f3"
		text_muted = "#b8b8b8"
		input_bg = "rgba(0, 0, 0, 0.76)"
		input_border = "rgba(255, 255, 255, 0.14)"
		btn_bg = "rgba(255, 255, 255, 0.08)"
		btn_hover = "rgba(255, 255, 255, 0.14)"
		sel_bg = "rgba(0, 120, 215, 0.48)"
		sel_text = "#ffffff"
	else:
		panel_bg = "rgba(255, 255, 255, 0.86)"
		panel_border = "rgba(0, 0, 0, 0.16)"
		text_primary = "#1f1f1f"
		text_muted = "#5f5f5f"
		input_bg = "rgba(255, 255, 255, 0.92)"
		input_border = "rgba(0, 0, 0, 0.14)"
		btn_bg = "rgba(0, 0, 0, 0.06)"
		btn_hover = "rgba(0, 0, 0, 0.10)"
		sel_bg = "rgba(0, 120, 215, 0.22)"
		sel_text = "#111111"

	oid = _PLUGIN_INPUT_DIALOG_QSS_ID
	ex_id = _PLUGIN_INPUT_EXAMPLE_LABEL_ID
	return (
		f"QDialog#{oid} {{"
		f"background-color: {panel_bg};"
		f"color: {text_primary};"
		f"border: 1px solid {panel_border};"
		f"border-radius: 8px;"
		"}"
		f"QDialog#{oid} QWidget {{ background: transparent; }}"
		f"QDialog#{oid} QLabel {{ color: {text_primary}; }}"
		f"QDialog#{oid} QLabel#{ex_id} {{ color: {text_muted}; }}"
		f"QDialog#{oid} QLineEdit {{"
		f"background-color: {input_bg};"
		f"color: {text_primary};"
		f"border: 1px solid {input_border};"
		"border-radius: 4px;"
		"padding: 4px 8px;"
		f"selection-background-color: {sel_bg};"
		f"selection-color: {sel_text};"
		"}"
		f"QDialog#{oid} QLineEdit::placeholder {{ color: {text_muted}; }}"
		f"QDialog#{oid} QPushButton {{"
		f"background-color: {btn_bg};"
		f"color: {text_primary};"
		f"border: 1px solid {input_border};"
		"border-radius: 4px;"
		"padding: 6px 14px;"
		"min-height: 20px;"
		"}"
		f"QDialog#{oid} QPushButton:hover {{ background-color: {btn_hover}; }}"
		f"QDialog#{oid} QPushButton:pressed {{ background-color: {btn_hover}; }}"
	)


def _hint_example_font(src):
	"""Italic, slightly smaller 'e.g.' line. Resolves stylesheet fonts with pointSize -1 (avoids Qt warnings)."""

	from PyQt6.QtGui import QFont
	from PyQt6.QtWidgets import QApplication

	f = QFont(src)
	if f.pointSize() <= 0 and f.pixelSize() <= 0:
		app = QApplication.instance()
		if isinstance(app, QApplication):
			base = app.font()
			if base.pointSize() > 0:
				f.setPointSize(base.pointSize())
			elif base.pixelSize() > 0:
				f.setPixelSize(base.pixelSize())
			else:
				f.setPointSize(9)
		else:
			f.setPointSize(9)
	f.setItalic(True)
	ps = f.pointSizeF()
	if ps > 0:
		f.setPointSizeF(max(8.0, ps - 1.0))
	return f


def _quote(path: Path) -> str:
    try:
        return shlex.quote(str(path))
    except Exception:
        return str(path)


def open_path_in_explorer(target: Union[Path, str]) -> None:
    """Open a folder (or the parent of a file) in the platform file explorer."""
    path = Path(target)
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    folder = path if path.is_dir() else path.parent
    folder_str = str(folder)

    if sys.platform.startswith("win"):
        os.startfile(folder_str)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        os.system(f"open {_quote(folder)}")
    else:
        os.system(f"xdg-open {_quote(folder)}")


def confirm_action(parent, title: str, message: str) -> bool:
    """Show a confirmation prompt."""
    from PyQt6.QtWidgets import QMessageBox

    res = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    return res == QMessageBox.StandardButton.Yes


def format_restore_confirmation_text(details: dict, backup_filename: str) -> str:
	"""Short restore warning for QMessageBox (mode, safety, optional path hints)."""

	roots: list = details.get("roots") or []
	n_roots = len(roots)
	snap_n = sum(1 for r in roots if r.get("has_existing_files"))
	clear = bool(details.get("clear_before_unpack"))

	if clear:
		mode_line = "Full replace — save folders are cleared, then the backup is extracted."
	else:
		mode_line = "Merge — files in the ZIP overwrite matching paths; other files on disk stay."

	policy = "plugin" if details.get("policy_from_plugin") else "profile default"

	if details.get("any_safety_zip"):
		safety_line = f"Safety ZIPs: {snap_n} of {n_roots} location(s) → {details['safety_folder_display']}"
	else:
		safety_line = "Safety ZIPs: none (no existing saves to snapshot)."

	def _short_path(p: str, max_len: int = 72) -> str:
		t = str(p).strip()
		return t if len(t) <= max_len else t[: max_len - 1] + "…"

	lines: list[str] = [
		f"Restore “{backup_filename}” into {details['game_label']}?",
		"",
		mode_line,
		f"Policy: {policy}",
		"",
		safety_line,
	]

	if n_roots <= 3:
		for r in roots:
			ep = _short_path(r["expanded_path"])
			if r.get("has_existing_files"):
				tag = "snapshot, then " + ("clear & extract" if clear else "unpack")
			else:
				tag = "empty — no snapshot"
			lines.append(f"• [{r['logical_key']}] {tag}: {ep}")
	else:
		lines.append(f"{n_roots} save locations (paths are those configured for this profile).")

	lines.extend(["", "Continue with restore?"])
	return "\n".join(lines)


def confirm_restore(
	parent,
	profile: "GameProfile",
	plugin: object | None,
	config: "ConfigManager",
	backup_file: Path,
) -> bool:
	"""Show detailed restore confirmation; returns True if user accepts."""

	from .archive.metadata import read_archive_metadata
	from .core import restore_confirmation_details

	details = restore_confirmation_details(profile, plugin, config)
	msg = format_restore_confirmation_text(details, backup_file.name)
	meta = read_archive_metadata(backup_file)
	if meta is not None and meta.has_registry_export:
		msg += "\n\nIncludes registry export — entries apply on Windows after files."
	return confirm_action(parent, "Confirm restore", msg)


def _ensure_main_detail(spec_prompt: str) -> str:
	return spec_prompt.strip() or _DEFAULT_ENSURE_MSG


def _retry_main_detail(exception_message: Optional[str]) -> str:
	if exception_message is None:
		return _DEFAULT_RETRY_MSG
	text = exception_message.strip()
	return text if text else _DEFAULT_RETRY_MSG


def _restore_spec_for_key(pg: GamePlugin, input_key: str) -> RestoreInputSpec | None:
	target = input_key.strip()
	for spec in pg.restore_input_specs_for_review():
		if spec.key.strip() == target:
			return spec
	return None


def _field_labels_for_restore_input_key(
	pg: GamePlugin,
	key: str,
	spec_prompt: str,
	*,
	spec_label: str = "",
) -> tuple[str, str, str]:
	"""Return ``(field_label, placeholder, browse_dialog_title)`` for a restore-input key."""

	primary = pg.profile_primary_input_key()
	if primary is not None and primary.strip() == key.strip():
		hints_fn = getattr(pg, "primary_path_editor_hints", None)
		if callable(hints_fn):
			try:
				hint_pair = hints_fn()
			except Exception:
				hint_pair = None
			if isinstance(hint_pair, (tuple, list)) and len(hint_pair) >= 2:
				h0 = str(hint_pair[0]).strip()
				h1 = str(hint_pair[1]).strip()
				if h0 and h1:
					return h0, h1, h0

	short = (spec_label or "").strip()
	label = short if short else (key.replace("_", " ").strip().title() or "Folder")
	sp = spec_prompt.strip()
	if sp:
		return label, sp, sp
	return label, _DEFAULT_FIELD_PLACEHOLDER, label


def prompt_plugin_input(
	parent,
	*,
	window_title: str,
	detail: str,
	field_label: str,
	placeholder: str,
	initial_text: str,
	example: str | None = None,
	with_browse: bool = True,
	browse_mode: Literal["folder", "file"] = "folder",
	browse_title: str | None = None,
	input_kind: str = "existing_directory",
	validations: tuple[str, ...] | None = None,
) -> str | None:
	"""Plugin modal: detail, optional ``e.g.``, label over full-width field, OK/Cancel. ``with_browse=False`` = text only."""

	from PyQt6.QtCore import Qt
	from PyQt6.QtWidgets import (
		QDialog,
		QDialogButtonBox,
		QFileDialog,
		QHBoxLayout,
		QLabel,
		QLineEdit,
		QPushButton,
		QVBoxLayout,
	)

	from .core import PathUtils

	vals = validations or ()

	fl = field_label.strip()
	bt = (browse_title or "").strip() or (fl.rstrip(":") if fl else "") or _DEFAULT_BROWSE_DIALOG_TITLE

	dlg = QDialog(parent)
	dlg.setObjectName(_PLUGIN_INPUT_DIALOG_QSS_ID)
	dlg.setStyleSheet(_plugin_input_dialog_stylesheet())
	dlg.setWindowTitle(window_title)
	dlg.setMinimumWidth(480)

	root = QVBoxLayout(dlg)
	root.setContentsMargins(12, 12, 12, 12)
	root.setSpacing(10)

	edit = QLineEdit(initial_text)
	edit.setPlaceholderText(placeholder.strip() or _DEFAULT_LINE_EDIT_PLACEHOLDER)
	edit.setMinimumHeight(28)

	msg = QLabel((detail.strip() or "Details:"))
	msg.setWordWrap(True)
	msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
	root.addWidget(msg)

	ex = (example or "").strip()
	if ex:
		h = QLabel(f"e.g. {ex}")
		h.setWordWrap(True)
		h.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
		h.setFont(_hint_example_font(msg.font()))
		h.setObjectName(_PLUGIN_INPUT_EXAMPLE_LABEL_ID)
		root.addWidget(h)

	fs = field_label.strip()
	cap = QLabel((fs if fs.endswith(":") else f"{fs}:") if fs else "Value:")
	cap.setWordWrap(True)
	stack = QVBoxLayout()
	stack.setSpacing(6)
	stack.addWidget(cap)

	row = QHBoxLayout()
	row.setSpacing(8)
	row.addWidget(edit, stretch=1)

	def pick() -> None:
		if browse_mode == "folder":
			dir_path = QFileDialog.getExistingDirectory(dlg, bt)
			if dir_path:
				edit.setText(PathUtils.contract(dir_path))
			return
		file_path, _ = QFileDialog.getOpenFileName(dlg, bt, "", "All files (*)")
		if file_path:
			edit.setText(PathUtils.contract(file_path))

	if with_browse:
		b = QPushButton("Browse…")
		b.clicked.connect(pick)
		row.addWidget(b)

	stack.addLayout(row)
	root.addLayout(stack)

	err_label = QLabel("")
	err_label.setWordWrap(True)
	err_label.setStyleSheet("color: #c62828;")
	err_label.hide()
	root.addWidget(err_label)

	box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
	ok_btn = box.button(QDialogButtonBox.StandardButton.Ok)
	cancel_btn = box.button(QDialogButtonBox.StandardButton.Cancel)

	def submit() -> None:
		raw_line = edit.text().strip()
		ok, err_msg = validate_restore_input(input_kind, raw_line, vals)
		if ok:
			err_label.hide()
			dlg.accept()
			return
		err_label.setText(err_msg or "Invalid input.")
		err_label.show()

	ok_btn.clicked.connect(submit)
	cancel_btn.clicked.connect(dlg.reject)
	root.addWidget(box)

	if dlg.exec() != QDialog.DialogCode.Accepted:
		return None
	out = edit.text().strip()
	if input_kind == "existing_directory":
		if not out:
			return ""
		if not with_browse:
			return out
		clean = PathUtils.clean_input_path(out)
		return PathUtils.contract(clean) if clean else None
	if not out:
		return ""
	return out


def ensure_plugin_restore_inputs(
	parent,
	profile: "GameProfile",
	plugin: object | None,
	config: "ConfigManager",
) -> bool:
	"""Before backup/restore: collect any missing ``restore_input_specs`` via the shared path dialog.

	Persists under ``GameProfile.plugin_inputs`` with ``persist_restore_input_value``.
	Returns False if the user cancels.
	"""

	from .plugin_runtime import as_game_plugin

	pg = as_game_plugin(plugin)
	if pg is None:
		return True
	specs = pg.restore_input_specs()
	if not specs:
		return True

	values: Dict[str, Any] = dict(pg.profile_restore_input_values(profile))

	dirty = False
	for spec in specs:
		if not spec.key.strip():
			continue
		if spec.kind != "existing_directory":
			continue
		prev = values.get(spec.key)
		if isinstance(prev, str) and prev.strip():
			continue

		sl = (spec.label or "").strip()
		flabel, ph, btitle = _field_labels_for_restore_input_key(pg, spec.key, spec.prompt, spec_label=sl)
		ex_hint = spec.example.strip() if spec.example.strip() else None
		path = prompt_plugin_input(
			parent,
			window_title="Folder",
			detail=_ensure_main_detail(spec.prompt),
			field_label=flabel,
			placeholder=ph,
			initial_text="",
			browse_title=btitle,
			example=ex_hint,
			input_kind=spec.kind,
			validations=tuple(spec.validations),
		)
		if path is None:
			return False
		pg.persist_restore_input_value(profile, spec.key, path)
		dirty = True
		values = dict(pg.profile_restore_input_values(profile))

	if dirty:
		config.save_config()

	return True


def offer_plugin_restore_input_review(
	parent,
	profile: "GameProfile",
	plugin: object | None,
	config: "ConfigManager",
) -> bool:
	"""Optional pre-restore step: ask whether to review or change plugin path pins (``plugin_inputs``).

	Uses :meth:`GamePlugin.restore_input_specs_for_review`. Returns False if the user cancels.
	"""

	from PyQt6.QtWidgets import QMessageBox

	from .plugin_runtime import as_game_plugin

	pg = as_game_plugin(plugin)
	if pg is None:
		return True

	specs = pg.restore_input_specs_for_review()

	editable = [s for s in specs if s.key.strip() and s.kind == "existing_directory"]
	if not editable:
		return True

	res = QMessageBox.question(
		parent,
		"Restore paths",
		"This profile may use folder paths (install/save pins) for restore.\n\n"
		"Do you want to review or change them before continuing?\n\n"
		"• Yes — edit paths\n"
		"• No — use saved values\n"
		"• Cancel — abort restore",
		QMessageBox.StandardButton.Yes
		| QMessageBox.StandardButton.No
		| QMessageBox.StandardButton.Cancel,
		QMessageBox.StandardButton.No,
	)
	if res == QMessageBox.StandardButton.Cancel:
		return False
	if res != QMessageBox.StandardButton.Yes:
		return True

	values: Dict[str, Any] = dict(pg.profile_restore_input_values(profile))
	dirty = False

	for spec in editable:
		sl = (spec.label or "").strip()
		flabel, ph, btitle = _field_labels_for_restore_input_key(pg, spec.key, spec.prompt, spec_label=sl)
		ex_hint = spec.example.strip() if spec.example.strip() else None
		prev = values.get(spec.key)
		initial = (prev or "").strip() if isinstance(prev, str) else ""

		path = prompt_plugin_input(
			parent,
			window_title="Review restore path",
			detail=_ensure_main_detail(spec.prompt),
			field_label=flabel,
			placeholder=ph,
			initial_text=initial,
			browse_title=btitle,
			example=ex_hint,
			input_kind=spec.kind,
			validations=tuple(spec.validations),
		)
		if path is None:
			return False
		pg.persist_restore_input_value(profile, spec.key, path)
		dirty = True
		values = dict(pg.profile_restore_input_values(profile))

	if dirty:
		config.save_config()

	return True


def prompt_plugin_primary_path_fix(
	parent,
	profile: "GameProfile",
	plugin: object | None,
	config: "ConfigManager",
	*,
	detail: Optional[str] = None,
) -> bool:
	"""Same folder dialog as ``ensure_plugin_restore_inputs``; persists primary pin on OK."""

	from .plugin_runtime import as_game_plugin

	if not profile.plugin_id.strip():
		return False
	pg = as_game_plugin(plugin)
	if pg is None:
		return False

	pk_opt = pg.profile_primary_input_key()
	if pk_opt is None or not pk_opt.strip():
		return False
	key = pk_opt.strip()

	sp_spec = _restore_spec_for_key(pg, key)
	spec_prompt = sp_spec.prompt if sp_spec is not None else ""
	spec_example = sp_spec.example if sp_spec is not None else ""
	sp_label = (sp_spec.label or "").strip() if sp_spec is not None else ""
	kind = sp_spec.kind if sp_spec is not None else "existing_directory"
	vals = tuple(sp_spec.validations) if sp_spec is not None else ()
	flabel, ph, btitle = _field_labels_for_restore_input_key(pg, key, spec_prompt, spec_label=sp_label)
	body = _retry_main_detail(detail)
	ex_hint = spec_example.strip() if spec_example.strip() else None
	path = prompt_plugin_input(
		parent,
		window_title="Fix path",
		detail=body,
		field_label=flabel,
		placeholder=ph,
		initial_text=profile.editor_primary_path_display(pg),
		browse_title=btitle,
		example=ex_hint,
		input_kind=kind,
		validations=vals,
	)
	if path is None:
		return False
	pg.persist_restore_input_value(profile, key, path)
	config.save_config()
	return True
