from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
	QAbstractItemView,
	QFileDialog,
	QFrame,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QListWidgetItem,
	QTableWidgetItem,
	QVBoxLayout,
	QWidget,
)
from qfluentwidgets import (
	BodyLabel,
	CaptionLabel,
	InfoBar,
	InfoBarPosition,
	LineEdit,
	ListWidget,
	PlainTextEdit,
	PrimaryPushButton,
	PushButton,
	SegmentedWidget,
	SimpleCardWidget,
	SingleDirectionScrollArea,
	StrongBodyLabel,
	TableWidget,
	TitleLabel,
	TransparentPushButton,
	setCustomStyleSheet,
)
from qfluentwidgets import (
	Dialog as FluentDialog,
)
from qfluentwidgets import (
	FluentIcon as FIF,
)

from ..core import (
	ConfigManager,
	GameProfile,
	PathUtils,
	read_archive_metadata,
	run_backup,
	run_restore,
	summarize_archive_metadata,
	verify_save_locations_report,
)
from ..fluent_window import resolve_plugin_for_profile, toast_parent
from ..modern_widgets import ModernGameEditor
from ..plugin_runtime import run_plugin_hook
from ..ui_shared import (
	confirm_action,
	ensure_plugin_restore_inputs,
	offer_plugin_restore_input_review,
	open_path_in_explorer,
)
from .helpers import (
	_install_read_only_table,
	format_verify_report_text,
)
from .poster_refresh import PosterRefreshCoordinator
from .profile_visuals import (
	POSTER_LABEL_NAME,
	ProfilePosterService,
	fit_pixmap_to_label,
)
from .restore_dialog import RestoreBackupDialog
from .verify_dialog import VerifySaveDialog
from .styles import AdaptiveThemeStyles


class ModernGameProfileInterface(SingleDirectionScrollArea):
	"""Comprehensive Game Profile view.

	Provides 1-click Backup, Restore, Executable Finder & Launcher,
	Save Locations Verification, and Single-Game Backup History.
	"""

	back_requested = pyqtSignal()
	profiles_changed = pyqtSignal()
	backup_requested = pyqtSignal()

	_HERO_POSTER_SIZE = QSize(240, 135)

	def __init__(
		self,
		config: ConfigManager,
		plugin_manager=None,
		poster_refresh: PosterRefreshCoordinator | None = None,
		parent=None,
	):
		super().__init__(orient=Qt.Orientation.Vertical, parent=parent)
		self.config = config
		self._plugin_manager = plugin_manager
		self._poster_refresh = poster_refresh
		self._posters = ProfilePosterService(
			self, plugin_manager=plugin_manager, app_dir=config.app_dir
		)
		self.current_profile: GameProfile | None = None
		self.current_plugin: object | None = None
		self.source_view: str = "library"  # "library" or "store"
		self._backup_rows: list[dict[str, Any]] = []

		self.setWidgetResizable(True)
		self.setStyleSheet("SingleDirectionScrollArea { background: transparent; border: none; }")
		self.scroll_content = QWidget(self)
		self.scroll_content.setObjectName("profileScrollContent")
		self.scroll_content.setStyleSheet("#profileScrollContent { background: transparent; }")
		self.setWidget(self.scroll_content)

		self._setup_ui()
		if self._poster_refresh is not None:
			self._poster_refresh.register(self._on_posters_refreshed)

	def _setup_ui(self):
		main_layout = QVBoxLayout(self.scroll_content)
		main_layout.setContentsMargins(24, 20, 24, 24)
		main_layout.setSpacing(18)

		# Top Navigation Bar (Back button + Source breadcrumb)
		top_bar = QHBoxLayout()
		self.back_btn = PushButton(FIF.LEFT_ARROW, "Back")
		self.back_btn.setFixedHeight(32)
		self.back_btn.clicked.connect(self._on_back_clicked)
		top_bar.addWidget(self.back_btn)

		self.breadcrumb_label = CaptionLabel("Library > Game Profile")
		self.breadcrumb_label.setStyleSheet(
			"CaptionLabel {"
			"  color: #858b9c;"
			"  font-size: 12px;"
			"  background-color: #1e202e;"
			"  border: 1px solid #2b2e42;"
			"  border-radius: 9999px;"
			"  padding: 4px 14px;"
			"}"
		)
		top_bar.addWidget(self.breadcrumb_label)
		top_bar.addStretch()

		main_layout.addLayout(top_bar)

		# Hero Header Card (Cover Art + Title + Status Badges + Action Buttons)
		self.hero_card = SimpleCardWidget(self.scroll_content)
		self.hero_card.setObjectName("heroCard")
		self.hero_card.setStyleSheet(
			"SimpleCardWidget#heroCard {"
			"  background-color: #181a24;"
			"  border: 1px solid #2b2e42;"
			"  border-radius: 12px;"
			"}"
			"SimpleCardWidget#heroCard QLabel, SimpleCardWidget#heroCard TitleLabel, SimpleCardWidget#heroCard BodyLabel, SimpleCardWidget#heroCard CaptionLabel, SimpleCardWidget#heroCard StrongBodyLabel {"
			"  background-color: transparent;"
			"  border: none;"
			"}"
		)
		hero_layout = QHBoxLayout(self.hero_card)
		hero_layout.setContentsMargins(20, 20, 20, 20)
		hero_layout.setSpacing(24)

		# Left: Poster Image Frame
		self.poster_frame = QFrame()
		self.poster_frame.setFixedSize(self._HERO_POSTER_SIZE)
		self.poster_frame.setStyleSheet(
			"QFrame {"
			"  background-color: #12131a;"
			"  border: 1px solid #2b2e42;"
			"  border-radius: 8px;"
			"}"
		)
		poster_frame_layout = QVBoxLayout(self.poster_frame)
		poster_frame_layout.setContentsMargins(0, 0, 0, 0)
		self.poster_label = QLabel()
		self.poster_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.poster_label.setObjectName(POSTER_LABEL_NAME)
		poster_frame_layout.addWidget(self.poster_label)
		hero_layout.addWidget(self.poster_frame)

		# Middle / Right: Game Details & Hero Actions
		info_layout = QVBoxLayout()
		info_layout.setSpacing(10)

		# Badges row
		badges_row = QHBoxLayout()
		badges_row.setSpacing(8)

		self.type_badge = CaptionLabel("Store Plugin")
		self.type_badge.setStyleSheet(
			"CaptionLabel {"
			"  background-color: #26293b;"
			"  color: #a0a6b8;"
			"  border: 1px solid #363a52;"
			"  border-radius: 9999px;"
			"  padding: 3px 12px;"
			"  font-weight: bold;"
			"  font-size: 11px;"
			"}"
		)
		badges_row.addWidget(self.type_badge)

		self.status_badge = CaptionLabel("Ready")
		self.status_badge.setStyleSheet(
			"CaptionLabel {"
			"  background-color: #1a3328;"
			"  color: #4ade80;"
			"  border: 1px solid #234c38;"
			"  border-radius: 9999px;"
			"  padding: 3px 12px;"
			"  font-weight: bold;"
			"  font-size: 11px;"
			"}"
		)
		badges_row.addWidget(self.status_badge)

		self.library_badge = CaptionLabel("In Library")
		self.library_badge.setStyleSheet(
			"CaptionLabel {"
			"  background-color: #2b2e42;"
			"  color: #5b6cf9;"
			"  border: 1px solid #3f4460;"
			"  border-radius: 9999px;"
			"  padding: 3px 12px;"
			"  font-weight: bold;"
			"  font-size: 11px;"
			"}"
		)
		badges_row.addWidget(self.library_badge)
		badges_row.addStretch()

		info_layout.addLayout(badges_row)

		# Title
		self.title_label = TitleLabel("Game Profile")
		self.title_label.setWordWrap(True)
		self.title_label.setStyleSheet("TitleLabel { font-size: 24px; font-weight: bold; background: transparent; border: none; padding: 0px; color: #ffffff; }")
		info_layout.addWidget(self.title_label)

		# Subtitle / Save summary
		self.summary_label = BodyLabel("Configured Save Locations")
		self.summary_label.setWordWrap(True)
		self.summary_label.setStyleSheet("BodyLabel { color: #a0a6b8; font-size: 13px; background: transparent; border: none; padding: 0px; }")
		info_layout.addWidget(self.summary_label)

		info_layout.addSpacing(6)

		# Action Button Bars (Clean 2-row layout to prevent button text clipping)
		# Row 1: Primary game actions
		actions_row_1 = QHBoxLayout()
		actions_row_1.setSpacing(10)

		self.backup_btn = PrimaryPushButton(FIF.SAVE, "Backup Now")
		self.backup_btn.setFixedHeight(34)
		self.backup_btn.clicked.connect(self._on_backup_clicked)
		actions_row_1.addWidget(self.backup_btn)

		self.restore_btn = PushButton(FIF.HISTORY, "Restore Backup")
		self.restore_btn.setFixedHeight(34)
		self.restore_btn.clicked.connect(self._on_restore_clicked)
		actions_row_1.addWidget(self.restore_btn)

		self.launch_btn = PushButton(FIF.PLAY, "Launch Game")
		self.launch_btn.setFixedHeight(34)
		self.launch_btn.clicked.connect(self._on_launch_clicked)
		actions_row_1.addWidget(self.launch_btn)

		self.library_toggle_btn = PushButton(FIF.ADD, "Add to Library")
		self.library_toggle_btn.setFixedHeight(34)
		self.library_toggle_btn.clicked.connect(self._on_library_toggle_clicked)
		actions_row_1.addWidget(self.library_toggle_btn)
		actions_row_1.addStretch()
		info_layout.addLayout(actions_row_1)

		# Row 2: Secondary / Tool actions
		actions_row_2 = QHBoxLayout()
		actions_row_2.setSpacing(10)

		self.open_save_btn = PushButton(FIF.FOLDER, "Save Folder")
		self.open_save_btn.setFixedHeight(32)
		self.open_save_btn.clicked.connect(self._on_open_save_folder)
		actions_row_2.addWidget(self.open_save_btn)

		self.open_backup_btn = PushButton(FIF.FOLDER_ADD, "Backup Folder")
		self.open_backup_btn.setFixedHeight(32)
		self.open_backup_btn.clicked.connect(self._on_open_backup_folder)
		actions_row_2.addWidget(self.open_backup_btn)

		self.verify_btn = PushButton(FIF.ACCEPT, "Verify Saves")
		self.verify_btn.setFixedHeight(32)
		self.verify_btn.clicked.connect(self._on_verify_saves)
		actions_row_2.addWidget(self.verify_btn)

		self.edit_btn = PushButton(FIF.EDIT, "Edit Profile")
		self.edit_btn.setFixedHeight(32)
		self.edit_btn.clicked.connect(self._on_edit_profile)
		actions_row_2.addWidget(self.edit_btn)
		actions_row_2.addStretch()
		info_layout.addLayout(actions_row_2)

		hero_layout.addLayout(info_layout)
		main_layout.addWidget(self.hero_card)

		# Content Section Header & Segmented Tabs
		tab_header = QHBoxLayout()
		self.tab_segment = SegmentedWidget(self)
		self.tab_segment.addItem(routeKey="backups", text="Backups History", icon=FIF.SAVE, onClick=lambda: self._switch_tab("backups"))
		self.tab_segment.addItem(routeKey="game_info", text="Game Settings and Executable", icon=FIF.SETTING, onClick=lambda: self._switch_tab("game_info"))
		self.tab_segment.setCurrentItem("backups")
		tab_header.addWidget(self.tab_segment)
		tab_header.addStretch()

		# Quick Refresh / Delete all actions for backups
		self.delete_all_backups_btn = TransparentPushButton(FIF.DELETE, "Delete All Backups")
		self.delete_all_backups_btn.clicked.connect(self._on_delete_all_backups)
		tab_header.addWidget(self.delete_all_backups_btn)

		main_layout.addLayout(tab_header)

		# Tab Content Stack Container
		self.tab_container = QWidget()
		self.tab_layout = QVBoxLayout(self.tab_container)
		self.tab_layout.setContentsMargins(0, 0, 0, 0)
		self.tab_layout.setSpacing(12)

		# --- Tab 1: Backups Page ---
		self.backups_tab_widget = QWidget()
		backups_layout = QVBoxLayout(self.backups_tab_widget)
		backups_layout.setContentsMargins(0, 0, 0, 0)
		backups_layout.setSpacing(10)

		# Backups Table
		self.backups_table = TableWidget()
		self.backups_table.setColumnCount(6)
		self.backups_table.setHorizontalHeaderLabels(
			["Type", "Date & Time", "Size", "Archive Contents", "Filename", "Actions"]
		)
		header = self.backups_table.horizontalHeader()
		header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
		header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
		header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
		header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
		header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
		header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
		self.backups_table.setWordWrap(False)
		self.backups_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
		self.backups_table.setAlternatingRowColors(True)
		self.backups_table.setMinimumHeight(280)
		styles = AdaptiveThemeStyles()
		styles.apply_table_style(self.backups_table)
		_install_read_only_table(self.backups_table)
		backups_layout.addWidget(self.backups_table)

		# --- Tab 2: Game Settings & Executable Info ---
		self.info_tab_widget = QWidget()
		info_tab_layout = QVBoxLayout(self.info_tab_widget)
		info_tab_layout.setContentsMargins(0, 0, 0, 0)
		info_tab_layout.setSpacing(16)

		# 1. Executable Finder & Configuration Card
		self.exe_card = SimpleCardWidget(self.scroll_content)
		self.exe_card.setObjectName("exeCard")
		self.exe_card.setStyleSheet(
			"SimpleCardWidget#exeCard {"
			"  background-color: #181a24;"
			"  border: 1px solid #2b2e42;"
			"  border-radius: 10px;"
			"  padding: 16px;"
			"}"
			"SimpleCardWidget#exeCard > QLabel, SimpleCardWidget#exeCard StrongBodyLabel, SimpleCardWidget#exeCard CaptionLabel, SimpleCardWidget#exeCard BodyLabel {"
			"  background-color: transparent;"
			"  border: none;"
			"}"
		)
		exe_card_layout = QVBoxLayout(self.exe_card)
		exe_card_layout.setSpacing(12)

		exe_title_row = QHBoxLayout()
		exe_title_lbl = StrongBodyLabel("Game Executable")
		exe_title_lbl.setStyleSheet("StrongBodyLabel { background: transparent; border: none; font-size: 14px; font-weight: bold; }")
		exe_title_row.addWidget(exe_title_lbl)
		exe_title_row.addStretch()

		self.scan_exe_btn = PushButton(FIF.SEARCH, "Auto-Detect Executables")
		self.scan_exe_btn.clicked.connect(self._on_scan_executables)
		exe_title_row.addWidget(self.scan_exe_btn)
		exe_card_layout.addLayout(exe_title_row)

		# Executable path edit row
		exe_edit_row = QHBoxLayout()
		self.exe_path_edit = LineEdit()
		self.exe_path_edit.setPlaceholderText("Select or enter path to game executable (.exe)...")
		self.exe_path_edit.textChanged.connect(self._on_exe_path_edited)
		exe_edit_row.addWidget(self.exe_path_edit)

		self.browse_exe_btn = PushButton(FIF.FOLDER, "Browse...")
		self.browse_exe_btn.clicked.connect(self._on_browse_executable)
		exe_edit_row.addWidget(self.browse_exe_btn)

		self.save_exe_btn = PrimaryPushButton(FIF.ACCEPT, "Save Path")
		self.save_exe_btn.clicked.connect(self._on_save_executable_path)
		exe_edit_row.addWidget(self.save_exe_btn)

		exe_card_layout.addLayout(exe_edit_row)

		# Discovered Executables List
		self.discovered_exe_label = CaptionLabel("Discovered Candidates on Machine:")
		self.discovered_exe_label.setStyleSheet("CaptionLabel { color: #858b9c; font-weight: bold; background: transparent; border: none; }")
		self.discovered_exe_label.setVisible(False)
		exe_card_layout.addWidget(self.discovered_exe_label)

		self.discovered_exe_list = ListWidget()
		self.discovered_exe_list.setObjectName("discoveredExeList")
		_exe_list_light_qss = (
			"ListWidget#discoveredExeList { background-color: #e8eaf0; border: 1px solid #d0d3e0; border-radius: 6px; padding: 4px; }"
			"ListWidget#discoveredExeList::item { padding: 6px 10px; border-radius: 4px; }"
			"ListWidget#discoveredExeList::item:hover { background-color: #e0e3ed; }"
			"ListWidget#discoveredExeList::item:selected { background-color: #4f46e5; color: #ffffff; }"
		)
		_exe_list_dark_qss = (
			"ListWidget#discoveredExeList { background-color: #12131a; border: 1px solid #2b2e42; border-radius: 6px; color: #ffffff; padding: 4px; }"
			"ListWidget#discoveredExeList::item { padding: 6px 10px; border-radius: 4px; color: #ffffff; background: transparent; }"
			"ListWidget#discoveredExeList::item:hover { background-color: #26293b; }"
			"ListWidget#discoveredExeList::item:selected { background-color: #5b6cf9; color: #ffffff; }"
		)
		setCustomStyleSheet(self.discovered_exe_list, _exe_list_light_qss, _exe_list_dark_qss)
		self.discovered_exe_list.itemDoubleClicked.connect(self._on_discovered_exe_double_clicked)
		self.discovered_exe_list.setVisible(False)
		exe_card_layout.addWidget(self.discovered_exe_list)

		info_tab_layout.addWidget(self.exe_card)

		# 2. Save Paths & Locations Card
		self.paths_card = SimpleCardWidget(self.scroll_content)
		self.paths_card.setObjectName("pathsCard")
		self.paths_card.setStyleSheet(
			"SimpleCardWidget#pathsCard {"
			"  background-color: #181a24;"
			"  border: 1px solid #2b2e42;"
			"  border-radius: 10px;"
			"  padding: 16px;"
			"}"
			"SimpleCardWidget#pathsCard > QLabel, SimpleCardWidget#pathsCard StrongBodyLabel, SimpleCardWidget#pathsCard CaptionLabel, SimpleCardWidget#pathsCard BodyLabel {"
			"  background-color: transparent;"
			"  border: none;"
			"}"
		)
		paths_layout = QVBoxLayout(self.paths_card)
		paths_layout.setSpacing(10)
		paths_title_lbl = StrongBodyLabel("Configured Save Locations & Status")
		paths_title_lbl.setStyleSheet("StrongBodyLabel { background: transparent; border: none; font-size: 14px; font-weight: bold; }")
		paths_layout.addWidget(paths_title_lbl)

		self.locations_display = PlainTextEdit()
		self.locations_display.setReadOnly(True)
		self.locations_display.setMinimumHeight(100)
		self.locations_display.setMaximumHeight(180)
		self.locations_display.setStyleSheet(
			"PlainTextEdit, QPlainTextEdit {"
			"  background-color: #12131a;"
			"  color: #a0a6b8;"
			"  border: 1px solid #2b2e42;"
			"  border-radius: 8px;"
			"  padding: 8px 10px;"
			"  font-family: 'Consolas', monospace;"
			"  font-size: 12px;"
			"}"
		)
		paths_layout.addWidget(self.locations_display)
		info_tab_layout.addWidget(self.paths_card)

		info_tab_layout.addStretch()

		# Add tabs to container
		self.tab_layout.addWidget(self.backups_tab_widget)
		self.tab_layout.addWidget(self.info_tab_widget)
		self.info_tab_widget.hide()

		main_layout.addWidget(self.tab_container)

	def _switch_tab(self, route_key: str):
		if route_key == "backups":
			self.info_tab_widget.hide()
			self.backups_tab_widget.show()
			self.delete_all_backups_btn.show()
		else:
			self.backups_tab_widget.hide()
			self.info_tab_widget.show()
			self.delete_all_backups_btn.hide()

	def set_profile(self, profile: GameProfile, source_view: str = "library"):
		"""Load and display the game profile."""
		self.current_profile = profile
		self.source_view = source_view
		self.current_plugin = resolve_plugin_for_profile(profile, self)

		# Breadcrumb
		source_title = "Game Store" if source_view == "store" else "Library"
		self.breadcrumb_label.setText(f"{source_title} > Game Profile")

		# Update hero labels
		display_name = profile.resolved_name(self.current_plugin)
		if len(display_name) > 70:
			font_size = 17
		elif len(display_name) > 40:
			font_size = 20
		else:
			font_size = 24
		self.title_label.setStyleSheet(f"TitleLabel {{ font-size: {font_size}px; font-weight: bold; background: transparent; border: none; padding: 0px; color: #ffffff; }}")
		self.title_label.setText(display_name)
		self.title_label.setToolTip(display_name)

		# Type badge
		if profile.plugin_id:
			pv = getattr(self.current_plugin, "version", "") or profile.plugin_version
			v_str = f" v{pv}" if pv else ""
			self.type_badge.setText(f"Store Plugin{v_str}")
			self.type_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #26293b;"
				"  color: #a0a6b8;"
				"  border: 1px solid #363a52;"
				"  border-radius: 9999px;"
				"  padding: 3px 12px;"
				"  font-weight: bold;"
				"  font-size: 11px;"
				"}"
			)
		else:
			self.type_badge.setText("Custom Game")
			self.type_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #2b2342;"
				"  color: #c084fc;"
				"  border: 1px solid #4a3473;"
				"  border-radius: 9999px;"
				"  padding: 3px 12px;"
				"  font-weight: bold;"
				"  font-size: 11px;"
				"}"
			)

		# In Library status
		in_library = profile.id in self.config.games
		if in_library:
			self.library_badge.setText("In Library")
			self.library_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #1e2442;"
				"  color: #5b6cf9;"
				"  border: 1px solid #2f3a6e;"
				"  border-radius: 9999px;"
				"  padding: 3px 12px;"
				"  font-weight: bold;"
				"  font-size: 11px;"
				"}"
			)
			self.library_toggle_btn.setText("Remove from Library")
			self.library_toggle_btn.setIcon(FIF.DELETE)
		else:
			self.library_badge.setText("Not Added")
			self.library_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #26293b;"
				"  color: #858b9c;"
				"  border: 1px solid #363a52;"
				"  border-radius: 9999px;"
				"  padding: 3px 12px;"
				"  font-weight: bold;"
				"  font-size: 11px;"
				"}"
			)
			self.library_toggle_btn.setText("Add to Library")
			self.library_toggle_btn.setIcon(FIF.ADD)

		# Save detection & status
		self._update_save_detection_status()

		# Executable path
		self.exe_path_edit.setText(profile.executable_path or "")
		self.discovered_exe_list.clear()
		self.discovered_exe_list.setVisible(False)
		self.discovered_exe_label.setVisible(False)

		# Poster loading
		self._load_poster()

		# Refresh backups table
		self._refresh_backups()

	def _update_save_detection_status(self):
		if not self.current_profile:
			return

		rep = verify_save_locations_report(self.current_profile, self.current_plugin)
		locs = rep.get("locations", [])
		total_files = sum(r.get("file_count", 0) for r in locs)
		any_exists = any(r.get("exists", False) for r in locs)
		is_detected = rep.get("plugin_is_detected", False)

		if total_files > 0:
			self.status_badge.setText(f"Ready ({total_files} save files)")
			self.status_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #143322;"
				"  color: #4ade80;"
				"  border: 1px solid #1e5938;"
				"  border-radius: 9999px;"
				"  padding: 3px 12px;"
				"  font-weight: bold;"
				"  font-size: 11px;"
				"}"
			)
		elif any_exists or is_detected:
			self.status_badge.setText("Installed / Folders Ready")
			self.status_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #1a2942;"
				"  color: #60a5fa;"
				"  border: 1px solid #23426b;"
				"  border-radius: 9999px;"
				"  padding: 3px 12px;"
				"  font-weight: bold;"
				"  font-size: 11px;"
				"}"
			)
		else:
			self.status_badge.setText("Not Detected")
			self.status_badge.setStyleSheet(
				"CaptionLabel {"
				"  background-color: #2e2326;"
				"  color: #f87171;"
				"  border: 1px solid #542d34;"
				"  border-radius: 9999px;"
				"  padding: 3px 12px;"
				"  font-weight: bold;"
				"  font-size: 11px;"
				"}"
			)

		# Summary label
		loc_str = self.current_profile.effective_save_path(self.current_plugin)
		self.summary_label.setText(f"Save Roots: {loc_str or 'No save path configured'}")
		self.summary_label.setStyleSheet("BodyLabel { color: #a0a6b8; font-size: 13px; background: transparent; border: none; padding: 0px; }")

		# Locations details
		text_lines = []
		for loc in locs:
			status = "FOUND" if loc.get("exists") else "MISSING"
			files = loc.get("file_count", 0)
			text_lines.append(f"[{status}] {loc.get('logical_key')}: {loc.get('contracted_path')} ({files} files)")
			text_lines.append(f"       Expanded: {loc.get('expanded_path')}")
		self.locations_display.setPlainText("\n".join(text_lines) if text_lines else "No configured save locations.")

	def _load_poster(self):
		if not self.current_profile:
			return
		p_path = self._posters.poster_path(self.current_profile, on_complete=self._load_poster)
		if p_path and Path(p_path).is_file():
			pix = QPixmap(p_path)
			if not pix.isNull():
				fit_pixmap_to_label(self.poster_label, pix, self._HERO_POSTER_SIZE)
				return

		# Fallback icon
		self.poster_label.clear()
		self.poster_label.setText("GAME")
		self.poster_label.setStyleSheet("QLabel { color: #5b6cf9; font-weight: bold; font-size: 18px; }")

	def _on_posters_refreshed(self, plugin_game_id: str | None = None):
		self._load_poster()

	def _on_back_clicked(self):
		self.back_requested.emit()

	def _refresh_backups(self):
		"""Refresh the list of backups for the current profile."""
		self.backups_table.setRowCount(0)
		self._backup_rows = []
		if not self.current_profile:
			return

		backup_dir = self.config.backup_dir_for_profile(self.current_profile, self.current_plugin)
		safety_dir = self.config.safety_backup_dir_for_profile(self.current_profile, self.current_plugin)

		if backup_dir.exists():
			for f in backup_dir.glob("*.zip"):
				try:
					st = f.stat()
					self._backup_rows.append({
						"path_obj": f,
						"type": "Regular",
						"timestamp": st.st_mtime,
						"bytes": st.st_size,
						"filename": f.name,
					})
				except OSError:
					pass

		if safety_dir.exists():
			for f in safety_dir.glob("*.zip"):
				try:
					st = f.stat()
					self._backup_rows.append({
						"path_obj": f,
						"type": "Safety Checkpoint",
						"timestamp": st.st_mtime,
						"bytes": st.st_size,
						"filename": f.name,
					})
				except OSError:
					pass

		# Sort newest first
		self._backup_rows.sort(key=lambda r: r["timestamp"], reverse=True)

		self.backups_table.setRowCount(len(self._backup_rows))
		for row, r in enumerate(self._backup_rows):
			# Type
			type_item = QTableWidgetItem(r["type"])
			type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
			self.backups_table.setItem(row, 0, type_item)

			# Date
			dt = datetime.fromtimestamp(r["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
			self.backups_table.setItem(row, 1, QTableWidgetItem(dt))

			# Size
			sz = r["bytes"]
			sz_disp = f"{sz / 1024 / 1024:.2f} MB" if sz >= 1024 * 1024 else f"{sz / 1024:.1f} KB"
			size_item = QTableWidgetItem(sz_disp)
			size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
			self.backups_table.setItem(row, 2, size_item)

			# Archive summary
			meta = read_archive_metadata(r["path_obj"])
			meta_info = summarize_archive_metadata(meta, zip_path=r["path_obj"]) if meta else {"summary": "Backup Archive"}
			summary = meta_info.get("summary", "Backup Archive") if isinstance(meta_info, dict) else str(meta_info)
			tooltip = meta_info.get("tooltip", summary) if isinstance(meta_info, dict) else summary
			arch_item = QTableWidgetItem(summary)
			arch_item.setToolTip(tooltip)
			self.backups_table.setItem(row, 3, arch_item)

			# Filename
			fn_item = QTableWidgetItem(r["filename"])
			fn_item.setToolTip(r["filename"])
			self.backups_table.setItem(row, 4, fn_item)

			# Action Buttons Widget
			action_widget = QWidget()
			act_layout = QHBoxLayout(action_widget)
			act_layout.setContentsMargins(4, 2, 4, 2)
			act_layout.setSpacing(6)

			# Restore single backup button
			res_btn = PushButton(FIF.HISTORY, "Restore")
			res_btn.setFixedHeight(26)
			res_btn.clicked.connect(lambda _, p=r["path_obj"]: self._restore_single_backup(p))
			act_layout.addWidget(res_btn)

			# Open zip
			open_btn = PushButton(FIF.FOLDER, "Explore")
			open_btn.setFixedHeight(26)
			open_btn.clicked.connect(lambda _, p=r["path_obj"]: open_path_in_explorer(p.parent))
			act_layout.addWidget(open_btn)

			# Delete
			del_btn = PushButton(FIF.DELETE, "Delete")
			del_btn.setFixedHeight(26)
			del_btn.clicked.connect(lambda _, p=r["path_obj"]: self._delete_single_backup(p))
			act_layout.addWidget(del_btn)

			self.backups_table.setCellWidget(row, 5, action_widget)

	def _on_backup_clicked(self):
		"""Create an instant backup for this profile."""
		if not self.current_profile:
			return

		try:
			# Ensure profile is in config so backups are tracked properly
			if self.current_profile.id not in self.config.games:
				self.config.games[self.current_profile.id] = self.current_profile
				self.config.save_config()
				self.profiles_changed.emit()

			# Run plugin pre-backup hook if applicable
			if self.current_plugin is not None:
				if not ensure_plugin_restore_inputs(
					self, self.current_profile, self.current_plugin, self.config
				):
					return
				run_plugin_hook(
					self.current_plugin,
					"pre_backup",
					self.current_profile.as_operation_dict(self.current_plugin),
				)

			dest = run_backup(
				self.current_profile,
				self.config,
				self.current_plugin,
			)

			if dest and dest.exists():
				InfoBar.success(
					title="Backup Completed",
					content=f"Saved backup successfully: {dest.name}",
					parent=toast_parent(self),
					position=InfoBarPosition.TOP,
					duration=3500,
				)
			else:
				InfoBar.warning(
					title="Backup Warning",
					content="Backup completed, but no destination file was returned.",
					parent=toast_parent(self),
					position=InfoBarPosition.TOP,
				)

			# Post-backup hook
			if self.current_plugin is not None:
				run_plugin_hook(
					self.current_plugin,
					"post_backup",
					self.current_profile.as_operation_dict(self.current_plugin),
				)

			self._refresh_backups()
			self._update_save_detection_status()
			self.backup_requested.emit()

		except Exception as e:
			InfoBar.error(
				title="Backup Failed",
				content=str(e),
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=5000,
			)

	def _on_restore_clicked(self):
		"""Open the standard Restore dialog for this game."""
		if not self.current_profile:
			return

		# Ensure profile is in config
		if self.current_profile.id not in self.config.games:
			self.config.games[self.current_profile.id] = self.current_profile
			self.config.save_config()
			self.profiles_changed.emit()

		dlg = RestoreBackupDialog(self.config, self)
		# Pre-select current profile
		if hasattr(dlg, "profile_combo"):
			for i in range(dlg.profile_combo.count()):
				data = dlg.profile_combo.itemData(i)
				if data and getattr(data, "id", None) == self.current_profile.id:
					dlg.profile_combo.setCurrentIndex(i)
					break

		if dlg.exec():
			self._refresh_backups()
			self._update_save_detection_status()

	def _restore_single_backup(self, zip_path: Path):
		"""Restore from a specific backup file."""
		if not self.current_profile or not zip_path.exists():
			return

		# Confirm restore
		ok = confirm_action(
			self,
			"Confirm Restore",
			f"Are you sure you want to restore save files from:\n{zip_path.name}\n\nExisting save files will be replaced!",
		)
		if not ok:
			return

		try:
			# Review plugin restore inputs if needed
			if self.current_plugin is not None:
				if not offer_plugin_restore_input_review(
					self, self.current_profile, self.current_plugin, self.config
				):
					return
				run_plugin_hook(
					self.current_plugin,
					"pre_restore",
					self.current_profile.as_operation_dict(self.current_plugin),
				)

			# Run restore
			run_restore(
				self.current_profile,
				self.config,
				zip_path,
				self.current_plugin,
			)

			InfoBar.success(
				title="Restore Completed",
				content=f"Successfully restored saves from {zip_path.name}",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=4000,
			)

			if self.current_plugin is not None:
				run_plugin_hook(
					self.current_plugin,
					"post_restore",
					self.current_profile.as_operation_dict(self.current_plugin),
				)

			self._update_save_detection_status()

		except Exception as e:
			InfoBar.error(
				title="Restore Failed",
				content=str(e),
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=5000,
			)

	def _delete_single_backup(self, zip_path: Path):
		if not zip_path.exists():
			return
		ok = confirm_action(
			self,
			"Delete Backup",
			f"Are you sure you want to permanently delete:\n{zip_path.name}?",
		)
		if ok:
			try:
				zip_path.unlink()
				self._refresh_backups()
				InfoBar.success(
					title="Backup Deleted",
					content=f"Deleted {zip_path.name}",
					parent=toast_parent(self),
					position=InfoBarPosition.TOP,
					duration=2500,
				)
			except Exception as e:
				InfoBar.error(
					title="Delete Failed",
					content=str(e),
					parent=toast_parent(self),
					position=InfoBarPosition.TOP,
				)

	def _on_delete_all_backups(self):
		if not self._backup_rows:
			InfoBar.info(
				title="No Backups",
				content="There are no backups to delete for this game.",
				parent=toast_parent(self),
			)
			return

		ok = confirm_action(
			self,
			"Delete All Backups",
			f"Are you sure you want to delete ALL {len(self._backup_rows)} backups for {self.current_profile.resolved_name(self.current_plugin)}?\nThis cannot be undone.",
		)
		if not ok:
			return

		deleted = 0
		for r in self._backup_rows:
			try:
				p = r["path_obj"]
				if p.exists():
					p.unlink()
					deleted += 1
			except Exception:
				pass

		self._refresh_backups()
		InfoBar.success(
			title="All Backups Deleted",
			content=f"Deleted {deleted} backup file(s).",
			parent=toast_parent(self),
			position=InfoBarPosition.TOP,
		)

	def _on_launch_clicked(self):
		"""Launch game executable. If missing, prompt user to select one."""
		if not self.current_profile:
			return

		exe_path = (self.current_profile.executable_path or "").strip()
		if not exe_path or not Path(exe_path).is_file():
			# Try auto-detecting candidates first
			candidates = self.current_profile.find_candidate_executables(self.current_plugin)
			primary = [
				c for c in candidates
				if not any(ign in Path(c).name.lower() for ign in ("unins", "uninstall", "crashhandler", "crashreport", "helper", "setup", "update"))
			]
			auto_exe = primary[0] if primary else (candidates[0] if candidates else None)

			if auto_exe and Path(auto_exe).is_file():
				file_path = auto_exe
			else:
				# Ask user to select executable manually
				InfoBar.info(
					title="Executable Not Set",
					content="Please select the game executable (.exe) to launch.",
					parent=toast_parent(self),
					position=InfoBarPosition.TOP,
					duration=3000,
				)
				file_path, _ = QFileDialog.getOpenFileName(
					self,
					"Select Game Executable",
					"",
					"Executable Files (*.exe);;All Files (*.*)",
				)
				if not file_path:
					return

			self.current_profile.executable_path = file_path
			self.exe_path_edit.setText(file_path)
			if self.current_profile.id in self.config.games:
				self.config.games[self.current_profile.id].executable_path = file_path
				self.config.save_config()
			exe_path = file_path

		ok = self.current_profile.launch_executable(exe_path)
		if ok:
			InfoBar.success(
				title="Game Launched",
				content=f"Launched {Path(exe_path).name}",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=3000,
			)
		else:
			InfoBar.error(
				title="Launch Failed",
				content=f"Could not launch executable at:\n{exe_path}",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=4000,
			)

	def _on_browse_executable(self):
		file_path, _ = QFileDialog.getOpenFileName(
			self,
			"Select Game Executable",
			self.exe_path_edit.text() or "",
			"Executable Files (*.exe);;All Files (*.*)",
		)
		if file_path:
			self.exe_path_edit.setText(file_path)
			self._on_save_executable_path()

	def _on_exe_path_edited(self, text: str):
		pass

	def _on_save_executable_path(self):
		if not self.current_profile:
			return
		path_val = self.exe_path_edit.text().strip()
		self.current_profile.executable_path = path_val
		if self.current_profile.id in self.config.games:
			self.config.games[self.current_profile.id].executable_path = path_val
			self.config.save_config()
		InfoBar.success(
			title="Executable Saved",
			content="Game executable path updated.",
			parent=toast_parent(self),
			position=InfoBarPosition.TOP,
			duration=2000,
		)

	def _on_scan_executables(self):
		"""Scan candidate paths for executables."""
		if not self.current_profile:
			return
		candidates = self.current_profile.find_candidate_executables(self.current_plugin)
		self.discovered_exe_list.clear()
		if candidates:
			self.discovered_exe_label.setVisible(True)
			self.discovered_exe_list.setVisible(True)
			for c in candidates:
				item = QListWidgetItem(FIF.APPLICATION.icon(), c)
				self.discovered_exe_list.addItem(item)
			row_count = min(len(candidates), 5)
			self.discovered_exe_list.setFixedHeight(row_count * 38 + 12)
			InfoBar.success(
				title="Executables Found",
				content=f"Found {len(candidates)} candidate executable(s). Double-click to select.",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
			)
		else:
			self.discovered_exe_label.setVisible(False)
			self.discovered_exe_list.setVisible(False)
			InfoBar.info(
				title="Scan Complete",
				content="No candidate executables discovered automatically. Please use Browse...",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
			)

	def _on_discovered_exe_double_clicked(self, item: QListWidgetItem):
		if item and self.current_profile:
			chosen = item.text().strip()
			self.exe_path_edit.setText(chosen)
			self._on_save_executable_path()

	def _on_library_toggle_clicked(self):
		"""Add or remove this game from Library."""
		if not self.current_profile:
			return

		p_id = self.current_profile.id
		if p_id in self.config.games:
			# Remove
			del self.config.games[p_id]
			self.config.save_config()
			self.set_profile(self.current_profile, self.source_view)
			self.profiles_changed.emit()
			InfoBar.success(
				title="Removed from Library",
				content=f"{self.current_profile.resolved_name(self.current_plugin)} removed from your Library.",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=3000,
			)
		else:
			# Add
			self.config.games[p_id] = self.current_profile
			self.config.save_config()
			self.set_profile(self.current_profile, self.source_view)
			self.profiles_changed.emit()
			InfoBar.success(
				title="Added to Library",
				content=f"{self.current_profile.resolved_name(self.current_plugin)} added to your Library!",
				parent=toast_parent(self),
				position=InfoBarPosition.TOP,
				duration=3000,
			)

	def _on_open_save_folder(self):
		if not self.current_profile:
			return
		locs = self.current_profile.effective_save_locations(self.current_plugin)
		for _, contracted in locs:
			p = PathUtils.expand(contracted)
			if p.exists():
				open_path_in_explorer(p)
				return
		InfoBar.warning(
			title="Save Folder Not Found",
			content="The configured save folder does not exist on disk yet.",
			parent=toast_parent(self),
			position=InfoBarPosition.TOP,
		)

	def _on_open_backup_folder(self):
		if not self.current_profile:
			return
		b_dir = self.config.backup_dir_for_profile(self.current_profile, self.current_plugin)
		b_dir.mkdir(parents=True, exist_ok=True)
		open_path_in_explorer(b_dir)

	def _on_edit_profile(self):
		if not self.current_profile:
			return
		editor = ModernGameEditor(self.current_profile, self)
		if editor.exec():
			updated = editor.get_profile()
			self.config.games[updated.id] = updated
			self.config.save_config()
			self.set_profile(updated, self.source_view)
			self.profiles_changed.emit()

	def _on_verify_saves(self):
		if not self.current_profile:
			return
		dlg = VerifySaveDialog(
			self.current_profile,
			self.current_plugin,
			self.config,
			self,
		)
		dlg.exec()
		self._update_save_detection_status()
