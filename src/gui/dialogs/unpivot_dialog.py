"""
Unpivot Dialog for CAATmaster
Unpivot (melt) operation — converts wide format to long format
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QRadioButton, QButtonGroup, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea, QWidget, QMessageBox,
    QLineEdit, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer

from ..components.common_modals import BaseModal, PreviewTable, MultiColumnSelector, create_primary_button
from ..theme import Colors


class UnpivotDialog(BaseModal):
    """
    Unpivot dialog
    Converts wide format (many columns) to long format (attribute/value pairs)
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Unpivot Columns", dataframe, parent)
        self.setMinimumSize(700, 600)

    def _setup_ui(self):
        """Setup the unpivot dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Unpivot options
        options_group = QGroupBox("Unpivot Options")
        options_layout = QVBoxLayout(options_group)

        self.option_group = QButtonGroup(options_group)

        self.all_cols_radio = QRadioButton("Unpivot All Columns")
        self.all_cols_radio.setChecked(True)
        self.option_group.addButton(self.all_cols_radio, 0)
        options_layout.addWidget(self.all_cols_radio)

        self.selected_cols_radio = QRadioButton("Unpivot Only These Columns")
        self.option_group.addButton(self.selected_cols_radio, 1)
        options_layout.addWidget(self.selected_cols_radio)

        self.except_cols_radio = QRadioButton("Unpivot All Columns Except")
        self.option_group.addButton(self.except_cols_radio, 2)
        options_layout.addWidget(self.except_cols_radio)

        layout.addWidget(options_group)

        # Column selection
        columns_group = QGroupBox("Columns to Unpivot")
        columns_layout = QVBoxLayout(columns_group)

        self.column_selector = MultiColumnSelector(self.original_df)
        columns_layout.addWidget(self.column_selector)

        layout.addWidget(columns_group)

        # Output column names
        output_group = QGroupBox("Output Column Names")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Attribute Column Name:"), 0, 0)
        self.attr_edit = QLineEdit("attribute")
        output_layout.addWidget(self.attr_edit, 0, 1)

        output_layout.addWidget(QLabel("Value Column Name:"), 1, 0)
        self.value_edit = QLineEdit("value")
        output_layout.addWidget(self.value_edit, 1, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview (First 10 Rows of Output)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Row count info
        self.row_info = QLabel()
        self.row_info.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-style: italic;
            }}
        """)
        layout.addWidget(self.row_info)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Update Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.unpivot_btn = create_primary_button("Unpivot")
        self.unpivot_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.unpivot_btn)

        layout.addLayout(btn_layout)

        # Connect signals
        self.option_group.buttonClicked.connect(self._on_option_changed)
        self.column_selector.columnsSelected.connect(self._on_columns_changed)

        # Initial preview
        QTimer.singleShot(100, self.preview)

    def _on_option_changed(self, button):
        """Handle option change"""
        option = self.option_group.id(button)
        if option == 0:  # All columns
            self.column_selector.setEnabled(False)
        elif option == 1:  # Selected columns
            self.column_selector.setEnabled(True)
        elif option == 2:  # Except columns
            self.column_selector.setEnabled(True)

    def _on_columns_changed(self, columns: List[str]):
        """Handle column selection change"""
        pass  # Preview will be updated when user clicks Update Preview

    def get_parameters(self) -> dict:
        """Get the unpivot parameters"""
        option = self.option_group.checkedId()

        if option == 0:
            # All columns except ID vars
            id_vars = [c for c in self.original_df.columns if c not in self.original_df.columns]
            value_vars = None
        elif option == 1:
            # Only selected columns
            id_vars = [c for c in self.original_df.columns if c not in self.column_selector.get_selected_columns()]
            value_vars = self.column_selector.get_selected_columns()
        else:  # option == 2
            # All except selected
            id_vars = [c for c in self.original_df.columns if c not in self.column_selector.get_selected_columns()]
            value_vars = None

        return {
            "id_vars": id_vars,
            "value_vars": value_vars,
            "var_name": self.attr_edit.text() or "attribute",
            "value_name": self.value_edit.text() or "value",
        }

    def validate(self) -> bool:
        """Validate the unpivot parameters"""
        option = self.option_group.checkedId()

        if option in [1, 2]:
            selected = self.column_selector.get_selected_columns()
            if not selected:
                QMessageBox.warning(self, "Validation Error",
                                  "Please select at least one column to unpivot.")
                return False

        return True

    def preview(self):
        """Generate preview of unpivoted data"""
        try:
            params = self.get_parameters()
            id_vars = params["id_vars"]
            value_vars = params["value_vars"]
            var_name = params["var_name"]
            value_name = params["value_name"]

            # Perform unpivot
            unpivoted = self.original_df.melt(
                id_vars=id_vars,
                value_vars=value_vars,
                variable_name=var_name,
                value_name=value_name
            )

            # Show preview
            self.preview_table.load_dataframe(unpivoted)

            # Update row info
            original_rows = len(self.original_df)
            new_rows = len(unpivoted)
            self.row_info.setText(f"Original rows: {original_rows:,} → Unpivoted rows: {new_rows:,}")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

