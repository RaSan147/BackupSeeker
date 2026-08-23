from __future__ import annotations

from PyQt6.QtGui import QBrush, QColor
from qfluentwidgets import TableWidget, setCustomStyleSheet

from ..ui_helpers import is_app_dark

# ============================================================================
# UI Constants & Helpers
# ============================================================================

# Card and panel stylesheets for clean, bold modern UI (Hydra launcher aesthetic)
CARD_STYLE_SEMI = "RoundedCard{background: #1e202e; border: 1px solid #2b2e42; border-radius: 10px;}"
CARD_STYLE_TRANSPARENT = "RoundedCard{background: #1e202e; border: 1px solid #2b2e42; border-radius: 10px;}"

# List/widget styling - ONLY use with QListWidget (not qfluentwidgets ListWidget).
# For qfluentwidgets ListWidget, use apply_list_transparent_style() instead.
LIST_STYLE_TRANSPARENT = (
    "ListWidget, QListWidget { background: transparent; border: none; outline: none; } "
    "ListWidget::item, QListWidget::item { background: transparent; border: none; outline: none; }"
)

# Safe transparent-background style for qfluentwidgets ListWidget.
# Appends to (rather than replacing) the native Fluent QSS so scrollbars stay intact.
_LIST_TRANSPARENT_CUSTOM_QSS = (
    "ListWidget { background: transparent; border: none; outline: none; } "
    "ListWidget::item { background: transparent; border: none; outline: none; }"
)


def apply_list_transparent_style(list_widget) -> None:
    """Apply transparent background to a qfluentwidgets ``ListWidget`` safely.

    Uses :func:`setCustomStyleSheet` so the Fluent-native scrollbar and
    selection QSS is preserved and only the background/border overrides are
    appended on top.
    """
    setCustomStyleSheet(list_widget, _LIST_TRANSPARENT_CUSTOM_QSS, _LIST_TRANSPARENT_CUSTOM_QSS)

# Dim color for inactive/installed items
DIM_COLOR = QColor("#858b9c")
DIM_BRUSH = QBrush(DIM_COLOR)


class AdaptiveThemeStyles:
    """Centralized adaptive colors/styles for dark and light themes (Hydra aesthetic)."""

    # Color palette separated by theme for clarity and easy adjustment
    COLORS = {
        'dark': {
            'bg_main': '#12131a',
            'bg_surface': '#181a24',
            'bg_card': '#1e202e',
            'bg_card_hover': '#26293b',
            'text_primary': '#ffffff',
            'text_secondary': '#a0a6b8',
            'text_muted': '#6e758a',
            'badge_bg': '#2b2e42',
            'separator': '#26293b',
            'dim_color': '#858b9c',
            'panel_bg': '#181a24',
            'panel_border': '#2b2e42',
            'table_bg': '#181a24',
            'table_border': '#26293b',
            'table_gridline': '#1f2230',
            'table_header_bg': '#14151f',
            'table_header_border': '#26293b',
            'table_alt_bg': '#1b1d29',
            'table_selection_bg': '#5b6cf9',
            'table_selection_text': '#ffffff',
            'accent': '#5b6cf9',
            'accent_hover': '#7180fa',
        },
        'light': {
            'bg_main': '#f4f5f9',
            'bg_surface': '#ffffff',
            'bg_card': '#ffffff',
            'bg_card_hover': '#f0f2f8',
            'text_primary': '#16171d',
            'text_secondary': '#4f5466',
            'text_muted': '#7c8296',
            'badge_bg': '#e4e7f0',
            'separator': '#e0e3ed',
            'dim_color': '#6c7285',
            'panel_bg': '#ffffff',
            'panel_border': '#e0e3ed',
            'table_bg': '#ffffff',
            'table_border': '#e0e3ed',
            'table_gridline': '#eceef5',
            'table_header_bg': '#f0f2f8',
            'table_header_border': '#d8dce8',
            'table_alt_bg': '#fafbfe',
            'table_selection_bg': '#4f46e5',
            'table_selection_text': '#ffffff',
            'accent': '#4f46e5',
            'accent_hover': '#6366f1',
        }
    }

    def __init__(self, dark: bool | None = None):
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
        # Space before ``{`` is required - ``QWidget#id{`` fails Qt's QSS parser.
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
            "border-radius: 8px;"
            "padding: 10px 12px;"
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

    def apply_table_style(self, table: TableWidget) -> None:
        """Apply minimal explicit text color fixes over qfluentwidgets.
        
        qfluentwidgets natively resets stylesheets at runtime.
        setCustomStyleSheet safely appends our header text rules.
        """
        light_qss = self._build_table_qss(self.COLORS['light'])
        dark_qss = self._build_table_qss(self.COLORS['dark'])
        setCustomStyleSheet(table, light_qss, dark_qss)

    def apply_dialog_table_style(self, table: TableWidget) -> None:
        """Light/dark table body + selection for dialogs (see :meth:`apply_table_style` for main UI)."""

        light_qss = self._build_dialog_table_qss(self.COLORS['light'])
        dark_qss = self._build_dialog_table_qss(self.COLORS['dark'])
        setCustomStyleSheet(table, light_qss, dark_qss)
