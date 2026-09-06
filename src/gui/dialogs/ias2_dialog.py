"""
IAS 2 Inventory NRV Write-Down Dialog
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QMessageBox, QDoubleSpinBox
)
from PySide6.QtCore import Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors


class IAS2NrvWritedownDialog(BaseModal):
    """Dialog for the IAS 2 inventory NRV write-down test."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IAS 2 Inventory NRV Write-Down", dataframe, parent)
        self.resize(600, 480)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Flags inventory carried at cost above net realizable value (selling price less costs "
            "to sell), per IAS 2.9."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        all_cols = list(self.original_df.columns)
        all_cols_with_blank = [""] + all_cols

        col_group = QGroupBox("Column Mapping")
        grid = QGridLayout(col_group)
        self.column_combos = {}

        required_fields = [
            ("cost", "Carrying Cost"),
            ("selling_price", "Estimated Selling Price"),
        ]
        optional_fields = [
            ("costs_to_sell", "Estimated Costs to Sell (optional)"),
            ("quantity", "Quantity (optional - multiplies to a total $ write-down)"),
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
        threshold_row.addWidget(QLabel("Tolerance above NRV before flagging:"))
        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setRange(0.0, 100.0)
        self.tolerance_spin.setValue(0.0)
        self.tolerance_spin.setSuffix("%")
        threshold_row.addWidget(self.tolerance_spin)
        layout.addLayout(threshold_row)

        info_lbl = QLabel(
            "<b>Output Columns:</b> <i>ias2_nrv</i>, <i>ias2_writedown_amount</i>, <i>ias2_writedown_flag</i>"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 10px;")
        layout.addWidget(info_lbl)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Check NRV Write-Downs")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def get_parameters(self):
        mapping = {key: combo.currentText() for key, combo in self.column_combos.items() if combo.currentText()}
        return {"mapping": mapping, "tolerance_pct": self.tolerance_spin.value()}

    def accept_changes(self):
        params = self.get_parameters()
        if not params["mapping"].get("cost") or not params["mapping"].get("selling_price"):
            QMessageBox.warning(self, "Missing Data", "Please map both Carrying Cost and Estimated Selling Price.")
            return
        self.transformation_applied.emit("ias2_nrv_writedown", params)
        self.accept()
