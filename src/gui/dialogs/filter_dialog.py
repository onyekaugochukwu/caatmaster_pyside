"""
Filter Dialog for CAATmaster
Complex filtering with multiple conditions (AND/OR)
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QRadioButton, QButtonGroup, QGroupBox, QTableWidget,
    QTableWidgetItem, QWidget, QMessageBox, QLineEdit, QCheckBox,
    QFrame, QToolButton, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer

from ..components.common_modals import BaseModal, PreviewTable, create_primary_button
from ..theme import Colors


# Operator definitions
OPERATORS = {
    "text": [
        ("Equals", "=="),
        ("Does Not Equal", "!="),
        ("Contains", "contains"),
        ("Does Not Contain", "not_contains"),
        ("Starts With", "starts_with"),
        ("Ends With", "ends_with"),
        ("Is Empty", "is_null"),
        ("Is Not Empty", "is_not_null"),
        ("In List...", "in_list"),
    ],
    "number": [
        ("Equals", "=="),
        ("Does Not Equal", "!="),
        ("Greater Than", ">"),
        ("Greater Than or Equal", ">="),
        ("Less Than", "<"),
        ("Less Than or Equal", "<="),
        ("Between...", "between"),
        ("Is Empty", "is_null"),
        ("Is Not Empty", "is_not_null"),
    ],
    "date": [
        ("Equals", "=="),
        ("Does Not Equal", "!="),
        ("Is Before", "<"),
        ("Is After", ">"),
        ("Is On or Before", "<="),
        ("Is On or After", ">="),
        ("Between...", "between"),
        ("Is Empty", "is_null"),
        ("Is Not Empty", "is_not_null"),
    ],
}

DEFAULT_OPERATORS = [
    ("Equals", "=="),
    ("Does Not Equal", "!="),
    ("Contains", "contains"),
    ("Greater Than", ">"),
    ("Less Than", "<"),
    ("Is Empty", "is_null"),
    ("Is Not Empty", "is_not_null"),
]


class FilterConditionWidget(QWidget):
    """
    Widget representing a single filter condition
    """

    removed = Signal()

    def __init__(self, columns: List[str], parent=None, dataframe: pl.DataFrame = None):
        super().__init__(parent)
        self.columns = columns
        # Stored directly rather than looked up via self.parent(): once this
        # widget is added to a layout, Qt reparents it to that layout's own
        # widget (e.g. a scroll area's content widget) — self.parent() then
        # silently stops being the owning dialog, which used to make every
        # column-switch after the first fall back to text-only operators.
        self._dataframe = dataframe
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Column selector
        self.column_combo = QComboBox()
        self.column_combo.addItems(self.columns)
        self.column_combo.currentTextChanged.connect(self._on_column_changed)
        layout.addWidget(self.column_combo, 1)

        # Operator selector
        self.operator_combo = QComboBox()
        layout.addWidget(self.operator_combo, 1)

        # Value input
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("Value...")
        layout.addWidget(self.value_edit, 2)

        # Remove button
        self.remove_btn = QPushButton("×")
        self.remove_btn.setFixedSize(24, 24)
        self.remove_btn.setToolTip("Remove this condition")
        self.remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.DANGER_SOFT};
                color: {Colors.DANGER};
                border: 1px solid {Colors.DANGER_SOFT};
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {Colors.DANGER};
                color: {Colors.TEXT_ON_ACCENT};
            }}
        """)
        self.remove_btn.clicked.connect(self.removed.emit)
        layout.addWidget(self.remove_btn)

        # Initialize operators
        self._on_column_changed(self.column_combo.currentText())

    def _on_column_changed(self, column_name: str):
        """Update operators based on column type"""
        df = self._dataframe
        col_type = "text"
        if df is not None and column_name in df.columns:
            dtype = df[column_name].dtype
            # is_numeric() covers every numeric dtype polars has (signed AND
            # unsigned ints of every width, floats, decimal) — an explicit
            # list here previously missed UInt8/16/32/64, so any column of
            # that type (e.g. this app's own add_index_column, or a
            # row/group count) silently lost the >/</>=/<= operators.
            if dtype.is_numeric():
                col_type = "number"
            elif dtype in [pl.Date, pl.Datetime]:
                col_type = "date"

        # Update operators
        operators = OPERATORS.get(col_type, DEFAULT_OPERATORS)
        current_op = self.operator_combo.currentText()
        self.operator_combo.clear()
        for label, value in operators:
            self.operator_combo.addItem(label, value)
        # Restore selection if still valid
        for i in range(self.operator_combo.count()):
            if self.operator_combo.itemData(i) == current_op:
                self.operator_combo.setCurrentIndex(i)
                break

    def get_condition(self) -> dict:
        """Get the filter condition"""
        return {
            "column": self.column_combo.currentText(),
            "operator": self.operator_combo.currentData(),
            "value": self.value_edit.text(),
        }

    def set_condition(self, column: str, operator: str, value: str):
        """Set the filter condition"""
        self.column_combo.setCurrentText(column)
        for i in range(self.operator_combo.count()):
            if self.operator_combo.itemData(i) == operator:
                self.operator_combo.setCurrentIndex(i)
                break
        self.value_edit.setText(value)


class FilterDialog(BaseModal):
    """
    Complex filter dialog with multiple conditions and AND/OR grouping
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        self.conditions = []  # List of (widget, combine_with)
        super().__init__("Filter Data", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(700, 600)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if column_name and self.conditions:
            # Set the first condition's column to the selected column
            self.conditions[0].column_combo.setCurrentText(column_name)
            QTimer.singleShot(100, self.preview)

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        if column_name and self.conditions:
            self.conditions[0].column_combo.setCurrentText(column_name)
            QTimer.singleShot(100, self.preview)

    def _setup_ui(self):
        """Setup the filter dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Filter conditions
        conditions_group = QGroupBox("Filter Conditions")
        conditions_layout = QVBoxLayout(conditions_group)

        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Column"))
        header_layout.addWidget(QLabel("Operator"))
        header_layout.addWidget(QLabel("Value"))
        header_layout.addWidget(QLabel(""))  # For remove button
        conditions_layout.addLayout(header_layout)

        # Conditions scroll area
        self.conditions_scroll = QWidget()
        self.conditions_layout = QVBoxLayout(self.conditions_scroll)
        self.conditions_layout.setSpacing(4)
        conditions_layout.addWidget(self.conditions_scroll)

        # Add condition button
        add_btn = QPushButton("+ Add Condition")
        add_btn.clicked.connect(self._add_condition)
        conditions_layout.addWidget(add_btn)

        # Combine options
        combine_group = QGroupBox("Combine Conditions")
        combine_layout = QVBoxLayout(combine_group)

        self.and_radio = QRadioButton("AND - Keep rows that match ALL conditions")
        self.and_radio.setChecked(True)
        combine_layout.addWidget(self.and_radio)

        self.or_radio = QRadioButton("OR - Keep rows that match ANY condition")
        combine_layout.addWidget(self.or_radio)

        self.and_or_mix_radio = QRadioButton("Custom - Group conditions")
        combine_layout.addWidget(self.and_or_mix_radio)

        conditions_layout.addWidget(combine_group)

        layout.addWidget(conditions_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=15)
        preview_layout.addWidget(self.preview_table)

        # Row count
        self.row_info = QLabel()
        self.row_info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-style: italic;")
        preview_layout.addWidget(self.row_info)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(self.clear_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Update Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.filter_btn = create_primary_button("Apply Filter")
        self.filter_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.filter_btn)

        layout.addLayout(btn_layout)

        # Add initial condition
        self._add_condition()

    def _add_condition(self):
        """Add a new filter condition"""
        widget = FilterConditionWidget(self.original_df.columns, self, dataframe=self.original_df)
        widget.removed.connect(lambda: self._remove_condition(widget))
        self.conditions_layout.addWidget(widget)
        self.conditions.append(widget)

    def _remove_condition(self, widget: FilterConditionWidget):
        """Remove a filter condition"""
        if len(self.conditions) > 1:
            self.conditions.remove(widget)
            widget.deleteLater()
            self.preview()

    def _clear_all(self):
        """Clear all conditions"""
        for widget in self.conditions[1:]:
            widget.deleteLater()
        self.conditions[0].set_condition(
            self.original_df.columns[0] if self.original_df.columns else "",
            "==",
            ""
        )
        self.and_radio.setChecked(True)
        self.preview()

    def get_parameters(self) -> dict:
        """Get the filter parameters"""
        conditions = []
        for widget in self.conditions:
            cond = widget.get_condition()
            if cond["column"] and cond["operator"]:
                conditions.append(cond)

        return {
            "conditions": conditions,
            "combine_operator": "AND" if self.and_radio.isChecked() else "OR",
        }

    def validate(self) -> bool:
        """Validate the filter parameters"""
        return True

    def preview(self):
        """Generate preview of filtered data — delegates to the same
        DataProcessor._build_condition_expr the real filter_advanced/
        audit_flag_rows operations use, instead of maintaining a second,
        separately-buggy copy of the same condition-to-expression logic
        (this one used to fall back to comparing a raw, uncoerced string
        against numeric columns whenever float(val) failed, e.g. while a
        value field was still empty — "cannot compare string with numeric
        type")."""
        try:
            params = self.get_parameters()
            conditions = params["conditions"]
            combine_op = params["combine_operator"]

            if not conditions:
                self.preview_table.load_dataframe(self.original_df)
                self.row_info.setText(f"Showing all {len(self.original_df):,} rows")
                return

            from core.data_processor import DataProcessor
            combined = DataProcessor()._build_condition_expr(self.original_df, conditions, combine_op)
            filtered_df = self.original_df.filter(combined) if combined is not None else self.original_df

            self.preview_table.load_dataframe(filtered_df)

            # Update row info
            original_rows = len(self.original_df)
            filtered_rows = len(filtered_df)
            percentage = (filtered_rows / original_rows * 100) if original_rows > 0 else 0
            self.row_info.setText(
                f"Showing {filtered_rows:,} of {original_rows:,} rows ({percentage:.1f}%)"
            )

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply filter:\n{str(e)}")
            return self.original_df.clone()


class AuditFlagDialog(FilterDialog):
    """Flag rows matching one or more conditions (AND/OR) with a new
    column, instead of removing non-matching rows like Filter does.
    Reuses FilterDialog's condition-builder UI since both dialogs solve
    the same "build a condition" problem."""

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        self.conditions = []
        BaseModal.__init__(self, "Audit Flag", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(700, 650)
        if selected_column:
            self.set_selected_column(selected_column)

    def _setup_ui(self):
        super()._setup_ui()
        flag_name_layout = QHBoxLayout()
        flag_name_layout.addWidget(QLabel("Flag Column Name:"))
        self.flag_column_edit = QLineEdit("flagged")
        flag_name_layout.addWidget(self.flag_column_edit)
        self.layout().insertLayout(0, flag_name_layout)

    def get_parameters(self) -> dict:
        params = super().get_parameters()
        params["flag_column"] = self.flag_column_edit.text().strip() or "flagged"
        return params
