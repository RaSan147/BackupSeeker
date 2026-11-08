"""Scaled poster caching for store/library cards.

Viewport recycling was abandoned in favor of pagination: only one page of
eager ``setItemWidget`` cards is mounted at a time.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel

from .profile_visuals import load_pixmap, scale_poster


class ScaledPosterCache:
	"""LRU of fitted poster canvases keyed by path + mtime + size."""

	def __init__(self, capacity: int = 80) -> None:
		self._capacity = max(8, int(capacity))
		self._entries: OrderedDict[str, QPixmap] = OrderedDict()

	def get(self, path: str | None, size: QSize) -> QPixmap | None:
		if not path:
			return None
		key = self._key(path, size)
		if key is None:
			return None
		pix = self._entries.get(key)
		if pix is None or pix.isNull():
			return None
		self._entries.move_to_end(key)
		return pix

	def put(self, path: str | None, size: QSize, canvas: QPixmap) -> QPixmap:
		if not path or canvas is None or canvas.isNull():
			return canvas
		key = self._key(path, size)
		if key is None:
			return canvas
		self._entries[key] = canvas
		self._entries.move_to_end(key)
		while len(self._entries) > self._capacity:
			self._entries.popitem(last=False)
		return canvas

	def get_or_load(self, path: str | None, size: QSize) -> QPixmap | None:
		cached = self.get(path, size)
		if cached is not None:
			return cached
		if not path or not Path(path).is_file():
			return None
		raw = load_pixmap(path)
		if raw is None or raw.isNull():
			return None
		return self.put(path, size, scale_poster(raw, size))

	@staticmethod
	def _key(path: str, size: QSize) -> str | None:
		try:
			p = Path(path)
			if not p.is_file():
				return None
			mtime = p.stat().st_mtime_ns
			resolved = str(p.resolve())
		except Exception:
			return None
		return f"{resolved}|{mtime}|{size.width()}x{size.height()}"


POSTER_CACHE = ScaledPosterCache(80)


def apply_cached_poster(label: QLabel, path: str | None, size: QSize) -> bool:
	"""Paint a cached/scaled poster onto ``label``. Returns True if applied."""

	canvas = POSTER_CACHE.get_or_load(path, size)
	if canvas is None or canvas.isNull():
		return False
	label.setStyleSheet("QLabel{background: transparent; border:0;}")
	label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
	label.setScaledContents(False)
	label.setAlignment(Qt.AlignmentFlag.AlignCenter)
	label.setPixmap(canvas)
	return True


def page_bounds(total: int, page: int, page_size: int) -> tuple[int, int, int]:
	"""Return ``(page_index, start, end)`` clamped for ``total`` items."""

	size = max(1, int(page_size))
	pages = max(1, (max(0, int(total)) + size - 1) // size)
	page_index = min(max(0, int(page)), pages - 1)
	start = page_index * size
	end = min(total, start + size)
	return page_index, start, end
