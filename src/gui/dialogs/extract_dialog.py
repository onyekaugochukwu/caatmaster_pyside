"""
Extract Dialog for CAATmaster
Extract components from text and date columns
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QCheckBox, QGroupBox, QWidget,
    QMessageBox, QLineEdit, QRadioButton, QButtonGroup, QTabWidget, QWidget,
    QScrollArea, QSpinBox
)
from PySide6.QtCore import Qt, QTimer

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button


class ExtractDialog(BaseModal):
    """
    Dialog for extracting components from text and date columns
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        super().__init__("Extract Values", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(600, 550)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'column_selector') and column_name:
            self.column_selector.set_current_column(column_name)
            # Update output column name
            self.output_col_edit.setText(f"{column_name}_extracted")
            QTimer.singleShot(100, self.preview)

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        if hasattr(self, 'column_selector'):
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_extracted")
            QTimer.singleShot(100, self.preview)

    def _setup_ui(self):
        """Setup the extract dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Source Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column:")
        col_layout.addWidget(self.column_selector)

        layout.addWidget(col_group)

        # Extraction type tabs
        self.tabs = QTabWidget()

        # Text extraction tab
        self._create_text_tab()

        # Date extraction tab
        self._create_date_tab()

        self.tabs.addTab(self.text_tab, "Text")
        self.tabs.addTab(self.date_tab, "Date/Time")

        layout.addWidget(self.tabs)

        # Output options
        output_group = QGroupBox("Output Column")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Name:"), 0, 0)
        self.output_col_edit = QLineEdit("extracted")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        layout.addWidget(output_group)

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

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.extract_btn = create_primary_button("Extract")
        self.extract_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.extract_btn)

        layout.addLayout(btn_layout)

    def _create_text_tab(self):
        """Create text extraction tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        options_group = QGroupBox("Text Extraction")
        options_layout = QVBoxLayout(options_group)

        self.text_extract_type = QButtonGroup()

        text_options = [
            ("First N Characters", 1),
            ("Last N Characters", 2),
            ("Characters from Position", 3),
            ("Between Characters", 4),
        ]

        for label, value in text_options:
            radio = QRadioButton(label)
            self.text_extract_type.addButton(radio, value)
            options_layout.addWidget(radio)
            if value == 1:
                radio.setChecked(True)

        # Store the radio buttons for reference
        self.text_radio_buttons = {1: "first_n", 2: "last_n", 3: "from_pos", 4: "between"}

        # Parameters
        params_layout = QGridLayout()

        params_layout.addWidget(QLabel("Number/Position:"), 0, 0)
        self.text_param = QSpinBox()
        self.text_param.setRange(0, 1000)
        self.text_param.setValue(3)
        params_layout.addWidget(self.text_param, 0, 1)

        params_layout.addWidget(QLabel("End Position:"), 1, 0)
        self.text_param2 = QSpinBox()
        self.text_param2.setRange(0, 1000)
        self.text_param2.setValue(5)
        params_layout.addWidget(self.text_param2, 1, 1)

        options_layout.addLayout(params_layout)
        layout.addWidget(options_group)
        layout.addStretch()

        self.text_tab = tab

    def _create_date_tab(self):
        """Create date extraction tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        options_group = QGroupBox("Date/Time Extraction")
        options_layout = QVBoxLayout(options_group)

        self.date_extract_type = QButtonGroup()

        date_options = [
            ("Year", 1),
            ("Quarter", 2),
            ("Month (Number)", 3),
            ("Month Name", 4),
            ("Day of Month", 5),
            ("Day of Week", 6),
            ("Day Name", 7),
            ("Week of Year", 8),
            ("Hour", 9),
            ("Minute", 10),
            ("Second", 11),
            ("Day of Year", 12),
            ("Is Weekend", 13),
            ("Days Until Today", 14),
        ]

        for label, value in date_options:
            radio = QRadioButton(label)
            self.date_extract_type.addButton(radio, value)
            options_layout.addWidget(radio)
            if value == 1:
                radio.setChecked(True)

        # Store the radio buttons for reference
        self.date_radio_buttons = {
            1: "year", 2: "quarter", 3: "month_num", 4: "month_name", 5: "day",
            6: "dow", 7: "dow_name", 8: "week", 9: "hour", 10: "minute",
            11: "second", 12: "doy", 13: "is_weekend", 14: "days_until"
        }

        layout.addWidget(options_group)
        layout.addStretch()

        self.date_tab = tab

    def get_parameters(self) -> dict:
        """Get the extract parameters"""
        column = self.column_selector.get_column()
        tab_index = self.tabs.currentIndex()

        params = {
            "column": column,
            "output_column": self.output_col_edit.text() or "extracted",
        }

        if tab_index == 0:  # Text
            extract_type_id = self.text_extract_type.checkedId()
            params["extract_type"] = self.text_radio_buttons.get(extract_type_id, "first_n")
            params["param1"] = self.text_param.value()
            params["param2"] = self.text_param2.value()
        else:  # Date
            extract_type_id = self.date_extract_type.checkedId()
            params["extract_type"] = self.date_radio_buttons.get(extract_type_id, "year")

        return params

    def validate(self) -> bool:
        """Validate parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column.")
            return False

        tab_index = self.tabs.currentIndex()

        if tab_index == 0:  # Text
            if column in self.original_df.columns:
                dtype = self.original_df[column].dtype
                if dtype not in [pl.Utf8]:
                    QMessageBox.warning(self, "Validation Error",
                                      "Selected column must be text type.")
                    return False
        else:  # Date
            if column in self.original_df.columns:
                dtype = self.original_df[column].dtype
                if dtype not in [pl.Date, pl.Datetime]:
                    QMessageBox.warning(self, "Validation Error",
                                      "Selected column must be a date/datetime type.")
                    return False

        return True

    def preview(self):
        """Generate preview of extraction"""
        try:
            params = self.get_parameters()
            column = params["column"]
            output_col = params["output_column"]
            tab_index = self.tabs.currentIndex()

            if not column:
                return

            # Get data
            col_data = self.original_df[column].to_list()

            if tab_index == 0:  # Text extraction
                result = self._extract_text(col_data, params)
            else:  # Date extraction
                result = self._extract_date(col_data, params)

            preview_df = self.original_df[:10].clone()
            preview_df = preview_df.with_columns(
                pl.Series(name=output_col, values=result[:10])
            )
            self.preview_table.load_dataframe(preview_df)

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

    def _extract_text(self, data: list, params: dict) -> list:
        """Extract text based on parameters"""
        extract_type = params.get("extract_type", "first_n")
        param1 = params.get("param1", 3)
        param2 = params.get("param2", 5)

        result = []
        for val in data:
            if not val:
                result.append("")
                continue

            val = str(val)

            if extract_type == "first_n":
                result.append(val[:param1])
            elif extract_type == "last_n":
                result.append(val[-param1:] if len(val) >= param1 else val)
            elif extract_type == "from_pos":
                end = param2 if param2 > param1 else len(val)
                start = min(param1, len(val))
                end = min(end, len(val))
                result.append(val[start:end])
            elif extract_type == "between":
                # Find content between param1 and param2 characters
                start_char = chr(param1) if param1 < 128 else ""
                end_char = chr(param2) if param2 < 128 else ""
                if start_char and end_char and start_char in val:
                    try:
                        start_idx = val.index(start_char) + 1
                        end_idx = val.index(end_char, start_idx)
                        result.append(val[start_idx:end_idx])
                    except ValueError:
                        result.append("")
                else:
                    result.append("")
            else:
                result.append(val)

        return result

    def _extract_date(self, data: list, params: dict) -> list:
        """Extract date components"""
        from datetime import datetime

        extract_type = params.get("extract_type", "year")
        result = []

        for val in data:
            if val is None:
                result.append(None)
                continue

            # Parse date if string
            if isinstance(val, str):
                try:
                    val = datetime.fromisoformat(val.replace('Z', '+00:00'))
                except ValueError:
                    result.append(None)
                    continue

            if not isinstance(val, datetime):
                result.append(None)
                continue

            if extract_type == "year":
                result.append(val.year)
            elif extract_type == "quarter":
                result.append((val.month - 1) // 3 + 1)
            elif extract_type == "month_num":
                result.append(val.month)
            elif extract_type == "month_name":
                result.append(val.strftime("%B"))
            elif extract_type == "day":
                result.append(val.day)
            elif extract_type == "dow":
                result.append(val.weekday() + 1)  # Monday = 1
            elif extract_type == "dow_name":
                result.append(val.strftime("%A"))
            elif extract_type == "week":
                result.append(val.isocalendar()[1])
            elif extract_type == "hour":
                result.append(val.hour)
            elif extract_type == "minute":
                result.append(val.minute)
            elif extract_type == "second":
                result.append(val.second)
            elif extract_type == "doy":
                result.append(val.timetuple().tm_yday)
            elif extract_type == "is_weekend":
                result.append(val.weekday() >= 5)
            elif extract_type == "days_until":
                today = datetime.now()
                delta = val - today
                result.append(delta.days)
            else:
                result.append(None)

        return result

    def apply_extraction(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply extraction to dataframe"""
        params = self.get_parameters()
        column = params["column"]
        output_col = params["output_column"]
        tab_index = self.tabs.currentIndex()

        col_data = df[column].to_list()

        if tab_index == 0:  # Text
            result = self._extract_text(col_data, params)
        else:  # Date
            result = self._extract_date(col_data, params)

        return df.with_columns(
            pl.Series(name=output_col, values=result)
        )
