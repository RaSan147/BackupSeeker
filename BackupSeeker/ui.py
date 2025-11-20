"""Qt UI for BackupSeeker Game Save Manager.

This is a refactored version of the `MainWindow` and dialogs from
`gemini.py`, wired against the reusable core API in `BackupSeeker.core`.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QAction, QActionGroup, QFont, QPalette, QColor
from PyQt6.QtWidgets import (
	QApplication,
	QCheckBox,
	QDialog,
	QFileDialog,
	QFormLayout,
	QGroupBox,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QListWidget,
	QListWidgetItem,
	QMainWindow,
	QMessageBox,
	QPushButton,
	QTableWidget,
	QTableWidgetItem,
	QTabWidget,
	QTextEdit,
	QVBoxLayout,
	QWidget,
	QHeaderView,
)

from .core import ConfigManager, GameProfile, PathUtils
from .plugin_manager import PluginManager


class ThemeManager:
	@staticmethod
	def get_effective_theme(app: QApplication, config_theme: str) -> str:
		if config_theme == "dark":
			return "dark"
		if config_theme == "light":
			return "light"
		if hasattr(Qt, "ColorScheme"):
			try:
				scheme = app.styleHints().colorScheme()
				if scheme == Qt.ColorScheme.Dark:
					return "dark"
			except Exception:
				pass
		return "light"

	@staticmethod
	def apply_theme(app: QApplication, config_theme: str) -> None:
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


class GameEditorDialog(QDialog):
	def __init__(self, profile: Optional[GameProfile] = None, parent: QWidget | None = None) -> None:
		super().__init__(parent)
		self.profile = profile or GameProfile()
		self.setWindowTitle("Game Profile 🎮")
		self.setMinimumWidth(500)

		layout = QVBoxLayout(self)
		form = QFormLayout()

		self.name_edit = QLineEdit(self.profile.name)
		self.name_edit.setPlaceholderText("e.g. Cyberpunk 2077")

		self.path_edit = QLineEdit(self.profile.save_path)
		self.path_edit.setPlaceholderText("Paste path here...")
		path_btn = QPushButton("📂 Browse")
		path_btn.clicked.connect(self.browse_path)
		path_layout = QHBoxLayout()
		path_layout.addWidget(self.path_edit)
		path_layout.addWidget(path_btn)

		self.compress_cb = QCheckBox("Use Compression")
		self.compress_cb.setChecked(self.profile.use_compression)
		self.clear_cb = QCheckBox("Clear folder before restore")
		self.clear_cb.setChecked(self.profile.clear_folder_on_restore)

		form.addRow("Name:", self.name_edit)
		form.addRow("Path:", path_layout)
		form.addRow("", self.compress_cb)
		form.addRow("", self.clear_cb)

		layout.addLayout(form)

		btns = QHBoxLayout()
		save = QPushButton("💾 Save Profile")
		save.clicked.connect(self.save)
		cancel = QPushButton("❌ Cancel")
		cancel.clicked.connect(self.reject)
		btns.addWidget(save)
		btns.addWidget(cancel)
		layout.addLayout(btns)

	def browse_path(self) -> None:
		d = QFileDialog.getExistingDirectory(self, "Select Save Folder")
		if d:
			self.path_edit.setText(PathUtils.contract(d))

	def save(self) -> None:
		name = self.name_edit.text().strip()
		raw_path = PathUtils.clean_input_path(self.path_edit.text())
		if not name or not raw_path:
			QMessageBox.warning(self, "Error", "Name and Path are required.")
			return
		contracted_path = PathUtils.contract(raw_path)
		self.profile.name = name
		self.profile.save_path = contracted_path
		self.profile.use_compression = self.compress_cb.isChecked()
		self.profile.clear_folder_on_restore = self.clear_cb.isChecked()
		if not self.profile.id:
			self.profile.id = f"game_{datetime.now().strftime('%Y%m%d%H%M%S')}"
		self.accept()


class PluginBrowserDialog(QDialog):
	"""Panel for searching, auto-detecting and adding plugin games."""

	def __init__(self, plugin_manager: PluginManager, config: ConfigManager, parent: QWidget | None = None) -> None:
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
		self.search_edit = QLineEdit()
		self.search_edit.setPlaceholderText("Search games (plugin database)...")
		btn_search = QPushButton("🔎 Search")
		btn_search.clicked.connect(self._on_search_clicked)
		btn_reset = QPushButton("Reset")
		btn_reset.clicked.connect(self._refresh_all_plugins)
		search_row.addWidget(self.search_edit)
		search_row.addWidget(btn_search)
		search_row.addWidget(btn_reset)
		layout.addLayout(search_row)

		# List of games
		self.list_widget = QListWidget()
		layout.addWidget(self.list_widget)

		# Buttons
		btn_row = QHBoxLayout()
		btn_detect = QPushButton("🔍 Auto Detect Installed")
		btn_detect.clicked.connect(self._on_detect_clicked)
		btn_add = QPushButton("➕ Add Selected to Profiles")
		btn_add.clicked.connect(self._on_add_selected)
		btn_close = QPushButton("Close")
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
			font = item.font()
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
		self.init_ui()

	def init_ui(self) -> None:
		self.setWindowTitle("Game Save Manager 💾 (BackupSeeker)")
		self.resize(1000, 700)
		self.create_menu()

		central = QWidget()
		self.setCentralWidget(central)
		main_h = QHBoxLayout(central)

		left = QVBoxLayout()
		self.game_list = QListWidget()
		self.game_list.itemSelectionChanged.connect(self.on_game_select)
		left.addWidget(QLabel("Profiles"))
		left.addWidget(self.game_list)

		btn_add = QPushButton("➕ Add Game")
		btn_add.clicked.connect(self.add_game)
		left.addWidget(btn_add)

		self.btn_edit = QPushButton("✏️ Edit")
		self.btn_edit.clicked.connect(self.edit_game)
		left.addWidget(self.btn_edit)

		self.btn_del = QPushButton("🗑️ Delete")
		self.btn_del.clicked.connect(self.delete_game)
		left.addWidget(self.btn_del)

		left_widget = QWidget()
		left_widget.setLayout(left)
		left_widget.setFixedWidth(250)

		self.tabs = QTabWidget()

		self.tab_dash = QWidget()
		dash_layout = QVBoxLayout(self.tab_dash)
		self.lbl_title = QLabel("Select a game")
		self.lbl_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
		self.lbl_path = QLabel("Path: -")

		self.btn_backup = QPushButton("💾 BACKUP NOW")
		self.btn_backup.setMinimumHeight(40)
		self.btn_backup.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
		self.btn_backup.clicked.connect(self.perform_backup)

		self.log_view = QTextEdit()
		self.log_view.setReadOnly(True)

		dash_layout.addWidget(self.lbl_title)
		dash_layout.addWidget(self.lbl_path)
		dash_layout.addSpacing(10)
		dash_layout.addWidget(self.btn_backup)
		dash_layout.addWidget(QLabel("Activity Log:"))
		dash_layout.addWidget(self.log_view)

		self.tabs.addTab(self.tab_dash, "Dashboard")

		self.tab_restore = QWidget()
		restore_layout = QVBoxLayout(self.tab_restore)
		self.table = QTableWidget()
		self.table.setColumnCount(4)
		self.table.setHorizontalHeaderLabels(["Type", "Date", "Size", "Filename"])
		header = self.table.horizontalHeader()
		header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
		header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
		header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
		header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
		self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

		self.btn_restore_sel = QPushButton("♻️ Restore Selected")
		self.btn_restore_sel.clicked.connect(self.perform_restore)
		self.btn_refresh = QPushButton("🔄 Refresh List")
		self.btn_refresh.clicked.connect(self.refresh_backups)

		restore_layout.addWidget(self.table)
		restore_layout.addWidget(self.btn_refresh)
		restore_layout.addWidget(self.btn_restore_sel)
		self.tabs.addTab(self.tab_restore, "Backups / Restore")

		main_h.addWidget(left_widget)
		main_h.addWidget(self.tabs)

		ThemeManager.apply_theme(QApplication.instance(), self.config.theme)
		self.update_button_styles()
		self.refresh_game_list()
		self.update_ui_state()

		if self.config.window_geometry:
			try:
				ba = QByteArray.fromHex(self.config.window_geometry.encode("ascii"))
				self.restoreGeometry(ba)
			except Exception:
				pass

	def showEvent(self, event):  # type: ignore[override]
		super().showEvent(event)
		if self.config.table_widths:
			for i, w in enumerate(self.config.table_widths):
				if i < 3:
					self.table.setColumnWidth(i, w)
		else:
			total_w = self.table.width()
			if total_w > 0:
				col_w = int(total_w * 0.15)
				self.table.setColumnWidth(0, col_w)
				self.table.setColumnWidth(1, col_w)
				self.table.setColumnWidth(2, col_w)

	def closeEvent(self, event):  # type: ignore[override]
		self.config.window_geometry = self.saveGeometry().toHex().data().decode("ascii")
		widths = [self.table.columnWidth(i) for i in range(3)]
		self.config.table_widths = widths
		self.config.save_config()
		event.accept()

	def create_menu(self) -> None:
		bar = self.menuBar()
		view = bar.addMenu("View")
		plugins_menu = bar.addMenu("Plugins")
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

	def open_plugin_panel(self) -> None:
		dlg = PluginBrowserDialog(self.plugin_manager, self.config, self)
		if dlg.exec():
			# Profiles may have changed
			self.refresh_game_list()

	def refresh_game_list(self) -> None:
		self.game_list.clear()
		for pid, p in self.config.games.items():
			item = QListWidgetItem(f"🎮 {p.name}")
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
		if enabled and self.current_profile is not None:
			self.lbl_title.setText(f"🎮 {self.current_profile.name}")
			self.lbl_path.setText(f"Path: {self.current_profile.save_path}")
		else:
			self.lbl_title.setText("Select a Game")
			self.lbl_path.setText("-")
			self.table.setRowCount(0)

	def add_game(self) -> None:
		dlg = GameEditorDialog(parent=self)
		if dlg.exec():
			self.config.games[dlg.profile.id] = dlg.profile
			self.config.save_config()
			self.refresh_game_list()
			self.log(f"Added {dlg.profile.name}")

	def edit_game(self) -> None:
		if not self.current_profile:
			return
		dlg = GameEditorDialog(self.current_profile, self)
		if dlg.exec():
			self.config.save_config()
			self.refresh_game_list()
			self.on_game_select()
			self.log(f"Updated {self.current_profile.name}")

	def delete_game(self) -> None:
		if not self.current_profile:
			return
		res = QMessageBox.question(self, "Delete", f"Delete profile '{self.current_profile.name}'?")
		if res == QMessageBox.StandardButton.Yes:
			del self.config.games[self.current_profile.id]
			self.config.save_config()
			self.refresh_game_list()
			self.current_profile = None
			self.update_ui_state()

	def perform_backup(self) -> None:
		from .core import run_backup

		if not self.current_profile:
			return
		self.log(f"Starting backup for {self.current_profile.name}...")
		# Apply optional plugin preprocess/postprocess hooks
		plugin = self.plugin_manager.get_plugin_for_profile(self.current_profile.plugin_id)
		profile_dict = self.current_profile.to_dict()
		if plugin is not None:
			profile_dict = plugin.preprocess_backup(profile_dict)
			# push any changed save_path back into profile
			self.current_profile.save_path = profile_dict.get("save_path", self.current_profile.save_path)
		try:
			dest = run_backup(self.current_profile, self.config)
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
		from .core import ConfigManager

		self.table.setRowCount(0)
		if not self.current_profile:
			return
		reg_dir = self.config.get_game_backup_dir(self.current_profile.name)
		backups = list(reg_dir.glob("*.zip"))
		safe_dir = self.config.get_safety_backup_dir(self.current_profile.name)
		safety_backups = list(safe_dir.glob("*.zip"))
		all_files = []
		for f in backups:
			all_files.append((f, "Regular"))
		for f in safety_backups:
			all_files.append((f, "Safety"))
		all_files.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)

		for fpath, btype in all_files:
			row = self.table.rowCount()
			self.table.insertRow(row)
			type_str = "🛡️ Safety" if btype == "Safety" else "💾 Regular"
			self.table.setItem(row, 0, QTableWidgetItem(type_str))
			dt = datetime.fromtimestamp(fpath.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
			self.table.setItem(row, 1, QTableWidgetItem(dt))
			sz = f"{fpath.stat().st_size/1024/1024:.1f} MB"
			self.table.setItem(row, 2, QTableWidgetItem(sz))
			item = QTableWidgetItem(fpath.name)
			item.setData(Qt.ItemDataRole.UserRole, str(fpath))
			self.table.setItem(row, 3, item)

	def perform_restore(self) -> None:
		from .core import run_restore

		if not self.current_profile:
			return
		rows = self.table.selectedItems()
		if not rows:
			return
		row_idx = rows[0].row()
		fpath_str = self.table.item(row_idx, 3).data(Qt.ItemDataRole.UserRole)
		fpath = Path(fpath_str)
		res = QMessageBox.warning(
			self,
			"Restore",
			f"Are you sure you want to restore?\n{fpath.name}\n\nCurrent data will be archived in the 'Safety' folder.",
			QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
		)
		if res == QMessageBox.StandardButton.Yes:
			plugin = self.plugin_manager.get_plugin_for_profile(self.current_profile.plugin_id)
			profile_dict = self.current_profile.to_dict()
			if plugin is not None:
				profile_dict = plugin.preprocess_restore(profile_dict)
				self.current_profile.save_path = profile_dict.get("save_path", self.current_profile.save_path)
			try:
				run_restore(self.current_profile, self.config, fpath, self.current_profile.clear_folder_on_restore)
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

	def log(self, msg: str) -> None:
		self.log_view.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def run_app() -> int:
	app = QApplication(sys.argv)
	app.setStyle("Fusion")
	w = MainWindow()
	w.show()
	return app.exec()

