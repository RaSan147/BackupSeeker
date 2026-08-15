from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
	QApplication,
	QFileDialog,
	QHBoxLayout,
	QVBoxLayout,
	QWidget,
	QSizePolicy,
)

from qframelesswindow import AcrylicWindow
from qfluentwidgets import (
	BodyLabel,
	CaptionLabel,
	ComboBox,
	InfoBar,
	PushButton,
	StrongBodyLabel,
	SwitchButton,
	FluentIcon as FIF,
	setTheme,
	Theme,
)

from ..core import ConfigManager, log_and_reraise, run_backup
from ..developer_mode import apply_log_verbosity, developer_mode_status_text, is_developer_mode, set_dev_widgets_visible
from ..modern_widgets import ModernTitleBar, ModernNavigationInterface
from ..fluent_window import resolve_plugin_for_profile, toast_parent
from ..plugin_manager import PluginManager, format_load_report_summary
from ..plugin_hot_reload import PluginHotReloader
from ..plugin_runtime import PluginHookError, format_plugin_hook_error, run_plugin_hook
from ..ui_helpers import is_app_dark
from ..ui_shared import (
	ensure_plugin_restore_inputs,
	open_path_in_explorer,
	prompt_plugin_primary_path_fix,
)

from .poster_refresh import PosterRefreshCoordinator
from .library_page import ModernLibraryInterface
from .store_page import ModernGameStoreInterface
from .profile_detail_page import ModernGameProfileInterface
from .restore_dialog import RestoreBackupDialog
from .styles import AdaptiveThemeStyles


class ModernBackupSeekerWindow(AcrylicWindow):
    """Main Window - Clean, bold Hydra-style layout with Library, Game Store, and Profile views."""

    def _apply_acrylic_frameless_flags_and_effects(self) -> None:
        if sys.platform != "win32":
            return
        try:
            from qframelesswindow.utils import win32_utils as win_utils

            stay_on_top = (
                Qt.WindowType.WindowStaysOnTopHint
                if self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
                else Qt.WindowType(0)
            )

            if win_utils.isWin7():
                self.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.WindowMinMaxButtonsHint
                    | stay_on_top
                )
            else:
                self.setWindowFlags(
                    Qt.WindowType.Window
                    | Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.NoTitleBarBackgroundHint
                    | stay_on_top
                )

            wid = self.winId()
            if win_utils.isWin7():
                self.windowEffect.addShadowEffect(wid)
            else:
                if win_utils.isGreaterEqualWin11():
                    self.windowEffect.addShadowEffect(wid)
        except Exception:
            logging.getLogger("BackupSeeker.ui_fluent").exception(
                "Failed to apply frameless window flags"
            )

    def updateFrameless(self):
        self._apply_acrylic_frameless_flags_and_effects()

    def __init__(self):
        # Load config FIRST
        self.config = ConfigManager()
        super().__init__()
        
        # Initialize plugin manager
        original_level = logging.getLogger('BackupSeeker.plugin_manager').level
        logging.getLogger('BackupSeeker.plugin_manager').setLevel(logging.ERROR)
        self.plugin_manager = PluginManager(self.config.app_dir)
        logging.getLogger('BackupSeeker.plugin_manager').setLevel(original_level)
        self._poster_refresh = PosterRefreshCoordinator(self.plugin_manager)
        self._plugin_hot = PluginHotReloader(self.plugin_manager)
        self._plugin_hot.reload_finished.connect(self._on_plugins_hot_reload)
        self.plugin_manager.on_visual_assets_ready = self._poster_refresh.on_assets_ready
        self.config.sync_plugin_versions_from(self.plugin_manager)
        self.config.save_config()

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._apply_developer_mode()
        self._apply_theme(self.config.theme or "dark")
        self._poster_refresh.kick_loads(self.config.games)
        
    def _setup_window(self):
        """Setup window geometry and title bar."""
        self.setTitleBar(ModernTitleBar(self))
        self.setWindowTitle("")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 820)
        self.center()

        # Solid background styling (Hydra aesthetic)
        is_dark = (self.config.theme or "dark").lower() != "light"
        bg_color = "#12131a" if is_dark else "#f4f5f9"
        self.setStyleSheet(f"ModernBackupSeekerWindow {{ background-color: {bg_color}; }}")

    def showEvent(self, event):
        super().showEvent(event)
        tb = self.titleBar
        if tb is not None:
            QTimer.singleShot(50, lambda: tb.raise_())
            tb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            tb.setMouseTracking(True)

        try:
            QTimer.singleShot(0, self._apply_acrylic_frameless_flags_and_effects)
            QTimer.singleShot(150, self._apply_acrylic_frameless_flags_and_effects)
        except Exception:
            pass

        try:
            self._ensure_within_screen()
            QTimer.singleShot(50, lambda: self._ensure_within_screen())
        except Exception:
            pass

    def center(self):
        """Center window on screen."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        avail = screen.availableGeometry()
        try:
            geom = self.frameGeometry()
        except Exception:
            geom = self.geometry()

        w = geom.width() or self.width() or self.minimumWidth() or 1100
        h = geom.height() or self.height() or self.minimumHeight() or 700

        x = avail.left() + max(0, (avail.width() - w) // 2)
        y = avail.top() + max(0, (avail.height() - h) // 2)

        x = max(avail.left(), min(x, avail.right() - w))
        y = max(avail.top(), min(y, avail.bottom() - h))

        self.move(x, y)

    def _ensure_within_screen(self):
        """Keep window fully visible on screen."""
        try:
            ws = self.windowState()
            if (ws & Qt.WindowState.WindowMaximized) or (ws & Qt.WindowState.WindowFullScreen):
                return
            geom = None
            try:
                geom = self.frameGeometry()
            except Exception:
                geom = self.geometry()

            center_pt = geom.center() if geom is not None else None
            screen = None
            if center_pt is not None:
                try:
                    screen = QGuiApplication.screenAt(center_pt)
                except Exception:
                    screen = None
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            if screen is None:
                return

            avail = screen.availableGeometry()
            try:
                geom = self.frameGeometry()
            except Exception:
                geom = self.geometry()

            w = geom.width()
            h = geom.height()

            if w > avail.width() or h > avail.height():
                mw = self.minimumWidth()
                mh = self.minimumHeight()
                new_w = max(mw, min(w, avail.width()))
                new_h = max(mh, min(h, avail.height()))
                try:
                    self.resize(new_w, new_h)
                except Exception:
                    pass
                try:
                    geom = self.frameGeometry()
                    w = geom.width()
                    h = geom.height()
                except Exception:
                    w = self.width()
                    h = self.height()

            cur_x = geom.left()
            cur_y = geom.top()
            x = max(avail.left(), min(cur_x, avail.right() - w))
            y = max(avail.top(), min(cur_y, avail.bottom() - h))

            if x != cur_x or y != cur_y:
                try:
                    self.move(x, y)
                except Exception:
                    pass
        except Exception:
            pass
        
    def _setup_ui(self):
        """Setup UI with Library, Game Store, Game Profile, and Settings."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Full-width spacer matching title bar height
        title_bar = self.titleBar
        title_height = title_bar.sizeHint().height() if title_bar is not None else 45
        full_top_spacer = QWidget()
        full_top_spacer.setFixedHeight(title_height)
        full_top_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outer_layout.addWidget(full_top_spacer)

        # Main horizontal layout
        main_h_layout = QHBoxLayout()
        main_h_layout.setContentsMargins(0, 0, 0, 0)
        main_h_layout.setSpacing(0)

        # Navigation sidebar
        self.navigation = ModernNavigationInterface(self)
        self.navigation.setExpandWidth(220)
        self.navigation.setMinimumExpandWidth(800)
        is_dark = (self.config.theme or "dark").lower() != "light"
        nav_bg = "#181a24" if is_dark else "#ffffff"
        self.navigation.setStyleSheet(f"ModernNavigationInterface {{ background-color: {nav_bg}; border-right: 1px solid {'#26293b' if is_dark else '#e0e3ed'}; }}")

        # Content area
        self.content_widget = QWidget()
        self.content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_bg = "#12131a" if is_dark else "#f4f5f9"
        self.content_widget.setStyleSheet(f"QWidget {{ background-color: {content_bg}; }}")
        self.stacked_layout = QVBoxLayout(self.content_widget)
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)

        # Primary Interfaces
        self.library_interface = ModernLibraryInterface(
            self.config, self.plugin_manager, self._poster_refresh, parent=self
        )
        self.store_interface = ModernGameStoreInterface(
            self.config, self.plugin_manager, self._poster_refresh, parent=self
        )
        self.profile_interface = ModernGameProfileInterface(
            self.config, self.plugin_manager, self._poster_refresh, parent=self
        )
        self.settings_interface = self._create_settings_interface()

        # Add to stacked layout
        self.stacked_layout.addWidget(self.library_interface)
        self.stacked_layout.addWidget(self.store_interface)
        self.stacked_layout.addWidget(self.profile_interface)
        self.stacked_layout.addWidget(self.settings_interface)

        # Hide all except Library by default
        self.library_interface.show()
        self.store_interface.hide()
        self.profile_interface.hide()
        self.settings_interface.hide()

        # Setup navigation items
        self._setup_navigation()

        main_h_layout.addWidget(self.navigation)
        main_h_layout.addWidget(self.content_widget)
        outer_layout.addLayout(main_h_layout)
        
    def _setup_navigation(self):
        """Setup 3-item clean navigation sidebar."""
        self.navigation.addItem(
            routeKey="library",
            icon=FIF.APPLICATION,
            text="Library",
            onClick=lambda: self._show_interface("library")
        )
        
        self.navigation.addItem(
            routeKey="store", 
            icon=FIF.MARKET,
            text="Game Store",
            onClick=lambda: self._show_interface("store")
        )
        
        self.navigation.addItem(
            routeKey="settings",
            icon=FIF.SETTING,
            text="Settings",
            onClick=lambda: self._show_interface("settings")
        )
        
        self.navigation.setCurrentItem("library")
        
    def _create_settings_interface(self):
        """Create settings page."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title_label = StrongBodyLabel("Settings")
        title_label.setStyleSheet("StrongBodyLabel { font-size: 24px; font-weight: bold; }")
        layout.addWidget(title_label)

        # Theme selector card
        theme_card = QWidget()
        theme_card.setStyleSheet("QWidget { background-color: #181a24; border: 1px solid #2b2e42; border-radius: 10px; padding: 16px; }")
        t_layout = QVBoxLayout(theme_card)
        t_layout.setSpacing(8)
        t_layout.addWidget(StrongBodyLabel("App Theme"))
        t_layout.addWidget(CaptionLabel("Choose between sleek dark mode or light mode appearance."))

        theme_row = QHBoxLayout()
        self.theme_combo = ComboBox()
        self.theme_combo.addItem("Dark")
        self.theme_combo.addItem("Light")
        self.theme_combo.addItem("System")
        current = (self.config.theme or "dark").lower()
        if current == "light":
            self.theme_combo.setCurrentText("Light")
        elif current == "system":
            self.theme_combo.setCurrentText("System")
        else:
            self.theme_combo.setCurrentText("Dark")
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        t_layout.addLayout(theme_row)
        layout.addWidget(theme_card)

        # Storage options card
        storage_card = QWidget()
        storage_card.setStyleSheet("QWidget { background-color: #181a24; border: 1px solid #2b2e42; border-radius: 10px; padding: 16px; }")
        s_layout = QVBoxLayout(storage_card)
        s_layout.setSpacing(8)
        s_layout.addWidget(StrongBodyLabel("Backup Storage Location"))
        s_layout.addWidget(CaptionLabel("Configure where game save backup zip files are stored on disk."))

        storage_row = QHBoxLayout()
        self.use_cwd_btn = PushButton(FIF.FOLDER, "Use Workspace (./backups)")
        self.use_cwd_btn.clicked.connect(self._set_backup_cwd)
        storage_row.addWidget(self.use_cwd_btn)

        self.choose_fixed_btn = PushButton(FIF.FOLDER_ADD, "Choose Custom Folder...")
        self.choose_fixed_btn.clicked.connect(self._choose_fixed_location)
        storage_row.addWidget(self.choose_fixed_btn)

        self.open_storage_btn = PushButton(FIF.FOLDER, "Open Folder")
        self.open_storage_btn.clicked.connect(self._open_backup_root)
        storage_row.addWidget(self.open_storage_btn)
        storage_row.addStretch()
        s_layout.addLayout(storage_row)

        self.root_label = CaptionLabel(f"Current Path: {self.config.backup_root}")
        self.root_label.setStyleSheet("CaptionLabel { color: #858b9c; font-family: 'Consolas', monospace; }")
        s_layout.addWidget(self.root_label)

        layout.addWidget(storage_card)

        # Developer Mode card
        dev_card = QWidget()
        dev_card.setStyleSheet("QWidget { background-color: #181a24; border: 1px solid #2b2e42; border-radius: 10px; padding: 16px; }")
        d_layout = QVBoxLayout(dev_card)
        d_layout.setSpacing(8)

        dev_row = QHBoxLayout()
        dev_row.addWidget(StrongBodyLabel("Developer Mode"))
        dev_row.addStretch()
        self.dev_mode_switch = SwitchButton(self)
        self.dev_mode_switch.setChecked(is_developer_mode(self.config))
        self.dev_mode_switch.checkedChanged.connect(self._on_developer_mode_changed)
        dev_row.addWidget(self.dev_mode_switch)
        d_layout.addLayout(dev_row)

        d_layout.addWidget(
            CaptionLabel(
                "Enables plugin hot-reload, detailed diagnostics, and manual refresh triggers."
            )
        )

        self._dev_status_label = CaptionLabel("")
        d_layout.addWidget(self._dev_status_label)

        dev_actions = QHBoxLayout()
        self.dev_reload_plugins_btn = PushButton(FIF.SYNC, "Reload plugins")
        self.dev_reload_plugins_btn.clicked.connect(lambda: self.developer_refresh("plugins"))
        dev_actions.addWidget(self.dev_reload_plugins_btn)

        self.dev_reload_config_btn = PushButton(FIF.DOCUMENT, "Reload config")
        self.dev_reload_config_btn.clicked.connect(lambda: self.developer_refresh("config"))
        dev_actions.addWidget(self.dev_reload_config_btn)

        self.dev_refresh_all_btn = PushButton(FIF.UPDATE, "Refresh all UI")
        self.dev_refresh_all_btn.clicked.connect(lambda: self.developer_refresh("all"))
        dev_actions.addWidget(self.dev_refresh_all_btn)
        dev_actions.addStretch()
        d_layout.addLayout(dev_actions)

        self._dev_action_widgets = (
            self._dev_status_label,
            self.dev_reload_plugins_btn,
            self.dev_reload_config_btn,
            self.dev_refresh_all_btn,
        )

        layout.addWidget(dev_card)
        layout.addStretch()
        return widget
        
    def _show_interface(self, key: str):
        """Switch active interface."""
        interfaces = {
            "library": self.library_interface,
            "store": self.store_interface,
            "profile": self.profile_interface,
            "settings": self.settings_interface,
        }

        for k, widget in interfaces.items():
            widget.setVisible(k == key)

        if key in ("library", "store", "settings"):
            self.navigation.setCurrentItem(key)
        
    def open_game_profile(self, profile: GameProfile, source: str = "library"):
        """Navigate to the Game Profile view."""
        self.profile_interface.set_profile(profile, source_view=source)
        self._show_interface("profile")

    def back_from_game_profile(self):
        """Return to the source view from profile."""
        target = getattr(self.profile_interface, "source_view", "library")
        self._show_interface(target)

    def _connect_signals(self):
        """Connect signals across all pages."""
        # Library signals
        self.library_interface.game_profile_requested.connect(lambda prof: self.open_game_profile(prof, source="library"))
        self.library_interface.profiles_changed.connect(self._on_profiles_changed)
        self.library_interface.navigate_to_store_requested.connect(lambda: self._show_interface("store"))

        # Store signals
        self.store_interface.game_profile_requested.connect(lambda prof: self.open_game_profile(prof, source="store"))
        self.store_interface.profiles_changed.connect(self._on_profiles_changed)

        # Profile signals
        self.profile_interface.back_requested.connect(self.back_from_game_profile)
        self.profile_interface.profiles_changed.connect(self._on_profiles_changed)
        self.profile_interface.backup_requested.connect(self._on_profiles_changed)

    def _on_profiles_changed(self):
        """Callback invoked when profiles are added/edited/deleted."""
        self.library_interface.reload()
        self.store_interface.reload()
        self._poster_refresh.kick_loads(self.config.games)

    def _on_developer_mode_changed(self, enabled: bool) -> None:
        self.config.developer_mode = bool(enabled)
        self.config.save_config()
        self._apply_developer_mode()
        InfoBar.info(
            "Developer mode",
            "Enabled — hot reload and refresh controls are active."
            if enabled
            else "Disabled — hot reload and verbose diagnostics are off.",
            parent=toast_parent(self),
            duration=5000,
        )

    def _apply_developer_mode(self) -> None:
        """Sync hot reload, logging verbosity, and dev-only UI widgets."""
        enabled = is_developer_mode(self.config)
        apply_log_verbosity(enabled=enabled)
        if enabled:
            self._plugin_hot.start()
        else:
            self._plugin_hot.stop()

        status = developer_mode_status_text(self.config)
        if hasattr(self, "_dev_status_label"):
            self._dev_status_label.setText(status)
        if hasattr(self, "dev_mode_switch"):
            self.dev_mode_switch.blockSignals(True)
            self.dev_mode_switch.setChecked(enabled)
            self.dev_mode_switch.blockSignals(False)
        if hasattr(self, "_dev_action_widgets"):
            set_dev_widgets_visible(enabled, self._dev_action_widgets)

        if hasattr(self.store_interface, "reload_btn"):
            self.store_interface.reload_btn.setVisible(enabled)

    def developer_refresh(self, scope: str) -> None:
        """Manual refresh entry points used by developer-mode toolbar buttons."""
        scope = (scope or "all").strip().lower()
        logging.getLogger("BackupSeeker.ui_fluent").info("Developer refresh: %s", scope)

        if scope in ("config", "all"):
            try:
                self.config.load_config()
                self.config.update_backup_root()
                if hasattr(self, "root_label"):
                    self.root_label.setText(f"Current Path: {self.config.backup_root}")
            except Exception:
                logging.getLogger("BackupSeeker.ui_fluent").exception("Reload config failed")
                InfoBar.error("Config reload failed", "See logs for details.", parent=toast_parent(self))
                return

        if scope in ("plugins", "all"):
            self._plugin_hot.reload_now(reason=f"developer:{scope}")
            if scope == "plugins":
                return

        if scope in ("library", "store", "all"):
            self.config.sync_plugin_versions_from(self.plugin_manager)
            self.library_interface.reload()
            self.store_interface.reload()
            self._poster_refresh.kick_loads(self.config.games)

        InfoBar.success(
            "Refreshed",
            f"UI refreshed ({scope}).",
            parent=toast_parent(self),
            duration=3000,
        )

    def _on_plugins_hot_reload(self, report) -> None:
        """Refresh live UI after plugin files change on disk or manual reload."""
        self.config.sync_plugin_versions_from(self.plugin_manager)
        self.config.save_config()
        self.library_interface.reload()
        self.store_interface.reload()
        self._poster_refresh.kick_loads(self.config.games)
        
    def _apply_theme(self, theme_name: str):
        """Apply dark/light theme."""
        if (theme_name or "").lower() == "light":
            setTheme(Theme.LIGHT)
            self.setStyleSheet("ModernBackupSeekerWindow { background-color: #f4f5f9; }")
            if hasattr(self, "navigation"):
                self.navigation.setStyleSheet("ModernNavigationInterface { background-color: #ffffff; border-right: 1px solid #e0e3ed; }")
            if hasattr(self, "content_widget"):
                self.content_widget.setStyleSheet("QWidget { background-color: #f4f5f9; }")
        else:
            setTheme(Theme.DARK)
            self.setStyleSheet("ModernBackupSeekerWindow { background-color: #12131a; }")
            if hasattr(self, "navigation"):
                self.navigation.setStyleSheet("ModernNavigationInterface { background-color: #181a24; border-right: 1px solid #26293b; }")
            if hasattr(self, "content_widget"):
                self.content_widget.setStyleSheet("QWidget { background-color: #12131a; }")

        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def _on_theme_changed(self, text: str):
        val = (text or "").strip().lower()
        if val == "light":
            self.config.theme = "light"
        elif val == "system":
            self.config.theme = "system"
        else:
            self.config.theme = "dark"

        try:
            self.config.save_config()
            self._apply_theme(self.config.theme)
            InfoBar.success(
                title="Theme Updated",
                content=f"Theme set to {text}.",
                parent=toast_parent(self),
                duration=2500,
            )
        except Exception as e:
            InfoBar.warning("Theme Save Failed", str(e), parent=toast_parent(self))

    def _set_backup_cwd(self):
        self.config.set_backup_mode_cwd()
        try:
            self.root_label.setText(f"Current Path: {self.config.backup_root}")
            InfoBar.success("Storage Updated", "Backups will be saved in workspace ./backups folder.", parent=toast_parent(self))
        except Exception:
            pass

    def _choose_fixed_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Storage Folder")
        if folder:
            self.config.set_backup_mode_fixed(folder)
            try:
                self.root_label.setText(f"Current Path: {self.config.backup_root}")
                InfoBar.success("Storage Updated", f"Backups will be saved to: {folder}", parent=toast_parent(self))
            except Exception:
                pass

    def _open_backup_root(self):
        try:
            path = self.config.backup_root
            path.mkdir(parents=True, exist_ok=True)
            open_path_in_explorer(path)
        except Exception as e:
            InfoBar.error("Open Failed", str(e), parent=toast_parent(self))
