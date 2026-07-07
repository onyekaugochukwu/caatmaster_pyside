"""
Promote Row as Header Dialog
Allows users to select a row to promote as column headers with preview.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QSpinBox, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal
import polars as pl

from ..components.common_modals import BaseModal, PreviewTable, create_primary_button


class PromoteRowHeaderDialog(BaseModal):
    """Dialog for promoting a row to column headers"""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("Use First Row as Headers", dataframe, parent)
        self.resize(1000, 700)

    def _setup_ui(self):
        """Setup the UI components"""
        # Use the existing layout from BaseModal
        main_layout = self.layout()
        if main_layout is None:
            main_layout = QVBoxLayout(self)

        # Clear the default label if present
        for i in range(main_layout.count()):
            item = main_layout.itemAt(i)
            widget = item.widget()
            if widget and isinstance(widget, QLabel) and widget.text() == f"Modal: {self.windowTitle()}":
                widget.hide()
                break

        # Use the dataframe from BaseModal
        df = self.dataframe

        # Preview section
        preview_group = QGroupBox("Preview: Select Row to Use as Headers")
        preview_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 10px; }")
        preview_layout = QVBoxLayout(preview_group)

        # Row selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Row to promote as header (0-based):"))

        self.row_spinner = QSpinBox()
        self.row_spinner.setRange(0, max(0, len(df) - 1))
        self.row_spinner.setValue(0)
        self.row_spinner.valueChanged.connect(self._update_preview)
        selector_layout.addWidget(self.row_spinner)

        selector_layout.addStretch()
        preview_layout.addLayout(selector_layout)

        # Preview table
        self.preview_table = PreviewTable(max_rows=10, parent=self)
        self.preview_table.load_dataframe(df)
        preview_layout.addWidget(self.preview_table)

        # Result preview - show what columns will look like
        result_group = QGroupBox("Resulting Column Names")
        result_layout = QVBoxLayout(result_group)

        self.result_table = QTableWidget()
        self.result_table.setFixedHeight(100)
        self.result_table.setColumnCount(len(df.columns))
        self.result_table.setHorizontalHeaderLabels(df.columns)
        self.result_table.horizontalHeader().setStretchLastSection(True)
        result_layout.addWidget(self.result_table)

        main_layout.addWidget(preview_group, 1)
        main_layout.addWidget(result_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        apply_btn = create_primary_button("Promote Row as Headers")
        apply_btn.clicked.connect(self.accept_changes)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)

        main_layout.addLayout(btn_layout)

        # Initial preview
        self._update_preview(0)

    def _update_preview(self, row_index: int):
        """Update the preview to show what the result will look like"""
        df = self.dataframe
        if row_index >= len(df):
            return

        # Get the row to use as header
        row = df.row(row_index)

        # Generate column names
        new_headers = []
        seen = {}
        for i, h in enumerate(row):
            h_str = str(h).strip() if h is not None else f"col_{i}"
            # Handle duplicates by appending a suffix
            if h_str in seen:
                seen[h_str] += 1
                h_str = f"{h_str}_{seen[h_str]}"
            else:
                seen[h_str] = 0
            new_headers.append(h_str)

        # Update result table
        self.result_table.setRowCount(1)
        for col_idx, header in enumerate(new_headers):
            item = QTableWidgetItem(header)
            self.result_table.setItem(0, col_idx, item)

    def accept_changes(self):
        """Validate and accept"""
        row_index = self.row_spinner.value()

        if row_index >= len(self.original_df):
            QMessageBox.warning(self, "Invalid Row", "Selected row index is out of range.")
            return

        # Get parameters
        params = {
            "row_index": row_index
        }

        self.transformation_applied.emit("promote_row_header", params)
        self.accept()

    def get_parameters(self) -> dict:
        """Get the parameters for the operation"""
        return {
            "row_index": self.row_spinner.value()
        }
