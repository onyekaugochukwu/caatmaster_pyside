"""
CaatMaster design tokens — single source of truth for color, spacing, radius,
and typography.

Palette is a refinement of Microsoft's Fluent Design tokens - same family
(a "communication blue" accent, clean neutrals), tuned toward a slightly more
confident, cool-toned reading rather than stock Fluent defaults. This is a
deliberate choice for a tool auditors use alongside the office productivity
suites they already work in all day: keep the visual vocabulary they already
trust, don't invent a new one.

Every widget-level stylesheet in the app should build on these tokens instead
of hardcoding hex values. `get_stylesheet()` returns the one application-wide
QSS string loaded once in main.py; nothing else should call setStyleSheet()
with its own hardcoded palette.
"""
from pathlib import Path


def load_bundled_fonts() -> bool:
    """Register the bundled Inter variable fonts (resources/fonts/) with
    Qt's font database, so the app renders identically on Windows/Mac/
    Linux instead of depending on whichever system font happens to be
    installed. Must be called once, after QApplication exists and before
    get_stylesheet() is applied. Returns whether both files loaded - if
    not (or if this is never called at all), Typography.FONT_FAMILY's
    system-font fallbacks still make the app usable, just OS-dependent."""
    from PySide6.QtGui import QFontDatabase

    fonts_dir = Path(__file__).resolve().parent.parent.parent / "resources" / "fonts"
    regular_id = QFontDatabase.addApplicationFont(str(fonts_dir / "Inter-Variable.ttf"))
    italic_id = QFontDatabase.addApplicationFont(str(fonts_dir / "Inter-Italic-Variable.ttf"))
    return regular_id != -1 and italic_id != -1


class Colors:
    # Backgrounds
    BG_PRIMARY = "#ffffff"        # main content area, dialogs, grid ("surface")
    BG_SECONDARY = "#eaeff4"      # query pane, ribbon groups, panels - cool-toned, not flat gray ("muted")
    BG_TERTIARY = "#e4e9ef"       # hover state
    BG_PRESSED = "#d8dfe7"        # pressed state
    BG_SELECTED = "#e4edf9"       # selected row/item - tinted toward the accent
    BG_SELECTED_STRONG = "#cfe0f5"  # selected + hover

    # Borders / dividers
    BORDER = "#dce3ea"
    BORDER_STRONG = "#c7d1db"

    # Text
    TEXT_PRIMARY = "#151a21"      # near-black, cool undertone ("ink")
    TEXT_SECONDARY = "#5b6472"
    TEXT_TERTIARY = "#8a93a1"
    TEXT_DISABLED = "#a7b0bc"
    TEXT_ON_ACCENT = "#ffffff"

    # Accent - a more confident, deeper blue than stock Fluent, still the
    # same "communication blue" family so nothing feels replaced.
    ACCENT = "#1657a6"
    ACCENT_HOVER = "#124b8f"
    ACCENT_PRESSED = "#0d3b70"
    ACCENT_SOFT = "#e4edf9"       # tint for selected tabs/rows

    # Semantic - deliberately distinct hues from the accent, so status is
    # never confused with "this is clickable". _SOFT variants are tinted
    # backgrounds for status chips/labels (text stays the full-strength color).
    SUCCESS = "#1e8e5a"
    SUCCESS_HOVER = "#17703f"
    SUCCESS_SOFT = "#e1f4ea"
    WARNING = "#8a6d1f"
    WARNING_STRONG = "#b8710e"
    WARNING_SOFT = "#faf0dd"
    DANGER = "#c4302b"
    DANGER_HOVER = "#a12723"
    DANGER_SOFT = "#fbe6e5"

    # Data-quality bar segments (column profiling)
    QUALITY_VALID = "#1e8e5a"
    QUALITY_ERROR = "#c4302b"
    QUALITY_EMPTY = "#c7d1db"


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
    # Inter is bundled (resources/fonts/, loaded by load_bundled_fonts() in
    # main.py) so the app renders identically on Windows/Mac/Linux instead
    # of depending on whichever system font happens to be installed. The
    # rest of the chain is a graceful fallback for the (should never
    # happen) case where loading the bundled font failed.
    FONT_FAMILY = '"Inter", "Segoe UI", -apple-system, "Helvetica Neue", sans-serif'
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
    /* For a "commit/apply to dataset" action that needs to read as
    distinct from the primary "run/preview" action alongside it (e.g. a
    dialog with both "Run Analysis" and "Apply to Dataset" buttons). */
    QPushButton#SuccessButton {{
        background-color: {c.SUCCESS};
        color: {c.TEXT_ON_ACCENT};
        border: none;
    }}
    QPushButton#SuccessButton:hover {{ background-color: {c.SUCCESS_HOVER}; }}
    /* Without these, a disabled #PrimaryButton/#DangerButton still painted
    its full-strength color (the ID selector's un-conditioned background
    otherwise wins over the generic QPushButton:disabled rule above) -
    fully clickable-looking buttons that were actually inert. */
    QPushButton#PrimaryButton:disabled, QPushButton#DangerButton:disabled, QPushButton#SuccessButton:disabled {{
        background-color: {c.BG_SECONDARY};
        color: {c.TEXT_DISABLED};
        border: 1px solid {c.BORDER};
    }}
    QPushButton#GhostButton:disabled {{
        color: {c.TEXT_DISABLED};
    }}

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
        margin-top: 14px;
        padding-top: 14px;
        font-weight: 700;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: {c.ACCENT};
    }}

    /* ------------------------------------------------------------------ */
    /* Lists                                                               */
    /* ------------------------------------------------------------------ */
    QListWidget {{
        background-color: {c.BG_PRIMARY};
        border: 1px solid {c.BORDER};
        border-radius: {r.MD}px;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 8px;
        border-radius: {r.SM}px;
        color: {c.TEXT_PRIMARY};
    }}
    QListWidget::item:hover {{
        background-color: {c.BG_TERTIARY};
    }}
    QListWidget::item:selected {{
        background-color: {c.ACCENT};
        color: {c.TEXT_ON_ACCENT};
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
