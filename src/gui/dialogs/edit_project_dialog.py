"""Edit Project Dialog"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QComboBox,
    QPushButton, QDialogButtonBox
)
from PySide6.QtCore import Qt
from core.models import Project


class EditProjectDialog(QDialog):
    """Dialog for editing an existing project"""

    def __init__(self, project: Project, parent=None):
        super().__init__(parent if parent else None)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.project = project
        self.project_data = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle(f"Edit Project: {self.project.name}")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Form layout
        form_layout = QFormLayout()

        # Project name
        self.name_input = QLineEdit()
        self.name_input.setText(self.project.name)
        form_layout.addRow("Project Name*:", self.name_input)

        # Client name
        self.client_input = QLineEdit()
        self.client_input.setText(self.project.client_name or "")
        form_layout.addRow("Client Name:", self.client_input)

        # Engagement type
        self.engagement_combo = QComboBox()
        self.engagement_combo.addItems([
            "Financial Audit",
            "Compliance Review",
            "Internal Audit",
            "Investigation",
            "Consulting"
        ])
        # Convert back to readable format
        type_map = {
            "audit": "Financial Audit",
            "review": "Compliance Review",
            "internal_audit": "Internal Audit",
            "investigation": "Investigation",
            "consulting": "Consulting"
        }
        current_type = type_map.get(self.project.engagement_type, "Financial Audit")
        self.engagement_combo.setCurrentText(current_type)
        form_layout.addRow("Engagement Type:", self.engagement_combo)

        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Planning", "Active", "Completed", "Archived"])
        status_map = {
            "planning": "Planning",
            "active": "Active",
            "completed": "Completed",
            "archived": "Archived"
        }
        current_status = status_map.get(self.project.status, "Planning")
        self.status_combo.setCurrentText(current_status)
        form_layout.addRow("Status:", self.status_combo)

        # Description
        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(80)
        self.description_input.setPlainText(self.project.description or "")
        form_layout.addRow("Description:", self.description_input)

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
            QMessageBox.warning(self, "Validation Error", "Project name is required")
            return

        # Convert engagement type back to database format
        engagement_map = {
            "Financial Audit": "audit",
            "Compliance Review": "review",
            "Internal Audit": "internal_audit",
            "Investigation": "investigation",
            "Consulting": "consulting"
        }

        # Convert status back to database format
        status_map = {
            "Planning": "planning",
            "Active": "active",
            "Completed": "completed",
            "Archived": "archived"
        }

        self.project_data = {
            'name': name,
            'client_name': self.client_input.text().strip() or None,
            'engagement_type': engagement_map[self.engagement_combo.currentText()],
            'status': status_map[self.status_combo.currentText()],
            'description': self.description_input.toPlainText().strip() or None,
        }

        self.accept()

    def get_project_data(self):
        """Return the project data"""
        return self.project_data
