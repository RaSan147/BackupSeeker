"""Modern Fluent UI for BackupSeeker - NO CIRCULAR IMPORTS!"""

from __future__ import annotations

import sys
import subprocess
import os
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import html

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QEvent
from PyQt6.QtGui import QGuiApplication, QBrush, QColor, QPixmap, QPalette
from PyQt6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
                             QListWidgetItem, QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QFileDialog, QSizePolicy, QDialog, QListView, QListWidget,
                             QScrollArea)

from qframelesswindow import AcrylicWindow
from qfluentwidgets import (
    FluentTranslator, Theme,
    MessageBox, InfoBar, PushButton,
    PrimaryPushButton, LineEdit, PlainTextEdit, TableWidget,
    ComboBox, StrongBodyLabel, BodyLabel, CaptionLabel,
    RoundMenu, Action, FluentIcon as FIF, setTheme
)

from PyQt6.QtWidgets import QMessageBox

from .core import ConfigManager, GameProfile, run_backup, run_restore
from .plugin_manager import PluginManager
from .modern_widgets import ModernTitleBar, RoundedCard, ModernNavigationInterface, ModernGameEditor
from .ui_helpers import is_app_dark
from .ui_shared import confirm_action, open_path_in_explorer

# Disable extensive plugin logging
logging.getLogger('BackupSeeker.plugin_manager').setLevel(logging.WARNING)


class ModernDashboardInterface(QWidget):
    """FIXED Dashboard - Actually Works"""
    
    backup_requested = pyqtSignal()
    restore_requested = pyqtSignal()
    profiles_changed = pyqtSignal()
    
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_profile = None
        
        self._setup_ui()
        self._load_profiles()
        
    def _setup_ui(self):
        """Setup functional dashboard UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        header_label = StrongBodyLabel("Dashboard")
        header_label.setStyleSheet("StrongBodyLabel{font-size: 24px; font-weight: bold;}")
        layout.addWidget(header_label)
        
        # Main content
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # Left column - Profiles
        left_column = QVBoxLayout()
        left_column.setSpacing(15)
        
        profiles_card = RoundedCard()
        # Prefer transparent card backgrounds so the window acrylic
        # effect (if available) can show through instead of a solid
        # color like #2d2d2d. Individual cards can still override this
        # if a stronger tint is desired.
        profiles_card.setStyleSheet("RoundedCard{background: transparent;}")
        # Let the profiles card expand to use available left-side width
        profiles_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        profiles_layout = QVBoxLayout(profiles_card)
        profiles_layout.setContentsMargins(20, 15, 20, 15)
        
        profiles_header = QHBoxLayout()
        profiles_header.addWidget(StrongBodyLabel("Game Profiles"))
        profiles_header.addStretch()

        # Search bar for profiles (merged management)
        self.search_edit = LineEdit()
        self.search_edit.setPlaceholderText("Search profiles...")
        self.search_edit.textChanged.connect(self._on_profiles_search)
        self.search_edit.setFixedWidth(220)
        profiles_header.addWidget(self.search_edit)

        # View mode selector (List / Cards)
        self.view_toggle = ComboBox()
        self.view_toggle.addItem("List")
        self.view_toggle.addItem("Cards")
        self.view_toggle.setFixedWidth(110)
        self.view_toggle.currentTextChanged.connect(self._on_profiles_view_changed)
        profiles_header.addWidget(self.view_toggle)

        self.add_btn = PushButton(FIF.ADD, "Add Game")
        self.add_btn.clicked.connect(self._add_profile)
        profiles_header.addWidget(self.add_btn)
        
        profiles_layout.addLayout(profiles_header)
        
        # Use QListWidget so we can present both list and icon/card modes
        self.profiles_list = QListWidget()
        # Let the list expand to fill the left column; it's scrollable when needed
        self.profiles_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.profiles_list.itemClicked.connect(self._on_profile_selected)
        self.profiles_list.setMinimumHeight(300)
        # Ensure the list widget does not draw an opaque background so
        # window-level acrylic or the parent card's translucency can show
        # through. Apply to the viewport too (the area that is actually
        # painted by the scroll area).

        self.profiles_list.setStyleSheet(
            "QListWidget{background: transparent; border:0;} QListWidget::item{background: transparent;}"
        )
        self.profiles_list.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        vp = self.profiles_list.viewport()
        if vp is not None:
            vp.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            vp.setStyleSheet("background: transparent;")

        # Prevent list items/cards from being draggable or moved by the view.

        self.profiles_list.setDragEnabled(False)
        self.profiles_list.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.profiles_list.setMovement(QListView.Movement.Static)
        self.profiles_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # Default sizes for card mode
        self._card_image_size = QSize(160, 90)
        self._card_grid_size = QSize(200, 140)
        self.profiles_list.setIconSize(self._card_image_size)
        self.profiles_list.setSpacing(8)
        # Also provide a compact table view for the Dashboard (Name + Last Backup + Actions)
        self.profiles_table = TableWidget()
        self.profiles_table.setColumnCount(3)
        self.profiles_table.setHorizontalHeaderLabels(["Name", "Last Backup", "Actions"])
        pheader = self.profiles_table.horizontalHeader()
        pheader.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        pheader.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        pheader.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.profiles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.profiles_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Keep table selection changes in sync with dashboard controls
        self.profiles_table.itemSelectionChanged.connect(self._on_profile_table_selected)

        # Add both views; visibility toggled in _load_profiles
        profiles_layout.addWidget(self.profiles_table)
        profiles_layout.addWidget(self.profiles_list)
        
        left_column.addWidget(profiles_card)
        
        # Right column - Profile info
        right_column = QVBoxLayout()
        right_column.setSpacing(15)
        
        # Profile info card
        self.info_card = RoundedCard()
        # Allow the info card to size vertically so its labels can wrap
        # while keeping the overall layout stable via the right container's
        # maximum width. Avoid a fixed maximum height which caused content
        # to be clipped and invisible.
        self.info_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.info_card.setMaximumWidth(900)
        # Build a scrollable info area so long details can scroll instead
        # of forcing large layout shifts or being clipped.
        info_card_layout = QVBoxLayout(self.info_card)
        info_card_layout.setContentsMargins(20, 15, 20, 15)

        # Header area (fixed): icon + title
        self.profile_header = QHBoxLayout()
        self.profile_icon = QLabel("🎮")
        self.profile_icon.setStyleSheet("QLabel{font-size: 24px;}")
        self.profile_name = StrongBodyLabel("Select a Game Profile")
        self.profile_name.setStyleSheet("StrongBodyLabel{font-size: 18px;}")
        self.profile_name.setWordWrap(True)

        self.profile_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.profile_name.setMaximumHeight(64)

        self.profile_header.addWidget(self.profile_icon)
        self.profile_header.addWidget(self.profile_name)
        self.profile_header.addStretch()
        info_card_layout.addLayout(self.profile_header)

        # Cover image: shown on large windows, hidden on small screens
        self.cover_label = QLabel()
        self.cover_label.setScaledContents(True)
        self.cover_label.setFixedSize(240, 135)
        self.cover_label.setVisible(False)
        info_card_layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignHCenter)

        # DETAILS: make only this part scrollable so long paths/details don't shift the whole card
        self.details_container = QWidget()
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(0)
        # keep container transparent so card background shows through
        self.details_container.setStyleSheet("background: transparent; border:0;")

        # Single text block for details to keep consistent line spacing
        # and predictable wrapping. Use QLabel (plain text) so the block
        # behaves as a stable text element unaffected by window resizing
        # and does not act as an editor.
        self.details_text = QLabel()
        # Use rich text so we can bold labels and present the path in monospace
        self.details_text.setTextFormat(Qt.TextFormat.RichText)
        self.details_text.setWordWrap(True)
        self.details_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        # Keep background transparent and make text color follow the active
        # theme by using the palette's window text color. Ensure no opaque
        # background is drawn by the label itself.
        self.details_text.setStyleSheet("QLabel{background:transparent; border:0; padding:0; color: palette(windowText);}")
        # Allow the user to select/copy the path
        self.details_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Initial (empty) rich text
        # Use explicit hex color from the widget palette because Qt's
        # rich-text 'color:inherit' is not consistently supported across
        # platforms/Qt versions. This ensures the details text follows
        # the active theme (light/dark).
        try:
            default_color = self.palette().color(QPalette.ColorRole.WindowText).name()
        except Exception:
            default_color = "#000000"
        self.details_text.setText(
            f"<div style='font-family:Segoe UI, Roboto, Arial; font-size:16px; color:{default_color};'>"
            "<b>Save Path:</b> <span style='font-family:monospace; white-space:pre-wrap;'>Not selected</span><br><br>"
            "<b>Storage:</b> Not set<br><br>"
            "<b>Status:</b> Waiting</div>"
        )

        details_layout.addWidget(self.details_text)

        self.details_scroll = QScrollArea()
        # Only allow vertical scrolling when content overflows; disable
        # horizontal scrolling so long text wraps instead of creating a
        # horizontal scrollbar.
        self.details_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)


        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setWidget(self.details_container)

        # Make scroll area background transparent so it doesn't render a static box
        self.details_scroll.setStyleSheet("QScrollArea{background: transparent; border:0;} QScrollArea QWidget{background:transparent}")
        vp = self.details_scroll.viewport()
        if vp is not None:
            vp.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            vp.setStyleSheet("background: transparent;")


        # Ensure the label wraps text and prefers to expand horizontally
        # within the available width; combined with the disabled
        # horizontal scrollbar this prevents sideways scrolling and keeps
        # long paths readable by wrapping and using word-break rules.
        self.details_text.setWordWrap(True)
        self.details_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # keep a modest height but allow scroll for long content
        self.details_scroll.setFixedHeight(160)
        info_card_layout.addWidget(self.details_scroll)


        # Action buttons - fixed area under the scrollable details
        action_layout = QHBoxLayout()
        self.backup_btn = PrimaryPushButton(FIF.SAVE, "Backup Now")
        self.backup_btn.setFixedHeight(40)
        self.backup_btn.setFixedWidth(150)
        self.backup_btn.clicked.connect(self.backup_requested.emit)
        self.backup_btn.setEnabled(False)

        self.restore_btn = PushButton(FIF.SYNC, "Restore")
        self.restore_btn.setFixedHeight(40)
        self.restore_btn.setFixedWidth(120)
        self.restore_btn.clicked.connect(self.restore_requested.emit)
        self.restore_btn.setEnabled(False)

        action_layout.addWidget(self.backup_btn)
        action_layout.addStretch()
        action_layout.addWidget(self.restore_btn)
        info_card_layout.addLayout(action_layout)
        
        # Activity log (create before adding to layouts to avoid scope issues)
        log_card = RoundedCard()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 15, 20, 15)

        log_layout.addWidget(StrongBodyLabel("Activity Log"))
        self.log_view = PlainTextEdit()
        self.log_view.setReadOnly(True)
        # Constrain the log height so it cannot expand to fill the window.
        # Use a fixed height plus size policy to ensure consistent layout.
        self.log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.log_view.setFixedHeight(150)
        # Let the containing card be fixed-height as well to avoid cascaded expansion.
        log_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        log_card.setMaximumHeight(200)
        log_layout.addWidget(self.log_view)

        # Right column constrained to ~20% width of typical window
        right_container = QWidget()
        right_container.setLayout(QVBoxLayout())
        right_container.layout().setContentsMargins(0, 0, 0, 0)
        right_container.layout().setSpacing(12)
        # limit width to approximate 20% of a 1400px window (~280-320)
        right_container.setMinimumWidth(380)
        
        right_container.setMaximumWidth(450)

        right_container.layout().addWidget(self.info_card)
        right_container.layout().addWidget(log_card)
        right_column.addWidget(right_container)
        
        # Combine columns with stretch factors to stabilize sizing (right panel ~20%)
        content_layout.addLayout(left_column, 4)
        content_layout.addLayout(right_column, 1)
        layout.addLayout(content_layout)
        
    def _load_profiles(self):
        """Load existing profiles."""
        # Reset selection and visible controls to avoid stale state
        self.current_profile = None
        self.backup_btn.setEnabled(False)
        self.restore_btn.setEnabled(False)


        # Clear both list and table views before repopulating to avoid duplicates
        self.profiles_list.clear()
        
        self.profiles_table.setRowCount(0)

        # Ensure view mode settings are applied
        mode = (getattr(self, 'view_toggle', None).currentText() if getattr(self, 'view_toggle', None) else 'List')
        is_cards = (mode or '').lower().startswith('c')

        if is_cards:
            self.profiles_list.setViewMode(QListView.ViewMode.IconMode)
            self.profiles_list.setIconSize(self._card_image_size)
            self.profiles_list.setGridSize(self._card_grid_size)
        else:
            self.profiles_list.setViewMode(QListView.ViewMode.ListMode)
            # smaller icon for list
            self.profiles_list.setIconSize(QSize(24, 24))
            self.profiles_list.setGridSize(QSize(0, 0))


        for profile_id, profile in self.config.games.items():
            if is_cards:
                item = QListWidgetItem()
                item.setSizeHint(self._card_grid_size)
                item.setData(Qt.ItemDataRole.UserRole, profile_id)
                self.profiles_list.addItem(item)
                widget = self._create_profile_card(profile)
                self.profiles_list.setItemWidget(item, widget)
            else:
                # Populate the compact dashboard table: Name, Last Backup, Actions
                row = self.profiles_table.rowCount()
                self.profiles_table.insertRow(row)
                name_item = QTableWidgetItem(profile.name)
                # store profile id on the row so selection can enable actions
                name_item.setData(Qt.ItemDataRole.UserRole, profile_id)
                self.profiles_table.setItem(row, 0, name_item)

                # compute last backup timestamp for this profile
                last_dt = "Never"
                try:
                    bdir = self.config.get_game_backup_dir(profile.name)
                    files = list(bdir.glob("*.zip"))
                    if files:
                        latest = max(files, key=lambda f: f.stat().st_mtime)
                        last_dt = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    last_dt = "Unknown"
                self.profiles_table.setItem(row, 1, QTableWidgetItem(last_dt))

                # Actions widget (Edit / Open File)
                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(5, 5, 5, 5)
                edit_btn = PushButton("Edit")
                edit_btn.setFixedWidth(80)
                # Use dashboard helper to perform edit/open behavior so the
                # same logic is shared with other UI pages (Profiles page).
                edit_btn.clicked.connect(lambda checked, pid=profile_id: self.open_profile_editor_or_source(pid))

                delete_btn = PushButton("Delete")
                delete_btn.setFixedWidth(80)
                delete_btn.clicked.connect(lambda checked, pid=profile_id: self._delete_profile(pid))
                action_layout.addWidget(edit_btn)
                action_layout.addWidget(delete_btn)
                action_layout.addStretch()
                self.profiles_table.setCellWidget(row, 2, action_widget)
            
        # Show table in list mode, list widget in cards mode
        self.profiles_table.setVisible(not is_cards)
        self.profiles_list.setVisible(is_cards)

        if self.config.games:
            self.log("Loaded existing profiles")
        else:
            self.log("No profiles found. Add your first game!")

    def _find_placeholder(self) -> Path | None:
        """Search for a placeholder image in likely app locations.

        Looks in `app_dir`, `app_dir.parent`, and common `Data` directories
        so bundled placeholder assets are found whether the package is
        installed as a module or run from the repository root.
        Returns the first matching Path or None if not found.
        """
        try:
            appdir = Path(self.config.app_dir)
            candidates = [
                appdir,
                appdir.parent,
                appdir / "Data",
                appdir.parent / "Data",
            ]
            seen = set()
            for base in candidates:
                if not base or not base.exists():
                    continue
                # avoid scanning the same dir twice
                real = str(base.resolve())
                if real in seen:
                    continue
                seen.add(real)
                for p in base.rglob('*'):
                    if p.is_file() and p.name.lower().startswith('placeholder'):
                        return p
        except Exception:
            pass
        return None

    def _set_label_pixmap_fit(self, label: QLabel, pix: QPixmap, max_size: QSize):
        """Place a QPixmap into `label` without stretching.

        Behavior:
        - Keep label background transparent.
        - Do not upscale small images (only shrink if larger than max_size).
        - Preserve aspect ratio (no cropping).
        - Center the pixmap inside the label.
        """
        # Ensure transparent background so blank area stays blank
        label.setStyleSheet("QLabel{background: transparent; border:0;}")
        label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        if pix is None or pix.isNull():
            label.clear()
            return

        target_w = max_size.width()
        target_h = max_size.height()

        pw = pix.width()
        ph = pix.height()

        # If image is larger than allowed, shrink it while keeping aspect
        if pw > target_w or ph > target_h:
            scaled = pix.scaled(max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        else:
            # Do not upscale — use original pixmap
            scaled = pix

        # Ensure the label does not auto-stretch the pixmap
        label.setScaledContents(False)

        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setPixmap(scaled)

    def _on_profiles_view_changed(self, text: str):
        """Switch between List and Cards view for profiles."""
        self._load_profiles()

    def _on_profile_table_selected(self):
        """Handle selection coming from the compact dashboard table."""
        sel = self.profiles_table.selectionModel().selectedRows()
        if not sel:
            self.current_profile = None
            self.backup_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
            return

        row = sel[0].row()
        item = self.profiles_table.item(row, 0)
        if not item:
            return
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        if not profile_id:
            return

        # Reuse the same selection handling as list selection
        self.current_profile = self.config.games.get(profile_id)
        if self.current_profile:
            self._display_profile(self.current_profile)

    def _on_profiles_search(self, text: str):
        """Filter profiles list/cards and the compact dashboard table by search text.

        This handler is connected to the search LineEdit on the Dashboard and
        should filter both the icon/list view (cards) and the compact table
        view so users see consistent results regardless of view mode.
        """
        t = (text or "").strip().lower()

        # Filter the QListWidget items (cards / list mode)
        for i in range(self.profiles_list.count()):
            item = self.profiles_list.item(i)
            if not item:
                continue
            profile_id = item.data(Qt.ItemDataRole.UserRole)
            name = None
            if profile_id:
                profile = self.config.games.get(profile_id)
                if profile:
                    name = profile.name
            if not name:
                name = item.text() or ""
            visible = (not t) or (t in name.lower())
            item.setHidden(not visible)

        # Also filter the compact table view when visible
        # Use setRowHidden to hide entire rows that don't match
        try:
            for row in range(self.profiles_table.rowCount()):
                name_item = self.profiles_table.item(row, 0)
                # If there is no name item, show the row conservatively
                if not name_item:
                    self.profiles_table.setRowHidden(row, False)
                    continue
                # Try to use stored profile id first (from UserRole)
                profile_id = name_item.data(Qt.ItemDataRole.UserRole)
                row_name = None
                if profile_id and profile_id in self.config.games:
                    row_name = self.config.games[profile_id].name
                if not row_name:
                    row_name = name_item.text() or ""
                match = (not t) or (t in row_name.lower())
                self.profiles_table.setRowHidden(row, not match)
        except Exception:
            # Be fault-tolerant: ignore filtering errors to avoid breaking the UI
            pass
            
    def _add_profile(self):
        """Add new game profile."""
        editor = ModernGameEditor(parent=self)
        if editor.exec():
            self.config.games[editor.profile.id] = editor.profile
            self.config.save_config()
            self._load_profiles()
            self.log(f"Added: {editor.profile.name}")
            # Show a toast anchored to the main window so its placement
            # matches other app notifications.
            try:
                InfoBar.success(
                    "Profile Added",
                    f"Added profile: {editor.profile.name}",
                    parent=(getattr(self.window(), 'content_widget', self.window()) or self)
                )
            except Exception:
                pass
            try:
                self.profiles_changed.emit()
            except Exception:
                pass
            
    def _edit_profile(self, profile_id):
        """Edit existing profile (reused from Profiles management)."""
        profile = self.config.games.get(profile_id)
        if profile:
            editor = ModernGameEditor(profile, self)
            if editor.exec():
                self.config.save_config()
                self._load_profiles()
                self.profiles_changed.emit()

    def open_profile_editor_or_source(self, pid):
        """Open profile for editing or open the source (plugin/python/json) in Explorer.

        This extracts the inline closure logic used on the dashboard so
        other UI pages (Profiles management) can reuse the same behavior.
        """
        prof = self.config.games.get(pid)
        if not prof:
            return

        # If profile is plugin-backed, attempt to open its source (module)
        if getattr(prof, 'plugin_id', None):
            pm = getattr(self.window(), 'plugin_manager', None)
            plugin = None
            if pm:
                # plugin manager may provide helper to locate plugin for profile
                plugin = pm.get_plugin_for_profile(prof.plugin_id)
                if plugin is None:
                    plugin = pm.available_plugins.get(prof.plugin_id)
            if plugin is not None:
                import importlib.util as _ilutil
                mod_name = plugin.__class__.__module__
                spec = _ilutil.find_spec(mod_name)
                origin = getattr(spec, 'origin', None) if spec is not None else None
                if origin:
                    path = Path(origin)
                    # If it's a python file, open Explorer selecting it on Windows
                    if path.name.lower().endswith('.py'):
                        if sys.platform.startswith('win'):
                            subprocess.Popen(['explorer', '/select,', str(path)])
                            return
                        else:
                            os.system(f"xdg-open '{path}'")
                            return
            # Fallback: try to open plugins/games.jsonc if it mentions this plugin id
            pjson = Path(self.config.app_dir) / 'plugins' / 'games.jsonc'
            if pjson.exists():
                text = pjson.read_text(encoding='utf-8')
                if prof.plugin_id in text:
                    if sys.platform.startswith('win'):
                        subprocess.Popen(['explorer', '/select,', str(pjson)])
                        return
                    else:
                        os.system(f"xdg-open '{pjson}'")
                        return
            # final fallback: open config file for manual editing
            cfg = Path(self.config.config_path)
            if sys.platform.startswith('win'):
                subprocess.Popen(['explorer', '/select,', str(cfg)])
                return
            else:
                os.system(f"xd-open '{cfg}'")

        # Non-plugin-backed profiles: open in editor
        editor = ModernGameEditor(self.config.games.get(pid), self)
        if editor.exec():
            self.config.save_config()
            self._load_profiles()
            self.profiles_changed.emit()

    def _delete_profile(self, profile_id):
        """Delete a profile from config."""
        profile = self.config.games.get(profile_id)
        if profile:
            if confirm_action(self, "Delete Profile", f"Are you sure you want to delete '{profile.name}'?"):
                del self.config.games[profile_id]
                self.config.save_config()
                self._load_profiles()
                self.profiles_changed.emit()
    def _on_profile_selected(self, item):
        """Handle profile selection."""
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        self.current_profile = self.config.games.get(profile_id)
        
        if self.current_profile:
            self._display_profile(self.current_profile)

    def _display_profile(self, profile: GameProfile):
        """Update the info card with the given profile and handle cover image visibility."""
        self.profile_name.setText(profile.name)
        # Use rich text with bold field labels and a monospace, wrap-capable
        # save path so very long paths wrap nicely in the UI.
        save_path_html = html.escape(str(profile.save_path)) if getattr(profile, 'save_path', None) else "Not selected"
        storage_html = html.escape(str(self.config.backup_root))
        try:
            color_hex = self.palette().color(QPalette.ColorRole.WindowText).name()
        except Exception:
            color_hex = "#000000"

        html_text = (
            f"<div style='font-family:Segoe UI, Roboto, Arial; font-size:13px; color:{color_hex};'>"
            f"<b>Save Path:</b> <span style='font-family:monospace; white-space:pre-wrap; word-break:break-all;'>{save_path_html}</span><br><br>"
            f"<b>Storage:</b> <span style='white-space:pre-wrap;'>{storage_html}</span><br><br>"
            "<b>Status:</b> Ready"
            "</div>"
        )
        self.details_text.setText(html_text)

        self.backup_btn.setEnabled(True)
        self.restore_btn.setEnabled(True)

        # Determine image source: prefer plugin manager saved icon, then profile.icon
        img_path = None
        pm = getattr(self.window(), 'plugin_manager', None)
        if pm and getattr(profile, 'plugin_id', None):
            plugin = pm.available_plugins.get(profile.plugin_id)
            if plugin and getattr(plugin, '_saved_icon', None):
                img_path = plugin._saved_icon

        if not img_path and getattr(profile, 'icon', None):
            img_path = profile.icon

        pix = QPixmap(str(img_path)) if img_path else QPixmap()

        # If no image available, attempt to find a placeholder file in the
        # app directory (case-insensitive), e.g. Data/Placeholder.png or data/placeholder.png
        if pix.isNull():
            ph = self._find_placeholder()
            if ph is not None:
                pix = QPixmap(str(ph))

        # Only show cover image on sufficiently large windows to avoid
        # cluttering small layouts. 750px is the threshold requested.
        width = self.window().width() if getattr(self, 'window', None) and self.window() is not None else self.width()
        show_img = (pix is not None and not pix.isNull() and (width >= 750))
        if show_img:
            self.cover_label.setVisible(True)
            # Use helper: do not stretch, only shrink to fit, keep blank bg
            self._set_label_pixmap_fit(self.cover_label, pix, self.cover_label.size())
        else:
            # final fallback: clear and hide
            self.cover_label.clear()
            self.cover_label.setVisible(False)

        self.log(f"Selected: {profile.name}")


    def log(self, message: str):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{timestamp}] {message}")

    def _create_profile_card(self, profile: GameProfile) -> QWidget:
        """Create a compact card widget for a game profile.

        Card contains a poster image (or placeholder) and the game name.
        """
        card = RoundedCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(8)

        img_label = QLabel()
        img_label.setFixedSize(self._card_image_size)

        # Determine image source: prefer plugin manager saved icon, then profile.icon
        img_path = None
        pm = getattr(self.window(), 'plugin_manager', None)
        if pm and profile.plugin_id:
            plugin = pm.available_plugins.get(profile.plugin_id)
            if plugin and getattr(plugin, '_saved_icon', None):
                img_path = plugin._saved_icon

        if not img_path and profile.icon:
            img_path = profile.icon

        pix = QPixmap(str(img_path)) if img_path else QPixmap()

        if pix.isNull():
            # Try to find a placeholder image in likely app locations
            ph = self._find_placeholder()
            if ph is not None:
                pix = QPixmap(str(ph))

        if pix.isNull():
            # final fallback: transparent pixmap so background remains blank
            pix = QPixmap(self._card_image_size)
            pix.fill(Qt.GlobalColor.transparent)

        # Place pixmap into label without stretching (only shrink to fit)
        self._set_label_pixmap_fit(img_label, pix, self._card_image_size)

        title = StrongBodyLabel(profile.name)
        # Theme-aware text color: compute color from the app palette so
        # the label is readable in light and dark themes.
        # Get App theme mode
        # Use centralized detection helper for consistency and robustness
        dark = is_app_dark()
        title_color = QColor(240, 240, 240) if dark else QColor(30, 30, 30)
        title.setStyleSheet(f"StrongBodyLabel{{color: {title_color.name()}; font-size:12px;}}")

        # Allow wrapping and centering for long titles
        title.setWordWrap(True)


        title.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        # Constrain title width to card grid so layout can elide/wrap predictably
        title.setMaximumWidth(self._card_grid_size.width() - 12)

        card_layout.addWidget(img_label, 0, Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)

        # Visual styling for the card
        # Slightly tint the card background to differentiate it from list
        card.setStyleSheet("background: transparent;")

        return card



class ModernProfilesInterface(QWidget):
    """Profiles Management Page - ACTUALLY WORKS"""
    profiles_changed = pyqtSignal()
    
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        
        self._setup_ui()
        self._load_profiles()
        
    def _setup_ui(self):
        if self.layout() is None:
            layout = QVBoxLayout(self)
        else:
            layout = self.layout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        header.addWidget(StrongBodyLabel("Game Profiles Management"))
        header.addStretch()
        # Search box for quick filtering of the profiles table
        self.profile_search = LineEdit()
        self.profile_search.setPlaceholderText("Search profiles...")
        self.profile_search.setFixedWidth(220)
        self.profile_search.textChanged.connect(self._on_profiles_table_search)
        header.addWidget(self.profile_search)
        
        self.add_btn = PrimaryPushButton(FIF.ADD, "Add Profile")
        self.add_btn.clicked.connect(self._add_profile)
        header.addWidget(self.add_btn)
        
        layout.addLayout(header)
        
        # Profiles table
        self.profiles_table = TableWidget()
        # Add a Last Backup column (Name, Last Backup, Save Path, Compression, Clear on Restore, Actions)
        self.profiles_table.setColumnCount(6)
        self.profiles_table.setHorizontalHeaderLabels(["Name", "Last Backup", "Save Path", "Compression", "Clear on Restore", "Actions"])
        pheader = self.profiles_table.horizontalHeader()
        pheader.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        pheader.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        pheader.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        pheader.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        pheader.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        pheader.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.profiles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.profiles_table)
        
    def _load_profiles(self):
        """Load profiles into table."""
        self.profiles_table.setRowCount(0)
        
        for profile_id, profile in self.config.games.items():
            row = self.profiles_table.rowCount()
            self.profiles_table.insertRow(row)
            
            # Name
            self.profiles_table.setItem(row, 0, QTableWidgetItem(profile.name))
            # Last Backup (compute)
            try:
                bdir = self.config.get_game_backup_dir(profile.name)
                files = list(bdir.glob("*.zip"))
                if files:
                    latest = max(files, key=lambda f: f.stat().st_mtime)
                    last_dt = datetime.fromtimestamp(latest.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                else:
                    last_dt = "Never"
            except Exception:
                last_dt = "Unknown"
            self.profiles_table.setItem(row, 1, QTableWidgetItem(last_dt))
            # Path
            self.profiles_table.setItem(row, 2, QTableWidgetItem(profile.save_path))
            # Compression
            self.profiles_table.setItem(row, 3, QTableWidgetItem("Yes" if profile.use_compression else "No"))
            # Clear on restore
            self.profiles_table.setItem(row, 4, QTableWidgetItem("Yes" if profile.clear_folder_on_restore else "No"))
            
            # Actions
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 5, 5, 5)
            
            edit_btn = PushButton("Edit")
            edit_btn.setFixedWidth(80)
            edit_btn.clicked.connect(lambda checked, pid=profile_id: self._edit_profile(pid))
            
            delete_btn = PushButton("Delete")
            delete_btn.setFixedWidth(80)
            delete_btn.clicked.connect(lambda checked, pid=profile_id: self._delete_profile(pid))
            
            action_layout.addWidget(edit_btn)
            action_layout.addWidget(delete_btn)
            action_layout.addStretch()
            
            self.profiles_table.setCellWidget(row, 5, action_widget)
            
    def _add_profile(self):
        """Add new profile."""
        editor = ModernGameEditor(parent=self)
        if editor.exec():
            self.config.games[editor.profile.id] = editor.profile
            self.config.save_config()
            self._load_profiles()
            # Show a toast anchored to the app content area so it appears below titlebar
            try:
                InfoBar.success(
                    "Profile Added",
                    f"Added profile: {editor.profile.name}",
                    parent=(getattr(self.window(), 'content_widget', self.window()) or self)
                )
            except Exception:
                pass
            try:
                self.profiles_changed.emit()
            except Exception:
                pass
            
    def _on_profiles_table_search(self, text: str):
        """Filter rows in the Profiles Management table by name (case-insensitive)."""
        t = (text or "").strip().lower()
        try:
            for row in range(self.profiles_table.rowCount()):
                name_item = self.profiles_table.item(row, 0)
                if not name_item:
                    self.profiles_table.setRowHidden(row, False)
                    continue
                name = (name_item.text() or "")
                match = (not t) or (t in name.lower())
                self.profiles_table.setRowHidden(row, not match)
        except Exception:
            pass

    def _edit_profile(self, profile_id):
        """Edit existing profile."""
        profile = self.config.games.get(profile_id)
        if not profile:
            return

        # Prefer to reuse dashboard logic which will open the editor or
        # open the plugin/json/python source in Explorer when appropriate.
        win = self.window()
        dashboard = win.dashboard
        if dashboard:
            dashboard.open_profile_editor_or_source(profile_id)
            return


        # Fallback: open using in-app editor
        editor = ModernGameEditor(profile, self)
        if editor.exec():
            self.config.save_config()
            self._load_profiles()
            self.profiles_changed.emit()

                
    def _delete_profile(self, profile_id):
        """Delete profile."""
        profile = self.config.games.get(profile_id)
        if profile:
            if confirm_action(self, "Delete Profile", f"Are you sure you want to delete '{profile.name}'?"):
                del self.config.games[profile_id]
                self.config.save_config()
                self._load_profiles()
                try:
                    self.profiles_changed.emit()
                except Exception:
                    pass


class ModernBackupsInterface(QWidget):
    """Backups Management Page - SHOWS ACTUAL BACKUPS"""
    
    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.current_profile = None
        
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
        
        self.refresh_btn = PushButton(FIF.SYNC, "Refresh")
        self.refresh_btn.clicked.connect(self._refresh_backups)
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
        self.backups_table.setColumnCount(5)
        self.backups_table.setHorizontalHeaderLabels(["Type", "Date", "Size", "Filename", "Actions"])
        header = self.backups_table.horizontalHeader()
        # Keep a reference to the header and enable clickable sections so
        # the sort handlers and event filter can work reliably.
        self._table_header = header
        header.setSectionsClickable(True)
        header.sectionPressed.connect(self._on_table_header_clicked)
        header.installEventFilter(self)
        # Mark header initialized so _refresh_backups doesn't attempt to
        # rewire handlers again.
        self._header_initialized = True
        # Make date and size compact, filename stretch, actions sized to contents
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.backups_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backups_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.backups_table.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.backups_table)
        
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
            self.profile_combo.addItem(profile.name)
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
            if p.name == text:
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
        backup_dir = self.config.get_game_backup_dir(self.current_profile.name)
        safety_dir = self.config.get_safety_backup_dir(self.current_profile.name)

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

        # Prepare display fields
        for r in self._backup_rows:
            bsize = r["bytes"]
            if bsize < 1024 * 1024:
                r["size_display"] = f"{bsize/1024:.1f} KB"
            else:
                r["size_display"] = f"{bsize/1024/1024:.1f} MB"
            r["date_display"] = datetime.fromtimestamp(r["timestamp"]).strftime("%Y-%m-%d %H:%M")

        # Sort and render
        self._ensure_sort_state()
        self._sort_backup_rows()

        # Initialize header handlers once
        if not hasattr(self, "_header_initialized"):
            self._header_initialized = True
            header = getattr(self, "_table_header", None)
            if header is not None:
                header.setSectionsClickable(True)
                header.sectionPressed.connect(self._on_table_header_clicked)
                header.installEventFilter(self)

    def _ensure_sort_state(self):
        if not hasattr(self, "_type_sort_mode"):
            self._type_sort_mode = "none"
        if not hasattr(self, "_date_sort_mode"):
            self._date_sort_mode = "desc"

    def _sort_backup_rows(self):
        if not hasattr(self, "_backup_rows"):
            return
        self._ensure_sort_state()

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
        self.backups_table.setRowCount(0)
        for r in getattr(self, "_backup_rows", []):
            row = self.backups_table.rowCount()
            self.backups_table.insertRow(row)
            self.backups_table.setItem(row, 0, QTableWidgetItem(r.get("type", "")))
            self.backups_table.setItem(row, 1, QTableWidgetItem(r.get("date_display", "")))
            self.backups_table.setItem(row, 2, QTableWidgetItem(r.get("size_display", "")))
            item = QTableWidgetItem(r.get("filename", ""))
            item.setData(Qt.ItemDataRole.UserRole, r.get("path_obj"))
            self.backups_table.setItem(row, 3, item)

            # Actions widget
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(5, 5, 5, 5)
            restore_btn = PushButton("Restore")
            restore_btn.setFixedWidth(100)
            restore_btn.clicked.connect(lambda checked, p=r.get("path_obj"): self._restore_backup(p))
            action_layout.addWidget(restore_btn)
            open_btn = PushButton("Open")
            open_btn.setFixedWidth(90)
            open_btn.clicked.connect(lambda checked, p=r.get("path_obj"): self._open_backup(p))
            action_layout.addWidget(open_btn)
            delete_btn = PushButton("Delete")
            delete_btn.setFixedWidth(90)
            delete_btn.clicked.connect(lambda checked, p=r.get("path_obj"): self._delete_backup(p))
            action_layout.addWidget(delete_btn)
            action_layout.addStretch()
            self.backups_table.setCellWidget(row, 4, action_widget)

        # Ensure selection/controls are updated
        try:
            sel_model = self.backups_table.selectionModel()
            if sel_model:
                sel_model.clearSelection()
        except Exception:
            pass

    def _update_header_sort_indicators(self):
        labels = ["Type", "Date", "Size", "Filename", "Actions"]
        if getattr(self, "_type_sort_mode", "none") != "none":
            arrow = "↑" if self._type_sort_mode == "asc" else "↓"
            labels[0] = f"{labels[0]} {arrow}"
        arrow = "↑" if getattr(self, "_date_sort_mode", "desc") == "asc" else "↓"
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
        last_col = getattr(self, "_last_header_col", None)
        last_time = getattr(self, "_last_header_time", 0.0)
        if last_col == col and (now - last_time) < interval:
            return True
        self._last_header_col = col
        self._last_header_time = now
        return False

    def _on_table_header_clicked(self, col: int):
        if not hasattr(self, "_backup_rows"):
            return
        if self._should_skip_header_click(col):
            return
        self._ensure_sort_state()
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
        header = getattr(self, "_table_header", None)
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
        """Restore backup."""
        if not self.current_profile:
            return
            
        if confirm_action(self, "Restore Backup", f"Restore backup '{backup_file.name}'?"):
            try:
                run_restore(self.current_profile, self.config, backup_file, self.current_profile.clear_folder_on_restore)
                InfoBar.success(
                    "Restore Complete",
                    "Backup restored successfully",
                    parent=(getattr(self.window(), 'content_widget', self.window()) or self)
                )
            except Exception as e:
                InfoBar.error("Restore Failed", str(e), parent=(getattr(self.window(), 'content_widget', self.window()) or self))
                
    def _open_backup(self, backup_file):
        """Open backup location."""
        try:
            open_path_in_explorer(backup_file.parent)
        except Exception as e:
            InfoBar.error("Open Failed", str(e), parent=(getattr(self.window(), 'content_widget', self.window()) or self))
            
    def _delete_backup(self, backup_file):
        """Delete backup file."""
        if confirm_action(self, "Delete Backup", f"Delete backup '{backup_file.name}'?"):
            try:
                backup_file.unlink()
                self._refresh_backups()
                InfoBar.success("Backup Deleted", "Backup file deleted", parent=(getattr(self.window(), 'content_widget', self.window()) or self))
            except Exception as e:
                InfoBar.error("Delete Failed", str(e), parent=(getattr(self.window(), 'content_widget', self.window()) or self))


class ModernPluginsInterface(QWidget):
    """Plugins Page - SHOWS ACTUAL PLUGINS"""
    profiles_changed = pyqtSignal()
    
    def __init__(self, config: ConfigManager, plugin_manager: PluginManager, parent=None):
        super().__init__(parent)
        self.config = config
        self.plugin_manager = plugin_manager
        
        self._setup_ui()
        self._load_plugins()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header
        header = QHBoxLayout()
        header.addWidget(StrongBodyLabel("Game Plugins"))
        header.addStretch()
        
        self.refresh_btn = PushButton(FIF.SYNC, "Reload Plugins")
        self.refresh_btn.clicked.connect(self._load_plugins)
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
        self.plugins_table.setColumnCount(4)
        # Add an "Installed" column to clearly indicate detection status
        self.plugins_table.setHorizontalHeaderLabels(["Game", "ID", "Save Paths", "Installed"])
        self.plugins_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Allow selecting multiple rows (shift/ctrl) but keep rows selectable when dimmed
        self.plugins_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.plugins_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        layout.addWidget(self.plugins_table)

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
            # Installed: reflect whether this plugin is already added to profiles
            installed_ids = {p.plugin_id for p in self.config.games.values() if p.plugin_id}
            is_installed = plugin.game_id in installed_ids
            det_item = QTableWidgetItem("Yes" if is_installed else "No")
            self.plugins_table.setItem(row, 3, det_item)

            # Dim installed rows slightly while keeping them selectable
            if is_installed:
                dim_brush = QBrush(QColor("#7a7a7a"))
                name_item.setForeground(dim_brush)
                id_item.setForeground(dim_brush)
                paths_item.setForeground(dim_brush)
                det_item.setForeground(dim_brush)

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
            det_item = self.plugins_table.item(row, 3)
            paths_item = self.plugins_table.item(row, 2)
            if not pid_item or not name_item or det_item is None:
                continue
            pid = pid_item.text()
            if pid in detected_ids:
                # Highlight the entire row background to make detection obvious
                for col_item in (name_item, pid_item, paths_item, det_item):
                    if col_item is not None:
                        col_item.setBackground(highlight_brush)
            else:
                # Clear any previous highlight
                for col_item in (name_item, pid_item, paths_item, det_item):
                    if col_item is not None:
                        col_item.setBackground(clear_brush)

        InfoBar.info(
            "Detect Complete",
            "Detected games are highlighted. Use 'Add Selected' to add profiles.",
            parent=(getattr(self.window(), 'content_widget', self.window()) or self)
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
                # Installed status reflects existing profiles; avoid detection here
                installed_ids = {p.plugin_id for p in self.config.games.values() if p.plugin_id}
                is_installed = plugin.game_id in installed_ids
                det_item = QTableWidgetItem("Yes" if is_installed else "No")
                self.plugins_table.setItem(row, 0, name_item)
                self.plugins_table.setItem(row, 1, id_item)
                self.plugins_table.setItem(row, 2, paths_item)
                self.plugins_table.setItem(row, 3, det_item)
                if is_installed:
                    dim_brush = QBrush(QColor("#7a7a7a"))
                    name_item.setForeground(dim_brush)
                    id_item.setForeground(dim_brush)
                    paths_item.setForeground(dim_brush)
                    det_item.setForeground(dim_brush)

    def _add_selected(self):
        selected = self.plugins_table.selectionModel().selectedRows()
        if not selected:
            InfoBar.info(
                "No Selection",
                "Select at least one plugin to add.",
                parent=(getattr(self.window(), 'content_widget', self.window()) or self)
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
                parent=(getattr(self.window(), 'content_widget', self.window()) or self)
            )
            self._load_plugins()
            
            try:
                self.profiles_changed.emit()
            except Exception:
                pass
    


class ModernBackupSeekerWindow(AcrylicWindow):
    """Main Window - COMPLETELY FIXED"""
    
    def __init__(self):
        # Load config FIRST
        self.config = ConfigManager()
        super().__init__()
        
        # Initialize plugin manager with minimal logging
        original_level = logging.getLogger('BackupSeeker.plugin_manager').level
        logging.getLogger('BackupSeeker.plugin_manager').setLevel(logging.ERROR)
        self.plugin_manager = PluginManager(self.config.app_dir)
        logging.getLogger('BackupSeeker.plugin_manager').setLevel(original_level)
        
        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        
        # Apply saved theme
        self._apply_theme(self.config.theme)
        
    def _setup_window(self):
        """Setup window properly."""
        self.setTitleBar(ModernTitleBar(self))
        # Remove this line as it causes the overflow issue:
        # self.titleBar.raise_()  # This ensures window buttons are visible!
        
        # Avoid setting a window title string that some frameless/title
        # implementations render inside the client area. The modern title
        # bar widget provides the visible title, so keep the native window
        # title empty to prevent stray text rendering.
        self.setWindowTitle("")
        # Ensure a reasonable minimum startup size so layout adjustments
        # during initialization cannot shrink the window below this.
        self.setMinimumSize(1100, 700)
        # self.resize(1600, 900)
        self.center()
        
        # setThemeColor('#28afe9')
        # Use a stronger, dark blueish acrylic tint in dark mode so
        # lower-window content is less visible and has a cool tone.
        # Apply acrylic using a guarded helper that tries multiple formats
        # and logs the results. This helps diagnose parsing / byte-order
        # issues in underlying native APIs that previously produced a
        # red tint.
        # acrylic helper now implemented as a method on the window class

        dark_hex = "11112299"
        light_hex = "F0F0F099"
        # Try common formats in order
        candidates = [dark_hex] if is_app_dark() else [light_hex]
        # use the central helper implemented on the class
        self._try_acrylic(candidates)

    def showEvent(self, event):
        """Ensure title bar is raised after the window is shown so its
        buttons receive mouse events. Doing this after show avoids layout
        ordering issues that could let other widgets capture clicks.
        
        This helps ensure the custom title bar remains interactive.
        """
        super().showEvent(event)
        tb = getattr(self, "titleBar", None)
        if tb is not None:
            # Raise after a short delay to let layouts settle
            QTimer.singleShot(50, lambda: tb.raise_())
            tb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            tb.setMouseTracking(True)

        # # Ensure the window minimum size is set after the first show so
        # # layout changes when switching pages cannot shrink the window
        # # below the initially rendered size. This avoids unexpected
        # # resizing when returning to the dashboard while still allowing
        # # the user to resize the window larger.
        # try:
        #     if not hasattr(self, "_min_size_set"):
        #         sz = self.size()
        #         # Only apply if size is valid
        #         if sz.width() > 0 and sz.height() > 0:

        #             self.setMinimumSize(sz)
        #             self._min_size_set = True

        # except Exception:
        #     pass

    def center(self):
        """Center window."""
        screen = QGuiApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2)
        
    def _try_acrylic(self, opts, debug: bool = True) -> bool:
        """Attempt to apply acrylic effect using a list of candidate values.

        Returns True on first success, False otherwise. Logs attempts
        to an `acrylic_debug.log` file in the app dir.
        """
        log_path = Path(self.config.app_dir) / "acrylic_debug.log"
        for val in opts:
            try:
                # attempt
                self.windowEffect.setAcrylicEffect(self.winId(), val)

                if debug:
                    with open(log_path, "a", encoding="utf-8") as _f:
                        _f.write(f"{datetime.now().isoformat()} - setAcrylicEffect succeeded with: {repr(val)}\n")
                return True
            except Exception as e:
                if debug:
                    with open(log_path, "a", encoding="utf-8") as _f:
                        _f.write(f"{datetime.now().isoformat()} - setAcrylicEffect failed for {repr(val)}: {e}\n")
        return False
        
    def _setup_ui(self):
        """Setup UI with working pages."""
        # Outer vertical layout so we can add a full-width spacer under the
        # custom title bar. This prevents any child (navigation or content)
        # from overlapping the title controls.
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        # try:
        #     # Prevent the outer layout from forcing the window to resize
        #     # to match child size hints when pages are shown/hidden.
        #     outer_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        # except Exception:
        #     pass

        # full-width spacer matching title bar height
        title_bar = getattr(self, "titleBar", None)
        title_height = title_bar.sizeHint().height() if title_bar is not None else 45
        full_top_spacer = QWidget()
        full_top_spacer.setFixedHeight(title_height)
        full_top_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer_layout.addWidget(full_top_spacer)

        # Inner horizontal layout holds navigation and the content widget
        main_h_layout = QHBoxLayout()
        main_h_layout.setContentsMargins(0, 0, 0, 0)
        main_h_layout.setSpacing(0)

        # Navigation
        self.navigation = ModernNavigationInterface(self)
        self.navigation.setFixedWidth(280)

        # Content area
        self.content_widget = QWidget()
        self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.stacked_layout = QVBoxLayout(self.content_widget)
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)

        # Setup ALL interfaces (no placeholders!)
        self.dashboard = ModernDashboardInterface(self.config, parent=self)
        # Profiles management uses its own page (do not reuse dashboard)
        self.profiles_interface = ModernProfilesInterface(self.config, parent=self)
        self.backups_interface = ModernBackupsInterface(self.config)
        self.plugins_interface = ModernPluginsInterface(self.config, self.plugin_manager)
        self.settings_interface = self._create_settings_interface()

        # Add to content stacked layout
        self.stacked_layout.addWidget(self.dashboard)
        self.stacked_layout.addWidget(self.profiles_interface)
        self.stacked_layout.addWidget(self.backups_interface)
        self.stacked_layout.addWidget(self.plugins_interface)
        self.stacked_layout.addWidget(self.settings_interface)

        # Hide all except dashboard
        self.dashboard.hide()
        self.profiles_interface.hide()
        self.backups_interface.hide()
        self.plugins_interface.hide()
        self.settings_interface.hide()
        # show dashboard by default
        self.dashboard.show()

        # Setup navigation
        self._setup_navigation()

        main_h_layout.addWidget(self.navigation)
        main_h_layout.addWidget(self.content_widget)
        outer_layout.addLayout(main_h_layout)
        
    def _setup_navigation(self):
        """Setup navigation."""
        self.navigation.addItem(
            routeKey="dashboard",
            icon=FIF.HOME,
            text="Dashboard",
            onClick=lambda: self._show_interface("dashboard")
        )
        
        self.navigation.addItem(
            routeKey="profiles", 
            icon=FIF.APPLICATION,
            text="Profiles",
            onClick=lambda: self._show_interface("profiles")
        )
        
        self.navigation.addItem(
            routeKey="backups",
            icon=FIF.SAVE, 
            text="Backups",
            onClick=lambda: self._show_interface("backups")
        )
        
        self.navigation.addItem(
            routeKey="plugins",
            icon=FIF.GAME,
            text="Plugins", 
            onClick=lambda: self._show_interface("plugins")
        )
        
        self.navigation.addItem(
            routeKey="settings",
            icon=FIF.SETTING,
            text="Settings",
            onClick=lambda: self._show_interface("settings")
        )
        
        self.navigation.setCurrentItem("dashboard")
        
    def _create_settings_interface(self):
        """Create settings page."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("Settings"))

        # Theme selector
        layout.addWidget(BodyLabel("App Theme"))
        theme_row = QHBoxLayout()
        self.theme_combo = ComboBox()
        self.theme_combo.addItem("System")
        self.theme_combo.addItem("Dark")
        self.theme_combo.addItem("Light")
        # reflect current setting
        current = (self.config.theme or "system").lower()
        if current == "dark":
            self.theme_combo.setCurrentText("Dark")
        elif current == "light":
            self.theme_combo.setCurrentText("Light")
        else:
            self.theme_combo.setCurrentText("System")
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        layout.addLayout(theme_row)

        # Storage options
        layout.addWidget(BodyLabel("Backup Storage"))
        storage_row = QHBoxLayout()
        self.use_cwd_btn = PushButton("Use Current Dir (./backups)")
        self.use_cwd_btn.clicked.connect(self._set_backup_cwd)
        storage_row.addWidget(self.use_cwd_btn)

        self.choose_fixed_btn = PushButton("Use Fixed Location...")
        self.choose_fixed_btn.clicked.connect(self._choose_fixed_location)
        storage_row.addWidget(self.choose_fixed_btn)

        storage_row.addStretch()
        layout.addLayout(storage_row)

        # Current backup root display + open button
        root_row = QHBoxLayout()
        self.root_label = BodyLabel(f"Storage: {self.config.backup_root}")
        root_row.addWidget(self.root_label)
        open_btn = PushButton(FIF.FOLDER, "Open")
        open_btn.clicked.connect(lambda: self._open_backup_root())
        root_row.addWidget(open_btn)
        root_row.addStretch()
        layout.addLayout(root_row)

        layout.addStretch()
        return widget
        
    def _show_interface(self, key):
        """Lightweight interface switcher that does not preserve or reapply
        window geometry. This avoids window resize flicker when switching
        between navigation items and returning to the dashboard.
        """
        interfaces = {
            "dashboard": self.dashboard,
            "profiles": self.profiles_interface,
            "backups": self.backups_interface,
            "plugins": self.plugins_interface,
            "settings": self.settings_interface,
        }
        # Log geometry before change for debugging persistent resize issues
        logging.getLogger('BackupSeeker.ui_fluent').debug(f"_show_interface: switching to {key} - before size: {self.size().width()}x{self.size().height()} geom={self.geometry()}")

        for k, widget in interfaces.items():
            widget.setVisible(k == key)

        self.navigation.setCurrentItem(key)

        logging.getLogger('BackupSeeker.ui_fluent').debug(f"_show_interface: switched to {key} - after size: {self.size().width()}x{self.size().height()} geom={self.geometry()}")
        
    def _connect_signals(self):
        """Connect signals."""
        self.dashboard.backup_requested.connect(self._perform_backup)
        self.dashboard.restore_requested.connect(self._show_restore_dialog)
        # Refresh other pages when profiles change
        self.profiles_interface.profiles_changed.connect(self._on_profiles_changed)
        self.dashboard.profiles_changed.connect(self._on_profiles_changed)
        self.plugins_interface.profiles_changed.connect(self._on_profiles_changed)

    def _on_profiles_changed(self):
        """Callback invoked when profiles are added/edited/deleted."""
        # Refresh all pages that depend on profiles
        if hasattr(self, "dashboard"):
            self.dashboard._load_profiles()
        if hasattr(self, "profiles_interface"):
            self.profiles_interface._load_profiles()
        if hasattr(self, "backups_interface"):
            self.backups_interface._load_profiles()
        
    def _apply_theme(self, theme_name):
        """Apply theme."""

        if theme_name == "dark":
            setTheme(Theme.DARK)
        elif theme_name == "light":
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.AUTO)

        # Don't let theme failures terminate the program.
        # Reapply accent color (some widgets cache this)
        # setThemeColor('#28afe9')


        # Update acrylic/window effect which was initialized at startup

        if hasattr(self, "windowEffect") and hasattr(self.windowEffect, "setAcrylicEffect"):
                # Use a more opaque, dark-blue tint to lower acrylic transparency.
                # Reapply neutral tint using the same guarded helper.
                    dark_hex = "11112299"
                    light_hex = "F0F0F099"
                    candidates = [dark_hex] if is_app_dark() else [light_hex]
                    try:
                        self._try_acrylic(candidates)
                    except Exception:
                        pass


        # Process events so style changes propagate immediately

        app = QApplication.instance()
        if app is not None:
            app.processEvents()


    def _perform_backup(self):
        """Perform backup."""
        profile = self.dashboard.current_profile
        if not profile:
            return
            
        try:
            backup_path = run_backup(profile, self.config)
            self.dashboard.log(f"Backup created: {backup_path.name}")
            InfoBar.success("Success", "Backup completed", parent=(getattr(self, 'content_widget', self) or self))
        except Exception as e:
            self.dashboard.log(f"Backup failed: {str(e)}")
            InfoBar.error("Error", str(e), parent=(getattr(self, 'content_widget', self) or self))
        
    def _show_restore_dialog(self):
        """Show restore dialog as a popup listing backups for the selected profile."""
        profile = self.dashboard.current_profile
        if not profile:
            InfoBar.warning("No Profile", "Please select a game profile first", parent=(getattr(self, 'content_widget', self) or self))
            return

        dialog = RestoreBackupDialog(profile, self.config, self)
        dialog.exec()

    def _on_theme_changed(self, text: str):
        # Safer theme change flow: persist the user's choice and prompt
        # for a restart. Applying theme live can trigger native crashes
        # in some environments, so don't force a live apply by default.
        val = (text or "").strip().lower()
        if val == "dark":
            self.config.theme = "dark"
        elif val == "light":
            self.config.theme = "light"
        else:
            self.config.theme = "system"

        try:
            self.config.save_config()
        except Exception as e:
            try:
                InfoBar.warning("Save Failed", f"Could not persist theme: {e}", parent=(getattr(self, 'content_widget', self) or self))
            except Exception:
                pass

        # Prompt the user: restart recommended to fully apply theme.
        try:
            fn = getattr(MessageBox, "question", None)
            if callable(fn):
                # MessageBox.question signature varies; mirror earlier calls
                res = fn(self, "Theme Changed", "Restart recommended to fully apply theme. Restart now?", parent=self)
                from PyQt6.QtWidgets import QMessageBox as _QMB
                if res == _QMB.StandardButton.Yes:
                    try:
                        subprocess.Popen([sys.executable] + sys.argv)
                    except Exception:
                        pass
                    QApplication.quit()
                else:
                    # Offer a risky live-apply path if the user insists
                    # (not recommended). Use a secondary prompt.
                    res2 = _QMB.question(self, "Apply Now?", "Apply theme now without restart? This may crash the app.", _QMB.StandardButton.Yes | _QMB.StandardButton.No)
                    if res2 == _QMB.StandardButton.Yes:
                        try:
                            self._apply_theme(self.config.theme)
                        except Exception:
                            pass
            else:
                from PyQt6.QtWidgets import QMessageBox as _QMB
                ans = _QMB.question(self, "Theme Changed", "Restart recommended to fully apply theme. Restart now?", _QMB.StandardButton.Yes | _QMB.StandardButton.No)
                if ans == _QMB.StandardButton.Yes:
                    try:
                        subprocess.Popen([sys.executable] + sys.argv)
                    except Exception:
                        pass
                    QApplication.quit()
        except Exception:
            # Best-effort: inform user to restart via InfoBar
            try:
                InfoBar.info("Theme Saved", "Restart the application to fully apply the new theme.", parent=(getattr(self, 'content_widget', self) or self))
            except Exception:
                pass

    def _set_backup_cwd(self):
        self.config.set_backup_mode_cwd()
        # Refresh UI elements that show backup root
        try:
            if hasattr(self, "backups_interface"):
                self.backups_interface._refresh_backups()
        except Exception:
            pass
        try:
            if hasattr(self, "root_label"):
                self.root_label.setText(f"Storage: {self.config.backup_root}")
        except Exception:
            pass

    def _choose_fixed_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Storage Folder")
        if folder:
            self.config.set_backup_mode_fixed(folder)
            try:
                if hasattr(self, "backups_interface"):
                    self.backups_interface._refresh_backups()
            except Exception:
                pass
            try:
                if hasattr(self, "root_label"):
                    self.root_label.setText(f"Storage: {self.config.backup_root}")
            except Exception:
                pass

    def _open_backup_root(self):
        try:
            path = self.config.backup_root
            path.mkdir(parents=True, exist_ok=True)
            open_path_in_explorer(path)
        except Exception as e:
            InfoBar.error("Open Failed", str(e), parent=(getattr(self, 'content_widget', self) or self))

class RestoreBackupDialog(QDialog):
    """Popup widget for restoring backups."""
    
    def __init__(self, profile: GameProfile, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.config = config
        self.selected_backup = None
        
        self.setFixedSize(700, 500)
        self._setup_ui()
        self._load_backups()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(StrongBodyLabel(f"Restore Backup: {self.profile.name}"))
        header_layout.addStretch()
        
        self.refresh_btn = PushButton(FIF.SYNC, "Refresh")
        self.refresh_btn.clicked.connect(self._load_backups)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Backups table
        self.backups_table = TableWidget()
        self.backups_table.setColumnCount(4)
        self.backups_table.setHorizontalHeaderLabels(["Type", "Date", "Size", "Filename"])
        self.backups_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.backups_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.backups_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.backups_table.doubleClicked.connect(self._restore_selected)
        
        layout.addWidget(self.backups_table)
        
        # Info text
        info_label = CaptionLabel("🛡️ Safety backups are created automatically before each restore operation")
        info_label.setStyleSheet("CaptionLabel{color: #666; padding: 5px;}")
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
        
    def _load_backups(self):
        """Load all backups for the profile."""
        self.backups_table.setRowCount(0)
        
        # Get regular backups
        backup_dir = self.config.get_game_backup_dir(self.profile.name)
        safety_dir = self.config.get_safety_backup_dir(self.profile.name)
        
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
        
        for file, backup_type in backups:
            row = self.backups_table.rowCount()
            self.backups_table.insertRow(row)
            
            # Type with appropriate icon
            type_icon = "🛡️ Safety" if backup_type == "Safety" else "💾 Regular"
            self.backups_table.setItem(row, 0, QTableWidgetItem(type_icon))
            
            # Date
            mtime = file.stat().st_mtime
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            self.backups_table.setItem(row, 1, QTableWidgetItem(date_str))
            
            # Size
            size_bytes = file.stat().st_size
            if size_bytes < 1024 * 1024:
                size_str = f"{size_bytes/1024:.1f} KB"
            else:
                size_str = f"{size_bytes/1024/1024:.1f} MB"
            self.backups_table.setItem(row, 2, QTableWidgetItem(size_str))
            
            # Filename
            item = QTableWidgetItem(file.name)
            item.setData(Qt.ItemDataRole.UserRole, file)  # Store file path
            self.backups_table.setItem(row, 3, item)
            
    def _on_selection_changed(self):
        """Enable/disable restore button based on selection."""
        selected = self.backups_table.selectionModel().hasSelection()
        self.restore_btn.setEnabled(selected)
        
    def _restore_selected(self):
        """Restore the selected backup."""
        selected_items = self.backups_table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        file_item = self.backups_table.item(row, 3)
        if not file_item:
            return
            
        backup_file = file_item.data(Qt.ItemDataRole.UserRole)
        backup_type = "Safety" if "Safety" in self.backups_table.item(row, 0).text() else "Regular"
        
        # Confirmation dialog
        if backup_type == "Safety":
            message = f"Restore safety backup?\n{backup_file.name}\n\nThis will overwrite current game data."
        else:
            message = f"Restore backup?\n{backup_file.name}\n\nCurrent data will be archived to Safety folder first."
            
        if confirm_action(self, "Confirm Restore", message):
            try:
                run_restore(self.profile, self.config, backup_file, self.profile.clear_folder_on_restore)
                InfoBar.success(
                    "Restore Complete",
                    f"Backup restored successfully",
                    parent=(getattr(self.window(), 'content_widget', self.window()) or self)
                )
                self.accept()
            except Exception as e:
                InfoBar.error("Restore Failed", str(e), parent=(getattr(self.window(), 'content_widget', self.window()) or self))

def run_modern_fluent_app() -> int:
    """Run the fixed modern app."""
    try:
        logging.getLogger('BackupSeeker.plugin_manager').setLevel(logging.WARNING)

        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(sys.argv)
        app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

        translator = FluentTranslator()
        app.installTranslator(translator)

        # Respect saved user preference for theme instead of forcing dark.
        # Create a temporary ConfigManager to read the persisted theme
        # before any theme-dependent window setup occurs.
        try:
            cfg = ConfigManager()
            if (cfg.theme or "").lower() == "dark":
                setTheme(Theme.DARK)
            elif (cfg.theme or "").lower() == "light":
                setTheme(Theme.LIGHT)
            else:
                setTheme(Theme.AUTO)
        except Exception:
            # Fall back to automatic theme detection if config cannot be read
            setTheme(Theme.AUTO)

        window = ModernBackupSeekerWindow()
        window.show()

        return app.exec()

    except Exception as e:
        # Log traceback then ask user whether to restart rather than exiting silently.
        import traceback as _tb
        _tb.print_exc()

        msg = f"A fatal error occurred in the Fluent UI:\n{e}\n\nWould you like to restart the application?"
        confirmed = False
        try:
            # Prefer qfluentwidgets MessageBox if available
            fn = getattr(MessageBox, "question", None)
            if callable(fn):
                res = fn(None, "Fluent UI Error", msg, parent=None)
                from PyQt6.QtWidgets import QMessageBox as _QMB
                confirmed = res == _QMB.StandardButton.Yes
            else:
                from PyQt6.QtWidgets import QMessageBox as _QMB
                ans = _QMB.question(None, "Fluent UI Error", msg, _QMB.StandardButton.Yes | _QMB.StandardButton.No)
                confirmed = ans == _QMB.StandardButton.Yes
        except Exception:
            confirmed = False

        if confirmed:
            try:
                subprocess.Popen([sys.executable] + sys.argv)
            except Exception:
                pass

        # Fall back to legacy UI if available, otherwise exit gracefully.
        try:
            from .ui import run_app as fallback_run
            return fallback_run()
        except Exception:
            return 1