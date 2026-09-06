"""
IFRS 15 Revenue Recognition Dialogs - margin-shift (CUSUM) detection and
revenue timing-gap check.
"""
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QMessageBox, QDoubleSpinBox, QSpinBox
)
from PySide6.QtCore import Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors


class IFRS15MarginCusumDialog(BaseModal):
    """Dialog for the IFRS 15 CUSUM margin-shift detection test."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IFRS 15 Margin Shift Detection (CUSUM)", dataframe, parent)
        self.resize(600, 480)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Detects a sustained shift in a contract's revenue-to-cost margin over time - catches "
            "cost-shifting between periods that a simple period-over-period threshold would miss."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        col_group = QGroupBox("Column Mapping")
        grid = QGridLayout(col_group)

        self.revenue_combo = QComboBox()
        self.revenue_combo.addItems(self.original_df.columns)
        self.cost_combo = QComboBox()
        self.cost_combo.addItems(self.original_df.columns)
        self.date_combo = QComboBox()
        self.date_combo.addItems(self.original_df.columns)
        self.group_combo = QComboBox()
        self.group_combo.addItems([""] + list(self.original_df.columns))

        for col in self.original_df.columns:
            lower = col.lower()
            if "revenue" in lower or "sales" in lower:
                self.revenue_combo.setCurrentText(col)
            if lower == "cost" or "cogs" in lower or "cost_of" in lower:
                self.cost_combo.setCurrentText(col)
            if "date" in lower or "period" in lower:
                self.date_combo.setCurrentText(col)
            if "contract" in lower or "customer" in lower:
                idx = self.group_combo.findText(col)
                if idx >= 0:
                    self.group_combo.setCurrentIndex(idx)

        grid.addWidget(QLabel("Revenue Column:"), 0, 0)
        grid.addWidget(self.revenue_combo, 0, 1)
        grid.addWidget(QLabel("Cost Column:"), 1, 0)
        grid.addWidget(self.cost_combo, 1, 1)
        grid.addWidget(QLabel("Period Date Column:"), 2, 0)
        grid.addWidget(self.date_combo, 2, 1)
        grid.addWidget(QLabel("Contract/Group Column (optional):"), 3, 0)
        grid.addWidget(self.group_combo, 3, 1)
        layout.addWidget(col_group)

        sensitivity_group = QGroupBox("CUSUM Sensitivity")
        sensitivity_grid = QGridLayout(sensitivity_group)
        sensitivity_grid.addWidget(QLabel("Slack (k, x std dev):"), 0, 0)
        self.k_spin = QDoubleSpinBox()
        self.k_spin.setRange(0.0, 5.0)
        self.k_spin.setSingleStep(0.1)
        self.k_spin.setValue(0.5)
        sensitivity_grid.addWidget(self.k_spin, 0, 1)
        sensitivity_grid.addWidget(QLabel("Threshold (h, x std dev):"), 1, 0)
        self.h_spin = QDoubleSpinBox()
        self.h_spin.setRange(0.5, 20.0)
        self.h_spin.setSingleStep(0.5)
        self.h_spin.setValue(4.0)
        sensitivity_grid.addWidget(self.h_spin, 1, 1)
        sensitivity_grid.addWidget(
            QLabel("Higher threshold = fewer, more confident flags."), 2, 0, 1, 2
        )
        layout.addWidget(sensitivity_group)

        info_lbl = QLabel(
            "<b>Output Columns:</b> <i>ifrs15_margin</i>, <i>ifrs15_cusum_flag</i>"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 10px;")
        layout.addWidget(info_lbl)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Detect Margin Shifts")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def get_parameters(self):
        return {
            "revenue_column": self.revenue_combo.currentText(),
            "cost_column": self.cost_combo.currentText(),
            "date_column": self.date_combo.currentText(),
            "group_column": self.group_combo.currentText() or None,
            "k_multiplier": self.k_spin.value(),
            "h_multiplier": self.h_spin.value(),
        }

    def accept_changes(self):
        self.transformation_applied.emit("ifrs15_margin_cusum", self.get_parameters())
        self.accept()


class IFRS15TimingGapDialog(BaseModal):
    """Dialog for the IFRS 15 revenue-recognition timing-gap check."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IFRS 15 Revenue Timing Gap", dataframe, parent)
        self.resize(550, 320)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Flags revenue recognized materially before the performance obligation was satisfied "
            "(delivery/shipment) - a premature recognition risk under the IFRS 15 transfer-of-"
            "control test."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        col_group = QGroupBox("Column Mapping")
        grid = QGridLayout(col_group)

        self.revenue_date_combo = QComboBox()
        self.revenue_date_combo.addItems(self.original_df.columns)
        self.delivery_date_combo = QComboBox()
        self.delivery_date_combo.addItems(self.original_df.columns)

        for col in self.original_df.columns:
            lower = col.lower()
            if "revenue" in lower and "date" in lower:
                self.revenue_date_combo.setCurrentText(col)
            if "deliver" in lower or "shipment" in lower or "shipped" in lower:
                self.delivery_date_combo.setCurrentText(col)

        grid.addWidget(QLabel("Revenue Recognition Date Column:"), 0, 0)
        grid.addWidget(self.revenue_date_combo, 0, 1)
        grid.addWidget(QLabel("Delivery/Shipment Date Column:"), 1, 0)
        grid.addWidget(self.delivery_date_combo, 1, 1)
        layout.addWidget(col_group)

        threshold_row = QHBoxLayout()
        threshold_row.addWidget(QLabel("Allowed buffer before flagging:"))
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 365)
        self.threshold_spin.setValue(0)
        self.threshold_spin.setSuffix(" days")
        threshold_row.addWidget(self.threshold_spin)
        layout.addLayout(threshold_row)

        info_lbl = QLabel(
            "<b>Output Columns:</b> <i>ifrs15_timing_gap_days</i>, <i>ifrs15_premature_recognition_flag</i>"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 10px;")
        layout.addWidget(info_lbl)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Check Timing Gap")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def get_parameters(self):
        return {
            "revenue_date_column": self.revenue_date_combo.currentText(),
            "delivery_date_column": self.delivery_date_combo.currentText(),
            "threshold_days": self.threshold_spin.value(),
        }

    def accept_changes(self):
        self.transformation_applied.emit("ifrs15_timing_gap", self.get_parameters())
        self.accept()
