"""
Replace Values Dialog for CAATmaster
Find and replace values in a text column.
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QWidget, QMessageBox, QLineEdit,
    QCheckBox, QScrollArea
)
from PySide6.QtCore import Qt, QTimer

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button
from ..theme import Colors


class ReplaceValuesDialog(BaseModal):
    """
    Dialog for find-and-replace in a column, backed by
    DataProcessor.replace_values(). Offers a single find/replace pair
    with Case Sensitive, Whole Word Only, and Use Regular Expression
    options, matching replace_values()'s own parameters exactly (see
    that method's docstring for their semantics).
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        super().__init__("Replace Values", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(600, 480)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'column_selector') and column_name:
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_replaced")
            self._load_unique_values()

    def _on_column_selected(self, column_name: str):
        self.set_selected_column(column_name)

    def _load_unique_values(self):
        """Load unique values from selected column"""
        column = self.column_selector.get_column()
        if not column:
            return

        try:
            unique_vals = self.original_df[column].unique().to_list()
            # Limit to first 50 unique values
            unique_vals = unique_vals[:50]

            self.find_combo.clear()
            self.find_combo.addItems([str(v) for v in unique_vals])
        except Exception:
            pass

    def _setup_ui(self):
        """Setup the replace values dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Container widget for scroll area
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Source Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column:")
        self.column_selector.combo.currentIndexChanged.connect(self._load_unique_values)
        col_layout.addWidget(self.column_selector)

        scroll_layout.addWidget(col_group)

        # Find and replace
        options_group = QGroupBox("Find and Replace")
        options_layout = QGridLayout(options_group)

        options_layout.addWidget(QLabel("Find:"), 0, 0)
        self.find_combo = QComboBox()
        self.find_combo.setEditable(True)
        self.find_combo.setPlaceholderText("Value to find...")
        options_layout.addWidget(self.find_combo, 0, 1)

        options_layout.addWidget(QLabel("Replace with:"), 1, 0)
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replacement value...")
        options_layout.addWidget(self.replace_edit, 1, 1)

        self.case_sensitive = QCheckBox("Case sensitive")
        self.case_sensitive.setChecked(True)
        options_layout.addWidget(self.case_sensitive, 2, 0, 1, 2)

        self.whole_word = QCheckBox("Whole word only")
        options_layout.addWidget(self.whole_word, 3, 0, 1, 2)

        self.regex_check = QCheckBox("Use regular expression")
        options_layout.addWidget(self.regex_check, 4, 0, 1, 2)

        scroll_layout.addWidget(options_group)

        # Output options
        output_group = QGroupBox("Output Column")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Name:"), 0, 0)
        self.output_col_edit = QLineEdit("replaced")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        scroll_layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        # Stats
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-style: italic;")
        preview_layout.addWidget(self.stats_label)

        scroll_layout.addWidget(preview_group)

        # Set scroll area content
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.replace_btn = create_primary_button("Replace All")
        self.replace_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.replace_btn)

        layout.addLayout(btn_layout)

    def get_parameters(self) -> dict:
        """The parameters sent to DataProcessor.replace_values(), both
        for this dialog's own preview() below and, via
        TransformView.apply_transformation, for the applied operation.
        Key names match replace_values()'s signature exactly."""
        return {
            "column": self.column_selector.get_column(),
            "output_column": self.output_col_edit.text() or "replaced",
            "find_value": self.find_combo.currentText(),
            "replace_value": self.replace_edit.text(),
            "case_sensitive": self.case_sensitive.isChecked(),
            "whole_word": self.whole_word.isChecked(),
            "use_regex": self.regex_check.isChecked(),
        }

    def validate(self) -> bool:
        """Validate parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column.")
            return False

        if not self.find_combo.currentText():
            QMessageBox.warning(self, "Validation Error",
                              "Please enter a value to find.")
            return False

        return True

    def preview(self):
        """Generate a preview by calling the same DataProcessor.replace_values()
        that Replace All uses."""
        from core.data_processor import DataProcessor

        try:
            params = self.get_parameters()
            column = params["column"]

            if not column or not params["find_value"]:
                return

            processor = DataProcessor()
            try:
                # Uses _call_mapped_method so parameter name mapping
                # (output_column -> output_col) matches the real apply
                # path via TransformView.apply_transformation.
                result = processor._call_mapped_method(processor.replace_values, self.original_df, params)
            except Exception as regex_error:
                if params["use_regex"]:
                    self.stats_label.setText(f"Invalid regular expression: {regex_error}")
                    self.preview_table.clear()
                    return
                raise

            output_col = params["output_column"]
            col_data = self.original_df[column].to_list()
            replaced_data = result[output_col].to_list()
            replacement_count = sum(1 for v, r in zip(col_data, replaced_data) if str(v) != str(r))

            self.preview_table.load_dataframe(result.head(10))
            self.stats_label.setText(f"Found {replacement_count} changed value(s) in {len(col_data)} row(s)")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")
