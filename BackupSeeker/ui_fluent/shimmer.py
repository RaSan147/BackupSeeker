"""Shimmer skeleton placeholder widget for modern card and poster loading states."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..ui_helpers import is_app_dark


class ShimmerSkeleton(QWidget):
	"""A modern, hardware-efficient shimmer placeholder.

	Renders smooth rounded placeholder rectangles with an animated sweeping linear gradient.
	Automatically adapts to light and dark themes.
	"""

	def __init__(self, parent: QWidget | None = None, corner_radius: int = 6):
		super().__init__(parent)
		self._radius = corner_radius
		self._phase = 0.0
		self._animation_enabled = True

		self._animation = QVariantAnimation(self)
		self._animation.setStartValue(0.0)
		self._animation.setEndValue(1.0)
		self._animation.setDuration(1400)
		self._animation.setLoopCount(-1)
		self._animation.setEasingCurve(QEasingCurve.Type.Linear)
		self._animation.valueChanged.connect(self._on_phase_changed)

		self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		self._animation.start()

	def _on_phase_changed(self, value: float) -> None:
		self._phase = value
		self.update()

	def setCornerRadius(self, radius: int) -> None:
		self._radius = radius
		self.update()

	def setAnimationEnabled(self, enabled: bool) -> None:
		self._animation_enabled = enabled
		if enabled:
			if self._animation.state() != QVariantAnimation.State.Running:
				self._animation.start()
		else:
			self._animation.stop()
		self.update()

	def paintEvent(self, event) -> None:
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)

		w = float(self.width())
		h = float(self.height())
		if w <= 0 or h <= 0:
			return

		dark = is_app_dark()
		base_color = QColor("#1e202e") if dark else QColor("#e2e5ef")
		highlight_color = QColor(255, 255, 255, 40) if dark else QColor(255, 255, 255, 120)

		rect = QRectF(0, 0, w, h)
		path = QPainterPath()
		path.addRoundedRect(rect, self._radius, self._radius)
		painter.fillPath(path, base_color)

		if self._animation_enabled:
			# Sweeping diagonal/horizontal shimmer
			sweep_width = w * 0.7
			start_x = -sweep_width + (w + sweep_width * 2) * self._phase
			gradient = QLinearGradient(start_x, 0, start_x + sweep_width, 0)
			gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
			gradient.setColorAt(0.5, highlight_color)
			gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

			painter.setClipPath(path)
			painter.fillRect(rect, gradient)
