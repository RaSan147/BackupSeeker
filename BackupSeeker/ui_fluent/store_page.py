from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
	QAbstractItemView,
	QFrame,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QListView,
	QListWidget,
	QListWidgetItem,
	QSizePolicy,
	QTableWidgetItem,
	QVBoxLayout,
	QWidget,
)

from qfluentwidgets import (
	BodyLabel,
	CaptionLabel,
	ComboBox,
	FluentIcon as FIF,
	InfoBar,
	InfoBarPosition,
	LineEdit,
	PlainTextEdit,
	PrimaryPushButton,
	PushButton,
	RoundMenu,
	Action,
	SimpleCardWidget,
	StrongBodyLabel,
	TableWidget,
	TitleLabel,
	TransparentPushButton,
)

from ..core import ConfigManager, GameProfile, verify_save_locations_report
from ..developer_mode import is_developer_mode, set_dev_widgets_visible
from ..fluent_window import toast_parent
from ..modern_widgets import RoundedCard
from ..plugin_manager import PluginLoadReport, PluginManager
from .helpers import (
	_install_read_only_table,
	apply_combo_ui_view,
	ui_view_mode_from_combo_text,
)
from .poster_refresh import PosterRefreshCoordinator
from .profile_visuals import (
	POSTER_LABEL_NAME,
	ProfilePosterService,
	elide_multiline_text,
	fit_pixmap_to_label,
)
from .styles import AdaptiveThemeStyles, LIST_STYLE_TRANSPARENT


class StoreCardWidget(RoundedCard):
	"""Modern Hydra-style store card showing plugin artwork, detection badge, and 1-click Add."""

	clicked = pyqtSignal()
	profile_requested = pyqtSignal()
	toggle_library_requested = pyqtSignal()

	def __init__(
		self,
		plugin: object,
		config: ConfigManager,
		poster_service: ProfilePosterService,
		is_detected: bool = False,
		in_library: bool = False,
		parent: QWidget | None = None,
	):
		super().__init__(parent)
		self.plugin = plugin
		self.config = config
		self._posters = poster_service
		self.is_detected = is_detected
		self.in_library = in_library

		self.setFixedSize(260, 275)
		self.setCursor(Qt.CursorShape.PointingHandCursor)

		self.setStyleSheet(
			"RoundedCard {"
			"  background-color: #1a1c26;"
			"  border: 1px solid #2b2e42;"
			"  border-radius: 10px;"
			"}"
			"RoundedCard:hover {"
			"  background-color: #222534;"
			"  border: 1px solid #5b6cf9;"
			"}"
		)

		layout = QVBoxLayout(self)
		layout.setContentsMargins(10, 10, 10, 10)
		layout.setSpacing(8)

		# Poster Area
		self.poster_frame = QFrame(self)
		self.poster_frame.setFixedSize(240, 135)
		self.poster_frame.setStyleSheet(
			"QFrame {"
			"  background-color: #12131a;"
			"  border: 1px solid #26293b;"
			"  border-radius: 6px;"
			"}"
		)
		p_layout = QVBoxLayout(self.poster_frame)
		p_layout.setContentsMargins(0, 0, 0, 0)
		self.poster_label = QLabel(self.poster_frame)
		self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.poster_label.setObjectName(POSTER_LABEL_NAME)
		p_layout.addWidget(self.poster_label)
		layout.addWidget(self.poster_frame)

		# Title (Multi-line elision + tooltip)
		name = getattr(self.plugin, "game_name", "") or getattr(self.plugin, "game_id", "Game")
		self.title_label = StrongBodyLabel(self)
		self.title_label.setWordWrap(True)
		self.title_label.setFixedHeight(40)
		self.title_label.setText(elide_multiline_text(name, self.title_label.font(), 230, max_lines=2))
		self.title_label.setToolTip(name)
		self.title_label.setStyleSheet("StrongBodyLabel { font-size: 14px; font-weight: bold; background: transparent; border: none; padding: 0px; }")
		layout.addWidget(self.title_label)

		# Status Badges Row
		status_row = QHBoxLayout()
		status_row.setSpacing(6)

		if self.is_detected:
			det_badge = CaptionLabel("Installed", self)
			det_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #143322;"
				"  color: #4ade80;"
				"  border: 1px solid #1e5938;"
				"  border-radius: 9999px;"
				"  padding: 2px 10px;"
				"  font-weight: bold;"
				"  font-size: 11px;"
				"}"
			)
			status_row.addWidget(det_badge)
		else:
			sup_badge = CaptionLabel("Supported", self)
			sup_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #26293b;"
				"  color: #a0a6b8;"
				"  border: 1px solid #363a52;"
				"  border-radius: 9999px;"
				"  padding: 2px 10px;"
				"  font-size: 11px;"
				"}"
			)
			status_row.addWidget(sup_badge)

		if self.in_library:
			lib_badge = CaptionLabel("In Library", self)
			lib_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #1e2442;"
				"  color: #5b6cf9;"
				"  border: 1px solid #2f3a6e;"
				"  border-radius: 9999px;"
				"  padding: 2px 10px;"
				"  font-weight: bold;"
				"  font-size: 11px;"
				"}"
			)
			status_row.addWidget(lib_badge)

		status_row.addStretch()
		layout.addLayout(status_row)

		# Action Button Row (Add/Remove & Profile buttons)
		btn_row = QHBoxLayout()
		btn_row.setSpacing(8)

		if self.in_library:
			self.add_btn = PushButton(FIF.DELETE, "Remove", self)
			self.add_btn.setFixedHeight(30)
		else:
			self.add_btn = PrimaryPushButton(FIF.ADD, "Add", self)
			self.add_btn.setFixedHeight(30)

		self.add_btn.clicked.connect(self.toggle_library_requested.emit)
		btn_row.addWidget(self.add_btn)

		view_btn = PushButton(FIF.APPLICATION, "Profile", self)
		view_btn.setFixedHeight(30)
		view_btn.clicked.connect(self.profile_requested.emit)
		btn_row.addWidget(view_btn)

		layout.addLayout(btn_row)
		layout.addStretch()

		self._load_poster()

	def _load_poster(self):
		saved = getattr(self.plugin, "_saved_poster", "")
		if saved and Path(saved).is_file():
			pix = QPixmap(saved)
			if not pix.isNull():
				fit_pixmap_to_label(self.poster_label, pix, QSize(240, 135))
				return

		# Trigger poster preload if needed
		pm = self._posters.plugin_manager()
		if pm is not None:
			pm.ensure_plugin_visual_assets(self.plugin, self._on_assets_ready)

		self.poster_label.clear()
		self.poster_label.setText("GAME")
		self.poster_label.setStyleSheet("QLabel { color: #5b6cf9; font-weight: bold; font-size: 16px; }")

	def _on_assets_ready(self):
		saved = getattr(self.plugin, "_saved_poster", "")
		if saved and Path(saved).is_file():
			pix = QPixmap(saved)
			if not pix.isNull():
				fit_pixmap_to_label(self.poster_label, pix, QSize(240, 135))

	def mousePressEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			self.clicked.emit()
		super().mousePressEvent(event)


class ModernGameStoreInterface(QWidget):
	"""Game Store view for browsing supported plugins, detecting installed games,

	and adding games to the user's Library.
	"""

	game_profile_requested = pyqtSignal(object)  # GameProfile
	profiles_changed = pyqtSignal()

	_CARD_GRID_SIZE = QSize(275, 290)

	def __init__(
		self,
		config: ConfigManager,
		plugin_manager: PluginManager,
		poster_refresh: PosterRefreshCoordinator | None = None,
		parent=None,
	):
		super().__init__(parent)
		self.config = config
		self.plugin_manager = plugin_manager
		self._poster_refresh = poster_refresh
		self._posters = ProfilePosterService(
			self, plugin_manager=plugin_manager, app_dir=config.app_dir
		)
		self._detected_game_ids: set[str] = set()

		self._setup_ui()
		self._scan_detected_games_initial()
		self._load_store()
		if self._poster_refresh is not None:
			self._poster_refresh.register(self.refresh_posters)

	def _setup_ui(self):
		layout = QVBoxLayout(self)
		layout.setContentsMargins(24, 20, 24, 24)
		layout.setSpacing(18)

		# Top Header Row
		header = QHBoxLayout()
		header.setSpacing(12)

		title_v = QVBoxLayout()
		title_v.setSpacing(2)
		self.title_label = StrongBodyLabel("Game Store")
		self.title_label.setStyleSheet("StrongBodyLabel { font-size: 24px; font-weight: bold; background: transparent; border: none; }")
		self.count_label = CaptionLabel("0 Supported Games")
		self.count_label.setStyleSheet("CaptionLabel { color: #858b9c; font-size: 13px; background: transparent; border: none; }")
		title_v.addWidget(self.title_label)
		title_v.addWidget(self.count_label)
		header.addLayout(title_v)

		header.addStretch()

		# Search Box
		self.search_edit = LineEdit()
		self.search_edit.setPlaceholderText("Search supported games...")
		self.search_edit.setFixedWidth(240)
		self.search_edit.textChanged.connect(self._on_search_changed)
		header.addWidget(self.search_edit)

		# Filter Combo
		self.filter_combo = ComboBox()
		self.filter_combo.addItem("All Games")
		self.filter_combo.addItem("Installed on System")
		self.filter_combo.addItem("In Library")
		self.filter_combo.addItem("Available to Add")
		self.filter_combo.setFixedWidth(160)
		self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
		header.addWidget(self.filter_combo)

		# View Mode Toggle (Cards / List)
		self.view_toggle = ComboBox()
		self.view_toggle.addItem("Cards")
		self.view_toggle.addItem("List")
		self.view_toggle.setFixedWidth(100)
		self.view_toggle.currentTextChanged.connect(self._on_view_mode_changed)
		header.addWidget(self.view_toggle)

		# Detect Installed Button
		self.detect_btn = PrimaryPushButton(FIF.SEARCH, "Detect Installed Games")
		self.detect_btn.setFixedHeight(34)
		self.detect_btn.clicked.connect(self._detect_games)
		header.addWidget(self.detect_btn)

		# Reload Plugins Button (Dev mode)
		self.reload_btn = PushButton(FIF.SYNC, "Reload Plugins")
		self.reload_btn.setFixedHeight(34)
		self.reload_btn.clicked.connect(self._reload_plugins)
		self.reload_btn.setVisible(is_developer_mode(self.config))
		header.addWidget(self.reload_btn)

		layout.addLayout(header)

		# Content Container
		self.content_container = QWidget()
		self.content_layout = QVBoxLayout(self.content_container)
		self.content_layout.setContentsMargins(0, 0, 0, 0)
		self.content_layout.setSpacing(12)

		# 1. Cards Grid View
		self.card_list = QListWidget()
		self.card_list.setViewMode(QListView.ViewMode.IconMode)
		self.card_list.setGridSize(self._CARD_GRID_SIZE)
		self.card_list.setSpacing(12)
		self.card_list.setStyleSheet(LIST_STYLE_TRANSPARENT)
		self.card_list.setDragEnabled(False)
		self.card_list.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
		self.card_list.setMovement(QListView.Movement.Static)
		self.card_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
		self.card_list.setFlow(QListView.Flow.LeftToRight)
		self.card_list.setWrapping(True)
		self.card_list.setResizeMode(QListView.ResizeMode.Adjust)
		self.card_list.setUniformItemSizes(True)
		self.content_layout.addWidget(self.card_list)

		# 2. Table List View
		self.table_view = TableWidget()
		self.table_view.setColumnCount(5)
		self.table_view.setHorizontalHeaderLabels(
			["Game", "Version", "System Detection", "Library Status", "Actions"]
		)
		t_header = self.table_view.horizontalHeader()
		t_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
		t_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
		t_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
		t_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
		t_header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
		self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
		self.table_view.setAlternatingRowColors(True)
		styles = AdaptiveThemeStyles()
		styles.apply_table_style(self.table_view)
		_install_read_only_table(self.table_view)
		self.table_view.itemDoubleClicked.connect(self._on_table_item_double_clicked)
		self.content_layout.addWidget(self.table_view)

		layout.addWidget(self.content_container)

	def _scan_detected_games_initial(self):
		"""Quick initial scan for detected games."""
		self._detected_game_ids = set()
		for p in self.plugin_manager.plugins.values():
			try:
				if hasattr(p, "is_detected") and p.is_detected():
					self._detected_game_ids.add(p.game_id)
			except Exception:
				pass

	def _detect_games(self):
		"""Deep detection scan with toast summary."""
		found = []
		for p in self.plugin_manager.plugins.values():
			try:
				if hasattr(p, "is_detected") and p.is_detected():
					self._detected_game_ids.add(p.game_id)
					found.append(p.game_name or p.game_id)
			except Exception:
				pass

		self._load_store()

		if found:
			InfoBar.success(
				title="Games Detected",
				content=f"Found {len(found)} installed game(s) on your system: {', '.join(found[:3])}{'...' if len(found) > 3 else ''}",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=4000,
			)
		else:
			InfoBar.info(
				title="Detection Complete",
				content="No installed games were detected at standard default save/registry locations.",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
			)

	def _load_store(self):
		"""Populate store items."""
		self.card_list.clear()
		self.table_view.setRowCount(0)

		query = self.search_edit.text().strip().lower()
		filter_type = self.filter_combo.currentText()
		view_mode = self.view_toggle.currentText().lower()

		plugins = list(self.plugin_manager.plugins.values())
		self.count_label.setText(f"{len(plugins)} Supported Game(s)")

		# Existing library game IDs
		library_plugin_ids = {
			prof.plugin_id
			for prof in self.config.games.values()
			if prof.plugin_id
		}

		filtered = []
		for plug in plugins:
			gid = getattr(plug, "game_id", "")
			name = getattr(plug, "game_name", "") or gid
			is_det = gid in self._detected_game_ids
			in_lib = gid in library_plugin_ids

			if query and query not in name.lower() and query not in gid.lower():
				continue

			if filter_type == "Installed on System" and not is_det:
				continue
			if filter_type == "In Library" and not in_lib:
				continue
			if filter_type == "Available to Add" and in_lib:
				continue

			filtered.append((plug, is_det, in_lib))

		if view_mode == "list":
			self.card_list.hide()
			self.table_view.show()
			self.table_view.setRowCount(len(filtered))

			for row, (plug, is_det, in_lib) in enumerate(filtered):
				name = getattr(plug, "game_name", "") or getattr(plug, "game_id", "Game")
				version = getattr(plug, "version", "1.0.0")
				det_text = "Installed / Save Files Found" if is_det else "Supported"
				lib_text = "In Library" if in_lib else "Not Added"

				self.table_view.setItem(row, 0, QTableWidgetItem(name))
				self.table_view.setItem(row, 1, QTableWidgetItem(version))
				self.table_view.setItem(row, 2, QTableWidgetItem(det_text))
				self.table_view.setItem(row, 3, QTableWidgetItem(lib_text))

				# Actions
				act_w = QWidget()
				act_lay = QHBoxLayout(act_w)
				act_lay.setContentsMargins(4, 2, 4, 2)
				act_lay.setSpacing(6)

				view_btn = PushButton(FIF.APPLICATION, "Profile")
				view_btn.setFixedHeight(26)
				view_btn.clicked.connect(lambda _, p=plug: self._open_profile_for_plugin(p))
				act_lay.addWidget(view_btn)

				if in_lib:
					toggle_btn = PushButton(FIF.DELETE, "Remove")
					toggle_btn.setFixedHeight(26)
					toggle_btn.clicked.connect(lambda _, p=plug: self._toggle_plugin_in_library(p, in_library=True))
				else:
					toggle_btn = PrimaryPushButton(FIF.ADD, "Add")
					toggle_btn.setFixedHeight(26)
					toggle_btn.clicked.connect(lambda _, p=plug: self._toggle_plugin_in_library(p, in_library=False))

				act_lay.addWidget(toggle_btn)
				self.table_view.setCellWidget(row, 4, act_w)

		else:
			self.table_view.hide()
			self.card_list.show()

			for plug, is_det, in_lib in filtered:
				card = StoreCardWidget(
					plug,
					self.config,
					self._posters,
					is_detected=is_det,
					in_library=in_lib,
					parent=self.card_list,
				)
				card.clicked.connect(lambda p=plug: self._open_profile_for_plugin(p))
				card.profile_requested.connect(lambda p=plug: self._open_profile_for_plugin(p))
				card.toggle_library_requested.connect(lambda p=plug, lib=in_lib: self._toggle_plugin_in_library(p, lib))

				item = QListWidgetItem(self.card_list)
				item.setSizeHint(self._CARD_GRID_SIZE)
				item.setData(Qt.ItemDataRole.UserRole, plug)
				self.card_list.addItem(item)
				self.card_list.setItemWidget(item, card)

	def _open_profile_for_plugin(self, plugin: object):
		gid = getattr(plugin, "game_id", "")
		# Check if already in config.games
		existing = None
		for prof in self.config.games.values():
			if prof.plugin_id == gid:
				existing = prof
				break

		if existing is None:
			# Ephemeral profile for viewing
			existing = GameProfile(
				id=gid,
				name=getattr(plugin, "game_name", "") or gid,
				plugin_id=gid,
				plugin_version=getattr(plugin, "version", "1.0.0"),
			)

		self.game_profile_requested.emit(existing)

	def _toggle_plugin_in_library(self, plugin: object, in_library: bool):
		gid = getattr(plugin, "game_id", "")
		name = getattr(plugin, "game_name", "") or gid

		if in_library:
			# Remove from library
			target_id = None
			for pid, prof in self.config.games.items():
				if prof.plugin_id == gid or prof.id == gid:
					target_id = pid
					break
			if target_id and target_id in self.config.games:
				del self.config.games[target_id]
				self.config.save_config()
				self._load_store()
				self.profiles_changed.emit()
				InfoBar.success(
					title="Removed from Library",
					content=f"{name} removed from your Library.",
					parent=toast_parent(self),
					position=InfoBarPosition.TOP,
					duration=2500,
				)
		else:
			# Add to library
			new_prof = GameProfile(
				id=gid,
				name=name,
				plugin_id=gid,
				plugin_version=getattr(plugin, "version", "1.0.0"),
			)
			self.config.games[gid] = new_prof
			self.config.save_config()
			self._load_store()
			self.profiles_changed.emit()
			InfoBar.success(
				title="Added to Library",
				content=f"{name} added to your Library!",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=2500,
			)

	def _on_search_changed(self, text: str):
		self._load_store()

	def _on_filter_changed(self, text: str):
		self._load_store()

	def _on_view_mode_changed(self, text: str):
		self._load_store()

	def _on_table_item_double_clicked(self, item: QTableWidgetItem):
		row = item.row()
		plugins = list(self.plugin_manager.plugins.values())
		if 0 <= row < len(plugins):
			self._open_profile_for_plugin(plugins[row])

	def _reload_plugins(self):
		hot = getattr(self.window(), "_plugin_hot", None)
		if hot is not None and hasattr(hot, "reload_now"):
			hot.reload_now(reason="manual button")
			return
		report = self.plugin_manager.reload_plugins(hot=True)
		self._scan_detected_games_initial()
		self._load_store()
		InfoBar.success(
			title="Plugins Reloaded",
			content=f"Loaded {len(self.plugin_manager.plugins)} plugin(s).",
			parent=toast_parent(self),
			position=InfoBarPosition.TOP,
		)

	def reload(self):
		self._scan_detected_games_initial()
		self._load_store()

	def refresh_posters(self, plugin_game_id: str | None = None) -> None:
		self._load_store()
