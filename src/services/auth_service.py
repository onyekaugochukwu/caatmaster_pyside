"""
Authentication Service for CAATmaster
Handles user authentication, registration, and session management
"""
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from pathlib import Path

from core.database import get_db_context
from core.models import User


# Password hashing context - using argon2 for better compatibility
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

# JWT settings
SECRET_KEY = "caatmaster-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


class AuthService:
    """Service for user authentication and management"""

    def __init__(self):
        """Initialize the authentication service"""
        self.current_user_id: Optional[int] = None
        self.session_token: Optional[str] = None

    def __getattr__(self, name):
        """Trap attribute access to detect missing attributes."""
        import sys
        print(f"[DEBUG] AuthService.__getattr__ called for '{name}'", file=sys.stderr)
        raise AttributeError(f"'AuthService' object has no attribute '{name}'")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def decode_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode and verify a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.PyJWTError:
            return None

    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str = None
    ) -> User:
        """
        Register a new user

        Args:
            username: Unique username
            email: User email address
            password: Plain text password (will be hashed)
            full_name: Optional full name

        Returns:
            Created User object

        Raises:
            ValueError: If username or email already exists
        """
        with get_db_context() as db:
            # Check if username exists
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                raise ValueError(f"Username '{username}' already exists")

            # Check if email exists
            existing_email = db.query(User).filter(User.email == email).first()
            if existing_email:
                raise ValueError(f"Email '{email}' already exists")

            # Create new user
            hashed_password = self.get_password_hash(password)
            user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                full_name=full_name or username,
                is_active=True
            )

            db.add(user)
            db.commit()

            # Re-query to get a clean instance that won't cause issues outside session
            user_id = user.id

        # Return a fresh User object by querying in a new session
        return self.get_user_by_id(user_id)

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user with username and password

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise
        """
        with get_db_context() as db:
            # Try to find user by username or email
            user = db.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()

            if not user:
                return None

            if not user.is_active:
                return None

            # Verify password
            if not self.verify_password(password, user.hashed_password):
                return None

            return user

    def login(self, username: str, password: str) -> Optional[str]:
        """
        Login a user and return session token

        Args:
            username: Username or email
            password: Plain text password

        Returns:
            Session token if successful, None otherwise
        """
        user = self.authenticate_user(username, password)
        if not user:
            return None

        # Update last login
        with get_db_context() as db:
            db_user = db.query(User).filter(User.id == user.id).first()
            if db_user:
                db_user.last_login = datetime.utcnow()
                db.commit()

        # Create session token
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email
        }
        token = self.create_access_token(token_data)

        # Set current user
        self.current_user_id = user.id
        self.session_token = token

        return token

    def logout(self):
        """Logout the current user"""
        self.current_user_id = None
        self.session_token = None

    def get_current_user(self) -> Optional[User]:
        """Get the currently logged-in user"""
        if self.current_user_id is None:
            return None
        return self.get_user_by_id(self.current_user_id)

    def is_authenticated(self) -> bool:
        """Check if a user is currently authenticated"""
        return self.current_user_id is not None

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get a user by ID"""
        with get_db_context() as db:
            return db.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get a user by username"""
        with get_db_context() as db:
            return db.query(User).filter(User.username == username).first()

    def update_user(
        self,
        user_id: int,
        email: str = None,
        full_name: str = None,
        current_password: str = None,
        new_password: str = None
    ) -> User:
        """
        Update user information

        Args:
            user_id: User ID
            email: New email (optional)
            full_name: New full name (optional)
            current_password: Current password (required for password change)
            new_password: New password (optional)

        Returns:
            Updated User object

        Raises:
            ValueError: If validation fails
        """
        with get_db_context() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            # Update email
            if email:
                # Check if email is taken by another user
                existing = db.query(User).filter(
                    User.email == email,
                    User.id != user_id
                ).first()
                if existing:
                    raise ValueError("Email already exists")
                user.email = email

            # Update full name
            if full_name:
                user.full_name = full_name

            # Update password
            if new_password:
                if not current_password:
                    raise ValueError("Current password required")
                if not self.verify_password(current_password, user.hashed_password):
                    raise ValueError("Current password is incorrect")
                user.hashed_password = self.get_password_hash(new_password)

            user.updated_at = datetime.utcnow()
            db.commit()

        # Return a fresh User object by querying in a new session
        return self.get_user_by_id(user_id)

    def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """
        Change user password

        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password

        Returns:
            True if successful

        Raises:
            ValueError: If current password is incorrect
        """
        with get_db_context() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            if not self.verify_password(current_password, user.hashed_password):
                raise ValueError("Current password is incorrect")

            user.hashed_password = self.get_password_hash(new_password)
            user.updated_at = datetime.utcnow()
            db.commit()

            return True

    def list_users(self) -> list:
        """Get all users"""
        with get_db_context() as db:
            return db.query(User).all()

    def delete_user(self, user_id: int) -> bool:
        """
        Delete a user

        Args:
            user_id: User ID to delete

        Returns:
            True if successful

        Raises:
            ValueError: If trying to delete currently logged-in user
        """
        if self.current_user_id is not None and self.current_user_id == user_id:
            raise ValueError("Cannot delete your own account while logged in")

        with get_db_context() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            db.delete(user)
            db.commit()

            return True

    def create_default_admin(self) -> User:
        """Create a default admin user if none exists"""
        with get_db_context() as db:
            # Check if any users exist
            user_count = db.query(User).count()
            if user_count > 0:
                return None

            # Create default admin
            admin = User(
                username="admin",
                email="admin@caatmaster.local",
                hashed_password=self.get_password_hash("admin123"),
                full_name="System Administrator",
                is_active=True,
                is_superuser=True
            )

            db.add(admin)
            db.commit()
            db.refresh(admin)

            return admin

    def is_auth_enabled(self) -> bool:
        """Whether password-based login is required at startup. Off by
        default - this is a single-user desktop app with no server and no
        password-recovery flow, so login here is about attributing saved
        work to a name (author=... on save_caat, etc.), not about keeping
        anyone out. Device-level auth is assumed to already be the real
        security boundary. Persisted via QSettings so the choice survives
        restarts; changing it only takes effect on the next launch."""
        from PySide6.QtCore import QSettings
        settings = QSettings()
        return settings.value("auth/enabled", False, type=bool)

    def set_auth_enabled(self, enabled: bool):
        """Persist whether password-based login is required. The caller
        is responsible for telling the user this takes effect on next
        launch, not the current session, and (when turning it on) that
        there is no password-recovery flow."""
        from PySide6.QtCore import QSettings
        settings = QSettings()
        settings.setValue("auth/enabled", enabled)

    def login_as_system_user(self) -> User:
        """Auto-login as a local user named after this OS account, for
        when auth is disabled. Reuses the real User table/row (rather than
        a parallel fake-user concept) so every existing consumer of
        get_current_user()/current_user_id - project authorship, the
        Settings page's user info, etc. - keeps working completely
        unchanged. The row's password is a random value that's never
        shown or stored in plaintext anywhere, so this account can never
        actually be logged into through the normal username/password form
        even if auth is later turned back on."""
        import getpass
        import secrets

        username = getpass.getuser() or "local_user"

        with get_db_context() as db:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                try:
                    user = User(
                        username=username,
                        email=f"{username}@local",
                        hashed_password=self.get_password_hash(secrets.token_hex(32)),
                        full_name=username,
                        is_active=True,
                    )
                    db.add(user)
                    db.commit()
                except Exception:
                    # Extremely unlikely email collision with a manually
                    # registered account - fall back to a guaranteed-unique
                    # email rather than crash startup over it.
                    db.rollback()
                    user = User(
                        username=username,
                        email=f"{username}+{secrets.token_hex(4)}@local",
                        hashed_password=self.get_password_hash(secrets.token_hex(32)),
                        full_name=username,
                        is_active=True,
                    )
                    db.add(user)
                    db.commit()
            user_id = user.id

        self.current_user_id = user_id
        self.session_token = None
        return self.get_user_by_id(user_id)

    def save_session(self, file_path: str = None):
        """
        Save current session to file for auto-login

        Args:
            file_path: Path to save session (default: ~/.caatmaster_session)
        """
        if not self.session_token:
            return

        if file_path is None:
            file_path = Path.home() / ".caatmaster_session"

        Path(file_path).parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w') as f:
            f.write(self.session_token)

    def load_session(self, file_path: str = None) -> bool:
        """
        Load session from file for auto-login

        Args:
            file_path: Path to load session from (default: ~/.caatmaster_session)

        Returns:
            True if session loaded successfully
        """
        if file_path is None:
            file_path = Path.home() / ".caatmaster_session"

        if not Path(file_path).exists():
            return False

        try:
            with open(file_path, 'r') as f:
                token = f.read().strip()

            # Decode token
            payload = self.decode_access_token(token)
            if not payload:
                return False

            # Get user
            user_id = int(payload.get("sub"))
            user = self.get_user_by_id(user_id)
            if not user or not user.is_active:
                return False

            # Set current user
            self.current_user_id = user.id
            self.session_token = token

            return True

        except Exception:
            return False

    def clear_session(self, file_path: str = None):
        """Clear saved session"""
        if file_path is None:
            file_path = Path.home() / ".caatmaster_session"

        if Path(file_path).exists():
            Path(file_path).unlink()
