from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    SearchLineEdit,
    SegmentedWidget,
    SimpleCardWidget,
    SingleDirectionScrollArea,
    StrongBodyLabel,
    SubtitleLabel,
    TransparentPushButton,
)

from ..core import (
    ConfigManager,
    GameProfile,
    PathUtils,
    verify_save_locations_report,
)
from ..fluent_window import resolve_plugin_for_profile, toast_parent
from ..ui_shared import open_path_in_explorer
from .helpers import format_verify_report_text
from .styles import AdaptiveThemeStyles


class VerifySaveDialog(QDialog):
    """Modern, scrollable verification dialog for game save locations and detection."""

    def __init__(
        self,
        profile: GameProfile,
        plugin: object | None = None,
        config: ConfigManager | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.profile = profile
        self.config = config
        self._parent_widget = parent
        self.plugin = plugin or resolve_plugin_for_profile(profile, parent)
        self._disp = profile.resolved_name(self.plugin)

        self._theme = AdaptiveThemeStyles()
        self.setObjectName("verifySaveDialog")
        self.setWindowTitle(f"Verify Saves — {self._disp}")
        self.setStyleSheet(self._theme.verify_report_dialog_stylesheet("verifySaveDialog"))

        # Setup initial sizing and constrain maximum height to screen
        self.resize(840, 620)
        self.setMinimumSize(640, 460)
        screen = QGuiApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            self.setMaximumHeight(min(840, max(460, avail.height() - 60)))
            self.setMaximumWidth(min(1060, max(640, avail.width() - 60)))

        self._location_card_items: list[tuple[QWidget, dict[str, Any]]] = []
        self._report: dict[str, Any] = {}
        self._current_filter_tab: str = "all"

        self._setup_ui()
        self._load_report()


    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(14)

        t = self._theme.theme
        is_dark = self._theme.dark

        # ---------------------------------------------------------------------
        # 1. Header (Title, Subtitle & Overall Status Badge)
        # ---------------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        # Left: Icon & Title block
        icon_box = QFrame(self)
        icon_box.setFixedSize(42, 42)
        icon_box_bg = "#232742" if is_dark else "#e8ebfb"
        icon_box.setStyleSheet(
            f"QFrame {{ background-color: {icon_box_bg}; border-radius: 10px; border: 1px solid {t['panel_border']}; }}"
        )
        icon_box_lay = QVBoxLayout(icon_box)
        icon_box_lay.setContentsMargins(0, 0, 0, 0)
        icon_box_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_icon = QLabel(icon_box)
        header_icon.setPixmap(FIF.GAME.icon().pixmap(QSize(22, 22)))
        header_icon.setStyleSheet("background: transparent; border: none;")
        icon_box_lay.addWidget(header_icon)
        header_layout.addWidget(icon_box)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        self.title_label = SubtitleLabel(f"Save Verification: {self._disp}", self)
        self.title_label.setStyleSheet(f"color: {t['text_primary']}; font-size: 16px; font-weight: bold; background: transparent;")
        self.subtitle_label = CaptionLabel("Inspect configured save directories, detected files, and installation status.", self)
        self.subtitle_label.setStyleSheet(f"color: {t['text_muted']}; font-size: 12px; background: transparent;")
        title_vbox.addWidget(self.title_label)
        title_vbox.addWidget(self.subtitle_label)
        header_layout.addLayout(title_vbox)

        header_layout.addStretch()

        self.overall_badge = CaptionLabel("", self)
        self.overall_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.overall_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        root_layout.addLayout(header_layout)

        # ---------------------------------------------------------------------
        # 2. Metric Summary Cards (Hero Row)
        # ---------------------------------------------------------------------
        self.metrics_container = QWidget(self)
        self.metrics_container.setStyleSheet("background: transparent;")
        metrics_layout = QHBoxLayout(self.metrics_container)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(12)

        self.card_paths = self._create_metric_card(
            FIF.FOLDER, "SAVE ROOTS", "0 Configured", "0 found on disk", accent_tint="#5b6cf9"
        )
        self.card_files = self._create_metric_card(
            FIF.DOCUMENT, "SAVE FILES", "0 Files", "Matching patterns", accent_tint="#10b981"
        )
        self.card_detect = self._create_metric_card(
            FIF.GAME, "GAME DETECTION", "Checking...", "Plugin status", accent_tint="#8b5cf6"
        )

        metrics_layout.addWidget(self.card_paths)
        metrics_layout.addWidget(self.card_files)
        metrics_layout.addWidget(self.card_detect)
        root_layout.addWidget(self.metrics_container)

        # ---------------------------------------------------------------------
        # 3. Filter & Search Controls Row
        # ---------------------------------------------------------------------
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(12)

        self.segmented_filter = SegmentedWidget(self)
        self.segmented_filter.addItem("all", "All Locations")
        self.segmented_filter.addItem("found", "Found on Disk")
        self.segmented_filter.addItem("missing", "Not Found")
        self.segmented_filter.setCurrentItem("all")
        self.segmented_filter.currentItemChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.segmented_filter)

        controls_layout.addStretch()

        self.search_box = SearchLineEdit(self)
        self.search_box.setPlaceholderText("Filter by name or path...")
        self.search_box.setFixedWidth(240)
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._on_search_changed)
        controls_layout.addWidget(self.search_box)

        root_layout.addLayout(controls_layout)

        # ---------------------------------------------------------------------
        # 4. Scrollable Content Area for Locations & Registry
        # ---------------------------------------------------------------------
        self.scroll_area = SingleDirectionScrollArea(orient=Qt.Orientation.Vertical, parent=self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 4, 10, 4)
        self.scroll_layout.setSpacing(10)
        self.scroll_area.setWidget(self.scroll_content)

        root_layout.addWidget(self.scroll_area, stretch=1)

        # ---------------------------------------------------------------------
        # 5. Footer Actions
        # ---------------------------------------------------------------------
        footer_line = QFrame(self)
        footer_line.setFrameShape(QFrame.Shape.HLine)
        footer_line.setFrameShadow(QFrame.Shadow.Sunken)
        footer_line.setStyleSheet(f"background-color: {self._theme.separator()}; max-height: 1px; border: none;")
        root_layout.addWidget(footer_line)

        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)

        self.copy_report_btn = TransparentPushButton(FIF.COPY, "Copy Full Report", self)
        self.copy_report_btn.clicked.connect(self._on_copy_full_report)
        footer_layout.addWidget(self.copy_report_btn)

        footer_layout.addStretch()

        self.refresh_btn = PushButton(FIF.SYNC, "Refresh", self)
        self.refresh_btn.clicked.connect(self._load_report)
        footer_layout.addWidget(self.refresh_btn)

        self.open_first_btn = PushButton(FIF.FOLDER, "Open Save Folder", self)
        self.open_first_btn.clicked.connect(self._on_open_first_folder)
        footer_layout.addWidget(self.open_first_btn)

        self.close_btn = PrimaryPushButton("Close", self)
        self.close_btn.setFixedWidth(96)
        self.close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(self.close_btn)

        root_layout.addLayout(footer_layout)

    def _create_metric_card(
        self, icon: FIF, title: str, initial_value: str, subtext: str, accent_tint: str = "#5b6cf9"
    ) -> SimpleCardWidget:
        card = SimpleCardWidget(self)
        card.setFixedHeight(68)
        t = self._theme.theme
        is_dark = self._theme.dark
        card.setStyleSheet(
            f"SimpleCardWidget {{"
            f"  background-color: {t['bg_card']};"
            f"  border: 1px solid {t['panel_border']};"
            f"  border-radius: 10px;"
            f"}}"
        )
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        # Icon badge circle
        icon_frame = QFrame(card)
        icon_frame.setFixedSize(36, 36)
        icon_bg = f"{accent_tint}22" if is_dark else f"{accent_tint}18"
        icon_frame.setStyleSheet(
            f"QFrame {{ background-color: {icon_bg}; border-radius: 18px; border: 1px solid {accent_tint}40; }}"
        )
        if_lay = QVBoxLayout(icon_frame)
        if_lay.setContentsMargins(0, 0, 0, 0)
        if_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel(icon_frame)
        icon_lbl.setPixmap(icon.icon().pixmap(QSize(18, 18)))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        if_lay.addWidget(icon_lbl)
        lay.addWidget(icon_frame)

        vbox = QVBoxLayout()
        vbox.setSpacing(2)
        vbox.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        cap = CaptionLabel(title, card)
        cap.setStyleSheet(f"color: {t['text_muted']}; font-size: 10px; font-weight: bold; background: transparent;")
        val = StrongBodyLabel(initial_value, card)
        val.setStyleSheet(f"color: {t['text_primary']}; font-size: 14px; font-weight: bold; background: transparent;")
        sub = CaptionLabel(subtext, card)
        sub.setStyleSheet(f"color: {t['text_secondary']}; font-size: 11px; background: transparent;")

        vbox.addWidget(cap)
        vbox.addWidget(val)
        vbox.addWidget(sub)
        lay.addLayout(vbox)
        lay.addStretch()

        card._val_label = val  # type: ignore[attr-defined]
        card._sub_label = sub  # type: ignore[attr-defined]
        return card

    def _clear_scroll_layout(self):
        self._location_card_items.clear()
        while self.scroll_layout.count() > 0:
            item = self.scroll_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_sub_layout(item.layout())

    def _clear_sub_layout(self, layout):
        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_sub_layout(item.layout())

    def _load_report(self):
        """Fetch and render the latest verification report."""
        try:
            self._report = verify_save_locations_report(self.profile, self.plugin)
        except Exception as ex:
            self._report = {"locations": [], "registry": [], "plugin_is_detected": False, "error": str(ex)}

        self._render_report(self._report)

    def _render_report(self, report: dict[str, Any]):
        self._clear_scroll_layout()
        t = self._theme.theme
        is_dark = self._theme.dark

        locations = report.get("locations") or []
        registry = report.get("registry") or []
        is_detected = report.get("plugin_is_detected", False)

        total_locs = len(locations)
        existing_locs = sum(1 for loc in locations if loc.get("exists", False))
        total_files = sum(loc.get("file_count", 0) for loc in locations)
        missing_locs = total_locs - existing_locs

        # Update Metrics Cards
        self.card_paths._val_label.setText(f"{total_locs} Configured")  # type: ignore
        self.card_paths._sub_label.setText(f"{existing_locs} found on disk")  # type: ignore

        self.card_files._val_label.setText(f"{total_files} file{'s' if total_files != 1 else ''}")  # type: ignore
        if total_files > 0:
            self.card_files._sub_label.setText(f"Ready in {existing_locs} location{'s' if existing_locs != 1 else ''}")  # type: ignore
        else:
            self.card_files._sub_label.setText("No save files discovered")  # type: ignore

        if self.plugin is not None:
            detect_text = "Detected" if is_detected else "Installed / Inactive"
            detect_sub = f"Plugin: {getattr(self.plugin, 'game_id', 'custom')}"
        else:
            detect_text = "Manual Profile"
            detect_sub = "No store plugin linked"
        self.card_detect._val_label.setText(detect_text)  # type: ignore
        self.card_detect._sub_label.setText(detect_sub)  # type: ignore

        # Update Filter Tabs Labels
        self.segmented_filter.setItemText("all", f"All ({total_locs})")
        self.segmented_filter.setItemText("found", f"Found ({existing_locs})")
        self.segmented_filter.setItemText("missing", f"Missing ({missing_locs})")

        # Update Overall Badge
        if total_files > 0:
            self.overall_badge.setText(f"● Ready ({total_files} save files)")
            if is_dark:
                self.overall_badge.setStyleSheet(
                    "CaptionLabel { background-color: #143322; color: #4ade80; "
                    "border: 1px solid #1e5938; border-radius: 12px; padding: 4px 14px; font-weight: bold; font-size: 12px; }"
                )
            else:
                self.overall_badge.setStyleSheet(
                    "CaptionLabel { background-color: #eafbf0; color: #15803d; "
                    "border: 1px solid #bbf7d0; border-radius: 12px; padding: 4px 14px; font-weight: bold; font-size: 12px; }"
                )
        elif existing_locs > 0 or is_detected:
            self.overall_badge.setText("● Folders Ready (0 saves)")
            if is_dark:
                self.overall_badge.setStyleSheet(
                    "CaptionLabel { background-color: #2b2816; color: #facc15; "
                    "border: 1px solid #4d431c; border-radius: 12px; padding: 4px 14px; font-weight: bold; font-size: 12px; }"
                )
            else:
                self.overall_badge.setStyleSheet(
                    "CaptionLabel { background-color: #fefce8; color: #a16207; "
                    "border: 1px solid #fef08a; border-radius: 12px; padding: 4px 14px; font-weight: bold; font-size: 12px; }"
                )
        else:
            self.overall_badge.setText("● No Saves Located")
            if is_dark:
                self.overall_badge.setStyleSheet(
                    "CaptionLabel { background-color: #2e1c1c; color: #f87171; "
                    "border: 1px solid #572a2a; border-radius: 12px; padding: 4px 14px; font-weight: bold; font-size: 12px; }"
                )
            else:
                self.overall_badge.setStyleSheet(
                    "CaptionLabel { background-color: #fef2f2; color: #dc2626; "
                    "border: 1px solid #fecaca; border-radius: 12px; padding: 4px 14px; font-weight: bold; font-size: 12px; }"
                )

        # Enable/disable open first button based on existence
        first_existing = next((loc.get("expanded_path") for loc in locations if loc.get("exists")), None)
        self.open_first_btn.setEnabled(bool(first_existing))
        self._first_existing_path = first_existing

        # ---------------------------------------------------------------------
        # Save Locations Section
        # ---------------------------------------------------------------------
        if not locations:
            empty_card = SimpleCardWidget(self.scroll_content)
            empty_card.setStyleSheet(
                f"SimpleCardWidget {{ background-color: {t['bg_card']}; border: 1px dashed {t['panel_border']}; border-radius: 10px; }}"
            )
            empty_lay = QVBoxLayout(empty_card)
            empty_lay.setContentsMargins(20, 20, 20, 20)
            empty_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_msg = BodyLabel("No save locations are configured for this profile.", empty_card)
            empty_msg.setStyleSheet(f"color: {t['text_muted']}; font-size: 13px; background: transparent;")
            empty_lay.addWidget(empty_msg)
            self.scroll_layout.addWidget(empty_card)
        else:
            for row in locations:
                card = self._build_location_card(row, is_dark, t)
                self._location_card_items.append((card, row))
                self.scroll_layout.addWidget(card)

        # Placeholder label when search/filter has zero results
        self.no_filter_match_card = SimpleCardWidget(self.scroll_content)
        self.no_filter_match_card.setStyleSheet(
            f"SimpleCardWidget {{ background-color: {t['bg_card']}; border: 1px dashed {t['panel_border']}; border-radius: 10px; }}"
        )
        no_match_lay = QVBoxLayout(self.no_filter_match_card)
        no_match_lay.setContentsMargins(20, 20, 20, 20)
        no_match_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_match_lbl = BodyLabel("No locations match the current filter or search criteria.", self.no_filter_match_card)
        self.no_match_lbl.setStyleSheet(f"color: {t['text_muted']}; font-size: 13px; background: transparent;")
        no_match_lay.addWidget(self.no_match_lbl)
        self.scroll_layout.addWidget(self.no_filter_match_card)
        self.no_filter_match_card.setVisible(False)

        # ---------------------------------------------------------------------
        # Registry & Detection Hints Section
        # ---------------------------------------------------------------------
        if registry:
            self.scroll_layout.addSpacing(10)
            reg_header_layout = QHBoxLayout()
            reg_icon = QLabel(self.scroll_content)
            reg_icon.setPixmap(FIF.COMMAND_PROMPT.icon().pixmap(QSize(18, 18)))
            reg_icon.setStyleSheet("background: transparent; border: none;")
            reg_icon.setFixedSize(18, 18)
            reg_header_layout.addWidget(reg_icon)
            reg_title = StrongBodyLabel(f"Registry & Installation Checks ({len(registry)})", self.scroll_content)
            reg_title.setStyleSheet(f"color: {t['text_primary']}; font-size: 13px; font-weight: bold; background: transparent;")
            reg_header_layout.addWidget(reg_title)
            reg_header_layout.addStretch()
            self.scroll_layout.addLayout(reg_header_layout)

            for reg_row in registry:
                reg_card = self._build_registry_card(reg_row, is_dark, t)
                self.scroll_layout.addWidget(reg_card)

        self.scroll_layout.addStretch()
        self._apply_filter()

    def _build_location_card(self, row: dict[str, Any], is_dark: bool, t: dict[str, str]) -> SimpleCardWidget:
        card = SimpleCardWidget(self.scroll_content)
        exists = row.get("exists", False)
        file_count = row.get("file_count", 0)
        has_data = row.get("has_data", False)

        # Visual indicator border depending on status
        if has_data:
            border_qss = "border: 1px solid #1e5938; border-left: 4px solid #10b981;" if is_dark else "border: 1px solid #bbf7d0; border-left: 4px solid #10b981;"
        elif exists:
            border_qss = "border: 1px solid #4d431c; border-left: 4px solid #f59e0b;" if is_dark else "border: 1px solid #fef08a; border-left: 4px solid #f59e0b;"
        else:
            border_qss = f"border: 1px solid {t['panel_border']}; border-left: 4px solid {t['separator']};"

        card.setStyleSheet(
            f"SimpleCardWidget {{"
            f"  background-color: {t['bg_card']};"
            f"  {border_qss}"
            f"  border-radius: 8px;"
            f"}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        # Top row: Folder icon, Label, key badge, and Status pill
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        key = row.get("logical_key", "path_0")
        label = (row.get("label") or "").strip()
        disp_title = label if label and label != key else f"Save Location ({key})"

        # Small status dot or folder icon
        loc_icon = QLabel(card)
        loc_icon.setPixmap(FIF.FOLDER.icon().pixmap(QSize(16, 16)))
        loc_icon.setStyleSheet("background: transparent; border: none;")
        loc_icon.setFixedSize(16, 16)
        top_row.addWidget(loc_icon)

        title_lbl = StrongBodyLabel(disp_title, card)
        title_lbl.setStyleSheet(f"color: {t['text_primary']}; font-size: 13px; font-weight: bold; background: transparent;")
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_row.addWidget(title_lbl)

        key_badge = CaptionLabel(f"[{key}]", card)
        key_badge.setStyleSheet(
            f"background-color: {t['badge_bg']}; color: {t['text_secondary']}; "
            f"border-radius: 4px; padding: 2px 6px; font-size: 11px;"
        )
        top_row.addWidget(key_badge)

        top_row.addStretch()

        # Status badge (pill with icon)
        status_badge = CaptionLabel("", card)
        if has_data:
            status_badge.setText(f"✓ {file_count} save file{'s' if file_count != 1 else ''}")
            if is_dark:
                status_badge.setStyleSheet(
                    "background-color: #143322; color: #4ade80; border: 1px solid #1e5938; "
                    "border-radius: 10px; padding: 3px 10px; font-weight: 600; font-size: 11px;"
                )
            else:
                status_badge.setStyleSheet(
                    "background-color: #eafbf0; color: #15803d; border: 1px solid #bbf7d0; "
                    "border-radius: 10px; padding: 3px 10px; font-weight: 600; font-size: 11px;"
                )
        elif exists:
            status_badge.setText("⚠ Empty folder")
            if is_dark:
                status_badge.setStyleSheet(
                    "background-color: #2b2816; color: #facc15; border: 1px solid #4d431c; "
                    "border-radius: 10px; padding: 3px 10px; font-weight: 600; font-size: 11px;"
                )
            else:
                status_badge.setStyleSheet(
                    "background-color: #fefce8; color: #a16207; border: 1px solid #fef08a; "
                    "border-radius: 10px; padding: 3px 10px; font-weight: 600; font-size: 11px;"
                )
        else:
            status_badge.setText("✕ Not found")
            if is_dark:
                status_badge.setStyleSheet(
                    "background-color: #2b1a1a; color: #f87171; border: 1px solid #4a2424; "
                    "border-radius: 10px; padding: 3px 10px; font-weight: 600; font-size: 11px;"
                )
            else:
                status_badge.setStyleSheet(
                    "background-color: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; "
                    "border-radius: 10px; padding: 3px 10px; font-weight: 600; font-size: 11px;"
                )

        top_row.addWidget(status_badge)
        lay.addLayout(top_row)

        # Path container (Monospace styled code box)
        expanded_path = row.get("expanded_path", "")
        contracted_path = row.get("contracted_path", "")

        path_frame = QFrame(card)
        path_bg = "#161722" if is_dark else "#f4f5f9"
        path_frame.setStyleSheet(
            f"QFrame {{ background-color: {path_bg}; border: 1px solid {t['panel_border']}; border-radius: 6px; }}"
        )
        path_vbox = QVBoxLayout(path_frame)
        path_vbox.setContentsMargins(10, 8, 10, 8)
        path_vbox.setSpacing(2)

        path_lbl = BodyLabel(expanded_path or "(no path configured)", path_frame)
        path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mono_font = QFont("Consolas, Segoe UI Mono, Courier New, monospace", 9)
        path_lbl.setFont(mono_font)
        path_text_color = t['text_primary'] if exists else t['text_muted']
        path_lbl.setStyleSheet(f"color: {path_text_color}; border: none; background: transparent;")
        path_vbox.addWidget(path_lbl)

        if contracted_path and contracted_path != expanded_path:
            c_lbl = CaptionLabel(f"Pattern: {contracted_path}", path_frame)
            c_lbl.setStyleSheet(f"color: {t['text_muted']}; border: none; background: transparent; font-size: 11px;")
            path_vbox.addWidget(c_lbl)

        lay.addWidget(path_frame)

        # Actions row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        open_btn = PushButton(FIF.FOLDER, "Open Folder", card)
        open_btn.setFixedHeight(28)
        open_btn.setEnabled(exists)
        if exists:
            open_btn.clicked.connect(lambda _, p=expanded_path: open_path_in_explorer(p))
        actions_row.addWidget(open_btn)

        copy_btn = TransparentPushButton(FIF.COPY, "Copy Path", card)
        copy_btn.setFixedHeight(28)
        copy_btn.clicked.connect(lambda _, p=expanded_path: self._copy_to_clipboard(p, "Path copied to clipboard."))
        actions_row.addWidget(copy_btn)

        actions_row.addStretch()
        lay.addLayout(actions_row)

        return card

    def _build_registry_card(self, row: dict[str, Any], is_dark: bool, t: dict[str, str]) -> SimpleCardWidget:
        card = SimpleCardWidget(self.scroll_content)
        card.setStyleSheet(
            f"SimpleCardWidget {{"
            f"  background-color: {t['bg_card']};"
            f"  border: 1px solid {t['panel_border']};"
            f"  border-radius: 8px;"
            f"}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        key_path = row.get("key_path", "")
        value_name = row.get("value_name", "")
        present = row.get("present_and_valid", False)

        title_lbl = StrongBodyLabel(f"{key_path} :: {value_name}", card)
        title_lbl.setStyleSheet(f"color: {t['text_primary']}; font-size: 12px; font-weight: bold; background: transparent;")
        title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_row.addWidget(title_lbl)

        top_row.addStretch()

        badge = CaptionLabel("", card)
        if present:
            badge.setText("✓ Found & Valid")
            if is_dark:
                badge.setStyleSheet(
                    "background-color: #143322; color: #4ade80; border: 1px solid #1e5938; "
                    "border-radius: 10px; padding: 2px 8px; font-weight: 600; font-size: 11px;"
                )
            else:
                badge.setStyleSheet(
                    "background-color: #eafbf0; color: #15803d; border: 1px solid #bbf7d0; "
                    "border-radius: 10px; padding: 2px 8px; font-weight: 600; font-size: 11px;"
                )
        else:
            badge.setText("✕ Not Found")
            if is_dark:
                badge.setStyleSheet(
                    "background-color: #2b1a1a; color: #f87171; border: 1px solid #4a2424; "
                    "border-radius: 10px; padding: 2px 8px; font-weight: 600; font-size: 11px;"
                )
            else:
                badge.setStyleSheet(
                    "background-color: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; "
                    "border-radius: 10px; padding: 2px 8px; font-weight: 600; font-size: 11px;"
                )
        top_row.addWidget(badge)
        lay.addLayout(top_row)

        detail = row.get("detail", "")
        if detail:
            detail_frame = QFrame(card)
            detail_bg = "#161722" if is_dark else "#f4f5f9"
            detail_frame.setStyleSheet(
                f"QFrame {{ background-color: {detail_bg}; border: 1px solid {t['panel_border']}; border-radius: 6px; }}"
            )
            df_lay = QHBoxLayout(detail_frame)
            df_lay.setContentsMargins(10, 6, 10, 6)
            df_lay.setSpacing(8)

            detail_lbl = BodyLabel(detail, detail_frame)
            detail_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            detail_lbl.setStyleSheet(f"color: {t['text_secondary']}; font-size: 11px; background: transparent;")
            df_lay.addWidget(detail_lbl, stretch=1)

            copy_detail_btn = TransparentPushButton(FIF.COPY, "", detail_frame)
            copy_detail_btn.setFixedSize(26, 26)
            copy_detail_btn.setToolTip("Copy Value")
            copy_detail_btn.clicked.connect(lambda _, d=detail: self._copy_to_clipboard(d, "Value copied."))
            df_lay.addWidget(copy_detail_btn)

            lay.addWidget(detail_frame)

        return card

    def _on_filter_changed(self, route_key: str | None = None):
        if route_key:
            self._current_filter_tab = route_key
        self._apply_filter()

    def _on_search_changed(self, text: str):
        self._apply_filter()

    def _apply_filter(self):
        tab = self._current_filter_tab or "all"
        query = (self.search_box.text() or "").strip().lower()

        visible_count = 0
        for card, row in self._location_card_items:
            exists = bool(row.get("exists", False))
            
            # Check tab filter
            if tab == "found" and not exists:
                card.setVisible(False)
                continue
            elif tab == "missing" and exists:
                card.setVisible(False)
                continue

            # Check search query
            if query:
                title = (row.get("label") or "").lower()
                key = (row.get("logical_key") or "").lower()
                exp_path = (row.get("expanded_path") or "").lower()
                con_path = (row.get("contracted_path") or "").lower()
                if query not in title and query not in key and query not in exp_path and query not in con_path:
                    card.setVisible(False)
                    continue

            card.setVisible(True)
            visible_count += 1

        if hasattr(self, "no_filter_match_card"):
            if len(self._location_card_items) > 0 and visible_count == 0:
                self.no_filter_match_card.setVisible(True)
            else:
                self.no_filter_match_card.setVisible(False)


    def _copy_to_clipboard(self, text: str, toast_message: str = "Copied to clipboard"):
        if not text:
            return
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text)
        InfoBar.success(
            title="Copied",
            content=toast_message,
            parent=self,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=2000,
        )

    def _on_copy_full_report(self):
        text = format_verify_report_text(self._report)
        self._copy_to_clipboard(text, "Full verification report copied to clipboard.")

    def _on_open_first_folder(self):
        if getattr(self, "_first_existing_path", None):
            open_path_in_explorer(self._first_existing_path)
