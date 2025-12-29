"""
Split Column Dialog for CAATmaster
Split text columns by delimiter, characters, or positions
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QCheckBox, QGroupBox, QWidget,
    QMessageBox, QLineEdit, QRadioButton, QButtonGroup, QTabWidget, QWidget
)
from PySide6.QtCore import Qt

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector


class SplitColumnDialog(BaseModal):
    """
    Dialog for splitting text columns into multiple columns
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Split Column", dataframe, parent)
        self.setMinimumSize(600, 500)

    def _setup_ui(self):
        """Setup the split column dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Column to Split")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Source Column:")
        col_layout.addWidget(self.column_selector)

        layout.addWidget(col_group)

        # Split method tabs
        self.tabs = QTabWidget()

        # By delimiter tab
        self._create_delimiter_tab()

        # By number of characters tab
        self._create_chars_tab()

        # By position tab
        self._create_position_tab()

        self.tabs.addTab(self.delimiter_tab, "By Delimiter")
        self.tabs.addTab(self.chars_tab, "By Characters")
        self.tabs.addTab(self.position_tab, "By Position")

        layout.addWidget(self.tabs)

        # Output options
        output_group = QGroupBox("Output Options")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Prefix:"), 0, 0)
        self.prefix_edit = QLineEdit("split")
        output_layout.addWidget(self.prefix_edit, 0, 1)

        self.remove_original = QCheckBox("Remove original column")
        output_layout.addWidget(self.remove_original, 1, 0, 1, 2)

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

        self.split_btn = QPushButton("Split Column")
        self.split_btn.setStyleSheet("""
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
        self.split_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.split_btn)

        layout.addLayout(btn_layout)

    def _create_delimiter_tab(self):
        """Create delimiter-based split tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        options_group = QGroupBox("Delimiter Options")
        options_layout = QGridLayout(options_group)

        # Delimiter type
        options_layout.addWidget(QLabel("Delimiter:"), 0, 0)
        self.delimiter_edit = QLineEdit(",")
        self.delimiter_edit.setPlaceholderText("e.g., , ; - space")
        options_layout.addWidget(self.delimiter_edit, 0, 1)

        # Custom delimiter
        self.custom_delim_radio = QRadioButton("Custom")
        self.custom_delim_radio.setChecked(True)
        options_layout.addWidget(self.custom_delim_radio, 1, 0)

        self.space_radio = QRadioButton("Space")
        options_layout.addWidget(self.space_radio, 1, 1)

        self.tab_radio = QRadioButton("Tab")
        options_layout.addWidget(self.tab_radio, 2, 0)

        # Limit splits
        options_layout.addWidget(QLabel("Max Splits (0 = all):"), 2, 1)
        self.max_splits_spin = QSpinBox()
        self.max_splits_spin.setRange(0, 100)
        self.max_splits_spin.setValue(0)
        options_layout.addWidget(self.max_splits_spin, 2, 2)

        layout.addWidget(options_group)
        layout.addStretch()

        self.delimiter_tab = tab

    def _create_chars_tab(self):
        """Create character count split tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        options_group = QGroupBox("Character Count Options")
        options_layout = QGridLayout(options_group)

        options_layout.addWidget(QLabel("Characters per part:"), 0, 0)
        self.chars_per_part = QSpinBox()
        self.chars_per_part.setRange(1, 100)
        self.chars_per_part.setValue(2)
        options_layout.addWidget(self.chars_per_part, 0, 1)

        self.from_start = QRadioButton("From start")
        self.from_start.setChecked(True)
        options_layout.addWidget(self.from_start, 1, 0)

        self.from_end = QRadioButton("From end")
        options_layout.addWidget(self.from_end, 1, 1)

        layout.addWidget(options_group)
        layout.addStretch()

        self.chars_tab = tab

    def _create_position_tab(self):
        """Create position-based split tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        options_group = QGroupBox("Position Options")
        options_layout = QGridLayout(options_group)

        options_layout.addWidget(QLabel("Split at position:"), 0, 0)
        self.split_position = QSpinBox()
        self.split_position.setRange(1, 1000)
        self.split_position.setValue(3)
        options_layout.addWidget(self.split_position, 0, 1)

        # Keep/drop split character
        self.keep_split = QRadioButton("Keep split character as separator")
        self.keep_split.setChecked(True)
        options_layout.addWidget(self.keep_split, 1, 0, 1, 2)

        self.drop_split = QRadioButton("Drop split character")
        options_layout.addWidget(self.drop_split, 2, 0, 1, 2)

        layout.addWidget(options_group)
        layout.addStretch()

        self.position_tab = tab

    def get_parameters(self) -> dict:
        """Get the split parameters"""
        tab_index = self.tabs.currentIndex()

        params = {
            "column": self.column_selector.get_column(),
            "method": ["delimiter", "chars", "position"][tab_index],
            "prefix": self.prefix_edit.text() or "split",
            "remove_original": self.remove_original.isChecked(),
        }

        if params["method"] == "delimiter":
            if self.custom_delim_radio.isChecked():
                params["delimiter"] = self.delimiter_edit.text()
            elif self.space_radio.isChecked():
                params["delimiter"] = " "
            elif self.tab_radio.isChecked():
                params["delimiter"] = "\t"
            params["max_splits"] = self.max_splits_spin.value()

        elif params["method"] == "chars":
            params["chars_per_part"] = self.chars_per_part.value()
            params["from_end"] = self.from_end.isChecked()

        elif params["method"] == "position":
            params["position"] = self.split_position.value()
            params["keep_separator"] = self.keep_split.isChecked()

        return params

    def validate(self) -> bool:
        """Validate parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column to split.")
            return False

        if column in self.original_df.columns:
            dtype = self.original_df[column].dtype
            if dtype not in [pl.Utf8, pl.Str]:
                QMessageBox.warning(self, "Validation Error",
                                  "Selected column must be text type.")
                return False

        return True

    def preview(self):
        """Generate preview of split"""
        try:
            params = self.get_parameters()
            column = params["column"]
            prefix = params["prefix"]

            if not column:
                return

            # Get data
            col_data = self.original_df[column].to_list()

            # Apply split based on method
            if params["method"] == "delimiter":
                delimiter = params.get("delimiter", ",")
                max_splits = params.get("max_splits", 0)

                # Get max number of parts
                max_parts = 0
                for val in col_data:
                    if val:
                        parts = val.split(delimiter, max_splits if max_splits > 0 else -1)
                        max_parts = max(max_parts, len(parts))

                # Create preview
                preview_data = {column: col_data[:10]}
                for i in range(max_parts):
                    preview_data[f"{prefix}_{i+1}"] = [
                        val.split(delimiter, max_splits if max_splits > 0 else -1)[i]
                        if val and i < len(val.split(delimiter)) else ""
                        for val in col_data[:10]
                    ]

            elif params["method"] == "chars":
                chars_per = params.get("chars_per_part", 2)
                from_end = params.get("from_end", False)

                preview_data = {column: col_data[:10]}
                part_idx = 0
                for val in col_data[:10]:
                    if val:
                        if from_end:
                            parts = [val[max(0, i-chars_per):i] for i in range(len(val), 0, -chars_per)][::-1]
                        else:
                            parts = [val[i:i+chars_per] for i in range(0, len(val), chars_per)]
                    else:
                        parts = []
                    for j, part in enumerate(parts):
                        col_name = f"{prefix}_{j+1}"
                        if col_name not in preview_data:
                            preview_data[col_name] = [""] * 10
                        preview_data[col_name][part_idx] = part
                    part_idx += 1

            else:  # position
                pos = params.get("position", 3)
                keep_sep = params.get("keep_separator", True)

                preview_data = {column: col_data[:10]}
                for val in col_data[:10]:
                    if val and len(val) >= pos:
                        if keep_sep:
                            parts = [val[:pos], val[pos:]]
                        else:
                            parts = [val[:pos], val[pos:]]
                    else:
                        parts = [val or "", ""]

                    for j, part in enumerate(parts):
                        col_name = f"{prefix}_{j+1}"
                        if col_name not in preview_data:
                            preview_data[col_name] = [""] * 10
                        preview_data[col_name][col_data.index(val)] = part

            preview_df = pl.DataFrame(preview_data)
            self.preview_table.load_dataframe(preview_df)

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")
