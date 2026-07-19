"""Shared profile poster/icon loading for dashboard and profiles pages."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QLabel, QWidget

from ..core import GameProfile
from ..fluent_window import plugin_manager_from_widget, resolve_plugin_for_profile
from ..plugin_manager import PluginManager

POSTER_LABEL_NAME = "profileCardPoster"

_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".svg", ".ico")


def find_placeholder_image(app_dir: Path) -> Path | None:
	"""Locate a bundled ``placeholder*`` image under the app tree."""

	try:
		candidates = [
			app_dir,
			app_dir.parent,
			app_dir / "Data",
			app_dir.parent / "Data",
		]
		seen: set[str] = set()
		for base in candidates:
			if not base or not base.exists():
				continue
			real = str(base.resolve())
			if real in seen:
				continue
			seen.add(real)
			for path in base.rglob("*"):
				if path.is_file() and path.name.lower().startswith("placeholder"):
					return path
	except Exception:
		pass
	return None


def load_pixmap(image_path: str | None) -> QPixmap | None:
	if not image_path:
		return None
	try:
		pix = QPixmap(str(image_path))
		return pix if not pix.isNull() else None
	except Exception:
		return None


def fit_pixmap_to_label(label: QLabel, pix: QPixmap, max_size: QSize) -> None:
	"""Shrink-to-fit on a transparent canvas; never upscale."""

	label.setStyleSheet("QLabel{background: transparent; border:0;}")
	label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

	if pix is None or pix.isNull():
		label.clear()
		return

	target_w = max_size.width()
	target_h = max_size.height()
	if pix.width() > target_w or pix.height() > target_h:
		scaled = pix.scaled(
			max_size,
			Qt.AspectRatioMode.KeepAspectRatio,
			Qt.TransformationMode.SmoothTransformation,
		)
	else:
		scaled = pix

	canvas = QPixmap(target_w, target_h)
	canvas.fill(Qt.GlobalColor.transparent)
	x = max(0, (target_w - scaled.width()) // 2)
	y = max(0, (target_h - scaled.height()) // 2)
	painter = QPainter(canvas)
	painter.drawPixmap(x, y, scaled)
	painter.end()

	label.setScaledContents(False)
	label.setAlignment(Qt.AlignmentFlag.AlignCenter)
	label.setPixmap(canvas)


def is_emoji_icon(icon_str: str) -> bool:
	if not icon_str:
		return False
	text = icon_str.strip()
	if not text:
		return False
	lower = text.lower()
	if any(sep in text for sep in ("/", "\\", "%")):
		return False
	if any(lower.endswith(ext) for ext in _IMAGE_EXTENSIONS):
		return False
	if any(ch.isalnum() for ch in text):
		return False
	return len(text) <= 4


class ProfilePosterService:
	"""Resolve plugin posters and paint them into profile cards."""

	def __init__(
		self,
		widget: QWidget,
		*,
		plugin_manager: PluginManager | None = None,
		app_dir: Path | None = None,
	) -> None:
		self._widget = widget
		self._plugin_manager = plugin_manager
		self._app_dir = app_dir

	def plugin_manager(self) -> PluginManager | None:
		if self._plugin_manager is not None:
			return self._plugin_manager
		return plugin_manager_from_widget(self._widget)

	def icon_for(self, profile: GameProfile) -> str:
		plugin = resolve_plugin_for_profile(profile, self._widget)
		if plugin and getattr(plugin, "icon", ""):
			return plugin.icon
		return (profile.icon or "") or "🎮"

	def poster_path(
		self,
		profile: GameProfile,
		on_complete: Callable[[], None] | None = None,
		*,
		queue_download: bool = True,
	) -> str | None:
		"""Local filesystem path for the poster, never a remote URL."""

		pm = self.plugin_manager()
		plugin = resolve_plugin_for_profile(profile, self._widget)
		if pm is not None and plugin is not None:
			if queue_download:
				pm.ensure_plugin_visual_assets(plugin, on_complete)
			saved = getattr(plugin, "_saved_poster", "")
			if saved:
				return saved

		poster = (profile.poster or "").strip()
		if poster and not poster.lower().startswith(("http://", "https://")):
			return poster
		return None

	def expects_download(self, profile: GameProfile) -> bool:
		plugin = resolve_plugin_for_profile(profile, self._widget)
		if plugin is not None:
			if getattr(plugin, "_saved_poster", ""):
				return False
			poster = (getattr(plugin, "poster", "") or "").strip()
			if poster.lower().startswith(("http://", "https://")):
				return not getattr(plugin, "_visual_assets_loaded", False)

		poster = (profile.poster or "").strip()
		return poster.lower().startswith(("http://", "https://"))

	def pixmap_for(
		self,
		profile: GameProfile,
		*,
		poster_size: QSize | None = None,
		allow_placeholder: bool = True,
		queue_download: bool = True,
	) -> QPixmap:
		poster_path = self.poster_path(profile, queue_download=queue_download)
		pix = load_pixmap(poster_path) or QPixmap()
		if not pix.isNull():
			return pix

		if self.expects_download(profile):
			blank = QPixmap(poster_size or QSize(1, 1))
			blank.fill(Qt.GlobalColor.transparent)
			return blank

		if allow_placeholder and self._app_dir is not None:
			ph = find_placeholder_image(self._app_dir)
			if ph:
				pix = load_pixmap(str(ph)) or QPixmap()
				if not pix.isNull():
					return pix

		blank = QPixmap(poster_size or QSize(1, 1))
		blank.fill(Qt.GlobalColor.transparent)
		return blank

	def apply_to_label(
		self,
		label: QLabel,
		profile: GameProfile,
		poster_size: QSize,
		*,
		allow_placeholder: bool = True,
		queue_download: bool = False,
	) -> None:
		pix = self.pixmap_for(
			profile,
			poster_size=poster_size,
			allow_placeholder=allow_placeholder,
			queue_download=queue_download,
		)
		if not pix.isNull():
			fit_pixmap_to_label(label, pix, poster_size)

	def apply_to_card(
		self,
		card: QWidget,
		profile: GameProfile,
		poster_size: QSize,
		*,
		allow_placeholder: bool = True,
	) -> None:
		label = card.findChild(QLabel, POSTER_LABEL_NAME)
		if label is None:
			return
		self.apply_to_label(
			label,
			profile,
			poster_size,
			allow_placeholder=allow_placeholder,
			queue_download=False,
		)
