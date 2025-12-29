"""
Column Context Menu for CAATmaster
Power Query-style right-click menu with 50+ transformation operations
Organized with logical groupings following Power Query conventions
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QCursor
from PySide6.QtWidgets import QMenu, QWidget, QVBoxLayout, QLabel, QFrame

# Import operations registry
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.core.operation_registry import OPERATION_REGISTRY, TransformationStepType


class ColumnContextMenu(QMenu):
    """
    Context menu for column transformations
    Structure follows Power Query conventions with logical groupings
    """

    # Signals
    transformRequested = Signal(str, dict)  # operation_name, parameters
    filterRequested = Signal(str, str)  # column, filter_expression
    sortRequested = Signal(str, bool)  # column, ascending
    renameRequested = Signal(str, str)  # old_name, new_name
    duplicateRequested = Signal(str)  # column
    hideRequested = Signal(str)  # column
    deleteRequested = Signal(str)  # column
    pivotRequested = Signal(str)  # column
    unpivotRequested = Signal(str)  # column
    mlRequested = Signal(str, str)  # column, operation
    aiRequested = Signal(str, str)  # column, operation
    statsRequested = Signal(str, str)  # column, operation

    def __init__(self, column_name: str, parent: QWidget = None):
        super().__init__(parent)
        self.column_name = column_name
        self.setObjectName("ContextMenu")
        self.setMinimumWidth(280)

        self._build_menu()

    def _build_menu(self):
        """Build the complete menu structure with Power Query-style organization"""

        # === SORT ===
        self._add_sort_section()

        # === FILTER ===
        self._add_filter_section()

        self.addSeparator()

        # === SPLIT COLUMN ===
        self._add_split_section()

        # === EXTRACT ===
        self._add_extract_section()

        # === TRANSFORM ===
        self._add_transform_section()

        # === STANDARDIZE (Statistics) ===
        self._add_standardize_section()

        self.addSeparator()

        # === ML ANALYSIS ===
        self._add_ml_section()

        # === AI ANALYSIS ===
        self._add_ai_section()

        # === COLUMN OPERATIONS ===
        self._add_column_section()

    def _add_sort_section(self):
        """Add sorting options"""
        sort_menu = self._create_submenu("Sort", "sort")

        asc_action = QAction("Sort Ascending", self)
        asc_action.setIcon(QIcon.fromTheme("sort-ascending"))
        asc_action.triggered.connect(
            lambda: self.sortRequested.emit(self.column_name, True)
        )
        sort_menu.addAction(asc_action)

        desc_action = QAction("Sort Descending", self)
        desc_action.setIcon(QIcon.fromTheme("sort-descending"))
        desc_action.triggered.connect(
            lambda: self.sortRequested.emit(self.column_name, False)
        )
        sort_menu.addAction(desc_action)

        self.addMenu(sort_menu)

    def _add_filter_section(self):
        """Add filter options"""
        filter_action = QAction("Filter...", self)
        filter_action.setIcon(QIcon.fromTheme("funnel"))
        filter_action.triggered.connect(
            lambda: self.filterRequested.emit(self.column_name, "")
        )
        self.addAction(filter_action)

    def _add_split_section(self):
        """Add Split Column options - Power Query style"""
        split_menu = self._create_submenu("Split Column", "split")

        # By Delimiter
        delimiter_menu = self._create_submenu("By Delimiter", "split")
        delimiters = [
            ("Comma", "split_comma", ","),
            ("Space", "split_space", " "),
            ("Semicolon", "split_semicolon", ";"),
            ("Pipe", "split_pipe", "|"),
            ("Tab", "split_tab", "\t"),
            ("Custom Character...", "split_custom", None),
        ]
        for label, op, delim in delimiters:
            action = QAction(label, self)
            if delim is None:
                action.triggered.connect(
                    lambda checked, o=op: self._emit_transform(o)
                )
            else:
                action.triggered.connect(
                    lambda checked, o=op, d=delim: self._emit_transform(o, {"delimiter": d})
                )
            delimiter_menu.addAction(action)
        split_menu.addMenu(delimiter_menu)

        # By Number of Characters
        chars_action = QAction("By Number of Characters...", self)
        chars_action.triggered.connect(
            lambda: self._emit_transform("split_chars")
        )
        split_menu.addAction(chars_action)

        # Positions
        positions_action = QAction("By Positions...", self)
        positions_action.triggered.connect(
            lambda: self._emit_transform("split_positions")
        )
        split_menu.addAction(positions_action)

        self.addMenu(split_menu)

    def _add_extract_section(self):
        """Add Extract operations - Power Query style"""
        extract_menu = self._create_submenu("Extract", "extract")

        # Text Extract
        text_extract_menu = self._create_submenu("Text", "format-text")
        text_extracts = [
            ("First Characters...", "text_extract_first"),
            ("Last Characters...", "text_extract_last"),
            ("Characters Between...", "text_extract_between"),
            ("Text Before Delimiter", "text_before_delimiter"),
            ("Text After Delimiter", "text_after_delimiter"),
            ("Range of Characters", "text_range"),
        ]
        for label, op in text_extracts:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            text_extract_menu.addAction(action)
        extract_menu.addMenu(text_extract_menu)

        # Date/Time Extract - following Power Query pattern
        date_extract_menu = self._create_submenu("Date", "calendar")
        date_parts = [
            ("Year", "datetime_year", "Year"),
            ("Month", "datetime_month", "Month Number"),
            ("Day", "datetime_day", "Day"),
            ("Week of Year", "datetime_weekofyear", "Week"),
            ("Quarter", "datetime_quarter", "Quarter"),
            ("Day of Week", "datetime_weekday", "Day Name"),
            ("Day of Year", "datetime_dayofyear", "Day Number"),
        ]
        for label, op, desc in date_parts:
            action = QAction(f"{label}", self)
            action.setToolTip(desc)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            date_extract_menu.addAction(action)
        extract_menu.addMenu(date_extract_menu)

        # Time Extract
        time_extract_menu = self._create_submenu("Time", "clock")
        time_parts = [
            ("Hour", "datetime_hour"),
            ("Minute", "datetime_minute"),
            ("Second", "datetime_second"),
        ]
        for label, op in time_parts:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            time_extract_menu.addAction(action)
        extract_menu.addMenu(time_extract_menu)

        # Duration Extract
        duration_menu = self._create_submenu("Duration", "timer")
        duration_parts = [
            ("Total Years", "duration_total_years"),
            ("Total Days", "duration_total_days"),
            ("Total Hours", "duration_total_hours"),
            ("Total Minutes", "duration_total_minutes"),
            ("Total Seconds", "duration_total_seconds"),
        ]
        for label, op in duration_parts:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(op)
            )
            duration_menu.addAction(action)
        extract_menu.addMenu(duration_menu)

        self.addMenu(extract_menu)

    def _add_transform_section(self):
        """Add Transform operations - Power Query style"""
        transform_menu = self._create_submenu("Transform", "transform")

        # Text Transforms
        text_menu = self._create_submenu("Text", "format-text")
        text_ops = [
            ("Lowercase", "text_lowercase"),
            ("Uppercase", "text_uppercase"),
            ("Title Case", "text_titlecase"),
            ("Trim", "text_trim"),
            ("Clean", "text_clean"),
            ("Add Prefix...", "text_add_prefix"),
            ("Add Suffix...", "text_add_suffix"),
            ("Reverse", "text_reverse"),
        ]
        for label, op in text_ops:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            text_menu.addAction(action)
        transform_menu.addMenu(text_menu)

        # Number Transforms
        number_menu = self._create_submenu("Number", "math")
        number_ops = [
            ("Round", "math_round"),
            ("Round Up", "math_ceil"),
            ("Round Down", "math_floor"),
            ("Absolute Value", "math_abs"),
            ("Square Root", "math_sqrt"),
            ("Square", "math_square"),
            ("Logarithm (ln)", "math_log"),
            ("Logarithm (base 10)", "math_log10"),
            ("Exponential", "math_exp"),
            ("Modulo...", "math_modulo"),
            ("Power...", "math_power"),
        ]
        for label, op in number_ops:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            number_menu.addAction(action)
        transform_menu.addMenu(number_menu)

        # Trigonometric
        trig_menu = self._create_submenu("Trigonometric", "math")
        trig_ops = [
            ("Sine", "trig_sin"),
            ("Cosine", "trig_cos"),
            ("Tangent", "trig_tan"),
            ("Arc Sine", "trig_asin"),
            ("Arc Cosine", "trig_acos"),
            ("Arc Tangent", "trig_atan"),
        ]
        for label, op in trig_ops:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            trig_menu.addAction(action)
        transform_menu.addMenu(trig_menu)

        # Date Transforms
        date_menu = self._create_submenu("Date", "calendar")
        date_ops = [
            ("Calculate Age", "datetime_age_years"),
            ("Start of Week", "datetime_week_start"),
            ("Start of Month", "datetime_month_start"),
            ("End of Week", "datetime_week_end"),
            ("End of Month", "datetime_month_end"),
            ("Is Weekend", "datetime_is_weekend"),
            ("Is Leap Year", "datetime_is_leap_year"),
            ("Days in Month", "datetime_days_in_month"),
        ]
        for label, op in date_ops:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            date_menu.addAction(action)
        transform_menu.addMenu(date_menu)

        # Data Type
        dtype_menu = self._create_submenu("Data Type", "type")
        dtypes = [
            ("Text", "dtype_text"),
            ("Whole Number", "dtype_int"),
            ("Decimal Number", "dtype_float"),
            ("Date", "dtype_date"),
            ("Date/Time", "dtype_datetime"),
            ("Boolean", "dtype_bool"),
        ]
        for label, op in dtypes:
            action = QAction(label, self)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(op)
            )
            dtype_menu.addAction(action)
        transform_menu.addMenu(dtype_menu)

        self.addMenu(transform_menu)

    def _add_standardize_section(self):
        """Add Statistics/Standardize operations"""
        stats_menu = self._create_submenu("Standardize", "chart-bar")

        # Z-Score (Standard Score)
        zscore_action = QAction("Z-Score (Standard Score)", self)
        zscore_action.setToolTip("Converts values to standard normal distribution (mean=0, std=1)")
        zscore_action.triggered.connect(
            lambda: self._emit_transform("stat_zscore")
        )
        stats_menu.addAction(zscore_action)

        # Min-Max Scaling
        minmax_action = QAction("Min-Max Scaling (0-1)", self)
        minmax_action.setToolTip("Scales values to range [0, 1]")
        minmax_action.triggered.connect(
            lambda: self._emit_transform("stat_minmax")
        )
        stats_menu.addAction(minmax_action)

        stats_menu.addSeparator()

        # Percent Rank
        pct_action = QAction("Percent Rank", self)
        pct_action.setToolTip("Returns the percent rank of each value")
        pct_action.triggered.connect(
            lambda: self._emit_transform("stat_percent_rank")
        )
        stats_menu.addAction(pct_action)

        # Rank
        rank_action = QAction("Rank", self)
        rank_action.setToolTip("Returns the rank of each value")
        rank_action.triggered.connect(
            lambda: self._emit_transform("stat_rank")
        )
        stats_menu.addAction(rank_action)

        self.addMenu(stats_menu)

    def _add_ml_section(self):
        """Add ML analysis submenu"""
        ml_menu = self._create_submenu("ML Analysis", "chart")

        # Anomaly Detection
        anomaly_menu = self._create_submenu("Detect Anomalies", "warning")
        anomaly_ops = [
            ("Isolation Forest", "ml_anomaly_iforest", "Tree-based anomaly detection"),
            ("Z-Score Method", "ml_anomaly_zscore", "Statistical outlier detection"),
            ("IQR Method", "ml_anomaly_iqr", "Interquartile range method"),
            ("Local Outlier Factor", "ml_anomaly_lof", "Density-based detection"),
        ]
        for label, op, desc in anomaly_ops:
            action = QAction(label, self)
            action.setToolTip(desc)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            anomaly_menu.addAction(action)
        ml_menu.addMenu(anomaly_menu)

        # Outlier Detection
        outlier_action = QAction("Outlier Detection", self)
        outlier_action.triggered.connect(
            lambda: self._emit_transform("ml_outlier")
        )
        ml_menu.addAction(outlier_action)

        ml_menu.addSeparator()

        # Clustering
        cluster_action = QAction("Cluster (K-Means)", self)
        cluster_action.setToolTip("Groups data into K clusters")
        cluster_action.triggered.connect(
            lambda: self._emit_transform("ml_cluster")
        )
        ml_menu.addAction(cluster_action)

        # Time Series Forecast
        forecast_action = QAction("Time Series Forecast", self)
        forecast_action.setToolTip("Predicts future values using exponential smoothing")
        forecast_action.triggered.connect(
            lambda: self._emit_transform("ml_forecast")
        )
        ml_menu.addAction(forecast_action)

        ml_menu.addSeparator()

        # Audit Operations
        audit_menu = self._create_submenu("Audit", "shield")
        audit_ops = [
            ("Benford's Law Analysis", "audit_benfords_law", "Digit distribution analysis"),
        ]
        for label, op, desc in audit_ops:
            action = QAction(label, self)
            action.setToolTip(desc)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            audit_menu.addAction(action)
        ml_menu.addMenu(audit_menu)

        self.addMenu(ml_menu)

    def _add_ai_section(self):
        """Add AI analysis submenu"""
        ai_menu = self._create_submenu("AI", "sparkles")

        # Text AI
        text_ai_menu = self._create_submenu("Text Analysis", "format-text")
        text_ai_ops = [
            ("Explain Column", "ai_explain", "Generate AI explanations"),
            ("Sentiment Analysis", "ai_sentiment", "Positive/Negative sentiment scoring"),
            ("Extract Entities", "ai_extract", "Extract emails, phones, dates, etc."),
            ("Summarize", "ai_summarize", "Generate text summaries"),
            ("Classify", "ai_classify", "Auto-classify text categories"),
        ]
        for label, op, desc in text_ai_ops:
            action = QAction(label, self)
            action.setToolTip(desc)
            action.triggered.connect(
                lambda checked, o=op: self._emit_transform(o)
            )
            text_ai_menu.addAction(action)
        ai_menu.addMenu(text_ai_menu)

        # Pattern Learning
        pattern_action = QAction("Pattern Learning (Flash Fill)", self)
        pattern_action.setToolTip("Learn patterns from examples")
        pattern_action.triggered.connect(
            lambda: self._emit_transform("ai_pattern_learn")
        )
        ai_menu.addAction(pattern_action)

        # Generate Code
        code_action = QAction("Generate Transformation Code", self)
        code_action.setToolTip("AI generates transformation code")
        code_action.triggered.connect(
            lambda: self._emit_transform("ai_generate_code")
        )
        ai_menu.addAction(code_action)

        self.addMenu(ai_menu)

    def _add_column_section(self):
        """Add column-level operations"""
        # Duplicate Column
        dup_action = QAction("Duplicate Column", self)
        dup_action.setIcon(QIcon.fromTheme("edit-copy"))
        dup_action.triggered.connect(
            lambda: self.duplicateRequested.emit(self.column_name)
        )
        self.addAction(dup_action)

        # Rename Column
        rename_action = QAction("Rename...", self)
        rename_action.setIcon(QIcon.fromTheme("edit-rename"))
        rename_action.triggered.connect(
            lambda: self.renameRequested.emit(self.column_name, "")
        )
        self.addAction(rename_action)

        self.addSeparator()

        # Replace Values
        replace_action = QAction("Replace Values...", self)
        replace_action.setIcon(QIcon.fromTheme("edit-find-replace"))
        replace_action.triggered.connect(
            lambda: self._emit_transform("replace_values")
        )
        self.addAction(replace_action)

        # Fill
        fill_menu = self._create_submenu("Fill", "fill-down")
        fill_menu.addAction("Fill Down")
        fill_menu.addAction("Fill Up")
        self.addMenu(fill_menu)

        self.addSeparator()

        # Hide Column
        hide_action = QAction("Hide", self)
        hide_action.setIcon(QIcon.fromTheme("eye-off"))
        hide_action.triggered.connect(
            lambda: self.hideRequested.emit(self.column_name)
        )
        self.addAction(hide_action)

        # Delete Column
        delete_action = QAction("Delete", self)
        delete_action.setIcon(QIcon.fromTheme("edit-delete"))
        delete_action.setProperty("danger", True)
        delete_action.triggered.connect(
            lambda: self.deleteRequested.emit(self.column_name)
        )
        self.addAction(delete_action)

    def _create_submenu(self, title: str, icon_name: str = None) -> QMenu:
        """Create a submenu with icon"""
        menu = QMenu(title, self)
        if icon_name:
            menu.setIcon(QIcon.fromTheme(icon_name))
        return menu

    def _emit_transform(self, operation: str, extra_params: dict = None):
        """Emit transform requested signal"""
        params = {"column": self.column_name}
        if extra_params:
            params.update(extra_params)
        self.transformRequested.emit(operation, params)

    def show_at(self, pos):
        """Show menu at position"""
        self.exec(pos)


class CellContextMenu(QMenu):
    """Context menu for cell operations"""

    copyRequested = Signal()
    editRequested = Signal()
    filterEqualsRequested = Signal(str)  # value
    filterNotEqualsRequested = Signal(str)  # value
    setToValueRequested = Signal(str)  # value
    setToNullRequested = Signal()

    def __init__(self, value: str = "", parent: QWidget = None):
        super().__init__(parent)
        self.value = value
        self.setObjectName("ContextMenu")
        self._build_menu()

    def _build_menu(self):
        # Copy
        copy_action = QAction("Copy", self)
        copy_action.setIcon(QIcon.fromTheme("edit-copy"))
        copy_action.triggered.connect(self.copyRequested.emit)
        self.addAction(copy_action)

        # Edit
        edit_action = QAction("Edit Value", self)
        edit_action.setIcon(QIcon.fromTheme("edit"))
        edit_action.triggered.connect(self.editRequested.emit)
        self.addAction(edit_action)

        self.addSeparator()

        # Filter
        filter_menu = QMenu("Filter", self)
        filter_menu.setIcon(QIcon.fromTheme("funnel"))

        equals_action = QAction(f"Equals: {self.value}", self)
        equals_action.triggered.connect(
            lambda: self.filterEqualsRequested.emit(self.value)
        )
        filter_menu.addAction(equals_action)

        not_equals_action = QAction(f"Not Equals: {self.value}", self)
        not_equals_action.triggered.connect(
            lambda: self.filterNotEqualsRequested.emit(self.value)
        )
        filter_menu.addAction(not_equals_action)

        self.addMenu(filter_menu)

        self.addSeparator()

        # Set
        set_menu = QMenu("Set All Rows To", self)
        set_menu.setIcon(QIcon.fromTheme("edit"))

        set_value_action = QAction(f"Value: {self.value}", self)
        set_value_action.triggered.connect(
            lambda: self.setToValueRequested.emit(self.value)
        )
        set_menu.addAction(set_value_action)

        set_null_action = QAction("NULL", self)
        set_null_action.triggered.connect(self.setToNullRequested.emit)
        set_menu.addAction(set_null_action)

        self.addMenu(set_menu)


class RowContextMenu(QMenu):
    """Context menu for row operations"""

    copyRequested = Signal()
    duplicateRequested = Signal()
    exportRequested = Signal()
    pinRequested = Signal()
    flagRequested = Signal()
    moveUpRequested = Signal()
    moveDownRequested = Signal()
    hideRequested = Signal()
    deleteRequested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("ContextMenu")
        self._build_menu()

    def _build_menu(self):
        # Selected
        self.addSeparator()

        # Copy
        copy_action = QAction("Copy Row", self)
        copy_action.setIcon(QIcon.fromTheme("edit-copy"))
        copy_action.triggered.connect(self.copyRequested.emit)
        self.addAction(copy_action)

        # Duplicate
        dup_action = QAction("Duplicate Row", self)
        dup_action.setIcon(QIcon.fromTheme("edit-copy"))
        dup_action.triggered.connect(self.duplicateRequested.emit)
        self.addAction(dup_action)

        self.addSeparator()

        # Export
        export_action = QAction("Export as JSON", self)
        export_action.setIcon(QIcon.fromTheme("document-export"))
        export_action.triggered.connect(self.exportRequested.emit)
        self.addAction(export_action)

        self.addSeparator()

        # Status
        pin_action = QAction("Pinned", self)
        pin_action.setCheckable(True)
        pin_action.triggered.connect(self.pinRequested.emit)
        self.addAction(pin_action)

        flag_action = QAction("Flagged", self)
        flag_action.setCheckable(True)
        flag_action.triggered.connect(self.flagRequested.emit)
        self.addAction(flag_action)

        self.addSeparator()

        # Move
        move_menu = QMenu("Move", self)
        move_up_action = QAction("Move Up", self)
        move_up_action.triggered.connect(self.moveUpRequested.emit)
        move_menu.addAction(move_up_action)

        move_down_action = QAction("Move Down", self)
        move_down_action.triggered.connect(self.moveDownRequested.emit)
        move_menu.addAction(move_down_action)

        self.addMenu(move_menu)

        self.addSeparator()

        # Hide
        hide_action = QAction("Hide Row", self)
        hide_action.setIcon(QIcon.fromTheme("eye-off"))
        hide_action.triggered.connect(self.hideRequested.emit)
        self.addAction(hide_action)

        # Delete
        delete_action = QAction("Delete Row", self)
        delete_action.setIcon(QIcon.fromTheme("edit-delete"))
        delete_action.setProperty("danger", True)
        delete_action.triggered.connect(self.deleteRequested.emit)
        self.addAction(delete_action)


# ============================================================================
# TRANSFORMATION DIALOGS
# ============================================================================

class TransformationDialog(QFrame):
    """
    Base dialog for transformation parameters
    To be subclassed for specific operations
    """

    submitted = Signal(dict)  # parameters

    def __init__(self, operation: str, column: str, parent: QWidget = None):
        super().__init__(parent)
        self.operation = operation
        self.column = column
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI - override in subclasses"""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Operation: {self.operation}"))
        layout.addWidget(QLabel(f"Column: {self.column}"))

    def get_parameters(self) -> dict:
        """Get the parameters for the transformation"""
        return {}

    def accept(self):
        """Submit the transformation"""
        self.submitted.emit(self.get_parameters())
        self.deleteLater()

    def reject(self):
        """Cancel the transformation"""
        self.deleteLater()
