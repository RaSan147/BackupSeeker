from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
	QAbstractItemView,
	QHeaderView,
	QHBoxLayout,
	QListView,
	QListWidget,
	QListWidgetItem,
	QLabel,
	QSizePolicy,
	QTableWidgetItem,
	QVBoxLayout,
	QWidget,
)

from qfluentwidgets import (
	CaptionLabel,
	ComboBox,
	InfoBar,
	LineEdit,
	PlainTextEdit,
	PrimaryPushButton,
	PushButton,
	StrongBodyLabel,
	TableWidget,
	FluentIcon as FIF,
)

from ..core import ConfigManager, GameProfile
from ..developer_mode import set_dev_widgets_visible
from ..fluent_window import plugin_manager_from_widget, resolve_plugin_for_profile, toast_parent
from ..modern_widgets import ModernGameEditor, RoundedCard
from ..ui_shared import confirm_action
from . import helpers as _dash_helpers
from .helpers import (
	_install_read_only_table,
	_make_transparent_widget,
	_profile_display_name,
	apply_combo_ui_view,
	last_backup_label,
	ui_view_mode_from_combo_text,
)
from .poster_refresh import PosterRefreshCoordinator
from .profile_visuals import (
	POSTER_LABEL_NAME,
	ProfilePosterService,
	fit_pixmap_to_label,
	is_emoji_icon,
)
from .styles import AdaptiveThemeStyles, LIST_STYLE_TRANSPARENT


class ModernDashboardInterface(QWidget):
    """Dashboard with profile selection, quick actions, and status display."""

    # Cover art in the right-hand profile card: scales with sidebar width, capped
    _COVER_ART_MAX_W = 320
    _COVER_ART_MAX_H = 200

    backup_requested = pyqtSignal()
    restore_requested = pyqtSignal()
    profiles_changed = pyqtSignal()
    
    def __init__(
        self,
        config: ConfigManager,
        plugin_manager=None,
        poster_refresh: PosterRefreshCoordinator | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.config = config
        self._poster_refresh = poster_refresh
        self._posters = ProfilePosterService(
            self,
            plugin_manager=plugin_manager,
            app_dir=config.app_dir,
        )
        self.current_profile = None
        self._cover_pixmap_full: QPixmap | None = None

        self._setup_ui()
        self._load_profiles()
        if self._poster_refresh is not None:
            self._poster_refresh.register(self.refresh_posters)

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._refresh_cover_pixmap()

    def _reset_profile_detail_panel(self) -> None:
        """Clear names, icons, and cover — no backup/restore toggle here."""
        self.profile_name.setText("Select a Game Profile")
        self.profile_icon.setText("🎮")
        self.profile_icon.setStyleSheet("QLabel{font-size: 24px;}")
        self._cover_pixmap_full = None
        self.cover_label.clear()
        self.cover_label.setVisible(False)

    def _sidebar_cover_budget(self) -> QSize:
        """Responsive max size for cover art inside the profile card."""
        inner = 0
        parent = self.cover_label.parentWidget()
        if parent is not None:
            inner = parent.width()
        if inner <= 0 and getattr(self, "info_card", None) is not None:
            inner = self.info_card.width()
        if inner <= 0:
            inner = self._COVER_ART_MAX_W
        avail = max(56, min(inner - 24, self._COVER_ART_MAX_W))
        return QSize(int(avail), int(self._COVER_ART_MAX_H))

    def _refresh_cover_pixmap(self) -> None:
        if self._cover_pixmap_full is None or self._cover_pixmap_full.isNull():
            self.cover_label.clear()
            return
        fit_pixmap_to_label(
            self.cover_label,
            self._cover_pixmap_full,
            self._sidebar_cover_budget(),
        )

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
        apply_combo_ui_view(self.view_toggle, self.config.ui_view_dashboard_profiles)

        self.dev_refresh_btn = PushButton(FIF.SYNC, "Refresh")
        self.dev_refresh_btn.setToolTip("Developer: reload config and refresh profiles")
        self.dev_refresh_btn.clicked.connect(self._dev_refresh)
        self.dev_refresh_btn.setVisible(False)
        profiles_header.addWidget(self.dev_refresh_btn)

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

        self.profiles_list.setStyleSheet(LIST_STYLE_TRANSPARENT)
        _make_transparent_widget(self.profiles_list)

        # Prevent list items/cards from being draggable or moved by the view.

        self.profiles_list.setDragEnabled(False)
        self.profiles_list.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.profiles_list.setMovement(QListView.Movement.Static)
        self.profiles_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.profiles_list.setFlow(QListView.Flow.LeftToRight)
        self.profiles_list.setWrapping(True)
        self.profiles_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.profiles_list.setUniformItemSizes(True)

        # Default sizes for card mode
        self._card_image_size = QSize(160, 90)
        self._card_grid_size = QSize(200, 156)
        self.profiles_list.setIconSize(self._card_image_size)
        self.profiles_list.setSpacing(8)
        # Compact table: Name + Last Backup (actions live under Game Profiles)
        self.profiles_table = TableWidget()
        self.profiles_table.setColumnCount(2)
        self.profiles_table.setHorizontalHeaderLabels(["Name", "Last Backup"])
        pheader = self.profiles_table.horizontalHeader()
        pheader.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        pheader.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.profiles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.profiles_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Apply theme-aware stylesheet
        styles = AdaptiveThemeStyles()
        styles.apply_table_style(self.profiles_table)
        _install_read_only_table(self.profiles_table)
        # Keep table selection changes in sync with dashboard controls
        self.profiles_table.itemSelectionChanged.connect(self._on_profile_table_selected)

        # Add both views; visibility toggled in _load_profiles
        profiles_layout.addWidget(self.profiles_table)
        profiles_layout.addWidget(self.profiles_list)
        
        left_column.addWidget(profiles_card)
        
        # Right column - Profile info (tight vertical rhythm; avoid stretching card body)
        right_column = QVBoxLayout()
        right_column.setSpacing(12)
        right_column.setContentsMargins(0, 0, 0, 0)

        # Profile info card — height = content only; do not Expanding vertically
        # or full-screen will insert huge gaps between header, cover, and actions.
        self.info_card = RoundedCard()
        self.info_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.info_card.setMaximumWidth(900)
        info_card_layout = QVBoxLayout(self.info_card)
        info_card_layout.setContentsMargins(16, 14, 16, 14)
        info_card_layout.setSpacing(10)

        # Header area: icon + title
        self.profile_header = QHBoxLayout()
        self.profile_header.setSpacing(8)
        self.profile_icon = QLabel("🎮")
        self.profile_icon.setStyleSheet("QLabel{font-size: 22px;}")
        self.profile_name = StrongBodyLabel("Select a Game Profile")
        self.profile_name.setStyleSheet("StrongBodyLabel{font-size: 16px;}")
        self.profile_name.setWordWrap(True)

        self.profile_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.profile_name.setMaximumHeight(56)

        self.profile_header.addWidget(self.profile_icon)
        self.profile_header.addWidget(self.profile_name)
        self.profile_header.addStretch()
        info_card_layout.addLayout(self.profile_header)

        # Cover image: scales with sidebar width up to max size (see _sidebar_cover_budget)
        self.cover_label = QLabel()
        self.cover_label.setScaledContents(False)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("QLabel{background: transparent; border:0;}")
        self.cover_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.cover_label.setMinimumSize(1, 1)
        self.cover_label.setMaximumWidth(self._COVER_ART_MAX_W)
        self.cover_label.setMaximumHeight(self._COVER_ART_MAX_H)
        self.cover_label.setVisible(False)
        info_card_layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignHCenter)

        # Actions: equal-width row, consistent with typical fluent side panels
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        self.backup_btn = PrimaryPushButton(FIF.SAVE, "Backup Now")
        self.backup_btn.setFixedHeight(40)
        self.backup_btn.setMinimumWidth(0)
        self.backup_btn.clicked.connect(self.backup_requested.emit)
        self.backup_btn.setEnabled(False)

        self.restore_btn = PushButton(FIF.SYNC, "Restore")
        self.restore_btn.setFixedHeight(40)
        self.restore_btn.setMinimumWidth(0)
        self.restore_btn.clicked.connect(self.restore_requested.emit)
        self.restore_btn.setEnabled(False)

        action_layout.addWidget(self.backup_btn, 1)
        action_layout.addWidget(self.restore_btn, 1)
        info_card_layout.addLayout(action_layout)
        
        # Activity log (create before adding to layouts to avoid scope issues)
        log_card = RoundedCard()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 12, 16, 12)
        log_layout.setSpacing(8)

        log_title = StrongBodyLabel("Activity Log")
        log_title.setStyleSheet("StrongBodyLabel{font-size: 13px;}")
        log_layout.addWidget(log_title)
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

        # Sidebar column: profile block + log stay pinned to the top; extra window
        # height becomes empty space below the log (not blown up inside info_card).
        right_container = QWidget()
        rc_layout = QVBoxLayout(right_container)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.setSpacing(12)
        right_container.setMinimumWidth(340)
        right_container.setMaximumWidth(440)
        right_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        rc_layout.addWidget(self.info_card, 0, Qt.AlignmentFlag.AlignTop)
        rc_layout.addWidget(log_card, 0, Qt.AlignmentFlag.AlignTop)
        rc_layout.addStretch(1)

        right_column.addWidget(right_container)
        
        # Combine columns with stretch factors to stabilize sizing (right panel ~20%)
        content_layout.addLayout(left_column, 4)
        content_layout.addLayout(right_column, 1)
        layout.addLayout(content_layout)
        
    def _load_profiles(self, *, preserve_selection: bool = True):
        """Load existing profiles and refresh dashboard display.

        When *preserve_selection* is True (default), the profile that was
        selected before reload (if any) stays selected afterward. This avoids
        clearing the dashboard when the table is rebuilt — e.g. after a backup
        refreshes the "Last Backup" column.
        """
        keep_pid = (
            self.current_profile.id if (preserve_selection and self.current_profile) else None
        )
        # Reset selection and visible controls to avoid stale state
        self.current_profile = None
        self.backup_btn.setEnabled(False)
        self.restore_btn.setEnabled(False)

        # Clear sidebar UI to show "not selected" state
        self._reset_profile_detail_panel()

        # Clear both list and table views before repopulating to avoid duplicates
        self.profiles_list.clear()
        self.profiles_table.setRowCount(0)

        # Ensure view mode settings are applied
        mode = self.view_toggle.currentText()
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
                row = self.profiles_table.rowCount()
                self.profiles_table.insertRow(row)
                name_item = QTableWidgetItem(_dash_helpers._profile_kind_prefix(profile) + _profile_display_name(profile, self))
                name_item.setData(Qt.ItemDataRole.UserRole, profile_id)
                self.profiles_table.setItem(row, 0, name_item)

                last_dt = last_backup_label(profile, self, self.config).removeprefix("Last: ")
                self.profiles_table.setItem(row, 1, QTableWidgetItem(last_dt))
            
        # Show table in list mode, list widget in cards mode
        self.profiles_table.setVisible(not is_cards)
        self.profiles_list.setVisible(is_cards)

        # Re-apply search filter after rebuild (row hidden state is lost on repopulate)
        try:
            self._on_profiles_search(self.search_edit.text())
        except Exception:
            pass

        # Restore selection when requested, otherwise clear — same as old clear-only path
        try:
            if keep_pid and keep_pid in self.config.games:
                if is_cards:
                    for i in range(self.profiles_list.count()):
                        item = self.profiles_list.item(i)
                        if not item:
                            continue
                        if item.data(Qt.ItemDataRole.UserRole) == keep_pid:
                            self.profiles_list.setCurrentItem(item)
                            self._on_profile_selected(item)
                            break
                else:
                    for row in range(self.profiles_table.rowCount()):
                        name_item = self.profiles_table.item(row, 0)
                        if (
                            name_item
                            and name_item.data(Qt.ItemDataRole.UserRole) == keep_pid
                        ):
                            self.profiles_table.selectRow(row)
                            prof = self.config.games.get(keep_pid)
                            if prof:
                                self.current_profile = prof
                                self.backup_btn.setEnabled(True)
                                self.restore_btn.setEnabled(True)
                                self._display_profile(prof)
                            break
            else:
                if not is_cards:
                    sel_model = self.profiles_table.selectionModel()
                    if sel_model:
                        sel_model.clearSelection()
                else:
                    list_sel_model = self.profiles_list.selectionModel()
                    if list_sel_model:
                        list_sel_model.clearSelection()
        except Exception:
            pass

        if self.config.games:
            self.log("Loaded existing profiles")
        else:
            self.log("No profiles found. Add your first game!")

    def _on_profiles_view_changed(self, text: str):
        """Switch between List and Cards view for profiles."""
        self.config.ui_view_dashboard_profiles = ui_view_mode_from_combo_text(text)
        self.config.save_config()
        self._load_profiles()

    def _on_profile_table_selected(self):
        """Handle selection coming from the compact dashboard table."""
        sel = self.profiles_table.selectionModel().selectedRows()
        if not sel:
            self.current_profile = None
            self.backup_btn.setEnabled(False)
            self.restore_btn.setEnabled(False)
            self._reset_profile_detail_panel()
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
                    name = _profile_display_name(profile, self)
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
                    row_name = _profile_display_name(self.config.games[profile_id], self)
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
            self.log(f"Added: {_profile_display_name(editor.profile, self)}")
            # Show a toast anchored to the main window so its placement
            # matches other app notifications.
            try:
                InfoBar.success(
                    "Profile Added",
                    f"Added profile: {_profile_display_name(editor.profile, self)}",
                    parent=toast_parent(self)
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
        if prof.plugin_id:
            pm = plugin_manager_from_widget(self)
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
                origin = spec.origin if spec is not None else None
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
            if confirm_action(self, "Delete Profile", f"Are you sure you want to delete '{_profile_display_name(profile, self)}'?"):
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
        """Update sidebar header + responsive cover image for the selected profile."""
        self.profile_name.setText(_profile_display_name(profile, self))

        icon_str = self._posters.icon_for(profile)
        if icon_str and is_emoji_icon(icon_str):
            self.profile_icon.setText(icon_str)
            self.profile_icon.setStyleSheet("QLabel{font-size: 24px;}")

        self.backup_btn.setEnabled(True)
        self.restore_btn.setEnabled(True)

        allow_ph = not self._posters.expects_download(profile)
        budget = self._sidebar_cover_budget()

        def refresh_display():
            if self.current_profile != profile:
                return
            pix = self._posters.pixmap_for(
                profile,
                poster_size=budget,
                allow_placeholder=allow_ph,
                queue_download=False,
            )
            if pix.isNull():
                self._cover_pixmap_full = None
                self.cover_label.clear()
                self.cover_label.setVisible(False)
            else:
                self._cover_pixmap_full = pix
                self.cover_label.setVisible(True)
                self._refresh_cover_pixmap()
                QTimer.singleShot(0, self._refresh_cover_pixmap)

        self._posters.poster_path(profile, on_complete=lambda: QTimer.singleShot(0, refresh_display), queue_download=False)
        pix = self._posters.pixmap_for(
            profile,
            poster_size=budget,
            allow_placeholder=allow_ph,
            queue_download=False,
        )

        if pix.isNull():
            self._cover_pixmap_full = None
            self.cover_label.clear()
            self.cover_label.setVisible(False)
        else:
            self._cover_pixmap_full = pix
            self.cover_label.setVisible(True)
            self._refresh_cover_pixmap()
            QTimer.singleShot(0, self._refresh_cover_pixmap)

        self.log(f"Selected: {_profile_display_name(profile, self)}")


    def log(self, message: str):
        """Add timestamped message to activity log display.
        
        Args:
            message: Message to display in the log view
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{timestamp}] {message}")

    def refresh_posters(self, plugin_game_id: str | None = None) -> None:
        """Refresh card posters and the sidebar cover (PosterRefreshCoordinator target)."""

        self._refresh_all_profile_cards()
        prof = self.current_profile
        if prof is None:
            return
        pid = (prof.plugin_id or "").strip()
        if plugin_game_id is None or pid == (plugin_game_id or "").strip():
            self._display_profile(prof)

    def _refresh_all_profile_cards(self) -> None:
        """Refresh every visible dashboard card poster."""

        mode = self.view_toggle.currentText()
        if not (mode or "").lower().startswith("c"):
            return
        allow = lambda p: not self._posters.expects_download(p)
        for i in range(self.profiles_list.count()):
            item = self.profiles_list.item(i)
            if item is None:
                continue
            profile_id = item.data(Qt.ItemDataRole.UserRole)
            profile = self.config.games.get(profile_id)
            if not profile:
                continue
            card = self.profiles_list.itemWidget(item)
            if card is not None:
                self._posters.apply_to_card(
                    card,
                    profile,
                    self._card_image_size,
                    allow_placeholder=allow(profile),
                )
        try:
            self.profiles_list.viewport().update()
        except Exception:
            pass

    def _create_profile_card(self, profile: GameProfile) -> QWidget:
        """Create a dashboard card matching the profile-management card structure."""
        styles = AdaptiveThemeStyles()
        card = RoundedCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)

        poster_size = self._card_image_size

        poster_container = QWidget()
        poster_container.setFixedSize(poster_size)
        poster_container.setStyleSheet("background: transparent;")

        img_label = QLabel(poster_container)
        img_label.setObjectName(POSTER_LABEL_NAME)
        img_label.setGeometry(0, 0, poster_size.width(), poster_size.height())
        img_label.setFixedSize(poster_size)
        img_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._posters.apply_to_label(
            img_label,
            profile,
            poster_size,
            allow_placeholder=not self._posters.expects_download(profile),
            queue_download=False,
        )

        title_overlay = QWidget(poster_container)
        overlay_h = max(1, int(poster_size.height() * 0.7))
        title_overlay.setGeometry(
            0,
            poster_size.height() - overlay_h,
            poster_size.width(),
            overlay_h,
        )
        title_overlay.setStyleSheet(
            "QWidget {"
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 rgba(0,0,0,0), stop:1 rgba(0,0,0,0.88));"
            "border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
            "}"
        )
        ovl_layout = QVBoxLayout(title_overlay)
        ovl_layout.setContentsMargins(8, 8, 8, 6)
        ovl_layout.addStretch(1)
        title = QLabel(_profile_display_name(profile, self))
        title.setStyleSheet(
            "QLabel{font-size:12px;font-weight:600;color:#ffffff !important;background:transparent;}"
        )
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        ovl_layout.addWidget(title)

        icon_str = self._posters.icon_for(profile)
        if icon_str and is_emoji_icon(icon_str):
            badge = QLabel(icon_str, poster_container)
            badge.setStyleSheet(
                f"QLabel{{font-size: 18px; background: {styles.badge_bg()}; padding: 4px; border-radius: 4px;}}"
            )
            badge.setFixedSize(32, 32)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.move(6, 6)

        card_layout.addWidget(poster_container, 0, Qt.AlignmentFlag.AlignHCenter)

        info_container = QWidget()
        info_container.setObjectName("dashboardProfileInfoPanel")
        info_container.setFixedWidth(poster_size.width())
        info_container.setStyleSheet(styles.info_panel_stylesheet("dashboardProfileInfoPanel", radius=8))
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(8, 6, 8, 6)
        info_layout.setSpacing(3)

        meta = CaptionLabel()
        meta.setStyleSheet(f"CaptionLabel{{font-size:10px; color:{styles.text_secondary()};}}")
        meta.setText(last_backup_label(profile, self, self.config, date_fmt="%Y-%m-%d"))
        info_layout.addWidget(meta)

        card_layout.addWidget(info_container, 0, Qt.AlignmentFlag.AlignHCenter)
        card.setStyleSheet("background: transparent;")

        return card

    def set_developer_mode(self, enabled: bool) -> None:
        set_dev_widgets_visible(enabled, (self.dev_refresh_btn,))

    def _dev_refresh(self) -> None:
        root = self.window()
        fn = getattr(root, "developer_refresh", None)
        if callable(fn):
            fn("dashboard")
