"""
Command palette (Ctrl+K) — searchable list of every transformation, report,
and navigation action in the app.

With 80+ operations spread across ribbon tabs and right-click menus, the
palette exists so a user can type what they want ("benford", "pivot",
"export") instead of already knowing which tab it lives under.
"""
from typing import Callable, List, Tuple

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
)

from gui.theme import Colors

# (label, action_id) pairs mirroring every ribbon button — kept in sync with
# gui.components.ribbon's emit_action() calls, so the palette can find the
# same 80+ operations without the user needing to know which tab they're on.
RIBBON_ACTIONS = [
    ("Import", "import_data"), ("Export", "export_data"), ("Quick Export", "export_data"),
    ("Sort", "sort_asc"), ("Remove", "remove_rows"), ("Filter", "filter"),
    ("Upper/Lower", "text_upper"), ("Split", "split_comma"), ("Trim", "text_trim"),
    ("Round", "math_round"), ("Abs", "math_abs"), ("Sqrt", "math_sqrt"),
    ("Year/Month", "extract_year"), ("Weekday", "extract_weekday"), ("Age", "date_age"),
    ("Pivot", "pivot"), ("Unpivot", "unpivot"),
    ("Type", "change_dtype"), ("Rename", "rename_col"), ("Reorder", "reorder_cols"), ("Select", "select_cols"),
    ("Z-Score", "stat_zscore"), ("Benford", "benford_law"), ("Duplicates", "audit_duplicates"),
    ("Gaps", "audit_gaps"), ("Round #s", "audit_round_numbers"),
    ("Custom Column", "custom_col"), ("Index Column", "index_col"),
    ("Text Length", "text_length"), ("Text Extract", "text_extract"),
    ("Quick Stats", "stat_quick"), ("Quarter", "date_quarter"), ("Hour", "extract_hour"),
    ("Summary Statistics", "stat_summary"), ("Mean/Median", "stat_central"), ("Variance", "stat_variance"),
    ("T-Test", "stat_ttest"), ("ANOVA", "stat_anova"), ("Chi-Square", "stat_chisquare"),
    ("Pearson Correlation", "stat_pearson"), ("Spearman Correlation", "stat_spearman"), ("Heatmap", "stat_heatmap"),
    ("Normal Distribution", "stat_normal"), ("Binomial Distribution", "stat_binomial"), ("Poisson Distribution", "stat_poisson"),
    ("Generate Audit Report", "report_audit"), ("LLM Analysis", "report_llm"), ("Export Report as PDF", "report_pdf"),
    ("Data Profile Report", "report_profile"), ("Transformation Log", "report_transformation"), ("Quality Metrics", "report_quality"),
    ("Export as Word", "report_word"), ("Export as Excel", "report_excel"),
    ("AI Explain", "ai_explain"), ("AI Sentiment", "ai_sentiment"), ("AI Extract", "ai_extract"), ("AI Pattern", "ai_pattern"),
    ("AI Text Classify", "ai_classify"), ("AI Summarize", "ai_summarize"), ("AI Enrich", "ai_enrich"),
    ("Linear Regression", "ml_linear_regression"), ("GLM", "ml_glm"),
    ("Decision Tree", "ml_decision_tree"), ("Random Forest", "ml_random_forest"), ("Gradient Boosting", "ml_gradient_boosting"),
    ("XGBoost", "ml_xgboost"), ("LightGBM", "ml_lightgbm"),
    ("K-Means Clustering", "ml_cluster"), ("DBSCAN Clustering", "ml_dbscan"), ("Gaussian Mixture", "ml_gmm"),
    ("ARIMA Forecast", "ml_arima"), ("Exponential Smoothing", "ml_ets"),
    ("Isolation Forest (Anomaly)", "ml_anomaly_iforest"), ("Z-Score (Anomaly)", "ml_anomaly_zscore"),
    ("IQR (Anomaly)", "ml_anomaly_iqr"), ("LOF (Anomaly)", "ml_lof"),
    ("Query Settings", "query_settings"), ("Dependencies", "dependencies"),
    ("Column Quality", "col_quality"), ("Column Profile", "col_profile"),
    ("Formula Bar", "formula_bar"), ("Applied Steps Panel", "steps_panel"),
]

_CATEGORY_BY_PREFIX = [
    ("ml_", "ML"), ("ai_", "AI"), ("stat_", "Statistics"), ("report_", "Reports"),
    ("audit_", "Audit"), ("benford", "Audit"), ("import_", "File"), ("export_", "File"),
]


def _categorize(action_id: str) -> str:
    for prefix, category in _CATEGORY_BY_PREFIX:
        if action_id.startswith(prefix):
            return category
    return "Transform"


def build_ribbon_commands(action_handler: Callable[[str], None]) -> List[Tuple[str, str, Callable]]:
    """Turn RIBBON_ACTIONS into (label, category, callback) triples that
    invoke `action_handler(action_id)` — pass MainWindow.handle_ribbon_action."""
    seen = set()
    commands = []
    for label, action_id in RIBBON_ACTIONS:
        key = (label, action_id)
        if key in seen:
            continue
        seen.add(key)
        commands.append((label, _categorize(action_id), lambda aid=action_id: action_handler(aid)))
    return commands


class CommandPalette(QDialog):
    """Ctrl+K searchable command list. Each command is (label, category, callback)."""

    def __init__(self, commands: List[Tuple[str, str, Callable]], parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setModal(True)
        self.commands = commands
        self.setFixedWidth(480)

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Type a command or feature name...")
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                font-size: 14px;
                padding: 8px 12px;
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
            }}
        """)
        self.search_box.textChanged.connect(self._filter)
        self.search_box.installEventFilter(self)
        layout.addWidget(self.search_box)

        self.result_list = QListWidget()
        self.result_list.setMaximumHeight(360)
        self.result_list.itemActivated.connect(self._on_activated)
        layout.addWidget(self.result_list)

        self._populate(self.commands)
        self.search_box.setFocus()

    def _populate(self, commands):
        self.result_list.clear()
        for label, category, _callback in commands:
            item = QListWidgetItem(qta.icon("fa5s.bolt", color=Colors.TEXT_TERTIARY), f"{label}   —   {category}")
            item.setData(Qt.UserRole, _callback)
            self.result_list.addItem(item)
        if self.result_list.count() > 0:
            self.result_list.setCurrentRow(0)

    def _filter(self, text: str):
        text = text.lower().strip()
        matches = self.commands if not text else [
            c for c in self.commands if text in c[0].lower() or text in c[1].lower()
        ]
        self._populate(matches)

    def _on_activated(self, item: QListWidgetItem):
        callback = item.data(Qt.UserRole)
        self.accept()
        if callback:
            callback()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        if obj is self.search_box and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Down:
                row = min(self.result_list.currentRow() + 1, self.result_list.count() - 1)
                self.result_list.setCurrentRow(row)
                return True
            if key == Qt.Key_Up:
                row = max(self.result_list.currentRow() - 1, 0)
                self.result_list.setCurrentRow(row)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                item = self.result_list.currentItem()
                if item:
                    self._on_activated(item)
                return True
            if key == Qt.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, event)
