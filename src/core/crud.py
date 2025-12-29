"""
CRUD (Create, Read, Update, Delete) operations for the database models.
This file separates the data access logic from the database connection setup
and model definitions.
"""
from sqlalchemy.orm import Session
from typing import List, Optional

from . import models
from .data_processor import TransformationPipeline, LegacyDataProcessor
import polars as pl


def get_project_sessions(db: Session, project_id: int) -> List[models.ProjectSession]:
    """Retrieve all sessions for a given project."""
    return db.query(models.ProjectSession).filter(models.ProjectSession.project_id == project_id).all()


def save_transformation_pipeline(db: Session, session_id: int, pipeline: TransformationPipeline):
    """
    Saves the state of a TransformationPipeline to the database.
    This involves deleting old steps and saving the new ones.
    """
    # First, delete all existing steps for this session to ensure a clean save
    db.query(models.TransformationStep).filter(models.TransformationStep.session_id == session_id).delete()

    # Now, create new TransformationStep objects from the pipeline
    for i, step_data in enumerate(pipeline.get_steps()):
        db_step = models.TransformationStep(
            session_id=session_id,
            step_order=i,
            operation_name=step_data['operation_id'],
            parameters=step_data['params'],
            # Other fields like status can be set here if needed
        )
        db.add(db_step)

    # Commit the changes to the database
    db.commit()


def load_transformation_pipeline(db: Session, session_id: int, initial_df: pl.DataFrame) -> TransformationPipeline:
    """
    Loads a TransformationPipeline from the database for a given session.
    """
    # Retrieve all transformation steps for the session, ordered by their execution order
    db_steps = db.query(models.TransformationStep)\
                 .filter(models.TransformationStep.session_id == session_id)\
                 .order_by(models.TransformationStep.step_order)\
                 .all()

    # Create a new pipeline with the initial DataFrame
    pipeline = TransformationPipeline(initial_df=initial_df)

    # Add each step from the database into the pipeline object
    for db_step in db_steps:
        pipeline.add_step(
            operation_id=db_step.operation_name,
            params=db_step.parameters
        )
    
    return pipeline
