"""
Database Models for CAATmaster
Adapted from PostgreSQL to SQLite for desktop portability

Only User (authentication) and MLModel (saved ML model registry) are
backed by real tables here - everything else the app persists (projects,
datasets, transformation pipelines) lives in the local .caat file format
(core/caat_format.py, core/project_manager.py) instead. This file used to
define 15 additional models (Dataset, DatasetColumn, Project, MLRun,
AIProvider, ComplianceDocument, ProjectArtifact, ProjectTeam,
ProjectTemplate, ProjectAuditLog, ProjectSession, SessionSnapshot,
SessionShare, TransformationStep, TrainedModel) left over from an earlier
multi-user/server-oriented design - their tables were created by
init_db() on every launch but never actually queried or written by any
service or view, so they were removed rather than carried forward as dead
schema.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)  # Added username
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, default="auditor", nullable=False)
    is_superuser = Column(Boolean, default=False)  # Added is_superuser
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)  # Added last_login
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MLModel(Base):
    """Machine Learning Model storage"""
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    model_type = Column(String, nullable=False)  # e.g., isolation_forest, random_forest
    file_path = Column(String, nullable=False)
    target_column = Column(String, nullable=False)
    feature_columns = Column(JSON, nullable=False)
    hyperparameters = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # No FK constraint - there's no "projects" table anymore (see module
    # docstring); this is just an opaque identifier the caller filters on.
    project_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User")
