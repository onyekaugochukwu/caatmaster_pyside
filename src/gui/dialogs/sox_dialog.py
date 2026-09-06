"""
SOX SoD Analysis Dialog
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QGroupBox, QGridLayout, QTableWidget, 
    QTableWidgetItem, QHeaderView, QWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal
import polars as pl

from ..components.common_modals import BaseModal, create_primary_button

class SoxSodDialog(BaseModal):
    """Dialog for SOX Segregation of Duties Analysis"""

    # Not inherited from BaseModal (only financial_ratios_dialog.py and
    # promote_row_header_dialog.py define this pattern) - without it,
    # `self.transformation_applied.emit(...)` below raised AttributeError
    # on every "Scan for Conflicts" click, so this dialog never actually
    # produced a result.
    transformation_applied = Signal(str, dict)  # operation_id, parameters

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
        
        # Table - a third action column is optional: leave it blank for an
        # ordinary pairwise conflict, or fill it in for a 3-way toxic
        # combination (a user must hold ALL non-blank actions in the row
        # to be flagged, not just any two).
        self.rule_table = QTableWidget()
        self.rule_table.setColumnCount(4)
        self.rule_table.setHorizontalHeaderLabels(
            ["Action A", "Action B", "Action C (optional, 3-way)", "Severity"]
        )
        self.rule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.rule_table.setRowCount(5)
        for row in range(self.rule_table.rowCount()):
            self._add_severity_combo(row)

        matrix_layout.addWidget(self.rule_table)
        
        # Row controls
        row_btn_layout = QHBoxLayout()
        add_row_btn = QPushButton("+ Add Row")
        add_row_btn.clicked.connect(self._add_row)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_rows)
        
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
        
        run_btn = create_primary_button("Scan for Conflicts")
        run_btn.clicked.connect(self.accept_changes)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        
        layout.addLayout(btn_layout)

    def _add_severity_combo(self, row: int):
        combo = QComboBox()
        combo.addItems(["High", "Critical", "Medium", "Low"])
        self.rule_table.setCellWidget(row, 3, combo)

    def _add_row(self):
        row = self.rule_table.rowCount()
        self.rule_table.insertRow(row)
        self._add_severity_combo(row)

    def _clear_rows(self):
        self.rule_table.setRowCount(0)
        self.rule_table.setRowCount(5)
        for row in range(5):
            self._add_severity_combo(row)

    def _load_template(self, index):
        """Load conflicts from template"""
        data = self.template_combo.itemData(index)
        if data:
            self.rule_table.setRowCount(len(data))
            for i, (a, b) in enumerate(data):
                self.rule_table.setItem(i, 0, QTableWidgetItem(a))
                self.rule_table.setItem(i, 1, QTableWidgetItem(b))
                self._add_severity_combo(i)

    def get_parameters(self):
        """Get dialog parameters"""
        user_col = self.user_combo.currentText()
        action_col = self.action_combo.currentText()

        conflicts = []
        for i in range(self.rule_table.rowCount()):
            roles = []
            for col in (0, 1, 2):
                item = self.rule_table.item(i, col)
                if item and item.text().strip():
                    roles.append(item.text().strip())

            if len(roles) >= 2:
                severity_widget = self.rule_table.cellWidget(i, 3)
                severity = severity_widget.currentText() if severity_widget else "High"
                conflicts.append({"roles": roles, "severity": severity})

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


class SoxAccessReviewDialog(BaseModal):
    """Dialog for the SOX ITGC User Access Review test - flags activity by
    a terminated/inactive user. Works on whatever's already in the current
    dataset: if the activity log doesn't already carry the user's status,
    join it in first via the existing Join Datasets step, then run this."""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__("SOX Access Review", dataframe, parent)
        self.resize(600, 420)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Flags rows belonging to a terminated/inactive user. If your activity log doesn't "
            "already have a status column, join it to your user-master extract first (Join "
            "Datasets), then run this."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        col_group = QGroupBox("Map Columns")
        col_layout = QGridLayout(col_group)

        self.status_combo = QComboBox()
        self.status_combo.addItems(self.original_df.columns)

        self.activity_date_combo = QComboBox()
        self.activity_date_combo.addItem("(none)", None)
        for col in self.original_df.columns:
            self.activity_date_combo.addItem(col, col)

        self.termination_date_combo = QComboBox()
        self.termination_date_combo.addItem("(none)", None)
        for col in self.original_df.columns:
            self.termination_date_combo.addItem(col, col)

        for col in self.original_df.columns:
            lower = col.lower()
            if "status" in lower or "employment" in lower:
                self.status_combo.setCurrentText(col)
            if "activity" in lower and "date" in lower:
                idx = self.activity_date_combo.findData(col)
                if idx >= 0:
                    self.activity_date_combo.setCurrentIndex(idx)
            if "termination" in lower and "date" in lower:
                idx = self.termination_date_combo.findData(col)
                if idx >= 0:
                    self.termination_date_combo.setCurrentIndex(idx)

        col_layout.addWidget(QLabel("User Status Column:"), 0, 0)
        col_layout.addWidget(self.status_combo, 0, 1)
        col_layout.addWidget(QLabel("Activity Date Column (optional):"), 1, 0)
        col_layout.addWidget(self.activity_date_combo, 1, 1)
        col_layout.addWidget(QLabel("Termination Date Column (optional):"), 2, 0)
        col_layout.addWidget(self.termination_date_combo, 2, 1)

        layout.addWidget(col_group)

        values_group = QGroupBox("Status Values Meaning \"No Longer Should Have Access\"")
        values_layout = QVBoxLayout(values_group)
        from PySide6.QtWidgets import QLineEdit
        self.terminated_values_edit = QLineEdit("Terminated, Inactive, Disabled, Suspended")
        self.terminated_values_edit.setToolTip("Comma-separated. Matching is case/whitespace-insensitive.")
        values_layout.addWidget(self.terminated_values_edit)
        layout.addWidget(values_group)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Run Access Review")
        run_btn.clicked.connect(self.accept_changes)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(run_btn)
        layout.addLayout(btn_layout)

    def get_parameters(self):
        terminated_values = [
            v.strip() for v in self.terminated_values_edit.text().split(",") if v.strip()
        ]
        return {
            "status_column": self.status_combo.currentText(),
            "terminated_values": terminated_values or None,
            "activity_date_column": self.activity_date_combo.currentData(),
            "termination_date_column": self.termination_date_combo.currentData(),
        }

    def accept_changes(self):
        self.transformation_applied.emit("sox_access_review", self.get_parameters())
        self.accept()
