"""
Backstage View for CaatMaster
==============================
Power BI / Microsoft Office-style backstage view that slides in from the left.
Used for File menu operations like New, Open, Save, Export, etc.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QScrollArea, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QIcon
from pathlib import Path
import json


class BackstageItem(QListWidgetItem):
    """Custom list item for backstage navigation"""

    def __init__(self, text, icon_text="", parent=None):
        # Store original text in UserRole, display text with icon
        display_text = f"{icon_text} {text}" if icon_text else text
        super().__init__(display_text, parent)
        self.icon_text = icon_text
        self.setData(Qt.UserRole, text)  # Store original text for mapping
        self.setSizeHint(QSize(200, 48))


class BackstageView(QFrame):
    """
    Backstage view - slides in from left for file operations.
    Similar to Power BI and Microsoft Office File menu.
    """

    # Signals for menu actions
    new_project = Signal()
    open_project = Signal()
    save_project = Signal()
    export_data = Signal()
    export_review = Signal()
    import_data = Signal()
    settings = Signal()
    help_requested = Signal(str)
    close = Signal()
    dashboard_requested = Signal()  # Request to switch to dashboard view

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BackstageView")
        self.current_project = None
        self._setup_ui()

    def set_project(self, project):
        """Set the current project for display"""
        self.current_project = project
        self._update_project_info()

    def _setup_ui(self):
        """Setup the backstage UI - Power Query style"""
        self.setStyleSheet("""
            QFrame#BackstageView {
                background-color: #ffffff;
                border-right: 1px solid #e5e7eb;
            }
            QWidget#NavContainer {
                background-color: #0f172a;
            }
            QListWidget {
                background-color: transparent;
                border: none;
                padding: 8px 0px;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0px 16px;
                color: #d1d5db;
                font-size: 14px;
                min-height: 44px;
                border-radius: 4px;
                margin: 2px 8px;
            }
            QListWidget::item:hover {
                background-color: #1f2937;
            }
            QListWidget::item:selected {
                background-color: #1e3a8a;
                color: white;
                font-weight: 500;
            }
            QListWidget::item:disabled {
                background-color: transparent;
                height: 1px;
                min-height: 1px;
                max-height: 1px;
                padding: 0px;
                margin: 8px 16px;
                border-top: 1px solid #374151;
            }
            QLabel#SectionTitle {
                color: #6b7280;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QLabel#ProjectName {
                color: #111827;
                font-size: 18px;
                font-weight: 600;
            }
            QLabel#ProjectMeta {
                color: #6b7280;
                font-size: 12px;
            }
        """)

        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left navigation panel
        nav_container = QWidget()
        nav_container.setObjectName("NavContainer")
        nav_container.setFixedWidth(220)
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")
        self.nav_list.setSelectionMode(QListWidget.SingleSelection)

        # Add items
        items = [
            ("Home", "🏠"),
            ("Dashboard", "📊"),
            ("", ""),  # Separator
            ("New", "➕"),
            ("Open", "📂"),
            ("Save", "💾"),
            ("Export", "📤"),
            ("", ""),  # Separator
            ("Settings", "⚙"),
            ("Help", "❓"),
            ("", ""),  # Separator
            ("Close", "✕"),
        ]

        for text, icon in items:
            if text:
                item = BackstageItem(text, icon)
                self.nav_list.addItem(item)
            else:
                # Create separator
                sep = QListWidgetItem()
                sep.setFlags(Qt.NoItemFlags)
                self.nav_list.addItem(sep)

        self.nav_list.itemClicked.connect(self._on_nav_itemClicked)
        self.nav_list.setCurrentRow(0)
        nav_layout.addWidget(self.nav_list)

        layout.addWidget(nav_container)

        # Right content area - Light mode
        right_container = QWidget()
        right_container.setObjectName("RightContainer")
        right_container.setStyleSheet("""
            QWidget#RightContainer {
                background-color: #ffffff;
                border-left: 1px solid #e5e7eb;
            }
        """)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(32, 32, 32, 32)
        right_layout.setSpacing(24)

        # Close button at top right - Light mode
        close_btn = QPushButton("✕")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6b7280;
                border: none;
                font-size: 18px;
                padding: 8px;
            }
            QPushButton:hover {
                color: #111827;
                background-color: #f3f4f6;
            }
        """)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close.emit)
        right_layout.addWidget(close_btn, alignment=Qt.AlignRight)

        # Content stack
        self.content_stack = QScrollArea()
        self.content_stack.setWidgetResizable(True)
        self.content_stack.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea QWidgetContents {
                background-color: transparent;
            }
        """)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(16)

        # Dynamic content based on selection
        self._create_welcome_content()

        self.content_stack.setWidget(self.content_widget)
        right_layout.addWidget(self.content_stack)

        layout.addWidget(right_container, 1)

    def _clear_content(self):
        """Clear the content area"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _create_welcome_content(self):
        """Create welcome/start content - Light mode"""
        self._clear_content()

        title = QLabel("Welcome to CaatMaster")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("""
            QLabel#SectionTitle {
                font-size: 28px;
                color: #111827;
                font-weight: 600;
                text-transform: none;
                letter-spacing: 0;
            }
        """)
        self.content_layout.addWidget(title)

        subtitle = QLabel("Professional Audit Analytics")
        subtitle.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 14px;
            }
        """)
        self.content_layout.addWidget(subtitle)

        self.content_layout.addSpacing(24)

        # Recent projects section
        recent_label = QLabel("Quick Actions")
        recent_label.setObjectName("SectionTitle")
        self.content_layout.addWidget(recent_label)

        # Action buttons - Light mode
        actions = [
            ("📄 New Project", "Create a new audit project", self.new_project.emit),
            ("📂 Open Project", "Open an existing project", self.open_project.emit),
            ("💾 Save Project", "Save current project", self.save_project.emit),
            ("📤 Export Data", "Export data for review", self.export_data.emit),
        ]

        for btn_text, desc, callback in actions:
            btn = QPushButton(btn_text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f3f4f6;
                    color: #111827;
                    border: 1px solid #e5e7eb;
                    border-radius: 6px;
                    padding: 16px 20px;
                    text-align: left;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #dbeafe;
                    border-color: #3b82f6;
                }
            """)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(callback)
            self.content_layout.addWidget(btn)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #6b7280;
                    font-size: 12px;
                    margin-bottom: 16px;
                }
            """)
            self.content_layout.addWidget(desc_label)

        self.content_layout.addStretch()

    def _create_new_content(self):
        """Create New project content - Just emit signal to show proper dialog"""
        self._clear_content()

        title = QLabel("New Project")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                color: #111827;
                font-weight: 600;
                margin-bottom: 8px;
            }
        """)
        self.content_layout.addWidget(title)

        info = QLabel("Create a new audit analytics project with all necessary settings.")
        info.setStyleSheet("color: #6b7280; font-size: 14px; margin-bottom: 24px;")
        self.content_layout.addWidget(info)

        # Feature highlights
        features = [
            ("📋", "Comprehensive project setup with client details, objectives, and scope"),
            ("⚠️", "Risk assessment scoring from 1-10"),
            ("📊", "Multiple engagement types including Financial Audit, Compliance, and more"),
            ("🔄", "Project phase tracking from Planning through Completion"),
        ]

        for icon, text in features:
            feature_layout = QHBoxLayout()
            icon_label = QLabel(icon)
            icon_label.setStyleSheet("font-size: 20px;")
            feature_layout.addWidget(icon_label)

            text_label = QLabel(text)
            text_label.setStyleSheet("color: #374151; font-size: 13px;")
            text_label.setWordWrap(True)
            feature_layout.addWidget(text_label, 1)

            feature_widget = QWidget()
            feature_widget.setLayout(feature_layout)
            self.content_layout.addWidget(feature_widget)

        self.content_layout.addSpacing(24)

        # Create button
        btn = QPushButton("📄 Create New Project")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.new_project.emit)
        self.content_layout.addWidget(btn)

        self.content_layout.addStretch()

    def _create_open_content(self):
        """Create Open project content - Light mode with recent projects"""
        self._clear_content()

        title = QLabel("Open Project")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                color: #111827;
                font-weight: 600;
                margin-bottom: 8px;
            }
        """)
        self.content_layout.addWidget(title)

        info = QLabel("Open an existing project from file or recent locations")
        info.setStyleSheet("color: #6b7280; font-size: 14px; margin-bottom: 24px;")
        self.content_layout.addWidget(info)

        # Browse button
        btn = QPushButton("📂 Browse for Project")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 500;
                margin-bottom: 24px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.open_project.emit)
        self.content_layout.addWidget(btn)

        # Recent projects section
        recent_label = QLabel("Recent Projects")
        recent_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #111827;
                font-weight: 600;
                margin-bottom: 12px;
            }
        """)
        self.content_layout.addWidget(recent_label)

        # Get recent projects from storage
        recent_projects = self._get_recent_projects()

        if recent_projects:
            for project_path, project_name in recent_projects:
                project_btn = QPushButton(f"📁 {project_name}")
                project_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f9fafb;
                        color: #111827;
                        border: 1px solid #e5e7eb;
                        border-radius: 6px;
                        padding: 12px 16px;
                        text-align: left;
                        font-size: 13px;
                        margin-bottom: 8px;
                    }
                    QPushButton:hover {
                        background-color: #dbeafe;
                        border-color: #3b82f6;
                    }
                """)
                project_btn.setCursor(Qt.PointingHandCursor)
                project_btn.clicked.connect(lambda checked, path=project_path: self._open_project_by_path(path))
                self.content_layout.addWidget(project_btn)

                path_label = QLabel(project_path)
                path_label.setStyleSheet("""
                    QLabel {
                        color: #9ca3af;
                        font-size: 11px;
                        margin-bottom: 12px;
                    }
                """)
                self.content_layout.addWidget(path_label)
        else:
            no_recent = QLabel("No recent projects found")
            no_recent.setStyleSheet("color: #9ca3af; font-size: 13px; font-style: italic; margin-bottom: 24px;")
            self.content_layout.addWidget(no_recent)

        self.content_layout.addStretch()

    def _create_save_content(self):
        """Create Save project content - Light mode"""
        self._clear_content()

        title = QLabel("Save Project")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("""
            QLabel#SectionTitle {
                font-size: 24px;
                color: #111827;
                font-weight: 600;
                text-transform: none;
                letter-spacing: 0;
            }
        """)
        self.content_layout.addWidget(title)

        # Project info section - Light mode
        if self.current_project:
            info_frame = QFrame()
            info_frame.setStyleSheet("""
                QFrame {
                    background-color: #f3f4f6;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    padding: 16px;
                    margin: 16px 0px;
                }
            """)
            info_layout = QVBoxLayout(info_frame)

            name_label = QLabel(f"Project: {self.current_project.name}")
            name_label.setObjectName("ProjectName")
            info_layout.addWidget(name_label)

            client_label = QLabel(f"Client: {self.current_project.client_name or 'N/A'}")
            client_label.setObjectName("ProjectMeta")
            info_layout.addWidget(client_label)

            self.content_layout.addWidget(info_frame)

        btn = QPushButton("💾 Save Project")
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.save_project.emit)
        self.content_layout.addWidget(btn)

    def _create_export_content(self):
        """Create Export content - Light mode"""
        self._clear_content()

        title = QLabel("Export Data")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("""
            QLabel#SectionTitle {
                font-size: 24px;
                color: #111827;
                font-weight: 600;
                text-transform: none;
                letter-spacing: 0;
            }
        """)
        self.content_layout.addWidget(title)

        info = QLabel("Export your data and analysis results")
        info.setStyleSheet("color: #6b7280; font-size: 14px; margin-bottom: 24px;")
        self.content_layout.addWidget(info)

        export_options = [
            ("📊 Export for Review", "Export complete package for senior auditor review"),
            ("📄 Export to Excel", "Export data to Excel with formatting"),
            ("📋 Export to CSV", "Export data to CSV format"),
            ("📈 Export Visualizations", "Export charts and graphs"),
        ]

        for btn_text, desc in export_options:
            btn = QPushButton(btn_text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f3f4f6;
                    color: #111827;
                    border: 1px solid #e5e7eb;
                    border-radius: 6px;
                    padding: 14px 20px;
                    text-align: left;
                    font-size: 14px;
                    margin-bottom: 8px;
                }
                QPushButton:hover {
                    background-color: #dbeafe;
                    border-color: #3b82f6;
                }
            """)
            btn.setCursor(Qt.PointingHandCursor)
            if "Review" in btn_text:
                btn.clicked.connect(self.export_review.emit)
            else:
                btn.clicked.connect(self.export_data.emit)
            self.content_layout.addWidget(btn)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #6b7280;
                    font-size: 12px;
                    margin-bottom: 16px;
                }
            """)
            self.content_layout.addWidget(desc_label)

    def _create_settings_content(self):
        """Create Settings content - Light mode"""
        self._clear_content()

        title = QLabel("Settings")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("""
            QLabel#SectionTitle {
                font-size: 24px;
                color: #111827;
                font-weight: 600;
                text-transform: none;
                letter-spacing: 0;
            }
        """)
        self.content_layout.addWidget(title)

        settings_options = [
            ("🔔 Notifications", "Configure notification preferences"),
            ("🎨 Appearance", "Customize theme and colors"),
            ("📁 Default Locations", "Set default directories"),
            ("📊 Data Settings", "Configure data processing options"),
            ("⌨️ Keyboard Shortcuts", "Configure keyboard shortcuts"),
            ("🔌 Connection Settings", "Manage database and API connections"),
            ("🔒 Security", "Manage security settings"),
        ]

        for btn_text, desc in settings_options:
            btn = QPushButton(btn_text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f3f4f6;
                    color: #111827;
                    border: 1px solid #e5e7eb;
                    border-radius: 6px;
                    padding: 14px 20px;
                    text-align: left;
                    font-size: 14px;
                    margin-bottom: 8px;
                }
                QPushButton:hover {
                    background-color: #dbeafe;
                    border-color: #3b82f6;
                }
            """)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(self.settings.emit)
            self.content_layout.addWidget(btn)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #6b7280;
                    font-size: 12px;
                    margin-bottom: 16px;
                }
            """)
            self.content_layout.addWidget(desc_label)

    def _create_help_content(self):
        """Create Help content - Light mode"""
        self._clear_content()

        title = QLabel("Help")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("""
            QLabel#SectionTitle {
                font-size: 24px;
                color: #111827;
                font-weight: 600;
                text-transform: none;
                letter-spacing: 0;
            }
        """)
        self.content_layout.addWidget(title)

        info = QLabel("Get assistance and learn how to use CaatMaster")
        info.setStyleSheet("color: #6b7280; font-size: 14px; margin-bottom: 24px;")
        self.content_layout.addWidget(info)

        help_options = [
            ("📖 User Guide", "Browse the complete user guide and documentation"),
            ("🎓 Tutorials", "Step-by-step tutorials for common tasks"),
            ("⌨️ Keyboard Shortcuts", "View all keyboard shortcuts for faster work"),
            ("🔄 Check for Updates", "Check for new versions of CaatMaster"),
            ("ℹ️ About", "Version information and credits"),
        ]

        for btn_text, desc in help_options:
            btn = QPushButton(btn_text)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f3f4f6;
                    color: #111827;
                    border: 1px solid #e5e7eb;
                    border-radius: 6px;
                    padding: 14px 20px;
                    text-align: left;
                    font-size: 14px;
                    margin-bottom: 8px;
                }
                QPushButton:hover {
                    background-color: #dbeafe;
                    border-color: #3b82f6;
                }
            """)
            btn.setCursor(Qt.PointingHandCursor)
            # Connect to help requested signal
            btn.clicked.connect(lambda checked, text=btn_text: self.help_requested.emit(text))
            self.content_layout.addWidget(btn)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("""
                QLabel {
                    color: #6b7280;
                    font-size: 12px;
                    margin-bottom: 16px;
                }
            """)
            self.content_layout.addWidget(desc_label)

    def _on_dashboard_clicked(self):
        """Handle dashboard navigation - switch to dashboard view"""
        self.dashboard_requested.emit()
        self.close.emit()  # Close backstage view

    def _on_nav_itemClicked(self, item):
        """Handle navigation item click"""
        # Get original text from UserRole (stored by BackstageItem)
        text = item.data(Qt.UserRole)
        if not text:
            # Fallback to displayed text (for separator items or legacy)
            text = item.text()

        content_map = {
            "Home": self._create_welcome_content,
            "Dashboard": self._on_dashboard_clicked,
            "New": self._create_new_content,
            "Open": self._create_open_content,
            "Save": self._create_save_content,
            "Export": self._create_export_content,
            "Settings": self._create_settings_content,
            "Help": self._create_help_content,
            "Close": self.close.emit,
        }

        if text in content_map:
            if callable(content_map[text]):
                content_map[text]()
            else:
                content_map[text]()

    def _update_project_info(self):
        """Update project information display"""
        if self.current_project:
            # Refresh content if save page is active
            current_row = self.nav_list.currentRow()
            if current_row >= 0:
                item = self.nav_list.item(current_row)
                if item and (item.data(Qt.UserRole) == "Save" or item.text() == "Save"):
                    self._create_save_content()

    def _get_recent_projects(self):
        """Get list of recent projects from storage"""
        recent_projects = []

        # Check for recent projects file
        recent_file = Path.home() / '.caatmaster' / 'recent_projects.json'

        if recent_file.exists():
            try:
                with open(recent_file, 'r') as f:
                    data = json.load(f)
                    for item in data.get('recent', [])[:5]:  # Get last 5 projects
                        project_path = item.get('path', '')
                        project_name = item.get('name', 'Unknown')
                        if Path(project_path).exists():
                            recent_projects.append((project_path, project_name))
            except Exception as e:
                print(f"Error loading recent projects: {e}")

        return recent_projects

    def _open_project_by_path(self, project_path):
        """Open a project by its file path"""
        path = Path(project_path)
        if path.exists():
            # Store the path temporarily so main window can access it
            self._pending_project_path = str(path)

            # Emit the signal - main window will handle actual project opening
            self.open_project.emit()
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Project Not Found", f"The project file was not found:\n{project_path}")
