"""
CaatMaster design tokens — single source of truth for color, spacing, radius,
and typography.

Palette follows Microsoft's Fluent Design tokens (the same ones Excel, Power
BI Desktop, and Power Query use) so the app reads as part of that family
rather than inventing its own visual language.

Every widget-level stylesheet in the app should build on these tokens instead
of hardcoding hex values. `get_stylesheet()` returns the one application-wide
QSS string loaded once in main.py; nothing else should call setStyleSheet()
with its own hardcoded palette.
"""


class Colors:
    # Backgrounds
    BG_PRIMARY = "#ffffff"        # main content area, dialogs, grid
    BG_SECONDARY = "#f3f2f1"      # query pane, ribbon groups, panels (Fluent neutralLighter)
    BG_TERTIARY = "#edebe9"       # hover state (Fluent neutralLighter2)
    BG_PRESSED = "#e1dfdd"        # pressed state (Fluent neutralLight)
    BG_SELECTED = "#deecf9"       # selected row/item (Fluent themeLighterAlt-ish)
    BG_SELECTED_STRONG = "#c7e0f4"  # selected + hover

    # Borders / dividers
    BORDER = "#e1dfdd"
    BORDER_STRONG = "#d2d0ce"

    # Text
    TEXT_PRIMARY = "#201f1e"      # Fluent neutralDark
    TEXT_SECONDARY = "#605e5c"    # Fluent neutralSecondary
    TEXT_TERTIARY = "#8a8886"     # Fluent neutralTertiary
    TEXT_DISABLED = "#a19f9d"
    TEXT_ON_ACCENT = "#ffffff"

    # Accent (Fluent "communication blue" — the exact blue Excel/Power BI use)
    ACCENT = "#0078d4"
    ACCENT_HOVER = "#106ebe"
    ACCENT_PRESSED = "#005a9e"
    ACCENT_SOFT = "#deecf9"       # tint for selected tabs/rows

    # Semantic
    SUCCESS = "#107c10"
    WARNING = "#797673"
    WARNING_STRONG = "#d29200"
    DANGER = "#d13438"
    DANGER_HOVER = "#a4262c"

    # Data-quality bar segments (column profiling)
    QUALITY_VALID = "#107c10"
    QUALITY_ERROR = "#d13438"
    QUALITY_EMPTY = "#c8c6c4"


class Spacing:
    XXS = 2
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    XXL = 24


class Radii:
    SM = 2
    MD = 4
    LG = 6


class Typography:
    FONT_FAMILY = '"Segoe UI", "Inter", sans-serif'
    SIZE_SM = 11
    SIZE_MD = 12
    SIZE_LG = 13
    SIZE_XL = 16
    SIZE_XXL = 20


def get_stylesheet() -> str:
    """Return the single application-wide stylesheet, built from tokens above."""
    c = Colors
    t = Typography
    r = Radii

    return f"""
    * {{
        font-family: {t.FONT_FAMILY};
        outline: none;
    }}

    QMainWindow, QDialog {{
        background-color: {c.BG_PRIMARY};
        color: {c.TEXT_PRIMARY};
    }}

    QWidget {{
        color: {c.TEXT_PRIMARY};
        font-size: {t.SIZE_MD}px;
    }}

    QLabel {{
        background: transparent;
        color: {c.TEXT_PRIMARY};
    }}

    /* ------------------------------------------------------------------ */
    /* Buttons                                                             */
    /* ------------------------------------------------------------------ */
    QPushButton {{
        background-color: {c.BG_PRIMARY};
        color: {c.TEXT_PRIMARY};
        border: 1px solid {c.BORDER_STRONG};
        border-radius: {r.SM}px;
        padding: 5px 12px;
    }}
    QPushButton:hover {{
        background-color: {c.BG_TERTIARY};
        border-color: {c.TEXT_TERTIARY};
    }}
    QPushButton:pressed {{
        background-color: {c.BG_PRESSED};
    }}
    QPushButton:disabled {{
        color: {c.TEXT_DISABLED};
        border-color: {c.BORDER};
        background-color: {c.BG_SECONDARY};
    }}
    QPushButton#PrimaryButton {{
        background-color: {c.ACCENT};
        color: {c.TEXT_ON_ACCENT};
        border: none;
    }}
    QPushButton#PrimaryButton:hover {{ background-color: {c.ACCENT_HOVER}; }}
    QPushButton#PrimaryButton:pressed {{ background-color: {c.ACCENT_PRESSED}; }}
    QPushButton#DangerButton {{
        background-color: {c.DANGER};
        color: {c.TEXT_ON_ACCENT};
        border: none;
    }}
    QPushButton#DangerButton:hover {{ background-color: {c.DANGER_HOVER}; }}
    QPushButton#GhostButton {{
        background-color: transparent;
        border: none;
    }}
    QPushButton#GhostButton:hover {{ background-color: {c.BG_TERTIARY}; }}

    QToolButton {{
        background-color: transparent;
        border: none;
        border-radius: {r.SM}px;
        padding: 4px;
        color: {c.TEXT_PRIMARY};
    }}
    QToolButton:hover {{ background-color: {c.BG_TERTIARY}; }}
    QToolButton:pressed {{ background-color: {c.BG_PRESSED}; }}
    QToolButton:checked {{ background-color: {c.BG_SELECTED}; }}

    /* ------------------------------------------------------------------ */
    /* Inputs                                                              */
    /* ------------------------------------------------------------------ */
    QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {c.BG_PRIMARY};
        color: {c.TEXT_PRIMARY};
        border: 1px solid {c.BORDER_STRONG};
        border-radius: {r.SM}px;
        padding: 4px 8px;
        selection-background-color: {c.ACCENT_SOFT};
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {c.ACCENT};
    }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background-color: {c.BG_PRIMARY};
        border: 1px solid {c.BORDER_STRONG};
        selection-background-color: {c.BG_SELECTED};
        selection-color: {c.TEXT_PRIMARY};
    }}

    QCheckBox, QRadioButton {{ spacing: 6px; color: {c.TEXT_PRIMARY}; }}

    /* ------------------------------------------------------------------ */
    /* Data grid                                                           */
    /* ------------------------------------------------------------------ */
    QTableWidget, QTableView {{
        background-color: {c.BG_PRIMARY};
        alternate-background-color: {c.BG_SECONDARY};
        gridline-color: {c.BORDER};
        color: {c.TEXT_PRIMARY};
        border: 1px solid {c.BORDER};
        selection-background-color: {c.BG_SELECTED};
        selection-color: {c.TEXT_PRIMARY};
    }}
    QTableWidget::item, QTableView::item {{
        padding: 4px;
        border: none;
    }}
    QTableWidget::item:selected, QTableView::item:selected {{
        background-color: {c.BG_SELECTED};
        color: {c.TEXT_PRIMARY};
    }}
    QHeaderView::section {{
        background-color: {c.BG_SECONDARY};
        color: {c.TEXT_SECONDARY};
        padding: 6px 8px;
        border: none;
        border-right: 1px solid {c.BORDER};
        border-bottom: 1px solid {c.BORDER_STRONG};
        font-weight: 600;
    }}
    QHeaderView::section:hover {{ background-color: {c.BG_TERTIARY}; }}

    /* ------------------------------------------------------------------ */
    /* Menus / Tooltips                                                    */
    /* ------------------------------------------------------------------ */
    QMenu {{
        background-color: {c.BG_PRIMARY};
        border: 1px solid {c.BORDER_STRONG};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 24px 6px 12px;
        border-radius: {r.SM}px;
        color: {c.TEXT_PRIMARY};
    }}
    QMenu::item:selected {{
        background-color: {c.BG_SELECTED};
    }}
    QMenu::separator {{
        height: 1px;
        background: {c.BORDER};
        margin: 4px 8px;
    }}
    QToolTip {{
        background-color: {c.TEXT_PRIMARY};
        color: {c.BG_PRIMARY};
        border: none;
        padding: 4px 8px;
    }}

    /* ------------------------------------------------------------------ */
    /* Tabs / Group boxes                                                  */
    /* ------------------------------------------------------------------ */
    QTabWidget::pane {{
        border: 1px solid {c.BORDER};
        background-color: {c.BG_PRIMARY};
    }}
    QTabBar::tab {{
        background-color: {c.BG_SECONDARY};
        color: {c.TEXT_SECONDARY};
        padding: 6px 16px;
        border: none;
    }}
    QTabBar::tab:selected {{
        background-color: {c.BG_PRIMARY};
        color: {c.TEXT_PRIMARY};
        border-bottom: 2px solid {c.ACCENT};
    }}
    QGroupBox {{
        border: 1px solid {c.BORDER};
        border-radius: {r.MD}px;
        margin-top: 10px;
        padding-top: 12px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        color: {c.TEXT_SECONDARY};
    }}

    /* ------------------------------------------------------------------ */
    /* Scroll bars                                                         */
    /* ------------------------------------------------------------------ */
    QScrollBar:vertical {{
        background: {c.BG_SECONDARY};
        width: 12px;
        border-radius: 6px;
    }}
    QScrollBar::handle:vertical {{
        background: {c.BORDER_STRONG};
        border-radius: 6px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c.TEXT_TERTIARY}; }}
    QScrollBar:horizontal {{
        background: {c.BG_SECONDARY};
        height: 12px;
        border-radius: 6px;
    }}
    QScrollBar::handle:horizontal {{
        background: {c.BORDER_STRONG};
        border-radius: 6px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{ background: {c.TEXT_TERTIARY}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; width: 0px; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

    /* ------------------------------------------------------------------ */
    /* Status bar                                                          */
    /* ------------------------------------------------------------------ */
    QStatusBar {{
        background-color: {c.BG_SECONDARY};
        border-top: 1px solid {c.BORDER};
        color: {c.TEXT_SECONDARY};
    }}
    QStatusBar::item {{ border: none; }}

    QScrollArea {{
        background-color: {c.BG_PRIMARY};
        border: none;
    }}

    /* ------------------------------------------------------------------ */
    /* Shared components (gui.components.modern_ui: Card, Section)        */
    /* ------------------------------------------------------------------ */
    QFrame#Card {{
        background-color: {c.BG_PRIMARY};
        border: 1px solid {c.BORDER};
        border-radius: {r.MD}px;
    }}
    QFrame#Section {{
        background-color: {c.BG_SECONDARY};
        border: 1px solid {c.BORDER};
        border-radius: {r.MD}px;
    }}
    QLabel#HeadingLabel {{
        color: {c.TEXT_PRIMARY};
    }}
    QLabel#TitleLabel {{
        color: {c.TEXT_PRIMARY};
        font-size: {t.SIZE_XXL}px;
        font-weight: 700;
    }}
    """
