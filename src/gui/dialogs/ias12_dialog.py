"""
IAS 12 Deferred Tax Asset Recoverability Dialog
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QMessageBox, QDoubleSpinBox, QRadioButton
)
from PySide6.QtCore import Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors


class IAS12DtaRecoverabilityDialog(BaseModal):
    """Dialog for the IAS 12 deferred tax asset recoverability check."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IAS 12 DTA Recoverability Check", dataframe, parent)
        self.resize(650, 560)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Solves for the average annual taxable profit a recognized DTA balance requires to be "
            "fully utilized within its available window, then flags it against a benchmark profit "
            "figure. A flag is a starting point for follow-up on recoverability, not proof the DTA "
            "is unsupportable."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        all_cols = list(self.original_df.columns)
        col_group = QGroupBox("Column Mapping")
        grid = QGridLayout(col_group)

        self.dta_combo = QComboBox()
        self.dta_combo.addItems(all_cols)
        self.rate_combo = QComboBox()
        self.rate_combo.addItems(all_cols)
        self.years_combo = QComboBox()
        self.years_combo.addItems(all_cols)

        for col in all_cols:
            lower = col.lower()
            if "dta" in lower or "deferred_tax" in lower:
                self.dta_combo.setCurrentText(col)
            if "tax_rate" in lower or lower == "rate":
                self.rate_combo.setCurrentText(col)
            if "year" in lower and ("util" in lower or "remain" in lower or "expir" in lower):
                self.years_combo.setCurrentText(col)

        grid.addWidget(QLabel("DTA Balance Column:"), 0, 0)
        grid.addWidget(self.dta_combo, 0, 1)
        grid.addWidget(QLabel("Tax Rate Column (decimal, e.g. 0.25):"), 1, 0)
        grid.addWidget(self.rate_combo, 1, 1)
        grid.addWidget(QLabel("Utilization Years Remaining Column:"), 2, 0)
        grid.addWidget(self.years_combo, 2, 1)
        layout.addWidget(col_group)

        benchmark_group = QGroupBox("Benchmark Taxable Profit")
        benchmark_layout = QVBoxLayout(benchmark_group)

        self.benchmark_col_radio = QRadioButton("Use a per-row benchmark column:")
        self.benchmark_value_radio = QRadioButton("Use a single benchmark value:")
        self.benchmark_value_radio.setChecked(True)

        col_row = QHBoxLayout()
        col_row.addWidget(self.benchmark_col_radio)
        self.benchmark_col_combo = QComboBox()
        self.benchmark_col_combo.addItems([""] + all_cols)
        col_row.addWidget(self.benchmark_col_combo)
        benchmark_layout.addLayout(col_row)

        val_row = QHBoxLayout()
        val_row.addWidget(self.benchmark_value_radio)
        self.benchmark_value_spin = QDoubleSpinBox()
        self.benchmark_value_spin.setRange(-1_000_000_000, 1_000_000_000)
        self.benchmark_value_spin.setDecimals(2)
        self.benchmark_value_spin.setValue(0.0)
        val_row.addWidget(self.benchmark_value_spin)
        benchmark_layout.addLayout(val_row)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Flag if required profit exceeds the benchmark by more than:"))
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 500.0)
        self.threshold_spin.setValue(20.0)
        self.threshold_spin.setSuffix("%")
        threshold_row.addWidget(self.threshold_spin)
        benchmark_layout.addLayout(threshold_row)

        layout.addWidget(benchmark_group)

        info_lbl = QLabel(
            "<b>Output Columns:</b><br>"
            "• <i>ias12_required_annual_taxable_profit</i><br>"
            "• <i>ias12_benchmark_profit</i>, <i>ias12_shortfall_pct</i>, <i>ias12_recoverability_flag</i>"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 10px;")
        layout.addWidget(info_lbl)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Check DTA Recoverability")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def get_parameters(self):
        mapping = {
            "dta_balance": self.dta_combo.currentText(),
            "tax_rate": self.rate_combo.currentText(),
            "utilization_years": self.years_combo.currentText(),
        }
        params = {
            "mapping": mapping,
            "flag_threshold_pct": self.threshold_spin.value(),
        }
        if self.benchmark_col_radio.isChecked() and self.benchmark_col_combo.currentText():
            params["benchmark_profit_column"] = self.benchmark_col_combo.currentText()
        else:
            params["benchmark_profit_value"] = self.benchmark_value_spin.value()
        return params

    def accept_changes(self):
        params = self.get_parameters()
        mapping = params["mapping"]
        if not mapping["dta_balance"] or not mapping["tax_rate"] or not mapping["utilization_years"]:
            QMessageBox.warning(self, "Missing Data", "Please map DTA Balance, Tax Rate, and Utilization Years.")
            return
        self.transformation_applied.emit("ias12_dta_recoverability", params)
        self.accept()
