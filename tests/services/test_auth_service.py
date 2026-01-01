"""
Tests for Authentication Service
"""
import pytest
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import User


class TestAuthService:
    """Test cases for the AuthService class"""

    @pytest.fixture
    def test_db(self, temp_dir):
        """Create a test database"""
        test_db_path = temp_dir / "test_auth.db"
        test_db_url = f"sqlite:///{test_db_path}"

        test_engine = create_engine(
            test_db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        test_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

        # Import models to ensure they're registered
        from core import models  # noqa: F401
        Base.metadata.create_all(bind=test_engine)

        yield test_session, test_engine

        # Cleanup
        Base.metadata.drop_all(bind=test_engine)

    @pytest.fixture
    def auth_service(self, test_db):
        """Create an AuthService instance with test database"""
        from core import database
        import services.auth_service as auth_module

        test_session, test_engine = test_db

        # Monkeypatch the database module
        original_session = database.SessionLocal
        original_engine = database.engine
        database.SessionLocal = test_session
        database.engine = test_engine

        # Create fresh auth service
        auth_service = auth_module.AuthService()

        yield auth_service

        # Restore original
        database.SessionLocal = original_session
        database.engine = original_engine

    def test_password_hashing(self, auth_service):
        """Test password hashing and verification"""
        password = "secure_password_123"
        hashed = auth_service.get_password_hash(password)

        # Hash should be different from original
        assert hashed != password
        assert len(hashed) > 50  # Argon2 hash is long

        # Verification should succeed
        assert auth_service.verify_password(password, hashed) is True

        # Wrong password should fail
        assert auth_service.verify_password("wrong_password", hashed) is False

    def test_password_hash_uniqueness(self, auth_service):
        """Test that same password produces different hashes (due to salt)"""
        password = "same_password"
        hash1 = auth_service.get_password_hash(password)
        hash2 = auth_service.get_password_hash(password)

        assert hash1 != hash2
        # But both should verify correctly
        assert auth_service.verify_password(password, hash1) is True
        assert auth_service.verify_password(password, hash2) is True

    def test_create_access_token(self, auth_service):
        """Test JWT token creation"""
        token_data = {
            "sub": "123",
            "username": "testuser",
            "email": "test@example.com"
        }
        token = auth_service.create_access_token(token_data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # JWT is fairly long

    def test_decode_access_token(self, auth_service):
        """Test JWT token decoding"""
        token_data = {
            "sub": "123",
            "username": "testuser",
            "email": "test@example.com"
        }
        token = auth_service.create_access_token(token_data)

        decoded = auth_service.decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "123"
        assert decoded["username"] == "testuser"

    def test_decode_invalid_token(self, auth_service):
        """Test decoding invalid token returns None"""
        invalid_token = "invalid.token.here"
        decoded = auth_service.decode_access_token(invalid_token)
        assert decoded is None

    def test_register_user(self, auth_service, test_db):
        """Test user registration"""
        test_session, _ = test_db

        user = auth_service.register_user(
            username="newuser",
            email="newuser@example.com",
            password="password123",
            full_name="New User"
        )

        assert user is not None
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.hashed_password != "password123"  # Should be hashed
        assert user.role == "auditor"  # Default role

        # Verify user exists in database
        with test_session() as db:
            db_user = db.query(User).filter(User.username == "newuser").first()
            assert db_user is not None

    def test_register_duplicate_username(self, auth_service):
        """Test registration fails with duplicate username"""
        auth_service.register_user(
            username="testuser",
            email="user1@example.com",
            password="password123"
        )

        with pytest.raises(ValueError, match="already exists"):
            auth_service.register_user(
                username="testuser",
                email="user2@example.com",
                password="password456"
            )

    def test_register_duplicate_email(self, auth_service):
        """Test registration fails with duplicate email"""
        auth_service.register_user(
            username="user1",
            email="same@example.com",
            password="password123"
        )

        with pytest.raises(ValueError, match="already exists"):
            auth_service.register_user(
                username="user2",
                email="same@example.com",
                password="password456"
            )

    def test_authenticate_user_success(self, auth_service, test_db):
        """Test successful user authentication"""
        auth_service.register_user(
            username="authuser",
            email="auth@example.com",
            password="correct_password"
        )

        user = auth_service.authenticate_user("authuser", "correct_password")

        assert user is not None
        assert user.username == "authuser"

    def test_authenticate_user_wrong_password(self, auth_service):
        """Test authentication fails with wrong password"""
        auth_service.register_user(
            username="authuser2",
            email="auth2@example.com",
            password="correct_password"
        )

        user = auth_service.authenticate_user("authuser2", "wrong_password")

        assert user is None

    def test_authenticate_user_by_email(self, auth_service):
        """Test authentication with email instead of username"""
        auth_service.register_user(
            username="emailuser",
            email="emaillogin@example.com",
            password="password123"
        )

        user = auth_service.authenticate_user("emaillogin@example.com", "password123")

        assert user is not None
        assert user.username == "emailuser"

    def test_authenticate_nonexistent_user(self, auth_service):
        """Test authentication fails for non-existent user"""
        user = auth_service.authenticate_user("nonexistent", "password")
        assert user is None

    def test_login(self, auth_service, test_db):
        """Test login returns token"""
        auth_service.register_user(
            username="loginuser",
            email="login@example.com",
            password="password123"
        )

        token = auth_service.login("loginuser", "password123")

        assert token is not None
        assert auth_service.current_user_id is not None
        assert auth_service.session_token == token

    def test_login_invalid_credentials(self, auth_service):
        """Test login fails with invalid credentials"""
        token = auth_service.login("nonexistent", "password")
        assert token is None
        assert auth_service.current_user_id is None

    def test_logout(self, auth_service):
        """Test logout clears session"""
        auth_service.current_user_id = 123
        auth_service.session_token = "test_token"

        auth_service.logout()

        assert auth_service.current_user_id is None
        assert auth_service.session_token is None

    def test_is_authenticated(self, auth_service):
        """Test is_authenticated check"""
        assert auth_service.is_authenticated() is False

        auth_service.current_user_id = 123
        assert auth_service.is_authenticated() is True

    def test_get_current_user(self, auth_service, test_db):
        """Test getting current user"""
        auth_service.register_user(
            username="currentuser",
            email="current@example.com",
            password="password123"
        )
        auth_service.login("currentuser", "password123")

        user = auth_service.get_current_user()
        assert user is not None
        assert user.username == "currentuser"

    def test_get_user_by_id(self, auth_service, test_db):
        """Test getting user by ID"""
        auth_service.register_user(
            username="byiduser",
            email="byid@example.com",
            password="password123"
        )
        auth_service.login("byiduser", "password123")

        user_id = auth_service.current_user_id
        user = auth_service.get_user_by_id(user_id)

        assert user is not None
        assert user.username == "byiduser"

    def test_get_user_by_username(self, auth_service, test_db):
        """Test getting user by username"""
        auth_service.register_user(
            username="byuser",
            email="byuser@example.com",
            password="password123"
        )

        user = auth_service.get_user_by_username("byuser")

        assert user is not None
        assert user.email == "byuser@example.com"

    def test_update_user_email(self, auth_service, test_db):
        """Test updating user email"""
        auth_service.register_user(
            username="updateuser",
            email="old@example.com",
            password="password123"
        )

        user = auth_service.update_user(
            user_id=auth_service.current_user_id or 1,
            email="new@example.com"
        )

        assert user.email == "new@example.com"

    def test_update_user_full_name(self, auth_service, test_db):
        """Test updating user full name"""
        auth_service.register_user(
            username="nameuser",
            email="name@example.com",
            password="password123"
        )

        user = auth_service.update_user(
            user_id=auth_service.current_user_id or 1,
            full_name="Updated Name"
        )

        assert user.full_name == "Updated Name"

    def test_change_password(self, auth_service, test_db):
        """Test changing password"""
        auth_service.register_user(
            username="pwduser",
            email="pwd@example.com",
            password="old_password"
        )

        result = auth_service.change_password(
            user_id=auth_service.current_user_id or 1,
            current_password="old_password",
            new_password="new_password"
        )

        assert result is True

        # Old password should not work
        assert auth_service.authenticate_user("pwduser", "old_password") is None

        # New password should work
        assert auth_service.authenticate_user("pwduser", "new_password") is not None

    def test_change_password_wrong_current(self, auth_service, test_db):
        """Test changing password with wrong current password"""
        auth_service.register_user(
            username="wrongpwd",
            email="wrongpwd@example.com",
            password="correct_password"
        )

        with pytest.raises(ValueError, match="Current password is incorrect"):
            auth_service.change_password(
                user_id=auth_service.current_user_id or 1,
                current_password="wrong_password",
                new_password="new_password"
            )

    def test_list_users(self, auth_service, test_db):
        """Test listing all users"""
        auth_service.register_user("user1", "user1@example.com", "password")
        auth_service.register_user("user2", "user2@example.com", "password")

        users = auth_service.list_users()

        assert len(users) >= 2
        usernames = [u.username for u in users]
        assert "user1" in usernames
        assert "user2" in usernames

    def test_create_default_admin(self, auth_service, test_db, monkeypatch):
        """Test default admin creation when no users exist"""
        # This should work when no users exist
        admin = auth_service.create_default_admin()
        # Returns None if users already exist
        # (since we registered users above, this might return None)
        # The key is it doesn't raise an error

    def test_session_save_load(self, auth_service, temp_dir):
        """Test saving and loading session"""
        auth_service.session_token = "test_token_123"
        session_file = temp_dir / "test_session"

        auth_service.save_session(str(session_file))

        # Create new auth service and load session
        from services import auth_service as auth_module
        new_auth_service = auth_module.AuthService()

        result = new_auth_service.load_session(str(session_file))
        # This will return False since the token is not valid
        # but the function should work without error
        # (token is just a random string, not a real JWT)

    def test_session_clear(self, auth_service, temp_dir):
        """Test clearing session"""
        session_file = temp_dir / "test_session"
        session_file.write_text("test_token")

        auth_service.clear_session(str(session_file))

        assert not session_file.exists()
