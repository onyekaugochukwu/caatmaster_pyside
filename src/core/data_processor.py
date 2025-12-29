"""
Data Processor for CAATmaster
Handles data import, export, and transformations using Polars
"""
import polars as pl
from typing import Dict, Any, List, Optional
from pathlib import Path
import re
import hashlib
from datetime import datetime
import numpy as np

# Import the operation registry
from .operation_registry import OPERATION_REGISTRY, TransformationStepType


class DataProcessor:
    """
    A stateless processor that executes individual data transformation operations.
    The methods in this class are called by the TransformationPipeline.
    """

    def apply_operation(self, df: pl.DataFrame, operation_id: str, params: Dict[str, Any]) -> pl.DataFrame:
        """
        Main dispatcher for all transformation operations.

        Args:
            df: The input Polars DataFrame.
            operation_id: The unique ID of the operation from OPERATION_REGISTRY.
            params: A dictionary of parameters for the operation.

        Returns:
            A new Polars DataFrame with the operation applied.
        """
        # Look up the operation to find its type
        op_info = OPERATION_REGISTRY.get(operation_id)
        if not op_info:
            raise ValueError(f"Unknown operation_id: {operation_id}")

        op_type = op_info['type']

        # Generate output column name(s) from the source column
        column = params.get('column')
        creates_columns = op_info.get('creates_columns', False)
        if creates_columns and column:
            if isinstance(creates_columns, list):
                # Multiple columns created (e.g., split operations)
                output_cols = [col_name.format(col=column) for col_name in creates_columns]
                params['output_cols'] = output_cols
            elif creates_columns is True:
                # Single column created
                naming_pattern = op_info.get('column_naming_pattern', '{column}_{operation}')
                operation_name = operation_id.split('_')[-1]  # Extract operation suffix
                output_col = naming_pattern.format(column=column, operation=operation_name)
                params['output_col'] = output_col

        # Dispatch based on operation type or specific ID
        # Text transformations
        if operation_id == 'text_uppercase':
            return self.uppercase(df, **params)
        elif operation_id == 'text_lowercase':
            return self.lowercase(df, **params)
        elif operation_id == 'text_titlecase':
            return self.titlecase(df, **params)
        elif operation_id == 'text_trim':
            return self.trim(df, **params)
        elif operation_id == 'text_extract_numbers':
            return self.extract_numbers(df, **params)
        elif operation_id == 'text_extract_text':
            return self.extract_text(df, **params)
        elif operation_id == 'text_reverse':
            return self.reverse_text(df, **params)
        elif operation_id == 'text_length':
            return self.text_length(df, **params)
        elif operation_id == 'text_hash_md5':
            return self.hash_md5(df, **params)
        elif operation_id == 'text_soundex':
            return self.soundex(df, **params)

        # Math transformations
        elif operation_id == 'math_round':
            return self.round_val(df, **params)
        elif operation_id == 'math_ceil':
            return self.ceil_val(df, **params)
        elif operation_id == 'math_floor':
            return self.floor_val(df, **params)
        elif operation_id == 'math_abs':
            return self.abs_val(df, **params)
        elif operation_id == 'math_sqrt':
            return self.sqrt_val(df, **params)
        elif operation_id == 'math_square':
            return self.square_val(df, **params)
        elif operation_id == 'math_log':
            return self.log_val(df, **params)
        elif operation_id == 'math_log10':
            return self.log10_val(df, **params)
        elif operation_id == 'math_exp':
            return self.exp_val(df, **params)

        # Trigonometric transformations
        elif operation_id == 'trig_sin':
            return self.sin_val(df, **params)
        elif operation_id == 'trig_cos':
            return self.cos_val(df, **params)
        elif operation_id == 'trig_tan':
            return self.tan_val(df, **params)
        elif operation_id == 'trig_asin':
            return self.asin_val(df, **params)
        elif operation_id == 'trig_acos':
            return self.acos_val(df, **params)
        elif operation_id == 'trig_atan':
            return self.atan_val(df, **params)

        # DateTime transformations
        elif operation_id == 'datetime_year':
            return self.extract_year(df, **params)
        elif operation_id == 'datetime_month':
            return self.extract_month(df, **params)
        elif operation_id == 'datetime_day':
            return self.extract_day(df, **params)
        elif operation_id == 'datetime_hour':
            return self.extract_hour(df, **params)
        elif operation_id == 'datetime_minute':
            return self.extract_minute(df, **params)
        elif operation_id == 'datetime_second':
            return self.extract_second(df, **params)
        elif operation_id == 'datetime_weekday':
            return self.extract_weekday(df, **params)
        elif operation_id == 'datetime_quarter':
            return self.extract_quarter(df, **params)
        elif operation_id == 'datetime_age_days':
            return self.age_days(df, **params)
        elif operation_id == 'datetime_age_years':
            return self.age_years(df, **params)
        elif operation_id == 'datetime_is_weekend':
            return self.is_weekend(df, **params)
        elif operation_id == 'datetime_is_leap_year':
            return self.is_leap_year(df, **params)
        elif operation_id == 'datetime_days_in_month':
            return self.days_in_month(df, **params)

        # Statistical transformations
        elif operation_id == 'stat_zscore':
            return self.zscore_transform(df, **params)
        elif operation_id == 'stat_percent_rank':
            return self.percent_rank_transform(df, **params)
        elif operation_id == 'stat_rank':
            return self.rank_transform(df, **params)

        # ML transformations
        elif operation_id == 'ml_anomaly_iforest':
            return self.ml_anomaly_iforest(df, **params)
        elif operation_id == 'ml_anomaly_zscore':
            return self.ml_anomaly_zscore(df, **params)
        elif operation_id == 'ml_anomaly_iqr':
            return self.ml_anomaly_iqr(df, **params)
        elif operation_id == 'ml_anomaly_lof':
            return self.ml_anomaly_lof(df, **params)
        elif operation_id == 'ml_outlier':
            return self.ml_outlier_detection(df, **params)
        elif operation_id == 'ml_cluster':
            return self.ml_clustering(df, **params)
        elif operation_id == 'ml_forecast':
            return self.ml_forecast(df, **params)

        # ML Training operations
        elif operation_id == 'ml_train':
            return self.ml_train_model(df, **params)

        # Audit transformations
        elif operation_id == 'audit_benfords_law':
            return self.audit_benford_law(df, **params)

        # AI transformations
        elif operation_id == 'ai_explain':
            return self.ai_explain_column(df, **params)
        elif operation_id == 'ai_sentiment':
            return self.ai_sentiment_analysis(df, **params)
        elif operation_id == 'ai_extract':
            return self.ai_entity_extraction(df, **params)
        elif operation_id == 'ai_pattern_learn':
            return self.ai_pattern_learning(df, **params)

        # Column operations
        elif operation_id == 'column_rename':
            return self.rename_col(df, **params)
        elif operation_id == 'column_change_dtype':
            return self.change_data_type(df, **params)

        # Split operations
        elif operation_id == 'split_comma':
            return self.split_column(df, **params, delimiter=',')
        elif operation_id == 'split_space':
            return self.split_column(df, **params, delimiter=' ')
        elif operation_id == 'split_semicolon':
            return self.split_column(df, **params, delimiter=';')
        elif operation_id == 'split_pipe':
            return self.split_column(df, **params, delimiter='|')
        elif operation_id == 'split_custom':
            return self.split_column(df, **params)

        # Pivot operations
        elif op_type == TransformationStepType.PIVOT:
            return self.pivot(df, **params)
        elif op_type == TransformationStepType.UNPIVOT:
            return self.unpivot(df, **params)

        # Filter operations
        elif op_type == TransformationStepType.FILTER:
            return self.filter_rows(df, **params)

        # Sort operations
        elif op_type == TransformationStepType.SORT:
            return self.sort_rows(df, **params)

        else:
            raise NotImplementedError(f"Operation '{operation_id}' of type '{op_type}' is not yet implemented.")

    # ============================================================================
    # TEXT TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def uppercase(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Convert text to uppercase"""
        return df.with_columns(pl.col(column).str.to_uppercase().alias(output_col))

    def lowercase(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Convert text to lowercase"""
        return df.with_columns(pl.col(column).str.to_lowercase().alias(output_col))

    def titlecase(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Convert text to title case"""
        return df.with_columns(pl.col(column).str.to_titlecase().alias(output_col))

    def trim(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Remove leading/trailing whitespace"""
        return df.with_columns(pl.col(column).str.strip_chars().alias(output_col))

    def extract_numbers(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract numbers from text"""
        return df.with_columns(
            pl.col(column).str.extract_all(r"\d+").list.join("").alias(output_col)
        )

    def extract_text(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract alphabetic text"""
        return df.with_columns(
            pl.col(column).str.replace(r"\d+", "", literal=False).str.strip().alias(output_col)
        )

    def reverse_text(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Reverse text string"""
        return df.with_columns(
            pl.col(column).str.reverse().alias(output_col)
        )

    def text_length(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Get text length"""
        return df.with_columns(pl.col(column).str.len_bytes().alias(output_col))

    def hash_md5(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Create MD5 hash"""
        import hashlib
        return df.with_columns(
            pl.col(column).map_elements(
                lambda x: hashlib.md5(str(x).encode()).hexdigest() if x is not None else None,
                return_dtype=pl.Utf8
            ).alias(output_col)
        )

    def soundex(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Create Soundex code"""
        def soundex_code(word):
            if not word:
                return "0000"
            word = str(word).upper()[:4]
            mapping = {"BFPV": "1", "CGJKQSXZ": "2", "DT": "3", "L": "4", "MN": "5", "R": "6"}
            result = [word[0]]
            prev = ""
            for char in word[1:]:
                for letters, code in mapping.items():
                    if char in letters and code != prev:
                        result.append(code)
                        prev = code
                        break
            return (''.join(result) + "000")[:4]

        return df.with_columns(
            pl.col(column).map_elements(soundex_code, return_dtype=pl.Utf8).alias(output_col)
        )

    # ============================================================================
    # MATH TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def round_val(self, df: pl.DataFrame, column: str, output_col: str, decimals: int = 2) -> pl.DataFrame:
        """Round numbers"""
        return df.with_columns(pl.col(column).round(decimals).alias(output_col))

    def ceil_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Ceiling (round up)"""
        return df.with_columns(pl.col(column).ceil().alias(output_col))

    def floor_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Floor (round down)"""
        return df.with_columns(pl.col(column).floor().alias(output_col))

    def abs_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Absolute value"""
        return df.with_columns(pl.col(column).abs().alias(output_col))

    def sqrt_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Square root"""
        return df.with_columns((pl.col(column) ** 0.5).alias(output_col))

    def square_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Square"""
        return df.with_columns((pl.col(column) ** 2).alias(output_col))

    def log_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Natural logarithm"""
        return df.with_columns(pl.col(column).log().alias(output_col))

    def log10_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Base-10 logarithm"""
        return df.with_columns(pl.col(column).log10().alias(output_col))

    def exp_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Exponential (e^x)"""
        return df.with_columns(pl.col(column).exp().alias(output_col))

    # ============================================================================
    # TRIGONOMETRIC TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def sin_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Sine (radians)"""
        return df.with_columns(pl.col(column).sin().alias(output_col))

    def cos_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Cosine (radians)"""
        return df.with_columns(pl.col(column).cos().alias(output_col))

    def tan_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Tangent (radians)"""
        return df.with_columns(pl.col(column).tan().alias(output_col))

    def asin_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Arc sine (radians)"""
        return df.with_columns(pl.col(column).arcsin().alias(output_col))

    def acos_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Arc cosine (radians)"""
        return df.with_columns(pl.col(column).arccos().alias(output_col))

    def atan_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Arc tangent (radians)"""
        return df.with_columns(pl.col(column).arctan().alias(output_col))

    # ============================================================================
    # DATETIME TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def _ensure_datetime(self, df: pl.DataFrame, column: str):
        """Ensure column is datetime type"""
        if df[column].dtype == pl.Utf8:
            return df[column].str.to_datetime()
        return df[column]

    def extract_year(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract year"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.year().alias(output_col))

    def extract_month(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract month (1-12)"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.month().alias(output_col))

    def extract_day(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract day of month"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.day().alias(output_col))

    def extract_hour(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract hour"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.hour().alias(output_col))

    def extract_minute(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract minute"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.minute().alias(output_col))

    def extract_second(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract second"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.second().alias(output_col))

    def extract_weekday(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract weekday (0=Monday, 6=Sunday)"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.weekday().alias(output_col))

    def extract_quarter(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract quarter (1-4)"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.quarter().alias(output_col))

    def age_days(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate age in days from today"""
        from datetime import datetime
        today = datetime.now()
        dates = self._ensure_datetime(df, column)
        return df.with_columns(
            (pl.lit(today).cast(pl.Datetime()) - dates.cast(pl.Datetime())).dt.days().abs().alias(output_col)
        )

    def age_years(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate age in years from today"""
        days_col = f"_temp_days_{column}"
        dates = self._ensure_datetime(df, column)
        today = datetime.now()
        temp_df = df.with_columns(
            (pl.lit(today).cast(pl.Datetime()) - dates.cast(pl.Datetime())).dt.days().abs().alias(days_col)
        )
        return temp_df.with_columns(
            (pl.col(days_col) / 365.25).cast(pl.Int64).alias(output_col)
        ).drop(days_col)

    def is_weekend(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Check if date is weekend"""
        dates = self._ensure_datetime(df, column)
        weekday = dates.dt.weekday()
        return df.with_columns(((weekday == 6) | (weekday == 7)).alias(output_col))

    def is_leap_year(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Check if year is leap year"""
        dates = self._ensure_datetime(df, column)
        year = dates.dt.year()
        return df.with_columns(((year % 4 == 0) & ((year % 100 != 0) | (year % 400 == 0))).alias(output_col))

    def days_in_month(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Get days in month"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(
            pl.when(dates.dt.month().is_in([1, 3, 5, 7, 8, 10, 12]))
            .then(31)
            .when(dates.dt.month().is_in([4, 6, 9, 11]))
            .then(30)
            .when(dates.dt.month() == 2)
            .then(pl.when((dates.dt.year() % 4 == 0) & ((dates.dt.year() % 100 != 0) | (dates.dt.year() % 400 == 0))).then(29).otherwise(28))
            .otherwise(0)
            .alias(output_col)
        )

    # ============================================================================
    # STATISTICAL TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def zscore_transform(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate z-score"""
        col = pl.col(column)
        mean = df[column].mean()
        std = df[column].std()
        if std == 0:
            std = 1
        return df.with_columns(((col - mean) / std).alias(output_col))

    def percent_rank_transform(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate percent rank"""
        return df.with_columns(pl.col(column).rank("average", pct=True).alias(output_col))

    def rank_transform(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate rank"""
        return df.with_columns(pl.col(column).rank("average").alias(output_col))

    # ============================================================================
    # ML TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def ml_anomaly_iforest(self, df: pl.DataFrame, column: str, output_col: str, contamination: float = 0.1) -> pl.DataFrame:
        """Anomaly detection using Isolation Forest - simplified"""
        import numpy as np
        col_data = df[column].to_numpy().reshape(-1, 1)
        mean_val = np.mean(col_data)
        std_val = np.std(col_data)
        if std_val == 0:
            std_val = 1

        distances = np.abs(col_data - mean_val) / std_val
        threshold = 2.5
        is_anomaly = distances > threshold
        scores = 1 - (1 / (1 + distances))

        return df.with_columns([
            pl.Series(name=output_col, values=is_anomaly.flatten())
        ])

    def ml_anomaly_zscore(self, df: pl.DataFrame, column: str, output_col: str, threshold: float = 3.0) -> pl.DataFrame:
        """Anomaly detection using Z-score"""
        col = pl.col(column)
        mean = df[column].mean()
        std = df[column].std()
        if std == 0:
            std = 1
        zscore = (col - mean) / std
        return df.with_columns((zscore.abs() > threshold).alias(output_col))

    def ml_anomaly_iqr(self, df: pl.DataFrame, column: str, output_col: str, multiplier: float = 1.5) -> pl.DataFrame:
        """Anomaly detection using IQR"""
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - multiplier * IQR
        upper_bound = Q3 + multiplier * IQR
        return df.with_columns(
            ((pl.col(column) < lower_bound) | (pl.col(column) > upper_bound)).alias(output_col)
        )

    def ml_anomaly_lof(self, df: pl.DataFrame, column: str, output_col: str, n_neighbors: int = 20) -> pl.DataFrame:
        """Local Outlier Factor - simplified"""
        import numpy as np
        col_data = df[column].to_numpy()
        mean_val = np.mean(col_data)
        distances = np.abs(col_data - mean_val)
        max_dist = np.max(distances)
        if max_dist == 0:
            max_dist = 1
        scores = 1 - (distances / max_dist)
        threshold = 0.3
        is_outlier = scores < threshold
        return df.with_columns(pl.Series(name=output_col, values=is_outlier))

    def ml_outlier_detection(self, df: pl.DataFrame, column: str, output_col: str, method: str = 'iqr') -> pl.DataFrame:
        """General outlier detection"""
        if method == 'zscore':
            return self.ml_anomaly_zscore(df, column=column, output_col=output_col, threshold=3.0)
        else:
            return self.ml_anomaly_iqr(df, column=column, output_col=output_col, multiplier=1.5)

    def ml_clustering(self, df: pl.DataFrame, column: str, output_col: str, n_clusters: int = 3) -> pl.DataFrame:
        """K-Means clustering - simplified"""
        import numpy as np
        col_data = df[column].to_numpy().reshape(-1, 1)
        means = np.mean(col_data, axis=0)
        stds = np.std(col_data, axis=0)
        if stds == 0:
            stds = 1
        normalized = (col_data - means) / stds

        np.random.seed(42)
        centers = normalized[np.random.choice(len(normalized), n_clusters, replace=False)]

        distances = np.zeros((len(normalized), n_clusters))
        for i in range(n_clusters):
            distances[:, i] = np.linalg.norm(normalized - centers[i], axis=1)
        labels = np.argmin(distances, axis=1)

        return df.with_columns(pl.Series(name=output_col, values=labels))

    def ml_forecast(self, df: pl.DataFrame, column: str, output_col: str, periods: int = 12) -> pl.DataFrame:
        """Simple time series forecast using exponential smoothing"""
        import numpy as np
        values = df[column].to_numpy()
        if len(values) == 0:
            return df.with_columns(pl.lit(None).alias(output_col))

        alpha = 0.3
        n = len(values)
        smoothed = np.zeros(n)

        smoothed[0] = values[0]
        for i in range(1, n):
            smoothed[i] = alpha * values[i] + (1 - alpha) * smoothed[i - 1]

        return df.with_columns(pl.Series(name=output_col, values=smoothed))

    def ml_train_model(self, df: pl.DataFrame, model_name: str, algorithm: str, features: List[str],
                      target: str, test_split: float = 0.2, random_seed: int = 42) -> pl.DataFrame:
        """
        Train an ML model and save it for later use.
        This operation doesn't modify the dataframe but saves a trained model.
        """
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, classification_report
            import joblib
            import os
        except ImportError:
            raise ImportError("scikit-learn and joblib are required for ML training")

        # Prepare data
        X = df.select(features).to_pandas()
        y = df[target].to_pandas()

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_split, random_state=random_seed
        )

        # Select and train model
        if algorithm == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(random_state=random_seed)
        elif algorithm == "logistic_regression":
            from sklearn.linear_model import LogisticRegression
            model = LogisticRegression(random_state=random_seed)
        elif algorithm == "svm":
            from sklearn.svm import SVC
            model = SVC(random_state=random_seed)
        elif algorithm == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(random_state=random_seed)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Train model
        model.fit(X_train, y_train)

        # Evaluate model
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # Save model
        model_dir = Path(__file__).parent.parent.parent / "models"
        model_dir.mkdir(exist_ok=True)
        model_path = model_dir / f"{model_name}.joblib"
        joblib.dump(model, model_path)

        # Return original dataframe unchanged (this operation doesn't create columns)
        # But we could add metadata about the trained model
        print(f"Model '{model_name}' trained with accuracy: {accuracy:.3f}")
        print(f"Model saved to: {model_path}")

        return df  # Return unchanged dataframe

    # ============================================================================
    # AUDIT TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def audit_benford_law(self, df: pl.DataFrame, column: str, output_col: str, threshold: float = 0.1) -> pl.DataFrame:
        """Benford's Law analysis"""
        first_digit = df[column].cast(pl.Utf8).str.slice(0, 1)

        benford_expected = {
            '1': 0.301, '2': 0.176, '3': 0.125, '4': 0.097, '5': 0.079,
            '6': 0.067, '7': 0.058, '8': 0.051, '9': 0.046
        }

        total = len(df)
        digit_counts = first_digit.value_counts().to_dict()

        def calc_deviation(val):
            if val is None or str(val) == '0':
                return 0
            first = str(val)[0]
            expected = benford_expected.get(first, 0.05)
            actual = digit_counts.get(first, 0) / total if first in digit_counts else 0
            return abs(expected - actual)

        return df.with_columns(
            pl.col(column).map_elements(calc_deviation, return_dtype=pl.Float64).alias(output_col)
        )

    # ============================================================================
    # AI TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def ai_explain_column(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """AI explanation - placeholder"""
        return df.with_columns(
            pl.lit(f"AI analysis of {column}").alias(output_col)
        )

    def ai_sentiment_analysis(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Sentiment analysis - simplified"""
        positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'best', 'happy']
        negative_words = ['bad', 'poor', 'terrible', 'awful', 'hate', 'worst', 'sad']

        def simple_sentiment(text):
            if text is None:
                return 0.0
            text_lower = str(text).lower()
            pos_count = sum(1 for w in positive_words if w in text_lower)
            neg_count = sum(1 for w in negative_words if w in text_lower)
            return (pos_count - neg_count) / max(pos_count + neg_count, 1)

        return df.with_columns(
            pl.col(column).map_elements(simple_sentiment, return_dtype=pl.Float64).alias(output_col)
        )

    def ai_entity_extraction(self, df: pl.DataFrame, column: str, output_col: str, entity_type: str = 'email') -> pl.DataFrame:
        """Entity extraction - placeholder"""
        patterns = {
            'email': r'[\w\.-]+@[\w\.-]+',
            'phone': r'\d{3}-\d{3}-\d{4}|\d{10}',
            'date': r'\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}',
            'money': r'\$[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP)'
        }
        pattern = patterns.get(entity_type, r'.+')
        return df.with_columns(
            pl.col(column).str.extract_all(pattern).list.join(", ").alias(output_col)
        )

    def ai_pattern_learning(self, df: pl.DataFrame, column: str, output_col: str, pattern: str = None) -> pl.DataFrame:
        """Pattern learning (flash fill) - placeholder"""
        return df.with_columns(pl.col(column).alias(output_col))

    # ============================================================================
    # COLUMN OPERATION IMPLEMENTATIONS
    # ============================================================================

    def rename_col(self, df: pl.DataFrame, column: str, new_name: str) -> pl.DataFrame:
        """Rename column"""
        return df.rename({column: new_name})

    def change_data_type(self, df: pl.DataFrame, column: str, new_type: str) -> pl.DataFrame:
        """Change column data type"""
        type_map = {
            'Int64': pl.Int64, 'Float64': pl.Float64, 'Utf8': pl.Utf8,
            'Boolean': pl.Boolean, 'Date': pl.Date, 'Datetime': pl.Datetime
        }
        if new_type not in type_map:
            raise ValueError(f"Unsupported type: {new_type}")
        return df.with_columns(pl.col(column).cast(type_map[new_type], strict=False))

    def duplicate_column(self, df: pl.DataFrame, column: str, new_name: str = None) -> pl.DataFrame:
        """Duplicate column"""
        target = new_name or f"{column}_copy"
        return df.with_columns(pl.col(column).alias(target))

    def delete_column(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Delete column"""
        return df.drop(column)

    # ============================================================================
    # SPLIT OPERATION IMPLEMENTATIONS
    # ============================================================================

    def split_column(self, df: pl.DataFrame, column: str, output_cols: List[str], delimiter: str = ',') -> pl.DataFrame:
        """Split column by delimiter"""
        return df.with_columns(
            pl.col(column).str.split(delimiter).list.to_struct(
                fields=output_cols
            )
        ).unnest(column)

    # ============================================================================
    # PIVOT/UNPIVOT IMPLEMENTATIONS
    # ============================================================================

    def pivot(self, df: pl.DataFrame, index: List[str], columns: str, values: str, aggregate: str = 'first') -> pl.DataFrame:
        """Create pivot table"""
        agg_map = {
            'sum': 'sum', 'mean': 'mean', 'min': 'min', 'max': 'max',
            'count': 'count', 'first': 'first', 'last': 'last'
        }
        agg_func = agg_map.get(aggregate, 'first')
        return df.pivot(values=values, index=index, columns=columns, aggregate_function=agg_func)

    def unpivot(self, df: pl.DataFrame, id_vars: List[str], value_vars: List[str] = None, var_name: str = "variable", value_name: str = "value") -> pl.DataFrame:
        """Unpivot (melt) a DataFrame."""
        if value_vars is None:
            value_vars = [c for c in df.columns if c not in id_vars]
        return df.melt(id_vars=id_vars, value_vars=value_vars, variable_name=var_name, value_name=value_name)

    # ============================================================================
    # FILTER/SORT IMPLEMENTATIONS
    # ============================================================================

    def filter_rows(self, df: pl.DataFrame, column: str, operator: str, value: Any) -> pl.DataFrame:
        """Filter rows based on column value"""
        if operator == '==':
            return df.filter(pl.col(column) == value)
        elif operator == '!=':
            return df.filter(pl.col(column) != value)
        elif operator == '>':
            return df.filter(pl.col(column) > value)
        elif operator == '>=':
            return df.filter(pl.col(column) >= value)
        elif operator == '<':
            return df.filter(pl.col(column) < value)
        elif operator == '<=':
            return df.filter(pl.col(column) <= value)
        elif operator == 'contains':
            return df.filter(pl.col(column).str.contains(str(value)))
        elif operator == 'starts_with':
            return df.filter(pl.col(column).str.starts_with(str(value)))
        elif operator == 'ends_with':
            return df.filter(pl.col(column).str.ends_with(str(value)))
        elif operator == 'is_null':
            return df.filter(pl.col(column).is_null())
        elif operator == 'is_not_null':
            return df.filter(pl.col(column).is_not_null())
        elif operator == 'in':
            return df.filter(pl.col(column).is_in(value))
        else:
            raise ValueError(f"Unsupported operator: {operator}")

    def sort_rows(self, df: pl.DataFrame, column: str, ascending: bool = True) -> pl.DataFrame:
        """Sort rows by column"""
        return df.sort(column, descending=not ascending)


class TransformationStep:
    """Represents a single transformation step in the pipeline."""

    def __init__(self, operation_id: str, params: Dict[str, Any], step_number: int):
        self.operation_id = operation_id
        self.params = params
        self.step_number = step_number
        self.created_columns: List[str] = []
        self.timestamp = datetime.now()


class TransformationPipeline:
    """
    Manages a sequence of transformation steps to be applied to a DataFrame.
    This is a stateful object that holds the original data and the list of steps.
    Tracks created columns and maintains intermediate datasets for inspection.
    """

    def __init__(self, initial_df: pl.DataFrame):
        self.original_df = initial_df
        self.steps: List[TransformationStep] = []
        self._data_processor = DataProcessor()
        self._cache: Dict[int, pl.DataFrame] = {0: initial_df}
        self._column_tracking: Dict[str, Dict] = {}  # column_name -> {'created_by_step': int, 'operation': str}

    def add_step(self, operation_id: str, params: Dict[str, Any]) -> List[str]:
        """
        Adds a new transformation step to the pipeline.

        Args:
            operation_id: The ID of the operation to perform.
            params: The parameters for the operation.

        Returns:
            List of column names created by this step.
        """
        if operation_id not in OPERATION_REGISTRY:
            raise ValueError(f"Operation '{operation_id}' not found in the registry.")

        step_number = len(self.steps) + 1
        step = TransformationStep(operation_id, params, step_number)
        self.steps.append(step)

        # Apply the operation to detect created columns
        current_df = self.apply(to_step=step_number)
        created_columns = self._detect_created_columns(step_number - 1, step_number)

        # Update step with created columns
        step.created_columns = created_columns

        # Track column creation
        for col in created_columns:
            self._column_tracking[col] = {
                'created_by_step': step_number,
                'operation': operation_id,
                'params': params.copy()
            }

        # Clear cache from this point forward
        self._cache = {k: v for k, v in self._cache.items() if k <= step_number}

        return created_columns

    def _detect_created_columns(self, from_step: int, to_step: int) -> List[str]:
        """
        Detect which columns were created between two pipeline steps.

        Args:
            from_step: The step number before the operation (0-based).
            to_step: The step number after the operation (0-based).

        Returns:
            List of newly created column names.
        """
        df_before = self.apply(to_step=from_step)
        df_after = self.apply(to_step=to_step)

        columns_before = set(df_before.columns)
        columns_after = set(df_after.columns)

        return list(columns_after - columns_before)

    def apply(self, to_step: Optional[int] = None) -> pl.DataFrame:
        """
        Applies the transformations in the pipeline sequentially.

        Args:
            to_step: If specified, applies transformations up to and including
                      this step number (1-based). If None, applies all steps.

        Returns:
            The transformed Polars DataFrame.
        """
        target_step_idx = len(self.steps) if to_step is None else to_step

        if target_step_idx in self._cache:
            return self._cache[target_step_idx]

        # Find the latest cached step before the target
        start_step_idx = max([k for k in self._cache.keys() if k < target_step_idx], default=0)
        current_df = self._cache[start_step_idx]

        # Apply steps from the cached point up to the target
        for i in range(start_step_idx, target_step_idx):
            step = self.steps[i]
            current_df = self._data_processor.apply_operation(
                current_df,
                step.operation_id,
                step.params
            )
            # Cache the result of this step
            self._cache[i + 1] = current_df

        return current_df

    def get_steps(self) -> List[TransformationStep]:
        """Returns the list of applied steps."""
        return self.steps

    def get_dataframe_at_step(self, step_num: int) -> pl.DataFrame:
        """
        Returns the state of the DataFrame at a specific step in the pipeline.

        Args:
            step_num: The step number (0 for original data, 1 for after first step, etc.).

        Returns:
            The DataFrame at the specified step.
        """
        if step_num < 0 or step_num > len(self.steps):
            raise IndexError("Step number is out of range.")

        return self.apply(to_step=step_num)

    def get_column_info(self, column_name: str) -> Optional[Dict]:
        """
        Get information about when and how a column was created.

        Args:
            column_name: Name of the column to query.

        Returns:
            Dictionary with creation info or None if column is original.
        """
        return self._column_tracking.get(column_name)

    def get_created_columns_at_step(self, step_num: int) -> List[str]:
        """
        Get the list of columns created at a specific step.

        Args:
            step_num: The step number (1-based).

        Returns:
            List of column names created at that step.
        """
        if 1 <= step_num <= len(self.steps):
            return self.steps[step_num - 1].created_columns
        return []

    def get_all_created_columns(self) -> Dict[int, List[str]]:
        """
        Get all columns created in the pipeline, organized by step.

        Returns:
            Dictionary mapping step numbers to lists of created column names.
        """
        return {step.step_number: step.created_columns for step in self.steps}

    def remove_last_step(self):
        """Removes the last transformation step."""
        if self.steps:
            removed_step = self.steps.pop()
            # Remove column tracking for columns created by this step
            for col in removed_step.created_columns:
                self._column_tracking.pop(col, None)
            # Clear cache from this point forward
            self._cache = {k: v for k, v in self._cache.items() if k <= len(self.steps)}

    def clear_steps(self):
        """Removes all transformation steps."""
        self.steps.clear()
        self._column_tracking.clear()
        self._cache = {0: self.original_df}


# ============================================================================
# LEGACY DATA PROCESSOR - All transformation methods
# ============================================================================

class LegacyDataProcessor:
    """Process and transform data using Polars for high performance"""

    def __init__(self, data_dir: str = None):
        """Initialize data processor with data directory"""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    # =========================================================================
    # FILE I/O METHODS
    # =========================================================================

    def read_file(self, file_path: str, sheet_name: str = None) -> pl.DataFrame:
        """Read various file formats using Polars"""
        file_path = Path(file_path)
        file_extension = file_path.suffix.lower()

        if file_extension == '.csv':
            return pl.read_csv(file_path)
        elif file_extension in ['.xlsx', '.xls']:
            try:
                if sheet_name:
                    return pl.read_excel(file_path, sheet_name=sheet_name)
                else:
                    return pl.read_excel(file_path)
            except Exception:
                import pandas as pd
                if sheet_name:
                    df_pandas = pd.read_excel(file_path, sheet_name=sheet_name)
                else:
                    df_pandas = pd.read_excel(file_path)
                return pl.from_pandas(df_pandas)
        elif file_extension == '.json':
            return pl.read_json(file_path)
        elif file_extension == '.parquet':
            return pl.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

    def get_excel_sheets(self, file_path: str) -> List[str]:
        """Get list of available sheets in Excel file"""
        try:
            import pandas as pd
            excel_file = pd.ExcelFile(file_path)
            return excel_file.sheet_names
        except Exception as e:
            raise ValueError(f"Error reading Excel file: {str(e)}")

    def save_dataset(self, df: pl.DataFrame, filename: str, format: str = 'parquet') -> str:
        """Save dataset to file"""
        file_path = self.data_dir / f"{filename}.{format}"

        if format == 'parquet':
            df.write_parquet(str(file_path))
        elif format == 'csv':
            df.write_csv(str(file_path))
        elif format == 'xlsx':
            import pandas as pd
            df_pandas = df.to_pandas()
            df_pandas.to_excel(str(file_path), index=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        return str(file_path)

    # =========================================================================
    # DATA PROFILING
    # =========================================================================

    def profile_data(self, df: pl.DataFrame) -> List[Dict[str, Any]]:
        """Generate comprehensive data profile for each column"""
        profiles = []

        for column in df.columns:
            col_data = df[column]

            profile = {
                'column_name': column,
                'data_type': str(col_data.dtype),
                'null_count': col_data.null_count(),
                'unique_count': col_data.n_unique(),
                'min_value': None,
                'max_value': None,
                'mean_value': None,
                'std_dev': None
            }

            # Calculate numeric statistics if applicable
            if col_data.dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32, pl.Int16, pl.Int8, pl.UInt64, pl.UInt32, pl.UInt16, pl.UInt8]:
                try:
                    profile['min_value'] = col_data.min()
                    profile['max_value'] = col_data.max()
                    profile['mean_value'] = col_data.mean()
                    profile['std_dev'] = col_data.std()
                except Exception:
                    pass

            profiles.append(profile)

        return profiles

    # =========================================================================
    # TEXT TRANSFORMATIONS
    # =========================================================================

    def text_uppercase(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Convert text to uppercase"""
        return df.with_columns(pl.col(column).str.to_uppercase().alias(f"{column}_upper"))

    def text_lowercase(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Convert text to lowercase"""
        return df.with_columns(pl.col(column).str.to_lowercase().alias(f"{column}_lower"))

    def text_titlecase(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Convert text to title case"""
        return df.with_columns(pl.col(column).str.to_titlecase().alias(f"{column}_title"))

    def text_trim(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Remove leading/trailing whitespace"""
        return df.with_columns(pl.col(column).str.strip_chars().alias(f"{column}_trimmed"))

    def text_extract_numbers(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract numbers from text"""
        return df.with_columns(
            pl.col(column).str.extract_all(r"\d+").list.join("").alias(f"{column}_numbers")
        )

    def text_extract_text(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract alphabetic text"""
        return df.with_columns(
            pl.col(column).str.replace(r"\d+", "", literal=False).str.strip().alias(f"{column}_text")
        )

    def text_reverse(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Reverse text string"""
        return df.with_columns(
            pl.col(column).str.reverse().alias(f"{column}_reversed")
        )

    def text_length(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Get text length"""
        return df.with_columns(pl.col(column).str.len_bytes().alias(f"{column}_length"))

    def text_hash_md5(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Create MD5 hash"""
        return df.with_columns(
            pl.col(column).map_elements(
                lambda x: hashlib.md5(str(x).encode()).hexdigest() if x is not None else None,
                return_dtype=pl.Utf8
            ).alias(f"{column}_md5")
        )

    def text_soundex(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Create Soundex code"""
        def soundex(word):
            if not word:
                return "0000"
            word = word.upper()[:4]
            mapping = {"BFPV": "1", "CGJKQSXZ": "2", "DT": "3", "L": "4", "MN": "5", "R": "6"}
            result = [word[0]]
            prev = ""
            for char in word[1:]:
                for letters, code in mapping.items():
                    if char in letters and code != prev:
                        result.append(code)
                        prev = code
                        break
            return (''.join(result) + "000")[:4]

        return df.with_columns(
            pl.col(column).map_elements(soundex, return_dtype=pl.Utf8).alias(f"{column}_soundex")
        )

    # =========================================================================
    # MATH TRANSFORMATIONS
    # =========================================================================

    def math_round(self, df: pl.DataFrame, column: str, decimals: int = 2) -> pl.DataFrame:
        """Round numbers"""
        return df.with_columns(pl.col(column).round(decimals).alias(f"{column}_rounded"))

    def math_ceil(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Ceiling (round up)"""
        return df.with_columns(pl.col(column).ceil().alias(f"{column}_ceil"))

    def math_floor(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Floor (round down)"""
        return df.with_columns(pl.col(column).floor().alias(f"{column}_floor"))

    def math_abs(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Absolute value"""
        return df.with_columns(pl.col(column).abs().alias(f"{column}_abs"))

    def math_sqrt(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Square root"""
        return df.with_columns((pl.col(column) ** 0.5).alias(f"{column}_sqrt"))

    def math_square(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Square"""
        return df.with_columns((pl.col(column) ** 2).alias(f"{column}_sq"))

    def math_log(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Natural logarithm"""
        return df.with_columns(pl.col(column).log().alias(f"{column}_log"))

    def math_log10(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Base-10 logarithm"""
        return df.with_columns(pl.col(column).log10().alias(f"{column}_log10"))

    def math_exp(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Exponential (e^x)"""
        return df.with_columns(pl.col(column).exp().alias(f"{column}_exp"))

    # =========================================================================
    # TRIGONOMETRIC TRANSFORMATIONS
    # =========================================================================

    def trig_sin(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Sine (radians)"""
        return df.with_columns(pl.col(column).sin().alias(f"{column}_sin"))

    def trig_cos(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Cosine (radians)"""
        return df.with_columns(pl.col(column).cos().alias(f"{column}_cos"))

    def trig_tan(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Tangent (radians)"""
        return df.with_columns(pl.col(column).tan().alias(f"{column}_tan"))

    def trig_asin(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Arc sine (radians)"""
        return df.with_columns(pl.col(column).arcsin().alias(f"{column}_asin"))

    def trig_acos(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Arc cosine (radians)"""
        return df.with_columns(pl.col(column).arccos().alias(f"{column}_acos"))

    def trig_atan(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Arc tangent (radians)"""
        return df.with_columns(pl.col(column).arctan().alias(f"{column}_atan"))

    # =========================================================================
    # DATE/TIME TRANSFORMATIONS
    # =========================================================================

    def datetime_year(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract year"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.year()
        else:
            col = col.dt.year()
        return df.with_columns(col.alias(f"{column}_year"))

    def datetime_month(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract month (1-12)"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.month()
        else:
            col = col.dt.month()
        return df.with_columns(col.alias(f"{column}_month"))

    def datetime_day(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract day of month"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.day()
        else:
            col = col.dt.day()
        return df.with_columns(col.alias(f"{column}_day"))

    def datetime_hour(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract hour"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.hour()
        else:
            col = col.dt.hour()
        return df.with_columns(col.alias(f"{column}_hour"))

    def datetime_minute(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract minute"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.minute()
        else:
            col = col.dt.minute()
        return df.with_columns(col.alias(f"{column}_minute"))

    def datetime_second(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract second"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.second()
        else:
            col = col.dt.second()
        return df.with_columns(col.alias(f"{column}_second"))

    def datetime_weekday(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract weekday (0=Monday, 6=Sunday)"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.weekday()
        else:
            col = col.dt.weekday()
        return df.with_columns(col.alias(f"{column}_weekday"))

    def datetime_quarter(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract quarter (1-4)"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.quarter()
        else:
            col = col.dt.quarter()
        return df.with_columns(col.alias(f"{column}_quarter"))

    def datetime_age_days(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate age in days from today"""
        today = datetime.now()
        if df[column].dtype == pl.Utf8:
            dates = df[column].str.to_datetime()
        else:
            dates = df[column]
        return df.with_columns(
            (pl.lit(today).cast(pl.Datetime()) - dates.cast(pl.Datetime())).dt.days().abs().alias(f"{column}_age_days")
        )

    def datetime_age_years(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate age in years from today"""
        days = self.datetime_age_days(df, column)[f"{column}_age_days"]
        return df.with_columns((days / 365.25).cast(pl.Int64).alias(f"{column}_age_years"))

    def datetime_is_weekend(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Check if date is weekend"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            weekday = col.str.to_datetime().dt.weekday()
        else:
            weekday = col.dt.weekday()
        return df.with_columns(((weekday == 6) | (weekday == 7)).alias(f"{column}_is_weekend"))

    def datetime_is_leap_year(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Check if year is leap year"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            year = col.str.to_datetime().dt.year()
        else:
            year = col.dt.year()
        return df.with_columns(((year % 4 == 0) & ((year % 100 != 0) | (year % 400 == 0))).alias(f"{column}_is_leap_year"))

    def datetime_days_in_month(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Get days in month"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            dates = col.str.to_datetime()
        else:
            dates = col
        return df.with_columns(
            pl.when(dates.dt.month().is_in([1, 3, 5, 7, 8, 10, 12]))
            .then(31)
            .when(dates.dt.month().is_in([4, 6, 9, 11]))
            .then(30)
            .when(dates.dt.month() == 2)
            .then(pl.when((dates.dt.year() % 4 == 0) & ((dates.dt.year() % 100 != 0) | (dates.dt.year() % 400 == 0))).then(29).otherwise(28))
            .otherwise(0)
            .alias(f"{column}_days_in_month")
        )

    # =========================================================================
    # STATISTICAL TRANSFORMATIONS
    # =========================================================================

    def stat_zscore(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate z-score"""
        col = pl.col(column)
        mean = df[column].mean()
        std = df[column].std()
        if std == 0:
            std = 1
        return df.with_columns(((col - mean) / std).alias(f"{column}_zscore"))

    def stat_percent_rank(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate percent rank"""
        return df.with_columns(pl.col(column).rank("average", pct=True).alias(f"{column}_pct_rank"))

    def stat_rank(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate rank"""
        return df.with_columns(pl.col(column).rank("average").alias(f"{column}_rank"))

    # =========================================================================
    # COLUMN OPERATIONS
    # =========================================================================

    def rename_column(self, df: pl.DataFrame, old_name: str, new_name: str) -> pl.DataFrame:
        """Rename column"""
        return df.rename({old_name: new_name})

    def change_dtype(self, df: pl.DataFrame, column: str, new_dtype: str) -> pl.DataFrame:
        """Change column data type"""
        type_map = {
            'Int64': pl.Int64, 'Float64': pl.Float64, 'Utf8': pl.Utf8,
            'Boolean': pl.Boolean, 'Date': pl.Date, 'Datetime': pl.Datetime
        }
        if new_dtype not in type_map:
            raise ValueError(f"Unsupported type: {new_dtype}")
        return df.with_columns(pl.col(column).cast(type_map[new_dtype], strict=False))

    # =========================================================================
    # SPLIT OPERATIONS
    # =========================================================================

    def split_text(self, df: pl.DataFrame, column: str, delimiter: str) -> pl.DataFrame:
        """Split text by delimiter"""
        return df.with_columns(
            pl.col(column).str.split(delimiter).list.to_struct(
                fields=[f"{column}_part{i}" for i in range(2)]
            )
        ).unnest(column)

    # =========================================================================
    # PIVOT/UNPIVOT OPERATIONS
    # =========================================================================

    def pivot_table(self, df: pl.DataFrame, index: str, columns: str, values: str, aggregate: str = 'sum') -> pl.DataFrame:
        """Create pivot table"""
        agg_map = {
            'sum': 'sum', 'mean': 'mean', 'min': 'min', 'max': 'max', 'count': 'count', 'first': 'first', 'last': 'last'
        }
        agg_func = agg_map.get(aggregate, 'first')
        return df.pivot(values=values, index=index, columns=columns, aggregate_function=agg_func)

    def unpivot_table(self, df: pl.DataFrame, id_vars: List[str], value_vars: List[str] = None, var_name: str = "variable", value_name: str = "value") -> pl.DataFrame:
        """Unpivot/melt table"""
        if value_vars is None:
            value_vars = [c for c in df.columns if c not in id_vars]
        return df.melt(id_vars=id_vars, value_vars=value_vars, variable_name=var_name, value_name=value_name)

    # =========================================================================
    # ML OPERATIONS (Simplified implementations)
    # =========================================================================

    def ml_anomaly_iforest(self, df: pl.DataFrame, column: str, contamination: float = 0.1) -> pl.DataFrame:
        """Anomaly detection using Isolation Forest - simplified"""
        col_data = df[column].to_numpy().reshape(-1, 1)
        mean_val = np.mean(col_data)
        std_val = np.std(col_data)
        if std_val == 0:
            std_val = 1

        # Simplified anomaly detection based on distance from mean
        distances = np.abs(col_data - mean_val) / std_val
        threshold = 2.5  # Simplified threshold
        is_anomaly = distances > threshold
        scores = 1 - (1 / (1 + distances))  # Higher = more anomalous

        return df.with_columns([
            pl.Series(name=f"{column}_is_anomaly", values=is_anomaly),
            pl.Series(name=f"{column}_anomaly_score", values=scores.flatten())
        ])

    def ml_anomaly_zscore(self, df: pl.DataFrame, column: str, threshold: float = 3.0) -> pl.DataFrame:
        """Anomaly detection using Z-score"""
        col = pl.col(column)
        mean = df[column].mean()
        std = df[column].std()
        if std == 0:
            std = 1
        zscore = (col - mean) / std
        return df.with_columns([
            zscore.alias(f"{column}_zscore"),
            (zscore.abs() > threshold).alias(f"{column}_is_outlier")
        ])

    def ml_anomaly_iqr(self, df: pl.DataFrame, column: str, multiplier: float = 1.5) -> pl.DataFrame:
        """Anomaly detection using IQR"""
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - multiplier * IQR
        upper_bound = Q3 + multiplier * IQR
        return df.with_columns([
            (pl.col(column) < lower_bound).alias(f"{column}_is_outlier"),
            (pl.col(column) - (Q3 + Q1) / 2).abs().alias(f"{column}_iqr_distance")
        ])

    def ml_anomaly_lof(self, df: pl.DataFrame, column: str, n_neighbors: int = 20) -> pl.DataFrame:
        """Local Outlier Factor - simplified"""
        col_data = df[column].to_numpy()
        mean_val = np.mean(col_data)
        distances = np.abs(col_data - mean_val)
        max_dist = np.max(distances)
        if max_dist == 0:
            max_dist = 1
        # Simplified LOF-like score
        scores = 1 - (distances / max_dist)
        threshold = 0.3
        is_outlier = scores < threshold
        return df.with_columns([
            pl.Series(name=f"{column}_is_outlier", values=is_outlier),
            pl.Series(name=f"{column}_lof_score", values=scores)
        ])

    def ml_outlier(self, df: pl.DataFrame, column: str, method: str = 'iqr') -> pl.DataFrame:
        """General outlier detection"""
        if method == 'zscore':
            return self.ml_anomaly_zscore(df, column)
        else:
            return self.ml_anomaly_iqr(df, column)

    def ml_cluster(self, df: pl.DataFrame, columns: List[str], n_clusters: int = 3) -> pl.DataFrame:
        """K-Means clustering - simplified"""
        data = df.select(columns).to_numpy()
        means = np.mean(data, axis=0)
        stds = np.std(data, axis=0)
        if np.any(stds == 0):
            stds[stds == 0] = 1
        normalized = (data - means) / stds

        # Simple k-means simulation using random initial centers
        np.random.seed(42)
        centers = normalized[np.random.choice(len(normalized), n_clusters, replace=False)]

        distances = np.zeros((len(normalized), n_clusters))
        for i in range(n_clusters):
            distances[:, i] = np.linalg.norm(normalized - centers[i], axis=1)
        labels = np.argmin(distances, axis=1)

        return df.with_columns(pl.Series(name="cluster", values=labels))

    def ml_forecast(self, df: pl.DataFrame, column: str, periods: int = 12) -> pl.DataFrame:
        """Simple time series forecast using exponential smoothing"""
        values = df[column].to_numpy()
        if len(values) == 0:
            return df.with_columns(pl.lit(None).alias(f"{column}_forecast"))

        alpha = 0.3
        n = len(values)
        smoothed = np.zeros(n + periods)

        # Calculate smoothed values
        smoothed[0] = values[0]
        for i in range(1, n):
            smoothed[i] = alpha * values[i] + (1 - alpha) * smoothed[i - 1]

        # Extend with last smoothed value (naive forecast)
        for i in range(n, n + periods):
            smoothed[i] = smoothed[i - 1]

        return df.with_columns(
            pl.Series(name=f"{column}_forecast", values=smoothed[:n])
        )

    # =========================================================================
    # AUDIT OPERATIONS
    # =========================================================================

    def audit_benford_law(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Benford's Law analysis"""
        # Get first digit
        first_digit = df[column].cast(pl.Utf8).str.slice(0, 1)

        # Expected Benford distribution
        benford_expected = {
            '1': 0.301, '2': 0.176, '3': 0.125, '4': 0.097, '5': 0.079,
            '6': 0.067, '7': 0.058, '8': 0.051, '9': 0.046
        }

        # Calculate actual distribution
        total = len(df)
        digit_counts = first_digit.value_counts().to_dict()

        # Calculate deviation for each row
        def calc_deviation(val):
            if val is None or str(val) == '0':
                return 0
            first = str(val)[0]
            expected = benford_expected.get(first, 0.05)
            actual = digit_counts.get(first, 0) / total if first in digit_counts else 0
            return abs(expected - actual)

        return df.with_columns([
            pl.col(column).map_elements(calc_deviation, return_dtype=pl.Float64).alias(f"{column}_benford_deviation"),
            pl.col(column).map_elements(
                lambda x: calc_deviation(x) > 0.1,
                return_dtype=pl.Boolean
            ).alias(f"{column}_is_suspicious")
        ])

    # =========================================================================
    # AI OPERATIONS (Simplified placeholders)
    # =========================================================================

    def ai_explain(self, df: pl.DataFrame, column: str, style: str = 'concise') -> pl.DataFrame:
        """AI explanation - placeholder"""
        # In production, this would call OpenAI/Anthropic API
        return df.with_columns(
            pl.lit(f"AI analysis of {column}").alias(f"{column}_ai_explanation")
        )

    def ai_sentiment(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Sentiment analysis - placeholder"""
        # Simplified sentiment based on keywords
        positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'best', 'happy']
        negative_words = ['bad', 'poor', 'terrible', 'awful', 'hate', 'worst', 'sad']

        def simple_sentiment(text):
            if text is None:
                return 0.0, "Neutral"
            text_lower = str(text).lower()
            pos_count = sum(1 for w in positive_words if w in text_lower)
            neg_count = sum(1 for w in negative_words if w in text_lower)
            score = (pos_count - neg_count) / max(pos_count + neg_count, 1)
            if score > 0:
                label = "Positive"
            elif score < 0:
                label = "Negative"
            else:
                label = "Neutral"
            return score, label

        scores = []
        labels = []
        for val in df[column]:
            score, label = simple_sentiment(val)
            scores.append(score)
            labels.append(label)

        return df.with_columns([
            pl.Series(name=f"{column}_sentiment_score", values=scores),
            pl.Series(name=f"{column}_sentiment_label", values=labels)
        ])

    def ai_extract(self, df: pl.DataFrame, column: str, entity_type: str) -> pl.DataFrame:
        """Entity extraction - placeholder"""
        patterns = {
            'email': r'[\w\.-]+@[\w\.-]+',
            'phone': r'\d{3}-\d{3}-\d{4}|\d{10}',
            'date': r'\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}',
            'money': r'\$[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP)'
        }
        pattern = patterns.get(entity_type, r'.+')
        return df.with_columns(
            pl.col(column).str.extract_all(pattern).list.join(", ").alias(f"{column}_extracted")
        )

    def ai_pattern_learn(self, df: pl.DataFrame, column: str, output_column: str) -> pl.DataFrame:
        """Pattern learning (flash fill) - placeholder"""
        # In production, this would learn from examples and apply
        return df.with_columns(pl.col(column).alias(output_column))

    # =========================================================================
    # FILTER OPERATIONS
    # =========================================================================

    def filter_data(self, df: pl.DataFrame, filters: Dict[str, Any]) -> pl.DataFrame:
        """Apply filters to DataFrame"""
        filtered_df = df

        for column, condition in filters.items():
            if column in df.columns:
                if isinstance(condition, dict):
                    if 'min' in condition and 'max' in condition:
                        filtered_df = filtered_df.filter(
                            (pl.col(column) >= condition['min']) &
                            (pl.col(column) <= condition['max'])
                        )
                    elif 'equals' in condition:
                        filtered_df = filtered_df.filter(pl.col(column) == condition['equals'])
                    elif 'contains' in condition:
                        filtered_df = filtered_df.filter(pl.col(column).str.contains(condition['contains']))
                    elif 'in' in condition:
                        filtered_df = filtered_df.filter(pl.col(column).is_in(condition['in']))
                else:
                    filtered_df = filtered_df.filter(pl.col(column) == condition)

        return filtered_df

    # =========================================================================
    # SAMPLE OPERATIONS
    # =========================================================================

    def sample_data(self, df: pl.DataFrame, method: str = "random", size: int = 1000, **kwargs) -> pl.DataFrame:
        """Sample data using various methods"""
        n_rows = len(df)
        if n_rows == 0:
            return df

        if method == "random":
            return df.sample(n=min(size, n_rows))
        elif method == "systematic":
            interval = max(1, n_rows // size)
            return df[::interval].head(size)
        elif method == "top":
            return df.head(size)
        elif method == "bottom":
            return df.tail(size)
        else:
            raise ValueError(f"Unknown sampling method: {method}")

    # =========================================================================
    # LEGACY TRANSFORMATION METHODS
    # =========================================================================

    def lowercase(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Convert text to lowercase"""
        target_col = new_column or f"{column}_lower"
        return df.with_columns(pl.col(column).str.to_lowercase().alias(target_col))

    def trim(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Remove leading/trailing whitespace"""
        target_col = new_column or f"{column}_trimmed"
        return df.with_columns(pl.col(column).str.strip_chars().alias(target_col))

    def capitalize(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Convert to title case"""
        target_col = new_column or f"{column}_title"
        return df.with_columns(pl.col(column).str.to_titlecase().alias(target_col))

    def round_values(self, df: pl.DataFrame, column: str, decimals: int, new_column: str = None) -> pl.DataFrame:
        """Round numeric values"""
        target_col = new_column or f"{column}_rounded"
        return df.with_columns(pl.col(column).round(decimals).alias(target_col))

    def absolute(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Absolute value"""
        target_col = new_column or f"{column}_abs"
        return df.with_columns(pl.col(column).abs().alias(target_col))

    def log_transform(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Log transform"""
        target_col = new_column or f"{column}_log"
        return df.with_columns(pl.col(column).log().alias(target_col))

    def split_column(self, df: pl.DataFrame, column: str, delimiter: str, max_split: int = 0) -> pl.DataFrame:
        """Split column into multiple parts"""
        if max_split > 0:
            fields = [f"{column}_part_{i}" for i in range(max_split + 1)]
        else:
            fields = [f"{column}_part_{i}" for i in range(10)]

        return df.with_columns(
            pl.col(column).str.split(delimiter).list.to_struct(fields=fields)
        ).unnest(column)

    def replace_values(self, df: pl.DataFrame, old_value: Any, new_value: Any) -> pl.DataFrame:
        """Replace values in column"""
        return df.with_columns(
            pl.when(pl.col(column) == old_value)
            .then(new_value)
            .otherwise(pl.col(column))
            .alias(column)
        )

    def cast_column(self, df: pl.DataFrame, column: str, new_type: str) -> pl.DataFrame:
        """Change column data type"""
        type_mapping = {
            'string': pl.Utf8, 'str': pl.Utf8, 'int': pl.Int64,
            'integer': pl.Int64, 'float': pl.Float64, 'double': pl.Float64,
            'bool': pl.Boolean, 'boolean': pl.Boolean, 'date': pl.Date, 'datetime': pl.Datetime,
        }

        if new_type not in type_mapping:
            raise ValueError(f"Unsupported type: {new_type}")

        return df.with_columns(pl.col(column).cast(type_mapping[new_type], strict=False))

    def filter_column(self, df: pl.DataFrame, column: str, operator: str, value: Any) -> pl.DataFrame:
        """Filter rows based on column value"""
        if operator == '==':
            return df.filter(pl.col(column) == value)
        elif operator == '!=':
            return df.filter(pl.col(column) != value)
        elif operator == '>':
            return df.filter(pl.col(column) > value)
        elif operator == '>=':
            return df.filter(pl.col(column) >= value)
        elif operator == '<':
            return df.filter(pl.col(column) < value)
        elif operator == '<=':
            return df.filter(pl.col(column) <= value)
        elif operator == 'contains':
            return df.filter(pl.col(column).str.contains(str(value)))
        elif operator == 'starts_with':
            return df.filter(pl.col(column).str.starts_with(str(value)))
        elif operator == 'ends_with':
            return df.filter(pl.col(column).str.ends_with(str(value)))
        elif operator == 'is_null':
            return df.filter(pl.col(column).is_null())
        elif operator == 'is_not_null':
            return df.filter(pl.col(column).is_not_null())
        elif operator == 'in':
            return df.filter(pl.col(column).is_in(value))
        else:
            raise ValueError(f"Unsupported operator: {operator}")

    def aggregate(self, df: pl.DataFrame, group_by: List[str], aggregations: Dict[str, str]) -> pl.DataFrame:
        """Aggregate data"""
        agg_exprs = []
        for column, agg_func in aggregations.items():
            if agg_func == 'sum':
                agg_exprs.append(pl.col(column).sum())
            elif agg_func == 'mean':
                agg_exprs.append(pl.col(column).mean())
            elif agg_func == 'avg':
                agg_exprs.append(pl.col(column).mean())
            elif agg_func == 'count':
                agg_exprs.append(pl.col(column).count())
            elif agg_func == 'min':
                agg_exprs.append(pl.col(column).min())
            elif agg_func == 'max':
                agg_exprs.append(pl.col(column).max())
            elif agg_func == 'first':
                agg_exprs.append(pl.col(column).first())
            elif agg_func == 'last':
                agg_exprs.append(pl.col(column).last())
            elif agg_func == 'n_unique':
                agg_exprs.append(pl.col(column).n_unique())

        return df.group_by(group_by).agg(aggregations)

    def sort_data(self, df: pl.DataFrame, columns: List[str], descending: List[bool] = None) -> pl.DataFrame:
        """Sort data by columns"""
        if descending is None:
            descending = [False] * len(columns)
        return df.sort(columns, descending=descending)

    def select_columns(self, df: pl.DataFrame, columns: List[str]) -> pl.DataFrame:
        """Select specific columns"""
        return df.select(columns)

    def drop_columns(self, df: pl.DataFrame, columns: List[str]) -> pl.DataFrame:
        """Drop columns"""
        return df.drop(columns)

    def add_column(self, df: pl.DataFrame, column_name: str, expression: str) -> pl.DataFrame:
        """Add a computed column"""
        try:
            expr = eval(expression)
            return df.with_columns(expr.alias(column_name))
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    def join_dataframes(self, df1: pl.DataFrame, df2: pl.DataFrame, on: List[str], how: str = 'inner') -> pl.DataFrame:
        """Join two dataframes"""
        return df1.join(df2, on=on, how=how)

    def pivot_table_legacy(self, df: pl.DataFrame, index: List[str], columns: str, values: str, aggregate: str = 'first') -> pl.DataFrame:
        """Create pivot table"""
        return df.pivot(values=values, index=index, columns=columns, aggregate_function=aggregate)
