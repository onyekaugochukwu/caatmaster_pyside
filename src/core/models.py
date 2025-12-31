"""
Database Models for CAATmaster
Adapted from PostgreSQL to SQLite for desktop portability
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

    # Relationships
    datasets = relationship("Dataset", back_populates="user")
    created_projects = relationship("Project", foreign_keys="Project.created_by")
    ml_runs = relationship("MLRun", back_populates="user")
    ai_providers = relationship("AIProvider", back_populates="user")
    compliance_documents = relationship("ComplianceDocument", back_populates="user")
    created_artifacts = relationship("ProjectArtifact", foreign_keys="ProjectArtifact.created_by")
    team_memberships = relationship("ProjectTeam", back_populates="user")
    audit_logs = relationship("ProjectAuditLog", back_populates="user")
    created_templates = relationship("ProjectTemplate", foreign_keys="ProjectTemplate.created_by")
    snapshots = relationship("SessionSnapshot", foreign_keys="SessionSnapshot.created_by")
    session_shares_received = relationship("SessionShare", foreign_keys="SessionShare.shared_with_user_id")
    session_shares_sent = relationship("SessionShare", foreign_keys="SessionShare.shared_by_user_id")


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    file_path = Column(String, nullable=False)
    file_format = Column(String, nullable=False)
    row_count = Column(Integer, nullable=False)
    column_count = Column(Integer, nullable=False)
    file_size = Column(Integer, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="datasets")
    project = relationship("Project", back_populates="datasets")
    columns = relationship("DatasetColumn", back_populates="dataset", cascade="all, delete-orphan")


class DatasetColumn(Base):
    __tablename__ = "dataset_columns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    column_name = Column(String, nullable=False)
    data_type = Column(String, nullable=False)
    null_count = Column(Integer, default=0)
    unique_count = Column(Integer, default=0)
    min_value = Column(Text)
    max_value = Column(Text)
    mean_value = Column(Text)
    std_dev = Column(Text)

    # Relationships
    dataset = relationship("Dataset", back_populates="columns")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    client_name = Column(String)
    engagement_type = Column(String)  # audit, review, consulting, investigation
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String, default="planning")  # planning, active, completed, archived
    tags = Column(JSON)  # JSON array of tags

    # Enhanced audit metadata
    industry = Column(String)
    audit_standard = Column(String)  # GAAS, PCAOB, ISO, IIA
    materiality_threshold = Column(Float)
    risk_assessment = Column(JSON)
    deliverables = Column(JSON)
    engagement_start_date = Column(DateTime)
    engagement_end_date = Column(DateTime)

    # Relationships
    user = relationship("User", foreign_keys=[created_by])
    artifacts = relationship("ProjectArtifact", back_populates="project", cascade="all, delete-orphan")
    team_members = relationship("ProjectTeam", back_populates="project", cascade="all, delete-orphan")
    datasets = relationship("Dataset", back_populates="project", cascade="all, delete-orphan")
    ml_runs = relationship("MLRun", back_populates="project", cascade="all, delete-orphan")
    ai_providers = relationship("AIProvider", back_populates="project", cascade="all, delete-orphan")
    compliance_documents = relationship("ComplianceDocument", back_populates="project", cascade="all, delete-orphan")
    audit_logs = relationship("ProjectAuditLog", back_populates="project", cascade="all, delete-orphan")
    sessions = relationship("ProjectSession", back_populates="project", cascade="all, delete-orphan")


class MLRun(Base):
    __tablename__ = "ml_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, unique=True, nullable=False)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)
    dataset_name = Column(String, nullable=False)
    algorithm = Column(String, nullable=False)
    recipe_id = Column(String, nullable=True)
    assertions = Column(Text, nullable=True)
    risk_rating = Column(String, nullable=True)
    parameters_json = Column(Text, nullable=True)  # JSON string
    workflow_context_json = Column(Text, nullable=True)  # JSON string
    metrics_json = Column(Text, nullable=True)  # JSON string
    results_json = Column(Text, nullable=True)  # JSON string
    summary = Column(Text, nullable=True)
    exception_count = Column(Integer, default=0)
    exception_preview_json = Column(Text, nullable=True)  # JSON string
    exception_file_path = Column(String, nullable=True)
    promoted_dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)
    promoted_dataset_name = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    dataset = relationship("Dataset", foreign_keys=[dataset_id])
    promoted_dataset = relationship("Dataset", foreign_keys=[promoted_dataset_id])
    user = relationship("User", back_populates="ml_runs")
    project = relationship("Project", back_populates="ml_runs")


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
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User")
    project = relationship("Project")


class AIProvider(Base):
    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    model = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="ai_providers")
    project = relationship("Project", back_populates="ai_providers")


class ComplianceDocument(Base):
    __tablename__ = "compliance_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="compliance_documents")
    project = relationship("Project", back_populates="compliance_documents")


class ProjectArtifact(Base):
    __tablename__ = "project_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    artifact_type = Column(String, nullable=False)  # dataset, ml_run, query, analysis, document, report
    artifact_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    tags = Column(JSON)

    # Relationships
    project = relationship("Project", back_populates="artifacts")
    user = relationship("User", foreign_keys=[created_by])


class ProjectTeam(Base):
    __tablename__ = "project_team"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, default="auditor")  # lead, senior, staff, reviewer
    permissions = Column(JSON)  # JSON array of permissions
    added_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="team_members")
    user = relationship("User", back_populates="team_memberships")


class ProjectTemplate(Base):
    __tablename__ = "project_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    template_type = Column(String, nullable=False)  # financial_audit, sox_compliance, internal_audit, fraud_investigation
    configuration = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", foreign_keys=[created_by])


class ProjectAuditLog(Base):
    __tablename__ = "project_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)  # dataset_upload, ml_run, transformation, query, analysis, document_upload
    entity_type = Column(String)
    entity_id = Column(String)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")


class ProjectSession(Base):
    __tablename__ = "project_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    session_name = Column(String, nullable=False)

    # Session metadata
    is_active = Column(Boolean, default=True)
    is_auto_saved = Column(Boolean, default=True)
    version = Column(Integer, default=1)

    # State storage - all JSON for SQLite compatibility
    workspace_state = Column(JSON, nullable=False, default=dict)
    analysis_context = Column(JSON, nullable=False, default=dict)
    query_cache = Column(JSON, nullable=False, default=dict)
    ui_state = Column(JSON, nullable=False, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)

    # Recovery
    last_snapshot = Column(JSON)
    last_snapshot_at = Column(DateTime)

    # Relationships
    project = relationship("Project", back_populates="sessions")
    snapshots = relationship("SessionSnapshot", back_populates="session", cascade="all, delete-orphan")
    shares = relationship("SessionShare", back_populates="session", cascade="all, delete-orphan")
    transformation_steps = relationship("TransformationStep", cascade="all, delete-orphan", order_by="TransformationStep.step_order")


class SessionSnapshot(Base):
    __tablename__ = "session_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("project_sessions.id"), nullable=False)
    snapshot_data = Column(JSON, nullable=False)
    snapshot_type = Column(String, default="auto")  # auto, manual, recovery
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))

    # Relationships
    session = relationship("ProjectSession", back_populates="snapshots")
    user = relationship("User", foreign_keys=[created_by])


class SessionShare(Base):
    __tablename__ = "session_shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("project_sessions.id"), nullable=False)
    shared_with_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shared_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission = Column(String, default="view")  # view, edit, admin
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    session = relationship("ProjectSession", back_populates="shares")
    shared_with = relationship("User", foreign_keys=[shared_with_user_id])
    shared_by = relationship("User", foreign_keys=[shared_by_user_id])


# ============================================================================
# TRANSFORMATION PIPELINE MODELS
# ============================================================================

class TransformationStep(Base):
    __tablename__ = "transformation_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("project_sessions.id"), nullable=False)
    operation_type = Column(String(50), nullable=False)  # ml_predict, ai_enrich, audit_flag, etc.
    operation_name = Column(String(100), nullable=False)  # ml_detect_anomaly, ai_classify, etc.
    parameters = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    status = Column(String(20), default="pending")  # pending, success, error
    result_dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True)
    output_columns = Column(JSON)  # List of columns created by this step
    input_columns = Column(JSON)  # List of columns required by this step
    execution_time = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)
    step_order = Column(Integer, default=0)

    # Relationships
    session = relationship("ProjectSession", overlaps="transformation_steps")
    result_dataset = relationship("Dataset")


class TrainedModel(Base):
    __tablename__ = "trained_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(String(100), unique=True, nullable=False)
    model_name = Column(String(200), nullable=False)
    algorithm = Column(String(50), nullable=False)
    model_file_path = Column(String(500), nullable=False)
    feature_columns = Column(JSON, nullable=False)
    target_column = Column(String(100), nullable=True)
    training_metrics = Column(JSON, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used = Column(DateTime, nullable=True)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    project = relationship("Project")
