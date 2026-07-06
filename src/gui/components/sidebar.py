"""
Sidebar for CaatMaster — the "Queries" pane.
Light, clean navigation with dataset management.
"""
from typing import List

import qtawesome as qta
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QToolButton, QListWidget, QListWidgetItem,
    QScrollArea, QMenu, QSizePolicy
)

from gui.theme import Colors


def _icon(name: str, color: str = Colors.TEXT_SECONDARY):
    return qta.icon(name, color=color)


class SidebarButton(QPushButton):
    """Custom styled button for sidebar"""
    def __init__(self, text, icon_name="", parent=None):
        super().__init__(parent)
        self.setText(f"  {text}")
        if icon_name:
            self.setIcon(_icon(icon_name))
            self.setIconSize(QSize(14, 14))
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(36)
        self.update_style(False)

    def update_style(self, selected):
        if selected:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.ACCENT_SOFT};
                    color: {Colors.ACCENT_PRESSED};
                    border: none;
                    border-radius: 4px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 13px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {Colors.BG_SELECTED_STRONG};
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {Colors.TEXT_SECONDARY};
                    border: none;
                    border-radius: 4px;
                    text-align: left;
                    padding-left: 12px;
                    font-size: 13px;
                }}
                QPushButton:hover {{
                    background-color: {Colors.BG_TERTIARY};
                    color: {Colors.TEXT_PRIMARY};
                }}
            """)


class DatasetItemWidget(QWidget):
    """Custom widget for dataset list items"""
    def __init__(self, name, row_count, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        icon = QLabel()
        icon.setPixmap(_icon("fa5s.table", color=Colors.TEXT_TERTIARY).pixmap(14, 14))
        layout.addWidget(icon)

        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 12px;
            }}
        """)
        name_label.setCursor(Qt.PointingHandCursor)
        layout.addWidget(name_label, 1)

        rows_label = QLabel(f"{row_count:,}")
        rows_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 11px;
            }}
        """)
        layout.addWidget(rows_label)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
                border-radius: 4px;
            }}
            QWidget:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
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
    dataset_refresh_requested = Signal(str)  # dataset_id
    dataset_visualize_requested = Signal(str)  # dataset_id
    join_datasets_requested = Signal(str)  # source_dataset_id
    append_datasets_requested = Signal(str)  # source_dataset_id
    upload_requested = Signal()  # Request to upload dataset
    cleaning_wizard_requested = Signal()  # Request to open the Data Cleaning Wizard
    paste_requested = Signal()  # Request to create a dataset from clipboard
    project_edit_requested = Signal()  # Request to edit current project
    project_delete_requested = Signal()  # Request to delete current project
    toggle_ai_panel = Signal()  # Request to toggle AI panel visibility
    audit_programs_requested = Signal()  # Request to open the Audit Programs gallery

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
            project_name = self.current_project.name if self.current_project.name else "No Project Selected"
            self.project_label.setText(project_name)

            client_name = self.current_project.client_name if self.current_project.client_name else "No Client"
            self.client_label.setText(client_name)

            self.edit_project_btn.setVisible(True)
            self.delete_project_btn.setVisible(True)
        else:
            self.project_label.setText("No Project Selected")
            self.client_label.setText("No Client")

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
            item.setIcon(_icon("fa5s.table", color=Colors.TEXT_TERTIARY))

            row_count = dataset.metadata.get('row_count', 0)
            item.setData(Qt.UserRole + 1, row_count)

            self.datasets_list.addItem(item)
            self.dataset_items[dataset.id] = item

        if datasets and not self.current_dataset_id:
            self.datasets_list.setCurrentRow(0)

    def select_dataset(self, dataset_id: str):
        """Highlight a specific dataset in the list — used when reopening a
        project to resume on whichever dataset was active when it was last
        saved, instead of always defaulting to the first one."""
        item = self.dataset_items.get(dataset_id)
        if item:
            self.current_dataset_id = dataset_id
            self.datasets_list.setCurrentItem(item)

    def _on_datasetClicked(self, item):
        """Handle dataset item click (left click only)"""
        if item:
            dataset_id = item.data(Qt.UserRole)
            self.current_dataset_id = dataset_id
            self.dataset_selected.emit(dataset_id)

    def _on_datasetContextMenu(self, pos):
        """Handle right-click context menu for dataset items"""
        from PySide6.QtGui import QAction

        item = self.datasets_list.itemAt(pos)
        if not item:
            return

        dataset_id = item.data(Qt.UserRole)
        dataset_name = item.text()

        menu = QMenu(self)

        info_action = QAction(_icon("fa5s.table", color=Colors.TEXT_TERTIARY), dataset_name, self)
        info_action.setEnabled(False)
        menu.addAction(info_action)
        menu.addSeparator()

        view_action = QAction(_icon("fa5s.eye"), "View Data", self)
        view_action.triggered.connect(lambda: self.dataset_selected.emit(dataset_id))
        menu.addAction(view_action)

        rename_action = QAction(_icon("fa5s.pen"), "Rename", self)
        rename_action.triggered.connect(lambda: self.dataset_rename_requested.emit(dataset_id))
        menu.addAction(rename_action)

        duplicate_action = QAction(_icon("fa5s.clone"), "Duplicate", self)
        duplicate_action.triggered.connect(lambda: self.dataset_duplicate_requested.emit(dataset_id))
        menu.addAction(duplicate_action)

        split_action = QAction(_icon("fa5s.cut"), "Split Sheet", self)
        split_action.triggered.connect(lambda: self.dataset_split_sheet_requested.emit(dataset_id))
        menu.addAction(split_action)

        refresh_action = QAction(_icon("fa5s.sync-alt"), "Refresh from Source", self)
        refresh_action.triggered.connect(lambda: self.dataset_refresh_requested.emit(dataset_id))
        menu.addAction(refresh_action)

        visualize_action = QAction(_icon("fa5s.chart-bar"), "Visualize This Dataset...", self)
        visualize_action.triggered.connect(lambda: self.dataset_visualize_requested.emit(dataset_id))
        menu.addAction(visualize_action)

        menu.addSeparator()

        delete_action = QAction(_icon("fa5s.trash-alt", color=Colors.DANGER), "Delete", self)
        delete_action.triggered.connect(lambda: self.dataset_delete_requested.emit(dataset_id))
        menu.addAction(delete_action)

        # Menu styling comes from the global stylesheet (QMenu rules in gui.theme)
        menu.exec_(self.mapToGlobal(pos))

    def _on_datasetDoubleClicked(self, item):
        """Handle dataset item double click - navigate to transform view"""
        if item:
            dataset_id = item.data(Qt.UserRole)
            self.dataset_selected.emit(dataset_id)
            self.navigation_requested.emit("transform")

    def _setup_ui(self):
        """Setup the sidebar UI"""
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_SECONDARY};
                border-right: 1px solid {Colors.BORDER};
            }}
            QListWidget {{
                background-color: transparent;
                border: none;
                color: {Colors.TEXT_PRIMARY};
            }}
            QListWidget::item {{
                background-color: transparent;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
            }}
            QListWidget::item:selected {{
                background-color: {Colors.ACCENT_SOFT};
                color: {Colors.ACCENT_PRESSED};
            }}
            QListWidget::item:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QToolTip {{
                background-color: {Colors.TEXT_PRIMARY};
                color: {Colors.BG_PRIMARY};
                border: none;
                padding: 4px 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header section with padding
        header_content = QWidget()
        header_content.setStyleSheet(f"background-color: {Colors.BG_SECONDARY};")
        header_layout = QVBoxLayout(header_content)
        header_layout.setContentsMargins(16, 12, 16, 8)

        subtitle_label = QLabel("Queries")
        subtitle_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 12px;
                font-weight: 600;
            }}
        """)
        header_layout.addWidget(subtitle_label)

        layout.addWidget(header_content)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMinimumHeight(200)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        scroll_content = QWidget()
        scroll_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        scroll_content.setStyleSheet(f"background-color: {Colors.BG_SECONDARY};")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(16, 8, 16, 16)
        scroll_layout.setSpacing(8)

        section_label_style = f"""
            QLabel {{
                color: {Colors.TEXT_TERTIARY};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
        """

        # Project section
        project_label = QLabel("PROJECT")
        project_label.setStyleSheet(section_label_style)
        scroll_layout.addWidget(project_label)

        project_row = QHBoxLayout()
        project_row.setContentsMargins(0, 0, 0, 0)
        project_row.setSpacing(8)

        self.project_label = QLabel("No Project Selected")
        self.project_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
                padding: 4px 0px;
            }}
        """)
        project_row.addWidget(self.project_label, 1)

        self.project_actions_widget = QWidget()
        project_actions_layout = QHBoxLayout(self.project_actions_widget)
        project_actions_layout.setContentsMargins(0, 0, 0, 0)
        project_actions_layout.setSpacing(4)

        def _small_icon_button(icon_name, hover_color=Colors.TEXT_PRIMARY):
            btn = QToolButton()
            btn.setFixedSize(22, 22)
            btn.setIcon(_icon(icon_name, color=Colors.TEXT_TERTIARY))
            btn.setIconSize(QSize(12, 12))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QToolButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                }}
                QToolButton:hover {{
                    background-color: {Colors.BG_TERTIARY};
                }}
            """)
            return btn

        self.edit_project_btn = _small_icon_button("fa5s.pen")
        self.edit_project_btn.clicked.connect(self.project_edit_requested.emit)
        self.edit_project_btn.setVisible(False)
        project_actions_layout.addWidget(self.edit_project_btn)

        self.delete_project_btn = _small_icon_button("fa5s.trash-alt")
        self.delete_project_btn.clicked.connect(self.project_delete_requested.emit)
        self.delete_project_btn.setVisible(False)
        project_actions_layout.addWidget(self.delete_project_btn)

        project_row.addWidget(self.project_actions_widget)
        scroll_layout.addLayout(project_row)

        self.client_label = QLabel("No Client")
        self.client_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
                padding-bottom: 8px;
            }}
        """)
        scroll_layout.addWidget(self.client_label)

        # Datasets section
        datasets_header = QHBoxLayout()

        datasets_label = QLabel("DATASETS")
        datasets_label.setStyleSheet(section_label_style.replace("}", "padding-top: 16px; }"))
        datasets_header.addWidget(datasets_label)

        datasets_header.addStretch()

        add_dataset_btn = QToolButton()
        add_dataset_btn.setFixedSize(22, 22)
        add_dataset_btn.setIcon(_icon("fa5s.plus", color=Colors.TEXT_ON_ACCENT))
        add_dataset_btn.setIconSize(QSize(11, 11))
        add_dataset_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {Colors.ACCENT};
                border: none;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                background-color: {Colors.ACCENT_HOVER};
            }}
            QToolTip {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 4px 8px;
            }}
        """)
        add_dataset_btn.setCursor(Qt.PointingHandCursor)
        add_dataset_btn.clicked.connect(self.upload_requested.emit)
        add_dataset_btn.setToolTip("Import a dataset from file")
        datasets_header.addWidget(add_dataset_btn)

        paste_dataset_btn = QToolButton()
        paste_dataset_btn.setFixedSize(22, 22)
        paste_dataset_btn.setIcon(_icon("fa5s.paste", color=Colors.TEXT_TERTIARY))
        paste_dataset_btn.setIconSize(QSize(11, 11))
        paste_dataset_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
            QToolTip {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 4px 8px;
            }}
        """)
        paste_dataset_btn.setCursor(Qt.PointingHandCursor)
        paste_dataset_btn.clicked.connect(self.paste_requested.emit)
        paste_dataset_btn.setToolTip("Paste a dataset from clipboard (Ctrl+Shift+V)")
        datasets_header.addWidget(paste_dataset_btn)

        cleaning_wizard_btn = QToolButton()
        cleaning_wizard_btn.setFixedSize(22, 22)
        cleaning_wizard_btn.setIcon(_icon("fa5s.magic", color=Colors.TEXT_TERTIARY))
        cleaning_wizard_btn.setIconSize(QSize(11, 11))
        cleaning_wizard_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                border: none;
                border-radius: 4px;
            }}
            QToolButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
            QToolTip {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                padding: 4px 8px;
            }}
        """)
        cleaning_wizard_btn.setCursor(Qt.PointingHandCursor)
        cleaning_wizard_btn.clicked.connect(self.cleaning_wizard_requested.emit)
        cleaning_wizard_btn.setToolTip("Import & Clean... (Data Cleaning Wizard for messy files)")
        datasets_header.addWidget(cleaning_wizard_btn)

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
        mode_label.setStyleSheet(section_label_style.replace("}", "padding: 16px 0px 8px 0px; }"))
        scroll_layout.addWidget(mode_label)

        self.data_workspace_btn = SidebarButton("Data", "fa5s.table")
        self.data_workspace_btn.setChecked(False)
        self.data_workspace_btn.update_style(False)
        self.data_workspace_btn.clicked.connect(lambda: self.navigation_requested.emit("data"))
        scroll_layout.addWidget(self.data_workspace_btn)

        self.sql_workspace_btn = SidebarButton("SQL Query", "fa5s.database")
        self.sql_workspace_btn.clicked.connect(lambda: self.navigation_requested.emit("sql"))
        scroll_layout.addWidget(self.sql_workspace_btn)

        # Actions section
        actions_label = QLabel("ACTIONS")
        actions_label.setStyleSheet(section_label_style.replace("}", "padding: 16px 0px 8px 0px; }"))
        scroll_layout.addWidget(actions_label)

        self.export_review_btn = SidebarButton("Export for Review", "fa5s.share-square")
        self.export_review_btn.clicked.connect(lambda: self.navigation_requested.emit("export_review"))
        scroll_layout.addWidget(self.export_review_btn)

        self.join_datasets_btn = SidebarButton("Join Datasets", "fa5s.link")
        self.join_datasets_btn.clicked.connect(self._on_join_datasets_clicked)
        scroll_layout.addWidget(self.join_datasets_btn)

        self.append_datasets_btn = SidebarButton("Append Datasets", "fa5s.layer-group")
        self.append_datasets_btn.clicked.connect(self._on_append_datasets_clicked)
        scroll_layout.addWidget(self.append_datasets_btn)

        self.audit_programs_btn = SidebarButton("Audit Programs", "fa5s.clipboard-list")
        self.audit_programs_btn.clicked.connect(self.audit_programs_requested.emit)
        scroll_layout.addWidget(self.audit_programs_btn)

        scroll_layout.addSpacing(16)

        # Bottom buttons (INSIDE scroll area for full scrollability)
        self.back_btn = SidebarButton("Projects", "fa5s.folder")
        self.back_btn.setCheckable(False)
        self.back_btn.clicked.connect(lambda: self.navigation_requested.emit("projects"))
        scroll_layout.addWidget(self.back_btn)

        self.settings_btn = SidebarButton("Settings", "fa5s.cog")
        self.settings_btn.setCheckable(False)
        self.settings_btn.clicked.connect(lambda: self.navigation_requested.emit("settings"))
        scroll_layout.addWidget(self.settings_btn)

        self.ai_btn = SidebarButton("AI Assistant", "fa5s.robot")
        self.ai_btn.setCheckable(False)
        self.ai_btn.clicked.connect(self.toggle_ai_panel.emit)
        scroll_layout.addWidget(self.ai_btn)

        scroll_layout.addSpacing(16)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def set_active_button(self, button_name):
        """Set the active navigation button"""
        for btn in [self.data_workspace_btn, self.sql_workspace_btn]:
            btn.setChecked(False)
            btn.update_style(False)

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
        item.setIcon(_icon("fa5s.table", color=Colors.TEXT_TERTIARY))
        item.setData(Qt.UserRole + 1, dataset.metadata.get('row_count', 0))

        self.datasets_list.addItem(item)
        self.dataset_items[dataset.id] = item

        self.datasets_list.setCurrentItem(item)
        self.current_dataset_id = dataset.id
        self.dataset_selected.emit(dataset.id)

    def _on_join_datasets_clicked(self):
        """Handle Join Datasets button click"""
        if self.current_dataset_id:
            self.join_datasets_requested.emit(self.current_dataset_id)
        else:
            self.join_datasets_requested.emit(None)

    def _on_append_datasets_clicked(self):
        """Handle Append Datasets button click"""
        if self.current_dataset_id:
            self.append_datasets_requested.emit(self.current_dataset_id)
        else:
            self.append_datasets_requested.emit(None)

    def get_dataset_names(self) -> List[str]:
        """Get list of dataset names in the current project"""
        if not self.current_project:
            return []
        return [ds.name for ds in self.current_project.list_datasets()]
