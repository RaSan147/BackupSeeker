"""Modern widgets for BackupSeeker - No circular imports!"""

from __future__ import annotations

import sys
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QGuiApplication
from PyQt6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
                             QListWidgetItem, QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QFileDialog, QDialog, QPushButton)

from qframelesswindow import AcrylicWindow, TitleBar
from qfluentwidgets import (
    setThemeColor, FluentTranslator, Theme,
    NavigationInterface, NavigationItemPosition,
    FluentWindow, MessageBox, InfoBar, InfoBarPosition, PushButton,
    PrimaryPushButton, LineEdit, ListWidget, PlainTextEdit, TableWidget,
    CheckBox, ComboBox, StrongBodyLabel, BodyLabel, CaptionLabel,
    Dialog, StateToolTip, SplitTitleBar, RoundMenu, Action,
    FluentIcon as FIF, TeachingTip, TeachingTipTailPosition,
    ElevatedCardWidget, setTheme, SwitchButton
)

from .core import ConfigManager, GameProfile, PathUtils, run_backup, run_restore


class RoundedCard(ElevatedCardWidget):
    """Modern card with rounded corners."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disable hover attribute to avoid built-in hover animations
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_Hover, False)
        except Exception:
            pass
        # Make card backgrounds translucent/transparent by default so
        # the window acrylic effect can show through instead of a
        # solid single-color background (e.g. #2d2d2d in some themes).
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        except Exception:
            pass
        try:
            # Use transparent background in stylesheet to override opaque defaults
            self.setStyleSheet("ElevatedCardWidget{background: transparent;} RoundedCard{background: transparent;}")
        except Exception:
            pass

    def enterEvent(self, event):
        # Override and swallow hover/enter events to prevent movement/animation
        try:
            event.accept()
        except Exception:
            pass

    def leaveEvent(self, event):
        # Override and swallow leave events as well
        try:
            event.accept()
        except Exception:
            pass
    
    def mousePressEvent(self, event):
        # Allow mouse press to propagate so parent views (e.g. QListWidget)
        # can handle selection/clicks. Do not accept here.
        try:
            event.ignore()
        except Exception:
            pass

    def mouseMoveEvent(self, event):
        # Prevent movement/drag from initiating when dragging on the card.
        # Swallow move events so the frameless/window drag handlers do not
        # receive them.
        try:
            event.accept()
        except Exception:
            pass

    def mouseReleaseEvent(self, event):
        # Let release propagate so click handlers / selection perform normally.
        try:
            event.ignore()
        except Exception:
            pass


class ModernNavigationInterface(NavigationInterface):
    """Modern navigation sidebar."""
    pass


class ModernTitleBar(SplitTitleBar):
    """Modern title bar that doesn't hide window buttons and follows theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setFixedHeight(45)
        except Exception:
            pass

        branding_layout = QHBoxLayout()
        branding_layout.setContentsMargins(15, 0, 0, 0)
        branding_layout.setSpacing(10)

        self.icon_label = QLabel("💾")
        try:
            self.icon_label.setStyleSheet("QLabel{font-size: 18px; background: transparent;}")
            self.icon_label.setFixedSize(24, 24)
        except Exception:
            pass

        self.title_label = StrongBodyLabel("BackupSeeker")
        # Use palette-based color so the title responds to dark/light themes
        try:
            self.title_label.setStyleSheet("StrongBodyLabel{font-size: 14px; font-weight: bold; background: transparent; color: palette(windowText);}")
        except Exception:
            pass

        branding_layout.addWidget(self.icon_label)
        branding_layout.addWidget(self.title_label)
        branding_layout.addStretch()

        try:
            # Insert branding at the start of the title bar layout
            self.hBoxLayout.insertLayout(0, branding_layout)
            self.hBoxLayout.insertSpacing(1, 15)
        except Exception:
            # If the SplitTitleBar internals differ, fall back to adding widgets
            try:
                self.hBoxLayout.addLayout(branding_layout)
            except Exception:
                pass


class ModernGameEditor(Dialog):
    """Modern game editor - NO CIRCULAR IMPORTS!

    Inherit from `qfluentwidgets.Dialog` so the editor popup automatically
    follows the application's fluent theme (dark/light) instead of using
    the raw `QDialog` defaults which can look incorrect with the fluent
    style engine.
    """
    
    def __init__(self, profile: Optional[GameProfile] = None, parent=None):
        # qfluentwidgets.Dialog accepts (title, content, parent); fall back
        # to the plain QDialog-style constructor when not available.
        try:
            super().__init__("Game Profile 🎮", "", parent)
        except TypeError:
            QDialog.__init__(self, parent)

        self.profile = profile or GameProfile()
        self.setWindowTitle("🎮 Game Profile")
        self.setFixedSize(500, 400)
        self._setup_ui()
        # If the dialog implementation provided its own action buttons
        # (e.g. qfluentwidgets.Dialog), remap its OK button to perform
        # a proper save so we don't require duplicate buttons in the UI.
        try:
            for btn in self.findChildren((PushButton, QPushButton)):
                try:
                    txt = btn.text().strip().lower()
                except Exception:
                    continue
                if txt in ("ok", "ok", "accept"):
                    try:
                        btn.setText("Save Profile")
                    except Exception:
                        pass
                    try:
                        btn.clicked.connect(self._save)
                    except Exception:
                        pass
        except Exception:
            pass
        
    def _setup_ui(self):
        # Build the form inside a single widget so we can reliably insert
        # it into whatever layout the dialog uses (textLayout or main layout).
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)

        # Hide built-in title/content labels to avoid duplication
        if hasattr(self, 'titleLabel'):
            try:
                self.titleLabel.hide()
            except Exception:
                pass
        if hasattr(self, 'contentLabel'):
            try:
                self.contentLabel.hide()
            except Exception:
                pass

        # Name field
        form_layout.addWidget(BodyLabel("Game Name"))
        self.name_edit = LineEdit()
        self.name_edit.setText(self.profile.name)
        self.name_edit.setPlaceholderText("Enter game name...")
        form_layout.addWidget(self.name_edit)

        # Path field
        form_layout.addWidget(BodyLabel("Save Folder Path"))
        path_layout = QHBoxLayout()
        self.path_edit = LineEdit()
        self.path_edit.setText(self.profile.save_path)
        self.path_edit.setPlaceholderText("Paste or browse for save folder...")

        self.browse_btn = PushButton("Browse")
        self.browse_btn.setFixedWidth(80)
        self.browse_btn.clicked.connect(self._browse_path)

        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        form_layout.addLayout(path_layout)

        # Options
        self.compress_cb = CheckBox("Use compression")
        self.compress_cb.setChecked(self.profile.use_compression)

        self.clear_cb = CheckBox("Clear folder before restore")
        self.clear_cb.setChecked(self.profile.clear_folder_on_restore)

        form_layout.addWidget(self.compress_cb)
        form_layout.addWidget(self.clear_cb)
        form_layout.addStretch()

        # Buttons - add only if dialog does not already provide actions
        has_dialog_actions = hasattr(self, 'yesButton') or hasattr(self, 'cancelButton') or hasattr(self, 'buttonGroup')
        if not has_dialog_actions:
            btn_holder = QWidget()
            btn_layout = QHBoxLayout(btn_holder)
            self.save_btn = PrimaryPushButton("Save Profile")
            self.save_btn.clicked.connect(self._save)

            self.cancel_btn = PushButton("Cancel")
            self.cancel_btn.clicked.connect(self.close)

            btn_layout.addWidget(self.save_btn)
            btn_layout.addWidget(self.cancel_btn)
            form_layout.addWidget(btn_holder)

        # Insert the form widget into the dialog layout before the dialog's
        # own buttonGroup (if present) so the form appears above the buttons.
        parent_layout = self.layout() or QVBoxLayout(self)
        inserted = False
        try:
            if hasattr(self, 'buttonGroup') and self.buttonGroup is not None:
                # Prefer inserting into the fluent Dialog's main vBoxLayout
                if hasattr(self, 'vBoxLayout') and getattr(self, 'vBoxLayout') is not None:
                    vbox = self.vBoxLayout
                    for i in range(vbox.count()):
                        item = vbox.itemAt(i)
                        if item is None:
                            continue
                        try:
                            if item.layout() is self.buttonGroup:
                                vbox.insertLayout(i, form_layout)
                                inserted = True
                                break
                        except Exception:
                            pass
                else:
                    # Fallback: try to find the buttonGroup inside the parent_layout
                    for i in range(parent_layout.count()):
                        item = parent_layout.itemAt(i)
                        if item is None:
                            continue
                        try:
                            if item.layout() is self.buttonGroup:
                                if hasattr(self, 'textLayout') and getattr(self, 'textLayout') is not None:
                                    self.textLayout.addLayout(form_layout)
                                else:
                                    parent_layout.addWidget(form_widget)
                                inserted = True
                                break
                        except Exception:
                            pass
        except Exception:
            inserted = False

        if not inserted:
            # Fallbacks: if dialog exposes textLayout, add there; otherwise
            # append to the main layout.
            try:
                if hasattr(self, 'textLayout') and getattr(self, 'textLayout') is not None:
                    self.textLayout.addWidget(form_widget)
                else:
                    parent_layout.addWidget(form_widget)
            except Exception:
                parent_layout.addWidget(form_widget)
        
    def _browse_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Folder")
        if folder:
            contracted = PathUtils.contract(folder)
            self.path_edit.setText(contracted)
            
    def _save(self):
        name = self.name_edit.text().strip()
        raw_path = PathUtils.clean_input_path(self.path_edit.text())
        
        if not name:
            TeachingTip.create(
                target=self.name_edit,
                icon=FIF.INFO,
                title="Name required",
                content="Please enter a game name",
                parent=self
            )
            return
            
        if not raw_path:
            TeachingTip.create(
                target=self.path_edit,
                icon=FIF.INFO,
                title="Path required", 
                content="Please select a save folder path",
                parent=self
            )
            return
            
        self.profile.name = name
        self.profile.save_path = PathUtils.contract(raw_path)
        self.profile.use_compression = self.compress_cb.isChecked()
        self.profile.clear_folder_on_restore = self.clear_cb.isChecked()
        
        if not self.profile.id:
            self.profile.id = f"game_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
        self.accept()