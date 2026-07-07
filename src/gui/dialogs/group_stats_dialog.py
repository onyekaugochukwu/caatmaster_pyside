"""
Group Statistics Dialog for CAATmaster
Calculate statistics grouped by a column
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QWidget, QMessageBox, QLineEdit,
    QCheckBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QTimer

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button
from ..theme import Colors


class GroupStatsDialog(BaseModal):
    """
    Dialog for calculating group statistics
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        super().__init__("Group Statistics", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(650, 550)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'value_column_selector') and column_name:
            self.value_column_selector.set_current_column(column_name)
            QTimer.singleShot(100, self.preview)

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        if hasattr(self, 'value_column_selector'):
            self.value_column_selector.set_current_column(column_name)
            QTimer.singleShot(100, self.preview)

    def _setup_ui(self):
        """Setup the group statistics dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection row
        columns_row = QHBoxLayout()

        # Group by column
        group_col_group = QGroupBox("Group By")
        group_col_layout = QVBoxLayout(group_col_group)

        self.group_column_selector = ColumnSelector(self.original_df)
        self.group_column_selector.set_label("Group Column:")
        group_col_layout.addWidget(self.group_column_selector)

        columns_row.addWidget(group_col_group)

        # Value column
        value_col_group = QGroupBox("Calculate For")
        value_col_layout = QVBoxLayout(value_col_group)

        self.value_column_selector = ColumnSelector(self.original_df)
        self.value_column_selector.set_label("Value Column:")
        value_col_layout.addWidget(self.value_column_selector)

        columns_row.addWidget(value_col_group)

        layout.addLayout(columns_row)

        # Statistics to calculate
        stats_group = QGroupBox("Statistics to Calculate")
        stats_layout = QGridLayout(stats_group)

        self.stats_checkboxes = {}

        stats_options = [
            ("Count", "count", True),
            ("Sum", "sum", True),
            ("Mean", "mean", True),
            ("Median", "median", True),
            ("Min", "min", True),
            ("Max", "max", True),
            ("Std Dev", "std", True),
            ("Variance", "var", False),
            ("First", "first", False),
            ("Last", "last", False),
        ]

        row, col = 0, 0
        for label, value, checked in stats_options:
            checkbox = QCheckBox(label)
            checkbox.setChecked(checked)
            stats_layout.addWidget(checkbox, row, col)
            self.stats_checkboxes[value] = checkbox
            col += 1
            if col > 2:
                col = 0
                row += 1

        layout.addWidget(stats_group)

        # Output options
        output_group = QGroupBox("Output Options")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Prefix:"), 0, 0)
        self.prefix_edit = QLineEdit("group")
        output_layout.addWidget(self.prefix_edit, 0, 1)

        self.add_as_new_rows = QCheckBox("Add as new rows (aggregate)")
        output_layout.addWidget(self.add_as_new_rows, 1, 0, 1, 2)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=15)
        preview_layout.addWidget(self.preview_table)

        # Stats
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
        """Get the group stats parameters"""
        selected_stats = [k for k, v in self.stats_checkboxes.items() if v.isChecked()]

        return {
            "group_column": self.group_column_selector.get_column(),
            "value_column": self.value_column_selector.get_column(),
            "statistics": selected_stats,
            "prefix": self.prefix_edit.text() or "group",
            "as_new_rows": self.add_as_new_rows.isChecked(),
        }

    def validate(self) -> bool:
        """Validate parameters"""
        group_col = self.group_column_selector.get_column()
        value_col = self.value_column_selector.get_column()

        if not group_col:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a group column.")
            return False

        if not value_col:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a value column.")
            return False

        selected_stats = [k for k, v in self.stats_checkboxes.items() if v.isChecked()]
        if not selected_stats:
            QMessageBox.warning(self, "Validation Error",
                              "Please select at least one statistic.")
            return False

        # Check value column is numeric
        if value_col in self.original_df.columns:
            dtype = self.original_df[value_col].dtype
            if dtype not in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]:
                QMessageBox.warning(self, "Validation Warning",
                                  "Value column should be numeric for most statistics.")

        return True

    def preview(self):
        """Generate preview of group statistics"""
        try:
            params = self.get_parameters()
            group_col = params["group_column"]
            value_col = params["value_column"]
            stats = params["statistics"]

            if not group_col or not value_col:
                return

            # Calculate group statistics
            result_df = self.original_df.group_by(group_col).agg(
                *[getattr(pl.col(value_col), s)().alias(f"{value_col}_{s}")
                  for s in stats]
            )

            # Sort by group column
            result_df = result_df.sort(group_col)

            # Limit preview
            preview_df = result_df.head(15)
            self.preview_table.load_dataframe(preview_df)

            # Update stats
            num_groups = len(result_df)
            self.stats_label.setText(f"{num_groups} groups found")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

    def apply_group_stats(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply group statistics to dataframe"""
        params = self.get_parameters()
        group_col = params["group_column"]
        value_col = params["value_column"]
        stats = params["statistics"]

        result_df = df.group_by(group_col).agg(
            *[getattr(pl.col(value_col), s)().alias(f"{value_col}_{s}")
              for s in stats]
        )

        return result_df.sort(group_col)
