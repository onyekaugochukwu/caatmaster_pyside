"""
Query Parameters dialog — manage the project's reusable named values
(materiality threshold, period dates, currency, ...) that steps and SQL
queries can reference as {{name}} instead of a hardcoded value.
"""
import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel
)

from gui.theme import Colors


class ParametersDialog(QDialog):
    """Edit a project's named parameters as a simple name/value table."""

    def __init__(self, parameters: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Query Parameters")
        self.resize(480, 360)
        self._result_parameters = dict(parameters)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Reference a parameter in a SQL step as {{name}} — e.g. "
            "\"WHERE amount > {{materiality_threshold}}\". Change the value here "
            "and every step that uses it picks up the new value next time it runs."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Name", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for name, value in parameters.items():
            self._add_row(name, str(value))
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Parameter")
        add_btn.setIcon(qta.icon("fa5s.plus", color=Colors.TEXT_PRIMARY))
        add_btn.clicked.connect(lambda: self._add_row("", ""))
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setIcon(qta.icon("fa5s.trash-alt", color=Colors.DANGER))
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        dialog_btn_row = QHBoxLayout()
        dialog_btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        dialog_btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._on_save)
        dialog_btn_row.addWidget(save_btn)
        layout.addLayout(dialog_btn_row)

    def _add_row(self, name: str, value: str):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(value))

    def _remove_selected(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def _on_save(self):
        result = {}
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            value = value_item.text().strip() if value_item else ""
            if name:
                result[name] = value
        self._result_parameters = result
        self.accept()

    def get_parameters(self) -> dict:
        return self._result_parameters
