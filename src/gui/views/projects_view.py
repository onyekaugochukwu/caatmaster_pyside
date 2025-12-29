"""
Projects View - Project management
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTextEdit, QMessageBox, QDialog, QFormLayout,
    QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QAction, QFont
from pathlib import Path


class ProjectsView(QWidget):
    """Project management view"""

    project_selected = Signal(int)  # Emit project_id when project is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_id = None
        self.project_service = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Left side - Title
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)

        title = QLabel("Projects")
        title.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 700;
                color: #111827;
            }
        """)
        left_layout.addWidget(title)

        subtitle = QLabel("Manage your audit projects and datasets")
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #374151;
            }
        """)
        left_layout.addWidget(subtitle)

        header_layout.addLayout(left_layout, 1)

        # Right side - Actions
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        # New project button
        self.new_project_btn = QPushButton("+ New Project")
        self.new_project_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)
        self.new_project_btn.setCursor(Qt.PointingHandCursor)
        self.new_project_btn.clicked.connect(self.new_project)
        btn_layout.addWidget(self.new_project_btn)

        header_layout.addLayout(btn_layout)

        main_layout.addWidget(header)

        # Create splitter
        splitter = QSplitter(Qt.Vertical)

        # Projects section
        projects_widget = QWidget()
        projects_layout = QVBoxLayout(projects_widget)
        projects_layout.setContentsMargins(0, 0, 0, 0)
        projects_layout.setSpacing(12)

        projects_label = QLabel("Your Projects")
        projects_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }
        """)
        projects_layout.addWidget(projects_label)

        # Projects table
        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(5)
        self.projects_table.setHorizontalHeaderLabels([
            "Name", "Client", "Type", "Status", "Created"
        ])
        self.projects_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.projects_table.setSelectionMode(QTableWidget.SingleSelection)
        self.projects_table.horizontalHeader().setStretchLastSection(True)
        self.projects_table.cellClicked.connect(self.on_project_selected)
        self.projects_table.setAlternatingRowColors(True)
        self.projects_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background-color: white;
                gridline-color: #f3f4f6;
            }
            QTableWidget::item {
                padding: 10px 8px;
                color: #111827;
                font-size: 13px;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #111827;
            }
            QHeaderView::section {
                background-color: #f9fafb;
                color: #374151;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-bottom: 1px solid #e5e7eb;
                border-right: 1px solid #f3f4f6;
                padding: 10px 8px;
            }
        """)
        self.projects_table.verticalHeader().setVisible(False)
        self.projects_table.verticalHeader().setDefaultSectionSize(40)
        projects_layout.addWidget(self.projects_table)

        splitter.addWidget(projects_widget)

        # Project details
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 16, 0, 0)
        details_layout.setSpacing(12)

        details_label = QLabel("Project Details")
        details_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }
        """)
        details_layout.addWidget(details_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 12px;
                color: #111827;
                font-size: 13px;
            }
        """)
        details_layout.addWidget(self.details_text)

        # Actions
        actions_layout = QHBoxLayout()

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9fafb;
                color: #374151;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
            }
            QPushButton:disabled {
                background-color: #f3f4f6;
                color: #9ca3af;
            }
        """)
        self.edit_btn.clicked.connect(self.edit_project)
        self.edit_btn.setEnabled(False)
        actions_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #fef2f2;
                color: #dc2626;
                border: 1px solid #fecaca;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
            }
            QPushButton:disabled {
                background-color: #fef2f2;
                color: #fca5a5;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_project)
        self.delete_btn.setEnabled(False)
        actions_layout.addWidget(self.delete_btn)

        self.open_btn = QPushButton("Open Project")
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #93c5fd;
            }
        """)
        self.open_btn.clicked.connect(self.open_project)
        self.open_btn.setEnabled(False)
        actions_layout.addWidget(self.open_btn)

        actions_layout.addStretch()

        details_layout.addLayout(actions_layout)
        splitter.addWidget(details_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

        # Load projects on startup
        self.load_projects()

    def load_projects(self):
        """Load all projects"""
        from services.project_service import ProjectService

        self.project_service = ProjectService()
        projects = self.project_service.get_projects()

        self.projects_table.setRowCount(len(projects))

        for row, project in enumerate(projects):
            self.projects_table.setItem(row, 0, QTableWidgetItem(project.name))
            self.projects_table.setItem(row, 1, QTableWidgetItem(project.client_name or "-"))
            self.projects_table.setItem(row, 2, QTableWidgetItem(project.engagement_type))
            self.projects_table.setItem(row, 3, QTableWidgetItem(project.status))
            self.projects_table.setItem(row, 4, QTableWidgetItem(
                project.created_at.strftime("%Y-%m-%d")
            ))
            self.projects_table.item(row, 0).setData(Qt.UserRole, project.id)

    def on_project_selected(self, row: int, column: int):
        """Handle project selection"""
        item = self.projects_table.item(row, 0)
        if item:
            project_id = item.data(Qt.UserRole)
            self.current_project_id = project_id
            self.show_project_details(project_id)
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
            self.open_btn.setEnabled(True)

    def show_project_details(self, project_id: int):
        """Show project details"""
        project = self.project_service.get_project(project_id)
        if not project:
            return

        details = f"""<b>Name:</b> {project.name}
<b>Status:</b> {project.status}
<b>Type:</b> {project.engagement_type}
<b>Client:</b> {project.client_name or 'Not specified'}
<b>Created:</b> {project.created_at.strftime('%Y-%m-%d %H:%M')}

<b>Description:</b>
{project.description or 'No description'}
"""

        # Count datasets
        datasets = self.project_service.get_project_datasets(project_id)
        details += f"\n<b>Datasets:</b> {len(datasets)}"

        # Count sessions
        sessions = self.project_service.get_sessions(project_id)
        details += f"\n<b>Sessions:</b> {len(sessions)}"

        self.details_text.setHtml(details)

    def new_project(self):
        """Create a new project"""
        from ..dialogs.project_dialog import NewProjectDialog

        dialog = NewProjectDialog(self)
        if dialog.exec():
            project_data = dialog.get_project_data()

            project = self.project_service.create_project(
                name=project_data['name'],
                description=project_data.get('description'),
                client_name=project_data.get('client_name'),
                engagement_type=project_data.get('engagement_type', 'audit')
            )

            QMessageBox.information(
                self,
                "Project Created",
                f"Project '{project.name}' has been created successfully!"
            )

            self.load_projects()

    def edit_project(self):
        """Edit the selected project"""
        if not self.current_project_id:
            return

        from ..dialogs.edit_project_dialog import EditProjectDialog

        project = self.project_service.get_project(self.current_project_id)
        if not project:
            return

        dialog = EditProjectDialog(project, self)
        if dialog.exec():
            project_data = dialog.get_project_data()

            updated = self.project_service.update_project(
                self.current_project_id,
                name=project_data.get('name'),
                description=project_data.get('description'),
                status=project_data.get('status')
            )

            if updated:
                QMessageBox.information(self, "Success", "Project updated successfully!")
                self.load_projects()
                self.show_project_details(self.current_project_id)

    def delete_project(self):
        """Delete the selected project"""
        if not self.current_project_id:
            return

        reply = QMessageBox.question(
            self,
            "Delete Project",
            "Are you sure you want to delete this project? All datasets and sessions will be lost.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success = self.project_service.delete_project(self.current_project_id)

            if success:
                QMessageBox.information(self, "Success", "Project deleted successfully!")
                self.current_project_id = None
                self.edit_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
                self.open_btn.setEnabled(False)
                self.details_text.clear()
                self.load_projects()

    def open_project(self):
        """Open the selected project"""
        if not self.current_project_id:
            return

        project = self.project_service.get_project(self.current_project_id)
        if project:
            self.project_selected.emit(self.current_project_id)
            QMessageBox.information(
                self,
                "Project Opened",
                f"Project '{project.name}' is now active!"
            )
