"""Verify Data Dialog - build a checklist of data-integrity expectations
(numeric/date/no-nulls/unique/positive/in-range) and run them against the
active dataset, mirroring ACL's VERIFY command. Read-only: never modifies
the dataset, just reports which expectations the real data violates."""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QDoubleSpinBox,
    QMessageBox
)
from PySide6.QtCore import Qt

from services.data_verification import verify_data_integrity, CHECK_TYPES
from ..theme import Colors
from ..components.common_modals import create_primary_button


class VerifyDataDialog(QDialog):
    """Build a checklist of column expectations, run them, and review
    results - all in one dialog."""

    def __init__(self, df: pl.DataFrame, parent=None):
        super().__init__(parent)
        self.df = df
        self.setWindowTitle("Verify Data Integrity")
        self.resize(750, 620)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(
            "Add one or more expectations below (e.g. \"vendor_id should have no nulls\", \"amount "
            "should be numeric\") and run them against the real data - each row reports how many "
            "values actually violate that expectation."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(info)

        add_group = QGroupBox("Add Expectation")
        add_layout = QHBoxLayout(add_group)

        self.column_combo = QComboBox()
        self.column_combo.addItems(self.df.columns)
        add_layout.addWidget(QLabel("Column:"))
        add_layout.addWidget(self.column_combo)

        self.check_combo = QComboBox()
        self.check_combo.addItems(CHECK_TYPES)
        self.check_combo.currentTextChanged.connect(self._on_check_type_changed)
        add_layout.addWidget(QLabel("Check:"))
        add_layout.addWidget(self.check_combo)

        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-1e12, 1e12)
        self.min_spin.setPrefix("min: ")
        self.min_spin.setVisible(False)
        add_layout.addWidget(self.min_spin)

        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-1e12, 1e12)
        self.max_spin.setPrefix("max: ")
        self.max_spin.setValue(100.0)
        self.max_spin.setVisible(False)
        add_layout.addWidget(self.max_spin)

        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(self._add_expectation)
        add_layout.addWidget(add_btn)
        add_layout.addStretch()

        layout.addWidget(add_group)

        list_group = QGroupBox("Expectations To Check")
        list_layout = QVBoxLayout(list_group)
        self.checks_table = QTableWidget()
        self.checks_table.setColumnCount(4)
        self.checks_table.setHorizontalHeaderLabels(["Column", "Check", "Range", "Remove"])
        self.checks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.checks_table.setMaximumHeight(160)
        list_layout.addWidget(self.checks_table)
        layout.addWidget(list_group)

        run_btn = create_primary_button("Run Verification")
        run_btn.clicked.connect(self._run_verification)
        layout.addWidget(run_btn)

        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        self.results_table = QTableWidget()
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        results_layout.addWidget(self.results_table)
        layout.addWidget(results_group, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._checks = []

    def _on_check_type_changed(self, check_type: str):
        show_range = check_type == "in_range"
        self.min_spin.setVisible(show_range)
        self.max_spin.setVisible(show_range)

    def _add_expectation(self):
        column = self.column_combo.currentText()
        check_type = self.check_combo.currentText()
        check = {"column": column, "check_type": check_type}
        range_text = ""
        if check_type == "in_range":
            check["min"] = self.min_spin.value()
            check["max"] = self.max_spin.value()
            range_text = f"[{check['min']}, {check['max']}]"

        self._checks.append(check)
        row = self.checks_table.rowCount()
        self.checks_table.insertRow(row)
        self.checks_table.setItem(row, 0, QTableWidgetItem(column))
        self.checks_table.setItem(row, 1, QTableWidgetItem(check_type))
        self.checks_table.setItem(row, 2, QTableWidgetItem(range_text))
        remove_btn = QPushButton("✕")
        remove_btn.clicked.connect(lambda checked=False, r=row: self._remove_expectation(r))
        self.checks_table.setCellWidget(row, 3, remove_btn)

    def _remove_expectation(self, row: int):
        if 0 <= row < len(self._checks):
            self._checks.pop(row)
            self.checks_table.removeRow(row)
            # Reconnect remaining remove buttons to their new row indices
            for r in range(self.checks_table.rowCount()):
                btn = self.checks_table.cellWidget(r, 3)
                if btn:
                    btn.clicked.disconnect()
                    btn.clicked.connect(lambda checked=False, rr=r: self._remove_expectation(rr))

    def _run_verification(self):
        if not self._checks:
            QMessageBox.information(self, "No Expectations", "Add at least one expectation first.")
            return

        result = verify_data_integrity(self.df, self._checks)
        self.results_table.setRowCount(result.height)
        self.results_table.setColumnCount(len(result.columns))
        self.results_table.setHorizontalHeaderLabels([str(c) for c in result.columns])
        status_col = result.columns.index("status")
        for r in range(result.height):
            row_vals = result.row(r)
            for c, val in enumerate(row_vals):
                item = QTableWidgetItem("" if val is None else str(val))
                if c == status_col and val == "FAIL":
                    item.setForeground(Qt.red)
                self.results_table.setItem(r, c, item)
