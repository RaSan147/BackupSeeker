from __future__ import annotations

import os
import subprocess
import time
from typing import Any
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, QSize, Qt
from PyQt6.QtWidgets import (
	QAbstractItemView,
	QApplication,
	QHBoxLayout,
	QHeaderView,
	QLabel,
	QListView,
	QListWidget,
	QListWidgetItem,
	QVBoxLayout,
	QWidget,
	QTableWidgetItem,
)

from qfluentwidgets import (
	BodyLabel,
	CaptionLabel,
	ComboBox,
	InfoBar,
	PushButton,
	RoundMenu,
	Action,
	StrongBodyLabel,
	TableWidget,
	FluentIcon as FIF,
)

from ..core import (
	ConfigManager,
	clear_before_restore,
	read_archive_metadata,
	run_restore,
	summarize_archive_metadata,
)
from ..developer_mode import set_dev_widgets_visible
from ..fluent_window import resolve_plugin_for_profile, toast_parent
from ..plugin_runtime import PluginHookError, run_plugin_hook
from ..modern_widgets import RoundedCard
from ..ui_shared import (
	confirm_action,
	confirm_restore,
	ensure_plugin_restore_inputs,
	offer_plugin_restore_input_review,
	open_path_in_explorer,
)
from .helpers import (
	_install_read_only_table,
	_make_transparent_widget,
	_profile_display_name,
	_profile_kind_prefix,
	apply_combo_ui_view,
	ui_view_mode_from_combo_text,
)
from .styles import AdaptiveThemeStyles, LIST_STYLE_TRANSPARENT


class ModernBackupsInterface(QWidget):
    """Backup management interface with sorting, restore, and delete operations."""
    
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_profile = None
        self._backup_rows: list[dict[str, Any]] = []
        self._type_sort_mode = "none"
        self._date_sort_mode = "desc"
        self._last_header_col: int | None = None
        self._last_header_time = 0.0

        self._setup_ui()
        
    def _setup_ui(self):
        if self.layout() is None:
            layout = QVBoxLayout(self)
        else:
            layout = self.layout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        header.addWidget(StrongBodyLabel("Backups Management"))
        header.addStretch()
        
        # View mode selector (List / Cards)
        self.backups_view_toggle = ComboBox()
        self.backups_view_toggle.addItem("List")
        self.backups_view_toggle.addItem("Cards")
        self.backups_view_toggle.setFixedWidth(110)
        self.backups_view_toggle.currentTextChanged.connect(self._on_backups_view_changed)
        header.addWidget(self.backups_view_toggle)
        apply_combo_ui_view(self.backups_view_toggle, self.config.ui_view_backups_management)
        
        self.refresh_btn = PushButton(FIF.SYNC, "Refresh")
        self.refresh_btn.clicked.connect(self._dev_refresh)
        self.refresh_btn.setToolTip("Developer: rescan backup files for the selected profile")
        self.refresh_btn.setVisible(False)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # Profile selector
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(BodyLabel("Select Game:"))
        
        self.profile_combo = ComboBox()
        self.profile_combo.setMinimumWidth(200)
        self.profile_combo.currentTextChanged.connect(self._on_profile_selected)
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addStretch()
        
        layout.addLayout(profile_layout)
        
        # Backups table
        self.backups_table = TableWidget()
        self.backups_table.setColumnCount(6)
        self.backups_table.setHorizontalHeaderLabels(
            ["Type", "Date", "Size", "Archive", "Filename", "Actions"]
        )
        header = self.backups_table.horizontalHeader()
        # Keep a reference to the header and enable clickable sections so
        # the sort handlers and event filter can work reliably.
        self._table_header = header
        header.setSectionsClickable(True)
        header.sectionPressed.connect(self._on_table_header_clicked)
        header.installEventFilter(self)
        # Make date and size compact, filename stretch, actions sized to contents
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.backups_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backups_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.backups_table.customContextMenuRequested.connect(self._show_context_menu)
        # Apply theme-aware stylesheet
        styles = AdaptiveThemeStyles()
        styles.apply_table_style(self.backups_table)
        _install_read_only_table(self.backups_table)
        
        # Backups list (card view)
        self.backups_card_list = QListWidget()
        self.backups_card_list.setViewMode(QListView.ViewMode.IconMode)
        self.backups_card_list.setIconSize(QSize(240, 135))
        self.backups_card_list.setGridSize(QSize(280, 200))
        self.backups_card_list.setSpacing(12)
        self.backups_card_list.setStyleSheet(LIST_STYLE_TRANSPARENT)
        self.backups_card_list.setDragEnabled(False)
        self.backups_card_list.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.backups_card_list.setMovement(QListView.Movement.Static)
        self.backups_card_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backups_card_list.setFlow(QListView.Flow.LeftToRight)
        self.backups_card_list.setWrapping(True)
        self.backups_card_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.backups_card_list.setUniformItemSizes(True)
        _make_transparent_widget(self.backups_card_list)
        
        layout.addWidget(self.backups_table)
        layout.addWidget(self.backups_card_list)
        
        # Load profiles
        self._load_profiles()
        
    def _load_profiles(self):
        """Load profiles into combo box - fixed for possible icon issues."""
        self.profile_combo.clear()
        self.profile_combo.addItem("Select a game...")

        for profile in self.config.games.values():
            # Add by name and attach the profile as user data.
            # Avoid using icons here because some ComboBox/theme mixes
            # can raise errors when icons are present or mismatched.
            index = self.profile_combo.count()
            self.profile_combo.addItem(_profile_kind_prefix(profile) + _profile_display_name(profile, self))
            # store the profile object as user data on the new item
            self.profile_combo.setItemData(index, profile)
            
    def _on_profile_selected(self, text):
        """Handle profile selection."""
        if text == "Select a game...":
            self.current_profile = None
            self.backups_table.setRowCount(0)
            return

        # Prefer the attached user data (safer than relying on visible text)
        profile = self.profile_combo.currentData()
        if profile:
            self.current_profile = profile
            self._refresh_backups()
            return

        # Fallback: try to find a profile by the shown text (handles
        # cases where currentData isn't available due to styling/plugins)
        for p in self.config.games.values():
            if (_profile_kind_prefix(p) + _profile_display_name(p, self)) == text:
                self.current_profile = p
                self._refresh_backups()
                break
            
    def _refresh_backups(self):
        """Refresh backups list and populate internal rows for sorting/rendering."""
        if not self.current_profile:
            return

        # Build row cache similar to classic UI so we can provide sorting
        self._backup_rows = []

        # Get dirs
        plug = resolve_plugin_for_profile(self.current_profile, self)
        backup_dir = self.config.backup_dir_for_profile(self.current_profile, plug)
        safety_dir = self.config.safety_backup_dir_for_profile(self.current_profile, plug)

        # Collect files
        if backup_dir.exists():
            for f in backup_dir.glob("*.zip"):
                self._backup_rows.append({
                    "path_obj": f,
                    "type": "💾 Regular",
                    "type_rank": 0,
                    "timestamp": f.stat().st_mtime,
                    "bytes": f.stat().st_size,
                    "filename": f.name,
                })
        if safety_dir.exists():
            for f in safety_dir.glob("*.zip"):
                self._backup_rows.append({
                    "path_obj": f,
                    "type": "🛡️ Safety",
                    "type_rank": 1,
                    "timestamp": f.stat().st_mtime,
                    "bytes": f.stat().st_size,
                    "filename": f.name,
                })

        # Prepare display fields + manifest summary for each ZIP
        for r in self._backup_rows:
            bsize = r["bytes"]
            if bsize < 1024 * 1024:
                r["size_display"] = f"{bsize/1024:.1f} KB"
            else:
                r["size_display"] = f"{bsize/1024/1024:.1f} MB"
            r["date_display"] = datetime.fromtimestamp(r["timestamp"]).strftime("%Y-%m-%d %H:%M")
            po = r.get("path_obj")
            meta = read_archive_metadata(po) if po else None
            summ = summarize_archive_metadata(meta, zip_path=po if po else Path("."))
            r["manifest_meta"] = summ
            r["archive_summary"] = summ.get("summary", "")
            r["archive_tooltip"] = summ.get("tooltip", "")

        # Sort and render
        self._sort_backup_rows()

    def _sort_backup_rows(self):
        def sort_key(row):
            if self._type_sort_mode == "asc":
                type_key = row.get("type_rank", 0)
            elif self._type_sort_mode == "desc":
                type_key = -row.get("type_rank", 0)
            else:
                type_key = 0
            ts = row.get("timestamp", 0)
            date_key = -ts if self._date_sort_mode == "desc" else ts
            return (type_key, date_key)

        self._backup_rows.sort(key=sort_key)
        self._render_backup_rows()
        self._update_header_sort_indicators()

    def _render_backup_rows(self):
        # Determine which view is active
        mode = self.backups_view_toggle.currentText()
        is_cards = (mode or '').lower().startswith('c')
        
        if is_cards:
            # Card view
            self.backups_card_list.clear()
            for r in self._backup_rows:
                item = QListWidgetItem()
                item.setSizeHint(QSize(280, 200))
                item.setData(Qt.ItemDataRole.UserRole, r.get("path_obj"))
                self.backups_card_list.addItem(item)
                widget = self._create_backup_card(r)
                self.backups_card_list.setItemWidget(item, widget)
        else:
            # Table view
            self.backups_table.setRowCount(0)
            for r in self._backup_rows:
                row = self.backups_table.rowCount()
                self.backups_table.insertRow(row)
                self.backups_table.setItem(row, 0, QTableWidgetItem(r.get("type", "")))
                self.backups_table.setItem(row, 1, QTableWidgetItem(r.get("date_display", "")))
                self.backups_table.setItem(row, 2, QTableWidgetItem(r.get("size_display", "")))
                arch_item = QTableWidgetItem(r.get("archive_summary", ""))
                arch_item.setToolTip(r.get("archive_tooltip", ""))
                self.backups_table.setItem(row, 3, arch_item)
                item = QTableWidgetItem(r.get("filename", ""))
                item.setData(Qt.ItemDataRole.UserRole, r.get("path_obj"))
                item.setToolTip(r.get("archive_tooltip", ""))
                self.backups_table.setItem(row, 4, item)

                # Actions widget
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(5, 5, 5, 5)
                restore_btn = PushButton("Restore")
                restore_btn.setFixedWidth(100)
                restore_btn.clicked.connect(lambda checked, p=r.get("path_obj"): self._restore_backup(p))
                action_layout.addWidget(restore_btn)
                view_btn = PushButton("View")
                view_btn.setFixedWidth(90)
                view_btn.clicked.connect(lambda checked, p=r.get("path_obj"): self._view_backup(p))
                action_layout.addWidget(view_btn)
                delete_btn = PushButton("Delete")
                delete_btn.setFixedWidth(90)
                delete_btn.clicked.connect(lambda checked, p=r.get("path_obj"): self._delete_backup(p))
                action_layout.addWidget(delete_btn)
                action_layout.addStretch()
                self.backups_table.setCellWidget(row, 5, action_widget)

            # Ensure selection/controls are updated
            try:
                sel_model = self.backups_table.selectionModel()
                if sel_model:
                    sel_model.clearSelection()
            except Exception:
                pass
        
        # Toggle visibility
        self.backups_table.setVisible(not is_cards)
        self.backups_card_list.setVisible(is_cards)
    
    def _on_backups_view_changed(self, text: str):
        """Switch between List and Cards view for backups."""
        self.config.ui_view_backups_management = ui_view_mode_from_combo_text(text)
        self.config.save_config()
        self._render_backup_rows()
    
    def _create_backup_card(self, backup_row: dict) -> QWidget:
        """Create a card widget for a backup with clean typography."""
        styles = AdaptiveThemeStyles()
        card = RoundedCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)
        card.setObjectName("backupMgmtCard")
        card.setStyleSheet(styles.info_panel_stylesheet("backupMgmtCard", radius=10))

        # Type + icon (header)
        type_label = BodyLabel(backup_row.get("type", "Backup"))
        type_label.setStyleSheet(f"BodyLabel{{font-weight: bold; font-size: 14px; color:{styles.text_primary()};}}")
        card_layout.addWidget(type_label)
        
        # Date
        date_label = BodyLabel(backup_row.get("date_display", ""))
        date_label.setStyleSheet(f"BodyLabel{{font-size: 12px; color: {styles.text_secondary()};}}")
        card_layout.addWidget(date_label)
        
        # Size
        size_label = CaptionLabel(backup_row.get("size_display", ""))
        size_label.setStyleSheet(f"CaptionLabel{{color: {styles.text_muted()}; font-size: 11px;}}")
        card_layout.addWidget(size_label)
        
        # Separator
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {styles.separator()};")
        card_layout.addWidget(sep)

        arch = (backup_row.get("archive_summary") or "").strip()
        if arch:
            arch_lbl = CaptionLabel(arch[:90] + ("…" if len(arch) > 90 else ""))
            arch_lbl.setToolTip(backup_row.get("archive_tooltip", "") or arch)
            arch_lbl.setStyleSheet(
                f"CaptionLabel{{color: {styles.text_secondary()}; font-size: 11px;}}"
            )
            arch_lbl.setWordWrap(True)
            card_layout.addWidget(arch_lbl)
        
        # Filename (truncated but more readable)
        filename = backup_row.get("filename", "")
        if len(filename) > 35:
            filename = filename[:32] + "..."
        filename_label = CaptionLabel(filename)
        filename_label.setStyleSheet(f"CaptionLabel{{color: {styles.text_secondary()}; font-size: 11px; font-family: monospace;}}")
        filename_label.setWordWrap(True)
        card_layout.addWidget(filename_label)
        
        card_layout.addStretch()
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        restore_btn = PushButton("Restore")
        restore_btn.setFixedWidth(90)
        restore_btn.setFixedHeight(32)
        restore_btn.clicked.connect(lambda checked, p=backup_row.get("path_obj"): self._restore_backup(p))
        button_layout.addWidget(restore_btn)

        view_btn = PushButton("View")
        view_btn.setFixedWidth(74)
        view_btn.setFixedHeight(32)
        view_btn.clicked.connect(lambda checked, p=backup_row.get("path_obj"): self._view_backup(p))
        button_layout.addWidget(view_btn)
        
        delete_btn = PushButton("Delete")
        delete_btn.setFixedWidth(80)
        delete_btn.setFixedHeight(32)
        delete_btn.clicked.connect(lambda checked, p=backup_row.get("path_obj"): self._delete_backup(p))
        button_layout.addWidget(delete_btn)
        button_layout.addStretch()
        
        card_layout.addLayout(button_layout)
        
        return card

    def _update_header_sort_indicators(self):
        labels = ["Type", "Date", "Size", "Archive", "Filename", "Actions"]
        if self._type_sort_mode != "none":
            arrow = "↑" if self._type_sort_mode == "asc" else "↓"
            labels[0] = f"{labels[0]} {arrow}"
        arrow = "↑" if self._date_sort_mode == "asc" else "↓"
        labels[1] = f"{labels[1]} {arrow}"
        self.backups_table.setHorizontalHeaderLabels(labels)

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
        last_col = self._last_header_col
        last_time = self._last_header_time
        if last_col == col and (now - last_time) < interval:
            return True
        self._last_header_col = col
        self._last_header_time = now
        return False

    def _on_table_header_clicked(self, col: int):
        if self._should_skip_header_click(col):
            return
        if col == 0:
            order = ["none", "asc", "desc"]
            idx = order.index(self._type_sort_mode)
            self._type_sort_mode = order[(idx + 1) % len(order)]
        elif col == 1:
            self._date_sort_mode = "asc" if self._date_sort_mode == "desc" else "desc"
        else:
            return
        self._sort_backup_rows()

    def eventFilter(self, obj, event):
        header = self._table_header
        if obj == header and event.type() == QEvent.Type.MouseButtonDblClick:
            pos = event.position().toPoint()
            col = header.logicalIndexAt(pos)
            if col >= 0:
                self._on_table_header_clicked(col)
            return True
        return super().eventFilter(obj, event)
            
    def _show_context_menu(self, pos):
        """Show right-click context menu."""
        menu = RoundMenu(parent=self)
        
        restore_action = Action(FIF.SYNC, "Restore")
        open_action = Action(FIF.FOLDER, "Open Location") 
        delete_action = Action(FIF.DELETE, "Delete")
        
        menu.addAction(restore_action)
        menu.addAction(open_action)
        menu.addAction(delete_action)
        
        menu.exec(self.backups_table.mapToGlobal(pos))
        
    def _restore_backup(self, backup_file):
        """Restore a backup file to the game's save directory.
        
        Args:
            backup_file: Path to the backup ZIP file to restore
        """
        if not self.current_profile:
            return
            
        plug = resolve_plugin_for_profile(self.current_profile, self)
        if not ensure_plugin_restore_inputs(self, self.current_profile, plug, self.config):
            return
        if not offer_plugin_restore_input_review(self, self.current_profile, plug, self.config):
            return
        if not confirm_restore(self, self.current_profile, plug, self.config, backup_file):
            return
        try:
            profile_dict = self.current_profile.as_operation_dict(plug)
            if plug is not None:
                profile_dict = run_plugin_hook(plug, "preprocess_restore", profile_dict)
                if not self.current_profile.plugin_id:
                    self.current_profile.save_path = profile_dict.get(
                        "save_path", self.current_profile.save_path
                    )
            run_restore(self.current_profile, self.config, backup_file, clear_before_restore(plug), plug)
            InfoBar.success(
                "Restore Complete",
                "Backup restored successfully",
                parent=toast_parent(self)
            )
        except PluginHookError as e:
            InfoBar.error("Plugin error", str(e), parent=toast_parent(self), duration=12000)
        except Exception as e:
            InfoBar.error("Restore Failed", str(e), parent=toast_parent(self))
                
    def _view_backup(self, backup_file):
        """Open file explorer with the selected backup highlighted."""
        try:
            backup_path = Path(backup_file)
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", str(backup_path.resolve())])
            else:
                open_path_in_explorer(backup_path.parent)
        except Exception as e:
            InfoBar.error("View Failed", str(e), parent=toast_parent(self))
            
    def _delete_backup(self, backup_file):
        """Delete backup file."""
        if confirm_action(self, "Delete Backup", f"Delete backup '{backup_file.name}'?"):
            try:
                backup_file.unlink()
                self._refresh_backups()
                InfoBar.success("Backup Deleted", "Backup file deleted", parent=toast_parent(self))
            except Exception as e:
                InfoBar.error("Delete Failed", str(e), parent=toast_parent(self))

    def set_developer_mode(self, enabled: bool) -> None:
        set_dev_widgets_visible(enabled, (self.refresh_btn,))

    def _dev_refresh(self) -> None:
        root = self.window()
        fn = getattr(root, "developer_refresh", None)
        if callable(fn):
            fn("backups")

