"""
ML Service for CAATmaster
Implements ML operations that create prediction columns
"""
import polars as pl
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.svm import OneClassSVM, SVC
from sklearn.neighbors import LocalOutlierFactor
from typing import Dict, Any, List, Tuple, Optional
import joblib
from pathlib import Path
import uuid


class MLService:
    """Service for ML operations that create prediction columns"""

    def __init__(self, models_dir: str = None):
        if models_dir is None:
            models_dir = Path(__file__).parent.parent.parent / "data" / "models"
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def detect_anomalies(
        self,
        df: pl.DataFrame,
        column: str,
        algorithm: str = "isolation_forest",
        contamination: float = 0.1,
        flag_column: str = None,
        score_column: str = None
    ) -> pl.DataFrame:
        """
        Detect anomalies using ML - creates flag and score columns
        """
        if flag_column is None:
            flag_column = f"{column}_is_anomaly"
        if score_column is None:
            score_column = f"{column}_anomaly_score"

        # Get column values
        values = df[column].to_numpy().reshape(-1, 1)

        # Remove null values for training
        valid_mask = ~df[column].is_null()
        valid_values = values[valid_mask]

        if len(valid_values) < 10:
            raise ValueError(f"Column {column} has too few valid values for anomaly detection")

        # Train model
        if algorithm == "isolation_forest":
            model = IsolationForest(contamination=contamination, random_state=42)
            predictions = model.fit_predict(valid_values)
            scores = model.score_samples(valid_values)
        elif algorithm == "local_outlier_factor":
            model = LocalOutlierFactor(n_neighbors=20, contamination=contamination, novelty=True)
            model.fit(valid_values)
            predictions = model.predict(valid_values)
            scores = model.score_samples(valid_values)
        elif algorithm == "one_class_svm":
            model = OneClassSVM(nu=contamination)
            model.fit(valid_values)
            predictions = model.predict(valid_values)
            scores = model.score_samples(valid_values)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        # Create result arrays
        result_flags = np.zeros(len(df), dtype=int)
        result_scores = np.zeros(len(df), dtype=float)

        # Fill in results for valid rows
        valid_indices = np.where(valid_mask.to_numpy())[0]
        result_flags[valid_indices] = (predictions == -1).astype(int)  # -1 means anomaly
        result_scores[valid_indices] = -scores  # Negative because lower = more anomalous

        # Add columns to dataframe
        result_df = df.with_columns([
            pl.Series(flag_column, result_flags, dtype=pl.Boolean),
            pl.Series(score_column, result_scores, dtype=pl.Float64)
        ])

        return result_df

    def classify(
        self,
        df: pl.DataFrame,
        features: List[str],
        model_id: str,
        output_column: str = "predicted_class",
        probability_column: str = None
    ) -> pl.DataFrame:
        """
        Classify using trained model - creates prediction and probability columns
        """
        # Load or train model
        if model_id == "train_new":
            raise ValueError("Please train a model first using ml_train_model")

        model_path = self.models_dir / f"{model_id}.pkl"
        if not model_path.exists():
            raise ValueError(f"Model {model_id} not found. Please train it first.")

        model_data = joblib.load(model_path)
        model = model_data['model']
        feature_names = model_data['feature_names']
        label_encoder = model_data.get('label_encoder')

        # Prepare features
        X = df.select(features).to_numpy()

        # Handle null values
        X = np.nan_to_num(X, nan=0)

        # Predict
        predictions = model.predict(X)

        # Convert back to labels if encoder exists
        if label_encoder:
            predictions = label_encoder.inverse_transform(predictions)

        # Get probabilities if supported
        probabilities = None
        if probability_column and hasattr(model, 'predict_proba'):
            proba = model.predict_proba(X)
            probabilities = np.max(proba, axis=1)

        # Create result dataframe
        result_columns = [pl.Series(output_column, predictions)]

        if probabilities is not None:
            result_columns.append(pl.Series(probability_column, probabilities))

        result_df = df.with_columns(result_columns)

        return result_df

    def calculate_risk_score(
        self,
        df: pl.DataFrame,
        group_column: str,
        feature_columns: List[str],
        output_column: str = None
    ) -> pl.DataFrame:
        """
        Calculate risk scores by group - creates risk_score column
        """
        if output_column is None:
            output_column = f"{group_column}_risk_score"

        def calculate_group_risk(group: pl.DataFrame) -> pl.DataFrame:
            """Calculate risk score for a single group"""
            # Extract features
            features = group.select(feature_columns).to_numpy()

            # Simple risk score: average of normalized features
            # Remove null values
            features = np.nan_to_num(features, nan=0)

            if features.size == 0:
                return group.with_columns(pl.lit(0.0).alias(output_column))

            # Normalize each feature to 0-1 range
            normalized = (features - features.min(axis=0)) / (features.max(axis=0) - features.min(axis=0) + 1e-8)

            # Risk score is average of normalized values
            risk_score = float(np.mean(normalized))

            # Add same score to all rows in group
            n_rows = len(group)
            return group.with_columns(pl.lit(risk_score).alias(output_column))

        # Group by column and calculate risk for each group
        result_df = df.group_by(group_column).map_groups(
            calculate_group_risk
        )

        return result_df

    def train_model(
        self,
        df: pl.DataFrame,
        features: List[str],
        target: str,
        algorithm: str = "random_forest",
        model_name: str = None,
        test_split: float = 0.2
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Train a classification model - returns model_id and metrics
        """
        if model_name is None:
            model_name = f"model_{uuid.uuid4().hex[:8]}"

        # Prepare data
        X = df.select(features).to_numpy()
        y = df[target].to_numpy()

        # Remove rows with null values
        valid_mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X = X[valid_mask]
        y = y[valid_mask]

        if len(X) < 10:
            raise ValueError("Not enough valid data for training")

        # Encode labels if classification
        label_encoder = None
        if y.dtype == object or y.dtype.kind in ['U', 'S', 'O']:
            label_encoder = LabelEncoder()
            y = label_encoder.fit_transform(y)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_split, random_state=42
        )

        # Scale features
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)

        # Train model
        if algorithm == "random_forest":
            model = RandomForestClassifier(n_estimators=100, random_state=42)
        elif algorithm == "logistic_regression":
            model = LogisticRegression(random_state=42, max_iter=1000)
        elif algorithm == "svm":
            model = SVC(probability=True, random_state=42)
        elif algorithm == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(random_state=42)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        model.fit(X_train, y_train)

        # Calculate metrics
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)

        metrics = {
            "train_accuracy": float(train_score),
            "test_accuracy": float(test_score),
            "n_samples": int(len(X)),
            "n_features": int(len(features)),
            "n_classes": int(len(np.unique(y)))
        }

        # Save model
        model_data = {
            'model': model,
            'scaler': scaler,
            'feature_names': features,
            'target_name': target,
            'label_encoder': label_encoder,
            'algorithm': algorithm,
            'metrics': metrics
        }

        model_path = self.models_dir / f"{model_name}.pkl"
        joblib.dump(model_data, model_path)

        return model_name, metrics
