"""
IAS 21 FX Rate Consistency Dialog
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QMessageBox, QDoubleSpinBox
)
from PySide6.QtCore import Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors


class IAS21FxRateCheckDialog(BaseModal):
    """Dialog for the IAS 21 foreign currency rate consistency check."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IAS 21 FX Rate Consistency Check", dataframe, parent)
        self.resize(600, 460)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Compares each transaction's booked FX rate against a benchmark rate already present on "
            "the row (e.g. joined in from a daily rate table via Join Datasets) and quantifies the "
            "resulting $ variance."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        all_cols = list(self.original_df.columns)
        all_cols_with_blank = [""] + all_cols

        col_group = QGroupBox("Column Mapping")
        grid = QGridLayout(col_group)
        self.column_combos = {}

        fields = [
            ("booked_rate", "Booked FX Rate"),
            ("benchmark_rate", "Benchmark FX Rate"),
            ("local_amount", "Local/Foreign Currency Amount (optional)"),
        ]
        for row, (key, label) in enumerate(fields):
            grid.addWidget(QLabel(f"{label}:"), row, 0)
            combo = QComboBox()
            combo.addItems(all_cols_with_blank)
            self.column_combos[key] = combo
            grid.addWidget(combo, row, 1)

        layout.addWidget(col_group)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Flag if the booked rate deviates from the benchmark by more than:"))
        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setRange(0.0, 100.0)
        self.tolerance_spin.setValue(1.0)
        self.tolerance_spin.setSuffix("%")
        threshold_row.addWidget(self.tolerance_spin)
        layout.addLayout(threshold_row)

        info_lbl = QLabel(
            "<b>Output Columns:</b> <i>ias21_rate_deviation_pct</i>, <i>ias21_fx_rate_flag</i>, "
            "and (if local amount mapped) <i>ias21_fx_amount_variance</i>"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 10px;")
        layout.addWidget(info_lbl)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Check FX Rates")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def get_parameters(self):
        mapping = {key: combo.currentText() for key, combo in self.column_combos.items() if combo.currentText()}
        return {"mapping": mapping, "tolerance_pct": self.tolerance_spin.value()}

    def accept_changes(self):
        params = self.get_parameters()
        if not params["mapping"].get("booked_rate") or not params["mapping"].get("benchmark_rate"):
            QMessageBox.warning(self, "Missing Data", "Please map both Booked FX Rate and Benchmark FX Rate.")
            return
        self.transformation_applied.emit("ias21_fx_rate_check", params)
        self.accept()
