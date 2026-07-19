from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
	QAbstractItemView,
	QHBoxLayout,
	QHeaderView,
	QTableWidgetItem,
	QVBoxLayout,
	QWidget,
)

from qfluentwidgets import (
	InfoBar,
	LineEdit,
	PlainTextEdit,
	PrimaryPushButton,
	PushButton,
	StrongBodyLabel,
	TableWidget,
	FluentIcon as FIF,
)

from ..plugin_manager import (
	PluginManager,
	PluginLoadReport,
	format_load_report_summary,
	format_load_report_verbose,
)
from ..core import ConfigManager
from ..developer_mode import dev_toast_duration_ms, is_developer_mode, set_dev_widgets_visible
from ..ui_helpers import is_app_dark
from .helpers import _install_read_only_table
from ..fluent_window import toast_parent
from .styles import AdaptiveThemeStyles


class ModernPluginsInterface(QWidget):
    """Plugin management interface for detection, installation, and configuration."""
    profiles_changed = pyqtSignal()
    
    def __init__(self, config: ConfigManager, plugin_manager: PluginManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.plugin_manager = plugin_manager
        self._plugin_issue_by_id: dict[str, list] = {}
        
        self._setup_ui()
        self.apply_load_report(self.plugin_manager.last_load_report)
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        header.addWidget(StrongBodyLabel("Game Plugins"))
        header.addStretch()
        
        self.refresh_btn = PushButton(FIF.SYNC, "Reload Plugins")
        self.refresh_btn.clicked.connect(self._reload_plugins)
        self.refresh_btn.setVisible(False)
        header.addWidget(self.refresh_btn)

        # Search bar for plugins
        self.search_edit = LineEdit()
        self.search_edit.setPlaceholderText("Search plugins...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        header.addWidget(self.search_edit)

        self.detect_btn = PrimaryPushButton(FIF.SEARCH, "Detect Installed")
        self.detect_btn.clicked.connect(self._detect_games)
        header.addWidget(self.detect_btn)

        # Add selected button - explicit add action
        self.add_selected_btn = PushButton(FIF.ADD, "Add Selected")
        self.add_selected_btn.clicked.connect(self._add_selected)
        header.addWidget(self.add_selected_btn)

        layout.addLayout(header)

        # Plugins table
        self.plugins_table = TableWidget()
        self.plugins_table.setColumnCount(5)
        self.plugins_table.setHorizontalHeaderLabels(
            ["Game", "ID", "Save Paths", "Added", "Load status"]
        )
        self.plugins_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Allow selecting multiple rows (shift/ctrl) but keep rows selectable when dimmed
        self.plugins_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.plugins_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.plugins_table.setAlternatingRowColors(True)
        styles = AdaptiveThemeStyles()
        styles.apply_table_style(self.plugins_table)
        _install_read_only_table(self.plugins_table)

        layout.addWidget(self.plugins_table)

        self.load_log = PlainTextEdit()
        self.load_log.setReadOnly(True)
        self.load_log.setPlaceholderText("Plugin reload diagnostics appear here after hot reload or manual reload.")
        self.load_log.setMaximumHeight(180)
        self.load_log.setVisible(False)
        layout.addWidget(self.load_log)

    def _reload_plugins(self) -> None:
        """Hot-reload plugin modules and refresh the table."""

        hot = getattr(self.window(), "_plugin_hot", None)
        if hot is not None and hasattr(hot, "reload_now"):
            hot.reload_now(reason="manual button")
            return
        report = self.plugin_manager.reload_plugins(hot=True)
        self.apply_load_report(report)
        self._notify_reload_result(report)

    def apply_load_report(self, report: PluginLoadReport | None) -> None:
        """Refresh plugin table and diagnostics from a load report."""

        if report is None:
            report = self.plugin_manager.last_load_report
        self._plugin_issue_by_id = {}
        for issue in report.issues:
            token = issue.source
            pid = ""
            if token.startswith("code:"):
                body = token[5:]
                if "#[" in body:
                    body = body.split("#[", 1)[0]
                if " (" in body:
                    body = body.split(" (", 1)[0]
                pid = body.strip()
            elif token.startswith("json:") and "#[" in token:
                pass
            elif token.startswith("plugin:"):
                pid = token.split(":", 1)[1].strip()
            if pid:
                self._plugin_issue_by_id.setdefault(pid, []).append(issue)
        self.load_log.setPlainText(format_load_report_verbose(report))
        self._load_plugins()

    def _notify_reload_result(self, report: PluginLoadReport, *, dev_mode: bool | None = None) -> None:
        if dev_mode is None:
            dev_mode = is_developer_mode(self.config)
        summary = format_load_report_summary(report)
        parent = toast_parent(self)
        duration = dev_toast_duration_ms(enabled=dev_mode, normal_ms=4000, dev_ms=12000)
        if report.ok:
            if report.warning_count:
                msg = summary
                if dev_mode and report.issues:
                    msg = summary + "\n" + report.issues[0].message
                InfoBar.warning("Plugins reloaded", msg, parent=parent, duration=duration)
            else:
                InfoBar.success("Plugins reloaded", summary, parent=parent, duration=duration)
        else:
            detail = summary
            if dev_mode and report.issues:
                first = report.issues[0]
                detail = f"{summary}\n{first.source}: {first.message}"
            InfoBar.error(
                "Plugin reload had errors",
                detail + (" See diagnostics below." if dev_mode else " Enable developer mode for details."),
                parent=parent,
                duration=duration,
            )

    def set_developer_mode(self, enabled: bool) -> None:
        set_dev_widgets_visible(enabled, (self.refresh_btn, self.load_log))
        if enabled and self.plugin_manager.last_load_report.issues:
            self.load_log.setPlainText(format_load_report_verbose(self.plugin_manager.last_load_report))

    def _load_plugins(self):
        """Load plugins into table."""
        self.plugins_table.setRowCount(0)
        self._plugin_rows = []

        for plugin_id, plugin in self.plugin_manager.available_plugins.items():
            row = self.plugins_table.rowCount()
            self.plugins_table.insertRow(row)


            # Game name
            name_item = QTableWidgetItem(plugin.game_name)
            self.plugins_table.setItem(row, 0, name_item)
            # ID
            id_item = QTableWidgetItem(plugin_id)
            self.plugins_table.setItem(row, 1, id_item)
            # Save paths
            paths = "\n".join(plugin.save_paths)
            paths_item = QTableWidgetItem(paths)
            self.plugins_table.setItem(row, 2, paths_item)
            # Added: reflect whether this plugin is already added to profiles
            installed_ids = {p.plugin_id for p in self.config.games.values() if p.plugin_id}
            is_added = plugin.game_id in installed_ids
            added_item = QTableWidgetItem("Yes" if is_added else "No")
            self.plugins_table.setItem(row, 3, added_item)

            issues = self._plugin_issue_by_id.get(plugin_id, [])
            has_error = any(i.severity == "error" for i in issues)
            has_warn = any(i.severity == "warning" for i in issues)
            if has_error:
                status_text = "Error"
                status_tip = "\n".join(f"[{i.severity}] {i.message}" for i in issues)
            elif has_warn:
                status_text = "Warning"
                status_tip = "\n".join(f"[{i.severity}] {i.message}" for i in issues)
            else:
                status_text = "OK"
                status_tip = f"Plugin {plugin_id} loaded successfully."
            status_item = QTableWidgetItem(status_text)
            status_item.setToolTip(status_tip)
            self.plugins_table.setItem(row, 4, status_item)

            # Dim added rows slightly while keeping them selectable
            if is_added:
                dim_brush = AdaptiveThemeStyles().dim_brush()
                name_item.setForeground(dim_brush)
                id_item.setForeground(dim_brush)
                paths_item.setForeground(dim_brush)
                added_item.setForeground(dim_brush)
                status_item.setForeground(dim_brush)

            self._plugin_rows.append((plugin_id, plugin))

    def _detect_games(self):
        """Detect installed games and highlight results; do not auto-add."""
        # Perform detection scan (expensive) and highlight detected rows
        detected_ids = {p.game_id for p in self.plugin_manager.available_plugins.values() if p.is_detected()}

        # Choose a subtle, theme-aware highlight color so detection is
        # visible but not overpowering in light or dark modes.
        if is_app_dark():
            # Slight translucent green tint for dark mode
            highlight_color = QColor(34, 85, 48, 60)
        else:
            # Very light green for light mode
            highlight_color = QColor("#eef9ef")
        highlight_brush = QBrush(highlight_color)
        clear_brush = QBrush()

        for row in range(self.plugins_table.rowCount()):
            pid_item = self.plugins_table.item(row, 1)
            name_item = self.plugins_table.item(row, 0)
            added_item = self.plugins_table.item(row, 3)
            paths_item = self.plugins_table.item(row, 2)
            if not pid_item or not name_item or added_item is None:
                continue
            pid = pid_item.text()
            if pid in detected_ids:
                # Highlight the entire row background to make detection obvious
                for col_item in (name_item, pid_item, paths_item, added_item):
                    if col_item is not None:
                        col_item.setBackground(highlight_brush)
            else:
                # Clear any previous highlight
                for col_item in (name_item, pid_item, paths_item, added_item):
                    if col_item is not None:
                        col_item.setBackground(clear_brush)

        InfoBar.info(
            "Detect Complete",
            "Detected games are highlighted. Use 'Add Selected' to add profiles.",
            parent=toast_parent(self)
        )

    def _on_search_changed(self, text: str):
        t = (text or "").strip().lower()
        self.plugins_table.setRowCount(0)
        for plugin_id, plugin in self._plugin_rows:
            if not t or t in plugin.game_name.lower() or t in plugin_id.lower():
                row = self.plugins_table.rowCount()
                self.plugins_table.insertRow(row)
                name_item = QTableWidgetItem(plugin.game_name)
                id_item = QTableWidgetItem(plugin_id)
                paths_item = QTableWidgetItem("\n".join(plugin.save_paths))
                installed_ids = {p.plugin_id for p in self.config.games.values() if p.plugin_id}
                is_added = plugin.game_id in installed_ids
                added_item = QTableWidgetItem("Yes" if is_added else "No")
                issues = self._plugin_issue_by_id.get(plugin_id, [])
                has_error = any(i.severity == "error" for i in issues)
                has_warn = any(i.severity == "warning" for i in issues)
                if has_error:
                    status_text = "Error"
                elif has_warn:
                    status_text = "Warning"
                else:
                    status_text = "OK"
                status_item = QTableWidgetItem(status_text)
                self.plugins_table.setItem(row, 0, name_item)
                self.plugins_table.setItem(row, 1, id_item)
                self.plugins_table.setItem(row, 2, paths_item)
                self.plugins_table.setItem(row, 3, added_item)
                self.plugins_table.setItem(row, 4, status_item)
                if is_added:
                    dim_brush = AdaptiveThemeStyles().dim_brush()
                    name_item.setForeground(dim_brush)
                    id_item.setForeground(dim_brush)
                    paths_item.setForeground(dim_brush)
                    added_item.setForeground(dim_brush)
                    status_item.setForeground(dim_brush)

    def _add_selected(self):
        selected = self.plugins_table.selectionModel().selectedRows()
        if not selected:
            InfoBar.info(
                "No Selection",
                "Select at least one plugin to add.",
                parent=toast_parent(self)
            )
            return
        added = 0
        existing_ids = {p.plugin_id for p in self.config.games.values() if p.plugin_id}
        for idx in selected:
            row = idx.row()
            pid_item = self.plugins_table.item(row, 1)
            if not pid_item:
                continue
            pid = pid_item.text()
            plugin = self.plugin_manager.available_plugins.get(pid)
            if not plugin:
                continue
            if plugin.game_id in existing_ids:
                continue
            self.config.add_game_from_plugin(plugin.to_profile())
            added += 1
        if added:
            # Anchor toast to the app content area so it appears below titlebar
            InfoBar.success(
                "Games Added",
                f"Added {added} game(s) to profiles",
                parent=toast_parent(self)
            )
            self._load_plugins()
            
            try:
                self.profiles_changed.emit()
            except Exception:
                pass
    

