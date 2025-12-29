"""
ML Model Management Service for CAATmaster
Handles saving, loading, and managing trained ML models
"""
import pickle
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import polars as pl

from sqlalchemy.orm import Session
from core.database import get_db_context
from core.models import MLModel, MLRun


class MLModelService:
    """Service for managing ML models"""

    def __init__(self):
        """Initialize the ML model service"""
        self.models_dir = Path.home() / ".caatmaster" / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model: Any,
        model_name: str,
        model_type: str,
        target_column: str,
        feature_columns: List[str],
        metrics: Dict[str, float] = None,
        description: str = None,
        user_id: int = 1,
        project_id: int = None
    ) -> MLModel:
        """
        Save a trained model to disk and database

        Args:
            model: Trained model object (scikit-learn)
            model_name: Name for the model
            model_type: Type of model (e.g., "isolation_forest", "random_forest")
            target_column: Column the model was trained on
            feature_columns: List of feature columns used
            metrics: Dictionary of performance metrics
            description: Optional description
            user_id: User ID who created the model
            project_id: Optional project ID

        Returns:
            Created MLModel database record
        """
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{model_name}_{timestamp}.pkl"
        file_path = self.models_dir / filename

        # Save model to disk
        with open(file_path, 'wb') as f:
            pickle.dump(model, f)

        # Save metadata
        metadata_path = self.models_dir / f"{model_name}_{timestamp}_metadata.json"
        metadata = {
            'model_type': model_type,
            'target_column': target_column,
            'feature_columns': feature_columns,
            'metrics': metrics or {},
            'created_at': datetime.now().isoformat()
        }

        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Create database record
        model_id = None
        with get_db_context() as db:
            ml_model = MLModel(
                name=model_name,
                model_type=model_type,
                file_path=str(file_path),
                target_column=target_column,
                feature_columns=json.dumps(feature_columns),
                hyperparameters=json.dumps({}),
                metrics=json.dumps(metrics or {}),
                description=description,
                user_id=user_id,
                project_id=project_id,
                is_active=True
            )

            db.add(ml_model)
            db.commit()
            model_id = ml_model.id

        # Return fresh MLModel object
        return self.get_model_by_id(model_id)

    def load_model(self, model_id: int) -> tuple:
        """
        Load a model from disk

        Args:
            model_id: Model ID in database

        Returns:
            Tuple of (model object, metadata dict)
        """
        with get_db_context() as db:
            ml_model = db.query(MLModel).filter(MLModel.id == model_id).first()

            if not ml_model:
                raise ValueError(f"Model with ID {model_id} not found")

            if not Path(ml_model.file_path).exists():
                raise FileNotFoundError(f"Model file not found: {ml_model.file_path}")

            # Load model
            with open(ml_model.file_path, 'rb') as f:
                model = pickle.load(f)

            # Prepare metadata
            metadata = {
                'id': ml_model.id,
                'name': ml_model.name,
                'model_type': ml_model.model_type,
                'target_column': ml_model.target_column,
                'feature_columns': json.loads(ml_model.feature_columns),
                'hyperparameters': json.loads(ml_model.hyperparameters),
                'metrics': json.loads(ml_model.metrics),
                'description': ml_model.description,
                'created_at': ml_model.created_at.isoformat() if ml_model.created_at else None
            }

            return model, metadata

    def get_models(
        self,
        user_id: int = None,
        model_type: str = None,
        project_id: int = None
    ) -> List[MLModel]:
        """
        Get list of models with optional filters

        Args:
            user_id: Filter by user ID
            model_type: Filter by model type
            project_id: Filter by project ID

        Returns:
            List of MLModel objects
        """
        with get_db_context() as db:
            query = db.query(MLModel).filter(MLModel.is_active == True)

            if user_id:
                query = query.filter(MLModel.user_id == user_id)

            if model_type:
                query = query.filter(MLModel.model_type == model_type)

            if project_id:
                query = query.filter(MLModel.project_id == project_id)

            return query.order_by(MLModel.created_at.desc()).all()

    def get_model_by_id(self, model_id: int) -> Optional[MLModel]:
        """Get a model by ID"""
        with get_db_context() as db:
            return db.query(MLModel).filter(MLModel.id == model_id).first()

    def delete_model(self, model_id: int) -> bool:
        """
        Delete a model

        Args:
            model_id: Model ID to delete

        Returns:
            True if successful
        """
        with get_db_context() as db:
            ml_model = db.query(MLModel).filter(MLModel.id == model_id).first()

            if not ml_model:
                raise ValueError(f"Model with ID {model_id} not found")

            # Delete model file
            model_path = Path(ml_model.file_path)
            if model_path.exists():
                model_path.unlink()

            # Delete metadata file
            metadata_path = str(model_path).replace('.pkl', '_metadata.json')
            if Path(metadata_path).exists():
                Path(metadata_path).unlink()

            # Mark as deleted in database
            ml_model.is_active = False
            ml_model.deleted_at = datetime.utcnow()
            db.commit()

            return True

    def update_model(
        self,
        model_id: int,
        name: str = None,
        description: str = None
    ) -> MLModel:
        """
        Update model metadata

        Args:
            model_id: Model ID
            name: New name (optional)
            description: New description (optional)

        Returns:
            Updated MLModel
        """
        with get_db_context() as db:
            ml_model = db.query(MLModel).filter(MLModel.id == model_id).first()

            if not ml_model:
                raise ValueError(f"Model with ID {model_id} not found")

            if name:
                ml_model.name = name

            if description:
                ml_model.description = description

            ml_model.updated_at = datetime.utcnow()
            db.commit()

        # Return fresh MLModel object
        return self.get_model_by_id(model_id)

    def predict_with_model(
        self,
        model_id: int,
        df: pl.DataFrame,
        prediction_column: str = None
    ) -> pl.DataFrame:
        """
        Make predictions using a saved model

        Args:
            model_id: Model ID to use
            df: DataFrame to make predictions on
            prediction_column: Name for prediction column

        Returns:
            DataFrame with predictions added
        """
        # Load model
        model, metadata = self.load_model(model_id)

        # Get feature columns
        feature_cols = metadata['feature_columns']

        # Validate features exist
        missing_features = [col for col in feature_cols if col not in df.columns]
        if missing_features:
            raise ValueError(f"Missing feature columns: {missing_features}")

        # Extract features
        X = df.select(feature_cols).to_pandas()

        # Make predictions
        if hasattr(model, 'predict'):
            predictions = model.predict(X)

            # Add prediction column
            pred_col = prediction_column or f"prediction_{metadata['target_column']}"
            df = df.with_columns(pl.Series(predictions, name=pred_col))

            # Add probabilities if available
            if hasattr(model, 'predict_proba'):
                probabilities = model.predict_proba(X)
                for i, class_label in enumerate(model.classes_ if hasattr(model, 'classes_') else range(probabilities.shape[1])):
                    prob_col = f"{pred_col}_prob_{class_label}"
                    df = df.with_columns(pl.Series(probabilities[:, i], name=prob_col))

        elif hasattr(model, 'fit_predict'):
            # For anomaly detection models
            predictions = model.fit_predict(X)
            pred_col = prediction_column or f"prediction_{metadata['target_column']}"
            df = df.with_columns(pl.Series(predictions, name=pred_col))

            # Add anomaly scores if available
            if hasattr(model, 'score_samples'):
                scores = model.score_samples(X)
                score_col = f"{pred_col}_score"
                df = df.with_columns(pl.Series(scores, name=score_col))

        return df

    def get_model_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about saved models

        Returns:
            Dictionary with model statistics
        """
        with get_db_context() as db:
            total_models = db.query(MLModel).filter(MLModel.is_active == True).count()

            # Count by model type
            models_by_type = {}
            for model_type in ['isolation_forest', 'random_forest', 'logistic_regression',
                             'kmeans', 'dbscan', 'local_outlier_factor']:
                count = db.query(MLModel).filter(
                    MLModel.model_type == model_type,
                    MLModel.is_active == True
                ).count()
                if count > 0:
                    models_by_type[model_type] = count

            # Count by user
            from sqlalchemy import func
            user_counts = db.query(
                MLModel.user_id,
                func.count(MLModel.id)
            ).filter(
                MLModel.is_active == True
            ).group_by(MLModel.user_id).all()

            # Disk usage
            total_size = sum(f.stat().st_size for f in self.models_dir.glob("*.pkl") if f.is_file())

            return {
                'total_models': total_models,
                'models_by_type': models_by_type,
                'user_count': len(user_counts),
                'disk_usage_mb': total_size / (1024 * 1024)
            }

    def export_model(self, model_id: int, export_path: str) -> str:
        """
        Export a model to an external file

        Args:
            model_id: Model ID to export
            export_path: Destination file path

        Returns:
            Path to exported file
        """
        ml_model = self.get_model_by_id(model_id)
        if not ml_model:
            raise ValueError(f"Model with ID {model_id} not found")

        # Copy model file
        import shutil
        Path(export_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ml_model.file_path, export_path)

        # Copy metadata
        metadata_export = str(export_path).replace('.pkl', '_metadata.json')
        metadata_source = str(ml_model.file_path).replace('.pkl', '_metadata.json')
        if Path(metadata_source).exists():
            shutil.copy2(metadata_source, metadata_export)

        return export_path

    def import_model(
        self,
        model_path: str,
        model_name: str,
        model_type: str,
        target_column: str,
        feature_columns: List[str],
        description: str = None,
        user_id: int = 1
    ) -> MLModel:
        """
        Import a model from an external file

        Args:
            model_path: Path to model file
            model_name: Name for the model
            model_type: Type of model
            target_column: Target column name
            feature_columns: List of feature columns
            description: Optional description
            user_id: User ID

        Returns:
            Created MLModel record
        """
        # Copy model to models directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{model_name}_{timestamp}.pkl"
        dest_path = self.models_dir / filename

        import shutil
        shutil.copy2(model_path, dest_path)

        # Create database record
        model_id = None
        with get_db_context() as db:
            ml_model = MLModel(
                name=model_name,
                model_type=model_type,
                file_path=str(dest_path),
                target_column=target_column,
                feature_columns=json.dumps(feature_columns),
                hyperparameters=json.dumps({}),
                metrics=json.dumps({}),
                description=description or f"Imported from {Path(model_path).name}",
                user_id=user_id,
                is_active=True
            )

            db.add(ml_model)
            db.commit()
            model_id = ml_model.id

        # Return fresh MLModel object
        return self.get_model_by_id(model_id)
