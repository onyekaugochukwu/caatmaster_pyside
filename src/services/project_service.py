"""
Project Service for CAATmaster
Manages projects, datasets, and sessions
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from core.database import SessionLocal, get_db_context
from core.models import (
    Project, Dataset, ProjectSession, User,
    ProjectArtifact, ProjectAuditLog
)


class ProjectService:
    """Service for project management"""

    def create_project(
        self,
        name: str,
        user_id: int = 1,
        description: str = None,
        client_name: str = None,
        engagement_type: str = "audit"
    ) -> Project:
        """Create a new project"""
        with get_db_context() as db:
            project = Project(
                name=name,
                description=description,
                client_name=client_name,
                engagement_type=engagement_type,
                created_by=user_id,
                status="planning"
            )
            db.add(project)
            db.commit()
            db.refresh(project)

            # Log creation
            self._log_activity(
                db, project.id, user_id, "project_created",
                {"project_name": name}
            )

            return project

    def get_projects(self, user_id: int = 1) -> List[Project]:
        """Get all projects for user"""
        with get_db_context() as db:
            projects = db.query(Project).filter(
                Project.created_by == user_id
            ).order_by(Project.created_at.desc()).all()
            return projects

    def get_project(self, project_id: int) -> Optional[Project]:
        """Get a specific project"""
        with get_db_context() as db:
            return db.query(Project).filter(Project.id == project_id).first()

    def update_project(
        self,
        project_id: int,
        name: str = None,
        description: str = None,
        status: str = None
    ) -> Optional[Project]:
        """Update project details"""
        with get_db_context() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return None

            if name:
                project.name = name
            if description is not None:
                project.description = description
            if status:
                project.status = status

            project.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(project)
            return project

    def delete_project(self, project_id: int) -> bool:
        """Delete a project"""
        with get_db_context() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return False

            db.delete(project)
            db.commit()
            return True

    def add_dataset_to_project(
        self,
        project_id: int,
        dataset_id: int
    ) -> bool:
        """Add a dataset to a project"""
        with get_db_context() as db:
            dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
            if not dataset:
                return False

            dataset.project_id = project_id
            db.commit()
            return True

    def get_project_datasets(self, project_id: int) -> List[Dataset]:
        """Get all datasets for a project"""
        with get_db_context() as db:
            return db.query(Dataset).filter(
                Dataset.project_id == project_id
            ).order_by(Dataset.created_at.desc()).all()

    def create_session(
        self,
        project_id: int,
        session_name: str,
        workspace_state: Dict[str, Any] = None
    ) -> ProjectSession:
        """Create a new analysis session"""
        with get_db_context() as db:
            session = ProjectSession(
                project_id=project_id,
                session_name=session_name,
                workspace_state=workspace_state or {},
                analysis_context={},
                query_cache={},
                ui_state={},
                is_active=True
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

    def get_sessions(self, project_id: int) -> List[ProjectSession]:
        """Get all sessions for a project"""
        with get_db_context() as db:
            return db.query(ProjectSession).filter(
                ProjectSession.project_id == project_id
            ).order_by(ProjectSession.created_at.desc()).all()

    def get_session(self, session_id: int) -> Optional[ProjectSession]:
        """Get a specific session"""
        with get_db_context() as db:
            return db.query(ProjectSession).filter(
                ProjectSession.id == session_id
            ).first()

    def save_session_state(
        self,
        session_id: int,
        workspace_state: Dict[str, Any],
        analysis_context: Dict[str, Any] = None,
        ui_state: Dict[str, Any] = None
    ) -> bool:
        """Save session state"""
        with get_db_context() as db:
            session = db.query(ProjectSession).filter(
                ProjectSession.id == session_id
            ).first()
            if not session:
                return False

            session.workspace_state = workspace_state
            if analysis_context:
                session.analysis_context = analysis_context
            if ui_state:
                session.ui_state = ui_state
            session.updated_at = datetime.utcnow()
            session.last_accessed = datetime.utcnow()

            db.commit()
            return True

    def delete_session(self, session_id: int) -> bool:
        """Delete a session"""
        with get_db_context() as db:
            session = db.query(ProjectSession).filter(
                ProjectSession.id == session_id
            ).first()
            if not session:
                return False

            db.delete(session)
            db.commit()
            return True

    def log_activity(
        self,
        project_id: int,
        user_id: int,
        action: str,
        details: Dict[str, Any] = None
    ):
        """Log an activity in the project"""
        with get_db_context() as db:
            log = ProjectAuditLog(
                project_id=project_id,
                user_id=user_id,
                action=action,
                details=details or {}
            )
            db.add(log)
            db.commit()

    def _log_activity(
        self,
        db: Session,
        project_id: int,
        user_id: int,
        action: str,
        details: Dict[str, Any]
    ):
        """Internal log activity (with existing session)"""
        log = ProjectAuditLog(
            project_id=project_id,
            user_id=user_id,
            action=action,
            details=details
        )
        db.add(log)

    def get_audit_logs(self, project_id: int, limit: int = 100) -> List[ProjectAuditLog]:
        """Get audit logs for a project"""
        with get_db_context() as db:
            return db.query(ProjectAuditLog).filter(
                ProjectAuditLog.project_id == project_id
            ).order_by(ProjectAuditLog.timestamp.desc()).limit(limit).all()
