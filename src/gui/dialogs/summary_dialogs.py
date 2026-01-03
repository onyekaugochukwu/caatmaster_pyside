"""
Summary report dialogs for CAATmaster
Includes: Group Summary, Top/Bottom, Stratification, Sampling, Cross-Tabulation, Trend Analysis
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any
import random

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QWidget, QMessageBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QListWidget, QListWidgetItem, QAbstractItemView,
    QFrame, QSplitter, QRadioButton, QButtonGroup, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector


class GroupSummaryDialog(BaseModal):
    """Dialog for creating aggregated summary reports by groups"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Group Summary", dataframe, parent)
        self.setMinimumSize(600, 450)

        # Create scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Create content widget
        self.content_widget = QWidget()
        self._setup_ui_content()

        self.scroll_area.setWidget(self.content_widget)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.scroll_area)

        # Add buttons at bottom
        self._setup_buttons()

    def _setup_ui_content(self):
        layout = QVBoxLayout(self.content_widget)
        layout.setSpacing(15)

        # Group by columns
        group_group = QGroupBox("Group By")
        group_layout = QVBoxLayout(group_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Columns to Group By:")
        group_layout.addWidget(self.column_selector)

        layout.addWidget(group_group)

        # Value column and aggregations
        value_group = QGroupBox("Values to Aggregate")
        value_layout = QGridLayout(value_group)

        value_layout.addWidget(QLabel("Value Column:"), 0, 0)
        self.value_combo = QComboBox()
        self.value_combo.addItems(self.original_df.columns)
        value_layout.addWidget(self.value_combo, 0, 1)

        value_layout.addWidget(QLabel("Aggregations:"), 1, 0)
        self.agg_checkboxes = {}
        agg_layout = QHBoxLayout()
        aggregations = ["sum", "mean", "count", "min", "max", "std", "median"]
        for agg in aggregations:
            checkbox = QCheckBox(agg.capitalize())
            checkbox.setChecked(agg in ["sum", "count"])
            self.agg_checkboxes[agg] = checkbox
            agg_layout.addWidget(checkbox)
        agg_layout.addStretch()
        value_layout.addLayout(agg_layout, 1, 1)

        layout.addWidget(value_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

    def _setup_buttons(self):
        """Setup buttons at the bottom of the dialog"""
        btn_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Generate Summary")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.apply_btn.clicked.connect(self._apply_summary)
        btn_layout.addWidget(self.apply_btn)

        # Add buttons to main layout (outside scroll area)
        self.layout().addLayout(btn_layout)

    def _apply_summary(self):
        """Validate and accept summary"""
        group_cols = self.column_selector.get_column()
        if not group_cols:
            QMessageBox.warning(self, "Warning", "Please select at least one column to group by.")
            return

        value_col = self.value_combo.currentText()
        aggregations = [agg for agg, cb in self.agg_checkboxes.items() if cb.isChecked()]

        if not aggregations:
            QMessageBox.warning(self, "Warning", "Please select at least one aggregation.")
            return

        self.current_params = {
            "group_columns": group_cols,
            "value_column": value_col,
            "aggregations": aggregations
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        group_cols = params["group_columns"]
        value_col = params["value_column"]
        aggregations = params["aggregations"]

        # Build aggregation expressions
        agg_exprs = []
        for agg in aggregations:
            if agg == "sum":
                agg_exprs.append(pl.col(value_col).sum().alias(f"{value_col}_sum"))
            elif agg == "mean":
                agg_exprs.append(pl.col(value_col).mean().alias(f"{value_col}_mean"))
            elif agg == "count":
                agg_exprs.append(pl.count().alias("count"))
            elif agg == "min":
                agg_exprs.append(pl.col(value_col).min().alias(f"{value_col}_min"))
            elif agg == "max":
                agg_exprs.append(pl.col(value_col).max().alias(f"{value_col}_max"))
            elif agg == "std":
                agg_exprs.append(pl.col(value_col).std().alias(f"{value_col}_std"))
            elif agg == "median":
                agg_exprs.append(pl.col(value_col).median().alias(f"{value_col}_median"))

        return df.group_by(group_cols).agg(*agg_exprs)


class TopBottomDialog(BaseModal):
    """Dialog for showing top/bottom N items"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Top/Bottom Items", dataframe, parent)
        self.setMinimumSize(600, 400)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Ranking")
        col_layout = QGridLayout(col_group)

        col_layout.addWidget(QLabel("Column to Rank By:"), 0, 0)
        self.rank_col_combo = QComboBox()
        self.rank_col_combo.addItems(self.original_df.columns)
        col_layout.addWidget(self.rank_col_combo, 0, 1)

        col_layout.addWidget(QLabel("Value Column:"), 1, 0)
        self.value_col_combo = QComboBox()
        self.value_col_combo.addItems(self.original_df.columns)
        col_layout.addWidget(self.value_col_combo, 1, 1)

        col_layout.addWidget(QLabel("Number of Items (N):"), 2, 0)
        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 10000)
        self.n_spin.setValue(10)
        col_layout.addWidget(self.n_spin, 2, 1)

        col_layout.addWidget(QLabel("Rank Type:"), 3, 0)
        self.rank_type_combo = QComboBox()
        self.rank_type_combo.addItems(["Top (Highest)", "Bottom (Lowest)"])
        col_layout.addWidget(self.rank_type_combo, 3, 1)

        layout.addWidget(col_group)

        # Tie breaking
        tie_group = QGroupBox("Tie Breaking")
        tie_layout = QVBoxLayout(tie_group)

        self.tie_combo = QComboBox()
        self.tie_combo.addItems(["Keep All", "Random", "First", "Last"])
        tie_layout.addWidget(self.tie_combo)

        layout.addWidget(tie_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=15)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Generate")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.apply_btn.clicked.connect(self._apply_ranking)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _apply_ranking(self):
        """Accept ranking parameters"""
        self.current_params = {
            "column": self.rank_col_combo.currentText(),
            "value_column": self.value_col_combo.currentText(),
            "n": self.n_spin.value(),
            "rank_type": "top" if self.rank_type_combo.currentText().startswith("Top") else "bottom",
            "tie_break": self.tie_combo.currentText().lower().replace(" ", "_")
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        col = params["column"]
        n = params["n"]
        ascending = params["rank_type"] == "bottom"

        return df.sort(col, descending=not ascending).head(n)


class StratificationDialog(BaseModal):
    """Dialog for creating stratified views by value ranges"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Stratification", dataframe, parent)
        self.setMinimumSize(700, 500)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column to stratify
        col_group = QGroupBox("Stratification Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column to Stratify:")
        col_layout.addWidget(self.column_selector)

        layout.addWidget(col_group)

        # Strata boundaries
        strata_group = QGroupBox("Strata Boundaries")
        strata_layout = QVBoxLayout(strata_group)

        strata_layout.addWidget(QLabel("Enter boundaries (comma-separated, use 'inf' for infinity):"))
        self.boundaries_edit = QLineEdit()
        self.boundaries_edit.setPlaceholderText("e.g., 0, 100, 500, 1000, inf")
        strata_layout.addWidget(self.boundaries_edit)

        # Quick presets
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Presets:"))
        for name, value in [("Small", "0, 100, 500, 1000"),
                           ("Medium", "0, 50, 100, 250, 500, 1000, inf"),
                           ("Large", "0, 1000, 5000, 10000, 50000, inf")]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, v=value: self.boundaries_edit.setText(v))
            preset_layout.addWidget(btn)
        preset_layout.addStretch()
        strata_layout.addLayout(preset_layout)

        layout.addWidget(strata_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.counts_check = QCheckBox("Include row counts")
        self.counts_check.setChecked(True)
        options_layout.addWidget(self.counts_check)

        self.percentages_check = QCheckBox("Include percentages")
        options_layout.addWidget(self.percentages_check)

        layout.addWidget(options_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=15)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Generate Stratification")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.apply_btn.clicked.connect(self._apply_stratification)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _apply_stratification(self):
        """Accept stratification parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Warning", "Please select a column to stratify.")
            return

        boundaries_text = self.boundaries_edit.text().strip()
        if not boundaries_text:
            QMessageBox.warning(self, "Warning", "Please enter strata boundaries.")
            return

        try:
            boundaries = []
            for b in boundaries_text.split(","):
                b = b.strip()
                if b.lower() == "inf":
                    boundaries.append(float("inf"))
                else:
                    boundaries.append(float(b))
        except ValueError:
            QMessageBox.warning(self, "Warning", "Invalid boundary values. Use numbers or 'inf'.")
            return

        self.current_params = {
            "column": column,
            "strata": boundaries,
            "include_counts": self.counts_check.isChecked(),
            "include_percentages": self.percentages_check.isChecked()
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        col = params["column"]
        strata = params["strata"]

        # Create stratum labels
        total = len(df)
        results = []

        for i in range(len(strata) - 1):
            lower = strata[i]
            upper = strata[i + 1]

            if lower == float("-inf"):
                mask = pl.col(col) < upper
                label = f"< {upper}"
            elif upper == float("inf"):
                mask = pl.col(col) >= lower
                label = f">= {lower}"
            else:
                mask = (pl.col(col) >= lower) & (pl.col(col) < upper)
                label = f"{lower} - {upper}"

            stratum_df = df.filter(mask)
            count = len(stratum_df)

            row = {"stratum": label, "min": lower, "max": upper, "count": count}
            if params.get("include_percentages"):
                row["percentage"] = (count / total * 100) if total > 0 else 0

            results.append(row)

        return pl.DataFrame(results)


class SamplingDialog(BaseModal):
    """Dialog for creating sample-based analytical views"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Sampling", dataframe, parent)
        self.setMinimumSize(600, 400)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Method selection
        method_group = QGroupBox("Sampling Method")
        method_layout = QVBoxLayout(method_group)

        self.method_group = QButtonGroup()
        self.random_radio = QRadioButton("Simple Random Sample")
        self.random_radio.setChecked(True)
        method_layout.addWidget(self.random_radio)
        self.method_group.addButton(self.random_radio)

        self.stratified_radio = QRadioButton("Stratified Sample")
        method_layout.addWidget(self.stratified_radio)
        self.method_group.addButton(self.stratified_radio)

        self.systematic_radio = QRadioButton("Systematic Sample (Every Nth)")
        method_layout.addWidget(self.systematic_radio)
        self.method_group.addButton(self.systematic_radio)

        layout.addWidget(method_group)

        # Sample size
        size_group = QGroupBox("Sample Size")
        size_layout = QGridLayout(size_group)

        self.percentage_radio = QRadioButton("Percentage of total")
        self.percentage_radio.setChecked(True)
        size_layout.addWidget(self.percentage_radio, 0, 0)

        self.fixed_radio = QRadioButton("Fixed number of rows")
        size_layout.addWidget(self.fixed_radio, 1, 0)

        self.percentage_spin = QDoubleSpinBox()
        self.percentage_spin.setRange(0.1, 100)
        self.percentage_spin.setValue(10)
        self.percentage_spin.setSuffix("%")
        size_layout.addWidget(self.percentage_spin, 0, 1)

        self.fixed_spin = QSpinBox()
        self.fixed_spin.setRange(1, 1000000)
        self.fixed_spin.setValue(100)
        size_layout.addWidget(self.fixed_spin, 1, 1)

        layout.addWidget(size_group)

        # Stratification column (shown when stratified selected)
        strat_group = QGroupBox("Stratification")
        strat_layout = QVBoxLayout(strat_group)

        self.stratify_combo = QComboBox()
        self.stratify_combo.addItems([""] + self.original_df.columns)
        strat_layout.addWidget(QLabel("Stratify by column:"))
        strat_layout.addWidget(self.stratify_combo)

        layout.addWidget(strat_group)

        # Random seed
        seed_group = QGroupBox("Random Options")
        seed_layout = QVBoxLayout(seed_group)

        seed_layout.addWidget(QLabel("Random Seed (optional):"))
        self.seed_edit = QLineEdit()
        self.seed_edit.setPlaceholderText("Leave empty for random results")
        seed_layout.addWidget(self.seed_edit)

        layout.addWidget(seed_group)

        # Info
        self.info_label = QLabel(f"Total rows: {len(self.original_df)}")
        self.info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.info_label)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Generate Sample")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.apply_btn.clicked.connect(self._apply_sampling)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _apply_sampling(self):
        """Accept sampling parameters"""
        method = "random" if self.random_radio.isChecked() else \
                 "stratified" if self.stratified_radio.isChecked() else "systematic"

        if self.percentage_radio.isChecked():
            sample_size = None
            percentage = self.percentage_spin.value()
        else:
            sample_size = self.fixed_spin.value()
            percentage = None

        self.current_params = {
            "method": method,
            "sample_size": sample_size,
            "percentage": percentage,
            "stratify_column": self.stratify_combo.currentText() if self.stratified_radio.isChecked() else None,
            "random_seed": self.seed_edit.text().strip() if self.seed_edit.text().strip() else None
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        total = len(df)

        if params.get("percentage"):
            n = int(total * params["percentage"] / 100)
        elif params.get("sample_size"):
            n = min(params["sample_size"], total)
        else:
            n = int(total * 0.1)  # Default 10%

        seed = int(params["random_seed"]) if params.get("random_seed") else None
        if seed:
            np.random.seed(seed)

        if params["method"] == "random":
            indices = np.random.choice(total, size=n, replace=False)
            return df[indices]

        elif params["method"] == "stratified":
            strat_col = params.get("stratify_column")
            if not strat_col:
                return df.head(n)
            # Stratified sampling
            strata = df.group_by(strat_col)
            sample_dfs = []
            for group_df in strata:
                group_n = max(1, int(len(group_df) * n / total))
                indices = np.random.choice(len(group_df), size=min(group_n, len(group_df)), replace=False)
                sample_dfs.append(group_df[indices])
            return pl.concat(sample_dfs) if sample_dfs else df.head(n)

        else:  # systematic
            step = max(1, total // n)
            indices = list(range(0, total, step))[:n]
            return df[indices]


class CrossTabulationDialog(BaseModal):
    """Dialog for creating contingency tables (crosstabs)"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Cross-Tabulation", dataframe, parent)
        self.setMinimumSize(600, 400)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Row and column variables
        vars_group = QGroupBox("Variables")
        vars_layout = QGridLayout(vars_group)

        vars_layout.addWidget(QLabel("Row Variable:"), 0, 0)
        self.row_combo = QComboBox()
        self.row_combo.addItems(self.original_df.columns)
        vars_layout.addWidget(self.row_combo, 0, 1)

        vars_layout.addWidget(QLabel("Column Variable:"), 1, 0)
        self.col_combo = QComboBox()
        self.col_combo.addItems(self.original_df.columns)
        vars_layout.addWidget(self.col_combo, 1, 1)

        vars_layout.addWidget(QLabel("Value Column (optional):"), 2, 0)
        self.value_combo = QComboBox()
        self.value_combo.addItems([""] + self.original_df.columns)
        vars_layout.addWidget(self.value_combo, 2, 1)

        layout.addWidget(vars_group)

        # Aggregation
        agg_group = QGroupBox("Aggregation")
        agg_layout = QVBoxLayout(agg_group)

        self.agg_combo = QComboBox()
        self.agg_combo.addItems(["count", "sum", "mean", "min", "max"])
        agg_layout.addWidget(QLabel("Aggregation Function:"))
        agg_layout.addWidget(self.agg_combo)

        layout.addWidget(agg_group)

        # Percentages
        pct_group = QGroupBox("Percentages")
        pct_layout = QVBoxLayout(pct_group)

        self.show_pct_check = QCheckBox("Show percentages")
        pct_layout.addWidget(self.show_pct_check)

        self.pct_by_combo = QComboBox()
        self.pct_by_combo.addItems(["Total", "Row", "Column"])
        pct_layout.addWidget(QLabel("Calculate percentages by:"))
        pct_layout.addWidget(self.pct_by_combo)

        layout.addWidget(pct_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Generate Crosstab")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.apply_btn.clicked.connect(self._apply_crosstab)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _apply_crosstab(self):
        """Accept crosstab parameters"""
        row_var = self.row_combo.currentText()
        col_var = self.col_combo.currentText()

        if row_var == col_var:
            QMessageBox.warning(self, "Warning", "Row and Column variables must be different.")
            return

        self.current_params = {
            "rows": row_var,
            "columns": col_var,
            "values": self.value_combo.currentText() if self.value_combo.currentText() else None,
            "agg_function": self.agg_combo.currentText(),
            "show_percentages": self.show_pct_check.isChecked(),
            "percentages_by": self.pct_by_combo.currentText().lower()
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        row_var = params["rows"]
        col_var = params["columns"]
        value_var = params.get("values")

        if value_var:
            # Crosstab with values
            agg = params["agg_function"]
            if agg == "sum":
                agg_expr = pl.col(value_var).sum()
            elif agg == "mean":
                agg_expr = pl.col(value_var).mean()
            elif agg == "min":
                agg_expr = pl.col(value_var).min()
            elif agg == "max":
                agg_expr = pl.col(value_var).max()
            else:
                agg_expr = pl.count()

            result = df.group_by([row_var, col_var]).agg(agg_expr.alias("value"))
            return result.pivot(values="value", on=col_var, index=row_var)
        else:
            # Simple frequency crosstab
            result = df.group_by([row_var, col_var]).agg(pl.count().alias("count"))
            return result.pivot(values="count", on=col_var, index=row_var, fill_value=0)


class TrendAnalysisDialog(BaseModal):
    """Dialog for time-based trend analysis"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Trend Analysis", dataframe, parent)
        self.setMinimumSize(700, 500)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Date and value columns
        cols_group = QGroupBox("Time Series Data")
        cols_layout = QGridLayout(cols_group)

        cols_layout.addWidget(QLabel("Date/Time Column:"), 0, 0)
        self.date_combo = QComboBox()
        self.date_combo.addItems(self.original_df.columns)
        cols_layout.addWidget(self.date_combo, 0, 1)

        cols_layout.addWidget(QLabel("Value Column:"), 1, 0)
        self.value_combo = QComboBox()
        self.value_combo.addItems(self.original_df.columns)
        cols_layout.addWidget(self.value_combo, 1, 1)

        layout.addWidget(cols_group)

        # Period selection
        period_group = QGroupBox("Time Period")
        period_layout = QVBoxLayout(period_group)

        self.period_combo = QComboBox()
        self.period_combo.addItems(["Day", "Week", "Month", "Quarter", "Year"])
        self.period_combo.setCurrentText("Month")
        period_layout.addWidget(QLabel("Aggregate by:"))
        period_layout.addWidget(self.period_combo)

        layout.addWidget(period_group)

        # Aggregations
        agg_group = QGroupBox("Aggregations")
        agg_layout = QVBoxLayout(agg_group)

        self.sum_check = QCheckBox("Sum")
        self.sum_check.setChecked(True)
        agg_layout.addWidget(self.sum_check)

        self.mean_check = QCheckBox("Mean (Average)")
        self.mean_check.setChecked(True)
        agg_layout.addWidget(self.mean_check)

        self.count_check = QCheckBox("Count")
        agg_layout.addWidget(self.count_check)

        self.min_check = QCheckBox("Min")
        agg_layout.addWidget(self.min_check)

        self.max_check = QCheckBox("Max")
        agg_layout.addWidget(self.max_check)

        layout.addWidget(agg_group)

        # Trend options
        trend_group = QGroupBox("Trend Analysis")
        trend_layout = QVBoxLayout(trend_group)

        self.trendline_check = QCheckBox("Include trend line")
        trend_layout.addWidget(self.trendline_check)

        self.trend_combo = QComboBox()
        self.trend_combo.addItems(["Linear", "Exponential", "Moving Average"])
        trend_layout.addWidget(QLabel("Trend Type:"))
        trend_layout.addWidget(self.trend_combo)

        self.ma_period_spin = QSpinBox()
        self.ma_period_spin.setRange(2, 365)
        self.ma_period_spin.setValue(3)
        trend_layout.addWidget(QLabel("Moving Average Period:"))
        trend_layout.addWidget(self.ma_period_spin)

        layout.addWidget(trend_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=15)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Generate Trend Analysis")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.apply_btn.clicked.connect(self._apply_trend)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _apply_trend(self):
        """Accept trend parameters"""
        date_col = self.date_combo.currentText()
        value_col = self.value_combo.currentText()

        if date_col == value_col:
            QMessageBox.warning(self, "Warning", "Date and Value columns must be different.")
            return

        aggregations = []
        if self.sum_check.isChecked():
            aggregations.append("sum")
        if self.mean_check.isChecked():
            aggregations.append("mean")
        if self.count_check.isChecked():
            aggregations.append("count")
        if self.min_check.isChecked():
            aggregations.append("min")
        if self.max_check.isChecked():
            aggregations.append("max")

        if not aggregations:
            QMessageBox.warning(self, "Warning", "Please select at least one aggregation.")
            return

        period_map = {"Day": "day", "Week": "week", "Month": "month", "Quarter": "quarter", "Year": "year"}

        self.current_params = {
            "date_column": date_col,
            "value_column": value_col,
            "period": period_map[self.period_combo.currentText()],
            "aggregations": aggregations,
            "include_trendline": self.trendline_check.isChecked(),
            "trend_type": self.trend_combo.currentText().lower().replace(" ", "_"),
            "ma_period": self.ma_period_spin.value()
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        date_col = params["date_column"]
        value_col = params["value_column"]
        period = params["period"]

        # Create period column
        period_df = df.with_columns(
            pl.col(date_col).dt.truncate(period).alias("period")
        )

        # Build aggregation expressions
        agg_exprs = []
        for agg in params["aggregations"]:
            if agg == "sum":
                agg_exprs.append(pl.col(value_col).sum().alias(f"{value_col}_sum"))
            elif agg == "mean":
                agg_exprs.append(pl.col(value_col).mean().alias(f"{value_col}_mean"))
            elif agg == "count":
                agg_exprs.append(pl.count().alias("count"))
            elif agg == "min":
                agg_exprs.append(pl.col(value_col).min().alias(f"{value_col}_min"))
            elif agg == "max":
                agg_exprs.append(pl.col(value_col).max().alias(f"{value_col}_max"))

        result = period_df.group_by("period").agg(*agg_exprs).sort("period")

        # Add trend line if requested
        if params.get("include_trendline"):
            trend_type = params.get("trend_type", "linear")
            if trend_type == "moving_average":
                ma_period = params.get("ma_period", 3)
                result = result.with_columns(
                    pl.col(f"{value_col}_sum").rolling_mean(ma_period).alias(f"{value_col}_ma_{ma_period}")
                )

        return result
