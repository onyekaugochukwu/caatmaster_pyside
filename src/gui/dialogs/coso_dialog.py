"""
COSO Risk Dialog
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QGroupBox, QGridLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button

class CosoDialog(BaseModal):
    """Dialog for COSO Risk Mapping"""

    # See sox_dialog.py's SoxSodDialog for why this is needed - without it,
    # self.transformation_applied.emit(...) below raises AttributeError.
    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("COSO Risk Heatmap", dataframe, parent)
        self.resize(700, 500)
        
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        
        # 1. Select Columns
        col_group = QGroupBox("1. Select Data")
        col_layout = QGridLayout(col_group)
        
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(self.original_df.columns)
        
        self.risk_combo = QComboBox()
        self.risk_combo.addItems(self.original_df.columns)
        
        # Auto-guess
        for col in self.original_df.columns:
            lower = col.lower()
            if "category" in lower or "process" in lower or "area" in lower:
                self.cat_combo.setCurrentText(col)
            if "risk" in lower or "score" in lower or "rating" in lower:
                self.risk_combo.setCurrentText(col)
                
        col_layout.addWidget(QLabel("Category/Process Column:"), 0, 0)
        col_layout.addWidget(self.cat_combo, 0, 1)
        col_layout.addWidget(QLabel("Risk Score Column:"), 1, 0)
        col_layout.addWidget(self.risk_combo, 1, 1)
        
        layout.addWidget(col_group)
        
        # 2. Map to COSO
        map_group = QGroupBox("2. Map Categories to COSO Components")
        map_layout = QVBoxLayout(map_group)
        
        self.map_table = QTableWidget()
        self.map_table.setColumnCount(2)
        self.map_table.setHorizontalHeaderLabels(["Your Category", "COSO Component"])
        self.map_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        map_layout.addWidget(self.map_table)
        
        # Refresh mapping button
        refresh_btn = QPushButton("Load Unique Categories")
        refresh_btn.setStyleSheet("min-width: 170px; padding: 4px 8px;")
        refresh_btn.clicked.connect(self._load_categories)
        map_layout.addWidget(refresh_btn)
        
        layout.addWidget(map_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        run_btn = create_primary_button("Generate Heatmap Data")
        run_btn.setStyleSheet("min-width: 170px; padding: 4px 8px;")
        run_btn.clicked.connect(self.accept_changes)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        
        layout.addLayout(btn_layout)
        
        # Initial load
        self._load_categories()

    def _load_categories(self):
        """Load unique values from selected category column"""
        col = self.cat_combo.currentText()
        if col not in self.original_df.columns:
            return
            
        # Get unique values (limit to 50 to avoid freezing)
        try:
            uniques = self.original_df[col].unique().to_list()
            uniques = [str(x) for x in uniques if x is not None][:50]
            
            self.map_table.setRowCount(len(uniques))
            
            coso_components = [
                "Control Environment", "Risk Assessment", 
                "Control Activities", "Info & Comm", "Monitoring"
            ]
            
            for i, val in enumerate(uniques):
                self.map_table.setItem(i, 0, QTableWidgetItem(val))
                
                # Combo for component
                combo = QComboBox()
                combo.addItems(coso_components)
                self.map_table.setCellWidget(i, 1, combo)
                
        except Exception as e:
            print(f"Error loading categories: {e}")

    def get_parameters(self):
        """Get parameters"""
        cat_col = self.cat_combo.currentText()
        risk_col = self.risk_combo.currentText()
        
        mapping = {}
        for i in range(self.map_table.rowCount()):
            cat_item = self.map_table.item(i, 0)
            comp_widget = self.map_table.cellWidget(i, 1)
            
            if cat_item and comp_widget:
                mapping[cat_item.text()] = comp_widget.currentText()
                
        return {
            "category_column": cat_col,
            "risk_score_column": risk_col,
            "mapping": mapping
        }

    def accept_changes(self):
        """Validate"""
        self.transformation_applied.emit("coso_risk_heatmap", self.get_parameters())
        self.accept()
