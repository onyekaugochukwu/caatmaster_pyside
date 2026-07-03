"""
Audit Programs gallery — save the current dataset's Applied Steps as a
reusable template, or apply a previously saved one to the active dataset.
"""
import qtawesome as qta
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QMessageBox, QTextEdit
)

from gui.theme import Colors
from core.audit_programs import list_programs, save_program, load_program, delete_program


class AuditProgramsDialog(QDialog):
    """Gallery of saved Audit Programs, with apply/save/delete."""

    programApplied = Signal(list)  # list of {operation_id, params} to replay

    def __init__(self, current_steps=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audit Programs")
        self.resize(520, 420)
        self.current_steps = current_steps or []

        layout = QVBoxLayout(self)

        info = QLabel(
            "Save this dataset's Applied Steps as a reusable Audit Program, or "
            "apply a saved program to the current dataset — reruns each step "
            "here, same as if you'd built them by hand."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(info)

        self.program_list = QListWidget()
        self.program_list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.program_list)

        self.description_label = QTextEdit()
        self.description_label.setReadOnly(True)
        self.description_label.setMaximumHeight(60)
        layout.addWidget(self.description_label)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Apply to Current Dataset")
        self.apply_btn.setIcon(qta.icon("fa5s.play", color=Colors.TEXT_ON_ACCENT))
        self.apply_btn.setObjectName("PrimaryButton")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self.apply_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setIcon(qta.icon("fa5s.trash-alt", color=Colors.DANGER))
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()

        self.save_current_btn = QPushButton("Save Current Steps As New Program...")
        self.save_current_btn.setIcon(qta.icon("fa5s.save", color=Colors.TEXT_PRIMARY))
        self.save_current_btn.setEnabled(bool(self.current_steps))
        self.save_current_btn.clicked.connect(self._on_save_current)
        btn_row.addWidget(self.save_current_btn)

        layout.addLayout(btn_row)

        self._refresh_list()

    def _refresh_list(self):
        self.program_list.clear()
        self._programs = list_programs()
        for program in self._programs:
            item = QListWidgetItem(f"{program['name']}  ({program['step_count']} step(s))")
            item.setData(1000, program)
            self.program_list.addItem(item)

    def _on_selection_changed(self, current, previous):
        has_selection = current is not None
        self.apply_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        if current:
            program = current.data(1000)
            self.description_label.setText(program.get("description", ""))
        else:
            self.description_label.clear()

    def _on_apply(self):
        item = self.program_list.currentItem()
        if not item:
            return
        program_meta = item.data(1000)
        try:
            data = load_program(program_meta["file_path"])
        except Exception as e:
            QMessageBox.critical(self, "Load Failed", f"Could not load program:\n{str(e)}")
            return

        self.programApplied.emit(data.get("steps", []))
        self.accept()

    def _on_save_current(self):
        if not self.current_steps:
            QMessageBox.information(self, "No Steps", "The current dataset has no applied steps to save.")
            return

        name, ok = QInputDialog.getText(self, "Save Audit Program", "Program name:")
        if not ok or not name.strip():
            return
        description, _ = QInputDialog.getMultiLineText(self, "Save Audit Program", "Description (optional):")

        try:
            save_program(name.strip(), description, self.current_steps)
            self._refresh_list()
            QMessageBox.information(self, "Saved", f"Audit Program '{name.strip()}' saved.")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save program:\n{str(e)}")

    def _on_delete(self):
        item = self.program_list.currentItem()
        if not item:
            return
        program = item.data(1000)
        reply = QMessageBox.question(
            self, "Delete Audit Program",
            f"Delete '{program['name']}'? This cannot be undone.",
        )
        if reply == QMessageBox.Yes:
            delete_program(program["file_path"])
            self._refresh_list()
