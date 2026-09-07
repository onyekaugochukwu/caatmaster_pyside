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

    def test_anomaly_zscore_direction_above_only_flags_fewer_than_both(self, numeric_data):
        """Regression test: the anomaly detection dialog's Z-Score tab has
        exposed a "Direction" dropdown (Both / Above Mean Only / Below
        Mean Only) since before this fix, but ml_anomaly_zscore accepted
        no such parameter - selecting "Above Mean Only" changed only the
        dialog's own preview, and had no effect on the value actually
        written to the dataset once Run Detection was clicked. "both"
        must flag every point either direction would flag, so it can
        never flag fewer than "above" alone."""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})

        both = processor.ml_anomaly_zscore(df, column="value", threshold=1.5, direction="both")
        above = processor.ml_anomaly_zscore(df, column="value", threshold=1.5, direction="above")
        below = processor.ml_anomaly_zscore(df, column="value", threshold=1.5, direction="below")

        assert above["value_is_outlier"].sum() <= both["value_is_outlier"].sum()
        assert below["value_is_outlier"].sum() <= both["value_is_outlier"].sum()
        # This dataset's outliers include both very high (200, 250, 300)
        # and very low (-100, -150) values, so each one-sided direction
        # must find strictly fewer than "both" finds - proves direction
        # is actually filtering, not silently ignored.
        assert above["value_is_outlier"].sum() < both["value_is_outlier"].sum()
        assert below["value_is_outlier"].sum() < both["value_is_outlier"].sum()
        # A value flagged as "above" must be genuinely above the mean.
        mean = df["value"].mean()
        flagged_above = above.filter(pl.col("value_is_outlier"))["value"]
        assert all(v > mean for v in flagged_above)

    def test_anomaly_iforest_accepts_n_estimators_and_max_samples(self, numeric_data):
        """Regression test: the Isolation Forest tab's "Number of Trees"
        and "Max Samples" spinners were collected into params by the
        dialog but silently dropped before reaching ml_anomaly_iforest,
        which accepted only contamination. Asserts the real method now
        accepts both without raising, matching what the dialog has always
        exposed."""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})
        result = processor.ml_anomaly_iforest(
            df, column="value", contamination=0.1, n_estimators=50, max_samples="auto"
        )
        assert "value_is_anomaly" in result.columns
        assert "value_anomaly_score" in result.columns

    def test_anomaly_lof_uses_real_contamination_parameter(self, numeric_data):
        """Mirrors test_anomaly_iforest_uses_real_contamination_parameter -
        LOF's contamination now controls the flagged fraction the same
        way Isolation Forest's does, rather than scikit-learn's own
        'auto' default that ignored the dialog's exposed contamination
        control entirely (the LOF tab exposed it under the misleading
        label "Outlier Threshold", tied to neither scikit-learn parameter
        at all)."""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        df = pl.DataFrame({"value": numeric_data})
        low = processor.ml_anomaly_lof(df, column="value", n_neighbors=20, contamination=0.02)
        high = processor.ml_anomaly_lof(df, column="value", n_neighbors=20, contamination=0.3)
        assert low["value_is_outlier"].sum() < high["value_is_outlier"].sum()

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
    """Test cases for ML forecasting operations.

    ml_forecast/ForecastDialog (formerly tested here) were removed this
    session: fully redundant with ml_arima/ml_ets below (both already
    real, working, genuinely extending the dataset with forecasted rows
    via statsmodels), while ml_forecast itself never did that at all -
    it silently smoothed existing rows in place and ignored its own
    `periods` parameter entirely, behind a dialog (date column, horizon,
    confidence bounds, seasonal period, method choice) that promised
    a feature no part of its real backend delivered. It had already been
    removed from the right-click menu as a "no-op/duplicate" before this
    session, and was not reachable from anywhere else in the UI.

    ml_arima/ml_ets had no test coverage of their own before this change;
    these replace what was removed instead of simply deleting it."""

    def test_arima_extends_dataset_with_forecast_rows(self):
        """ARIMA must genuinely forecast INTO THE FUTURE - add `steps` new
        rows beyond the original data - not just smooth existing rows,
        which is the exact gap that made the now-removed ml_forecast a
        broken promise of this same behavior."""
        from core.data_processor import DataProcessor

        np.random.seed(0)
        values = [10 + i * 0.5 + np.random.normal(0, 0.5) for i in range(30)]
        df = pl.DataFrame({"value": values})

        processor = DataProcessor()
        result = processor.ml_arima(df, column="value", output_col="forecast", steps=5)

        assert len(result) == len(df) + 5
        forecast_tail = result["forecast"].tail(5).to_list()
        assert all(v is not None for v in forecast_tail)

    def test_ets_extends_dataset_with_forecast_rows(self):
        """Mirrors the ARIMA test above for Exponential Smoothing."""
        from core.data_processor import DataProcessor

        np.random.seed(0)
        values = [10 + i * 0.5 + np.random.normal(0, 0.5) for i in range(30)]
        df = pl.DataFrame({"value": values})

        processor = DataProcessor()
        result = processor.ml_ets(df, column="value", output_col="forecast", steps=5)

        assert len(result) == len(df) + 5
        forecast_tail = result["forecast"].tail(5).to_list()
        assert all(v is not None for v in forecast_tail)

    def test_arima_forecast_values_are_reported_via_metrics_sink(self):
        """The dialog path relies on metrics_sink to build the Analysis
        Report shown after a forecast is applied (build_forecast_report,
        shared by ml_arima/ml_ets) - confirms it actually gets populated
        with a real model description, not left empty."""
        from core.data_processor import DataProcessor

        np.random.seed(0)
        values = [10 + i * 0.3 for i in range(25)]
        df = pl.DataFrame({"value": values})

        processor = DataProcessor()
        sink = {}
        processor.ml_arima(df, column="value", output_col="forecast", steps=3, metrics_sink=sink)

        assert "ARIMA" in sink.get("model_type", "")
        assert sink.get("task") == "forecasting"


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
