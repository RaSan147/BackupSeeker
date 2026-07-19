"""Fluent main-window discovery for PyQt widgets (no getattr on ``window()``).

Lives under :mod:`BackupSeeker` (not ``ui_fluent``) so :mod:`modern_widgets` can
import it without circular imports through ``ui_fluent.__init__``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from PyQt6.QtWidgets import QWidget

if TYPE_CHECKING:
	from .plugin_manager import PluginManager


@runtime_checkable
class FluentAppWindow(Protocol):
	"""Contract for the Fluent main window (``content_widget``, ``plugin_manager``)."""

	content_widget: QWidget
	plugin_manager: PluginManager


def toast_parent(widget: QWidget) -> QWidget:
	"""Preferred parent for InfoBar / dialogs (main content area)."""
	root = widget.window()
	if isinstance(root, FluentAppWindow):
		return root.content_widget
	return root


def plugin_manager_from_widget(start: QWidget | None):
	"""Return the app's :class:`~BackupSeeker.plugin_manager.PluginManager`.

	Walks from ``start`` through parent widgets so pop-up dialogs (whose
	``window()`` is the dialog itself) still find the main window's manager.
	"""

	if start is None:
		return None
	from .plugin_manager import PluginManager

	cur: QWidget | None = start
	visited: set[int] = set()
	while cur is not None:
		oid = id(cur)
		if oid in visited:
			break
		visited.add(oid)
		root = cur.window()
		if isinstance(root, FluentAppWindow):
			return root.plugin_manager
		pm = getattr(root, "plugin_manager", None)
		if isinstance(pm, PluginManager):
			return pm
		cur = cur.parentWidget()
	return None


def fluent_plugin_manager(widget: QWidget | None):
	"""Backward-compatible alias for :func:`plugin_manager_from_widget`."""

	return plugin_manager_from_widget(widget)


def resolve_plugin_for_profile(profile: object, widget: QWidget | None):
	"""Resolve the loaded plugin for ``profile`` using the same manager as backup/restore."""

	pid = (getattr(profile, "plugin_id", None) or "").strip()
	if not pid:
		return None
	pm = plugin_manager_from_widget(widget)
	if pm is None:
		return None
	try:
		return pm.get_plugin_for_profile(pid)
	except Exception:
		return None
