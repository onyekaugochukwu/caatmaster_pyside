"""
SOX SoD Analysis Dialog
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QGroupBox, QGridLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView, QWidget, QMessageBox
)
from PySide6.QtCore import Qt
import polars as pl

from ..components.common_modals import BaseModal

class SoxSodDialog(BaseModal):
    """Dialog for SOX Segregation of Duties Analysis"""
    
    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("SOX SoD Analysis", dataframe, parent)
        self.resize(800, 600)
        
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        
        # 1. Column Selection
        col_group = QGroupBox("1. Map Columns")
        col_layout = QGridLayout(col_group)
        
        self.user_combo = QComboBox()
        self.user_combo.addItems(self.original_df.columns)
        
        self.action_combo = QComboBox()
        self.action_combo.addItems(self.original_df.columns)
        
        # Auto-guess
        for col in self.original_df.columns:
            lower = col.lower()
            if "user" in lower or "id" in lower:
                self.user_combo.setCurrentText(col)
            if "action" in lower or "activity" in lower or "role" in lower or "type" in lower:
                self.action_combo.setCurrentText(col)
        
        col_layout.addWidget(QLabel("User ID Column:"), 0, 0)
        col_layout.addWidget(self.user_combo, 0, 1)
        col_layout.addWidget(QLabel("Action/Role Column:"), 1, 0)
        col_layout.addWidget(self.action_combo, 1, 1)
        
        layout.addWidget(col_group)
        
        # 2. Conflict Matrix
        matrix_group = QGroupBox("2. Define Toxic Combinations")
        matrix_layout = QVBoxLayout(matrix_group)
        
        # Pre-defined templates
        self.template_combo = QComboBox()
        self.template_combo.addItem("Select a template to load...", None)
        self.template_combo.addItem("Procure to Pay (P2P)", [
            ("Create Vendor", "Pay Vendor"),
            ("Create PO", "Approve PO"),
            ("Receive Goods", "Approve Invoice")
        ])
        self.template_combo.addItem("Order to Cash (O2C)", [
            ("Create Customer", "Approve Credit Limit"),
            ("Create Sales Order", "Edit Price Master"),
            ("Post Payment", "Issue Credit Memo")
        ])
        self.template_combo.addItem("General Ledger", [
            ("Create Journal Entry", "Post Journal Entry"),
            ("Open Period", "Close Period")
        ])
        self.template_combo.currentIndexChanged.connect(self._load_template)
        
        matrix_layout.addWidget(QLabel("Load Template (Optional):"))
        matrix_layout.addWidget(self.template_combo)
        
        # Table
        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(2)
        self.rule_table.setHorizontalHeaderLabels(["Action A", "Action B (Conflict)"])
        self.rule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rule_table.setRowCount(5)
        
        matrix_layout.addWidget(self.rule_table)
        
        # Row controls
        row_btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("+ Add Row")
        add_row_btn.clicked.connect(lambda: self.rule_table.insertRow(self.rule_table.rowCount()))
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self.rule_table.setRowCount(0) or self.rule_table.setRowCount(5))
        
        row_btn_layout.addWidget(add_row_btn)
        row_btn_layout.addWidget(clear_btn)
        row_btn_layout.addStretch()
        matrix_layout.addLayout(row_btn_layout)
        
        layout.addWidget(matrix_group)
        
        # 3. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        run_btn = QPushButton("Scan for Conflicts")
        run_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; padding: 8px 16px;")
        run_btn.clicked.connect(self.accept_changes)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        
        layout.addLayout(btn_layout)

    def _load_template(self, index):
        """Load conflicts from template"""
        data = self.template_combo.itemData(index)
        if data:
            self.rule_table.setRowCount(len(data))
            for i, (a, b) in enumerate(data):
                self.rule_table.setItem(i, 0, QTableWidgetItem(a))
                self.rule_table.setItem(i, 1, QTableWidgetItem(b))

    def get_parameters(self):
        """Get dialog parameters"""
        user_col = self.user_combo.currentText()
        action_col = self.action_combo.currentText()
        
        conflicts = []
        for i in range(self.rule_table.rowCount()):
            item_a = self.rule_table.item(i, 0)
            item_b = self.rule_table.item(i, 1)
            
            if item_a and item_b and item_a.text().strip() and item_b.text().strip():
                conflicts.append({
                    "role_a": item_a.text().strip(),
                    "role_b": item_b.text().strip(),
                    "severity": "High"
                })
                
        return {
            "user_column": user_col,
            "action_column": action_col,
            "conflicts": conflicts
        }

    def accept_changes(self):
        """Validate and run"""
        params = self.get_parameters()
        
        if not params["conflicts"]:
            QMessageBox.warning(self, "No Rules", "Please define at least one conflict rule.")
            return
            
        self.transformation_applied.emit("sox_sod_analysis", params)
        self.accept()
