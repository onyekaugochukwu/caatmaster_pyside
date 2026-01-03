"""
Sidebar for CaatMaster - Inspired by data_workspace_app.py design
Clean, professional navigation with dataset management
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QToolButton, QListWidget, QListWidgetItem,
    QScrollArea, QMenu, QSizePolicy, QGraphicsDropShadowEffect
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
    dataset_rename_requested = Signal(str)  # dataset_id
    dataset_duplicate_requested = Signal(str)  # dataset_id
    dataset_delete_requested = Signal(str)  # dataset_id
    dataset_split_sheet_requested = Signal(str)  # dataset_id
    upload_requested = Signal()  # Request to upload dataset
    project_edit_requested = Signal()  # Request to edit current project
    project_delete_requested = Signal()  # Request to delete current project

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

            # Show project action buttons
            self.edit_project_btn.setVisible(True)
            self.delete_project_btn.setVisible(True)
        else:
            self.project_label.setText("No Project Selected")
            self.client_label.setText("No Client")

            # Hide project action buttons
            self.edit_project_btn.setVisible(False)
            self.delete_project_btn.setVisible(False)

    def _update_datasets_list(self):
        """Update the datasets list with current project's datasets"""
        self.datasets_list.clear()
        self.dataset_items.clear()

        if not self.current_project:
            return

        datasets = self.current_project.list_datasets()

        if not datasets:
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
        """Handle dataset item click (left click only)"""
        if item:
            dataset_id = item.data(Qt.UserRole)
            self.current_dataset_id = dataset_id
            self.dataset_selected.emit(dataset_id)

    def _on_datasetContextMenu(self, pos):
        """Handle right-click context menu for dataset items"""
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import QMenu

        item = self.datasets_list.itemAt(pos)
        if not item:
            return

        dataset_id = item.data(Qt.UserRole)
        dataset_name = item.text()

        menu = QMenu(self)

        # Dataset info
        info_action = QAction(f"📊 {dataset_name}", self)
        info_action.setEnabled(False)
        menu.addAction(info_action)
        menu.addSeparator()

        # View data action
        view_action = QAction("View Data", self)
        view_action.triggered.connect(lambda: self.dataset_selected.emit(dataset_id))
        menu.addAction(view_action)

        # Rename action
        rename_action = QAction("✏️ Rename", self)
        rename_action.triggered.connect(lambda: self.dataset_rename_requested.emit(dataset_id))
        menu.addAction(rename_action)

        # Duplicate action
        duplicate_action = QAction("📋 Duplicate", self)
        duplicate_action.triggered.connect(lambda: self.dataset_duplicate_requested.emit(dataset_id))
        menu.addAction(duplicate_action)

        # Split Sheet action
        split_action = QAction("✂️ Split Sheet", self)
        split_action.triggered.connect(lambda: self.dataset_split_sheet_requested.emit(dataset_id))
        menu.addAction(split_action)

        menu.addSeparator()

        # Delete action - styled differently
        delete_action = QAction("🗑️ Delete", self)
        delete_action.triggered.connect(lambda: self.dataset_delete_requested.emit(dataset_id))
        menu.addAction(delete_action)

        # Style the menu with white text for dark background
        menu.setStyleSheet("""
            QMenu {
                background-color: #1f2937;
                border: 1px solid #374151;
                padding: 5px;
                color: #ffffff;
                font-size: 13px;
            }
            QMenu::item {
                color: #ffffff;
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
            }
            QMenu::item:last {
                color: #ef4444;
            }
        """)

        # Show menu at cursor position
        menu.exec_(self.mapToGlobal(pos))

    def _on_datasetDoubleClicked(self, item):
        """Handle dataset item double click - navigate to transform view"""
        if item:
            dataset_id = item.data(Qt.UserRole)
            self.dataset_selected.emit(dataset_id)
            self.navigation_requested.emit("transform")

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
        header_layout.setContentsMargins(16, 12, 16, 8)

        # Workspace label
        subtitle_label = QLabel("Workspace")
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #64748b;
                font-size: 12px;
            }
        """)
        header_layout.addWidget(subtitle_label)

        layout.addWidget(header_content)

        # Scrollable content area - properly structured
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMinimumHeight(200)  # Ensure scroll area can shrink
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0f172a;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #1e293b;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #475569;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #64748b;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Create scroll content widget that holds ALL sidebar items
        scroll_content = QWidget()
        scroll_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        scroll_content.setStyleSheet("background-color: #0f172a;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 8, 16, 16)
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

        # Project name with action buttons
        project_row = QHBoxLayout()
        project_row.setContentsMargins(0, 0, 0, 0)
        project_row.setSpacing(8)

        self.project_label = QLabel("No Project Selected")
        self.project_label.setStyleSheet("""
            QLabel {
                color: #9ca3af;
                font-size: 13px;
                padding: 4px 0px;
            }
        """)
        project_row.addWidget(self.project_label, 1)

        # Project actions container (edit/delete buttons)
        self.project_actions_widget = QWidget()
        project_actions_layout = QHBoxLayout(self.project_actions_widget)
        project_actions_layout.setContentsMargins(0, 0, 0, 0)
        project_actions_layout.setSpacing(4)

        # Edit project button
        self.edit_project_btn = QPushButton()
        self.edit_project_btn.setFixedSize(22, 22)
        self.edit_project_btn.setText("✏")
        self.edit_project_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6b7280;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #374151;
                color: white;
            }
        """)
        self.edit_project_btn.setCursor(Qt.PointingHandCursor)
        self.edit_project_btn.clicked.connect(self.project_edit_requested.emit)
        self.edit_project_btn.setVisible(False)  # Hidden until project is set
        project_actions_layout.addWidget(self.edit_project_btn)

        # Delete project button
        self.delete_project_btn = QPushButton()
        self.delete_project_btn.setFixedSize(22, 22)
        self.delete_project_btn.setText("🗑")
        self.delete_project_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6b7280;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #374151;
                color: #ef4444;
            }
        """)
        self.delete_project_btn.setCursor(Qt.PointingHandCursor)
        self.delete_project_btn.clicked.connect(self.project_delete_requested.emit)
        self.delete_project_btn.setVisible(False)  # Hidden until project is set
        project_actions_layout.addWidget(self.delete_project_btn)

        project_row.addWidget(self.project_actions_widget)
        scroll_layout.addLayout(project_row)

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
        self.datasets_list.setMinimumHeight(100)
        self.datasets_list.setMaximumHeight(300)
        self.datasets_list.setSelectionMode(QListWidget.SingleSelection)
        self.datasets_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.datasets_list.customContextMenuRequested.connect(self._on_datasetContextMenu)
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
        self.data_workspace_btn = SidebarButton("Data", "💾")
        self.data_workspace_btn.setChecked(False)
        self.data_workspace_btn.update_style(False)
        self.data_workspace_btn.clicked.connect(lambda: self.navigation_requested.emit("data"))
        scroll_layout.addWidget(self.data_workspace_btn)

        # SQL Query button
        self.sql_workspace_btn = SidebarButton("SQL Query", "📝")
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

        # Add some spacing
        scroll_layout.addSpacing(16)

        # Bottom buttons (now INSIDE scroll area for full scrollability)
        # Back to Projects button
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
        scroll_layout.addWidget(self.back_btn)

        # Settings button
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
        scroll_layout.addWidget(self.settings_btn)

        # Add bottom spacing
        scroll_layout.addSpacing(16)

        # Set the scroll content as the scroll area widget
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def set_active_button(self, button_name):
        """Set the active navigation button"""
        # Reset all buttons
        for btn in [self.data_workspace_btn, self.sql_workspace_btn]:
            btn.setChecked(False)
            btn.update_style(False)

        # Set active button
        button_map = {
            "data": self.data_workspace_btn,
            "transform": self.data_workspace_btn,  # Share Data button highlight
            "sql": self.sql_workspace_btn,
        }

        if button_name in button_map and button_map[button_name]:
            button_map[button_name].setChecked(True)
            button_map[button_name].update_style(True)

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

        # Select the new dataset and emit signal
        self.datasets_list.setCurrentItem(item)
        self.current_dataset_id = dataset.id
        self.dataset_selected.emit(dataset.id)
