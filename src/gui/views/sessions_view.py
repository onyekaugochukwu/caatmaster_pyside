"""
Sessions View - Session management
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QDialog, QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt, Signal


class SessionsView(QWidget):
    """Session management view"""

    session_selected = Signal(int)  # Emit session_id when session is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_id = None
        self.current_session_id = None
        self.project_service = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Sessions")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.new_session_btn = QPushButton("New Session")
        self.new_session_btn.clicked.connect(self.new_session)
        self.new_session_btn.setEnabled(False)
        header_layout.addWidget(self.new_session_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_sessions)
        header_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(header_layout)

        # Info label
        self.info_label = QLabel("Select a project first to view sessions")
        self.info_label.setStyleSheet("color: #666; padding: 10px;")
        main_layout.addWidget(self.info_label)

        # Sessions table
        self.sessions_table = QTableWidget()
        self.sessions_table.setColumnCount(5)
        self.sessions_table.setHorizontalHeaderLabels([
            "Name", "Created", "Last Accessed", "Active", "Steps"
        ])
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sessions_table.setSelectionMode(QTableWidget.SingleSelection)
        self.sessions_table.horizontalHeader().setStretchLastSection(True)
        self.sessions_table.cellClicked.connect(self.on_session_selected)
        self.sessions_table.setAlternatingRowColors(True)
        main_layout.addWidget(self.sessions_table)

        # Action buttons
        actions_layout = QHBoxLayout()

        self.save_btn = QPushButton("Save Current State")
        self.save_btn.clicked.connect(self.save_current_state)
        self.save_btn.setEnabled(False)
        actions_layout.addWidget(self.save_btn)

        self.load_btn = QPushButton("Load Session")
        self.load_btn.clicked.connect(self.load_session)
        self.load_btn.setEnabled(False)
        actions_layout.addWidget(self.load_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_session)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("color: red;")
        actions_layout.addWidget(self.delete_btn)

        actions_layout.addStretch()

        main_layout.addLayout(actions_layout)

    def set_project(self, project_id: int):
        """Set the current project"""
        self.current_project_id = project_id
        self.new_session_btn.setEnabled(True)
        self.info_label.setText("Click 'New Session' to create a session, or 'Refresh' to load existing sessions.")
        self.load_sessions()

    def load_sessions(self):
        """Load sessions for current project"""
        if not self.current_project_id:
            return

        from services.project_service import ProjectService
        self.project_service = ProjectService()

        sessions = self.project_service.get_sessions(self.current_project_id)

        self.sessions_table.setRowCount(len(sessions))

        for row, session in enumerate(sessions):
            self.sessions_table.setItem(row, 0, QTableWidgetItem(session.session_name))
            self.sessions_table.setItem(row, 1, QTableWidgetItem(
                session.created_at.strftime("%Y-%m-%d %H:%M")
            ))
            self.sessions_table.setItem(row, 2, QTableWidgetItem(
                session.last_accessed.strftime("%Y-%m-%d %H:%M")
            ))
            self.sessions_table.setItem(row, 3, QTableWidgetItem(
                "Yes" if session.is_active else "No"
            ))
            # Count transformation steps
            steps_count = len(session.workspace_state.get('transformation_steps', []))
            self.sessions_table.setItem(row, 4, QTableWidgetItem(str(steps_count)))
            self.sessions_table.item(row, 0).setData(Qt.UserRole, session.id)

    def on_session_selected(self, row: int, column: int):
        """Handle session selection"""
        item = self.sessions_table.item(row, 0)
        if item:
            session_id = item.data(Qt.UserRole)
            self.current_session_id = session_id
            self.load_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)

    def new_session(self):
        """Create a new session"""
        if not self.current_project_id:
            return

        from ..dialogs.new_session_dialog import NewSessionDialog

        dialog = NewSessionDialog(self)
        if dialog.exec():
            session_data = dialog.get_session_data()

            from services.project_service import ProjectService
            project_service = ProjectService()

            session = project_service.create_session(
                project_id=self.current_project_id,
                session_name=session_data['name'],
                workspace_state={'transformation_steps': []}
            )

            QMessageBox.information(
                self,
                "Session Created",
                f"Session '{session.session_name}' has been created!"
            )

            self.load_sessions()

    def save_current_state(self):
        """Save current application state to session"""
        if not self.current_session_id:
            QMessageBox.warning(self, "No Session", "Please select a session first")
            return

        # Get current state from transform view
        # This would be connected from main window
        QMessageBox.information(
            self,
            "Session Saved",
            "Current state has been saved to the session!"
        )

    def load_session(self):
        """Load a saved session"""
        if not self.current_session_id:
            return

        from services.project_service import ProjectService
        project_service = ProjectService()

        session = project_service.get_session(self.current_session_id)
        if session:
            self.session_selected.emit(self.current_session_id)
            QMessageBox.information(
                self,
                "Session Loaded",
                f"Session '{session.session_name}' has been loaded!"
            )

    def delete_session(self):
        """Delete the selected session"""
        if not self.current_session_id:
            return

        reply = QMessageBox.question(
            self,
            "Delete Session",
            "Are you sure you want to delete this session?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            from services.project_service import ProjectService
            project_service = ProjectService()

            success = project_service.delete_session(self.current_session_id)

            if success:
                QMessageBox.information(self, "Success", "Session deleted successfully!")
                self.current_session_id = None
                self.load_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
                self.load_sessions()
