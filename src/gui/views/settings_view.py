"""Settings View - Application settings with user management"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QFormLayout, QSpinBox, QDoubleSpinBox, QLineEdit,
    QCheckBox, QComboBox, QPushButton, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction


class SettingsView(QWidget):
    """Application settings view with user management"""

    logout_requested = Signal()  # Signal when user requests logout

    def __init__(self, parent=None):
        super().__init__(parent)
        self.auth_service = None
        self.main_window = parent  # Store reference to main window
        self.setup_ui()

    def set_auth_service(self, auth_service):
        """Set the authentication service"""
        self.auth_service = auth_service

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header with user info
        header_layout = QHBoxLayout()

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Logout button
        self.logout_btn = QPushButton("Logout")
        self.logout_btn.setStyleSheet("""
            QPushButton {
                background: #dc3545;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #c82333;
            }
        """)
        self.logout_btn.clicked.connect(self.logout)
        self.logout_btn.setEnabled(False)
        header_layout.addWidget(self.logout_btn)

        layout.addLayout(header_layout)

        # User info label
        self.user_info_label = QLabel("Not logged in")
        self.user_info_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.user_info_label)

        # Create tab widget for different settings categories
        self.tab_widget = QTabWidget()

        # User account tab
        self.user_tab = self.create_user_tab()
        self.tab_widget.addTab(self.user_tab, "User Account")

        # General settings
        general_tab = self.create_general_tab()
        self.tab_widget.addTab(general_tab, "General")

        # Data settings
        data_tab = self.create_data_tab()
        self.tab_widget.addTab(data_tab, "Data")

        # AI/ML settings
        ai_tab = self.create_ai_tab()
        self.tab_widget.addTab(ai_tab, "AI/ML")

        # Advanced settings
        advanced_tab = self.create_advanced_tab()
        self.tab_widget.addTab(advanced_tab, "Advanced")

        layout.addWidget(self.tab_widget)

    def update_user_info(self, user):
        """Update user information display"""
        if user:
            role = "Administrator" if user.is_superuser else "User"
            self.user_info_label.setText(
                f"Logged in as: <b>{user.full_name}</b> ({user.username}) - {role}"
            )
            self.logout_btn.setEnabled(True)
        else:
            self.user_info_label.setText("Not logged in")
            self.logout_btn.setEnabled(False)

    def logout(self):
        """Handle logout request"""
        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to logout?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.logout_requested.emit()

    def create_user_tab(self) -> QWidget:
        """Create user account management tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Current user info
        info_group = QGroupBox("Your Profile")
        info_layout = QFormLayout()

        self.username_label = QLabel("-")
        info_layout.addRow("Username:", self.username_label)

        self.email_label = QLabel("-")
        info_layout.addRow("Email:", self.email_label)

        self.fullname_label = QLabel("-")
        info_layout.addRow("Full Name:", self.fullname_label)

        self.role_label = QLabel("-")
        info_layout.addRow("Role:", self.role_label)

        self.created_label = QLabel("-")
        info_layout.addRow("Member Since:", self.created_label)

        self.last_login_label = QLabel("-")
        info_layout.addRow("Last Login:", self.last_login_label)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Actions
        actions_group = QGroupBox("Account Actions")
        actions_layout = QHBoxLayout()

        self.change_password_btn = QPushButton("Change Password")
        self.change_password_btn.clicked.connect(self.change_password)
        actions_layout.addWidget(self.change_password_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_user_info)
        actions_layout.addWidget(self.refresh_btn)

        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        # User management (for admins)
        self.users_group = QGroupBox("User Management")
        users_layout = QVBoxLayout()

        # Users table
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(5)
        self.users_table.setHorizontalHeaderLabels(["Username", "Email", "Full Name", "Role", "Actions"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        users_layout.addWidget(self.users_table)

        # User management buttons
        users_buttons = QHBoxLayout()

        self.add_user_btn = QPushButton("Add User")
        self.add_user_btn.clicked.connect(self.add_user)
        users_buttons.addWidget(self.add_user_btn)

        self.delete_user_btn = QPushButton("Delete User")
        self.delete_user_btn.clicked.connect(self.delete_user)
        users_buttons.addWidget(self.delete_user_btn)

        users_buttons.addStretch()

        users_layout.addLayout(users_buttons)
        self.users_group.setLayout(users_layout)
        layout.addWidget(self.users_group)

        # Hide user management by default (only for admins)
        self.users_group.setVisible(False)

        layout.addStretch()

        return widget

    def create_general_tab(self) -> QWidget:
        """Create general settings tab"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Theme
        theme_combo = QComboBox()
        theme_combo.addItems(["System Default", "Light", "Dark"])
        layout.addRow("Theme:", theme_combo)

        # Auto-save
        autosave_checkbox = QCheckBox("Enable auto-save")
        autosave_checkbox.setChecked(True)
        layout.addRow("Auto-save:", autosave_checkbox)

        # Auto-save interval
        autosave_interval = QSpinBox()
        autosave_interval.setRange(1, 60)
        autosave_interval.setValue(5)
        autosave_interval.setSuffix(" minutes")
        layout.addRow("Auto-save interval:", autosave_interval)

        # Max rows in preview
        max_rows = QSpinBox()
        max_rows.setRange(100, 100000)
        max_rows.setValue(1000)
        layout.addRow("Max preview rows:", max_rows)

        return widget

    def create_data_tab(self) -> QWidget:
        """Create data settings tab"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Default import format
        format_combo = QComboBox()
        format_combo.addItems(["Auto-detect", "CSV", "Excel", "Parquet", "JSON"])
        layout.addRow("Default import format:", format_combo)

        # CSV delimiter
        delimiter_input = QLineEdit(",")
        layout.addRow("CSV delimiter:", delimiter_input)

        # Date format
        date_format = QLineEdit("%Y-%m-%d")
        layout.addRow("Date format:", date_format)

        # Cache data
        cache_checkbox = QCheckBox("Cache imported data")
        cache_checkbox.setChecked(True)
        layout.addRow("Data caching:", cache_checkbox)

        return widget

    def create_ai_tab(self) -> QWidget:
        """Create AI/ML settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # AI Provider configuration button
        config_group = QGroupBox("Configure AI Providers")
        config_layout = QVBoxLayout()

        config_desc = QLabel(
            "Configure AI providers for dataset analysis, column generation, "
            "and compliance checking. Supports OpenAI, Anthropic, DeepSeek, "
            "Hugging Face, Ollama, LlamaCPP, and custom providers."
        )
        config_desc.setWordWrap(True)
        config_desc.setStyleSheet("color: #666; font-size: 12px;")
        config_layout.addWidget(config_desc)

        config_btn = QPushButton("Edit AI Settings")
        config_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        config_btn.clicked.connect(self.open_ai_settings)
        config_layout.addWidget(config_btn)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Current provider info
        info_group = QGroupBox("Current Configuration")
        info_layout = QFormLayout()

        self.ai_provider_label = QLabel("Not configured")
        info_layout.addRow("Active Provider:", self.ai_provider_label)

        self.ai_model_label = QLabel("-")
        info_layout.addRow("Model:", self.ai_model_label)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # ML settings
        ml_group = QGroupBox("Machine Learning")
        ml_layout = QFormLayout()

        max_features = QSpinBox()
        max_features.setRange(10, 10000)
        max_features.setValue(1000)
        ml_layout.addRow("Max features:", max_features)

        test_size = QDoubleSpinBox()
        test_size.setRange(0.1, 0.9)
        test_size.setSingleStep(0.1)
        test_size.setValue(0.2)
        ml_layout.addRow("Test size:", test_size)

        ml_group.setLayout(ml_layout)
        layout.addWidget(ml_group)

        layout.addStretch()

        return widget

    def open_ai_settings(self):
        """Open AI settings dialog"""
        from ..dialogs.ai_settings_dialog import AISettingsDialog

        if self.main_window and hasattr(self.main_window, 'ai_manager'):
            dialog = AISettingsDialog(self.main_window.ai_manager, self)
            dialog.exec()
            # Update info after settings change
            self.update_ai_info()
        else:
            QMessageBox.warning(
                self,
                "Error",
                "Unable to open AI settings. Please restart the application."
            )

    def update_ai_info(self):
        """Update AI configuration info display"""
        if self.main_window and hasattr(self.main_window, 'ai_manager'):
            ai_manager = self.main_window.ai_manager
            if ai_manager and ai_manager.providers:
                # Show the default provider
                default = ai_manager.default_provider
                provider = ai_manager.get_provider(default)
                if provider:
                    from ..dialogs.ai_settings_dialog import AIProviderFactory
                    display_name = AIProviderFactory.get_display_name(default)
                    self.ai_provider_label.setText(display_name)
                    self.ai_model_label.setText(provider.model or "-")
                else:
                    self.ai_provider_label.setText("Not configured")
                    self.ai_model_label.setText("-")
            else:
                self.ai_provider_label.setText("Not configured")
                self.ai_model_label.setText("-")

    def refresh_ai_info(self):
        """Refresh AI info - called when dialog closes"""
        self.update_ai_info()

    def create_advanced_tab(self) -> QWidget:
        """Create advanced settings tab"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Memory limit
        memory_limit = QSpinBox()
        memory_limit.setRange(512, 16384)
        memory_limit.setValue(4096)
        memory_limit.setSuffix(" MB")
        layout.addRow("Memory limit:", memory_limit)

        # Thread count
        thread_count = QSpinBox()
        thread_count.setRange(1, 16)
        thread_count.setValue(4)
        layout.addRow("Worker threads:", thread_count)

        # Debug mode
        debug_checkbox = QCheckBox("Enable debug logging")
        layout.addRow("Debug mode:", debug_checkbox)

        # Reset database button
        reset_btn = QPushButton("Reset Database")
        reset_btn.setStyleSheet("color: red;")
        reset_btn.clicked.connect(self.reset_database)
        layout.addRow("", reset_btn)

        layout.addRow(QLabel("<i>Resetting will delete all data!</i>"))

        return widget

    def refresh_user_info(self):
        """Refresh user information display"""
        if not self.auth_service:
            return

        user = self.auth_service.get_current_user()
        if user:
            # Reload from database
            user = self.auth_service.get_user_by_id(user.id)

            self.username_label.setText(user.username)
            self.email_label.setText(user.email)
            self.fullname_label.setText(user.full_name)
            self.role_label.setText("Administrator" if user.is_superuser else "User")
            self.created_label.setText(user.created_at.strftime("%Y-%m-%d") if user.created_at else "-")
            self.last_login_label.setText(user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "-")

            # Show user management for admins
            self.users_group.setVisible(user.is_superuser)
            self.load_users_table()
        else:
            self.username_label.setText("-")
            self.email_label.setText("-")
            self.fullname_label.setText("-")
            self.role_label.setText("-")
            self.created_label.setText("-")
            self.last_login_label.setText("-")
            self.users_group.setVisible(False)

        self.update_user_info(user)

    def load_users_table(self):
        """Load users into the table"""
        if not self.auth_service:
            return

        users = self.auth_service.list_users()
        current_user = self.auth_service.get_current_user()

        self.users_table.setRowCount(len(users))

        for row, user in enumerate(users):
            # Username
            self.users_table.setItem(row, 0, QTableWidgetItem(user.username))

            # Email
            self.users_table.setItem(row, 1, QTableWidgetItem(user.email))

            # Full Name
            self.users_table.setItem(row, 2, QTableWidgetItem(user.full_name))

            # Role
            role = "Administrator" if user.is_superuser else "User"
            self.users_table.setItem(row, 3, QTableWidgetItem(role))

            # Actions (only show delete button for other users)
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 0, 5, 0)

            if current_user and user.id != current_user.id:
                delete_btn = QPushButton("Delete")
                delete_btn.setStyleSheet("color: red; padding: 2px 8px;")
                delete_btn.clicked.connect(lambda checked, uid=user.id: self.delete_user_by_id(uid))
                actions_layout.addWidget(delete_btn)

            actions_layout.addStretch()
            self.users_table.setCellWidget(row, 4, actions_widget)

    def change_password(self):
        """Open change password dialog"""
        if not self.auth_service or not self.auth_service.get_current_user():
            QMessageBox.warning(self, "Not Logged In", "Please log in first")
            return

        from ..dialogs.login_dialog import ChangePasswordDialog

        user = self.auth_service.get_current_user()
        dialog = ChangePasswordDialog(self.auth_service, user.id, self)
        dialog.exec()

    def add_user(self):
        """Add a new user (admin only)"""
        from ..dialogs.login_dialog import RegisterDialog

        if not self.auth_service:
            return

        dialog = RegisterDialog(self.auth_service, self)
        if dialog.exec():
            QMessageBox.information(self, "Success", "User created successfully!")
            self.load_users_table()

    def delete_user(self):
        """Delete selected user"""
        # Find selected row
        current_row = self.users_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a user to delete")
            return

        username_item = self.users_table.item(current_row, 0)
        username = username_item.text()

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete user '{username}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Need to get user ID - this is a simplified version
            QMessageBox.information(self, "Info", "Use the delete button in the Actions column")

    def delete_user_by_id(self, user_id: int):
        """Delete a user by ID"""
        if not self.auth_service:
            return

        try:
            self.auth_service.delete_user(user_id)
            QMessageBox.information(self, "Success", "User deleted successfully!")
            self.load_users_table()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete user:\n{str(e)}")

    def reset_database(self):
        """Reset the database (WARNING: Deletes all data)"""
        reply = QMessageBox.warning(
            self,
            "DANGER: Database Reset",
            "This will DELETE ALL DATA including:\n"
            "- All users except admin\n"
            "- All projects and sessions\n"
            "- All imported datasets\n"
            "- All transformation history\n\n"
            "This action CANNOT be undone!\n\n"
            "Are you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Double-check
            reply2 = QMessageBox.warning(
                self,
                "Final Confirmation",
                "Last chance! This will permanently delete all data.\n\nProceed?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply2 == QMessageBox.Yes:
                try:
                    from core.database import reset_database

                    reset_database()
                    QMessageBox.information(
                        self,
                        "Database Reset",
                        "Database has been reset.\n\nPlease restart the application."
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to reset database:\n{str(e)}"
                    )
