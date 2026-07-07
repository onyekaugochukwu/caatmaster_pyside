"""
Split Columns by Delimiter Dialog
Provides UI for splitting a column into multiple columns based on a delimiter.
"""
from typing import Optional
import polars as pl

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QSpinBox, QLineEdit, QPushButton, QMessageBox,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QScrollArea, QWidget
)
from PySide6.QtCore import Qt

from ..components.common_modals import BaseModal, PreviewTable, create_primary_button


class SplitColumnsDialog(BaseModal):
    """Dialog for splitting columns by delimiter with preview."""

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        # Initialize with just QDialog to avoid BaseModal's _setup_ui being called
        super(BaseModal, self).__init__(parent if parent else None)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.setWindowTitle("Split Columns by Delimiter")
        self.setModal(True)
        self.dataframe = dataframe
        self.selected_column = selected_column
        self.setMinimumSize(600, 500)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the dialog UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        # Content widget inside scroll area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Column to Split")
        col_layout = QFormLayout(col_group)
        col_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.column_combo = QComboBox()
        self.column_combo.addItems(self.dataframe.columns)
        if self.selected_column:
            self.column_combo.setCurrentText(self.selected_column)
        self.column_combo.currentTextChanged.connect(self._update_preview)
        col_layout.addRow("Select Column:", self.column_combo)

        content_layout.addWidget(col_group)

        # Delimiter settings
        delim_group = QGroupBox("Delimiter Settings")
        delim_layout = QFormLayout(delim_group)
        delim_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.delimiter_combo = QComboBox()
        self.delimiter_combo.addItems(["space", "comma", "tab", "period", "asterisk", "custom"])
        self.delimiter_combo.setCurrentText("space")
        self.delimiter_combo.currentTextChanged.connect(self._on_delimiter_changed)
        delim_layout.addRow("Delimiter:", self.delimiter_combo)

        self.custom_delim_edit = QLineEdit()
        self.custom_delim_edit.setPlaceholderText("Enter custom delimiter character(s)")
        self.custom_delim_edit.setEnabled(False)
        delim_layout.addRow("Custom Delimiter:", self.custom_delim_edit)

        self.max_splits_spin = QSpinBox()
        self.max_splits_spin.setRange(-1, 100)
        self.max_splits_spin.setValue(-1)
        self.max_splits_spin.setSpecialValueText("-1 (all)")
        delim_layout.addRow("Max Splits:", self.max_splits_spin)

        content_layout.addWidget(delim_group)

        # Output column naming
        naming_group = QGroupBox("Output Column Names")
        naming_layout = QFormLayout(naming_group)
        naming_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.naming_combo = QComboBox()
        self.naming_combo.addItems(["Auto-generate (column_1, column_2...)", "Use custom prefix"])
        self.naming_combo.currentTextChanged.connect(self._on_naming_changed)
        naming_layout.addRow("Naming Pattern:", self.naming_combo)

        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("e.g., part_")
        self.prefix_edit.setEnabled(False)
        self.prefix_edit.textChanged.connect(self._update_preview)
        naming_layout.addRow("Custom Prefix:", self.prefix_edit)

        content_layout.addWidget(naming_group)

        # Preview
        preview_group = QGroupBox("Preview (First 10 rows)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        content_layout.addWidget(preview_group)

        # Set content widget in scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Button row (outside scroll area)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = create_primary_button("Split Column")
        self.apply_btn.clicked.connect(self._apply_split)
        btn_layout.addWidget(self.apply_btn)

        main_layout.addLayout(btn_layout)

        # Initial preview
        self._update_preview()

    def _connect_signals(self):
        """Connect signals - override if needed"""
        pass

    def _on_delimiter_changed(self):
        """Enable/disable custom delimiter input based on selection"""
        is_custom = self.delimiter_combo.currentText() == "custom"
        self.custom_delim_edit.setEnabled(is_custom)
        self._update_preview()

    def _on_naming_changed(self):
        """Enable/disable custom prefix input based on naming selection"""
        use_custom = self.naming_combo.currentText().startswith("Use custom")
        self.prefix_edit.setEnabled(use_custom)
        self._update_preview()

    def _get_delimiter(self) -> str:
        """Get the actual delimiter character"""
        delimiter = self.delimiter_combo.currentText()
        delimiter_map = {
            'space': ' ',
            'comma': ',',
            'tab': '\t',
            'period': '.',
            'asterisk': '*'
        }
        if delimiter == 'custom':
            return self.custom_delim_edit.text() or ' '
        return delimiter_map.get(delimiter, delimiter)

    def _get_output_prefix(self) -> str:
        """Get the output column prefix"""
        if self.naming_combo.currentText().startswith("Use custom"):
            return self.prefix_edit.text() or f"{self.column_combo.currentText()}_"
        return f"{self.column_combo.currentText()}_"

    def _update_preview(self):
        """Update preview table"""
        column = self.column_combo.currentText()
        if not column:
            return

        try:
            delimiter = self._get_delimiter()
            max_splits = self.max_splits_spin.value()

            # Create preview with split columns
            preview_df = self.dataframe.head(10).clone()

            # Perform the split
            if max_splits > 0:
                split_parts = preview_df[column].str.splitn(delimiter, max_splits + 1)
            else:
                split_parts = preview_df[column].str.split(delimiter)

            # Get max number of parts
            num_parts = split_parts.list.len().max()
            num_cols = max(min(num_parts, 10), 2)  # At least 2, at most 10

            # Create output column names
            prefix = self._get_output_prefix()
            output_cols = [f"{prefix}{i+1}" for i in range(num_cols)]

            # Build preview dataframe
            for i, col_name in enumerate(output_cols):
                preview_df = preview_df.with_columns(
                    split_parts.list.get(i).alias(col_name)
                )

            # Show only output columns
            display_df = preview_df.select(output_cols)
            self.preview_table.load_dataframe(display_df)

        except Exception as e:
            self.preview_table.load_dataframe(self.dataframe.head(10).select([column]))

    def _apply_split(self):
        """Validate and accept the split"""
        column = self.column_combo.currentText()
        if not column:
            QMessageBox.warning(self, "Warning", "Please select a column to split.")
            return

        delimiter = self._get_delimiter()
        max_splits = self.max_splits_spin.value()

        if not delimiter:
            QMessageBox.warning(self, "Warning", "Please specify a delimiter.")
            return

        self.current_params = {
            "column": column,
            "delimiter": self.delimiter_combo.currentText(),
            "custom_delimiter": self.custom_delim_edit.text() if self.delimiter_combo.currentText() == "custom" else None,
            "max_splits": max_splits,
            "output_prefix": self._get_output_prefix()
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def validate(self) -> bool:
        return bool(self.column_combo.currentText())
