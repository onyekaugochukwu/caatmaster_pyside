"""
Sidebar Widget for CAATmaster
Provides a tree-based navigation for projects, sessions, and datasets.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QAbstractItemView,
    QLabel, QPushButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
from pathlib import Path


class SidebarWidget(QWidget):
    """
    A widget that displays a tree view for navigating projects, sessions,
    and other artifacts, complete with a header and actions.
    """
    item_selected = Signal(str, object)
    new_project_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")

        # --- Main Layout ---
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # --- Header ---
        header_widget = QWidget()
        header_widget.setObjectName("SidebarHeader")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel("PROJECTS")
        title_label.setObjectName("SidebarTitle")
        
        add_project_btn = QPushButton("+")
        add_project_btn.setObjectName("AddProjectButton")
        add_project_btn.setFixedSize(24, 24)
        add_project_btn.clicked.connect(self.new_project_requested)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(add_project_btn)
        
        self.layout.addWidget(header_widget)

        # --- Tree View ---
        self.tree_view = QTreeView()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Explicitly set scrollbar policy to fix the bug
        self.tree_view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tree_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.layout.addWidget(self.tree_view)

        # --- Model Setup ---
        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)
        self.root_item = self.model.invisibleRootItem()

        # --- Connections ---
        self.tree_view.clicked.connect(self.on_item_clicked)
        
        # --- Icons ---
        self.icon_path = Path(__file__).parent.parent.parent / "resources" / "icons"
        self.project_icon = QIcon(str(self.icon_path / "project_icon.svg"))
        self.session_icon = QIcon(str(self.icon_path / "session_icon.svg"))
        self.dataset_icon = QIcon(str(self.icon_path / "dataset_icon.svg"))

        # --- Populate with dummy data for testing ---
        self.load_dummy_data()

    def on_item_clicked(self, index):
        """Handle item clicks and emit a signal."""
        item = self.model.itemFromIndex(index)
        item_type = item.data(Qt.UserRole + 1)
        item_id = item.data(Qt.UserRole + 2)

        if item_type and item_id:
            self.item_selected.emit(item_type, item_id)

    def load_projects(self, projects: list):
        """
        Populates the tree view with a list of project objects.
        """
        self.model.clear()
        self.root_item = self.model.invisibleRootItem()

        for proj in projects:
            project_item = QStandardItem(self.project_icon, proj.name)
            project_item.setData("project", Qt.UserRole + 1)
            project_item.setData(proj.id, Qt.UserRole + 2)
            self.root_item.appendRow(project_item)

            if hasattr(proj, 'sessions'):
                for sess in proj.sessions:
                    session_item = QStandardItem(self.session_icon, sess.session_name)
                    session_item.setData("session", Qt.UserRole + 1)
                    session_item.setData(sess.id, Qt.UserRole + 2)
                    project_item.appendRow(session_item)
            
            if hasattr(proj, 'datasets'):
                 for ds in proj.datasets:
                    dataset_item = QStandardItem(self.dataset_icon, ds.name)
                    dataset_item.setData("dataset", Qt.UserRole + 1)
                    dataset_item.setData(ds.id, Qt.UserRole + 2)
                    project_item.appendRow(dataset_item)

    def load_dummy_data(self):
        """Populates the tree with enough dummy data to require scrolling."""
        self.model.clear()
        self.root_item = self.model.invisibleRootItem()

        for i in range(1, 21): # Create 20 projects to ensure overflow
            proj_item = QStandardItem(f"Project {i}")
            proj_item.setData("project", Qt.UserRole + 1)
            proj_item.setData(i, Qt.UserRole + 2)
            proj_item.setIcon(self.project_icon)
            self.root_item.appendRow(proj_item)

            if i == 1: # Add details to the first project
                sess1 = QStandardItem("Q4 2025 Audit")
                sess1.setData("session", Qt.UserRole + 1)
                sess1.setData(101, Qt.UserRole + 2)
                sess1.setIcon(self.session_icon)
                proj_item.appendRow(sess1)

                ds1 = QStandardItem("Journal Entries.csv")
                ds1.setData("dataset", Qt.UserRole + 1)
                ds1.setData(1001, Qt.UserRole + 2)
                ds1.setIcon(self.dataset_icon)
                sess1.appendRow(ds1)

                ds2 = QStandardItem("All Transactions 2024.parquet")
                ds2.setData("dataset", Qt.UserRole + 1)
                ds2.setData(1002, Qt.UserRole + 2)
                ds2.setIcon(self.dataset_icon)
                proj_item.appendRow(ds2)

        self.tree_view.expandAll()

    def set_style(self, qss: str):
        """Applies a stylesheet to the sidebar."""
        self.setStyleSheet(qss)

