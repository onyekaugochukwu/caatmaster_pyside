"""
Table operation dialogs for CAATmaster
Includes: Split Sheet, Transpose, Combine Worksheets, Query Sheet, Select N Rows
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
    QFrame, QSplitter, QRadioButton, QButtonGroup, QProgressBar, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QFont

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector


class SplitSheetDialog(BaseModal):
    """Dialog for splitting a dataset into multiple sheets/tables by unique values"""

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        self.selected_column = selected_column
        self._preview_dfs = {}  # Store preview dataframes for each unique value
        super().__init__("Split Sheet", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(600, 500)

    def _setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Group by column
        col_group = QGroupBox("Split By Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column to Split By:")
        col_layout.addWidget(self.column_selector)

        # Connect to combo box currentIndexChanged signal
        self.column_selector.combo.currentIndexChanged.connect(self._on_column_changed)

        layout.addWidget(col_group)

        # Preview section - showing unique values and sample data
        preview_group = QGroupBox("Unique Values Preview")
        preview_layout = QVBoxLayout(preview_group)

        # Split view for unique values and sample data
        split_layout = QHBoxLayout()
        split_layout.setSpacing(10)

        # Left: List of unique values that will become datasets
        self.values_list = QListWidget()
        self.values_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.values_list.itemClicked.connect(self._on_value_selected)
        split_layout.addWidget(self.values_list, 1)

        # Right: Preview of filtered data for selected value
        self.preview_table = PreviewTable(max_rows=10)
        split_layout.addWidget(self.preview_table, 2)

        preview_layout.addLayout(split_layout)
        layout.addWidget(preview_group)

        # Info label
        self.info_label = QLabel("Select a column to see unique values")
        self.info_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 12px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.info_label)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Split Sheet")
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
        self.apply_btn.clicked.connect(self._apply_split)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _on_column_changed(self):
        """Called when the column selection changes"""
        column = self.column_selector.get_column()
        if not column:
            self.values_list.clear()
            self.preview_table.clear()
            self.info_label.setText("Select a column to see unique values")
            return

        # Get unique values and sort them
        unique_values = self.original_df[column].unique().to_list()
        unique_values.sort()

        self._preview_dfs.clear()
        self.values_list.clear()

        for value in unique_values:
            # Filter dataframe for this value
            filtered_df = self.original_df.filter(pl.col(column) == value)
            self._preview_dfs[str(value)] = filtered_df

            # Create list item with row count
            item = QListWidgetItem(f"{value} ({len(filtered_df):,} rows)")
            item.setData(Qt.UserRole, str(value))
            self.values_list.addItem(item)

        # Update info
        num_datasets = len(unique_values)
        self.info_label.setText(
            f"Splitting by '{column}' will create {num_datasets} new datasets. "
            f"Total rows: {len(self.original_df):,}"
        )

        # Select first item
        if self.values_list.count() > 0:
            self.values_list.setCurrentRow(0)

    def _on_value_selected(self, item):
        """Called when a value is selected from the list"""
        value = item.data(Qt.UserRole)
        if value in self._preview_dfs:
            self.preview_table.load_dataframe(self._preview_dfs[value])

    def _apply_split(self):
        """Validate and accept the split"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Warning", "Please select a column to split by.")
            return

        if not self._preview_dfs:
            QMessageBox.warning(self, "Warning", "No unique values found.")
            return

        self.current_params = {
            "column": column,
            "datasets": list(self._preview_dfs.items())  # List of (name, dataframe) tuples
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def get_split_datasets(self) -> List[tuple]:
        """Get the list of datasets to create - returns list of (name, dataframe)"""
        params = self.get_parameters()
        return params.get("datasets", [])

    def validate(self) -> bool:
        return bool(self.column_selector.get_column())


class TransposeDialog(BaseModal):
    """Dialog for transposing rows and columns"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Transpose", dataframe, parent)
        self.setMinimumSize(700, 500)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Columns to transpose
        col_group = QGroupBox("Columns to Transpose")
        col_layout = QVBoxLayout(col_group)

        # Selection type
        selection_layout = QHBoxLayout()
        self.selection_group = QButtonGroup()
        self.all_radio = QRadioButton("All Columns")
        self.all_radio.setChecked(True)
        self.all_radio.toggled.connect(self._on_selection_changed)
        selection_layout.addWidget(self.all_radio)
        self.selection_group.addButton(self.all_radio)

        self.selected_radio = QRadioButton("Selected Columns")
        selection_layout.addWidget(self.selected_radio)
        self.selection_group.addButton(self.selected_radio)
        selection_layout.addStretch()
        col_layout.addLayout(selection_layout)

        # Column list
        self.columns_list = QListWidget()
        self.columns_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.columns_list.setEnabled(False)
        for col in self.original_df.columns:
            self.columns_list.addItem(col)
        col_layout.addWidget(self.columns_list)

        layout.addWidget(col_group)

        # Index column
        index_group = QGroupBox("Index Column")
        index_layout = QVBoxLayout(index_group)

        self.include_index_check = QCheckBox("Include index column")
        self.include_index_check.setChecked(True)
        self.include_index_check.toggled.connect(self._on_include_index_changed)
        index_layout.addWidget(self.include_index_check)

        self.index_edit = QLineEdit("index")
        self.index_edit.setEnabled(True)
        index_layout.addWidget(self.index_edit)

        layout.addWidget(index_group)

        # Preview
        preview_group = QGroupBox("Preview (First 5 rows)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(150)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Transpose")
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
        self.apply_btn.clicked.connect(self._apply_transpose)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _on_selection_changed(self):
        """Enable/disable column list based on selection type"""
        self.columns_list.setEnabled(self.selected_radio.isChecked())

    def _on_include_index_changed(self):
        """Enable/disable index name field"""
        self.index_edit.setEnabled(self.include_index_check.isChecked())

    def _apply_transpose(self):
        """Validate and accept transpose"""
        if self.selected_radio.isChecked():
            selected = [self.columns_list.item(i).text()
                       for i in range(self.columns_list.count())
                       if self.columns_list.item(i).isSelected()]
            if not selected:
                QMessageBox.warning(self, "Warning", "Please select at least one column.")
                return
            columns_to_transpose = selected
        else:
            columns_to_transpose = self.original_df.columns

        if len(columns_to_transpose) < 2:
            QMessageBox.warning(self, "Warning", "Need at least 2 columns to transpose.")
            return

        self.current_params = {
            "columns_to_transpose": columns_to_transpose,
            "include_index": self.include_index_check.isChecked(),
            "index_column": self.index_edit.text() if self.include_index_check.isChecked() else ""
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        cols = params["columns_to_transpose"]

        # Transpose using polars
        transposed = df.select(cols).transpose(
            include_header=params["include_index"],
            header_name=params.get("index_column", "index") if params["include_index"] else None
        )
        return transposed


class JoinDatasetsDialog(BaseModal):
    """Dialog for joining two datasets using various join types"""

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        self.selected_column = selected_column
        super().__init__("Join Datasets", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(650, 500)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Join type selection
        join_group = QGroupBox("Join Type")
        join_layout = QVBoxLayout(join_group)

        self.join_type_group = QButtonGroup()
        join_types = [
            ("Left Join", "Keep all rows from left dataset, matching right rows"),
            ("Right Join", "Keep all rows from right dataset, matching left rows"),
            ("Inner Join", "Keep only rows that match in both datasets"),
            ("Outer Join", "Keep all rows from both datasets"),
            ("Cross Join", "Cartesian product of both datasets")
        ]

        self.join_radios = {}
        for i, (join_name, description) in enumerate(join_types):
            radio = QRadioButton(f"{join_name}")
            radio.setToolTip(description)
            if i == 0:
                radio.setChecked(True)
            self.join_type_group.addButton(radio)
            self.join_radios[join_name.lower().replace(" ", "_")] = radio
            join_layout.addWidget(radio)

        layout.addWidget(join_group)

        # Left dataset (current)
        left_group = QGroupBox("Left Dataset (Current)")
        left_layout = QFormLayout(left_group)

        self.left_key_combo = QComboBox()
        self.left_key_combo.addItems(self.original_df.columns)
        if self.selected_column:
            self.left_key_combo.setCurrentText(self.selected_column)
        left_layout.addRow("Join Key:", self.left_key_combo)

        layout.addWidget(left_group)

        # Right dataset selection (simplified - enter dataset name)
        right_group = QGroupBox("Right Dataset")
        right_layout = QFormLayout(right_group)

        self.right_dataset_edit = QLineEdit()
        self.right_dataset_edit.setPlaceholderText("Enter dataset name from your project")
        right_layout.addRow("Dataset Name:", self.right_dataset_edit)

        self.right_key_combo = QComboBox()
        self.right_key_combo.setEditable(True)
        self.right_key_combo.addItems(self.original_df.columns)
        self.right_key_combo.setPlaceholderText("Enter or select column name")
        right_layout.addRow("Join Key:", self.right_key_combo)

        layout.addWidget(right_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("_right")
        self.suffix_edit.setText("_right")
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("Suffix for right columns:"))
        suffix_layout.addWidget(self.suffix_edit)
        suffix_layout.addStretch()
        options_layout.addLayout(suffix_layout)

        layout.addWidget(options_group)

        # Preview
        preview_group = QGroupBox("Preview (Left Dataset)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=5)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Join Datasets")
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
        self.apply_btn.clicked.connect(self._apply_join)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

        # Load preview
        self.preview_table.load_dataframe(self.original_df.head(5))

    def _apply_join(self):
        """Validate and accept join"""
        dataset_name = self.right_dataset_edit.text().strip()
        if not dataset_name:
            QMessageBox.warning(self, "Warning", "Please enter the dataset name to join with.")
            return

        right_key = self.right_key_combo.currentText().strip()
        if not right_key:
            QMessageBox.warning(self, "Warning", "Please enter or select the right join key.")
            return

        # Determine join type
        join_type = "left"
        for name, radio in self.join_radios.items():
            if radio.isChecked():
                join_type = name
                break

        self.current_params = {
            "right_dataset": dataset_name,
            "left_key": self.left_key_combo.currentText(),
            "right_key": right_key,
            "join_type": join_type,
            "suffix": self.suffix_edit.text() or "_right"
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})


class AppendDatasetsDialog(BaseModal):
    """Dialog for appending/stacking datasets vertically"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Append Datasets", dataframe, parent)
        self.setMinimumSize(550, 350)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Source datasets
        source_group = QGroupBox("Datasets to Append")
        source_layout = QFormLayout(source_group)

        self.datasets_edit = QLineEdit()
        self.datasets_edit.setPlaceholderText("dataset1, dataset2, ...")
        source_layout.addRow("Dataset Names:", self.datasets_edit)

        layout.addWidget(source_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.align_check = QCheckBox("Auto-align columns by name")
        self.align_check.setChecked(True)
        options_layout.addWidget(self.align_check)

        self.fill_check = QCheckBox("Fill missing columns with null")
        self.fill_check.setChecked(True)
        options_layout.addWidget(self.fill_check)

        layout.addWidget(options_group)

        # Preview
        preview_group = QGroupBox("Current Dataset Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel(f"Current dataset: {len(self.original_df)} rows, {len(self.original_df.columns)} columns")
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
            }
        """)
        preview_layout.addWidget(self.preview_label)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Append Datasets")
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
        self.apply_btn.clicked.connect(self._apply_append)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _apply_append(self):
        """Validate and accept append"""
        datasets_text = self.datasets_edit.text().strip()
        if not datasets_text:
            QMessageBox.warning(self, "Warning", "Please enter dataset names.")
            return

        datasets = [d.strip() for d in datasets_text.split(",") if d.strip()]
        if not datasets:
            QMessageBox.warning(self, "Warning", "Please enter valid dataset names.")
            return

        self.current_params = {
            "source_datasets": datasets,
            "align_columns": self.align_check.isChecked(),
            "fill_missing": self.fill_check.isChecked()
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})


class CombineSheetsDialog(BaseModal):
    """Dialog for combining/unioning multiple worksheets"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Combine Worksheets", dataframe, parent)
        self.setMinimumSize(600, 400)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Source datasets
        source_group = QGroupBox("Source Datasets")
        source_layout = QVBoxLayout(source_group)

        self.datasets_edit = QLineEdit()
        self.datasets_edit.setPlaceholderText("Enter dataset names separated by commas")
        source_layout.addWidget(QLabel("Datasets to Combine:"))
        source_layout.addWidget(self.datasets_edit)

        help_label = QLabel("Enter the names of datasets in your project to combine")
        help_label.setStyleSheet("color: #666; font-size: 11px;")
        source_layout.addWidget(help_label)

        layout.addWidget(source_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.align_check = QCheckBox("Auto-align columns by name")
        self.align_check.setChecked(True)
        options_layout.addWidget(self.align_check)

        self.fill_check = QCheckBox("Fill missing columns with null")
        options_layout.addWidget(self.fill_check)

        layout.addWidget(options_group)

        # Preview
        preview_group = QGroupBox("Current Dataset Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel(f"Current dataset: {len(self.original_df)} rows, {len(self.original_df.columns)} columns")
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
            }
        """)
        preview_layout.addWidget(self.preview_label)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Combine")
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
        self.apply_btn.clicked.connect(self._apply_combine)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _apply_combine(self):
        """Validate and accept combine"""
        datasets_text = self.datasets_edit.text().strip()
        if not datasets_text:
            QMessageBox.warning(self, "Warning", "Please enter dataset names.")
            return

        datasets = [d.strip() for d in datasets_text.split(",") if d.strip()]
        if not datasets:
            QMessageBox.warning(self, "Warning", "Please enter valid dataset names.")
            return

        self.current_params = {
            "source_datasets": datasets,
            "align_columns": self.align_check.isChecked(),
            "fill_missing": self.fill_check.isChecked()
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        # This would need access to other datasets - for now return original
        # In full implementation, this would union multiple datasets
        return df


class QuerySheetDialog(BaseModal):
    """Dialog for creating filtered/transformed views with formulas"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Query Sheet", dataframe, parent)
        self.setMinimumSize(700, 500)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Filter condition
        filter_group = QGroupBox("Filter Condition")
        filter_layout = QVBoxLayout(filter_group)

        filter_layout.addWidget(QLabel("Enter filter condition (leave empty for no filter):"))
        self.condition_edit = QLineEdit()
        self.condition_edit.setPlaceholderText("e.g., pl.col('Amount') > 1000")
        filter_layout.addWidget(self.condition_edit)

        # Column reference helper
        cols_layout = QHBoxLayout()
        cols_layout.addWidget(QLabel("Available columns:"))
        self.cols_combo = QComboBox()
        self.cols_combo.addItems(self.original_df.columns)
        self.cols_combo.currentTextChanged.connect(self._insert_column)
        cols_layout.addWidget(self.cols_combo)
        cols_layout.addStretch()
        filter_layout.addLayout(cols_layout)

        layout.addWidget(filter_group)

        # Sort options
        sort_group = QGroupBox("Sort Options")
        sort_layout = QGridLayout(sort_group)

        sort_layout.addWidget(QLabel("Sort By:"), 0, 0)
        self.sort_col_edit = QLineEdit()
        self.sort_col_edit.setPlaceholderText("Column name")
        sort_layout.addWidget(self.sort_col_edit, 0, 1)

        sort_layout.addWidget(QLabel("Order:"), 1, 0)
        self.sort_order_combo = QComboBox()
        self.sort_order_combo.addItems(["Ascending", "Descending"])
        sort_layout.addWidget(self.sort_order_combo, 1, 1)

        layout.addWidget(sort_group)

        # Column selection
        select_group = QGroupBox("Select Columns")
        select_layout = QVBoxLayout(select_group)

        self.all_cols_check = QCheckBox("Include all columns")
        self.all_cols_check.setChecked(True)
        self.all_cols_check.toggled.connect(self._on_all_cols_changed)
        select_layout.addWidget(self.all_cols_check)

        self.cols_list = QListWidget()
        self.cols_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for col in self.original_df.columns:
            self.cols_list.addItem(col)
        self.cols_list.setEnabled(False)
        select_layout.addWidget(self.cols_list)

        layout.addWidget(select_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        self.update_preview()
        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Apply Query")
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
        self.apply_btn.clicked.connect(self._apply_query)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _on_all_cols_changed(self):
        """Enable/disable column list"""
        self.cols_list.setEnabled(not self.all_cols_check.isChecked())

    def _insert_column(self, column: str):
        """Insert column name into condition"""
        self.condition_edit.insert(f"pl.col('{column}')")

    def update_preview(self):
        """Update preview table"""
        try:
            result_df = self._get_filtered_df()
            if self.all_cols_check.isChecked():
                preview_df = result_df.head(10)
            else:
                selected = [self.cols_list.item(i).text()
                           for i in range(self.cols_list.count())
                           if self.cols_list.item(i).isSelected()]
                if selected:
                    preview_df = result_df.select(selected).head(10)
                else:
                    preview_df = result_df.head(10)
            self.preview_table.load_dataframe(preview_df)
        except Exception as e:
            self.preview_table.load_dataframe(self.original_df.head(10))

    def _get_filtered_df(self) -> pl.DataFrame:
        """Get filtered dataframe based on current settings"""
        condition = self.condition_edit.text().strip()
        df = self.original_df.clone()

        if condition:
            try:
                df = df.filter(eval(condition))
            except Exception:
                pass  # Invalid condition, return unfiltered

        # Apply sort
        sort_col = self.sort_col_edit.text().strip()
        if sort_col:
            order = "ascending" if self.sort_order_combo.currentText() == "Ascending" else "descending"
            df = df.sort(sort_col, descending=(order == "descending"))

        return df

    def _apply_query(self):
        """Validate and accept query"""
        self.current_params = {
            "condition": self.condition_edit.text().strip(),
            "sort_by": self.sort_col_edit.text().strip(),
            "sort_order": "asc" if self.sort_order_combo.currentText() == "Ascending" else "desc",
            "select_columns": [] if self.all_cols_check.isChecked()
                           else [self.cols_list.item(i).text()
                                for i in range(self.cols_list.count())
                                if self.cols_list.item(i).isSelected()]
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        result_df = df.clone()

        # Apply filter
        if params.get("condition"):
            try:
                result_df = result_df.filter(eval(params["condition"]))
            except Exception:
                pass

        # Apply sort
        if params.get("sort_by"):
            result_df = result_df.sort(params["sort_by"],
                                       descending=(params.get("sort_order") == "desc"))

        # Select columns
        if params.get("select_columns"):
            result_df = result_df.select(params["select_columns"])

        return result_df


class SelectNRowsDialog(BaseModal):
    """Dialog for selecting first N, last N, or random N rows"""

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Select N Rows", dataframe, parent)
        self.setMinimumSize(500, 300)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Selection type
        type_group = QGroupBox("Selection Type")
        type_layout = QVBoxLayout(type_group)

        self.type_group = QButtonGroup()
        self.first_radio = QRadioButton("First N Rows")
        self.first_radio.setChecked(True)
        type_layout.addWidget(self.first_radio)
        self.type_group.addButton(self.first_radio)

        self.last_radio = QRadioButton("Last N Rows")
        type_layout.addWidget(self.last_radio)
        self.type_group.addButton(self.last_radio)

        self.random_radio = QRadioButton("Random N Rows")
        type_layout.addWidget(self.random_radio)
        self.type_group.addButton(self.random_radio)

        self.nth_radio = QCheckBox("Every Nth Row")
        type_layout.addWidget(self.nth_radio)

        layout.addWidget(type_group)

        # N value
        n_group = QGroupBox("Number of Rows")
        n_layout = QGridLayout(n_group)

        n_layout.addWidget(QLabel("N:"), 0, 0)
        self.n_spin = QSpinBox()
        self.n_spin.setRange(1, 1000000)
        self.n_spin.setValue(100)
        n_layout.addWidget(self.n_spin, 0, 1)

        n_layout.addWidget(QLabel("Step (for every Nth):"), 1, 0)
        self.step_spin = QSpinBox()
        self.step_spin.setRange(1, 1000)
        self.step_spin.setValue(1)
        n_layout.addWidget(self.step_spin, 1, 1)

        layout.addWidget(n_group)

        # Random seed
        seed_group = QGroupBox("Random Options")
        seed_layout = QVBoxLayout(seed_group)

        self.seed_layout = QHBoxLayout()
        self.seed_layout.addWidget(QLabel("Random Seed:"))
        self.seed_edit = QLineEdit()
        self.seed_edit.setPlaceholderText("Leave empty for random")
        self.seed_layout.addWidget(self.seed_edit)

        self.sample_check = QCheckBox("Sample as percentage of total")
        self.sample_check.toggled.connect(self._on_sample_changed)
        seed_layout.addWidget(self.sample_check)

        self.percentage_spin = QDoubleSpinBox()
        self.percentage_spin.setRange(0.1, 100)
        self.percentage_spin.setValue(10)
        self.percentage_spin.setSuffix("%")
        self.percentage_spin.setVisible(False)
        seed_layout.addWidget(self.percentage_spin)

        seed_layout.addStretch()
        seed_group.setLayout(seed_layout)
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

        self.apply_btn = QPushButton("Select Rows")
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
        self.apply_btn.clicked.connect(self._apply_selection)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _on_sample_changed(self):
        """Show/hide percentage spin"""
        self.percentage_spin.setVisible(self.sample_check.isChecked())

    def _apply_selection(self):
        """Validate and accept selection"""
        n = self.n_spin.value()

        self.current_params = {
            "selection_type": "first" if self.first_radio.isChecked()
                            else "last" if self.last_radio.isChecked()
                            else "random",
            "n": n,
            "step": self.step_spin.value(),
            "random_seed": self.seed_edit.text().strip() if self.seed_edit.text().strip() else None,
            "is_percentage": self.sample_check.isChecked(),
            "percentage": self.percentage_spin.value() if self.sample_check.isChecked() else None
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        params = self.get_parameters()
        n = params["n"]

        if params.get("is_percentage"):
            n = int(len(df) * params["percentage"] / 100)

        if params["selection_type"] == "first":
            return df.head(n)
        elif params["selection_type"] == "last":
            return df.tail(n)
        else:  # random
            seed = int(params["random_seed"]) if params["random_seed"] else None
            if seed:
                np.random.seed(seed)
            indices = np.random.choice(len(df), size=min(n, len(df)), replace=False)
            return df[indices]
