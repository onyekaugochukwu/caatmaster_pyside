"""
IAS 36 Reverse-DCF Dialog
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QWidget, QMessageBox, QDoubleSpinBox, QRadioButton
)
from PySide6.QtCore import Qt, Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors


class IAS36ReverseDCFDialog(BaseModal):
    """Dialog for the IAS 36 reverse-DCF implied growth rate test - solves
    for the terminal growth rate each CGU's carrying value implicitly
    requires, and flags it against a growth benchmark."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IAS 36 Reverse DCF", dataframe, parent)
        self.resize(700, 620)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Solves for the terminal growth rate implied by each row's carrying value, discount "
            "rate, and explicit-period cash flow forecast. A high implied growth rate relative to "
            "a benchmark (e.g. GDP growth) is a starting point for follow-up audit judgment, not a "
            "pass/fail impairment test on its own."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        col_group = QGroupBox("Column Mapping")
        col_layout = QGridLayout(col_group)

        self.carrying_value_combo = QComboBox()
        self.carrying_value_combo.addItems(self.original_df.columns)
        self.discount_rate_combo = QComboBox()
        self.discount_rate_combo.addItems(self.original_df.columns)

        for col in self.original_df.columns:
            lower = col.lower()
            if "carrying" in lower or "book_value" in lower or "cgu" in lower and "value" in lower:
                self.carrying_value_combo.setCurrentText(col)
            if "discount" in lower or "wacc" in lower:
                self.discount_rate_combo.setCurrentText(col)

        col_layout.addWidget(QLabel("Carrying Value Column:"), 0, 0)
        col_layout.addWidget(self.carrying_value_combo, 0, 1)
        col_layout.addWidget(QLabel("Discount Rate Column (decimal, e.g. 0.10):"), 1, 0)
        col_layout.addWidget(self.discount_rate_combo, 1, 1)
        layout.addWidget(col_group)

        cf_group = QGroupBox("Explicit-Period Cash Flow Columns (in order, Year 1 first)")
        cf_layout = QVBoxLayout(cf_group)

        self.cf_table = QTableWidget()
        self.cf_table.setColumnCount(1)
        self.cf_table.setHorizontalHeaderLabels(["Cash Flow Column"])
        self.cf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cf_table.setRowCount(1)
        self._add_cf_combo(0)
        cf_layout.addWidget(self.cf_table)

        cf_btn_row = QHBoxLayout()
        add_year_btn = QPushButton("+ Add Year")
        add_year_btn.setStyleSheet("min-width: 100px; padding: 4px 8px;")
        add_year_btn.clicked.connect(self._add_cf_row)
        remove_year_btn = QPushButton("- Remove Last Year")
        remove_year_btn.setStyleSheet("min-width: 160px; padding: 4px 8px;")
        remove_year_btn.clicked.connect(self._remove_cf_row)
        cf_btn_row.addWidget(add_year_btn)
        cf_btn_row.addWidget(remove_year_btn)
        cf_btn_row.addStretch()
        cf_layout.addLayout(cf_btn_row)
        layout.addWidget(cf_group)

        benchmark_group = QGroupBox("Growth Benchmark")
        benchmark_layout = QVBoxLayout(benchmark_group)

        self.benchmark_col_radio = QRadioButton("Use a per-row benchmark column:")
        self.benchmark_value_radio = QRadioButton("Use a single benchmark value:")
        self.benchmark_value_radio.setChecked(True)

        col_row = QHBoxLayout()
        col_row.addWidget(self.benchmark_col_radio)
        self.benchmark_col_combo = QComboBox()
        self.benchmark_col_combo.addItems([""] + list(self.original_df.columns))
        col_row.addWidget(self.benchmark_col_combo)
        benchmark_layout.addLayout(col_row)

        val_row = QHBoxLayout()
        val_row.addWidget(self.benchmark_value_radio)
        self.benchmark_value_spin = QDoubleSpinBox()
        self.benchmark_value_spin.setRange(-0.5, 0.5)
        self.benchmark_value_spin.setSingleStep(0.005)
        self.benchmark_value_spin.setDecimals(4)
        self.benchmark_value_spin.setValue(0.02)
        val_row.addWidget(self.benchmark_value_spin)
        benchmark_layout.addLayout(val_row)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Flag if implied growth exceeds benchmark by more than:"))
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 50.0)
        self.threshold_spin.setValue(2.0)
        self.threshold_spin.setSuffix(" pp")
        threshold_row.addWidget(self.threshold_spin)
        benchmark_layout.addLayout(threshold_row)

        layout.addWidget(benchmark_group)

        info_lbl = QLabel(
            "<b>Output Columns:</b><br>"
            "• <i>ias36_implied_growth_rate</i>: solved terminal growth rate (null if no valid "
            "solution exists)<br>"
            "• <i>ias36_benchmark_growth_rate</i>, <i>ias36_growth_gap_pp</i>, <i>ias36_flag</i>"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 10px;")
        layout.addWidget(info_lbl)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Solve Implied Growth Rate")
        run_btn.setStyleSheet("min-width: 220px; padding: 4px 8px;")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def _add_cf_combo(self, row: int):
        combo = QComboBox()
        combo.addItems([""] + list(self.original_df.columns))
        self.cf_table.setCellWidget(row, 0, combo)

    def _add_cf_row(self):
        row = self.cf_table.rowCount()
        self.cf_table.insertRow(row)
        self._add_cf_combo(row)

    def _remove_cf_row(self):
        if self.cf_table.rowCount() > 1:
            self.cf_table.removeRow(self.cf_table.rowCount() - 1)

    def get_parameters(self):
        cash_flow_columns = []
        for row in range(self.cf_table.rowCount()):
            combo = self.cf_table.cellWidget(row, 0)
            if combo and combo.currentText():
                cash_flow_columns.append(combo.currentText())

        params = {
            "carrying_value_column": self.carrying_value_combo.currentText(),
            "discount_rate_column": self.discount_rate_combo.currentText(),
            "cash_flow_columns": cash_flow_columns,
            "flag_threshold_pp": self.threshold_spin.value(),
        }
        if self.benchmark_col_radio.isChecked() and self.benchmark_col_combo.currentText():
            params["benchmark_growth_column"] = self.benchmark_col_combo.currentText()
        else:
            params["benchmark_growth_value"] = self.benchmark_value_spin.value()
        return params

    def accept_changes(self):
        params = self.get_parameters()
        if not params["cash_flow_columns"]:
            QMessageBox.warning(self, "Missing Data", "Please map at least one cash flow column.")
            return
        self.transformation_applied.emit("ias36_implied_growth_rate", params)
        self.accept()
