"""
IFRS 9 Staging Dialog
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QGroupBox, QGridLayout, QSpinBox,
    QWidget, QMessageBox, QTabWidget
)
from PySide6.QtCore import Qt
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors

class IFRS9Dialog(BaseModal):
    """Dialog for IFRS 9 Staging Analysis"""
    
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
            "stage3_threshold": self.stage3_spin.value()
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
