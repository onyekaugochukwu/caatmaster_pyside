"""
IFRS 9 Staging Dialog
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QGroupBox, QGridLayout, QSpinBox,
    QWidget, QMessageBox, QTabWidget
)
from PySide6.QtCore import Qt, Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors

class IFRS9Dialog(BaseModal):
    """Dialog for IFRS 9 Staging Analysis"""

    # See sox_dialog.py's SoxSodDialog for why this is needed - without it,
    # self.transformation_applied.emit(...) below raises AttributeError.
    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IFRS 9 Staging & ECL", dataframe, parent)
        self.resize(700, 600)
        
    def _setup_ui(self):
        """Setup the UI components"""
        main_layout = QVBoxLayout(self)
        
        tabs = QTabWidget()
        
        # --- TAB 1: MAPPING ---
        map_tab = QWidget()
        map_layout = QVBoxLayout(map_tab)
        
        mapping_group = QGroupBox("Column Mapping")
        mapping_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 10px; }")
        grid = QGridLayout(mapping_group)
        
        self.column_combos = {}
        
        # Define fields
        fields = [
            ("dpd", "Days Past Due (DPD)", "Numeric column containing DPD"),
            ("exposure", "Exposure (EAD)", "Outstanding balance amount"),
            ("pd", "Prob. Default (PD)", "Optional: PD % (0-1)"),
            ("lgd", "Loss Given Default (LGD)", "Optional: LGD % (0-1)")
        ]
        
        # Fallback date fields if DPD missing
        date_fields = [
            ("payment_date", "Report/As-Of Date", "Date of analysis"),
            ("due_date", "Due Date", "Date payment was due")
        ]

        # Optional PD-based SICR trigger - a loan can be a real Stage 2
        # (Significant Increase in Credit Risk) case from PD deterioration
        # alone, even while still current on payments (DPD = 0).
        sicr_fields = [
            ("pd_current", "Current PD", "Optional: current probability of default"),
            ("pd_origination", "PD at Origination", "Optional: probability of default when originated")
        ]

        all_cols = self.original_df.columns
        all_cols.insert(0, "")

        row = 0
        grid.addWidget(QLabel("<b>Primary Fields</b>"), row, 0, 1, 2)
        row += 1

        for key, label, tooltip in fields:
            grid.addWidget(QLabel(f"{label}:"), row, 0)
            combo = QComboBox()
            combo.addItems(all_cols)
            combo.setToolTip(tooltip)

            # Auto-guess
            norm_key = key.lower()
            for col in all_cols:
                if col.lower() == norm_key or col.lower() == label.lower():
                    combo.setCurrentText(col)
                    break

            self.column_combos[key] = combo
            grid.addWidget(combo, row, 1)
            row += 1

        grid.addWidget(QLabel("<b>OR Date Calculation (if DPD missing)</b>"), row, 0, 1, 2)
        row += 1

        for key, label, tooltip in date_fields:
            grid.addWidget(QLabel(f"{label}:"), row, 0)
            combo = QComboBox()
            combo.addItems(all_cols)
            combo.setToolTip(tooltip)
            self.column_combos[key] = combo
            grid.addWidget(combo, row, 1)
            row += 1

        grid.addWidget(QLabel("<b>SICR Trigger by PD Deterioration (optional)</b>"), row, 0, 1, 2)
        row += 1

        for key, label, tooltip in sicr_fields:
            grid.addWidget(QLabel(f"{label}:"), row, 0)
            combo = QComboBox()
            combo.addItems(all_cols)
            combo.setToolTip(tooltip)
            self.column_combos[key] = combo
            grid.addWidget(combo, row, 1)
            row += 1

        map_layout.addWidget(mapping_group)
        map_layout.addStretch()
        tabs.addTab(map_tab, "Data Mapping")
        
        # --- TAB 2: THRESHOLDS ---
        thresh_tab = QWidget()
        thresh_layout = QVBoxLayout(thresh_tab)
        
        thresh_group = QGroupBox("Staging Criteria")
        thresh_grid = QGridLayout(thresh_group)
        
        # Stage 2 Threshold
        thresh_grid.addWidget(QLabel("Stage 2 Threshold (Days):"), 0, 0)
        self.stage2_spin = QSpinBox()
        self.stage2_spin.setRange(1, 365)
        self.stage2_spin.setValue(30)
        self.stage2_spin.setSuffix(" days")
        thresh_grid.addWidget(self.stage2_spin, 0, 1)
        thresh_grid.addWidget(QLabel("Loans > this DPD move to Stage 2 (SICR)"), 0, 2)
        
        # Stage 3 Threshold
        thresh_grid.addWidget(QLabel("Stage 3 Threshold (Days):"), 1, 0)
        self.stage3_spin = QSpinBox()
        self.stage3_spin.setRange(1, 365)
        self.stage3_spin.setValue(90)
        self.stage3_spin.setSuffix(" days")
        thresh_grid.addWidget(self.stage3_spin, 1, 1)
        thresh_grid.addWidget(QLabel("Loans > this DPD move to Stage 3 (Impaired)"), 1, 2)

        # SICR-by-PD-deterioration multiplier - only takes effect if both
        # Current PD and PD at Origination are mapped on the Data Mapping tab.
        from PySide6.QtWidgets import QDoubleSpinBox
        thresh_grid.addWidget(QLabel("SICR PD Multiplier:"), 2, 0)
        self.sicr_multiplier_spin = QDoubleSpinBox()
        self.sicr_multiplier_spin.setRange(1.0, 20.0)
        self.sicr_multiplier_spin.setSingleStep(0.5)
        self.sicr_multiplier_spin.setValue(2.0)
        self.sicr_multiplier_spin.setSuffix("x")
        thresh_grid.addWidget(self.sicr_multiplier_spin, 2, 1)
        thresh_grid.addWidget(
            QLabel("Escalate to Stage 2 if Current PD / PD at Origination exceeds this (needs both mapped)"),
            2, 2
        )

        thresh_layout.addWidget(thresh_group)

        info_lbl = QLabel(
            "<b>Output Columns:</b><br>"
            "• <i>ifrs9_stage</i>: 1, 2, or 3<br>"
            "• <i>ifrs9_status</i>: Performing, Underperforming, Non-Performing<br>"
            "• <i>ifrs9_ecl_amount</i>: EAD * PD * LGD (if mapped)"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 20px;")
        thresh_layout.addWidget(info_lbl)
        
        thresh_layout.addStretch()
        tabs.addTab(thresh_tab, "Thresholds")
        
        main_layout.addWidget(tabs)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        run_btn = create_primary_button("Run Staging Analysis")
        run_btn.clicked.connect(self.accept_changes)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        
        main_layout.addLayout(btn_layout)

    def get_parameters(self):
        """Get the parameters"""
        mapping = {}
        for key, combo in self.column_combos.items():
            val = combo.currentText()
            if val:
                mapping[key] = val
                
        thresholds = {
            "stage2_threshold": self.stage2_spin.value(),
            "stage3_threshold": self.stage3_spin.value(),
            "sicr_pd_multiplier": self.sicr_multiplier_spin.value()
            if mapping.get("pd_current") and mapping.get("pd_origination") else None
        }
                
        return {
            "mapping": mapping,
            "thresholds": thresholds
        }

    def accept_changes(self):
        """Validate"""
        params = self.get_parameters()
        mapping = params["mapping"]
        
        has_dpd = "dpd" in mapping
        has_dates = "payment_date" in mapping and "due_date" in mapping
        
        if not has_dpd and not has_dates:
            QMessageBox.warning(self, "Missing Data", 
                              "Please map 'Days Past Due' column OR both date columns to calculate it.")
            return
            
        self.transformation_applied.emit("ifrs9_staging", params)
        self.accept()


class IFRS9ScenarioECLDialog(BaseModal):
    """Dialog for probability-weighted IFRS 9 ECL across base/upside/
    downside PD scenarios, with an optional variance check against
    management's own booked ECL."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("IFRS 9 Scenario-Weighted ECL", dataframe, parent)
        self.resize(650, 560)

    def _setup_ui(self):
        from PySide6.QtWidgets import QDoubleSpinBox

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Weights ECL across up to three macro scenarios instead of a single point-estimate PD. "
            "Map at least one scenario's PD column - unmapped scenarios have their weight "
            "redistributed proportionally rather than silently dropped."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        all_cols = list(self.original_df.columns)
        all_cols_with_blank = [""] + all_cols

        map_group = QGroupBox("Column Mapping")
        map_grid = QGridLayout(map_group)
        self.column_combos = {}

        core_fields = [
            ("exposure", "Exposure (EAD)"),
            ("lgd", "Loss Given Default (LGD)"),
        ]
        scenario_fields = [
            ("pd_base", "Base Case PD"),
            ("pd_upside", "Upside PD (optional)"),
            ("pd_downside", "Downside PD (optional)"),
        ]
        optional_fields = [
            ("management_ecl", "Management's Booked ECL (optional)"),
        ]

        row = 0
        for group_label, field_group in (
            ("<b>Required</b>", core_fields),
            ("<b>Scenarios (map at least one)</b>", scenario_fields),
            ("<b>Variance Check (optional)</b>", optional_fields),
        ):
            map_grid.addWidget(QLabel(group_label), row, 0, 1, 2)
            row += 1
            for key, label in field_group:
                map_grid.addWidget(QLabel(f"{label}:"), row, 0)
                combo = QComboBox()
                combo.addItems(all_cols_with_blank)
                norm_key = key.replace("pd_", "").lower()
                for col in all_cols:
                    if norm_key in col.lower():
                        combo.setCurrentText(col)
                        break
                self.column_combos[key] = combo
                map_grid.addWidget(combo, row, 1)
                row += 1

        layout.addWidget(map_group)

        weights_group = QGroupBox("Scenario Weights")
        weights_grid = QGridLayout(weights_group)
        self.weight_spins = {}
        for i, (scenario, default) in enumerate([("base", 0.5), ("upside", 0.25), ("downside", 0.25)]):
            weights_grid.addWidget(QLabel(f"{scenario.title()}:"), i, 0)
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.05)
            spin.setValue(default)
            self.weight_spins[scenario] = spin
            weights_grid.addWidget(spin, i, 1)
        layout.addWidget(weights_group)

        variance_group = QGroupBox("Variance Flag")
        variance_layout = QHBoxLayout(variance_group)
        variance_layout.addWidget(QLabel("Flag if |recalculated - management| exceeds:"))
        self.variance_spin = QDoubleSpinBox()
        self.variance_spin.setRange(0.0, 500.0)
        self.variance_spin.setValue(20.0)
        self.variance_spin.setSuffix("%")
        variance_layout.addWidget(self.variance_spin)
        layout.addWidget(variance_group)

        info_lbl = QLabel(
            "<b>Output Columns:</b><br>"
            "• <i>ifrs9_weighted_pd</i>, <i>ifrs9_scenario_ecl</i><br>"
            "• <i>ifrs9_ecl_variance</i>, <i>ifrs9_ecl_variance_pct</i>, <i>ifrs9_ecl_variance_flag</i> "
            "(if management's ECL is mapped)"
        )
        info_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; margin-top: 10px;")
        layout.addWidget(info_lbl)
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Calculate Scenario ECL")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def get_parameters(self):
        mapping = {key: combo.currentText() for key, combo in self.column_combos.items() if combo.currentText()}
        weights = {scenario: spin.value() for scenario, spin in self.weight_spins.items()}
        return {
            "mapping": mapping,
            "weights": weights,
            "variance_threshold_pct": self.variance_spin.value(),
        }

    def accept_changes(self):
        params = self.get_parameters()
        mapping = params["mapping"]

        if not mapping.get("exposure") or not mapping.get("lgd"):
            QMessageBox.warning(self, "Missing Data", "Please map both Exposure (EAD) and LGD.")
            return
        if not any(mapping.get(f"pd_{s}") for s in ("base", "upside", "downside")):
            QMessageBox.warning(self, "Missing Data", "Please map at least one scenario's PD column.")
            return

        self.transformation_applied.emit("ifrs9_scenario_ecl", params)
        self.accept()
