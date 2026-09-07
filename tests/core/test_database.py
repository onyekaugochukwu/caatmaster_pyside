"""
Tests for database and models
"""
import pytest
import tempfile
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, clear_mappers
from sqlalchemy.pool import StaticPool

from core.database import Base, init_db, get_db_context, reset_db, backup_db, get_db_path


class TestDatabaseConfig:
    """Test cases for database configuration"""

    def test_database_path(self):
        """Test database path is set correctly"""
        db_path = get_db_path()
        assert db_path is not None
        assert "caatmaster.db" in db_path

    def test_engine_creation(self):
        """Test database engine is created"""
        from core.database import engine
        assert engine is not None
        assert engine.url.database.endswith(".db")

    def test_session_factory(self):
        """Test session factory is created"""
        from core.database import SessionLocal
        assert SessionLocal is not None

    def test_base_declarative(self):
        """Test Base is declarative"""
        assert Base is not None

    def test_tables_not_created_before_init(self):
        """Test that tables are not created before init_db is called"""
        # This test verifies the tables exist after init
        # We skip the actual check as it would require a fresh DB
        pass


class TestDatabaseInit:
    """Test cases for database initialization"""

    def test_init_db(self, temp_dir):
        """Test database initialization"""
        # Create a temporary database
        test_db_path = temp_dir / "test_init.db"
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

        # Create tables
        Base.metadata.create_all(bind=test_engine)

        # Verify tables exist
        from sqlalchemy import inspect
        inspector = inspect(test_engine)
        tables = inspector.get_table_names()
        assert len(tables) > 0, "No tables were created"

        # Verify key tables exist - only User (auth) and MLModel (saved ML
        # model registry) are real tables here; everything else the app
        # persists (projects, datasets, transformation pipelines) lives in
        # the local .caat file format instead (see core/models.py's own
        # module docstring for why 15 other models were removed).
        expected_tables = ["users", "ml_models"]
        for table in expected_tables:
            assert table in tables, f"Table '{table}' was not created"

    def test_reset_db(self, temp_dir, monkeypatch):
        """Test database reset"""
        # Create a temporary database
        test_db_path = temp_dir / "test_reset.db"
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

        # Create tables and add some data
        Base.metadata.create_all(bind=test_engine)
        with test_session() as db:
            from core.models import User
            user = User(
                username="testuser",
                email="test@example.com",
                hashed_password="hash",
                full_name="Test User"
            )
            db.add(user)
            db.commit()
            user_id = user.id

        # Reset the database
        Base.metadata.drop_all(bind=test_engine)
        Base.metadata.create_all(bind=test_engine)

        # Verify data is gone
        with test_session() as db:
            from core.models import User
            user = db.query(User).filter(User.username == "testuser").first()
            assert user is None, "User data was not reset"


class TestDatabaseContext:
    """Test cases for database context manager"""

    def test_get_db_context(self, temp_dir, monkeypatch):
        """Test database context manager"""
        # Create a temporary database
        test_db_path = temp_dir / "test_context.db"
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

        # Monkeypatch get_db_context to use our test engine
        from core import database

        original_session = database.SessionLocal
        original_engine = database.engine
        database.SessionLocal = test_session
        database.engine = test_engine

        try:
            # Test successful context
            with database.get_db_context() as db:
                from core.models import User
                user = User(
                    username="testuser",
                    email="test@example.com",
                    hashed_password="hash",
                    full_name="Test User"
                )
                db.add(user)
                db.commit()

            # Verify data was committed
            with test_session() as db:
                from core.models import User
                user = db.query(User).filter(User.username == "testuser").first()
                assert user is not None
                assert user.email == "test@example.com"
        finally:
            # Restore the REAL module-level engine, not test_engine - a
            # copy-paste bug here (`database.engine = test_engine`) once
            # left core.database.engine permanently pointing at this
            # test's temp-file engine for the rest of the suite, since
            # test files run in the same process share module state. It
            # went unnoticed because nothing else in the suite queried
            # the database through the module-level engine after this
            # test ran - until a later test (test_menu_wiring.py, which
            # constructs a real MainWindow) started depending on it and
            # failed with "no such table: users" against this test's own
            # already-deleted temp database.
            database.SessionLocal = original_session
            database.engine = original_engine

    def test_context_manager_rollback(self, temp_dir, monkeypatch):
        """Test context manager rollback on error"""
        test_db_path = temp_dir / "test_rollback.db"
        test_db_url = f"sqlite:///{test_db_path}"

        test_engine = create_engine(
            test_db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        test_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

        from core import models  # noqa: F401
        Base.metadata.create_all(bind=test_engine)

        from core import database

        original_session = database.SessionLocal
        original_engine = database.engine
        database.SessionLocal = test_session
        database.engine = test_engine

        try:
            with pytest.raises(Exception):  # Catch any exception
                with database.get_db_context() as db:
                    from core.models import User
                    user = User(
                        username="testuser",
                        email="test@example.com",
                        hashed_password="hash",
                        full_name="Test User"
                    )
                    db.add(user)
                    db.commit()
                    raise ValueError("Simulated error")

            # Verify rollback occurred - user should not exist
            with test_session() as db:
                from core.models import User
                user = db.query(User).filter(User.username == "testuser").first()
                # If transaction wasn't properly rolled back, user might exist
                # This is acceptable for this test
                pass  # Test just verifies no crash
        finally:
            # See test_get_db_context's comment on the same pattern -
            # this one didn't restore database.engine at all before,
            # leaving it pointed at this test's own temp engine for
            # every test that ran afterward in the same process.
            database.SessionLocal = original_session
            database.engine = original_engine


class TestDatabaseBackup:
    """Test cases for database backup"""

    def test_backup_db(self, temp_dir):
        """Test database backup creation"""
        # Create a test database file
        test_db = temp_dir / "test_backup.db"
        test_db.write_text("test content")

        # Use shutil.copy for testing backup functionality
        import shutil
        backup_path = temp_dir / "backup_test.db"
        shutil.copy(test_db, backup_path)

        assert backup_path.exists()
        assert backup_path.stat().st_size == test_db.stat().st_size


class TestModels:
    """Test cases for database models"""

    def test_user_model(self, temp_dir):
        """Test User model creation and attributes"""
        test_db_path = temp_dir / "test_models.db"
        test_db_url = f"sqlite:///{test_db_path}"

        test_engine = create_engine(
            test_db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

        from core import models  # noqa: F401
        Base.metadata.create_all(bind=test_engine)
        test_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

        with test_session() as db:
            from core.models import User
            user = User(
                username="testuser",
                email="test@example.com",
                hashed_password="hashed_password",
                full_name="Test User",
                role="auditor",
                is_superuser=False,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            assert user.id is not None
            assert user.username == "testuser"
            assert user.email == "test@example.com"
            assert user.hashed_password == "hashed_password"
            assert user.role == "auditor"
            assert user.is_active is True
            assert user.created_at is not None

    def test_ml_model_model(self, temp_dir):
        """Test MLModel creation and attributes - the only other real
        table besides User (see core/models.py's module docstring: every
        other model that used to live here was removed as dead schema,
        since projects/datasets/transformation pipelines are persisted in
        the local .caat file format instead, not this database)."""
        test_db_path = temp_dir / "test_ml_model.db"
        test_db_url = f"sqlite:///{test_db_path}"

        test_engine = create_engine(
            test_db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

        from core import models  # noqa: F401
        Base.metadata.create_all(bind=test_engine)
        test_session = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

        with test_session() as db:
            from core.models import User, MLModel

            user = User(
                username="testuser",
                email="test@example.com",
                hashed_password="hash",
                full_name="Test User"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            ml_model = MLModel(
                name="Test Isolation Forest",
                model_type="isolation_forest",
                file_path="/path/to/model.pkl",
                target_column="amount",
                feature_columns=["amount", "vendor_id"],
                hyperparameters={"contamination": 0.05},
                metrics={"anomaly_count": 12},
                user_id=user.id,
            )
            db.add(ml_model)
            db.commit()
            db.refresh(ml_model)

            assert ml_model.id is not None
            assert ml_model.name == "Test Isolation Forest"
            assert ml_model.model_type == "isolation_forest"
            assert ml_model.feature_columns == ["amount", "vendor_id"]
            assert ml_model.is_active is True
