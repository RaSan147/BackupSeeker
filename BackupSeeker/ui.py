"""Qt UI for BackupSeeker Game Save Manager.

This is a refactored version of the `MainWindow` and dialogs from
`gemini.py`, wired against the reusable core API in `BackupSeeker.core`.
"""

from __future__ import annotations

import sys
import os
import logging
from datetime import datetime
import time
from pathlib import Path
from typing import Optional, Any

from PyQt6.QtCore import Qt, QByteArray, QEvent
from PyQt6.QtGui import QAction, QActionGroup, QFont, QPalette, QColor
from PyQt6.QtWidgets import (
	QApplication,
	QDialog,
	QFileDialog,
	QFormLayout,
	QHBoxLayout,
	QLabel,
	QListWidgetItem,
	QMainWindow,
	QMessageBox,
	QTableWidget,
	QTableWidgetItem,
	QTabWidget,
	QVBoxLayout,
	QWidget,
	QHeaderView,
)
# Default widget aliases use standard PyQt6 widgets. When running in
# Fluent mode `BackupSeeker.ui_fluent` will inject qfluentwidgets
# equivalents into this module at runtime (after QApplication exists).
from PyQt6.QtWidgets import QLineEdit as _QLineEdit, QListWidget as _QListWidget, QPushButton as _QPushButton, QTextEdit as _QTextEdit, QDialog as _QDialog

LineEdit = _QLineEdit
ListWidget = _QListWidget
PushButton = _QPushButton
PrimaryPushButton = _QPushButton
PlainTextEdit = _QTextEdit
Dialog = _QDialog

from .core import ConfigManager, GameProfile, PathUtils, clear_before_restore, run_restore
from .plugin_manager import PluginManager
from .ui_shared import (
	confirm_action,
	confirm_restore,
	ensure_plugin_restore_inputs,
	offer_plugin_restore_input_review,
	open_path_in_explorer,
	prompt_plugin_primary_path_fix,
)


def _plugin_for_profile(profile: GameProfile, win: QWidget | None):
	if win is None or not getattr(profile, "plugin_id", ""):
		return None
	pm = getattr(win, "plugin_manager", None)
	return pm.get_plugin_for_profile(profile.plugin_id) if pm else None


def _profile_display(profile: GameProfile, win: QWidget | None) -> str:
	return profile.resolved_name(_plugin_for_profile(profile, win))


def _qfont_with_resolved_size(font: QFont) -> QFont:
	"""Copy *font* with an explicit point or pixel size.

	List/item fonts inherited from stylesheets often use pointSize -1;
	modifying and re-setting such a font triggers Qt warnings about
	``setPointSize(-1)``.
	"""
	f = QFont(font)
	if f.pointSize() > 0 or f.pixelSize() > 0:
		return f
	app = QApplication.instance()
	if isinstance(app, QApplication):
		base = app.font()
		if base.pointSize() > 0:
			f.setPointSize(base.pointSize())
			return f
		if base.pixelSize() > 0:
			f.setPixelSize(base.pixelSize())
			return f
	f.setPointSize(9)
	return f


class ThemeManager:
	@staticmethod
	def get_effective_theme(app: Any, config_theme: str) -> str:
		if config_theme == "dark":
			return "dark"
		if config_theme == "light":
			return "light"
		if hasattr(Qt, "ColorScheme"):
			try:
				scheme = app.styleHints().colorScheme()
				if scheme == Qt.ColorScheme.Dark:
					return "dark"
			except Exception as e:
				logging.debug(f"Could not determine system color scheme: {e}")
		return "light"

	@staticmethod
	def apply_theme(app: Any, config_theme: str) -> None:
		app.setStyle("Fusion")
		effective_theme = ThemeManager.get_effective_theme(app, config_theme)

		if effective_theme == "dark":
			p = QPalette()
			p.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
			p.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
			p.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
			p.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
			p.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
			p.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
			p.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
			p.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
			p.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
			p.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
			app.setPalette(p)
		else:
			p = QPalette()
			p.setColor(QPalette.ColorRole.Window, QColor(245, 245, 245))
			p.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
			p.setColor(QPalette.ColorRole.AlternateBase, QColor(225, 225, 225))
			p.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
			p.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
			p.setColor(QPalette.ColorRole.PlaceholderText, QColor(120, 120, 120))
			p.setColor(QPalette.ColorRole.Button, QColor(230, 230, 230))
			p.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
			p.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
			p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
			app.setPalette(p)


class GameEditorDialog(Dialog):
	def __init__(self, profile: Optional[GameProfile] = None, parent: QWidget | None = None) -> None:
		# qfluentwidgets.Dialog accepts (title, content, parent), but the
		# default Dialog alias may be a plain QDialog. Use a best-effort
		# constructor call so both cases work.
		try:
			super().__init__("Game Profile 🎮", "", parent)
		except TypeError:
			super().__init__(parent)
		self.profile = profile or GameProfile()
		self._editor_parent = parent
		self.setWindowTitle("Game Profile 🎮")
		self.setMinimumWidth(500)

		layout = QVBoxLayout(self)
		form = QFormLayout()

		plug = _plugin_for_profile(self.profile, parent)
		self.name_edit = LineEdit()
		if self.profile.plugin_id:
			self.name_edit.setText(self.profile.resolved_name(plug))
			self.name_edit.setReadOnly(True)
			self.name_edit.setPlaceholderText("Defined by plugin")
		else:
			self.name_edit.setText(self.profile.name)
			self.name_edit.setPlaceholderText("e.g. Cyberpunk 2077")

		self.path_edit = LineEdit(self.profile.editor_primary_path_display(plug))
		if self.profile.plugin_id:
			self.path_edit.setPlaceholderText("Leave empty — use plugin detection")
		else:
			self.path_edit.setPlaceholderText("Paste path here...")
		path_btn = PushButton("📂 Browse")
		path_btn.clicked.connect(self.browse_path)
		path_layout = QHBoxLayout()
		path_layout.addWidget(self.path_edit)
		path_layout.addWidget(path_btn)

		form.addRow("Name:", self.name_edit)
		form.addRow("Path:", path_layout)

		layout.addLayout(form)

		btns = QHBoxLayout()
		save = PushButton("💾 Save Profile")
		save.clicked.connect(self.save)
		cancel = PushButton("❌ Cancel")
		cancel.clicked.connect(self.reject)
		btns.addWidget(save)
		btns.addWidget(cancel)
		layout.addLayout(btns)

	def browse_path(self) -> None:
		d = QFileDialog.getExistingDirectory(self, "Select Save Folder")
		if d:
			self.path_edit.setText(PathUtils.contract(d))

	def save(self) -> None:
		raw_path = PathUtils.clean_input_path(self.path_edit.text())
		plug = _plugin_for_profile(self.profile, self._editor_parent)

		if self.profile.plugin_id:
			if plug:
				ver = getattr(plug, "version", "")
				if isinstance(ver, str) and ver.strip():
					self.profile.plugin_version = ver.strip()
			self.profile.name = ""
			self.profile.apply_editor_primary_path(plug, raw_path)
		else:
			name = self.name_edit.text().strip()
			if not name or not raw_path:
				QMessageBox.warning(self, "Error", "Name and Path are required.")
				return
			self.profile.name = name
			self.profile.save_path = PathUtils.contract(raw_path)

		if not self.profile.id:
			self.profile.id = f"game_{datetime.now().strftime('%Y%m%d%H%M%S')}"
		self.accept()


class PluginBrowserDialog(Dialog):
	"""Panel for searching, auto-detecting and adding plugin games."""

	def __init__(self, plugin_manager: PluginManager, config: ConfigManager, parent: QWidget | None = None) -> None:
		try:
			super().__init__("Plugin Games 🎮", "", parent)
		except TypeError:
			super().__init__(parent)
		self.plugin_manager = plugin_manager
		self.config = config
		self.setWindowTitle("Plugin Games 🎮")
		self.setMinimumSize(600, 500)
		self._init_ui()
		self._refresh_all_plugins()

	def _init_ui(self) -> None:
		layout = QVBoxLayout(self)

		# Search bar
		search_row = QHBoxLayout()
		self.search_edit = LineEdit()
		self.search_edit.setPlaceholderText("Search games (plugin database)...")
		btn_search = PushButton("🔎 Search")
		btn_search.clicked.connect(self._on_search_clicked)
		btn_reset = PushButton("Reset")
		btn_reset.clicked.connect(self._refresh_all_plugins)
		search_row.addWidget(self.search_edit)
		search_row.addWidget(btn_search)
		search_row.addWidget(btn_reset)
		layout.addLayout(search_row)

		# List of games
		self.list_widget = ListWidget()
		layout.addWidget(self.list_widget)

		# Buttons
		btn_row = QHBoxLayout()
		btn_detect = PushButton("🔍 Auto Detect Installed")
		btn_detect.clicked.connect(self._on_detect_clicked)
		btn_add = PushButton("➕ Add Selected to Profiles")
		btn_add.clicked.connect(self._on_add_selected)
		btn_close = PushButton("Close")
		btn_close.clicked.connect(self.reject)
		btn_row.addWidget(btn_detect)
		btn_row.addWidget(btn_add)
		btn_row.addWidget(btn_close)
		layout.addLayout(btn_row)

	def _refresh_all_plugins(self) -> None:
		self.list_widget.clear()
		self.plugin_manager.load_plugins()
		for plugin in self.plugin_manager.available_plugins.values():
			item = QListWidgetItem(f"🎮 {plugin.game_name}")
			item.setData(Qt.ItemDataRole.UserRole, plugin.game_id)
			self.list_widget.addItem(item)

	def _on_search_clicked(self) -> None:
		query = self.search_edit.text().strip().lower()
		self.list_widget.clear()
		for plugin in self.plugin_manager.available_plugins.values():
			if not query or query in plugin.game_name.lower() or query in plugin.game_id.lower():
				item = QListWidgetItem(f"🎮 {plugin.game_name}")
				item.setData(Qt.ItemDataRole.UserRole, plugin.game_id)
				self.list_widget.addItem(item)

	def _on_detect_clicked(self) -> None:
		# Highlight only detected games in the list, but don't auto-add
		detected_ids = {p["plugin_id"] for p in self.plugin_manager.detect_games()}
		for i in range(self.list_widget.count()):
			item = self.list_widget.item(i)
			pid = item.data(Qt.ItemDataRole.UserRole)
			font = _qfont_with_resolved_size(item.font())
			font.setBold(pid in detected_ids)
			item.setFont(font)

	def _on_add_selected(self) -> None:
		selected_items = self.list_widget.selectedItems()
		if not selected_items:
			QMessageBox.information(self, "Plugins", "Select at least one game to add.")
			return
		added = 0
		profiles = {p.plugin_id for p in self.config.games.values() if p.plugin_id}
		# Build quick map id->to_profile for detection-less add
		profile_map = {pid: plugin.to_profile() for pid, plugin in self.plugin_manager.available_plugins.items()}
		for item in selected_items:
			pid = item.data(Qt.ItemDataRole.UserRole)
			if pid in profiles:
				continue
			data = profile_map.get(pid)
			if not data:
				continue
			self.config.add_game_from_plugin(data)
			added += 1
		if added:
			QMessageBox.information(self, "Plugins", f"Added {added} game(s) to profiles.")
		self.accept()


class MainWindow(QMainWindow):
	def __init__(self, config: Optional[ConfigManager] = None) -> None:
		super().__init__()
		self.config = config or ConfigManager()
		self.current_profile: Optional[GameProfile] = None
		self._worker_thread = None
		self.plugin_manager = PluginManager(self.config.app_dir)
		self.config.sync_plugin_versions_from(self.plugin_manager)
		self.config.save_config()
		self.init_ui()

	def init_ui(self) -> None:
		self.setWindowTitle("Game Save Manager 💾 (BackupSeeker)")
		self.resize(1000, 700)

		central = QWidget()
		self.setCentralWidget(central)
		main_h = QHBoxLayout(central)

		left = QVBoxLayout()
		self.game_list = ListWidget()
		self.game_list.itemSelectionChanged.connect(self.on_game_select)
		left.addWidget(QLabel("Profiles"))
		left.addWidget(self.game_list)
		btn_add = PushButton("➕ Add Game")
		btn_add.clicked.connect(self.add_game)
		left.addWidget(btn_add)
		self.btn_edit = PushButton("✏️ Edit")
		self.btn_edit.clicked.connect(self.edit_game)
		left.addWidget(self.btn_edit)
		self.btn_del = PushButton("🗑️ Delete")
		self.btn_del.clicked.connect(self.delete_game)
		left.addWidget(self.btn_del)
		left_widget = QWidget()
		left_widget.setLayout(left)
		left_widget.setFixedWidth(260)

		self.tabs = QTabWidget()

		self.tab_dash = QWidget()
		dash_layout = QVBoxLayout(self.tab_dash)
		self.lbl_title = QLabel("Select a game")
		self.lbl_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
		self.lbl_path = QLabel("<b>Path:</b> -")
		self.lbl_backup_root = QLabel()
		self.lbl_backup_root.setObjectName("lblBackupRoot")

		self.btn_backup = PrimaryPushButton("💾 BACKUP NOW")
		self.btn_backup.setMinimumHeight(40)
		self.btn_backup.clicked.connect(self.perform_backup)

		self.log_view = PlainTextEdit()
		self.log_view.setReadOnly(True)

		dash_layout.addWidget(self.lbl_title)
		dash_layout.addWidget(self.lbl_path)
		dash_layout.addWidget(self.lbl_backup_root)
		dash_layout.addSpacing(10)
		dash_layout.addWidget(self.btn_backup)
		dash_layout.addWidget(QLabel("Activity Log:"))
		dash_layout.addWidget(self.log_view)

		self.tabs.addTab(self.tab_dash, "Dashboard")

		self.tab_restore = QWidget()
		restore_layout = QVBoxLayout(self.tab_restore)
		self.table = QTableWidget()
		self.table.setColumnCount(5)
		self._header_labels = ["Type", "Date", "Size", "Archive", "Filename"]
		self.table.setHorizontalHeaderLabels(self._header_labels)
		header = self.table.horizontalHeader()
		header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
		header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
		header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
		header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
		header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
		self._table_header = header
		self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
		self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)

		self.btn_restore_sel = PushButton("♻️ Restore Selected")
		self.btn_restore_sel.clicked.connect(self.perform_restore)
		self.btn_open_sel = PushButton("📂 Open Selected")
		self.btn_open_sel.clicked.connect(self.open_selected_backup_location)
		self.btn_delete_sel = PushButton("🗑️ Delete Selected")
		self.btn_delete_sel.clicked.connect(self.delete_selected_backups)
		self.btn_refresh = PushButton("🔄 Refresh List")
		self.btn_refresh.clicked.connect(self.refresh_backups)

		restore_layout.addWidget(self.table)
		# Bottom controls: compact horizontal layout. Open/Delete moved to context menu.
		btn_row = QHBoxLayout()
		btn_row.addWidget(self.btn_refresh)
		btn_row.addWidget(self.btn_restore_sel)
		btn_row.addStretch()
		restore_layout.addLayout(btn_row)
		self.tabs.addTab(self.tab_restore, "Backups / Restore")

		main_h.addWidget(left_widget)
		main_h.addWidget(self.tabs)
		# Build the top menus after the main widgets so widgets referenced by actions exist
		self.create_menu()
		# Enable custom context menu on backups table
		self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
		self.table.customContextMenuRequested.connect(self._on_table_context_menu)
		self.table.itemSelectionChanged.connect(self._on_backup_selection_changed)
		self._on_backup_selection_changed()

		ThemeManager.apply_theme(QApplication.instance(), self.config.theme)
		self.update_button_styles()
		self.refresh_game_list()
		self.update_ui_state()

		if self.config.window_geometry:
			try:
				ba = QByteArray.fromHex(self.config.window_geometry.encode("ascii"))
				self.restoreGeometry(ba)
			except Exception as e:
				self.log(f"Restore geometry failed: {e}")
		# Log the active storage root on startup
		self.log(f"Active storage: {self.config.backup_root}")

	def showEvent(self, event):  # type: ignore[override]
		super().showEvent(event)
		if self.config.table_widths:
			for i, w in enumerate(self.config.table_widths):
				if i < 5:
					self.table.setColumnWidth(i, w)
		else:
			total_w = self.table.width()
			if total_w > 0:
				col_w = int(total_w * 0.12)
				self.table.setColumnWidth(0, col_w)
				self.table.setColumnWidth(1, col_w)
				self.table.setColumnWidth(2, col_w)

	def closeEvent(self, event):  # type: ignore[override]
		self.config.window_geometry = self.saveGeometry().toHex().data().decode("ascii")
		widths = [self.table.columnWidth(i) for i in range(5)]
		self.config.table_widths = widths
		self.config.save_config()
		event.accept()

	def create_menu(self) -> None:
		bar = self.menuBar()
		view = bar.addMenu("View")
		plugins_menu = bar.addMenu("Plugins")
		storage_menu = bar.addMenu("Storage")
		theme = view.addMenu("Theme")
		group = QActionGroup(self)

		def add_theme_action(label: str, key: str) -> None:
			act = QAction(label, self)
			act.setCheckable(True)
			if self.config.theme == key:
				act.setChecked(True)
			act.triggered.connect(lambda: self.set_theme(key))
			group.addAction(act)
			theme.addAction(act)

		add_theme_action("System", "system")
		add_theme_action("Dark", "dark")
		add_theme_action("Light", "light")

		plugins_panel_action = QAction("Plugin Panel...", self)
		plugins_panel_action.triggered.connect(self.open_plugin_panel)
		plugins_menu.addAction(plugins_panel_action)

		# Storage / backup location actions
		self.storage_action_group = QActionGroup(self)
		self.act_cwd = QAction("Use Current Dir (./backups)", self)
		self.act_cwd.setCheckable(True)
		self.act_cwd.triggered.connect(self._set_backup_cwd)
		storage_menu.addAction(self.act_cwd)
		self.storage_action_group.addAction(self.act_cwd)

		self.act_fixed = QAction("Use Fixed Location...", self)
		self.act_fixed.setCheckable(True)
		self.act_fixed.triggered.connect(self._choose_fixed_location)
		storage_menu.addAction(self.act_fixed)
		self.storage_action_group.addAction(self.act_fixed)


		# (Storage menu and Open action are created in create_menu.)
		# Initialize checked state
		self._sync_storage_actions()

	def _sync_storage_actions(self) -> None:
		mode = self.config.backup_location_mode
		# Ensure actions exist before toggling
		if hasattr(self, "act_cwd"):
			self.act_cwd.setChecked(mode == "cwd")
		if hasattr(self, "act_fixed"):
			self.act_fixed.setChecked(mode == "fixed")
		self.update_storage_display()

	def update_storage_display(self) -> None:
		mode = self.config.backup_location_mode
		root = self.config.backup_root
		root_str = str(root)
		# Defensive UI: only update labels/status if they've been created
		if hasattr(self, "lbl_backup_root") and self.lbl_backup_root is not None:
			self.lbl_backup_root.setText(f"<b>Storage:</b> {mode} → {root_str}")
		# Show a shorter status message
		try:
			self.statusBar().showMessage(f"Storage: {mode} | {root_str}")
		except Exception as e:
			# Non-fatal: status bar may not exist in some states
			try:
				self.log(f"Status bar update failed: {e}")
			except Exception:
				logging.debug(f"Status bar update failed: {e}")

		# Storage menu items are created in create_menu

	def _open_backup_folder(self) -> None:
		try:
			path = self.config.backup_root
			path.mkdir(parents=True, exist_ok=True)
			open_path_in_explorer(path)
		except Exception as e:
			QMessageBox.warning(self, "Open Folder", f"Could not open folder: {e}")

	def _set_backup_cwd(self) -> None:
		self.config.set_backup_mode_cwd()
		self._after_backup_location_change()

	def _choose_fixed_location(self) -> None:
		d = QFileDialog.getExistingDirectory(self, "Select Backup Storage Folder")
		if d:
			self.config.set_backup_mode_fixed(d)
			self._after_backup_location_change()


	def _after_backup_location_change(self) -> None:
		self._sync_storage_actions()
		if self.current_profile:
			self.refresh_backups()
		self.log(f"Backup location set to {self.config.backup_root}")

	def set_theme(self, t: str) -> None:
		self.config.theme = t
		self.config.save_config()
		ThemeManager.apply_theme(QApplication.instance(), t)
		self.update_button_styles()

	def update_button_styles(self) -> None:
		effective_theme = ThemeManager.get_effective_theme(QApplication.instance(), self.config.theme)
		if effective_theme == "dark":
			self.btn_del.setStyleSheet("color: #ff6b6b; background-color: #353535;")
		else:
			self.btn_del.setStyleSheet("color: #d32f2f;")

		# Make disabled buttons more clearly dimmed for affordance
		try:
			if effective_theme == "dark":
				normal_color = "white"
				bg = "#353535"
				disabled_color = "#777777"
				disabled_bg = "transparent"
			else:
				normal_color = "#222222"
				bg = "#f0f0f0"
				disabled_color = "#a0a0a0"
				disabled_bg = "#f5f5f5"

			btns = []
			for name in ("btn_restore_sel", "btn_open_sel", "btn_delete_sel", "btn_refresh"):
				if hasattr(self, name):
					btns.append(getattr(self, name))
			for b in btns:
				bs = (
					f"QPushButton {{ color: {normal_color}; background-color: {bg}; }}"
					f"QPushButton:disabled {{ color: {disabled_color}; background-color: {disabled_bg}; }}"
				)
				b.setStyleSheet(bs)
		except Exception as e:
			# Non-fatal UI tweak failure; log for diagnostics
			try:
				self.log(f"Button style update failed: {e}")
			except Exception:
				logging.debug(f"Button style update failed: {e}")

	def open_plugin_panel(self) -> None:
		dlg = PluginBrowserDialog(self.plugin_manager, self.config, self)
		if dlg.exec():
			# Profiles may have changed
			self.refresh_game_list()

	def refresh_game_list(self) -> None:
		self.game_list.clear()
		for pid, p in self.config.games.items():
			item = QListWidgetItem(f"🎮 {_profile_display(p, self)}")
			item.setData(Qt.ItemDataRole.UserRole, pid)
			self.game_list.addItem(item)

	def on_game_select(self) -> None:
		items = self.game_list.selectedItems()
		if not items:
			self.current_profile = None
			self.update_ui_state()
			return
		pid = items[0].data(Qt.ItemDataRole.UserRole)
		self.current_profile = self.config.games.get(pid)
		self.update_ui_state()
		if self.current_profile:
			self.refresh_backups()

	def update_ui_state(self) -> None:
		enabled = self.current_profile is not None
		self.btn_edit.setEnabled(enabled)
		self.btn_del.setEnabled(enabled)
		self.tab_dash.setEnabled(enabled)
		self.tab_restore.setEnabled(enabled)
		self.update_storage_display()
		if enabled and self.current_profile is not None:
			self.lbl_title.setText(f"🎮 {_profile_display(self.current_profile, self)}")
			ep = self.current_profile.effective_save_path(_plugin_for_profile(self.current_profile, self))
			self.lbl_path.setText(f"<b>Path:</b> {ep or '(from plugin — at backup)'}")
		else:
			self.lbl_title.setText("Select a Game")
			self.lbl_path.setText("<b>Path:</b> -")
			self.table.setRowCount(0)

	def add_game(self) -> None:
		dlg = GameEditorDialog(parent=self)
		if dlg.exec():
			self.config.games[dlg.profile.id] = dlg.profile
			self.config.save_config()
			self.refresh_game_list()
			self.log(f"Added {_profile_display(dlg.profile, self)}")

	def edit_game(self) -> None:
		if not self.current_profile:
			return
		dlg = GameEditorDialog(self.current_profile, self)
		if dlg.exec():
			self.config.save_config()
			self.refresh_game_list()
			self.on_game_select()
			self.log(f"Updated {_profile_display(self.current_profile, self)}")

	def delete_game(self) -> None:
		if not self.current_profile:
			return
		if not confirm_action(self, "Delete", f"Delete profile '{_profile_display(self.current_profile, self)}'?"):
			return
		del self.config.games[self.current_profile.id]
		self.config.save_config()
		self.refresh_game_list()
		self.current_profile = None
		self.update_ui_state()

	def perform_backup(self) -> None:
		if not self.current_profile:
			return
		self.log(f"Starting backup for {_profile_display(self.current_profile, self)}...")
		self._execute_backup_attempt(self.current_profile, offer_path_fix=True)

	def _execute_backup_attempt(self, profile: GameProfile, *, offer_path_fix: bool) -> None:
		from .core import run_backup

		plugin = self.plugin_manager.get_plugin_for_profile(profile.plugin_id)
		if not ensure_plugin_restore_inputs(self, profile, plugin, self.config):
			self.log("Backup cancelled.")
			return
		profile_dict = profile.as_operation_dict(plugin)
		if plugin is not None:
			profile_dict = plugin.preprocess_backup(profile_dict)
			if not profile.plugin_id:
				profile.save_path = profile_dict.get("save_path", profile.save_path)
		try:
			dest = run_backup(profile, self.config, plugin)
		except (RuntimeError, FileNotFoundError) as e:
			msg = str(e)
			self.log(f"Backup skipped: {msg}")
			if offer_path_fix and prompt_plugin_primary_path_fix(
				self,
				profile,
				plugin,
				self.config,
				detail=msg,
			):
				self._execute_backup_attempt(profile, offer_path_fix=False)
				return
			QMessageBox.warning(self, "Nothing to back up", msg)
			return
		except Exception as e:
			self.log(f"ERROR: {e}")
			QMessageBox.critical(self, "Error", str(e))
			return
		result_data = {"backup_path": str(dest)}
		if plugin is not None:
			result_data = plugin.postprocess_backup(result_data)
		size_str = f"{dest.stat().st_size / 1024:.1f} KB"
		self.log(f"SUCCESS: Saved to {dest.name} ({size_str})")
		QMessageBox.information(self, "Backup", "Backup Successful!")
		self.refresh_backups()

	def refresh_backups(self) -> None:
		from .core import ConfigManager, read_archive_metadata, summarize_archive_metadata

		self.table.setRowCount(0)
		if not self.current_profile:
			return
		dn = _profile_display(self.current_profile, self)
		reg_dir = self.config.get_game_backup_dir(dn)
		backups = list(reg_dir.glob("*.zip"))
		safe_dir = self.config.get_safety_backup_dir(dn)
		safety_backups = list(safe_dir.glob("*.zip"))
		all_files = []
		for f in backups:
			all_files.append((f, "Regular"))
		for f in safety_backups:
			all_files.append((f, "Safety"))
		all_files.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)
		# Build internal row cache for custom sorting
		self._backup_rows = []  # type: ignore[attr-defined]
		for fpath, btype in all_files:
			bsize = fpath.stat().st_size
			if bsize < 1024 * 1024:  # < 1 MB show KB
				size_str = f"{bsize/1024:.1f} KB"
			else:
				size_str = f"{bsize/1024/1024:.1f} MB"
			meta = read_archive_metadata(fpath)
			summ = summarize_archive_metadata(meta, zip_path=fpath)
			row_dict = {
				"type": "🛡️ Safety" if btype == "Safety" else "💾 Regular",
				"type_rank": 1 if btype == "Safety" else 0,
				"date": datetime.fromtimestamp(fpath.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
				"timestamp": fpath.stat().st_mtime,
				"size": size_str,
				"bytes": bsize,
				"archive": summ.get("summary", ""),
				"archive_tooltip": summ.get("tooltip", ""),
				"filename": fpath.name,
				"path": str(fpath),
			}
			self._backup_rows.append(row_dict)
		self._ensure_sort_state()
		self._sort_backup_rows()
		# Ensure header handler only set once
		if not hasattr(self, "_header_initialized"):
			self._header_initialized = True
			header = self.table.horizontalHeader()
			header.setSectionsClickable(True)
			header.sectionPressed.connect(self._on_table_header_clicked)
			header.installEventFilter(self)

	def _render_backup_rows(self) -> None:
		self.table.setRowCount(0)
		for row_dict in getattr(self, "_backup_rows", []):
			row = self.table.rowCount()
			self.table.insertRow(row)
			self.table.setItem(row, 0, QTableWidgetItem(row_dict["type"]))
			self.table.setItem(row, 1, QTableWidgetItem(row_dict["date"]))
			self.table.setItem(row, 2, QTableWidgetItem(row_dict["size"]))
			arch_item = QTableWidgetItem(row_dict.get("archive", ""))
			arch_item.setToolTip(row_dict.get("archive_tooltip", ""))
			self.table.setItem(row, 3, arch_item)
			item = QTableWidgetItem(row_dict["filename"])
			item.setData(Qt.ItemDataRole.UserRole, row_dict["path"])
			item.setToolTip(row_dict.get("archive_tooltip", ""))
			self.table.setItem(row, 4, item)
		self._on_backup_selection_changed()

	def _ensure_sort_state(self) -> None:
		if not hasattr(self, "_type_sort_mode"):
			self._type_sort_mode = "none"  # none | asc | desc
		if not hasattr(self, "_date_sort_mode"):
			self._date_sort_mode = "desc"  # desc = latest first

	def _sort_backup_rows(self) -> None:
		if not hasattr(self, "_backup_rows"):
			return
		self._ensure_sort_state()

		def sort_key(row):
			# Type ordering component
			if self._type_sort_mode == "asc":
				type_key = row.get("type_rank", 0)
			elif self._type_sort_mode == "desc":
				type_key = -row.get("type_rank", 0)
			else:
				type_key = 0
			# Date ordering component (timestamp stored as float)
			ts = row.get("timestamp", 0)
			date_key = -ts if self._date_sort_mode == "desc" else ts
			return (type_key, date_key)

		self._backup_rows.sort(key=sort_key)
		self._render_backup_rows()
		self._update_header_sort_indicators()

	def _update_header_sort_indicators(self) -> None:
		if not hasattr(self, "_header_labels"):
			return
		labels = list(self._header_labels)
		if getattr(self, "_type_sort_mode", "none") != "none":
			arrow = "↑" if self._type_sort_mode == "asc" else "↓"
			labels[0] = f"{self._header_labels[0]} {arrow}"
		else:
			labels[0] = self._header_labels[0]
		arrow = "↑" if self._date_sort_mode == "asc" else "↓"
		labels[1] = f"{self._header_labels[1]} {arrow}"
		self.table.setHorizontalHeaderLabels(labels)

	def _get_selected_rows(self) -> list[int]:
		model = self.table.selectionModel()
		if not model:
			return []
		return sorted({idx.row() for idx in model.selectedRows()})

	def _on_backup_selection_changed(self) -> None:
		rows = self._get_selected_rows()
		count = len(rows)
		self.btn_restore_sel.setEnabled(count == 1)
		self.btn_open_sel.setEnabled(count == 1)
		self.btn_delete_sel.setEnabled(count > 0)

	def _should_skip_header_click(self, col: int) -> bool:
		interval_ms = 0
		app = QApplication.instance()
		if isinstance(app, QApplication):
			try:
				interval_ms = app.styleHints().mouseDoubleClickInterval()
			except Exception:
				interval_ms = 0
		if interval_ms <= 0:
			interval_ms = 400
		interval = interval_ms / 1000.0
		now = time.monotonic()
		last_col = getattr(self, "_last_header_col", None)
		last_time = getattr(self, "_last_header_time", 0.0)
		if last_col == col and (now - last_time) < interval:
			return True
		self._last_header_col = col
		self._last_header_time = now
		return False

	def _on_table_header_clicked(self, col: int) -> None:
		if not hasattr(self, "_backup_rows"):
			return
		if self._should_skip_header_click(col):
			return
		self._ensure_sort_state()
		if col == 0:  # Type column cycles neutral -> asc -> desc -> neutral
			order = ["none", "asc", "desc"]
			idx = order.index(self._type_sort_mode)
			self._type_sort_mode = order[(idx + 1) % len(order)]
		elif col == 1:  # Date column toggles between latest top/bottom
			self._date_sort_mode = "asc" if self._date_sort_mode == "desc" else "desc"
		else:
			return
		self._sort_backup_rows()

	def eventFilter(self, obj, event):  # type: ignore[override]
		header = getattr(self, "_table_header", None)
		if obj == header and event.type() == QEvent.Type.MouseButtonDblClick:
			pos = event.position().toPoint()
			col = header.logicalIndexAt(pos)
			if col >= 0:
				self._on_table_header_clicked(col)
			return True
		return super().eventFilter(obj, event)

	def perform_restore(self) -> None:
		if not self.current_profile:
			return
		rows = self._get_selected_rows()
		if len(rows) != 1:
			return
		row_idx = rows[0]
		fpath_str = self.table.item(row_idx, 4).data(Qt.ItemDataRole.UserRole)
		fpath = Path(fpath_str)
		plugin = self.plugin_manager.get_plugin_for_profile(self.current_profile.plugin_id)
		if not ensure_plugin_restore_inputs(self, self.current_profile, plugin, self.config):
			return
		if not offer_plugin_restore_input_review(self, self.current_profile, plugin, self.config):
			return
		if not confirm_restore(self, self.current_profile, plugin, self.config, fpath):
			return
		profile_dict = self.current_profile.as_operation_dict(plugin)
		if plugin is not None:
			profile_dict = plugin.preprocess_restore(profile_dict)
			if not self.current_profile.plugin_id:
				self.current_profile.save_path = profile_dict.get("save_path", self.current_profile.save_path)
		try:
			run_restore(self.current_profile, self.config, fpath, clear_before_restore(plugin), plugin)
		except Exception as e:
			self.log(f"RESTORE ERROR: {e}")
			QMessageBox.critical(self, "Error", str(e))
			return
		result_data = {"backup_path": str(fpath)}
		if plugin is not None:
			result_data = plugin.postprocess_restore(result_data)
		self.log("RESTORE COMPLETE")
		QMessageBox.information(self, "Done", "Game Restored Successfully.")
		self.refresh_backups()

	def open_selected_backup_location(self) -> None:
		rows = self._get_selected_rows()
		if len(rows) != 1:
			return
		row_idx = rows[0]
		fpath_str = self.table.item(row_idx, 4).data(Qt.ItemDataRole.UserRole)
		if not fpath_str:
			return
		fpath = Path(fpath_str)
		if not fpath.exists():
			QMessageBox.warning(self, "Open", "File no longer exists on disk.")
			return
		folder = fpath.parent
		try:
			open_path_in_explorer(folder)
			self.log(f"Opened folder: {folder}")
		except Exception as e:
			QMessageBox.critical(self, "Open Failed", str(e))

	def _on_table_context_menu(self, pos) -> None:
		index = self.table.indexAt(pos)
		menu = None
		if index.isValid():
			menu = self._build_backup_context_menu(index.row())
		else:
			return
		if menu:
			menu.exec(self.table.mapToGlobal(pos))

	def _build_backup_context_menu(self, row: int):
		from PyQt6.QtWidgets import QMenu
		fpath_item = self.table.item(row, 4)
		if not fpath_item:
			return None
		fpath_str = fpath_item.data(Qt.ItemDataRole.UserRole)
		menu = QMenu(self)
		# Style context menu so disabled items are visually dimmed (light theme: ash text + bg)
		try:
			eff = ThemeManager.get_effective_theme(QApplication.instance(), self.config.theme)
			if eff == "light":
				menu_bg = "#ffffff"
				txt = "#222222"
				disabled_txt = "#777777"
				disabled_bg = "#f5f5f5"
			else:
				menu_bg = "#2b2b2b"
				txt = "#ffffff"
				disabled_txt = "#777777"
				disabled_bg = "transparent"
			# Separate hover colors for enabled and disabled items
			if eff == "light":
				enabled_hover = "#e8f4ff"  # light bluish hover for actionable items
				disabled_hover = "#f5f5f5"  # subtle ash for disabled items
			else:
				enabled_hover = "#335b86"
				disabled_hover = "#3a3a3a"
			menu.setStyleSheet(
				f"QMenu {{ background-color: {menu_bg}; color: {txt}; padding: 4px; }}"
				f"QMenu::item {{ padding: 6px 24px; }}"
				f"QMenu::item:enabled:selected {{ background-color: {enabled_hover}; color: {txt}; }}"
				f"QMenu::item:disabled:selected {{ background-color: {disabled_hover}; color: {disabled_txt}; }}"
				f"QMenu::item:disabled {{ color: {disabled_txt}; background-color: transparent; }}"
			)
		except Exception:
			self.log("Context menu styling failed")
		selected_rows = self._get_selected_rows()
		# If user right-clicks a row that's not part of the existing selection,
		# treat it as a single selection for the purposes of the context menu.
		if not selected_rows or row not in selected_rows:
			selected_rows = [row]
		multi = len(selected_rows) != 1
		# Use the same enable/disable logic as the bottom buttons so state matches
		open_enabled = getattr(self, "btn_open_sel", None) is not None and self.btn_open_sel.isEnabled() and not multi
		restore_enabled = getattr(self, "btn_restore_sel", None) is not None and self.btn_restore_sel.isEnabled() and not multi
		delete_enabled = getattr(self, "btn_delete_sel", None) is not None and self.btn_delete_sel.isEnabled() and len(selected_rows) > 0
		act_open = menu.addAction("📂 Open in Explorer")
		act_open.setEnabled(open_enabled)
		act_open.triggered.connect(lambda: self._open_path_parent(fpath_str))
		act_restore = menu.addAction("♻️ Restore This Backup")
		act_restore.setEnabled(restore_enabled)
		act_restore.triggered.connect(lambda: self._restore_row(row))
		act_delete = menu.addAction("🗑️ Delete Selected")
		act_delete.setEnabled(delete_enabled)
		act_delete.triggered.connect(self.delete_selected_backups)
		return menu

	def _open_path_parent(self, fpath_str: str) -> None:
		if not fpath_str:
			return
		p = Path(fpath_str)
		if not p.exists():
			QMessageBox.warning(self, "Open", "File no longer exists.")
			return
		parent = p.parent
		try:
			open_path_in_explorer(parent)
			self.log(f"Opened folder: {parent}")
		except Exception as e:
			QMessageBox.critical(self, "Open Failed", str(e))

	def _restore_row(self, row: int) -> None:
		# Select the row, then call perform_restore
		self.table.selectRow(row)
		self.perform_restore()

	def delete_selected_backups(self) -> None:
		rows = self._get_selected_rows()
		if not rows:
			return
		files = []
		for r in rows:
			item = self.table.item(r, 4)
			if item is None:
				continue
			path_str = item.data(Qt.ItemDataRole.UserRole)
			if path_str:
				files.append(Path(path_str))
		if not files:
			return
		preview = "\n".join(p.name for p in files[:5])
		if len(files) > 5:
			preview += "\n..."
		msg = f"Delete {len(files)} backup(s)?\n\n{preview}"
		res = QMessageBox.warning(
			self,
			"Delete Backups",
			msg,
			QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
		)
		if res != QMessageBox.StandardButton.Yes:
			return
		deleted = 0
		for path in files:
			try:
				if path.exists():
					path.unlink()
				deleted += 1
			except Exception as e:
				self.log(f"DELETE ERROR: {e}")
		self.log(f"Deleted {deleted} backup(s)")
		self.refresh_backups()

	def log(self, msg: str) -> None:
		# PlainTextEdit uses appendPlainText instead of append
		self.log_view.insertPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def run_app() -> int:
	app = QApplication(sys.argv)
	app.setStyle("Fusion")
	w = MainWindow()
	w.show()
	return app.exec()

