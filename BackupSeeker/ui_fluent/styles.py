from __future__ import annotations

from typing import Optional

from PyQt6.QtGui import QBrush, QColor
from qfluentwidgets import TableWidget, setCustomStyleSheet

from ..ui_helpers import is_app_dark

# ============================================================================
# UI Constants & Helpers
# ============================================================================

# Card transparency - reduced for better UI clarity
CARD_STYLE_SEMI = "RoundedCard{background: rgba(0,0,0,0.5);}"
CARD_STYLE_TRANSPARENT = "RoundedCard{background: transparent;}"

# List/widget transparencies
LIST_STYLE_TRANSPARENT = (
    "QListWidget{background: transparent; border:0;} "
    "QListWidget::item{background: transparent;}"
)

SCROLL_AREA_STYLE_TRANSPARENT = (
    "QScrollArea{background: transparent; border:0;} "
    "QScrollArea QWidget{background:transparent}"
)

# Dim color for inactive/installed items
DIM_COLOR = QColor("#9a9a9a")
DIM_BRUSH = QBrush(DIM_COLOR)


class AdaptiveThemeStyles:
    """Centralized adaptive colors/styles for dark and light themes."""

    # Color palette separated by theme for clarity and easy adjustment
    COLORS = {
        'dark': {
            'text_primary': '#f3f3f3',
            'text_secondary': '#d3d3d3',
            'text_muted': '#b8b8b8',
            'badge_bg': 'rgba(255,255,255,0.25)',
            'separator': 'rgba(255,255,255,0.14)',
            'dim_color': '#b6b6b6',
            'panel_bg': 'rgba(0, 0, 0, 0.64)',
            'panel_border': 'rgba(255,255,255,0.12)',
            'table_bg': 'rgba(0, 0, 0, 0.76)',
            'table_border': 'rgba(255,255,255,0.14)',
            'table_gridline': 'rgba(255,255,255,0.10)',
            'table_header_bg': 'rgba(0, 0, 0, 0.88)',
            'table_header_border': 'rgba(255,255,255,0.16)',
            'table_alt_bg': 'rgba(255,255,255,0.04)',
            'table_selection_bg': 'rgba(0,120,215,0.48)',
            'table_selection_text': '#ffffff',
        },
        'light': {
            'text_primary': '#1f1f1f',
            'text_secondary': '#3f3f3f',
            'text_muted': '#5f5f5f',
            'badge_bg': 'rgba(0,0,0,0.14)',
            'separator': 'rgba(0,0,0,0.12)',
            'dim_color': '#6c6c6c',
            'panel_bg': 'rgba(255, 255, 255, 0.86)',
            'panel_border': 'rgba(0,0,0,0.16)',
            'table_bg': 'rgba(255, 255, 255, 0.92)',
            'table_border': 'rgba(0,0,0,0.14)',
            'table_gridline': 'rgba(0,0,0,0.08)',
            'table_header_bg': '#c5d0db',  # Distinct blue-gray header for clear visibility
            'table_header_border': 'rgba(0,0,0,0.30)',    # Darker border

            'table_alt_bg': 'rgba(0,0,0,0.03)',
            'table_selection_bg': 'rgba(0,120,215,0.22)',
            'table_selection_text': '#111111',
        }
    }

    def __init__(self, dark: Optional[bool] = None):
        self.dark = is_app_dark() if dark is None else dark
        self.theme = self.COLORS['dark'] if self.dark else self.COLORS['light']

    def text_primary(self) -> str:
        return self.theme['text_primary']

    def text_secondary(self) -> str:
        return self.theme['text_secondary']

    def text_muted(self) -> str:
        return self.theme['text_muted']

    def badge_bg(self) -> str:
        return self.theme['badge_bg']

    def separator(self) -> str:
        return self.theme['separator']

    def dim_brush(self) -> QBrush:
        return QBrush(QColor(self.theme['dim_color']))

    def info_panel_stylesheet(self, object_name: str, radius: int = 10) -> str:
        """Generate stylesheet for info panels with explicit color for text."""
        # Space before ``{`` is required — ``QWidget#id{`` fails Qt's QSS parser.
        return (
            f"QWidget#{object_name} {{"
            f"background: {self.theme['panel_bg']};"
            f"border: 1px solid {self.theme['panel_border']};"
            f"border-radius: {radius}px;"
            f"color: {self.theme['text_primary']};"
            "}"
        )

    def verify_report_dialog_stylesheet(self, dialog_object_name: str, radius: int = 8) -> str:
        """Apply to ``QDialog`` only (must use ``QDialog#id``, not ``QWidget#id``, or Qt fails to parse)."""

        t = self.theme
        return (
            f"QDialog#{dialog_object_name} {{"
            f"background-color: {t['panel_bg']};"
            f"border: 1px solid {t['panel_border']};"
            f"border-radius: {radius}px;"
            "}"
        )

    def restore_backup_dialog_stylesheet(self, dialog_object_name: str, radius: int = 8) -> str:
        """Surface + list text for Restore dialog; matches current light/dark palette."""

        t = self.theme
        oid = dialog_object_name
        return (
            f"QDialog#{oid} {{"
            f"background-color: {t['panel_bg']};"
            f"color: {t['text_primary']};"
            f"border: 1px solid {t['panel_border']};"
            f"border-radius: {radius}px;"
            "}"
            f"QDialog#{oid} StrongBodyLabel, QDialog#{oid} BodyLabel {{"
            f"color: {t['text_primary']};"
            "}"
            f"QDialog#{oid} CaptionLabel {{"
            f"color: {t['text_secondary']};"
            "}"
            f"QDialog#{oid} ComboBox {{"
            f"color: {t['text_primary']};"
            f"border: 1px solid {t['table_border']};"
            "border-radius: 4px;"
            "padding-left: 8px;"
            "}"
            f"QDialog#{oid} QListWidget {{"
            f"background-color: {t['table_bg']};"
            f"color: {t['text_primary']};"
            f"border: 1px solid {t['table_border']};"
            "border-radius: 6px;"
            "outline: none;"
            "}"
            f"QDialog#{oid} QListWidget::item {{"
            "background: transparent;"
            "border-radius: 4px;"
            "}"
            f"QDialog#{oid} QListWidget::item:selected {{"
            f"background-color: {t['table_selection_bg']};"
            f"color: {t['table_selection_text']};"
            "}"
            f"QDialog#{oid} QListWidget::item:hover:!selected {{"
            f"background-color: {t['table_alt_bg']};"
            "}"
        )

    def verify_report_plain_text_stylesheet(self) -> str:
        """Apply to ``QPlainTextEdit`` / Fluent PlainTextEdit child (same visual role as report body)."""

        t = self.theme
        return (
            "QPlainTextEdit {"
            f"background-color: {t['table_bg']};"
            f"color: {t['text_primary']};"
            f"border: 1px solid {t['panel_border']};"
            "border-radius: 6px;"
            "padding: 8px;"
            f"selection-background-color: {t['table_selection_bg']};"
            f"selection-color: {t['table_selection_text']};"
            "}"
            "QPlainTextEdit QScrollBar:vertical { width: 10px; background: transparent; }"
            "QPlainTextEdit QScrollBar::handle:vertical {"
            f"background-color: {t['separator']};"
            "border-radius: 4px;"
            "min-height: 24px;"
            "}"
        )

    def _build_table_qss(self, t: dict) -> str:
        # DO NOT override TableWidget background/border entirely so we don't lose
        # the beautiful native qfluentwidgets styling (transparency, scrollbars, indicators).
        # Only override the header text color so it isn't "ash" grey.
        return (
            f"TableWidget QHeaderView::section, QTableWidget QHeaderView::section {{"
            f"color: {t['text_primary']} !important;"
            f"font-weight: bold;"
            f"}}"
        )

    def _build_dialog_table_qss(self, t: dict) -> str:
        """Full table surface for modal dialogs where native Fluent chrome reads wrong."""
        return (
            self._build_table_qss(t)
            + f" TableWidget {{"
            f"background-color: {t['table_bg']};"
            f"color: {t['text_primary']};"
            f"border: 1px solid {t['table_border']};"
            "border-radius: 6px;"
            f"gridline-color: {t['table_gridline']};"
            "}"
            f" TableWidget::item {{ padding: 4px; }}"
            f" TableWidget::item:selected {{"
            f"background-color: {t['table_selection_bg']};"
            f"color: {t['table_selection_text']};"
            "}"
            f" TableWidget::item:alternate {{"
            f"background-color: {t['table_alt_bg']};"
            "}"
        )

    def apply_table_style(self, table: 'TableWidget') -> None:
        """Apply minimal explicit text color fixes over qfluentwidgets.
        
        qfluentwidgets natively resets stylesheets at runtime.
        setCustomStyleSheet safely appends our header text rules.
        """
        light_qss = self._build_table_qss(self.COLORS['light'])
        dark_qss = self._build_table_qss(self.COLORS['dark'])
        setCustomStyleSheet(table, light_qss, dark_qss)

    def apply_dialog_table_style(self, table: 'TableWidget') -> None:
        """Light/dark table body + selection for dialogs (see :meth:`apply_table_style` for main UI)."""

        light_qss = self._build_dialog_table_qss(self.COLORS['light'])
        dark_qss = self._build_dialog_table_qss(self.COLORS['dark'])
        setCustomStyleSheet(table, light_qss, dark_qss)
