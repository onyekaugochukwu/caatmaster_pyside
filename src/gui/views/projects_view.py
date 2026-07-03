"""
Projects View - Project management using file-based projects
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QTextEdit, QMessageBox, QDialog, QFormLayout,
    QLineEdit, QComboBox, QInputDialog, QFileDialog, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QAction, QFont
from pathlib import Path
import os
import json
from datetime import datetime
import uuid


class ProjectsView(QWidget):
    """Project management view using file-based projects"""

    project_open_requested = Signal(object)  # Signal when project should be opened (emits Project object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_path = None
        self.current_project_format = None  # "caat" or "json"
        self.projects_data = []  # List of (path, project_data) tuples
        self.setup_ui()

    def setup_ui(self):
        # Create a scroll area for the entire view
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(False)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: white;
                border: none;
            }
        """)

        # Create content widget
        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
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
        self.new_project_btn = QPushButton("New")
        self.new_project_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
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

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #f9fafb;
                border-color: #9ca3af;
            }
        """)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.load_projects)
        btn_layout.addWidget(self.refresh_btn)

        # Edit button
        self.edit_btn = QPushButton("✏️ Edit")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9fafb;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
                border-color: #9ca3af;
            }
            QPushButton:disabled {
                background-color: #f9fafb;
                color: #d1d5db;
                border-color: #e5e7eb;
            }
        """)
        self.edit_btn.clicked.connect(self.edit_project)
        self.edit_btn.setEnabled(False)
        btn_layout.addWidget(self.edit_btn)

        # Delete button
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #fef2f2;
                color: #dc2626;
                border: 1px solid #fecaca;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
            }
            QPushButton:disabled {
                background-color: #fef2f2;
                color: #fca5a5;
                border-color: #fecdd3;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_project)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)

        header_layout.addLayout(btn_layout)

        main_layout.addWidget(header)

        # Projects section
        projects_label = QLabel("Your Projects")
        projects_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }
        """)
        main_layout.addWidget(projects_label)

        # Projects table
        self.projects_table = QTableWidget()
        self.projects_table.setColumnCount(5)
        self.projects_table.setHorizontalHeaderLabels([
            "Name", "Client", "Type", "Phase", "Created"
        ])
        self.projects_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.projects_table.setSelectionMode(QTableWidget.SingleSelection)
        self.projects_table.horizontalHeader().setStretchLastSection(True)
        self.projects_table.cellClicked.connect(self.on_project_selected)
        self.projects_table.cellDoubleClicked.connect(self.on_project_double_clicked)
        self.projects_table.setAlternatingRowColors(True)
        self.projects_table.setMinimumHeight(300)
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
        main_layout.addWidget(self.projects_table)

        # Project details section
        details_label = QLabel("Project Details")
        details_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 700;
                color: #111827;
            }
        """)
        main_layout.addWidget(details_label)

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
        main_layout.addWidget(self.details_text)

        # Actions
        actions_layout = QHBoxLayout()

        self.open_btn = QPushButton("📂 Open Project")
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 20px;
                font-size: 13px;
                font-weight: 600;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #dbeafe;
                color: #93c5fd;
            }
        """)
        self.open_btn.clicked.connect(self.open_project)
        self.open_btn.setEnabled(False)
        actions_layout.addWidget(self.open_btn)



        actions_layout.addStretch()

        main_layout.addLayout(actions_layout)

        # Add stretch at the end to push content up
        main_layout.addStretch()

        # Set content_widget as the scroll area's widget
        scroll_area.setWidget(content_widget)

        # Set up the main widget layout (scroll area)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)

        # Load projects on startup
        self.load_projects()

    def load_projects(self):
        """Load all projects — .caat files (the app's native format) found
        in the default projects directory or previously opened from
        elsewhere (via the recent-projects index), plus any legacy .json
        project files for backward compatibility."""
        self.projects_data.clear()
        self.projects_table.setRowCount(0)

        from core.caat_format import peek_caat_metadata

        project_dirs = [
            Path.home() / "Documents" / "CaatMaster" / "Projects",
            Path.home() / "CaatMaster" / "Projects",
            Path.cwd() / "projects",
            Path.cwd() / "data" / "projects",
        ]

        caat_paths = set()
        for project_dir in project_dirs:
            if project_dir.exists():
                caat_paths.update(str(p) for p in project_dir.glob("*.caat"))

        # Merge in anything opened from a non-default location (e.g. Save As)
        try:
            from core.recent_projects import list_recent
            for entry in list_recent(limit=50):
                p = entry.get("path", "")
                if p.endswith(".caat"):
                    caat_paths.add(p)
        except Exception:
            pass

        rows = []
        for caat_path in caat_paths:
            try:
                meta = peek_caat_metadata(caat_path)
                rows.append({
                    "path": caat_path,
                    "format": "caat",
                    "name": meta.get("name", "Unknown"),
                    "client_name": meta.get("client_name") or "-",
                    "engagement_type": meta.get("engagement_type") or "-",
                    "phase": meta.get("phase") or "-",
                    "created": (meta.get("saved_at") or "Unknown").split("T")[0],
                    "meta": meta,
                })
            except Exception as e:
                print(f"Error reading project {caat_path}: {e}")

        # Legacy .json project files, still openable via ProjectExporter
        legacy_files = []
        for project_dir in project_dirs:
            if project_dir.exists():
                legacy_files.extend(project_dir.glob("*.json"))

        for project_path in legacy_files:
            try:
                with open(project_path, 'r') as f:
                    project_data = json.load(f)
                created = project_data.get('metadata', {}).get('created_at', 'Unknown')
                if isinstance(created, str):
                    created = created.split('T')[0]
                rows.append({
                    "path": str(project_path),
                    "format": "json",
                    "name": project_data.get('name', 'Unknown'),
                    "client_name": project_data.get('client_name') or '-',
                    "engagement_type": project_data.get('engagement_type') or '-',
                    "phase": project_data.get('phase') or '-',
                    "created": str(created),
                    "meta": project_data,
                })
            except Exception as e:
                print(f"Error loading project {project_path}: {e}")

        rows.sort(key=lambda r: r.get("created", ""), reverse=True)

        for row_data in rows:
            row = self.projects_table.rowCount()
            self.projects_table.insertRow(row)

            self.projects_table.setItem(row, 0, QTableWidgetItem(row_data["name"]))
            self.projects_table.setItem(row, 1, QTableWidgetItem(row_data["client_name"]))
            self.projects_table.setItem(row, 2, QTableWidgetItem(str(row_data["engagement_type"]).replace('_', ' ').title()))
            self.projects_table.setItem(row, 3, QTableWidgetItem(str(row_data["phase"]).replace('_', ' ').title()))
            self.projects_table.setItem(row, 4, QTableWidgetItem(row_data["created"]))

            self.projects_table.item(row, 0).setData(Qt.UserRole, row_data["path"])
            self.projects_table.item(row, 0).setData(Qt.UserRole + 1, row_data["format"])
            self.projects_data.append((row_data["path"], row_data["meta"]))

        if self.projects_table.rowCount() == 0:
            # Show empty state
            self.projects_table.insertRow(0)
            empty_item = QTableWidgetItem("No projects found. Click '+ New Project' to create one.")
            empty_item.setFlags(Qt.NoItemFlags)
            self.projects_table.setItem(0, 0, empty_item)
            self.projects_table.setSpan(0, 0, 1, 5)

    def on_project_selected(self, row: int, column: int):
        """Handle project selection"""
        if self.projects_table.rowCount() == 1 and self.projects_table.item(0, 0).text().startswith("No projects"):
            return

        item = self.projects_table.item(row, 0)
        if item:
            project_path = item.data(Qt.UserRole)
            self.current_project_format = item.data(Qt.UserRole + 1)
            self.current_project_path = project_path
            self.show_project_details(project_path)
            self.open_btn.setEnabled(True)
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)

    def on_project_double_clicked(self, row: int, column: int):
        """Handle project double-click to open project"""
        # First select the project (same as single click)
        self.on_project_selected(row, column)
        # If a project is selected, open it
        if self.current_project_path:
            self.open_project()

    def show_project_details(self, project_path: str):
        """Show project details"""
        try:
            if self.current_project_format == "caat":
                from core.caat_format import peek_caat_metadata
                meta = peek_caat_metadata(project_path)
                details = f"""<b>Name:</b> {meta.get('name', 'Unknown')}
<b>Client:</b> {meta.get('client_name') or 'Not specified'}
<b>Type:</b> {str(meta.get('engagement_type') or '-').replace('_', ' ').title()}
<b>Phase:</b> {str(meta.get('phase') or '-').replace('_', ' ').title()}
<b>Risk Score:</b> {meta.get('risk_score', '-')}/10

<b>Description:</b>
{meta.get('description') or 'No description'}

<b>Objectives:</b>
{meta.get('objectives') or 'None specified'}

<b>Last Saved:</b> {meta.get('saved_at', 'Unknown')}
<b>Datasets:</b> {meta.get('dataset_count', 0)}
<b>Location:</b> {project_path}
"""
                self.details_text.setHtml(details)
                return

            with open(project_path, 'r') as f:
                project_data = json.load(f)

            details = f"""<b>Name:</b> {project_data.get('name', 'Unknown')}
<b>Client:</b> {project_data.get('client_name', 'Not specified')}
<b>Type:</b> {project_data.get('engagement_type', '-').replace('_', ' ').title()}
<b>Phase:</b> {project_data.get('phase', '-').replace('_', ' ').title()}
<b>Risk Score:</b> {project_data.get('risk_score', '-')}/10

<b>Description:</b>
{project_data.get('description', 'No description')}

<b>Objectives:</b>
{project_data.get('objectives', 'None specified')}
"""

            metadata = project_data.get('metadata', {})
            details += f"""
<b>Created:</b> {metadata.get('created_at', 'Unknown')}
<b>Last Modified:</b> {metadata.get('last_modified', 'Unknown')}
<b>Datasets:</b> {len(project_data.get('datasets', {}))}
<b>Location:</b> {project_path}
"""

            self.details_text.setHtml(details)

        except Exception as e:
            self.details_text.setText(f"Error loading project details:\n{str(e)}")

    def new_project(self):
        """Create a new project"""
        # Emit signal to main window to show the New Project dialog
        self.project_open_requested.emit(None)  # None means create new
        QMessageBox.information(
            self,
            "New Project",
            "The New Project dialog will open. After creating the project, it will appear in this list."
        )

    def edit_project(self):
        """Edit the selected project's name"""
        if not self.current_project_path:
            return

        try:
            if self.current_project_format == "caat":
                from core.caat_format import load_caat, save_caat, peek_caat_metadata
                old_name = peek_caat_metadata(self.current_project_path).get('name', '')
                new_name, ok = QInputDialog.getText(
                    self, "Edit Project Name", "Project Name:", text=old_name
                )
                if ok and new_name.strip():
                    project = load_caat(self.current_project_path)
                    project.name = new_name.strip()
                    save_caat(project, self.current_project_path,
                              active_dataset_id=getattr(project, "last_active_dataset_id", None))
                    QMessageBox.information(self, "Success", "Project name updated successfully!")
                    self.load_projects()
                    self.show_project_details(self.current_project_path)
                return

            # Legacy .json project files
            with open(self.current_project_path, 'r') as f:
                project_data = json.load(f)

            old_name = project_data.get('name', '')
            new_name, ok = QInputDialog.getText(
                self,
                "Edit Project Name",
                "Project Name:",
                text=old_name
            )

            if ok and new_name.strip():
                project_data['name'] = new_name.strip()
                project_data.setdefault('id', str(uuid.uuid4()))
                project_data['metadata']['last_modified'] = datetime.now().isoformat()

                # Write back
                with open(self.current_project_path, 'w') as f:
                    json.dump(project_data, f, indent=2)

                QMessageBox.information(self, "Success", "Project name updated successfully!")
                self.load_projects()
                self.show_project_details(self.current_project_path)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to edit project:\n{str(e)}")

    def delete_project(self):
        """Delete the selected project"""
        if not self.current_project_path:
            return

        reply = QMessageBox.question(
            self,
            "Delete Project",
            "Are you sure you want to delete this project? The project file will be permanently deleted.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                os.remove(self.current_project_path)

                QMessageBox.information(self, "Success", "Project deleted successfully!")
                self.current_project_path = None
                self.open_btn.setEnabled(False)
                self.edit_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
                self.details_text.clear()
                self.load_projects()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete project:\n{str(e)}")

    def open_project(self):
        """Open the selected project - emit signal to main window"""
        if not self.current_project_path:
            return

        try:
            if self.current_project_format == "caat":
                from core.caat_format import load_caat
                project = load_caat(self.current_project_path)
            else:
                from core.project_manager import ProjectExporter
                project = ProjectExporter.import_project(self.current_project_path)

            if project:
                # Emit (project, path) so main window knows where to save
                # back to and can restore the dataset that was active when
                # this project was last saved.
                self.project_open_requested.emit((project, self.current_project_path))
            else:
                QMessageBox.warning(self, "Error", "Failed to load project.")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open project:\n{str(e)}"
            )
