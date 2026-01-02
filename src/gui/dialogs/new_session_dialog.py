"""New Session Dialog"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QDialogButtonBox
)
from PySide6.QtCore import Qt


class NewSessionDialog(QDialog):
    """Dialog for creating a new analysis session"""

    def __init__(self, parent=None):
        super().__init__(parent if parent else None)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.session_data = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("New Analysis Session")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Form layout
        form_layout = QFormLayout()

        # Session name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Initial Analysis, Fraud Investigation")
        form_layout.addRow("Session Name*:", self.name_input)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate_and_accept(self):
        """Validate inputs and accept dialog"""
        name = self.name_input.text().strip()
        if not name:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Validation Error", "Session name is required")
            return

        self.session_data = {
            'name': name,
        }

        self.accept()

    def get_session_data(self):
        """Return the session data"""
        return self.session_data
