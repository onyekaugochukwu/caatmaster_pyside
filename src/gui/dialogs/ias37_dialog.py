"""
IAS 37 Provision Trend Break Dialog
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QDoubleSpinBox, QMessageBox
)
from PySide6.QtCore import Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors


class IAS37ProvisionTrendDialog(BaseModal):
    """Dialog for the IAS 37 YoY provision trend-break check, with an
    optional legal-claims/settlement cross-check."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IAS 37 Provision Trend Break", dataframe, parent)
        self.resize(600, 460)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Flags a large year-over-year provision change. If your provision population is "
            "already joined to a settlement/legal-claims indicator (via Join Datasets), map it "
            "below to distinguish a decrease with a recorded settlement from one with none."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        col_group = QGroupBox("Column Mapping")
        grid = QGridLayout(col_group)

        all_cols = list(self.original_df.columns)
        self.prior_combo = QComboBox()
        self.prior_combo.addItems(all_cols)
        self.current_combo = QComboBox()
        self.current_combo.addItems(all_cols)
        self.settlement_combo = QComboBox()
        self.settlement_combo.addItems([""] + all_cols)

        for col in all_cols:
            lower = col.lower()
            if "prior" in lower or "py" in lower or "last_year" in lower:
                self.prior_combo.setCurrentText(col)
            if "current" in lower or "cy" in lower or "this_year" in lower:
                self.current_combo.setCurrentText(col)
            if "settle" in lower or "claim" in lower:
                idx = self.settlement_combo.findText(col)
                if idx >= 0:
                    self.settlement_combo.setCurrentIndex(idx)

        grid.addWidget(QLabel("Prior Year Balance Column:"), 0, 0)
        grid.addWidget(self.prior_combo, 0, 1)
        grid.addWidget(QLabel("Current Year Balance Column:"), 1, 0)
        grid.addWidget(self.current_combo, 1, 1)
        grid.addWidget(QLabel("Settlement/Claim Flag Column (optional):"), 2, 0)
        grid.addWidget(self.settlement_combo, 2, 1)
        layout.addWidget(col_group)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Flag if YoY change exceeds:"))
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 500.0)
        self.threshold_spin.setValue(30.0)
        self.threshold_spin.setSuffix("%")
        threshold_row.addWidget(self.threshold_spin)
        layout.addLayout(threshold_row)

        info_lbl = QLabel(
            "<b>Output Columns:</b><br>"
            "• <i>ias37_yoy_change_pct</i>, <i>ias37_trend_break_flag</i><br>"
            "• If a settlement column is mapped: <i>ias37_unexplained_decrease_flag</i> "
            "(a flagged decrease with no recorded settlement)"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 10px;")
        layout.addWidget(info_lbl)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Check Provision Trend")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def get_parameters(self):
        mapping = {
            "prior_year": self.prior_combo.currentText(),
            "current_year": self.current_combo.currentText(),
        }
        if self.settlement_combo.currentText():
            mapping["settlement_flag"] = self.settlement_combo.currentText()
        return {"mapping": mapping, "change_threshold_pct": self.threshold_spin.value()}

    def accept_changes(self):
        params = self.get_parameters()
        if not params["mapping"]["prior_year"] or not params["mapping"]["current_year"]:
            QMessageBox.warning(self, "Missing Data", "Please map both Prior Year and Current Year balance columns.")
            return
        self.transformation_applied.emit("ias37_provision_trend", params)
        self.accept()
