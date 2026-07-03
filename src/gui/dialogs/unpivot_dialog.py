"""
Unpivot Dialog for CAATmaster
Unpivot (melt) operation — converts wide format to long format
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QRadioButton, QButtonGroup, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea, QWidget, QMessageBox,
    QLineEdit, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer

from ..components.common_modals import BaseModal, PreviewTable, MultiColumnSelector


class UnpivotDialog(BaseModal):
    """
    Unpivot dialog
    Converts wide format (many columns) to long format (attribute/value pairs)
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Unpivot Columns", dataframe, parent)
        self.setMinimumSize(700, 600)

    def _setup_ui(self):
        """Setup the unpivot dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Unpivot options
        options_group = QGroupBox("Unpivot Options")
        options_layout = QVBoxLayout(options_group)

        self.option_group = QButtonGroup(options_group)

        self.all_cols_radio = QRadioButton("Unpivot All Columns")
        self.all_cols_radio.setChecked(True)
        self.option_group.addButton(self.all_cols_radio, 0)
        options_layout.addWidget(self.all_cols_radio)

        self.selected_cols_radio = QRadioButton("Unpivot Only These Columns")
        self.option_group.addButton(self.selected_cols_radio, 1)
        options_layout.addWidget(self.selected_cols_radio)

        self.except_cols_radio = QRadioButton("Unpivot All Columns Except")
        self.option_group.addButton(self.except_cols_radio, 2)
        options_layout.addWidget(self.except_cols_radio)

        layout.addWidget(options_group)

        # Column selection
        columns_group = QGroupBox("Columns to Unpivot")
        columns_layout = QVBoxLayout(columns_group)

        self.column_selector = MultiColumnSelector(self.original_df)
        columns_layout.addWidget(self.column_selector)

        layout.addWidget(columns_group)

        # Output column names
        output_group = QGroupBox("Output Column Names")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Attribute Column Name:"), 0, 0)
        self.attr_edit = QLineEdit("attribute")
        output_layout.addWidget(self.attr_edit, 0, 1)

        output_layout.addWidget(QLabel("Value Column Name:"), 1, 0)
        self.value_edit = QLineEdit("value")
        output_layout.addWidget(self.value_edit, 1, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview (First 10 Rows of Output)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Row count info
        self.row_info = QLabel()
        self.row_info.setStyleSheet("""
            QLabel {
                color: #666;
                font-style: italic;
            }
        """)
        layout.addWidget(self.row_info)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Update Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.unpivot_btn = QPushButton("Unpivot")
        self.unpivot_btn.setStyleSheet("""
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
        self.unpivot_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.unpivot_btn)

        layout.addLayout(btn_layout)

        # Connect signals
        self.option_group.buttonClicked.connect(self._on_option_changed)
        self.column_selector.columnsSelected.connect(self._on_columns_changed)

        # Initial preview
        QTimer.singleShot(100, self.preview)

    def _on_option_changed(self, button):
        """Handle option change"""
        option = self.option_group.id(button)
        if option == 0:  # All columns
            self.column_selector.setEnabled(False)
        elif option == 1:  # Selected columns
            self.column_selector.setEnabled(True)
        elif option == 2:  # Except columns
            self.column_selector.setEnabled(True)

    def _on_columns_changed(self, columns: List[str]):
        """Handle column selection change"""
        pass  # Preview will be updated when user clicks Update Preview

    def get_parameters(self) -> dict:
        """Get the unpivot parameters"""
        option = self.option_group.checkedId()

        if option == 0:
            # All columns except ID vars
            id_vars = [c for c in self.original_df.columns if c not in self.original_df.columns]
            value_vars = None
        elif option == 1:
            # Only selected columns
            id_vars = [c for c in self.original_df.columns if c not in self.column_selector.get_selected_columns()]
            value_vars = self.column_selector.get_selected_columns()
        else:  # option == 2
            # All except selected
            id_vars = [c for c in self.original_df.columns if c not in self.column_selector.get_selected_columns()]
            value_vars = None

        return {
            "id_vars": id_vars,
            "value_vars": value_vars,
            "var_name": self.attr_edit.text() or "attribute",
            "value_name": self.value_edit.text() or "value",
        }

    def validate(self) -> bool:
        """Validate the unpivot parameters"""
        option = self.option_group.checkedId()

        if option in [1, 2]:
            selected = self.column_selector.get_selected_columns()
            if not selected:
                QMessageBox.warning(self, "Validation Error",
                                  "Please select at least one column to unpivot.")
                return False

        return True

    def preview(self):
        """Generate preview of unpivoted data"""
        try:
            params = self.get_parameters()
            id_vars = params["id_vars"]
            value_vars = params["value_vars"]
            var_name = params["var_name"]
            value_name = params["value_name"]

            # Perform unpivot
            unpivoted = self.original_df.melt(
                id_vars=id_vars,
                value_vars=value_vars,
                variable_name=var_name,
                value_name=value_name
            )

            # Show preview
            self.preview_table.load_dataframe(unpivoted)

            # Update row info
            original_rows = len(self.original_df)
            new_rows = len(unpivoted)
            self.row_info.setText(f"Original rows: {original_rows:,} → Unpivoted rows: {new_rows:,}")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

    def get_unpivot_result(self) -> pl.DataFrame:
        """Get the unpivoted result after dialog is accepted"""
        try:
            params = self.get_parameters()
            return self.original_df.melt(
                id_vars=params["id_vars"],
                value_vars=params["value_vars"],
                variable_name=params["var_name"],
                value_name=params["value_name"]
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to unpivot:\n{str(e)}")
            return None


class PivotColumnDialog(BaseModal):
    """
    Pivot dialog
    Pivots a single column into multiple columns
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Pivot Column", dataframe, parent)
        self.setMinimumSize(600, 500)

    def _setup_ui(self):
        """Setup the pivot column dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Source column (values to pivot)
        source_group = QGroupBox("Source Column (Values to Pivot)")
        source_layout = QVBoxLayout(source_group)

        self.source_combo = QComboBox()
        self.source_combo.addItems(self.original_df.columns)
        self.source_combo.currentTextChanged.connect(self._on_source_changed)
        source_layout.addWidget(self.source_combo)

        source_help = QLabel("Values from this column will become new columns")
        source_help.setStyleSheet("color: #666; font-size: 11px;")
        source_layout.addWidget(source_help)

        layout.addWidget(source_group)

        # Values column
        values_group = QGroupBox("Values Column (to Aggregate)")
        values_layout = QVBoxLayout(values_group)

        self.values_combo = QComboBox()
        self.values_combo.addItems(self.original_df.columns)
        values_layout.addWidget(self.values_combo)

        layout.addWidget(values_group)

        # Aggregation function
        agg_group = QGroupBox("Aggregation Function")
        agg_layout = QVBoxLayout(agg_group)

        self.agg_group = QButtonGroup(agg_group)

        agg_options = [
            ("Sum", "sum"),
            ("Count", "count"),
            ("Average", "mean"),
            ("Minimum", "min"),
            ("Maximum", "max"),
            ("Don't Aggregate (Keep First)", "first"),
        ]

        for label, value in agg_options:
            radio = QRadioButton(label)
            radio.setProperty("agg_value", value)
            self.agg_group.addButton(radio)
            agg_layout.addWidget(radio)
            if value == "sum":
                radio.setChecked(True)

        layout.addWidget(agg_group)

        # Advanced options
        advanced_group = QGroupBox("Advanced Options")
        advanced_layout = QVBoxLayout(advanced_group)

        self.ignore_errors = QCheckBox("Ignore errors (skip rows with errors)")
        advanced_layout.addWidget(self.ignore_errors)

        self.fill_missing = QCheckBox("Generate column for missing values")
        self.fill_missing.stateChanged.connect(self._on_fill_missing_changed)
        advanced_layout.addWidget(self.fill_missing)

        fill_layout = QHBoxLayout()
        fill_layout.addWidget(QLabel("Default value for missing:"))
        self.default_value = QLineEdit("0")
        fill_layout.addWidget(self.default_value)
        fill_layout.addStretch()
        advanced_layout.addLayout(fill_layout)

        layout.addWidget(advanced_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Update Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.pivot_btn = QPushButton("Pivot")
        self.pivot_btn.setStyleSheet("""
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
        self.pivot_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.pivot_btn)

        layout.addLayout(btn_layout)

        # Initial preview
        QTimer.singleShot(100, self.preview)

    def _on_source_changed(self, text):
        """Handle source column change"""
        # Update values combo to exclude source column
        current_values = self.values_combo.currentText()
        self.values_combo.clear()
        for col in self.original_df.columns:
            if col != text:
                self.values_combo.addItem(col)
        if current_values != text:
            self.values_combo.setCurrentText(current_values)

    def _on_fill_missing_changed(self, state):
        """Handle fill missing checkbox change"""
        self.default_value.setEnabled(state == Qt.Checked)

    def get_parameters(self) -> dict:
        """Get the pivot parameters"""
        return {
            "columns": self.source_combo.currentText(),  # Column to pivot (becomes headers)
            "values": self.values_combo.currentText(),   # Column to aggregate
            "aggregation": (self.agg_group.checkedButton().property("agg_value")
                            if self.agg_group.checkedButton() else "sum"),
            "ignore_errors": self.ignore_errors.isChecked(),
            "fill_missing": self.fill_missing.isChecked(),
            "default_value": self.default_value.text(),
        }

    def validate(self) -> bool:
        """Validate the pivot parameters"""
        source = self.source_combo.currentText()
        values = self.values_combo.currentText()

        if source == values:
            QMessageBox.warning(self, "Validation Error",
                              "Source column and Values column must be different.")
            return False

        return True

    def preview(self):
        """Generate preview of pivoted data"""
        try:
            params = self.get_parameters()

            pivot_df = self.original_df.pivot(
                values=params["values"],
                index=None,  # No index - all columns become rows
                columns=params["columns"],
                aggregate_function=params["aggregation"]
            )

            self.preview_table.load_dataframe(pivot_df)

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

    def get_pivot_result(self) -> pl.DataFrame:
        """Get the pivoted result after dialog is accepted"""
        try:
            params = self.get_parameters()
            return self.original_df.pivot(
                values=params["values"],
                index=None,
                columns=params["columns"],
                aggregate_function=params["aggregation"]
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to pivot:\n{str(e)}")
            return None
