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

from .backups_page import ModernBackupsInterface
from .poster_refresh import PosterRefreshCoordinator
from .dashboard import ModernDashboardInterface
from .plugins_page import ModernPluginsInterface
from .profiles_page import ModernProfilesInterface
from .restore_dialog import RestoreBackupDialog


class ModernBackupSeekerWindow(AcrylicWindow):
    """Main Window - COMPLETELY FIXED"""

    def _apply_acrylic_frameless_flags_and_effects(self) -> None:
        """AcrylicWindow.updateFrameless (qframelesswindow 0.8.x) replaces
        window flags on Qt 6.10+ with ``Window | NoTitleBarBackgroundHint``
        only, which drops ``FramelessWindowHint`` and can leave a *native*
        caption next to ``SplitTitleBar`` (duplicate window controls).

        Do not call ``AcrylicWindow.updateFrameless`` here — OR-ing flags
        after that call is unreliable on Qt 6.11. Set the combined flags in
        one ``setWindowFlags``, then mirror the library's blur/acrylic hooks.
        """
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
            self.windowEffect.enableBlurBehindWindow(wid)
            self.windowEffect.addWindowAnimation(wid)
            if win_utils.isWin7():
                self.windowEffect.addShadowEffect(wid)
                self.windowEffect.setAeroEffect(wid)
            else:
                self.windowEffect.setAcrylicEffect(wid)
                if win_utils.isGreaterEqualWin11():
                    self.windowEffect.addShadowEffect(wid)

            # Library default acrylic tint; restore app tint after flag churn.
            try:
                dark_hex = "11112299"
                light_hex = "F0F0F099"
                candidates = [dark_hex] if is_app_dark() else [light_hex]
                self._try_acrylic(candidates, debug=False)
            except Exception:
                pass
        except Exception:
            logging.getLogger("BackupSeeker.ui_fluent").exception(
                "Failed to apply frameless window flags / acrylic effects"
            )

    def updateFrameless(self):
        """Replace stock ``AcrylicWindow.updateFrameless`` (see ``_apply_…``)."""
        self._apply_acrylic_frameless_flags_and_effects()

    def __init__(self):
        # Load config FIRST
        self.config = ConfigManager()
        super().__init__()
        
        # Initialize plugin manager with minimal logging
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
        self._apply_theme(self.config.theme)
        self._poster_refresh.kick_loads(self.config.games)
        
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
        # Base AcrylicWindow defaults to 500×500; set a sane initial size so
        # launch is not tiny before the user resizes.
        self.resize(1280, 800)
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
        tb = self.titleBar
        if tb is not None:
            # Raise after a short delay to let layouts settle
            QTimer.singleShot(50, lambda: tb.raise_())
            tb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            tb.setMouseTracking(True)

        # Qt 6.11 + DWM can restore standard chrome after first paint; re-sync.
        try:
            QTimer.singleShot(0, self._apply_acrylic_frameless_flags_and_effects)
            QTimer.singleShot(150, self._apply_acrylic_frameless_flags_and_effects)
        except Exception:
            pass

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

        # Ensure the window is fully visible on the current screen. Some
        # window managers or high-DPI scaling can move parts of a frameless
        # window offscreen; clamp it here after show so the user can interact.
        try:
            # Run immediately and again after a short delay to allow any
            # layout-driven adjustments to finish.
            self._ensure_within_screen()
            QTimer.singleShot(50, lambda: self._ensure_within_screen())
        except Exception:
            pass

    def center(self):
        """Center window."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return

        # Use availableGeometry (excludes taskbars/docks) to avoid placing
        # the window under system UI or off-screen. Use frameGeometry so
        # the window frame/borders are considered when centering.
        avail = screen.availableGeometry()

        try:
            geom = self.frameGeometry()
        except Exception:
            geom = self.geometry()

        w = geom.width() or self.width() or self.minimumWidth() or 1100
        h = geom.height() or self.height() or self.minimumHeight() or 700

        x = avail.left() + max(0, (avail.width() - w) // 2)
        y = avail.top() + max(0, (avail.height() - h) // 2)

        # Clamp so the window is fully visible within the available area
        x = max(avail.left(), min(x, avail.right() - w))
        y = max(avail.top(), min(y, avail.bottom() - h))

        self.move(x, y)

    def _ensure_within_screen(self):
        """Clamp the window position (and shrink if necessary) to keep
        the window fully inside the available geometry of the screen that
        contains the window center (or the primary screen)."""
        try:
            ws = self.windowState()
            if (ws & Qt.WindowState.WindowMaximized) or (ws & Qt.WindowState.WindowFullScreen):
                return
            # Pick the screen that contains the window center if possible
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

            # Recompute geometry after any layout/resize operations
            try:
                geom = self.frameGeometry()
            except Exception:
                geom = self.geometry()

            w = geom.width()
            h = geom.height()

            # If the window is larger than the available area, shrink — but never
            # below minimumWidth/minimumHeight (otherwise launch can look "tiny").
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

            # Compute clamped top-left coordinates
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
            # Best-effort only; don't raise from UI hooks
            pass
        
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
        title_bar = self.titleBar
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
        self.dashboard = ModernDashboardInterface(
            self.config, self.plugin_manager, self._poster_refresh, parent=self
        )
        # Profiles management uses its own page (do not reuse dashboard)
        self.profiles_interface = ModernProfilesInterface(
            self.config, self._poster_refresh, parent=self
        )
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

        layout.addWidget(StrongBodyLabel("Developer"))
        dev_row = QHBoxLayout()
        self.dev_mode_switch = SwitchButton(self)
        self.dev_mode_switch.setChecked(is_developer_mode(self.config))
        self.dev_mode_switch.checkedChanged.connect(self._on_developer_mode_changed)
        dev_row.addWidget(BodyLabel("Developer mode"))
        dev_row.addStretch()
        dev_row.addWidget(self.dev_mode_switch)
        layout.addLayout(dev_row)
        layout.addWidget(
            BodyLabel(
                "Enables plugin hot-reload on save, DEBUG logging, diagnostics panels, "
                "and manual refresh buttons across the app."
            )
        )

        self._dev_status_label = BodyLabel("")
        layout.addWidget(self._dev_status_label)

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
        layout.addLayout(dev_actions)
        self._dev_action_widgets = (
            self._dev_status_label,
            self.dev_reload_plugins_btn,
            self.dev_reload_config_btn,
            self.dev_refresh_all_btn,
        )

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
        """Callback invoked when profiles are added/edited/deleted (or backups change timestamps)."""
        self.dashboard._load_profiles()
        self.profiles_interface._load_profiles()
        self.backups_interface._load_profiles()
        if self.backups_interface.current_profile is not None:
            self.backups_interface._refresh_backups()
        self.plugins_interface._load_plugins()

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

        self.dashboard.set_developer_mode(enabled)
        self.profiles_interface.set_developer_mode(enabled)
        self.backups_interface.set_developer_mode(enabled)
        self.plugins_interface.set_developer_mode(enabled)

    def developer_refresh(self, scope: str) -> None:
        """Manual refresh entry points used by developer-mode toolbar buttons."""

        scope = (scope or "all").strip().lower()
        logging.getLogger("BackupSeeker.ui_fluent").info("Developer refresh: %s", scope)

        if scope in ("config", "all"):
            try:
                self.config.load_config()
                self.config.update_backup_root()
                if hasattr(self, "root_label"):
                    self.root_label.setText(f"Storage: {self.config.backup_root}")
            except Exception:
                logging.getLogger("BackupSeeker.ui_fluent").exception("Reload config failed")
                InfoBar.error("Config reload failed", "See logs for details.", parent=toast_parent(self))
                return

        if scope in ("plugins", "all"):
            self._plugin_hot.reload_now(reason=f"developer:{scope}")
            if scope == "plugins":
                return

        if scope == "backups":
            if self.backups_interface.current_profile is not None:
                self.backups_interface._refresh_backups()
            InfoBar.success(
                "Refreshed",
                "Backup list refreshed.",
                parent=toast_parent(self),
                duration=3000,
            )
            return

        if scope in ("dashboard", "profiles", "all"):
            self.config.sync_plugin_versions_from(self.plugin_manager)
            self.dashboard._load_profiles()
            self.profiles_interface._load_profiles()
            self.backups_interface._load_profiles()
            self._poster_refresh.kick_loads(self.config.games)
            if self.backups_interface.current_profile is not None:
                self.backups_interface._refresh_backups()
            self.plugins_interface._load_plugins()

        if scope in ("dashboard", "profiles", "all"):
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
        self.dashboard._load_profiles()
        self.profiles_interface._load_profiles()
        self.backups_interface._load_profiles()
        self._poster_refresh.kick_loads(self.config.games)
        if self.backups_interface.current_profile is not None:
            self.backups_interface._refresh_backups()
        self.plugins_interface.apply_load_report(report)
        self.plugins_interface._notify_reload_result(report, dev_mode=is_developer_mode(self.config))
        try:
            summary = format_load_report_summary(report)
            self.dashboard.log(f"Plugins reloaded: {summary}")
        except Exception:
            pass
        
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
        self._execute_backup_attempt(profile, offer_path_fix=True)

    def _execute_backup_attempt(self, profile, *, offer_path_fix: bool) -> None:
        """One backup attempt; optionally open path-fix dialog once then retry."""

        try:
            plug = resolve_plugin_for_profile(profile, self)
            if not ensure_plugin_restore_inputs(self, profile, plug, self.config):
                return
            profile_dict = profile.as_operation_dict(plug)
            if plug is not None:
                profile_dict = run_plugin_hook(plug, "preprocess_backup", profile_dict)
                if not profile.plugin_id:
                    profile.save_path = profile_dict.get("save_path", profile.save_path)
            backup_path = run_backup(profile, self.config, plug)
            result_data = {"backup_path": str(backup_path)}
            if plug is not None:
                run_plugin_hook(plug, "postprocess_backup", result_data)
            self.dashboard.log(f"Backup created: {backup_path.name}")
            InfoBar.success("Success", "Backup completed", parent=toast_parent(self))
            self._on_profiles_changed()
        except PluginHookError as e:
            detail = format_plugin_hook_error(e, include_traceback=is_developer_mode(self.config))
            logging.error("Plugin hook failed during backup:\n%s", detail)
            self.dashboard.log(detail if is_developer_mode(self.config) else str(e))
            InfoBar.error(
                "Plugin error",
                detail if is_developer_mode(self.config) else str(e),
                parent=toast_parent(self),
                duration=12000 if is_developer_mode(self.config) else 6000,
            )
        except (RuntimeError, FileNotFoundError) as e:
            msg = str(e)
            logging.debug("Backup skipped: %s", msg)
            self.dashboard.log(f"Backup skipped: {msg}")
            plug = resolve_plugin_for_profile(profile, self)
            if offer_path_fix and prompt_plugin_primary_path_fix(
                self,
                profile,
                plug,
                self.config,
                detail=msg,
            ):
                self._execute_backup_attempt(profile, offer_path_fix=False)
                return
            InfoBar.warning("Nothing to back up", msg, parent=toast_parent(self))
        except Exception:
            log_and_reraise(
                "BACKUP FAILED — open Python stderr / logs for full traceback.",
                likely_cause="Unexpected error during backup (see traceback).",
            )
        
    def _show_restore_dialog(self):
        """Show restore dialog as a popup listing backups for the selected profile."""
        profile = self.dashboard.current_profile
        if not profile:
            InfoBar.warning("No Profile", "Please select a game profile first", parent=toast_parent(self))
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
                InfoBar.warning("Save Failed", f"Could not persist theme: {e}", parent=toast_parent(self))
            except Exception:
                pass

        # Prompt the user: restart recommended to fully apply theme.
        from PyQt6.QtWidgets import QMessageBox as _QMB

        try:
            res = _QMB.question(
                self,
                "Theme Changed",
                "Restart recommended to fully apply theme. Restart now?",
                _QMB.StandardButton.Yes | _QMB.StandardButton.No,
            )
            if res == _QMB.StandardButton.Yes:
                try:
                    subprocess.Popen([sys.executable] + sys.argv)
                except Exception:
                    pass
                QApplication.quit()
            else:
                res2 = _QMB.question(
                    self,
                    "Apply Now?",
                    "Apply theme now without restart? This may crash the app.",
                    _QMB.StandardButton.Yes | _QMB.StandardButton.No,
                )
                if res2 == _QMB.StandardButton.Yes:
                    try:
                        self._apply_theme(self.config.theme)
                    except Exception:
                        pass
        except Exception:
            try:
                InfoBar.info(
                    "Theme Saved",
                    "Restart the application to fully apply the new theme.",
                    parent=toast_parent(self),
                )
            except Exception:
                pass

    def _set_backup_cwd(self):
        self.config.set_backup_mode_cwd()
        # Refresh UI elements that show backup root
        try:
            self.backups_interface._refresh_backups()
        except Exception:
            pass
        try:
            self.root_label.setText(f"Storage: {self.config.backup_root}")
        except Exception:
            pass

    def _choose_fixed_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Storage Folder")
        if folder:
            self.config.set_backup_mode_fixed(folder)
            try:
                self.backups_interface._refresh_backups()
            except Exception:
                pass
            try:
                self.root_label.setText(f"Storage: {self.config.backup_root}")
            except Exception:
                pass

    def _open_backup_root(self):
        try:
            path = self.config.backup_root
            path.mkdir(parents=True, exist_ok=True)
            open_path_in_explorer(path)
        except Exception as e:
            InfoBar.error("Open Failed", str(e), parent=toast_parent(self))
