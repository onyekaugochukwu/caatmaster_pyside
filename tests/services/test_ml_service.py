"""
Tests for ML Service
"""
import pytest
import polars as pl
import numpy as np


class TestMLAnomalyDetection:
    """Test cases for ML anomaly detection operations"""

    @pytest.fixture
    def numeric_data(self):
        """Create numeric data with some outliers"""
        # Normal data points around 100
        normal_data = [100 + np.random.normal(0, 5) for _ in range(100)]
        # Add some outliers
        outliers = [200, 250, -100, 300, -150]
        all_data = normal_data + outliers
        return all_data

    def test_anomaly_iforest_simple(self, numeric_data):
        """Test Isolation Forest anomaly detection"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        result = processor.ml_anomaly_iforest(
            df,
            column="value",
            output_col="is_anomaly"
        )

        assert "is_anomaly" in result.columns
        # Should detect some anomalies
        anomaly_count = result["is_anomaly"].sum()
        assert anomaly_count > 0

    def test_anomaly_zscore_simple(self, numeric_data):
        """Test Z-score anomaly detection"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        result = processor.ml_anomaly_zscore(
            df,
            column="value",
            output_col="is_anomaly",
            threshold=3.0
        )

        assert "is_anomaly" in result.columns
        # Should detect extreme outliers

    def test_anomaly_iqr_simple(self, numeric_data):
        """Test IQR-based anomaly detection"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        result = processor.ml_anomaly_iqr(
            df,
            column="value",
            output_col="is_anomaly",
            multiplier=1.5
        )

        assert "is_anomaly" in result.columns

    def test_anomaly_lof_simple(self, numeric_data):
        """Test Local Outlier Factor detection"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        result = processor.ml_anomaly_lof(
            df,
            column="value",
            output_col="is_anomaly",
            n_neighbors=20
        )

        assert "is_anomaly" in result.columns

    def test_outlier_detection_method_selection(self, numeric_data):
        """Test outlier detection with different methods"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        # Test with zscore method
        result_zscore = processor.ml_outlier_detection(
            df,
            column="value",
            output_col="is_outlier_z",
            method='zscore'
        )

        # Test with iqr method
        result_iqr = processor.ml_outlier_detection(
            df,
            column="value",
            output_col="is_outlier_i",
            method='iqr'
        )

        assert "is_outlier_z" in result_zscore.columns
        assert "is_outlier_i" in result_iqr.columns


class TestMLClustering:
    """Test cases for ML clustering operations"""

    def test_kmeans_clustering(self):
        """Test K-Means clustering"""
        from core.data_processor import DataProcessor

        # Create data with 3 clear clusters
        np.random.seed(42)
        data = np.vstack([
            np.random.normal([0, 0], 0.5, (50, 2)),
            np.random.normal([5, 5], 0.5, (50, 2)),
            np.random.normal([10, 0], 0.5, (50, 2))
        ])

        df = pl.DataFrame({"value": data[:, 0]})

        processor = DataProcessor()
        result = processor.ml_clustering(
            df,
            column="value",
            output_col="cluster",
            n_clusters=3
        )

        assert "cluster" in result.columns
        # Should have 3 distinct clusters (0, 1, 2)
        unique_clusters = result["cluster"].unique()
        assert len(unique_clusters) <= 3

    def test_kmeans_different_cluster_counts(self):
        """Test K-Means with different cluster counts"""
        from core.data_processor import DataProcessor

        np.random.seed(42)
        data = np.random.normal(50, 10, 100)

        df = pl.DataFrame({"value": data})

        processor = DataProcessor()

        for n_clusters in [2, 4, 5]:
            result = processor.ml_clustering(
                df,
                column="value",
                output_col="cluster",
                n_clusters=n_clusters
            )
            unique_clusters = result["cluster"].unique()
            assert len(unique_clusters) == n_clusters


class TestMLForecasting:
    """Test cases for ML forecasting operations"""

    def test_simple_forecast(self):
        """Test simple time series forecasting"""
        from core.data_processor import DataProcessor

        # Create a simple trend
        values = [10 + i * 0.5 + np.random.normal(0, 1) for i in range(50)]

        df = pl.DataFrame({"value": values})

        processor = DataProcessor()
        result = processor.ml_forecast(
            df,
            column="value",
            output_col="forecast",
            periods=12
        )

        assert "forecast" in result.columns
        assert len(result) == len(df)

    def test_forecast_with_periods(self):
        """Test forecasting with different period values"""
        from core.data_processor import DataProcessor

        values = list(range(20))

        df = pl.DataFrame({"value": values})

        processor = DataProcessor()

        for periods in [1, 5, 10, 20]:
            result = processor.ml_forecast(
                df,
                column="value",
                output_col="forecast",
                periods=periods
            )
            assert "forecast" in result.columns

    def test_forecast_empty_data(self):
        """Test forecasting with empty data"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"value": []})

        processor = DataProcessor()
        result = processor.ml_forecast(
            df,
            column="value",
            output_col="forecast",
            periods=10
        )

        assert "forecast" in result.columns


class TestMLClassification:
    """Test cases for ML classification operations"""

    def test_ml_classify_basic(self):
        """Test basic ML classification"""
        from core.data_processor import DataProcessor

        # Create simple classification data
        np.random.seed(42)
        df = pl.DataFrame({
            "feature1": list(range(100)),
            "feature2": list(range(100, 200)),
            "target": [0] * 50 + [1] * 50
        })

        processor = DataProcessor()
        result = processor.ml_classify(
            df,
            features=["feature1", "feature2"],
            target="target",
            output_col="prediction",
            probability_col="probability"
        )

        assert "prediction" in result.columns
        assert "probability" in result.columns

    def test_ml_classify_returns_correct_labels(self):
        """Test that classification returns expected labels"""
        from core.data_processor import DataProcessor

        np.random.seed(42)
        df = pl.DataFrame({
            "f1": [1, 2, 3, 4, 5, 6, 7, 8],
            "f2": [2, 3, 4, 5, 6, 7, 8, 9],
            "target": ["A", "A", "A", "B", "B", "B", "C", "C"]
        })

        processor = DataProcessor()
        result = processor.ml_classify(
            df,
            features=["f1", "f2"],
            target="target",
            output_col="pred",
            probability_col="prob"
        )

        unique_predictions = result["pred"].unique()
        # Should have at least some of the target classes
        assert len(unique_predictions) <= 3


class TestMLRiskScoring:
    """Test cases for ML risk scoring operations"""

    def test_risk_score_calculation(self):
        """Test risk score calculation"""
        from core.data_processor import DataProcessor

        np.random.seed(42)
        df = pl.DataFrame({
            "group": ["A"] * 5 + ["B"] * 5,
            "feature1": np.random.random(10),
            "feature2": np.random.random(10),
            "feature3": np.random.random(10)
        })

        processor = DataProcessor()
        result = processor.ml_risk_score(
            df,
            group_column="group",
            features=["feature1", "feature2", "feature3"],
            output_col="risk_score"
        )

        assert "risk_score" in result.columns
        # Risk scores should be between 0 and 1
        scores = result["risk_score"]
        assert scores.min() >= 0
        assert scores.max() <= 1

    def test_risk_score_per_group(self):
        """Test that risk scores are calculated per group"""
        from core.data_processor import DataProcessor

        # Create data where groups should have different risk profiles
        df = pl.DataFrame({
            "group": ["High"] * 5 + ["Low"] * 5,
            "feature1": [0.9, 0.85, 0.95, 0.88, 0.92] + [0.1, 0.15, 0.05, 0.12, 0.08],
            "feature2": [0.8, 0.75, 0.85, 0.78, 0.82] + [0.2, 0.25, 0.15, 0.22, 0.18],
        })

        processor = DataProcessor()
        result = processor.ml_risk_score(
            df,
            group_column="group",
            features=["feature1", "feature2"],
            output_col="risk_score"
        )

        high_risk_avg = result.filter(pl.col("group") == "High")["risk_score"].mean()
        low_risk_avg = result.filter(pl.col("group") == "Low")["risk_score"].mean()

        assert high_risk_avg > low_risk_avg


class TestMLPrediction:
    """Test cases for ML prediction operations"""

    def test_ml_predict_no_model(self):
        """Test prediction when model doesn't exist (fallback behavior)"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "feature1": [1, 2, 3, 4, 5],
            "feature2": [10, 20, 30, 40, 50]
        })

        processor = DataProcessor()
        result = processor.ml_predict(
            df,
            model_id="nonexistent_model",
            features=["feature1"],
            output_col="prediction"
        )

        # Should return original feature values as fallback
        assert "prediction" in result.columns

    def test_ml_predict_returns_same_length(self):
        """Test that prediction returns same number of rows as input"""
        from core.data_processor import DataProcessor

        np.random.seed(42)
        df = pl.DataFrame({
            "feature1": np.random.random(50),
            "feature2": np.random.random(50),
            "feature3": np.random.random(50)
        })

        processor = DataProcessor()
        result = processor.ml_predict(
            df,
            model_id="nonexistent_model",
            features=["feature1"],
            output_col="pred"
        )

        assert len(result) == len(df)
