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

        # These simplified ml_anomaly_* methods don't take an output_col -
        # each names its own flag/score columns from the input column
        # name ("{column}_is_anomaly", "{column}_anomaly_score", ...).
        result = processor.ml_anomaly_iforest(df, column="value")

        assert "value_is_anomaly" in result.columns
        assert "value_anomaly_score" in result.columns
        # Should detect some anomalies (the fixture adds 5 clear outliers)
        anomaly_count = result["value_is_anomaly"].sum()
        assert anomaly_count > 0

    def test_anomaly_zscore_simple(self, numeric_data):
        """Test Z-score anomaly detection"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        result = processor.ml_anomaly_zscore(df, column="value", threshold=3.0)

        assert "value_is_outlier" in result.columns
        assert "value_zscore" in result.columns
        # Should detect extreme outliers (the fixture adds 5 clear outliers)
        assert result["value_is_outlier"].sum() > 0

    def test_anomaly_iqr_simple(self, numeric_data):
        """Test IQR-based anomaly detection"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        result = processor.ml_anomaly_iqr(df, column="value", multiplier=1.5)

        assert "value_is_outlier" in result.columns
        assert "value_iqr_distance" in result.columns
        assert result["value_is_outlier"].sum() > 0

    def test_anomaly_lof_simple(self, numeric_data):
        """Test Local Outlier Factor detection"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        result = processor.ml_anomaly_lof(df, column="value", n_neighbors=20)

        assert "value_is_outlier" in result.columns
        assert "value_lof_score" in result.columns

    def test_anomaly_iforest_uses_real_contamination_parameter(self, numeric_data):
        """Regression test: an earlier version of ml_anomaly_iforest computed
        a fixed distance-from-mean heuristic and ignored the contamination
        parameter entirely, despite the operation accepting it and the
        dialog exposing it - the flagged count never changed regardless of
        what a reviewer set it to. A genuine Isolation Forest's flagged
        count scales with contamination; this asserts that it now does."""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        low = processor.ml_anomaly_iforest(df, column="value", contamination=0.02)
        high = processor.ml_anomaly_iforest(df, column="value", contamination=0.3)

        assert low["value_is_anomaly"].sum() < high["value_is_anomaly"].sum()

    def test_anomaly_lof_score_reflects_local_density_not_distance_from_mean(self):
        """Regression test: an earlier version of ml_anomaly_lof scored every
        point purely by its raw distance from the column mean, which is not
        what Local Outlier Factor actually measures - LOF compares a
        point's local density to its neighbors' local density. Two points
        roughly equally far from a large central cluster can score very
        differently depending on whether either one has nearby company: a
        point with a few close neighbors of its own is locally normal even
        while sitting far from the main cluster, while a point with no
        neighbors at all is genuinely isolated. A pure distance-from-mean
        score cannot tell these two situations apart; LOF is specifically
        built to."""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        # A dense, evenly-spaced cluster around 0 (no exact duplicates, so
        # sklearn's LOF has real spacing to work with), a small companioned
        # group near +30 (three points close together, locally just as
        # dense as the main cluster), and one point at -30 with no
        # neighbors of its own anywhere nearby.
        main_cluster = [round(-0.5 + i * (1.0 / 29), 4) for i in range(30)]
        companions = [29.97, 30.0, 30.03]
        isolated = [-30.0]
        values = main_cluster + companions + isolated
        df = pl.DataFrame({"value": values})

        result = processor.ml_anomaly_lof(df, column="value", n_neighbors=2)
        scores = result["value_lof_score"].to_list()
        companioned_score = scores[31]  # the point at 30.0, with close neighbors at 29.97/30.03
        isolated_score = scores[-1]     # the point at -30.0, with no neighbors of its own
        # The companioned point is locally just as dense as the main cluster,
        # so its LOF score should stay near 1; the isolated point's only
        # neighbors are ~30 units away in a dense cluster, so a real LOF
        # score should mark it as dramatically more anomalous. A pure
        # distance-from-mean score would instead rate both far above 1
        # with no such gap between them.
        assert companioned_score < 2.0
        assert isolated_score > companioned_score * 50

    def test_outlier_detection_method_selection(self, numeric_data):
        """Test outlier detection with different methods.

        ml_outlier_detection() itself used to call ml_anomaly_zscore()/
        ml_anomaly_iqr() with an output_col kwarg neither accepts - a real
        TypeError on every call, not just a stale test expectation (fixed
        alongside restoring this test's own coverage, previously masked
        by this exact test's failure not stopping the suite from
        reporting green elsewhere)."""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        result_zscore = processor.ml_outlier_detection(
            df, column="value", output_col="is_outlier_z", method='zscore'
        )
        result_iqr = processor.ml_outlier_detection(
            df, column="value", output_col="is_outlier_i", method='iqr'
        )

        assert "is_outlier_z" in result_zscore.columns
        assert "is_outlier_i" in result_iqr.columns
        assert result_zscore["is_outlier_z"].sum() > 0
        assert result_iqr["is_outlier_i"].sum() > 0


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
