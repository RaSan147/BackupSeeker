from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QByteArray, QTimer, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
	QApplication,
	QFileDialog,
	QHBoxLayout,
	QVBoxLayout,
	QWidget,
)

from qfluentwidgets import (
	CaptionLabel,
	ComboBox,
	FluentWindow,
	InfoBar,
	NavigationItemPosition,
	PushButton,
	SimpleCardWidget,
	StrongBodyLabel,
	SwitchButton,
	FluentIcon as FIF,
	setTheme,
	Theme,
)
from BackupSeeker import GameProfile

from ..core import ConfigManager
from ..developer_mode import apply_log_verbosity, developer_mode_status_text, is_developer_mode, set_dev_widgets_visible
from ..fluent_window import toast_parent
from ..plugin_manager import PluginManager
from ..plugin_hot_reload import PluginHotReloader
from ..ui_shared import open_path_in_explorer

from .poster_refresh import PosterRefreshCoordinator
from .library_page import ModernLibraryInterface
from .store_page import ModernGameStoreInterface
from .profile_detail_page import ModernGameProfileInterface


class ModernBackupSeekerWindow(FluentWindow):
    """Main Window - Clean Fluent layout with Library, Game Store, and Profile views."""

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

        self._setup_sub_interfaces()
        self._setup_window()
        self._connect_signals()
        self._apply_developer_mode()
        self._apply_theme(self.config.theme or "dark")
        self._restore_or_init_geometry()
        self._poster_refresh.kick_loads(self.config.games)

    @property
    def navigation(self):
        """Compatibility alias for navigationInterface."""
        return self.navigationInterface

    @property
    def content_widget(self):
        """Compatibility alias for stackedWidget."""
        return self.stackedWidget

    def _setup_window(self):
        """Setup window metadata and navigation constraints."""
        self.setWindowTitle("BackupSeeker")
        self.setWindowIcon(FIF.SAVE.icon())
        self.setMinimumSize(1100, 700)
        self.navigationInterface.setReturnButtonVisible(False)
        self.navigationInterface.setExpandWidth(220)
        self.navigationInterface.setMinimumExpandWidth(800)
        self.widgetLayout.setContentsMargins(0, 48, 0, 0)

    def _restore_or_init_geometry(self):
        """Restore saved window geometry or apply default launch size and position."""
        restored = False
        if getattr(self.config, "window_geometry", None):
            try:
                ba = QByteArray.fromHex(self.config.window_geometry.encode("ascii"))
                restored = bool(self.restoreGeometry(ba))
            except Exception:
                restored = False

        if not restored or self.width() < 1100 or self.height() < 700:
            self.resize(1280, 820)
            self.center()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            if self.width() < 1100 or self.height() < 700:
                self._restore_or_init_geometry()

            self._ensure_within_screen()
            QTimer.singleShot(50, lambda: self._ensure_within_screen())
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            self.config.window_geometry = self.saveGeometry().toHex().data().decode("ascii")
            self.config.save_config()
        except Exception:
            pass
        super().closeEvent(event)

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

    def _setup_sub_interfaces(self):
        """Setup Library, Game Store, Game Profile, and Settings."""
        # Primary Interfaces
        self.library_interface = ModernLibraryInterface(
            self.config, self.plugin_manager, self._poster_refresh, parent=self
        )
        self.library_interface.setObjectName("libraryInterface")
        self.addSubInterface(
            self.library_interface,
            FIF.APPLICATION,
            "Library",
        )

        self.store_interface = ModernGameStoreInterface(
            self.config, self.plugin_manager, self._poster_refresh, parent=self
        )
        self.store_interface.setObjectName("storeInterface")
        self.addSubInterface(
            self.store_interface,
            FIF.MARKET,
            "Game Store",
        )

        self.profile_interface = ModernGameProfileInterface(
            self.config, self.plugin_manager, self._poster_refresh, parent=self
        )
        self.profile_interface.setObjectName("profileInterface")
        self.stackedWidget.addWidget(self.profile_interface)

        self.settings_interface = self._create_settings_interface()
        self.settings_interface.setObjectName("settingsInterface")
        self.addSubInterface(
            self.settings_interface,
            FIF.SETTING,
            "Settings",
            position=NavigationItemPosition.BOTTOM,
        )

    def _create_settings_interface(self):
        """Create settings page."""
        widget = QWidget()
        widget.setObjectName("settingsWidget")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title_label = StrongBodyLabel("Settings")
        title_label.setStyleSheet("StrongBodyLabel { font-size: 24px; font-weight: bold; background: transparent; }")
        layout.addWidget(title_label)

        # Theme selector card
        theme_card = SimpleCardWidget(widget)
        t_layout = QVBoxLayout(theme_card)
        t_layout.setContentsMargins(16, 16, 16, 16)
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
        storage_card = SimpleCardWidget(widget)
        s_layout = QVBoxLayout(storage_card)
        s_layout.setContentsMargins(16, 16, 16, 16)
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
        dev_card = SimpleCardWidget(widget)
        d_layout = QVBoxLayout(dev_card)
        d_layout.setContentsMargins(16, 16, 16, 16)
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
        key_map = {
            "library": self.library_interface,
            "store": self.store_interface,
            "profile": self.profile_interface,
            "settings": self.settings_interface,
        }
        target = key_map.get(key)
        if target is not None:
            self.switchTo(target)
            if key in ("library", "store", "settings"):
                self.navigationInterface.setCurrentItem(target.objectName())
        
    def open_game_profile(self, profile: GameProfile, source: str = "library"):
        """Navigate to the Game Profile view."""
        self.profile_interface.set_profile(profile, source_view=source)
        self.switchTo(self.profile_interface)

    def back_from_game_profile(self):
        """Return to the source view from profile."""
        target_name = getattr(self.profile_interface, "source_view", "library")
        target = self.store_interface if target_name == "store" else self.library_interface
        self.switchTo(target)
        self.navigationInterface.setCurrentItem(target.objectName())

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

    def _apply_developer_mode() -> None:
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
        is_dark = (theme_name or "dark").lower() != "light"
        if is_dark:
            setTheme(Theme.DARK)
            self.setCustomBackgroundColor("#12131a", "#12131a")
        else:
            setTheme(Theme.LIGHT)
            self.setCustomBackgroundColor("#f4f5f9", "#f4f5f9")

        if hasattr(self, "library_interface") and hasattr(self.library_interface, "reload"):
            self.library_interface.reload()
        if hasattr(self, "store_interface") and hasattr(self.store_interface, "reload"):
            self.store_interface.reload()

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
