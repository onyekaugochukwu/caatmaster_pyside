"""
Login and Registration Dialogs for CAATmaster
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QCheckBox, QMessageBox,
    QTabWidget, QWidget, QGroupBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
import traceback


class LoginDialog(QDialog):
    """Dialog for user login"""

    login_success = Signal(object)  # Signal emitted when login successful

    def __init__(self, auth_service, parent=None):
        super().__init__(parent if parent else None)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.auth_service = auth_service
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("CAATmaster - Login")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Logo/title
        title = QLabel("Welcome to CAATmaster")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d4; padding: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Professional Continuous Audit Analytics Tool")
        subtitle.setStyleSheet("font-size: 14px; color: #666; padding-bottom: 20px;")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        # Login form
        form_group = QGroupBox("Sign In")
        form_layout = QFormLayout()

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username or email")
        form_layout.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Password")
        form_layout.addRow("Password:", self.password_input)

        self.remember_cb = QCheckBox("Remember me")
        form_layout.addRow("", self.remember_cb)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.login_btn = QPushButton("Login")
        self.login_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #106ebe;
            }
        """)
        self.login_btn.clicked.connect(self.attempt_login)
        button_layout.addWidget(self.login_btn)

        self.register_btn = QPushButton("Register")
        self.register_btn.clicked.connect(self.show_register)
        button_layout.addWidget(self.register_btn)

        layout.addLayout(button_layout)

        # Info
        info_label = QLabel(
            "Default admin account:\n  Username: admin\n  Password: admin123"
        )
        info_label.setStyleSheet("color: #999; font-size: 11px; padding: 10px; background: #f5f5f5; border-radius: 4px;")
        layout.addWidget(info_label)

        layout.addStretch()

    def attempt_login(self):
        """Attempt to login with provided credentials"""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Validation Error", "Please enter username and password")
            return

        try:
            # Attempt login
            token = self.auth_service.login(username, password)

            if token:
                # Save session if remember me checked
                if self.remember_cb.isChecked():
                    self.auth_service.save_session()

                # Emit success signal
                self.login_success.emit(self.auth_service.get_current_user())

                # Close dialog
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "Login Failed",
                    "Invalid username or password"
                )

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Login Error",
                f"An error occurred during login:\n{str(e)}"
            )

    def show_register(self):
        """Show registration dialog"""
        dialog = RegisterDialog(self.auth_service, self)
        if dialog.exec():
            # Registration successful, attempt login
            username = dialog.get_username()
            password = dialog.get_password()

            self.username_input.setText(username)
            self.password_input.setText(password)
            self.attempt_login()


class RegisterDialog(QDialog):
    """Dialog for user registration"""

    def __init__(self, auth_service, parent=None):
        super().__init__(parent if parent else None)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.auth_service = auth_service
        self._username = ""
        self._password = ""
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Register New Account")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Create New Account")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #0078d4; padding: 10px;")
        layout.addWidget(title)

        # Registration form
        form_group = QGroupBox("Account Information")
        form_layout = QFormLayout()

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Choose a unique username")
        form_layout.addRow("Username*:", self.username_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@example.com")
        form_layout.addRow("Email*:", self.email_input)

        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText("John Doe")
        form_layout.addRow("Full Name:", self.fullname_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Minimum 6 characters")
        form_layout.addRow("Password*:", self.password_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.setPlaceholderText("Re-enter password")
        form_layout.addRow("Confirm Password*:", self.confirm_input)

        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        # Password strength indicator
        self.strength_label = QLabel("Password Strength: -")
        self.strength_label.setStyleSheet("padding: 5px;")
        layout.addWidget(self.strength_label)

        self.password_input.textChanged.connect(self.update_strength_indicator)

        # Buttons
        button_layout = QHBoxLayout()

        self.register_btn = QPushButton("Register")
        self.register_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #218838;
            }
        """)
        self.register_btn.clicked.connect(self.attempt_register)
        button_layout.addWidget(self.register_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch()

    def update_strength_indicator(self, password: str):
        """Update password strength indicator"""
        if not password:
            self.strength_label.setText("Password Strength: -")
            self.strength_label.setStyleSheet("padding: 5px;")
            return

        strength = 0
        if len(password) >= 6:
            strength += 1
        if len(password) >= 10:
            strength += 1
        if any(c.isupper() for c in password):
            strength += 1
        if any(c.islower() for c in password):
            strength += 1
        if any(c.isdigit() for c in password):
            strength += 1

        levels = ["Very Weak", "Weak", "Fair", "Good", "Strong"]
        colors = ["#dc3545", "#dc3545", "#ffc107", "#28a745", "#28a745"]

        level = levels[min(strength, 4)]
        color = colors[min(strength, 4)]

        self.strength_label.setText(f"Password Strength: {level}")
        self.strength_label.setStyleSheet(f"padding: 5px; color: {color}; font-weight: bold;")

    def attempt_register(self):
        """Attempt to register a new user"""
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()
        fullname = self.fullname_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        # Validation
        if not username:
            QMessageBox.warning(self, "Validation Error", "Please enter a username")
            return

        if len(username) < 3:
            QMessageBox.warning(self, "Validation Error", "Username must be at least 3 characters")
            return

        if not email:
            QMessageBox.warning(self, "Validation Error", "Please enter an email address")
            return

        if "@" not in email:
            QMessageBox.warning(self, "Validation Error", "Please enter a valid email address")
            return

        if not password:
            QMessageBox.warning(self, "Validation Error", "Please enter a password")
            return

        if len(password) < 6:
            QMessageBox.warning(self, "Validation Error", "Password must be at least 6 characters")
            return

        if password != confirm:
            QMessageBox.warning(self, "Validation Error", "Passwords do not match")
            return

        try:
            # Attempt registration
            user = self.auth_service.register_user(
                username=username,
                email=email,
                password=password,
                full_name=fullname or username
            )

            # Store credentials for auto-login
            self._username = username
            self._password = password

            QMessageBox.information(
                self,
                "Registration Successful",
                f"Account created successfully!\n\nWelcome, {user.full_name}!"
            )

            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Registration Error", str(e))

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Registration Error",
                f"An error occurred during registration:\n{str(e)}"
            )

    def get_username(self) -> str:
        return self._username

    def get_password(self) -> str:
        return self._password


class ChangePasswordDialog(QDialog):
    """Dialog for changing password"""

    def __init__(self, auth_service, user_id: int, parent=None):
        super().__init__(parent if parent else None)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.auth_service = auth_service
        self.user_id = user_id
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Change Password")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Change Your Password")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        # Form
        form_layout = QFormLayout()

        self.current_input = QLineEdit()
        self.current_input.setEchoMode(QLineEdit.Password)
        self.current_input.setPlaceholderText("Enter current password")
        form_layout.addRow("Current Password*:", self.current_input)

        self.new_input = QLineEdit()
        self.new_input.setEchoMode(QLineEdit.Password)
        self.new_input.setPlaceholderText("Enter new password (min 6 characters)")
        form_layout.addRow("New Password*:", self.new_input)

        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        self.confirm_input.setPlaceholderText("Confirm new password")
        form_layout.addRow("Confirm Password*:", self.confirm_input)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()

        self.change_btn = QPushButton("Change Password")
        self.change_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #106ebe;
            }
        """)
        self.change_btn.clicked.connect(self.attempt_change)
        button_layout.addWidget(self.change_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        layout.addStretch()

    def attempt_change(self):
        """Attempt to change password"""
        current = self.current_input.text()
        new = self.new_input.text()
        confirm = self.confirm_input.text()

        if not current or not new or not confirm:
            QMessageBox.warning(self, "Validation Error", "All fields are required")
            return

        if new != confirm:
            QMessageBox.warning(self, "Validation Error", "New passwords do not match")
            return

        if len(new) < 6:
            QMessageBox.warning(self, "Validation Error", "Password must be at least 6 characters")
            return

        try:
            self.auth_service.change_password(self.user_id, current, new)

            QMessageBox.information(
                self,
                "Success",
                "Password changed successfully!"
            )

            self.accept()

        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to change password:\n{str(e)}")
