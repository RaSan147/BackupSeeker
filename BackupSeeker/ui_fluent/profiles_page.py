from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
	QAbstractItemView,
	QDialog,
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

from ..core import ConfigManager, GameProfile, verify_save_locations_report
from ..developer_mode import set_dev_widgets_visible
from ..modern_widgets import ModernGameEditor, RoundedCard
from ..ui_shared import confirm_action
from .helpers import (
	_install_read_only_table,
	_make_transparent_widget,
	_profile_display_name,
	_profile_kind_prefix,
	apply_combo_ui_view,
	format_verify_report_text,
	last_backup_label,
	ui_view_mode_from_combo_text,
)
from ..fluent_window import resolve_plugin_for_profile, toast_parent
from .poster_refresh import PosterRefreshCoordinator
from .profile_visuals import POSTER_LABEL_NAME, ProfilePosterService, is_emoji_icon
from .styles import AdaptiveThemeStyles, LIST_STYLE_TRANSPARENT


class ModernProfilesInterface(QWidget):
    """Profile management interface for add, edit, delete, and search operations."""
    profiles_changed = pyqtSignal()

    _CARD_POSTER_SIZE = QSize(240, 135)
    _CARD_GRID_SIZE = QSize(280, 236)
    
    def __init__(
        self,
        config: ConfigManager,
        poster_refresh: PosterRefreshCoordinator | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.config = config
        self._poster_refresh = poster_refresh
        self._posters = ProfilePosterService(self, app_dir=config.app_dir)
        
        self._setup_ui()
        self._load_profiles()
        if self._poster_refresh is not None:
            self._poster_refresh.register(self.refresh_posters)
        
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
        
        # View mode selector (List / Cards)
        self.profiles_view_toggle = ComboBox()
        self.profiles_view_toggle.addItem("List")
        self.profiles_view_toggle.addItem("Cards")
        self.profiles_view_toggle.setFixedWidth(110)
        self.profiles_view_toggle.currentTextChanged.connect(self._on_profiles_view_changed)
        header.addWidget(self.profiles_view_toggle)
        apply_combo_ui_view(self.profiles_view_toggle, self.config.ui_view_profiles_management)

        self.dev_refresh_btn = PushButton(FIF.SYNC, "Refresh")
        self.dev_refresh_btn.setToolTip("Developer: reload config and refresh profiles")
        self.dev_refresh_btn.clicked.connect(self._dev_refresh)
        self.dev_refresh_btn.setVisible(False)
        header.addWidget(self.dev_refresh_btn)
        
        self.add_btn = PrimaryPushButton(FIF.ADD, "Add Profile")
        self.add_btn.clicked.connect(self._add_profile)
        header.addWidget(self.add_btn)
        
        layout.addLayout(header)
        
        # Profiles table
        self.profiles_table = TableWidget()
        self.profiles_table.setColumnCount(3)
        self.profiles_table.setHorizontalHeaderLabels(["Name", "Last Backup", "Actions"])
        pheader = self.profiles_table.horizontalHeader()
        pheader.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        pheader.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        pheader.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.profiles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # Apply theme-aware stylesheet
        styles = AdaptiveThemeStyles()
        styles.apply_table_style(self.profiles_table)
        _install_read_only_table(self.profiles_table)
        
        # Profiles list (card view)
        self.profiles_card_list = QListWidget()
        self.profiles_card_list.setViewMode(QListView.ViewMode.IconMode)
        self.profiles_card_list.setIconSize(self._CARD_POSTER_SIZE)
        self.profiles_card_list.setGridSize(self._CARD_GRID_SIZE)
        self.profiles_card_list.setSpacing(12)
        self.profiles_card_list.setStyleSheet(LIST_STYLE_TRANSPARENT)
        self.profiles_card_list.setDragEnabled(False)
        self.profiles_card_list.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.profiles_card_list.setMovement(QListView.Movement.Static)
        self.profiles_card_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.profiles_card_list.setFlow(QListView.Flow.LeftToRight)
        self.profiles_card_list.setWrapping(True)
        self.profiles_card_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.profiles_card_list.setUniformItemSizes(True)
        _make_transparent_widget(self.profiles_card_list)
        
        # Add both table and list views to layout
        layout.addWidget(self.profiles_table)
        layout.addWidget(self.profiles_card_list)
        
    def _load_profiles(self):
        """Load profiles into table and list views."""
        self.profiles_table.setRowCount(0)
        self.profiles_card_list.clear()
        
        # Determine which view is active
        mode = self.profiles_view_toggle.currentText()
        is_cards = (mode or '').lower().startswith('c')
        
        for profile_id, profile in self.config.games.items():
            if is_cards:
                # Add to card list
                item = QListWidgetItem()
                item.setSizeHint(self._CARD_GRID_SIZE)
                item.setData(Qt.ItemDataRole.UserRole, profile_id)
                self.profiles_card_list.addItem(item)
                widget = self._create_profile_card(profile_id, profile)
                self.profiles_card_list.setItemWidget(item, widget)
            else:
                # Add to table
                row = self.profiles_table.rowCount()
                self.profiles_table.insertRow(row)
                
                # Name
                self.profiles_table.setItem(row, 0, QTableWidgetItem(_profile_kind_prefix(profile) + _profile_display_name(profile, self)))
                # Last Backup (compute)
                self.profiles_table.setItem(
                    row,
                    1,
                    QTableWidgetItem(last_backup_label(profile, self, self.config).removeprefix("Last: ")),
                )

                action_widget = QWidget()
                action_layout = QHBoxLayout(action_widget)
                action_layout.setContentsMargins(5, 5, 5, 5)

                edit_btn = PushButton("Edit")
                edit_btn.setFixedWidth(72)
                edit_btn.clicked.connect(lambda checked, pid=profile_id: self._edit_profile(pid))

                verify_btn = PushButton("Verify")
                verify_btn.setFixedWidth(72)
                verify_btn.clicked.connect(lambda checked, pid=profile_id: self._verify_profile(pid))

                delete_btn = PushButton("Delete")
                delete_btn.setFixedWidth(72)
                delete_btn.clicked.connect(lambda checked, pid=profile_id: self._delete_profile(pid))

                action_layout.addWidget(edit_btn)
                action_layout.addWidget(verify_btn)
                action_layout.addWidget(delete_btn)
                action_layout.addStretch()

                self.profiles_table.setCellWidget(row, 2, action_widget)
        
        # Toggle visibility
        self.profiles_table.setVisible(not is_cards)
        self.profiles_card_list.setVisible(is_cards)

    def _on_profiles_view_changed(self, text: str):
        """Switch between List and Cards view for profiles."""
        self.config.ui_view_profiles_management = ui_view_mode_from_combo_text(text)
        self.config.save_config()
        self._load_profiles()
        
    def _create_profile_card(self, profile_id: str, profile: GameProfile) -> QWidget:
        """Create a card widget for a game profile with poster image and icon overlay."""
        styles = AdaptiveThemeStyles()
        card = RoundedCard()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)

        poster_size = self._CARD_POSTER_SIZE

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
            "border-bottom-left-radius: 10px; border-bottom-right-radius: 10px;"
            "}"
        )
        ovl_layout = QVBoxLayout(title_overlay)
        ovl_layout.setContentsMargins(10, 10, 10, 8)
        ovl_layout.addStretch(1)
        name_label = QLabel(_profile_display_name(profile, self))
        name_label.setStyleSheet(
            "QLabel{font-weight:bold;font-size:13px;color:#ffffff !important;background:transparent;}"
        )
        name_label.setWordWrap(True)
        ovl_layout.addWidget(name_label)

        icon_str = self._posters.icon_for(profile)
        if icon_str and is_emoji_icon(icon_str):
            badge = QLabel(icon_str, poster_container)
            badge.setStyleSheet(
                f"QLabel{{font-size: 24px; background: {styles.badge_bg()}; padding: 6px; border-radius: 6px;}}"
            )
            badge.setFixedSize(48, 48)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.move(6, 6)

        card_layout.addWidget(poster_container, 0, Qt.AlignmentFlag.AlignHCenter)
        
        # Meta + actions (below poster); title lives on poster overlay
        info_container = QWidget()
        info_container.setObjectName("profileInfoPanel")
        info_container.setFixedWidth(poster_size.width())
        info_container.setStyleSheet(styles.info_panel_stylesheet("profileInfoPanel", radius=10))
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(8, 6, 8, 8)
        info_layout.setSpacing(4)
        
        # Info text (compressed)
        info_text = CaptionLabel()
        info_text.setStyleSheet(f"CaptionLabel{{font-size: 10px; color:{styles.text_secondary()};}}")
        info_lines = [last_backup_label(profile, self, self.config, date_fmt="%Y-%m-%d")]
        
        info_text.setText(" | ".join(info_lines))
        info_layout.addWidget(info_text)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 6, 0, 0)
        actions_layout.setSpacing(6)

        edit_btn = PushButton("Edit")
        edit_btn.setFixedWidth(68)
        edit_btn.setFixedHeight(30)
        edit_btn.clicked.connect(lambda checked, pid=profile_id: self._edit_profile(pid))

        verify_btn = PushButton("Verify")
        verify_btn.setFixedWidth(68)
        verify_btn.setFixedHeight(30)
        verify_btn.clicked.connect(lambda checked, pid=profile_id: self._verify_profile(pid))

        delete_btn = PushButton("Delete")
        delete_btn.setFixedWidth(68)
        delete_btn.setFixedHeight(30)
        delete_btn.clicked.connect(lambda checked, pid=profile_id: self._delete_profile(pid))

        actions_layout.addWidget(edit_btn)
        actions_layout.addWidget(verify_btn)
        actions_layout.addWidget(delete_btn)
        actions_layout.addStretch()
        info_layout.addLayout(actions_layout)
        
        card_layout.addWidget(info_container, 0, Qt.AlignmentFlag.AlignHCenter)
        
        return card

    def refresh_posters(self, plugin_game_id: str | None = None) -> None:
        """Refresh card posters when plugin assets finish downloading."""

        mode = self.profiles_view_toggle.currentText()
        if not (mode or "").lower().startswith("c"):
            return
        for i in range(self.profiles_card_list.count()):
            item = self.profiles_card_list.item(i)
            if item is None:
                continue
            profile_id = item.data(Qt.ItemDataRole.UserRole)
            profile = self.config.games.get(profile_id)
            if not profile:
                continue
            card = self.profiles_card_list.itemWidget(item)
            if card is not None:
                self._posters.apply_to_card(
                    card,
                    profile,
                    self._CARD_POSTER_SIZE,
                    allow_placeholder=not self._posters.expects_download(profile),
                )

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
                    f"Added profile: {_profile_display_name(editor.profile, self)}",
                    parent=toast_parent(self)
                )
            except Exception:
                pass
            try:
                self.profiles_changed.emit()
            except Exception:
                pass
            
    def _on_profiles_table_search(self, text: str):
        """Filter rows in the Profiles Management table and cards by name (case-insensitive)."""
        t = (text or "").strip().lower()
        try:
            # Filter table rows
            for row in range(self.profiles_table.rowCount()):
                name_item = self.profiles_table.item(row, 0)
                if not name_item:
                    self.profiles_table.setRowHidden(row, False)
                    continue
                name = (name_item.text() or "")
                match = (not t) or (t in name.lower())
                self.profiles_table.setRowHidden(row, not match)
            
            # Filter card list items
            for i in range(self.profiles_card_list.count()):
                item = self.profiles_card_list.item(i)
                if not item:
                    continue
                profile_id = item.data(Qt.ItemDataRole.UserRole)
                name = None
                if profile_id:
                    profile = self.config.games.get(profile_id)
                    if profile:
                        name = _profile_display_name(profile, self)
                if not name:
                    name = ""
                visible = (not t) or (t in name.lower())
                item.setHidden(not visible)
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

    def _verify_profile(self, profile_id: str) -> None:
        profile = self.config.games.get(profile_id)
        if not profile:
            return
        plug = resolve_plugin_for_profile(profile, self)
        try:
            report = verify_save_locations_report(profile, plug)
            text = format_verify_report_text(report)
        except Exception as ex:
            InfoBar.error(
                "Verify Failed",
                str(ex),
                parent=toast_parent(self),
            )
            return
        styles = AdaptiveThemeStyles()
        dlg = QDialog(self.window() or self)
        dlg.setObjectName("verifyReportDialog")
        dlg.setStyleSheet(styles.verify_report_dialog_stylesheet("verifyReportDialog"))
        dlg.setWindowTitle(f"Verify — {_profile_display_name(profile, self)}")
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        edit = PlainTextEdit(dlg)
        edit.setReadOnly(True)
        edit.setPlainText(text)
        edit.setStyleSheet(styles.verify_report_plain_text_stylesheet())
        lay.addWidget(edit)
        close_btn = PushButton("Close")
        close_btn.setFixedHeight(36)
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    def _delete_profile(self, profile_id):
        """Delete profile."""
        profile = self.config.games.get(profile_id)
        if profile:
            if confirm_action(self, "Delete Profile", f"Are you sure you want to delete '{_profile_display_name(profile, self)}'?"):
                del self.config.games[profile_id]
                self.config.save_config()
                self._load_profiles()
                # Clear any lingering table selection
                try:
                    sel_model = self.profiles_table.selectionModel()
                    if sel_model:
                        sel_model.clearSelection()
                except Exception:
                    pass
                try:
                    self.profiles_changed.emit()
                except Exception:
                    pass

    def set_developer_mode(self, enabled: bool) -> None:
        set_dev_widgets_visible(enabled, (self.dev_refresh_btn,))

    def _dev_refresh(self) -> None:
        root = self.window()
        fn = getattr(root, "developer_refresh", None)
        if callable(fn):
            fn("profiles")

