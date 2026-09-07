"""
Extract Dialog for CAATmaster
Extract a substring from a text column (LEFT/RIGHT/MID-style).
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QCheckBox, QGroupBox, QWidget,
    QMessageBox, QLineEdit, QRadioButton, QButtonGroup, QSpinBox
)
from PySide6.QtCore import Qt, QTimer

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button


class ExtractDialog(BaseModal):
    """
    Dialog for extracting a substring from a text column.

    Shared by three operation_ids (text_extract_first, text_extract_last,
    text_extract_middle), each dispatching to its own real DataProcessor
    method (extract_first_chars/extract_last_chars/extract_middle_chars) -
    operation_id alone decides which one actually runs on Apply, the same
    way AnomalyDetectionDialog's operation_id decides which algorithm
    runs there.

    This dialog used to also offer "Between Characters" (no real
    operation behind it - previewable, never applicable) and an entire
    second "Date/Time Extraction" tab with 14 more choices (Year,
    Quarter, Month Name, ...), none of which any operation_id in
    TransformationDialogFactory.DIALOG_MAPPING ever routed to this class
    for - real date-part extraction (datetime_year, datetime_month, ...)
    is handled entirely by the generic, registry-schema-driven dialog
    instead. Both were removed rather than wired up: the real gap
    reported was that this dialog's own "Number/Position" and "End
    Position" spinboxes didn't match extract_first_chars/
    extract_last_chars/extract_middle_chars's real num_chars/start_pos
    parameter names at all, so every real "Extract" click silently used
    those methods' defaults (num_chars=1, start_pos=1) regardless of
    what was configured - a much narrower, already-serious problem that
    didn't need a second, unrelated feature invented to fix it.
    """

    _MODE_BY_OPERATION_ID = {
        "text_extract_first": "first_n",
        "text_extract_last": "last_n",
        "text_extract_middle": "from_pos",
    }

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None,
                 operation_id: str = None):
        self.original_df = dataframe
        self.locked_mode = self._MODE_BY_OPERATION_ID.get(operation_id, "first_n")
        super().__init__("Extract Values", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(600, 500)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'column_selector') and column_name:
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_extracted")
            QTimer.singleShot(100, self.preview)

    def _on_column_selected(self, column_name: str):
        self.set_selected_column(column_name)

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

        # Extraction mode - locked to whichever operation_id this dialog
        # was opened for (see class docstring): only one is ever real for
        # a given menu action, so only that one is offered.
        options_group = QGroupBox("Text Extraction")
        options_layout = QVBoxLayout(options_group)

        self.text_extract_type = QButtonGroup()
        text_options = [
            ("First N Characters", "first_n"),
            ("Last N Characters", "last_n"),
            ("Characters from Position", "from_pos"),
        ]
        for label, value in text_options:
            radio = QRadioButton(label)
            radio.setProperty("mode_value", value)
            self.text_extract_type.addButton(radio)
            options_layout.addWidget(radio)
            if value == self.locked_mode:
                radio.setChecked(True)
            else:
                radio.setEnabled(False)

        # Parameters - label text adapts to the locked mode, since
        # "Start Position" only means something for "from_pos" and
        # "Number of Characters" means something for all three.
        params_layout = QGridLayout()

        self.param1_label = QLabel()
        params_layout.addWidget(self.param1_label, 0, 0)
        self.text_param = QSpinBox()
        self.text_param.setRange(1, 1000)
        params_layout.addWidget(self.text_param, 0, 1)

        self.param2_label = QLabel("Number of Characters:")
        params_layout.addWidget(self.param2_label, 1, 0)
        self.text_param2 = QSpinBox()
        self.text_param2.setRange(1, 1000)
        self.text_param2.setValue(5)
        params_layout.addWidget(self.text_param2, 1, 1)

        if self.locked_mode == "from_pos":
            self.param1_label.setText("Start Position (1 = first character):")
            self.text_param.setValue(1)
        else:
            self.param1_label.setText("Number of Characters:")
            self.text_param.setValue(3)
            self.param2_label.setVisible(False)
            self.text_param2.setVisible(False)

        options_layout.addLayout(params_layout)
        layout.addWidget(options_group)

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

    def get_parameters(self) -> dict:
        """The parameters actually sent to DataProcessor - both for this
        dialog's own preview() below and, via operation_id-based
        dispatch, for the real applied operation. Key names
        (num_chars/start_pos) match extract_first_chars/
        extract_last_chars/extract_middle_chars exactly - an earlier
        version used generic "param1"/"param2" names that matched
        nothing, so every real Extract click silently ran with those
        methods' own defaults regardless of what was configured here."""
        column = self.column_selector.get_column()
        params = {
            "column": column,
            "output_column": self.output_col_edit.text() or "extracted",
        }
        if self.locked_mode == "from_pos":
            params["start_pos"] = self.text_param.value()
            params["num_chars"] = self.text_param2.value()
        else:
            params["num_chars"] = self.text_param.value()
        return params

    def validate(self) -> bool:
        """Validate parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column.")
            return False

        if column in self.original_df.columns:
            dtype = self.original_df[column].dtype
            if dtype not in [pl.Utf8]:
                QMessageBox.warning(self, "Validation Error",
                                  "Selected column must be text type.")
                return False

        return True

    def preview(self):
        """Generate a preview by calling the exact same DataProcessor
        method Apply will call - see get_parameters()'s docstring for
        why that used not to be true."""
        from core.data_processor import DataProcessor

        try:
            params = self.get_parameters()
            column = params["column"]
            output_column = params["output_column"]

            if not column:
                return

            processor = DataProcessor()
            if self.locked_mode == "first_n":
                result = processor.extract_first_chars(
                    self.original_df, column=column, num_chars=params["num_chars"], output_col=output_column
                )
            elif self.locked_mode == "last_n":
                result = processor.extract_last_chars(
                    self.original_df, column=column, num_chars=params["num_chars"], output_col=output_column
                )
            else:  # from_pos
                result = processor.extract_middle_chars(
                    self.original_df, column=column,
                    start_pos=params["start_pos"], num_chars=params["num_chars"],
                    output_col=output_column,
                )

            self.preview_table.load_dataframe(result.head(10))

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")
