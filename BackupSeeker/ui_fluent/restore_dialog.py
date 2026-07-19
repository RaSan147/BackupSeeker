from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
	QAbstractItemView,
	QDialog,
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
	PrimaryPushButton,
	StrongBodyLabel,
	TableWidget,
	FluentIcon as FIF,
)

from ..core import (
	ConfigManager,
	GameProfile,
	clear_before_restore,
	read_archive_metadata,
	run_restore,
	summarize_archive_metadata,
)
from ..modern_widgets import RoundedCard
from ..ui_shared import confirm_restore, ensure_plugin_restore_inputs, offer_plugin_restore_input_review
from .helpers import (
	_install_read_only_table,
	apply_combo_ui_view,
	ui_view_mode_from_combo_text,
)
from ..fluent_window import resolve_plugin_for_profile, toast_parent
from ..plugin_runtime import PluginHookError, run_plugin_hook
from .styles import AdaptiveThemeStyles


class RestoreBackupDialog(QDialog):
    """Popup widget for restoring backups."""
    
    def __init__(self, profile: GameProfile, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.config = config
        self.selected_backup = None
        self._plug = resolve_plugin_for_profile(profile, self)
        self._disp = profile.resolved_name(self._plug)

        self._theme_styles = AdaptiveThemeStyles()
        self.setObjectName("restoreBackupDialog")
        self.setStyleSheet(self._theme_styles.restore_backup_dialog_stylesheet("restoreBackupDialog"))
        self.setWindowTitle(f"Restore — {self._disp}")
        self.setFixedSize(700, 500)
        self._setup_ui()
        self._load_backups()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        styles = self._theme_styles
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(StrongBodyLabel(f"Restore Backup: {self._disp}"))
        header_layout.addStretch()
        
        # View mode selector (List / Cards)
        self.view_toggle = ComboBox()
        self.view_toggle.addItem("List")
        self.view_toggle.addItem("Cards")
        self.view_toggle.setFixedWidth(110)
        self.view_toggle.currentTextChanged.connect(self._on_view_changed)
        header_layout.addWidget(self.view_toggle)
        apply_combo_ui_view(self.view_toggle, self.config.ui_view_restore_dialog)
        
        self.refresh_btn = PushButton(FIF.SYNC, "Refresh")
        self.refresh_btn.clicked.connect(self._load_backups)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Backups table
        self.backups_table = TableWidget()
        self.backups_table.setColumnCount(5)
        self.backups_table.setHorizontalHeaderLabels(["Type", "Date", "Size", "Archive", "Filename"])
        h = self.backups_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.backups_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backups_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backups_table.doubleClicked.connect(self._restore_selected)
        self.backups_table.setAlternatingRowColors(True)
        styles.apply_dialog_table_style(self.backups_table)
        _install_read_only_table(self.backups_table)
        
        # Backups list (card view)
        self.backups_card_list = QListWidget()
        self.backups_card_list.setViewMode(QListView.ViewMode.IconMode)
        self.backups_card_list.setIconSize(QSize(240, 135))
        self.backups_card_list.setGridSize(QSize(280, 200))
        self.backups_card_list.setSpacing(12)
        self.backups_card_list.setDragEnabled(False)
        self.backups_card_list.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.backups_card_list.setMovement(QListView.Movement.Static)
        self.backups_card_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backups_card_list.setFlow(QListView.Flow.LeftToRight)
        self.backups_card_list.setWrapping(True)
        self.backups_card_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.backups_card_list.setUniformItemSizes(True)
        self.backups_card_list.itemDoubleClicked.connect(self._on_card_double_clicked)
        
        layout.addWidget(self.backups_table)
        layout.addWidget(self.backups_card_list)
        
        # Info text
        info_label = CaptionLabel("🛡️ Safety backups are created automatically before each restore operation")
        info_label.setStyleSheet(
            f"CaptionLabel{{color: {styles.text_secondary()}; padding: 5px;}}"
        )
        layout.addWidget(info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.restore_btn = PrimaryPushButton(FIF.SYNC, "Restore")
        self.restore_btn.setFixedWidth(180)  # Wider button
        self.restore_btn.clicked.connect(self._restore_selected)
        self.restore_btn.setEnabled(False)
        
        self.cancel_btn = PushButton(FIF.CLOSE, "Cancel")
        self.cancel_btn.setFixedWidth(120)  # Wider button
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.restore_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Connect selection change
        self.backups_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.backups_card_list.itemSelectionChanged.connect(self._on_selection_changed)
        
    def _load_backups(self):
        """Load all backups for the profile."""
        self.backups_table.setRowCount(0)
        self.backups_card_list.clear()
        
        # Get regular backups
        backup_dir = self.config.backup_dir_for_profile(self.profile, self._plug)
        safety_dir = self.config.safety_backup_dir_for_profile(self.profile, self._plug)
        
        backups = []
        
        # Add regular backups
        if backup_dir.exists():
            for file in backup_dir.glob("*.zip"):
                backups.append((file, "Regular"))
                
        # Add safety backups
        if safety_dir.exists():
            for file in safety_dir.glob("*.zip"):
                backups.append((file, "Safety"))
                
        # Sort by modification time (newest first)
        backups.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)
        
        # Determine which view is active
        mode = self.view_toggle.currentText()
        is_cards = (mode or '').lower().startswith('c')
        
        for file, backup_type in backups:
            # Prepare common data
            type_icon = "🛡️ Safety" if backup_type == "Safety" else "💾 Regular"
            mtime = file.stat().st_mtime
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            size_bytes = file.stat().st_size
            if size_bytes < 1024 * 1024:
                size_str = f"{size_bytes/1024:.1f} KB"
            else:
                size_str = f"{size_bytes/1024/1024:.1f} MB"

            meta = read_archive_metadata(file)
            summ = summarize_archive_metadata(meta, zip_path=file)
            arch_line = summ.get("summary", "")
            arch_tip = summ.get("tooltip", "")
            
            if is_cards:
                # Add to card list
                item = QListWidgetItem()
                item.setSizeHint(QSize(280, 200))
                item.setData(Qt.ItemDataRole.UserRole, file)
                self.backups_card_list.addItem(item)
                
                backup_data = {
                    "type": type_icon,
                    "date": date_str,
                    "size": size_str,
                    "archive": arch_line,
                    "archive_tooltip": arch_tip,
                    "filename": file.name,
                    "file": file
                }
                widget = self._create_backup_card(backup_data)
                self.backups_card_list.setItemWidget(item, widget)
            else:
                # Add to table
                row = self.backups_table.rowCount()
                self.backups_table.insertRow(row)
                
                # Type with appropriate icon
                self.backups_table.setItem(row, 0, QTableWidgetItem(type_icon))
                
                # Date
                self.backups_table.setItem(row, 1, QTableWidgetItem(date_str))
                
                # Size
                self.backups_table.setItem(row, 2, QTableWidgetItem(size_str))

                arch_item = QTableWidgetItem(arch_line)
                arch_item.setToolTip(arch_tip)
                self.backups_table.setItem(row, 3, arch_item)
                
                # Filename
                item = QTableWidgetItem(file.name)
                item.setData(Qt.ItemDataRole.UserRole, file)  # Store file path
                item.setToolTip(arch_tip)
                self.backups_table.setItem(row, 4, item)
        
        # Toggle visibility
        self.backups_table.setVisible(not is_cards)
        self.backups_card_list.setVisible(is_cards)
    
    def _on_view_changed(self, text: str):
        """Switch between List and Cards view for backups."""
        self.config.ui_view_restore_dialog = ui_view_mode_from_combo_text(text)
        self.config.save_config()
        self._load_backups()
    
    def _on_card_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on card to restore."""
        self._restore_selected()
    
    def _create_backup_card(self, backup_data: dict) -> QWidget:
        """Create a card widget for a backup with clean typography."""
        styles = self._theme_styles
        card = RoundedCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(8)
        card.setObjectName("restoreDialogBackupCard")
        card.setStyleSheet(styles.info_panel_stylesheet("restoreDialogBackupCard", radius=10))

        # Type + icon (header)
        type_label = BodyLabel(backup_data.get("type", "Backup"))
        type_label.setStyleSheet(f"BodyLabel{{font-weight: bold; font-size: 14px; color:{styles.text_primary()};}}")
        card_layout.addWidget(type_label)
        
        # Date
        date_label = BodyLabel(backup_data.get("date", ""))
        date_label.setStyleSheet(f"BodyLabel{{font-size: 12px; color: {styles.text_secondary()};}}")
        card_layout.addWidget(date_label)
        
        # Size
        size_label = CaptionLabel(backup_data.get("size", ""))
        size_label.setStyleSheet(f"CaptionLabel{{color: {styles.text_muted()}; font-size: 11px;}}")
        card_layout.addWidget(size_label)

        arch = (backup_data.get("archive") or "").strip()
        if arch:
            arch_lbl = CaptionLabel(arch[:90] + ("…" if len(arch) > 90 else ""))
            arch_lbl.setToolTip(backup_data.get("archive_tooltip", "") or arch)
            arch_lbl.setStyleSheet(
                f"CaptionLabel{{color: {styles.text_secondary()}; font-size: 11px;}}"
            )
            arch_lbl.setWordWrap(True)
            card_layout.addWidget(arch_lbl)
        
        # Separator
        sep = QLabel()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {styles.separator()};")
        card_layout.addWidget(sep)
        
        # Filename (truncated but more readable)
        filename = backup_data.get("filename", "")
        if len(filename) > 35:
            filename = filename[:32] + "..."
        filename_label = CaptionLabel(filename)
        filename_label.setStyleSheet(f"CaptionLabel{{color: {styles.text_secondary()}; font-size: 11px; font-family: monospace;}}")
        filename_label.setWordWrap(True)
        card_layout.addWidget(filename_label)
        
        card_layout.addStretch()
        
        # Action button
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        restore_btn = PushButton("Restore")
        restore_btn.setFixedWidth(110)
        restore_btn.setFixedHeight(32)
        restore_btn.clicked.connect(lambda checked, f=backup_data.get("file"): self._restore_backup(f, backup_data.get("type", "")))
        button_layout.addWidget(restore_btn)
        button_layout.addStretch()
        
        card_layout.addLayout(button_layout)
        
        return card
        
            
    def _on_selection_changed(self):
        """Enable/disable restore button based on selection in either view."""
        mode = self.view_toggle.currentText()
        is_cards = (mode or '').lower().startswith('c')
        
        if is_cards:
            selected = len(self.backups_card_list.selectedItems()) > 0
        else:
            selected = self.backups_table.selectionModel().hasSelection()
        
        self.restore_btn.setEnabled(selected)
        
    def _restore_backup(self, backup_file, backup_type_str: str = ""):
        """Restore a specific backup file."""
        if not ensure_plugin_restore_inputs(self, self.profile, self._plug, self.config):
            return
        if not offer_plugin_restore_input_review(self, self.profile, self._plug, self.config):
            return
        if not confirm_restore(self, self.profile, self._plug, self.config, Path(backup_file)):
            return
        try:
            profile_dict = self.profile.as_operation_dict(self._plug)
            if self._plug is not None:
                profile_dict = run_plugin_hook(self._plug, "preprocess_restore", profile_dict)
                if not self.profile.plugin_id:
                    self.profile.save_path = profile_dict.get("save_path", self.profile.save_path)
            run_restore(self.profile, self.config, Path(backup_file), clear_before_restore(self._plug), self._plug)
            if self._plug is not None:
                run_plugin_hook(self._plug, "postprocess_restore", {"backup_path": str(backup_file)})
            InfoBar.success(
                "Restore Complete",
                "Backup restored successfully",
                parent=toast_parent(self)
            )
            self.accept()
        except PluginHookError as e:
            InfoBar.error("Plugin error", str(e), parent=toast_parent(self), duration=12000)
        except Exception as e:
            InfoBar.error("Restore Failed", str(e), parent=toast_parent(self))
        
    def _restore_selected(self):
        """Restore the selected backup (works for both table and card views)."""
        mode = self.view_toggle.currentText()
        is_cards = (mode or '').lower().startswith('c')
        
        if is_cards:
            # Get selected card
            selected_items = self.backups_card_list.selectedItems()
            if not selected_items:
                return
            backup_file = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if not backup_file:
                return
            
            # Determine type from the list
            # Since we don't store type directly, check file location
            safety_dir = self.config.get_safety_backup_dir(self._disp)
            is_safety = backup_file.parent == safety_dir
            backup_type = "Safety" if is_safety else "Regular"
        else:
            # Get selected table row
            selected_items = self.backups_table.selectedItems()
            if not selected_items:
                return
                
            row = selected_items[0].row()
            file_item = self.backups_table.item(row, 4)
            if not file_item:
                return
                
            backup_file = file_item.data(Qt.ItemDataRole.UserRole)
            backup_type = "Safety" if "Safety" in self.backups_table.item(row, 0).text() else "Regular"
        
        self._restore_backup(backup_file, backup_type)
