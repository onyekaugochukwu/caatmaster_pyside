"""
Replace Values Dialog for CAATmaster
Find and replace values in columns
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QWidget, QMessageBox, QLineEdit,
    QCheckBox, QTextEdit, QTabWidget, QScrollArea
)
from PySide6.QtCore import Qt, QTimer

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button
from ..theme import Colors


class ReplaceValuesDialog(BaseModal):
    """
    Dialog for find and replace operations in columns
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        super().__init__("Replace Values", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(600, 500)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'column_selector') and column_name:
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_replaced")
            QTimer.singleShot(100, self._load_unique_values)

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        if hasattr(self, 'column_selector'):
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_replaced")
            QTimer.singleShot(100, self._load_unique_values)

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

        # Replace options tabs
        self.tabs = QTabWidget()

        # Simple replace tab
        self._create_simple_tab()

        # Advanced replace tab
        self._create_advanced_tab()

        self.tabs.addTab(self.simple_tab, "Simple Replace")
        self.tabs.addTab(self.advanced_tab, "Advanced")

        scroll_layout.addWidget(self.tabs)

        # Output options
        output_group = QGroupBox("Output Column")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Name:"), 0, 0)
        self.output_col_edit = QLineEdit("replaced")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        self.remove_original = QCheckBox("Remove original column")
        output_layout.addWidget(self.remove_original, 1, 0, 1, 2)

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

    def _create_simple_tab(self):
        """Create simple replace tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

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

        # Options
        self.case_sensitive = QCheckBox("Case sensitive")
        options_layout.addWidget(self.case_sensitive, 2, 0, 1, 2)

        self.whole_word = QCheckBox("Whole word only")
        options_layout.addWidget(self.whole_word, 3, 0, 1, 2)

        self.regex_check = QCheckBox("Use regular expression")
        options_layout.addWidget(self.regex_check, 4, 0, 1, 2)

        layout.addWidget(options_group)
        layout.addStretch()

        self.simple_tab = tab

    def _create_advanced_tab(self):
        """Create advanced replace tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        options_group = QGroupBox("Bulk Replace")
        options_layout = QVBoxLayout(options_group)

        help_label = QLabel("Enter replacements in format: old_value,new_value (one per line)")
        help_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        options_layout.addWidget(help_label)

        self.bulk_edit = QTextEdit()
        self.bulk_edit.setPlaceholderText("apple,green\nbanana,yellow\norange,orange")
        self.bulk_edit.setMaximumHeight(150)
        options_layout.addWidget(self.bulk_edit)

        layout.addWidget(options_group)
        layout.addStretch()

        self.advanced_tab = tab

    def get_parameters(self) -> dict:
        """Get the replace parameters"""
        tab_index = self.tabs.currentIndex()

        return {
            "column": self.column_selector.get_column(),
            "output_column": self.output_col_edit.text() or "replaced",
            "remove_original": self.remove_original.isChecked(),
            "replace_type": "simple" if tab_index == 0 else "bulk",
            "find_value": self.find_combo.currentText(),
            "replace_value": self.replace_edit.text(),
            "case_sensitive": self.case_sensitive.isChecked(),
            "whole_word": self.whole_word.isChecked(),
            "use_regex": self.regex_check.isChecked(),
            "bulk_replacements": self.bulk_edit.toPlainText(),
        }

    def validate(self) -> bool:
        """Validate parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column.")
            return False

        tab_index = self.tabs.currentIndex()
        if tab_index == 0:
            if not self.find_combo.currentText():
                QMessageBox.warning(self, "Validation Error",
                                  "Please enter a value to find.")
                return False
        else:
            if not self.bulk_edit.toPlainText().strip():
                QMessageBox.warning(self, "Validation Error",
                                  "Please enter bulk replacements.")
                return False

        return True

    def preview(self):
        """Generate preview of replacement"""
        try:
            params = self.get_parameters()
            column = params["column"]
            output_col = params["output_column"]

            if not column:
                return

            # Get data
            col_data = self.original_df[column].to_list()

            # Apply replacement
            if params["replace_type"] == "simple":
                find_val = str(params["find_value"])
                replace_val = str(params["replace_value"])

                result = []
                for val in col_data:
                    val_str = str(val) if val is not None else ""
                    if params["use_regex"]:
                        import re
                        try:
                            result.append(re.sub(find_val, replace_val, val_str,
                                                flags=0 if params["case_sensitive"] else re.IGNORECASE))
                        except re.error:
                            result.append(val_str)
                    elif params["case_sensitive"]:
                        result.append(val_str.replace(find_val, replace_val))
                    else:
                        # Case insensitive replace - need to preserve original case
                        # Find position of match and replace preserving case
                        find_lower = find_val.lower()
                        val_lower = val_str.lower()
                        replace_lower = replace_val.lower()
                        idx = val_lower.find(find_lower)
                        if idx != -1:
                            # Replace at the found position
                            result.append(val_str[:idx] + replace_val + val_str[idx + len(find_val):])
                        else:
                            result.append(val_str)
                replacement_count = sum(1 for v, r in zip(col_data, result) if str(v) != r)
            else:
                # Bulk replace
                bulk_lines = params["bulk_replacements"].strip().split('\n')
                replacements = {}
                for line in bulk_lines:
                    if ',' in line:
                        old, new = line.split(',', 1)
                        replacements[old.strip()] = new.strip()

                result = []
                replacement_count = 0
                for val in col_data:
                    val_str = str(val) if val is not None else ""
                    original = val_str
                    for old, new in replacements.items():
                        val_str = val_str.replace(old, new)
                    result.append(val_str)
                    if original != val_str:
                        replacement_count += 1

            # Update preview
            preview_df = self.original_df[:10].clone()
            preview_df = preview_df.with_columns(
                pl.Series(name=output_col, values=result[:10])
            )
            self.preview_table.load_dataframe(preview_df)

            # Update stats
            total = len(col_data)
            self.stats_label.setText(f"Found {replacement_count} matches in {total} rows")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")
