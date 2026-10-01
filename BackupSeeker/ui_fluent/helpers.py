from __future__ import annotations

import html
from datetime import datetime
from typing import Any

import time
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PyQt6.QtWidgets import QAbstractItemView, QAbstractScrollArea, QWidget
from qfluentwidgets import ComboBox, SingleDirectionScrollArea, TableWidget
from qfluentwidgets.common.smooth_scroll import SmoothScroll
from qfluentwidgets.components.widgets.scroll_bar import SmoothScrollDelegate, SmoothScrollBar

from ..core import ConfigManager, GameProfile
from ..fluent_window import resolve_plugin_for_profile
from .styles import AdaptiveThemeStyles


def _smooth_scroll_to(sb: SmoothScrollBar, delta: int) -> None:
	"""Target-accumulating smooth scroll with adaptive duration.

	- Single notch: glides 85px over 150ms with OutCubic easing curve.
	- G502 free-spin / infinity scroll: dynamically reduces duration to 50-80ms so
	  scrolling tracks the free-spinning hardware wheel with zero lag and stops immediately
	  when the user stops the wheel (no runaway momentum).
	- Direction reversal: instantly snaps in-flight target to current position so
	  reverse scrolls respond without having to unwind forward momentum.
	"""
	if not isinstance(sb, SmoothScrollBar) or sb.maximum() <= sb.minimum():
		return

	curr = sb.value()
	step = -int(round(delta / 120.0 * 85.0))
	if step == 0:
		step = -1 if delta > 0 else 1

	target = getattr(sb, "_target_smooth_val", curr)
	is_running = hasattr(sb, "ani") and sb.ani.state() == QPropertyAnimation.State.Running

	if not is_running:
		target = curr
	elif (step > 0 and target < curr) or (step < 0 and target > curr):
		target = curr

	target += step
	target = max(sb.minimum(), min(sb.maximum(), target))
	sb._target_smooth_val = target

	if target == curr:
		if hasattr(sb, "ani"):
			sb.ani.stop()
		return

	now = time.perf_counter()
	last_time = getattr(sb, "_last_wheel_time", 0.0)
	dt_ms = (now - last_time) * 1000.0
	sb._last_wheel_time = now

	if dt_ms < 25:
		duration = 50
	elif dt_ms < 50:
		duration = 80
	elif dt_ms < 80:
		duration = 110
	else:
		duration = 150

	if hasattr(sb, "ani"):
		sb.ani.stop()
		sb.ani.setEasingCurve(QEasingCurve.Type.OutCubic)
		sb.ani.setDuration(duration)
		sb.ani.setStartValue(curr)
		sb.ani.setEndValue(target)
		sb.ani.start()
	else:
		sb.setValue(target, useAni=False)


def optimize_fluent_scrolling() -> None:
	"""Optimize QFluentWidgets scrolling for notched and free-spin wheels (e.g. Logitech G502).

	Solves:
	1. Jumpy, discrete page-tick scrolling by driving SmoothScrollBar via target accumulation
	   with granular 85px steps instead of 301px row jumps or sluggish 400ms queueing engines.
	2. Free-spin runaway inertia by scaling animation duration to 50ms during high-frequency
	   wheel events, stopping immediately when the wheel stops.
	3. Mouse tilt wheel events discarding vertical scroll events on SmoothScrollDelegate and
	   SingleDirectionScrollArea.
	"""
	try:
		# 1. SmoothScrollDelegate wheel handling
		_orig_del_filter = getattr(SmoothScrollDelegate, "_orig_filter_backupseeker", None)
		if _orig_del_filter is None:
			_orig_del_filter = SmoothScrollDelegate.eventFilter
			SmoothScrollDelegate._orig_filter_backupseeker = _orig_del_filter

			def _fast_delegate_filter(self, obj, e):
				if e.type() == e.Type.Wheel:
					dy = e.angleDelta().y()
					dx = e.angleDelta().x()

					if dy != 0:
						vsb = self.vScrollBar
						at_top = dy > 0 and vsb.value() <= vsb.minimum()
						at_bottom = dy < 0 and vsb.value() >= vsb.maximum()
						if (at_top or at_bottom) and dx == 0:
							return False

						if not (at_top or at_bottom):
							_smooth_scroll_to(vsb, dy)
						e.setAccepted(True)
						return True
					elif dx != 0:
						hsb = self.hScrollBar
						at_left = dx > 0 and hsb.value() <= hsb.minimum()
						at_right = dx < 0 and hsb.value() >= hsb.maximum()
						if at_left or at_right:
							return False

						_smooth_scroll_to(hsb, dx)
						e.setAccepted(True)
						return True

					return False
				return _orig_del_filter(self, obj, e)

			SmoothScrollDelegate.eventFilter = _fast_delegate_filter

		# 2. Fix SingleDirectionScrollArea.wheelEvent so horizontal tilt doesn't drop vertical scrolling
		_orig_sd_wheel = getattr(SingleDirectionScrollArea, "_orig_wheel_backupseeker", None)
		if _orig_sd_wheel is None:
			_orig_sd_wheel = SingleDirectionScrollArea.wheelEvent
			SingleDirectionScrollArea._orig_wheel_backupseeker = _orig_sd_wheel

			def _fast_single_dir_wheel(self, e):
				dy = e.angleDelta().y()
				dx = e.angleDelta().x()
				if self.orient == Qt.Orientation.Vertical:
					delta = dy if dy != 0 else dx
					sb = self.vScrollBar
				else:
					delta = dx if dx != 0 else dy
					sb = self.hScrollBar

				if delta != 0:
					_smooth_scroll_to(sb, delta)
					e.setAccepted(True)

			SingleDirectionScrollArea.wheelEvent = _fast_single_dir_wheel
	except Exception:
		pass


# Auto-apply on module load
optimize_fluent_scrolling()


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
	table.setWordWrap(False)


def _make_details_text(
	detail_body: str = "Not selected",
	storage: str = "Not set",
	status: str = "Waiting",
	detail_title: str | None = "Save location",
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


def format_verify_report_text(report: dict[str, Any]) -> str:
	lines: list[str] = []
	lines.append("Save locations")
	lines.append("-" * 44)
	for row in report.get("locations") or []:
		if not isinstance(row, dict):
			continue
		key = row.get("logical_key", "?")
		label = (row.get("label") or "").strip()
		tag = f"{label} [{key}]" if label and label != key else f"[{key}]"
		ex = row.get("expanded_path", "")
		exists = row.get("exists", False)
		nf = row.get("file_count", 0)
		flag = "OK" if row.get("has_data") else ("missing/empty" if not exists else "empty")
		lines.append(f"  {tag} {flag} | files: {nf}")
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
			flag = "OK" if ok else "-"
			lines.append(f"  [{flag}] {row.get('key_path','')} :: {row.get('value_name','')}")
			detail = row.get("detail", "")
			if detail:
				lines.append(f"      {detail}")

	lines.append("")
	det = report.get("plugin_is_detected")
	if det is not None:
		lines.append(f"Plugin detection heuristic: {'yes' if det else 'no'}")
	return "\n".join(lines)
