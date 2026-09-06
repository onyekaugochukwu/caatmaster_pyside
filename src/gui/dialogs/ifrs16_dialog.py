"""
IFRS 16 Lease Liability & IBR Dialog
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QMessageBox, QDoubleSpinBox
)
from PySide6.QtCore import Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors


class IFRS16LeaseLiabilityDialog(BaseModal):
    """Dialog for IFRS 16 lease liability/ROU asset calculation and the
    IBR reasonableness check against a user-supplied benchmark rate."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IFRS 16 Lease Liability & IBR Check", dataframe, parent)
        self.resize(650, 560)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Calculates the lease liability as the present value of remaining payments, one row "
            "per lease. Optionally compares management's IBR against a benchmark rate you supply "
            "(this does not build a credit-spread model itself) and quantifies the resulting "
            "liability difference."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        all_cols = list(self.original_df.columns)
        all_cols_with_blank = [""] + all_cols

        col_group = QGroupBox("Column Mapping")
        grid = QGridLayout(col_group)
        self.column_combos = {}

        required_fields = [
            ("payment", "Periodic Payment Amount"),
            ("periods", "Remaining Number of Periods"),
            ("management_ibr", "Management's IBR (decimal, e.g. 0.05)"),
        ]
        optional_fields = [
            ("benchmark_ibr", "Benchmark IBR (optional, e.g. risk-free + spread)"),
            ("initial_direct_costs", "Initial Direct Costs (optional)"),
            ("lease_incentives", "Lease Incentives (optional)"),
        ]

        row = 0
        grid.addWidget(QLabel("<b>Required</b>"), row, 0, 1, 2)
        row += 1
        for key, label in required_fields:
            grid.addWidget(QLabel(f"{label}:"), row, 0)
            combo = QComboBox()
            combo.addItems(all_cols_with_blank)
            self.column_combos[key] = combo
            grid.addWidget(combo, row, 1)
            row += 1

        grid.addWidget(QLabel("<b>Optional</b>"), row, 0, 1, 2)
        row += 1
        for key, label in optional_fields:
            grid.addWidget(QLabel(f"{label}:"), row, 0)
            combo = QComboBox()
            combo.addItems(all_cols_with_blank)
            self.column_combos[key] = combo
            grid.addWidget(combo, row, 1)
            row += 1

        layout.addWidget(col_group)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Flag if IBR deviates from the benchmark by more than:"))
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 5000.0)
        self.threshold_spin.setValue(50.0)
        self.threshold_spin.setSuffix(" bps")
        threshold_row.addWidget(self.threshold_spin)
        layout.addLayout(threshold_row)

        info_lbl = QLabel(
            "<b>Output Columns:</b><br>"
            "• <i>ifrs16_lease_liability</i>, <i>ifrs16_rou_asset</i><br>"
            "• If a benchmark IBR is mapped: <i>ifrs16_benchmark_liability</i>, "
            "<i>ifrs16_ibr_deviation_bps</i>, <i>ifrs16_liability_understatement</i>, "
            "<i>ifrs16_ibr_flag</i>"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 10px;")
        layout.addWidget(info_lbl)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Calculate Lease Liability")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def get_parameters(self):
        mapping = {key: combo.currentText() for key, combo in self.column_combos.items() if combo.currentText()}
        return {"mapping": mapping, "threshold_bps": self.threshold_spin.value()}

    def accept_changes(self):
        params = self.get_parameters()
        mapping = params["mapping"]
        if not mapping.get("payment") or not mapping.get("periods") or not mapping.get("management_ibr"):
            QMessageBox.warning(
                self, "Missing Data",
                "Please map Payment, Remaining Periods, and Management's IBR."
            )
            return
        self.transformation_applied.emit("ifrs16_lease_liability", params)
        self.accept()
