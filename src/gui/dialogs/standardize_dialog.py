"""
Standardize Dialog for CAATmaster
Normalization and standardization operations
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QWidget, QMessageBox, QLineEdit, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button
from ..theme import Colors


class StandardizeDialog(BaseModal):
    """
    Dialog for data standardization and normalization.

    Shared by four operation_ids (stat_zscore, standardize_minmax,
    stat_percent_rank, stat_rank), each dispatching to its own real
    DataProcessor method - operation_id alone decides which one actually
    runs on Apply, the same way AnomalyDetectionDialog's operation_id
    decides which algorithm runs there. This dialog used to present four
    ADDITIONAL method choices (Min-Max -1 to 1, Decimal Scaling, two rank
    variants, Robust Z-Score) with no real operation behind any of them
    at all - selectable, previewable, but Apply would silently run
    whichever of the four real methods matched the operation_id it was
    opened for regardless of what was selected. Removed rather than
    wired up, since inventing new backend operations for them was a
    larger change than fixing the actual reported gap.
    """

    _METHOD_BY_OPERATION_ID = {
        "stat_zscore": "zscore",
        "standardize_minmax": "minmax",
        "stat_percent_rank": "percent_rank",
        "stat_rank": "rank",
    }

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None,
                 operation_id: str = None):
        self.original_df = dataframe
        self.locked_method = self._METHOD_BY_OPERATION_ID.get(operation_id, "zscore")
        super().__init__("Standardize/Normalize", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(550, 500)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from a right-click/menu action."""
        self.selected_column = column_name
        if hasattr(self, "column_selector") and column_name:
            self.column_selector.set_current_column(column_name)
            self.preview()

    def _on_column_selected(self, column_name: str):
        self.set_selected_column(column_name)

    def _setup_ui(self):
        """Setup the standardize dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Source Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column:")
        col_layout.addWidget(self.column_selector)

        layout.addWidget(col_group)

        # Method - locked to whichever operation_id this dialog was
        # opened for (see class docstring): only one is ever real for a
        # given menu action, so only that one is offered.
        method_group = QGroupBox("Standardization Method")
        method_layout = QVBoxLayout(method_group)

        self.method_group = QButtonGroup()

        methods = [
            ("Z-Score (Standard Score)", "zscore"),
            ("Min-Max Normalization (0-1)", "minmax"),
            ("Percent Rank", "percent_rank"),
            ("Rank", "rank"),
        ]

        for label, value in methods:
            radio = QRadioButton(label)
            radio.setProperty("method_value", value)
            self.method_group.addButton(radio)
            method_layout.addWidget(radio)
            if value == self.locked_method:
                radio.setChecked(True)
            else:
                radio.setEnabled(False)

        layout.addWidget(method_group)

        # Output column
        output_group = QGroupBox("Output Column")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Name:"), 0, 0)
        self.output_col_edit = QLineEdit("standardized")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview (First 10 Rows)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        # Statistics
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-style: italic;")
        preview_layout.addWidget(self.stats_label)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.apply_btn = create_primary_button("Apply")
        self.apply_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def get_parameters(self) -> dict:
        """The parameters actually sent to DataProcessor - both for this
        dialog's own preview() below and, via operation_id-based
        dispatch, for the real applied operation."""
        return {
            "column": self.column_selector.get_column(),
            "output_column": self.output_col_edit.text() or "standardized",
        }

    def validate(self) -> bool:
        """Validate parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column.")
            return False

        if column in self.original_df.columns:
            dtype = self.original_df[column].dtype
            if dtype not in [pl.Float64, pl.Float32, pl.Int64, pl.Int32, pl.Int16, pl.Int8]:
                QMessageBox.warning(self, "Validation Error",
                                  "Selected column must be numeric.")
                return False

        return True

    def preview(self):
        """Generate a preview by calling the exact same DataProcessor
        method Apply will call - an earlier version of this method
        recomputed each method locally (e.g. Percent Rank as 0-100 via
        np.argsort), which for Percent Rank specifically did not even
        match the real stat_percent_rank operation's own 0.0-1.0 scale,
        regardless of which method was selected."""
        from core.data_processor import DataProcessor

        try:
            params = self.get_parameters()
            column = params["column"]
            output_column = params["output_column"]

            if not column:
                return

            processor = DataProcessor()
            method = self.locked_method
            if method == "zscore":
                result = processor.zscore_transform(self.original_df, column=column, output_col=output_column)
                stats_text = "Mean=0, Std=1"
            elif method == "minmax":
                result = processor.minmax_normalize(self.original_df, column=column, output_col=output_column)
                stats_text = "Range: 0 to 1"
            elif method == "percent_rank":
                result = processor.percent_rank_transform(self.original_df, column=column, output_col=output_column)
                stats_text = "Range: 0.0 to 1.0"
            else:  # rank
                result = processor.rank_transform(self.original_df, column=column, output_col=output_column)
                stats_text = "Average rank (ties share the mean rank)"

            self.preview_table.load_dataframe(result.head(10))
            self.stats_label.setText(stats_text)

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")
