"""
Sidebar for CaatMaster - Inspired by data_workspace_app.py design
Clean, professional navigation with dataset management
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QToolButton, QListWidget, QListWidgetItem,
    QScrollArea, QMenu
)


class SidebarButton(QPushButton):
    """Custom styled button for sidebar"""
    def __init__(self, text, icon_text="", parent=None):
        super().__init__(parent)
        self.setText(f"  {icon_text}  {text}" if icon_text else f"  {text}")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(36)
        self.update_style(False)

    def update_style(self, selected):
        if selected:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #1e3a8a;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1e40af;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #9ca3af;
                    border: none;
                    border-radius: 4px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1f2937;
                    color: white;
                }
            """)


class DatasetItemWidget(QWidget):
    """Custom widget for dataset list items"""
    def __init__(self, name, row_count, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Icon
        icon = QLabel("📊")
        icon.setStyleSheet("font-size: 14px;")
        layout.addWidget(icon)

        # Name
        name_label = QLabel(name)
        name_label.setStyleSheet("""
            QLabel {
                color: #d1d5db;
                font-size: 12px;
            }
        """)
        name_label.setCursor(Qt.PointingHandCursor)
        layout.addWidget(name_label, 1)

        # Row count
        rows_label = QLabel(f"{row_count:,}")
        rows_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 11px;
            }
        """)
        layout.addWidget(rows_label)

        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border-radius: 4px;
            }
            QWidget:hover {
                background-color: #1f2937;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)


class Sidebar(QFrame):
    """Main sidebar widget for CaatMaster navigation with dataset management"""

    # Navigation signals
    navigation_requested = Signal(str)  # view_name
    dataset_selected = Signal(str)  # dataset_id
    upload_requested = Signal()  # Request to upload dataset

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.current_project = None
        self.current_dataset_id = None
        self.dataset_items = {}  # dataset_id -> list widget item
        self._setup_ui()

    def set_project(self, project):
        """Set the current project and update sidebar display"""
        self.current_project = project
        self._update_project_info()
        self._update_datasets_list()

    def _update_project_info(self):
        """Update the project info labels"""
        if self.current_project:
            # Update project name
            project_name = self.current_project.name if self.current_project.name else "No Project Selected"
            self.project_label.setText(project_name)

            # Update client name
            client_name = self.current_project.client_name if self.current_project.client_name else "No Client"
            self.client_label.setText(client_name)

            # Update phase button text
            phase = self.current_project.phase.capitalize() if self.current_project.phase else "Planning"
            self.planning_btn.setText(phase)
        else:
            self.project_label.setText("No Project Selected")
            self.client_label.setText("No Client")
            self.planning_btn.setText("Planning")

    def _update_datasets_list(self):
        """Update the datasets list with current project's datasets"""
        self.datasets_list.clear()
        self.dataset_items.clear()

        if not self.current_project:
            no_data_label = QListWidgetItem("No project loaded")
            no_data_label.setForeground(Qt.gray)
            self.datasets_list.addItem(no_data_label)
            return

        datasets = self.current_project.list_datasets()

        if not datasets:
            no_data_label = QListWidgetItem("No datasets yet")
            no_data_label.setForeground(Qt.gray)
            self.datasets_list.addItem(no_data_label)
            return

        for dataset in datasets:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, dataset.id)
            item.setText(dataset.name)

            # Store row count in item data
            row_count = dataset.metadata.get('row_count', 0)
            item.setData(Qt.UserRole + 1, row_count)

            self.datasets_list.addItem(item)
            self.dataset_items[dataset.id] = item

        # Select first dataset if available
        if datasets and not self.current_dataset_id:
            self.datasets_list.setCurrentRow(0)

    def _on_datasetClicked(self, item):
        """Handle dataset item click"""
        if item:
            dataset_id = item.data(Qt.UserRole)
            self.current_dataset_id = dataset_id
            self.dataset_selected.emit(dataset_id)

    def _on_datasetDoubleClicked(self, item):
        """Handle dataset item double click - navigate to data view"""
        if item:
            dataset_id = item.data(Qt.UserRole)
            self.dataset_selected.emit(dataset_id)
            self.navigation_requested.emit("data")

    def _setup_ui(self):
        """Setup the sidebar UI"""
        self.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border-right: 1px solid #1e293b;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                color: #d1d5db;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #1e3a8a;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #1f2937;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea QWidgetContents {
                background-color: transparent;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header section with padding
        header_content = QWidget()
        header_content.setStyleSheet("background-color: #0f172a;")
        header_layout = QVBoxLayout(header_content)
        header_layout.setContentsMargins(16, 16, 16, 8)

        # Logo/Title
        title_label = QLabel("CaatMaster")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 20px;
                font-weight: bold;
            }
        """)
        header_layout.addWidget(title_label)

        subtitle_label = QLabel("Project Workspace")
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #64748b;
                font-size: 12px;
            }
        """)
        header_layout.addWidget(subtitle_label)

        layout.addWidget(header_content)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: #0f172a;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 8, 16, 8)
        scroll_layout.setSpacing(8)

        # Project section
        project_label = QLabel("📁 PROJECT")
        project_label.setStyleSheet("""
            QLabel {
                color: #64748b;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
        """)
        scroll_layout.addWidget(project_label)

        # Project name
        self.project_label = QLabel("No Project Selected")
        self.project_label.setStyleSheet("""
            QLabel {
                color: #9ca3af;
                font-size: 13px;
                padding: 4px 0px;
            }
        """)
        scroll_layout.addWidget(self.project_label)

        # Client name
        self.client_label = QLabel("No Client")
        self.client_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 12px;
                padding-bottom: 8px;
            }
        """)
        scroll_layout.addWidget(self.client_label)

        # Phase button
        self.planning_btn = SidebarButton("Planning")
        self.planning_btn.setChecked(True)
        self.planning_btn.update_style(True)
        self.planning_btn.clicked.connect(lambda: self.navigation_requested.emit("planning"))
        scroll_layout.addWidget(self.planning_btn)

        # Datasets section
        datasets_header = QHBoxLayout()

        datasets_label = QLabel("📊 DATASETS")
        datasets_label.setStyleSheet("""
            QLabel {
                color: #64748b;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
                padding-top: 16px;
            }
        """)
        datasets_header.addWidget(datasets_label)

        datasets_header.addStretch()

        # Add dataset button
        add_dataset_btn = QPushButton("+")
        add_dataset_btn.setFixedSize(22, 22)
        add_dataset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        add_dataset_btn.setCursor(Qt.PointingHandCursor)
        add_dataset_btn.clicked.connect(self.upload_requested.emit)
        datasets_header.addWidget(add_dataset_btn)

        datasets_header_widget = QWidget()
        datasets_header_widget.setLayout(datasets_header)
        scroll_layout.addWidget(datasets_header_widget)

        # Datasets list
        self.datasets_list = QListWidget()
        self.datasets_list.setMaximumHeight(150)
        self.datasets_list.setSelectionMode(QListWidget.SingleSelection)
        self.datasets_list.itemClicked.connect(self._on_datasetClicked)
        self.datasets_list.itemDoubleClicked.connect(self._on_datasetDoubleClicked)
        scroll_layout.addWidget(self.datasets_list)

        # Workspace Mode section
        mode_label = QLabel("WORKSPACE MODE")
        mode_label.setStyleSheet("""
            QLabel {
                color: #475569;
                font-size: 11px;
                font-weight: bold;
                padding: 16px 0px 8px 0px;
                letter-spacing: 0.5px;
            }
        """)
        scroll_layout.addWidget(mode_label)

        # Data Workspace button
        self.data_workspace_btn = SidebarButton("Data Workspace", "💾")
        self.data_workspace_btn.setChecked(False)
        self.data_workspace_btn.update_style(False)
        self.data_workspace_btn.clicked.connect(lambda: self.navigation_requested.emit("data"))
        scroll_layout.addWidget(self.data_workspace_btn)

        # SQL Workspace button
        self.sql_workspace_btn = SidebarButton("SQL Workspace", "📝")
        self.sql_workspace_btn.clicked.connect(lambda: self.navigation_requested.emit("sql"))
        scroll_layout.addWidget(self.sql_workspace_btn)

        # Actions section
        actions_label = QLabel("ACTIONS")
        actions_label.setStyleSheet("""
            QLabel {
                color: #475569;
                font-size: 11px;
                font-weight: bold;
                padding: 16px 0px 8px 0px;
                letter-spacing: 0.5px;
            }
        """)
        scroll_layout.addWidget(actions_label)

        # Export for Review button
        self.export_review_btn = SidebarButton("Export for Review", "📤")
        self.export_review_btn.clicked.connect(lambda: self.navigation_requested.emit("export_review"))
        scroll_layout.addWidget(self.export_review_btn)

        scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # Bottom section
        bottom_content = QWidget()
        bottom_content.setStyleSheet("background-color: #0f172a;")
        bottom_layout = QVBoxLayout(bottom_content)
        bottom_layout.setContentsMargins(16, 8, 16, 16)

        # Bottom buttons
        self.back_btn = QPushButton("← Back to Projects")
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9ca3af;
                border: none;
                text-align: left;
                padding: 8px 0px;
                font-size: 13px;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(lambda: self.navigation_requested.emit("projects"))
        bottom_layout.addWidget(self.back_btn)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #9ca3af;
                border: none;
                text-align: left;
                padding: 8px 0px;
                font-size: 13px;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        self.settings_btn.setCursor(Qt.PointingHandCursor)
        self.settings_btn.clicked.connect(lambda: self.navigation_requested.emit("settings"))
        bottom_layout.addWidget(self.settings_btn)

        layout.addWidget(bottom_content)

    def set_active_button(self, button_name):
        """Set the active navigation button"""
        # Reset all buttons
        for btn in [self.planning_btn, self.data_workspace_btn, self.sql_workspace_btn]:
            btn.setChecked(False)
            btn.update_style(False)

        # Set active button
        if button_name == "planning" and self.planning_btn:
            self.planning_btn.setChecked(True)
            self.planning_btn.update_style(True)
        elif button_name == "data" and self.data_workspace_btn:
            self.data_workspace_btn.setChecked(True)
            self.data_workspace_btn.update_style(True)
        elif button_name == "sql" and self.sql_workspace_btn:
            self.sql_workspace_btn.setChecked(True)
            self.sql_workspace_btn.update_style(True)

    def add_dataset(self, dataset):
        """Add a dataset to the sidebar list"""
        if not self.current_project:
            return

        item = QListWidgetItem()
        item.setData(Qt.UserRole, dataset.id)
        item.setText(dataset.name)
        item.setData(Qt.UserRole + 1, dataset.metadata.get('row_count', 0))

        self.datasets_list.addItem(item)
        self.dataset_items[dataset.id] = item

        # Select the new dataset
        self.datasets_list.setCurrentItem(item)
        self.current_dataset_id = dataset.id
