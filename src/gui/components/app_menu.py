"""
Application menu bar — classic Office 2003-style chrome, built on native
QMenuBar/QMenu/QAction instead of hand-rolled ribbon widgets, with related
commands clustered into submenus (Minitab-18 style) instead of one long
flat list per menu.

Why native widgets: Qt's style engine renders menus/submenus correctly out
of the box — spacing, hover states, multi-column wrapping all come for
free. Custom QWidget-based ribbon widgets kept needing hand-tuned QSS and
pixel constants that were fragile and easy to get subtly wrong.

Every command is defined once as a QAction here and shared between the menu
bar and the Ctrl+K command palette (gui.components.command_palette), so
nothing is redefined twice.
"""
import qtawesome as qta
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenuBar, QMenu
from PySide6.QtCore import Qt

from gui.theme import Colors


def _icon(name, color=Colors.TEXT_SECONDARY):
    return qta.icon(name, color=color)


# ============================================================================
# Menu structure: a tree of (label, icon, action_id) leaves grouped into
# (label, [children]) submenus — mirrors Minitab's clustering, e.g.
# Transform > Text > Change Case > {Uppercase, Lowercase, Title Case}.
# `None` inside a children list is a separator.
# ============================================================================

TRANSFORM_MENU = [
    ("Rows && Columns", [
        ("Sort Ascending", "fa5s.sort-amount-down", "sort_asc"),
        ("Filter Rows...", "fa5s.filter", "filter"),
        ("Remove Rows...", "fa5s.eraser", "remove_rows"),
        ("Remove Columns...", "fa5s.eraser", "remove_cols"),
        ("Keep Top Rows...", "fa5s.angle-double-up", "keep_top"),
        ("Keep Bottom Rows...", "fa5s.angle-double-down", "keep_bottom"),
        None,
        ("Use First Row as Headers...", "fa5s.heading", "promote_header"),
        ("Use Headers as First Row", "fa5s.heading", "demote_header"),
    ]),
    ("Text", [
        ("Change Case", [
            ("Uppercase", "fa5s.font", "text_upper"),
            ("Lowercase", "fa5s.font", "text_lower"),
            ("Title Case", "fa5s.font", "text_title"),
        ]),
        ("Split Column", [
            ("By Comma", "fa5s.columns", "split_comma"),
            ("By Space", "fa5s.columns", "split_space"),
            ("Custom...", "fa5s.columns", "split_custom"),
        ]),
        None,
        ("Trim Whitespace", "fa5s.cut", "text_trim"),
        ("Text Length", "fa5s.ruler-horizontal", "text_length"),
    ]),
    ("Numbers", [
        ("Round", "fa5s.circle-notch", "math_round"),
        ("Absolute Value", "fa5s.arrows-alt-h", "math_abs"),
        ("Square Root", "fa5s.square-root-alt", "math_sqrt"),
    ]),
    ("Date && Time", [
        ("Extract Year", "fa5s.calendar-alt", "extract_year"),
        ("Extract Month", "fa5s.calendar-alt", "extract_month"),
        ("Extract Weekday", "fa5s.calendar-week", "extract_weekday"),
        ("Extract Hour", "fa5s.clock", "extract_hour"),
        ("Date Quarter", "fa5s.calendar-day", "date_quarter"),
        ("Date Age (Days)", "fa5s.hourglass-half", "date_age"),
    ]),
    ("Reshape", [
        ("Pivot Table...", "fa5s.table", "pivot"),
        ("Unpivot Columns...", "fa5s.stream", "unpivot"),
    ]),
    ("Column Operations", [
        ("Rename Column...", "fa5s.pen", "rename_col"),
        ("Change Data Type...", "fa5s.exchange-alt", "change_dtype"),
        ("Reorder Columns...", "fa5s.arrows-alt-h", "reorder_cols"),
        ("Select Columns...", "fa5s.check-square", "select_cols"),
        ("Custom Column...", "fa5s.magic", "custom_col"),
        ("Index Column", "fa5s.list-ol", "index_col"),
    ]),
]

AUDIT_MENU = [
    ("Audit Checks", [
        ("Benford's Law Analysis...", "fa5s.sort-numeric-down", "benford_law"),
        ("Find Duplicates...", "fa5s.clone", "audit_duplicates"),
        ("Gap Analysis...", "fa5s.ellipsis-h", "audit_gaps"),
        ("Outlier Detection...", "fa5s.exclamation-triangle", "audit_outliers"),
        ("Round Number Analysis", "fa5s.coins", "audit_round_numbers"),
        ("Flag Rows...", "fa5s.flag", "audit_flag"),
    ]),
    ("Statistical Flags", [
        ("Z-Score", "fa5s.chart-line", "stat_zscore"),
        ("Percentile Rank", "fa5s.percentage", "stat_pct_rank"),
        ("Rank", "fa5s.sort-numeric-down", "stat_rank"),
        ("Group Statistics...", "fa5s.layer-group", "stat_group_stats"),
    ]),
]

STATISTICS_MENU = [
    ("Visualize Dataset...", "fa5s.chart-bar", "visualize_dataset"),
    None,
    ("Descriptive", [
        ("Summary Statistics", "fa5s.chart-pie", "stat_summary"),
        ("Mean / Median", "fa5s.ruler-combined", "stat_central"),
        ("Variance", "fa5s.wave-square", "stat_variance"),
    ]),
    ("Hypothesis Tests", [
        ("T-Test", "fa5s.vial", "stat_ttest"),
        ("ANOVA", "fa5s.flask", "stat_anova"),
        ("Chi-Square", "fa5s.percentage", "stat_chisquare"),
    ]),
    ("Correlation", [
        ("Pearson Correlation", "fa5s.link", "stat_pearson"),
        ("Spearman Correlation", "fa5s.project-diagram", "stat_spearman"),
        ("Correlation Heatmap", "fa5s.fire", "stat_heatmap"),
    ]),
    ("Distributions", [
        ("Normal Distribution", "fa5s.bell", "stat_normal"),
        ("Binomial Distribution", "fa5s.dice", "stat_binomial"),
        ("Poisson Distribution", "fa5s.chart-bar", "stat_poisson"),
    ]),
]

REPORTS_MENU = [
    ("Audit Reports", [
        ("Generate Audit Report...", "fa5s.clipboard-check", "report_audit"),
        ("LLM Analysis...", "fa5s.brain", "report_llm"),
    ]),
    ("System Reports", [
        ("Data Profile Report", "fa5s.chart-bar", "report_profile"),
        ("Transformation Log", "fa5s.history", "report_transformation"),
        ("Quality Metrics", "fa5s.check-double", "report_quality"),
    ]),
    ("Export", [
        ("Export as Word (.docx)", "fa5s.file-word", "report_word"),
        ("Export as Excel (.xlsx)", "fa5s.file-excel", "report_excel"),
        ("Export as PDF (.pdf)", "fa5s.file-pdf", "report_pdf"),
    ]),
]

AI_MENU = [
    ("AI Operations", [
        ("AI Explain", "fa5s.lightbulb", "ai_explain"),
        ("AI Sentiment", "fa5s.smile", "ai_sentiment"),
        ("AI Extract", "fa5s.search", "ai_extract"),
        ("AI Pattern Learning", "fa5s.brain", "ai_pattern"),
    ]),
    ("Classify && Enrich", [
        ("Text Classify", "fa5s.tags", "ai_classify"),
        ("Summarize", "fa5s.align-left", "ai_summarize"),
        ("Enrich", "fa5s.magic", "ai_enrich"),
    ]),
    None,
    ("AI Activity Log...", "fa5s.history", "ai_activity_log"),
]

ML_MENU = [
    ("Regression", [
        ("Linear Regression...", "fa5s.chart-line", "ml_linear_regression"),
        ("GLM...", "fa5s.chart-area", "ml_glm"),
    ]),
    ("Tree-Based", [
        ("Decision Tree...", "fa5s.sitemap", "ml_decision_tree"),
        ("Random Forest...", "fa5s.tree", "ml_random_forest"),
        ("Gradient Boosting...", "fa5s.chart-line", "ml_gradient_boosting"),
        ("XGBoost...", "fa5s.bolt", "ml_xgboost"),
        ("LightGBM...", "fa5s.feather", "ml_lightgbm"),
    ]),
    ("Clustering", [
        ("K-Means Clustering...", "fa5s.object-group", "ml_cluster"),
        ("DBSCAN Clustering...", "fa5s.dot-circle", "ml_dbscan"),
        ("Gaussian Mixture...", "fa5s.chart-bar", "ml_gmm"),
    ]),
    ("Time Series", [
        ("ARIMA Forecast...", "fa5s.chart-line", "ml_arima"),
        ("Exponential Smoothing...", "fa5s.wave-square", "ml_ets"),
    ]),
    ("Anomaly Detection", [
        ("Isolation Forest", "fa5s.exclamation-triangle", "ml_anomaly_iforest"),
        ("Z-Score", "fa5s.ruler", "ml_anomaly_zscore"),
        ("IQR", "fa5s.ruler-combined", "ml_anomaly_iqr"),
        ("LOF", "fa5s.map-marker-alt", "ml_lof"),
    ]),
    ("Model Tools", [
        ("Train Model...", "fa5s.cogs", "ml_train"),
        ("Classify...", "fa5s.tags", "ml_classify"),
        ("Risk Score...", "fa5s.shield-alt", "ml_risk_score"),
        ("Predict...", "fa5s.magic", "ml_predict"),
    ]),
]

VIEW_MENU = [
    ("Query", [
        ("Query Parameters...", "fa5s.cog", "query_settings"),
        ("Dependencies", "fa5s.project-diagram", "dependencies"),
    ]),
    ("Column Preview", [
        ("Column Quality", "fa5s.check-circle", "col_quality"),
        ("Column Distribution", "fa5s.chart-bar", "col_dist"),
        ("Column Profile", "fa5s.chart-bar", "col_profile"),
    ]),
    ("Formula Bar", "fa5s.superscript", "formula_bar"),
]

_ALL_MENUS = (TRANSFORM_MENU, AUDIT_MENU, STATISTICS_MENU, REPORTS_MENU, AI_MENU, ML_MENU, VIEW_MENU)


def _is_leaf(item):
    """A leaf is (label, icon, action_id); a submenu is (label, [children])."""
    return len(item) == 3 and isinstance(item[1], str)


def _iter_leaves(items):
    for item in items:
        if item is None:
            continue
        if _is_leaf(item):
            yield item
        else:
            _, children = item
            yield from _iter_leaves(children)


class CommandRegistry:
    """Builds every QAction exactly once, keyed by action_id, so the menu
    bar (and anything else, like the command palette) can share the same
    objects instead of each defining their own copy."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.actions = {}
        for menu in _ALL_MENUS:
            for label, icon, action_id in _iter_leaves(menu):
                self._ensure(action_id, label, icon)

    def _ensure(self, action_id, label, icon):
        if action_id in self.actions:
            return self.actions[action_id]
        action = QAction(label, self.main_window)
        if icon:
            action.setIcon(_icon(icon))
        action.triggered.connect(lambda checked=False, aid=action_id: self.main_window.handle_ribbon_action(aid))
        self.actions[action_id] = action
        return action

    def get(self, action_id):
        return self.actions[action_id]


def _populate_menu(menu: QMenu, items, registry: CommandRegistry):
    for item in items:
        if item is None:
            menu.addSeparator()
        elif _is_leaf(item):
            _, _, action_id = item
            menu.addAction(registry.get(action_id))
        else:
            label, children = item
            submenu = menu.addMenu(label)
            _populate_menu(submenu, children, registry)


def build_menu_bar(main_window, registry: CommandRegistry) -> QMenuBar:
    """Build the full native menu bar. File and Help are wired directly to
    main_window methods; everything else routes through the shared
    CommandRegistry so actions are defined exactly once."""
    menu_bar = QMenuBar(main_window)

    file_menu = menu_bar.addMenu("&File")
    file_menu.addAction(_icon("fa5s.file"), "New Project...", main_window.new_project)
    file_menu.addAction(_icon("fa5s.folder-open"), "Open Project...", main_window.open_project)
    file_menu.addSeparator()
    file_menu.addAction(_icon("fa5s.save"), "Save Project", main_window.save_project).setShortcut(QKeySequence.Save)
    file_menu.addAction(_icon("fa5s.save"), "Save Project As...", main_window.save_project_as)
    file_menu.addSeparator()
    file_menu.addAction(_icon("fa5s.file-import"), "Import Data...", main_window.import_data)
    file_menu.addAction(_icon("fa5s.file-export"), "Export Data...", main_window.export_data)
    file_menu.addAction(_icon("fa5s.share-square"), "Export for Review...", main_window.export_for_review)
    file_menu.addSeparator()
    file_menu.addAction(_icon("fa5s.cog"), "Settings", lambda: main_window.on_navigation_requested("settings"))

    transform_menu = menu_bar.addMenu("&Transform")
    _populate_menu(transform_menu, TRANSFORM_MENU, registry)

    audit_menu = menu_bar.addMenu("&Audit")
    _populate_menu(audit_menu, AUDIT_MENU, registry)

    stats_menu = menu_bar.addMenu("&Statistics")
    _populate_menu(stats_menu, STATISTICS_MENU, registry)

    reports_menu = menu_bar.addMenu("&Reports")
    _populate_menu(reports_menu, REPORTS_MENU, registry)

    ai_menu = menu_bar.addMenu("A&I")
    _populate_menu(ai_menu, AI_MENU, registry)

    ml_menu = menu_bar.addMenu("&ML")
    _populate_menu(ml_menu, ML_MENU, registry)

    view_menu = menu_bar.addMenu("&View")
    _populate_menu(view_menu, VIEW_MENU, registry)
    view_menu.addSeparator()
    sidebar_action = QAction("Show Sidebar", main_window)
    sidebar_action.setCheckable(True)
    sidebar_action.setChecked(True)
    sidebar_action.setShortcut(QKeySequence("Ctrl+B"))
    sidebar_action.toggled.connect(main_window.toggle_sidebar)
    view_menu.addAction(sidebar_action)
    main_window.sidebar_toggle_action = sidebar_action

    help_menu = menu_bar.addMenu("&Help")
    help_menu.addAction(_icon("fa5s.search"), "Search Commands...\tCtrl+K", main_window.show_command_palette)
    help_menu.addSeparator()
    help_menu.addAction(_icon("fa5s.info-circle"), "About", main_window.show_about)

    return menu_bar
