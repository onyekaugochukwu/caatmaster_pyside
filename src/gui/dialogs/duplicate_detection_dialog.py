"""
Find Duplicates dialog.

Supports two paradigms, both driven by the same underlying operation
(audit_duplicate_detection) — the only difference is how many columns are
checked:

  - Single column: flags rows where THAT column's value repeats elsewhere
    (e.g. a duplicate invoice number).
  - Multiple columns: flags rows where the FULL COMBINATION of the selected
    columns repeats elsewhere (a composite/whole-row-style check, e.g. the
    same vendor + amount + date appearing more than once).

The output column names default to something that names which paradigm and
which column(s) were checked, so the resulting dataset and Applied Steps
stay self-documenting even without opening the step's parameters.
"""
import re

import polars as pl
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QListWidget, QAbstractItemView, QMessageBox
)

from ..components.common_modals import BaseModal
from gui.theme import Colors


class DuplicateDetectionDialog(BaseModal):
    """Find Duplicates — single-column or multi-column (composite) mode."""

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        self._names_auto = True
        super().__init__("Find Duplicates", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(560, 540)
        if selected_column:
            self.set_selected_column(selected_column)

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from a right-click header."""
        self.selected_column = column_name
        if hasattr(self, 'column_list') and column_name:
            for i in range(self.column_list.count()):
                item = self.column_list.item(i)
                if item.text() == column_name:
                    item.setSelected(True)
            self._update_defaults()

    def _on_column_selected(self, column_name: str):
        self.set_selected_column(column_name)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        help_label = QLabel(
            "<b>Single column</b> — checks whether that column's own values repeat elsewhere "
            "(e.g. duplicate invoice numbers).<br>"
            "<b>Multiple columns</b> — checks whether the full combination of the selected "
            "columns repeats elsewhere (e.g. the same vendor + amount + date more than once)."
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(help_label)

        columns_group = QGroupBox("Columns to Check")
        columns_layout = QVBoxLayout(columns_group)
        self.column_list = QListWidget()
        self.column_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for col in self.original_df.columns:
            self.column_list.addItem(col)
        self.column_list.itemSelectionChanged.connect(self._update_defaults)
        columns_layout.addWidget(self.column_list)
        layout.addWidget(columns_group, 1)

        self.mode_label = QLabel("Select one or more columns above.")
        self.mode_label.setWordWrap(True)
        self.mode_label.setStyleSheet(f"color: {Colors.ACCENT}; font-weight: 600;")
        layout.addWidget(self.mode_label)

        names_group = QGroupBox("Output Columns")
        names_layout = QFormLayout(names_group)
        self.group_id_edit = QLineEdit()
        self.group_id_edit.textEdited.connect(self._on_name_edited)
        names_layout.addRow("Group ID Column:", self.group_id_edit)
        self.flag_edit = QLineEdit()
        self.flag_edit.textEdited.connect(self._on_name_edited)
        names_layout.addRow("Flag Column:", self.flag_edit)
        layout.addWidget(names_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        self.apply_btn = QPushButton("Find Duplicates")
        self.apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }}
        """)
        self.apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(self.apply_btn)
        layout.addLayout(btn_layout)

    def _on_name_edited(self):
        # A genuine user edit stops us from clobbering their custom name the
        # next time the column selection changes.
        self._names_auto = False

    def _selected_columns(self):
        # Preserve the dataframe's own column order rather than selection
        # (click) order, so the composite key is stable and predictable.
        selected = {item.text() for item in self.column_list.selectedItems()}
        return [c for c in self.original_df.columns if c in selected]

    @staticmethod
    def _sanitize(name: str) -> str:
        return re.sub(r'[^0-9a-zA-Z_]', '_', name)

    def _update_defaults(self):
        cols = self._selected_columns()
        if not cols:
            self.mode_label.setText("Select one or more columns above.")
        elif len(cols) == 1:
            self.mode_label.setText(
                f"Single-column mode: flags rows where '{cols[0]}' repeats elsewhere."
            )
        else:
            self.mode_label.setText(
                f"Combination mode: flags rows where {', '.join(cols)} together repeat elsewhere."
            )

        if not self._names_auto:
            return
        if len(cols) == 1:
            safe = self._sanitize(cols[0])
            self.group_id_edit.setText(f"duplicate_group_{safe}")
            self.flag_edit.setText(f"is_duplicate_{safe}")
        elif len(cols) > 1:
            self.group_id_edit.setText("duplicate_group_id")
            self.flag_edit.setText("is_full_row_duplicate")

    def _on_apply(self):
        if self.validate():
            self.accept()

    def get_parameters(self) -> dict:
        return {
            "columns": self._selected_columns(),
            "output_column": self.group_id_edit.text().strip() or "duplicate_group_id",
            "flag_column": self.flag_edit.text().strip() or "is_duplicate",
        }

    def validate(self) -> bool:
        if not self._selected_columns():
            QMessageBox.warning(self, "No Columns Selected",
                                 "Please select at least one column to check for duplicates.")
            return False
        if not self.group_id_edit.text().strip() or not self.flag_edit.text().strip():
            QMessageBox.warning(self, "Missing Column Name",
                                 "Please provide names for both output columns.")
            return False
        return True
