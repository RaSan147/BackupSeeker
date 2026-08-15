from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QEvent, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
from PyQt6.QtWidgets import (
	QAbstractItemView,
	QApplication,
	QFrame,
	QGridLayout,
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
	CardWidget,
	ComboBox,
	Dialog as FluentDialog,
	ElevatedCardWidget,
	FluentIcon as FIF,
	InfoBar,
	InfoBarPosition,
	LineEdit,
	PrimaryPushButton,
	PushButton,
	RoundMenu,
	Action,
	SimpleCardWidget,
	StrongBodyLabel,
	SubtitleLabel,
	TableWidget,
	TitleLabel,
	TransparentPushButton,
)

from ..core import ConfigManager, GameProfile, PathUtils, run_backup
from ..developer_mode import set_dev_widgets_visible
from ..fluent_window import resolve_plugin_for_profile, toast_parent
from ..modern_widgets import ModernGameEditor, RoundedCard
from ..ui_shared import confirm_action, open_path_in_explorer
from .helpers import (
	_install_read_only_table,
	_profile_display_name,
	_profile_kind_prefix,
	apply_combo_ui_view,
	last_backup_label,
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


class GameCardWidget(RoundedCard):
	"""Modern Hydra-style game card for Library & Store grids."""

	clicked = pyqtSignal()
	profile_requested = pyqtSignal()
	backup_requested = pyqtSignal()
	remove_requested = pyqtSignal()

	_CARD_POSTER_SIZE = QSize(240, 135)

	def __init__(self, profile: GameProfile, config: ConfigManager, poster_service: ProfilePosterService, parent=None):
		super().__init__(parent)
		self.profile = profile
		self.config = config
		self._posters = poster_service
		self.setFixedSize(260, 270)
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

		# Game Title (Multi-line elision + tooltip)
		plugin = resolve_plugin_for_profile(self.profile, self)
		title_text = self.profile.resolved_name(plugin)
		self.title_label = StrongBodyLabel(self)
		self.title_label.setWordWrap(True)
		self.title_label.setFixedHeight(40)
		self.title_label.setText(elide_multiline_text(title_text, self.title_label.font(), 230, max_lines=2))
		self.title_label.setToolTip(title_text)
		self.title_label.setStyleSheet("StrongBodyLabel { font-size: 14px; font-weight: bold; background: transparent; border: none; padding: 0px; }")
		layout.addWidget(self.title_label)

		# Subtitle / Status Row
		sub_row = QHBoxLayout()
		sub_row.setSpacing(6)

		# Badge
		kind_text = "Store" if self.profile.plugin_id else "Custom"
		self.badge = CaptionLabel(kind_text, self)
		self.badge.setStyleSheet(
			"CaptionLabel {"
			"  background-color: #26293b;"
			"  color: #a0a6b8;"
			"  border: 1px solid #363a52;"
			"  border-radius: 9999px;"
			"  padding: 2px 10px;"
			"  font-size: 11px;"
			"}"
		)
		sub_row.addWidget(self.badge)

		# Last backup text
		bk_text = last_backup_label(self.profile, self, self.config)
		self.backup_label = CaptionLabel(bk_text, self)
		self.backup_label.setStyleSheet("CaptionLabel { color: #858b9c; font-size: 11px; background: transparent; border: none; padding: 0px; }")
		sub_row.addWidget(self.backup_label)
		sub_row.addStretch()

		layout.addLayout(sub_row)
		layout.addStretch()

		self._load_poster()

	def _load_poster(self):
		p_path = self._posters.poster_path(self.profile, on_complete=self._load_poster)
		if p_path and Path(p_path).is_file():
			pix = QPixmap(p_path)
			if not pix.isNull():
				fit_pixmap_to_label(self.poster_label, pix, QSize(240, 135))
				return

		self.poster_label.clear()
		self.poster_label.setText("GAME")
		self.poster_label.setStyleSheet("QLabel { color: #5b6cf9; font-weight: bold; font-size: 16px; }")

	def mousePressEvent(self, event):
		if event.button() == Qt.MouseButton.LeftButton:
			self.clicked.emit()
		super().mousePressEvent(event)

	def contextMenuEvent(self, event):
		menu = RoundMenu(parent=self)
		act_profile = Action(FIF.APPLICATION, "View Game Profile", self)
		act_profile.triggered.connect(self.profile_requested.emit)
		menu.addAction(act_profile)

		act_backup = Action(FIF.SAVE, "Backup Now", self)
		act_backup.triggered.connect(self.backup_requested.emit)
		menu.addAction(act_backup)

		act_remove = Action(FIF.DELETE, "Remove from Library", self)
		act_remove.triggered.connect(self.remove_requested.emit)
		menu.addAction(act_remove)

		menu.exec(event.globalPos())


class ModernLibraryInterface(QWidget):
	"""Modern Library view with cards/grid, list view, search, filtering,

	and custom game addition.
	"""

	game_profile_requested = pyqtSignal(object)  # GameProfile
	profiles_changed = pyqtSignal()
	navigate_to_store_requested = pyqtSignal()

	_CARD_GRID_SIZE = QSize(275, 285)

	def __init__(
		self,
		config: ConfigManager,
		plugin_manager=None,
		poster_refresh: PosterRefreshCoordinator | None = None,
		parent=None,
	):
		super().__init__(parent)
		self.config = config
		self._plugin_manager = plugin_manager
		self._poster_refresh = poster_refresh
		self._posters = ProfilePosterService(
			self, plugin_manager=plugin_manager, app_dir=config.app_dir
		)
		self._setup_ui()
		self._load_library()
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
		self.title_label = StrongBodyLabel("My Library")
		self.title_label.setStyleSheet("StrongBodyLabel { font-size: 24px; font-weight: bold; background: transparent; border: none; }")
		self.count_label = CaptionLabel("0 Games")
		self.count_label.setStyleSheet("CaptionLabel { color: #858b9c; font-size: 13px; background: transparent; border: none; }")
		title_v.addWidget(self.title_label)
		title_v.addWidget(self.count_label)
		header.addLayout(title_v)

		header.addStretch()

		# Search box
		self.search_edit = LineEdit()
		self.search_edit.setPlaceholderText("Search games in library...")
		self.search_edit.setFixedWidth(240)
		self.search_edit.textChanged.connect(self._on_search_changed)
		header.addWidget(self.search_edit)

		# Filter combo
		self.filter_combo = ComboBox()
		self.filter_combo.addItem("All Games")
		self.filter_combo.addItem("Store Plugins")
		self.filter_combo.addItem("Custom Games")
		self.filter_combo.setFixedWidth(130)
		self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
		header.addWidget(self.filter_combo)

		# View mode toggle (Cards / List)
		self.view_toggle = ComboBox()
		self.view_toggle.addItem("Cards")
		self.view_toggle.addItem("List")
		self.view_toggle.setFixedWidth(100)
		self.view_toggle.currentTextChanged.connect(self._on_view_mode_changed)
		header.addWidget(self.view_toggle)
		apply_combo_ui_view(self.view_toggle, self.config.ui_view_dashboard_profiles)

		# Add Custom Game Button
		self.add_custom_btn = PrimaryPushButton(FIF.ADD, "Add Custom Game")
		self.add_custom_btn.setFixedHeight(34)
		self.add_custom_btn.clicked.connect(self._on_add_custom_game)
		header.addWidget(self.add_custom_btn)

		layout.addLayout(header)

		# Content Stack (Cards Grid, Table List, Empty State)
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
		self.table_view.setColumnCount(4)
		self.table_view.setHorizontalHeaderLabels(
			["Game", "Type", "Last Backup", "Actions"]
		)
		t_header = self.table_view.horizontalHeader()
		t_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
		t_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
		t_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
		t_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
		self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
		self.table_view.setAlternatingRowColors(True)
		styles = AdaptiveThemeStyles()
		styles.apply_table_style(self.table_view)
		_install_read_only_table(self.table_view)
		self.table_view.itemDoubleClicked.connect(self._on_table_item_double_clicked)
		self.content_layout.addWidget(self.table_view)

		# 3. Empty State Container
		self.empty_container = QWidget()
		empty_layout = QVBoxLayout(self.empty_container)
		empty_layout.setContentsMargins(40, 60, 40, 60)
		empty_layout.setSpacing(14)

		empty_icon = QLabel()
		empty_icon.setPixmap(FIF.APPLICATION.icon().pixmap(48, 48))
		empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
		empty_icon.setStyleSheet("QLabel { background: transparent; border: none; }")
		empty_layout.addWidget(empty_icon)

		empty_title = StrongBodyLabel("Your Library is Empty")
		empty_title.setStyleSheet("StrongBodyLabel { font-size: 18px; font-weight: bold; background: transparent; border: none; }")
		empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
		empty_layout.addWidget(empty_title)

		empty_sub = CaptionLabel("Discover and add games from Game Store or create a custom game entry.")
		empty_sub.setStyleSheet("CaptionLabel { color: #858b9c; font-size: 13px; background: transparent; border: none; }")
		empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
		empty_layout.addWidget(empty_sub)

		btn_row = QHBoxLayout()
		btn_row.setSpacing(12)
		btn_row.addStretch()

		browse_store_btn = PrimaryPushButton(FIF.MARKET, "Browse Game Store")
		browse_store_btn.clicked.connect(self.navigate_to_store_requested.emit)
		btn_row.addWidget(browse_store_btn)

		create_custom_btn = PushButton(FIF.ADD, "Add Custom Game")
		create_custom_btn.clicked.connect(self._on_add_custom_game)
		btn_row.addWidget(create_custom_btn)

		btn_row.addStretch()
		empty_layout.addLayout(btn_row)

		self.content_layout.addWidget(self.empty_container)

		layout.addWidget(self.content_container)

	def _load_library(self):
		"""Populate games in library."""
		self.card_list.clear()
		self.table_view.setRowCount(0)

		query = self.search_edit.text().strip().lower()
		filter_type = self.filter_combo.currentText()
		view_mode = self.view_toggle.currentText().lower()

		profiles = list(self.config.games.values())
		self.count_label.setText(f"{len(profiles)} Game(s)")

		# Apply filters
		filtered = []
		for p in profiles:
			plug = resolve_plugin_for_profile(p, self)
			name = p.resolved_name(plug).lower()
			if query and query not in name and query not in (p.id or "").lower():
				continue
			if filter_type == "Store Plugins" and not p.plugin_id:
				continue
			if filter_type == "Custom Games" and p.plugin_id:
				continue
			filtered.append((p, plug))

		if not profiles:
			self.empty_container.show()
			self.card_list.hide()
			self.table_view.hide()
			return

		self.empty_container.hide()

		if view_mode == "list":
			self.card_list.hide()
			self.table_view.show()
			self.table_view.setRowCount(len(filtered))

			for row, (p, plug) in enumerate(filtered):
				name_text = p.resolved_name(plug)
				type_text = "Store Plugin" if p.plugin_id else "Custom"
				status_text = p.effective_save_path(plug) or "Configured"
				last_bk = last_backup_label(p, self, self.config)

				# Item 0: Name
				self.table_view.setItem(row, 0, QTableWidgetItem(name_text))
				# Item 1: Type
				self.table_view.setItem(row, 1, QTableWidgetItem(type_text))
				# Item 2: Save Status
				self.table_view.setItem(row, 2, QTableWidgetItem(status_text))
				# Item 3: Last Backup
				self.table_view.setItem(row, 3, QTableWidgetItem(last_bk))

				# Actions widget
				act_w = QWidget()
				act_lay = QHBoxLayout(act_w)
				act_lay.setContentsMargins(4, 2, 4, 2)
				act_lay.setSpacing(6)

				view_btn = PushButton(FIF.APPLICATION, "Profile")
				view_btn.setFixedHeight(26)
				view_btn.clicked.connect(lambda _, prof=p: self.game_profile_requested.emit(prof))
				act_lay.addWidget(view_btn)

				bk_btn = PushButton(FIF.SAVE, "Backup")
				bk_btn.setFixedHeight(26)
				bk_btn.clicked.connect(lambda _, prof=p: self._run_quick_backup(prof))
				act_lay.addWidget(bk_btn)

				del_btn = PushButton(FIF.DELETE, "Remove")
				del_btn.setFixedHeight(26)
				del_btn.clicked.connect(lambda _, prof=p: self._remove_from_library(prof))
				act_lay.addWidget(del_btn)

				self.table_view.setCellWidget(row, 4, act_w)

		else:
			self.table_view.hide()
			self.card_list.show()

			for p, plug in filtered:
				card = GameCardWidget(p, self.config, self._posters, parent=self.card_list)
				card.clicked.connect(lambda prof=p: self.game_profile_requested.emit(prof))
				card.profile_requested.connect(lambda prof=p: self.game_profile_requested.emit(prof))
				card.backup_requested.connect(lambda prof=p: self._run_quick_backup(prof))
				card.remove_requested.connect(lambda prof=p: self._remove_from_library(prof))

				item = QListWidgetItem(self.card_list)
				item.setSizeHint(self._CARD_GRID_SIZE)
				item.setData(Qt.ItemDataRole.UserRole, p)
				self.card_list.addItem(item)
				self.card_list.setItemWidget(item, card)

	def _on_search_changed(self, text: str):
		self._load_library()

	def _on_filter_changed(self, text: str):
		self._load_library()

	def _on_view_mode_changed(self, text: str):
		norm = ui_view_mode_from_combo_text(text)
		self.config.ui_view_dashboard_profiles = norm
		self.config.save_config()
		self._load_library()

	def _on_table_item_double_clicked(self, item: QTableWidgetItem):
		row = item.row()
		# Retrieve profile for this row
		profiles = list(self.config.games.values())
		if 0 <= row < len(profiles):
			self.game_profile_requested.emit(profiles[row])

	def _on_add_custom_game(self):
		"""Open modern game editor to create a custom profile."""
		editor = ModernGameEditor(None, self.config, self)
		if editor.exec():
			new_prof = editor.get_profile()
			self.config.games[new_prof.id] = new_prof
			self.config.save_config()
			self.reload()
			self.profiles_changed.emit()
			InfoBar.success(
				title="Custom Game Added",
				content=f"{new_prof.name} added to your library!",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
			)

	def _run_quick_backup(self, profile: GameProfile):
		try:
			plugin = resolve_plugin_for_profile(profile, self)
			dest = run_backup(profile, self.config, plugin)
			if dest and dest.exists():
				InfoBar.success(
					title="Backup Successful",
					content=f"Saved backup: {dest.name}",
					parent=toast_parent(self),
					position=InfoBarPosition.TOP,
					duration=3500,
				)
				self._load_library()
		except Exception as e:
			InfoBar.error(
				title="Backup Failed",
				content=str(e),
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
			)

	def _remove_from_library(self, profile: GameProfile):
		plugin = resolve_plugin_for_profile(profile, self)
		name = profile.resolved_name(plugin)
		ok = confirm_action(
			self,
			"Remove from Library",
			f"Are you sure you want to remove '{name}' from your Library?",
		)
		if ok and profile.id in self.config.games:
			del self.config.games[profile.id]
			self.config.save_config()
			self.reload()
			self.profiles_changed.emit()
			InfoBar.success(
				title="Removed",
				content=f"'{name}' removed from your library.",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=2500,
			)

	def reload(self):
		self._load_library()

	def refresh_posters(self, plugin_game_id: str | None = None) -> None:
		self._load_library()
