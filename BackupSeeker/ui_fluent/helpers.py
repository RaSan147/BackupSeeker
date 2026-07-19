from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QAbstractScrollArea, QWidget
from qfluentwidgets import ComboBox, TableWidget

from ..core import ConfigManager, GameProfile
from ..fluent_window import resolve_plugin_for_profile
from .styles import AdaptiveThemeStyles


def _plugin_for_profile_widget(profile: GameProfile, widget: QWidget):
	return resolve_plugin_for_profile(profile, widget)


def _profile_display_name(profile: GameProfile, widget: QWidget) -> str:
	return profile.resolved_name(_plugin_for_profile_widget(profile, widget))


def _profile_kind_prefix(profile: GameProfile) -> str:
	return "🔌 " if profile.plugin_id else "✎ "


def last_backup_label(
	profile: GameProfile,
	widget: QWidget,
	config: ConfigManager,
	*,
	prefix: str = "Last: ",
	date_fmt: str = "%Y-%m-%d %H:%M",
) -> str:
	"""Human-readable last-backup timestamp for a profile."""

	plug = resolve_plugin_for_profile(profile, widget)
	bdir = config.backup_dir_for_profile(profile, plug)
	files = list(bdir.glob("*.zip"))
	if not files:
		return f"{prefix}Never"
	latest = max(files, key=lambda f: f.stat().st_mtime)
	stamp = datetime.fromtimestamp(latest.stat().st_mtime).strftime(date_fmt)
	return f"{prefix}{stamp}"


def combo_label_for_ui_view(mode: str | None) -> str:
	"""Label for List/Cards ComboBox from stored config ('list' | 'cards')."""

	return "Cards" if (mode or "").strip().lower() == "cards" else "List"


def ui_view_mode_from_combo_text(text: str | None) -> str:
	"""Store 'list' or 'cards' from ComboBox display text."""

	return "cards" if (text or "").strip().lower().startswith("c") else "list"


def apply_combo_ui_view(combo: QWidget, mode: str) -> None:
	"""Set ComboBox to *mode* without emitting *currentTextChanged*."""

	if not isinstance(combo, ComboBox):
		return
	label = combo_label_for_ui_view(mode)
	combo.blockSignals(True)
	try:
		combo.setCurrentText(label)
	except Exception:
		combo.setCurrentIndex(1 if label == "Cards" else 0)
	finally:
		combo.blockSignals(False)


def _install_read_only_table(table: TableWidget) -> None:
	table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)


def _make_details_text(
	detail_body: str = "Not selected",
	storage: str = "Not set",
	status: str = "Waiting",
	detail_title: Optional[str] = "Save location",
	*,
	include_storage: bool = True,
) -> str:
	styles = AdaptiveThemeStyles()
	primary_color = styles.text_primary()
	secondary_color = styles.text_secondary()
	html_body = html.escape(detail_body)
	title_prefix = ""
	if detail_title is not None and str(detail_title).strip():
		title_esc = html.escape(str(detail_title).strip())
		title_prefix = (
			f"<b style='color:{primary_color}'>{title_esc}:</b> "
		)
	storage_bit = ""
	if include_storage:
		storage_bit = (
			f"<br><br>"
			f"<b style='color:{primary_color}'>Storage:</b> "
			f"<span style='white-space:pre-wrap; color:{secondary_color};'>{html.escape(storage)}</span>"
		)
	return (
		f"<div style='font-family:Segoe UI, Roboto, Arial; font-size:13px; color:{primary_color};'>"
		f"{title_prefix}"
		f"<span style='font-family:Segoe UI, Roboto, Arial; white-space:pre-wrap; word-break:break-word; color:{secondary_color};'>{html_body}</span>"
		f"{storage_bit}"
		f"<br><br>"
		f"<b style='color:{primary_color}'>Status:</b> <span style='color:{secondary_color};'>{html.escape(status)}</span>"
		"</div>"
	)


def _make_transparent_widget(widget: QWidget) -> None:
	widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
	if isinstance(widget, QAbstractScrollArea):
		vp = widget.viewport()
		if vp is not None:
			vp.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
			vp.setStyleSheet("background: transparent;")


def format_verify_report_text(report: Dict[str, Any]) -> str:
	lines: List[str] = []
	lines.append("Save locations")
	lines.append("-" * 44)
	for row in report.get("locations") or []:
		if not isinstance(row, dict):
			continue
		key = row.get("logical_key", "?")
		ex = row.get("expanded_path", "")
		exists = row.get("exists", False)
		nf = row.get("file_count", 0)
		flag = "OK" if row.get("has_data") else ("missing/empty" if not exists else "empty")
		lines.append(f"  [{key}] {flag} | files: {nf}")
		lines.append(f"      {ex}")

	lines.append("")
	lines.append("Registry (hints)")
	lines.append("-" * 44)
	reg_rows = report.get("registry") or []
	if not reg_rows:
		lines.append("  (none configured)")
	else:
		for row in reg_rows:
			if not isinstance(row, dict):
				continue
			ok = row.get("present_and_valid", False)
			flag = "OK" if ok else "—"
			lines.append(f"  [{flag}] {row.get('key_path','')} :: {row.get('value_name','')}")
			detail = row.get("detail", "")
			if detail:
				lines.append(f"      {detail}")

	lines.append("")
	det = report.get("plugin_is_detected")
	if det is not None:
		lines.append(f"Plugin detection heuristic: {'yes' if det else 'no'}")
	return "\n".join(lines)
