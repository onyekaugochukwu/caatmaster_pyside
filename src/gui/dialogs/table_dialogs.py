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
                color: #605e5c;
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

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None,
                 available_datasets: List[str] = None, source_dataset_name: str = None):
        self.original_df = dataframe
        self.selected_column = selected_column
        self.available_datasets = available_datasets or []
        self.source_dataset_name = source_dataset_name or "Current Dataset"
        super().__init__("Join Datasets", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(700, 600)

    def _setup_ui(self):
        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #e1dfdd;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #8a8886;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #605e5c;
            }
        """)

        # Content widget for scroll area
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # Join type selection
        join_group = QGroupBox("Join Type")
        join_layout = QVBoxLayout(join_group)

        self.join_type_group = QButtonGroup()
        join_types = [
            ("left", "Left Join", "Keep all rows from left dataset, matching right rows"),
            ("right", "Right Join", "Keep all rows from right dataset, matching left rows"),
            ("inner", "Inner Join", "Keep only rows that match in both datasets"),
            ("outer", "Outer Join", "Keep all rows from both datasets"),
            ("cross", "Cross Join", "Cartesian product of both datasets"),
            ("semi", "Match (Semi Join)", "Keep only left rows that DO have a matching key in the right dataset - no right-side columns are added"),
            ("anti", "Non-Match (Anti Join)", "Keep only left rows that DON'T have a matching key in the right dataset - useful for finding orphaned/missing records"),
        ]

        self.join_radios = {}
        for join_id, join_name, description in join_types:
            radio = QRadioButton(f"{join_name}")
            radio.setToolTip(description)
            if join_id == "left":
                radio.setChecked(True)
            self.join_type_group.addButton(radio)
            self.join_radios[join_id] = radio
            join_layout.addWidget(radio)

        layout.addWidget(join_group)

        # Left dataset (current)
        left_group = QGroupBox(f"Left Dataset ({self.source_dataset_name})")
        left_layout = QFormLayout(left_group)
        left_layout.setLabelAlignment(Qt.AlignRight)
        left_layout.setFormAlignment(Qt.AlignLeft)

        self.left_key_combo = QComboBox()
        self.left_key_combo.addItems(self.original_df.columns)
        self.left_key_combo.setMinimumWidth(200)
        if self.selected_column:
            self.left_key_combo.setCurrentText(self.selected_column)
        left_layout.addRow("Join Key:", self.left_key_combo)

        layout.addWidget(left_group)

        # Right dataset selection - dropdown to select from available datasets
        right_group = QGroupBox("Right Dataset")
        right_layout = QFormLayout(right_group)
        right_layout.setLabelAlignment(Qt.AlignRight)
        right_layout.setFormAlignment(Qt.AlignLeft)

        self.right_dataset_combo = QComboBox()
        self.right_dataset_combo.setEditable(False)
        self.right_dataset_combo.setMinimumWidth(200)
        # Filter out the source dataset from available datasets
        other_datasets = [ds for ds in self.available_datasets if ds != self.source_dataset_name]
        self.right_dataset_combo.addItems(other_datasets)
        if other_datasets:
            self.right_dataset_combo.setCurrentIndex(0)
        right_layout.addRow("Dataset:", self.right_dataset_combo)

        self.right_key_combo = QComboBox()
        self.right_key_combo.setEditable(False)
        self.right_key_combo.setMinimumWidth(200)
        self.right_key_combo.addItems(self.original_df.columns)
        right_layout.addRow("Join Key:", self.right_key_combo)

        layout.addWidget(right_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.suffix_edit = QLineEdit()
        self.suffix_edit.setPlaceholderText("_right")
        self.suffix_edit.setText("_right")
        self.suffix_edit.setMinimumWidth(200)
        suffix_layout = QHBoxLayout()
        suffix_layout.addWidget(QLabel("Suffix for right columns:"))
        suffix_layout.addWidget(self.suffix_edit)
        suffix_layout.addStretch()
        options_layout.addLayout(suffix_layout)

        layout.addWidget(options_group)

        # Preview
        preview_group = QGroupBox("Preview (First 10 rows)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Set content and add scroll area
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Button row (outside scroll area)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(15, 10, 15, 10)

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

        main_layout.addLayout(btn_layout)

        # Load preview
        self.preview_table.load_dataframe(self.original_df.head(10))

    def _apply_join(self):
        """Validate and accept join"""
        dataset_name = self.right_dataset_combo.currentText()
        if not dataset_name:
            QMessageBox.warning(self, "Warning", "Please select a dataset to join with.")
            return

        right_key = self.right_key_combo.currentText()
        if not right_key:
            QMessageBox.warning(self, "Warning", "Please select the right join key.")
            return

        # Determine join type
        join_type = "left"
        for join_id, radio in self.join_radios.items():
            if radio.isChecked():
                join_type = join_id
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


class CompareDatasetsDialog(BaseModal):
    """Dialog for a cell-by-cell comparison of two datasets by key -
    mirrors ActiveData for Excel's Compare Sheets. Classifies every key as
    only-in-left, only-in-right, matched-identical, or matched-different."""

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None,
                 available_datasets: List[str] = None, source_dataset_name: str = None):
        self.original_df = dataframe
        self.selected_column = selected_column
        self.available_datasets = available_datasets or []
        self.source_dataset_name = source_dataset_name or "Current Dataset"
        super().__init__("Compare Datasets", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(650, 600)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        left_group = QGroupBox(f"Left Dataset ({self.source_dataset_name})")
        left_layout = QVBoxLayout(left_group)
        left_layout.addWidget(QLabel("Key column(s) - identify the same record on both sides (Ctrl/Shift-click for multiple):"))
        self.key_list = QListWidget()
        self.key_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.key_list.addItems(self.original_df.columns)
        self.key_list.setMaximumHeight(120)
        if self.selected_column:
            for item in self.key_list.findItems(self.selected_column, Qt.MatchExactly):
                item.setSelected(True)
        left_layout.addWidget(self.key_list)
        layout.addWidget(left_group)

        right_group = QGroupBox("Right Dataset")
        right_layout = QFormLayout(right_group)
        right_layout.setLabelAlignment(Qt.AlignRight)
        right_layout.setFormAlignment(Qt.AlignLeft)
        self.right_dataset_combo = QComboBox()
        self.right_dataset_combo.setEditable(False)
        self.right_dataset_combo.setMinimumWidth(200)
        other_datasets = [ds for ds in self.available_datasets if ds != self.source_dataset_name]
        self.right_dataset_combo.addItems(other_datasets)
        if other_datasets:
            self.right_dataset_combo.setCurrentIndex(0)
        right_layout.addRow("Compare against:", self.right_dataset_combo)
        layout.addWidget(right_group)

        compare_group = QGroupBox("Columns To Compare (Optional)")
        compare_layout = QVBoxLayout(compare_group)
        compare_layout.addWidget(QLabel("Leave unselected to compare every column common to both datasets:"))
        self.compare_list = QListWidget()
        self.compare_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.compare_list.addItems([c for c in self.original_df.columns])
        self.compare_list.setMaximumHeight(120)
        compare_layout.addWidget(self.compare_list)
        layout.addWidget(compare_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Compare Datasets")
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
        self.apply_btn.clicked.connect(self._apply_compare)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _apply_compare(self):
        """Validate and accept compare parameters"""
        dataset_name = self.right_dataset_combo.currentText()
        if not dataset_name:
            QMessageBox.warning(self, "Warning", "Please select a dataset to compare against.")
            return

        key_columns = [item.text() for item in self.key_list.selectedItems()]
        if not key_columns:
            QMessageBox.warning(self, "Warning", "Please select at least one key column.")
            return

        compare_columns = [item.text() for item in self.compare_list.selectedItems()]

        self.current_params = {
            "right_dataset": dataset_name,
            "key_columns": key_columns,
            "compare_columns": compare_columns or None,
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})


class FuzzyMatchDatasetsDialog(BaseModal):
    """Dialog for approximate/fuzzy text matching between two datasets -
    mirrors ActiveData for Excel's Approximate Column Match, e.g. matching
    an employee's address against a vendor's to catch a conflict of
    interest even when the text isn't typed identically."""

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None,
                 available_datasets: List[str] = None, source_dataset_name: str = None):
        self.original_df = dataframe
        self.selected_column = selected_column
        self.available_datasets = available_datasets or []
        self.source_dataset_name = source_dataset_name or "Current Dataset"
        super().__init__("Fuzzy Match Datasets", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(650, 500)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        left_group = QGroupBox(f"Left Dataset ({self.source_dataset_name})")
        left_layout = QFormLayout(left_group)
        left_layout.setLabelAlignment(Qt.AlignRight)
        left_layout.setFormAlignment(Qt.AlignLeft)
        self.left_column_combo = QComboBox()
        self.left_column_combo.addItems(self.original_df.columns)
        self.left_column_combo.setMinimumWidth(200)
        if self.selected_column:
            self.left_column_combo.setCurrentText(self.selected_column)
        left_layout.addRow("Text Column:", self.left_column_combo)
        layout.addWidget(left_group)

        right_group = QGroupBox("Right Dataset")
        right_layout = QFormLayout(right_group)
        right_layout.setLabelAlignment(Qt.AlignRight)
        right_layout.setFormAlignment(Qt.AlignLeft)
        self.right_dataset_combo = QComboBox()
        self.right_dataset_combo.setEditable(False)
        self.right_dataset_combo.setMinimumWidth(200)
        other_datasets = [ds for ds in self.available_datasets if ds != self.source_dataset_name]
        self.right_dataset_combo.addItems(other_datasets)
        if other_datasets:
            self.right_dataset_combo.setCurrentIndex(0)
        right_layout.addRow("Dataset:", self.right_dataset_combo)
        self.right_column_combo = QComboBox()
        self.right_column_combo.setEditable(False)
        self.right_column_combo.setMinimumWidth(200)
        self.right_column_combo.addItems(self.original_df.columns)
        right_layout.addRow("Text Column:", self.right_column_combo)
        layout.addWidget(right_group)

        options_group = QGroupBox("Matching Options")
        options_layout = QFormLayout(options_group)
        options_layout.setLabelAlignment(Qt.AlignRight)
        options_layout.setFormAlignment(Qt.AlignLeft)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.5, 1.0)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setValue(0.8)
        self.threshold_spin.setToolTip(
            "How similar two values must be to count as a match, from 0.5 (loose) to 1.0 (exact). "
            "0.8 is a reasonable starting point for names/addresses with minor formatting differences."
        )
        options_layout.addRow("Similarity Threshold:", self.threshold_spin)

        self.max_matches_spin = QSpinBox()
        self.max_matches_spin.setRange(1, 10)
        self.max_matches_spin.setValue(1)
        options_layout.addRow("Max Matches Per Row:", self.max_matches_spin)

        layout.addWidget(options_group)

        note = QLabel(
            "Note: this compares every left row against every right row (an O(n×m) operation), "
            "so it may take a while on very large datasets."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(note)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Find Matches")
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
        self.apply_btn.clicked.connect(self._apply_fuzzy_match)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def _apply_fuzzy_match(self):
        """Validate and accept fuzzy match parameters"""
        dataset_name = self.right_dataset_combo.currentText()
        if not dataset_name:
            QMessageBox.warning(self, "Warning", "Please select a dataset to match against.")
            return

        right_column = self.right_column_combo.currentText()
        if not right_column:
            QMessageBox.warning(self, "Warning", "Please select the right text column.")
            return

        self.current_params = {
            "right_dataset": dataset_name,
            "left_column": self.left_column_combo.currentText(),
            "right_column": right_column,
            "threshold": self.threshold_spin.value(),
            "max_matches_per_row": self.max_matches_spin.value(),
        }
        self.accept()

    def get_parameters(self) -> dict:
        return getattr(self, 'current_params', {})


class AppendDatasetsDialog(BaseModal):
    """Dialog for appending/stacking datasets vertically"""

    def __init__(self, dataframe: pl.DataFrame, parent=None,
                 available_datasets: List[str] = None, source_dataset_name: str = None,
                 dataset_columns: Dict[str, List[str]] = None):
        self.original_df = dataframe
        self.available_datasets = available_datasets or []
        self.source_dataset_name = source_dataset_name or "Current Dataset"
        self.dataset_columns = dataset_columns or {}  # Map dataset name -> columns
        super().__init__("Append Datasets", dataframe, parent)
        self.setMinimumSize(700, 650)

    def _setup_ui(self):
        # Main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #e1dfdd;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #8a8886;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #605e5c;
            }
        """)

        # Content widget for scroll area
        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)

        # Source dataset info
        info_group = QGroupBox("Source Dataset (First)")
        info_layout = QVBoxLayout(info_group)

        self.source_label = QLabel(f"{self.source_dataset_name}: {len(self.original_df)} rows, {len(self.original_df.columns)} columns")
        self.source_label.setStyleSheet("""
            QLabel {
                background-color: #deecf9;
                padding: 12px;
                border-radius: 4px;
                font-weight: bold;
                border: 1px solid #0078d4;
            }
        """)
        info_layout.addWidget(self.source_label)

        source_cols = self.original_df.columns
        self.source_columns_label = QLabel(f"Columns ({len(source_cols)}): {', '.join(source_cols[:10])}" +
                                           ("..." if len(source_cols) > 10 else ""))
        self.source_columns_label.setStyleSheet("color: #666; font-size: 11px;")
        self.source_columns_label.setWordWrap(True)
        info_layout.addWidget(self.source_columns_label)

        layout.addWidget(info_group)

        # Datasets to append
        append_group = QGroupBox("Datasets to Append (Second and onwards)")
        append_layout = QVBoxLayout(append_group)

        # Filter out the source dataset from available datasets
        other_datasets = [ds for ds in self.available_datasets if ds != self.source_dataset_name]

        if other_datasets:
            self.datasets_list = QListWidget()
            self.datasets_list.setSelectionMode(QAbstractItemView.MultiSelection)
            self.datasets_list.setMinimumHeight(120)
            self.datasets_list.itemChanged.connect(self._update_schema_info)
            for ds_name in other_datasets:
                item = QListWidgetItem(ds_name)
                item.setCheckState(Qt.Unchecked)
                self.datasets_list.addItem(item)
            append_layout.addWidget(self.datasets_list)

            self.no_datasets_label = QLabel()
        else:
            self.datasets_list = QListWidget()
            self.datasets_list.setMinimumHeight(60)
            append_layout.addWidget(self.datasets_list)
            self.no_datasets_label = QLabel("No other datasets available in the project")
            self.no_datasets_label.setStyleSheet("color: #666; font-size: 11px;")
            append_layout.addWidget(self.no_datasets_label)

        layout.addWidget(append_group)

        # Schema comparison info
        schema_group = QGroupBox("Schema Comparison")
        schema_layout = QVBoxLayout(schema_group)

        self.schema_info_label = QLabel("Select datasets to see schema comparison")
        self.schema_info_label.setStyleSheet("color: #666; font-size: 12px;")
        self.schema_info_label.setWordWrap(True)
        schema_layout.addWidget(self.schema_info_label)

        self.common_cols_label = QLabel("")
        self.common_cols_label.setStyleSheet("color: #059669; font-size: 11px;")
        self.common_cols_label.setWordWrap(True)
        schema_layout.addWidget(self.common_cols_label)

        self.unique_cols_label = QLabel("")
        self.unique_cols_label.setStyleSheet("color: #f59e0b; font-size: 11px;")
        self.unique_cols_label.setWordWrap(True)
        schema_layout.addWidget(self.unique_cols_label)

        layout.addWidget(schema_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        # Warning checkbox
        self.warn_check = QCheckBox("Warn if schemas differ")
        self.warn_check.setChecked(True)
        options_layout.addWidget(self.warn_check)

        # Behavior info
        self.behavior_label = QLabel(
            "Missing columns will be filled with null values."
        )
        self.behavior_label.setStyleSheet("""
            QLabel {
                color: #0078d4;
                font-size: 11px;
                padding: 8px;
                background-color: #deecf9;
                border-radius: 4px;
            }
        """)
        self.behavior_label.setWordWrap(True)
        options_layout.addWidget(self.behavior_label)

        layout.addWidget(options_group)

        # Result preview
        result_group = QGroupBox("Expected Result")
        result_layout = QVBoxLayout(result_group)

        self.result_preview = QLabel("Select datasets to see preview")
        self.result_preview.setStyleSheet("""
            QLabel {
                background-color: #f3f2f1;
                padding: 10px;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
        self.result_preview.setWordWrap(True)
        result_layout.addWidget(self.result_preview)

        layout.addWidget(result_group)

        # Set content and add scroll area
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Button row (outside scroll area)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(15, 10, 15, 10)

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

        main_layout.addLayout(btn_layout)

    def _get_selected_datasets(self) -> List[str]:
        """Get list of selected dataset names"""
        selected = []
        for i in range(self.datasets_list.count()):
            item = self.datasets_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected

    def _update_schema_info(self):
        """Update schema comparison information"""
        selected_datasets = self._get_selected_datasets()

        if not selected_datasets:
            self.schema_info_label.setText("Select datasets to see schema comparison")
            self.common_cols_label.setText("")
            self.unique_cols_label.setText("")
            self.result_preview.setText("Select datasets to see preview")
            return

        # Collect all columns
        all_columns = set(self.original_df.columns)
        for ds_name in selected_datasets:
            if ds_name in self.dataset_columns:
                all_columns.update(self.dataset_columns[ds_name])

        # Find common columns
        common_cols = set(self.original_df.columns)
        for ds_name in selected_datasets:
            if ds_name in self.dataset_columns:
                common_cols = common_cols & set(self.dataset_columns[ds_name])

        # Find unique columns per dataset
        source_cols = set(self.original_df.columns)

        if selected_datasets:
            if common_cols:
                self.common_cols_label.setText(
                    f"Common columns ({len(common_cols)}): {', '.join(sorted(common_cols)[:8])}"
                    + ("..." if len(common_cols) > 8 else "")
                )
            else:
                self.common_cols_label.setText("No common columns found - all columns will be null")

            # Show unique columns info
            unique_info = []
            for ds_name in selected_datasets[:3]:  # Show up to 3
                if ds_name in self.dataset_columns:
                    ds_unique = set(self.dataset_columns[ds_name]) - common_cols
                    if ds_unique:
                        unique_info.append(f"{ds_name}: {len(ds_unique)} unique")
            if len(selected_datasets) > 3:
                unique_info.append(f"+ {len(selected_datasets) - 3} more")

            if unique_info:
                self.unique_cols_label.setText("Unique columns: " + ", ".join(unique_info))
            else:
                self.unique_cols_label.setText("")
        else:
            self.common_cols_label.setText("")
            self.unique_cols_label.setText("")

        # Update result preview
        total_rows = len(self.original_df)
        selected_rows_info = []
        for ds_name in selected_datasets:
            if ds_name in self.dataset_columns:
                # We don't have row counts, just show dataset names
                selected_rows_info.append(ds_name)

        result_text = f"Source: {self.source_dataset_name} ({len(self.original_df):,} rows)\n"
        result_text += f"Appending {len(selected_datasets)} dataset(s): {', '.join(selected_datasets[:3])}"
        if len(selected_datasets) > 3:
            result_text += f" + {len(selected_datasets) - 3} more"
        result_text += f"\nResult: {len(all_columns)} columns, ~{total_rows + len(selected_datasets) * 100} estimated rows"
        result_text += "\nMissing columns will be filled with nulls"

        self.result_preview.setText(result_text)

    def _apply_append(self):
        """Validate and accept append"""
        selected_datasets = self._get_selected_datasets()
        if not selected_datasets:
            QMessageBox.warning(self, "Warning", "Please select at least one dataset to append.")
            return

        # Check for schema differences if warning is enabled
        if self.warn_check.isChecked():
            all_columns = set(self.original_df.columns)
            for ds_name in selected_datasets:
                if ds_name in self.dataset_columns:
                    all_columns.update(self.dataset_columns[ds_name])

            common_cols = set(self.original_df.columns)
            for ds_name in selected_datasets:
                if ds_name in self.dataset_columns:
                    common_cols = common_cols & set(self.dataset_columns[ds_name])

            if common_cols != all_columns:
                # Schemas differ - show warning but allow proceeding
                reply = QMessageBox.question(
                    self, "Schema Differences Detected",
                    f"The selected datasets have different columns.\n\n"
                    f"Common columns: {len(common_cols)}\n"
                    f"Total unique columns: {len(all_columns)}\n\n"
                    f"Missing columns will be filled with null values.\n\n"
                    f"Do you want to proceed?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply != QMessageBox.Yes:
                    return

        self.current_params = {
            "source_datasets": selected_datasets,
            "warn_if_schemas_differ": self.warn_check.isChecked()
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
                background-color: #f3f2f1;
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
