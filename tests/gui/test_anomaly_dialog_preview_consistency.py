"""
Preview/apply consistency for the Anomaly Detection dialog.

A real, discovered defect: AnomalyDetectionDialog.preview() used to
recompute every method (Isolation Forest, Z-Score, IQR, Local Outlier
Factor) as its own local distance-from-mean heuristic, entirely separate
from DataProcessor's real implementations that transform_view actually
calls once "Run Detection" is clicked. A reviewer could preview one
result and get a genuinely different one after committing - the exact
kind of silent mismatch that erodes trust in every other number this
application produces. preview() now calls the same DataProcessor methods,
with the same parameters, that the real apply path calls; these tests
pin that down structurally so a future edit can't quietly reintroduce a
second, independently-drifting implementation.
"""
import numpy as np
import polars as pl
import pytest


@pytest.fixture
def sample_df():
    np.random.seed(0)
    normal = [100 + np.random.normal(0, 5) for _ in range(60)]
    outliers = [250, -120, 300]
    return pl.DataFrame({"amount": normal + outliers})


@pytest.fixture
def dialog(qtbot, sample_df):
    from gui.dialogs.anomaly_dialog import AnomalyDetectionDialog

    dlg = AnomalyDetectionDialog(sample_df, parent=None)
    qtbot.addWidget(dlg)
    return dlg


class TestOpensOnTheRequestedTab:
    """Regression test: all four ml_anomaly_* operation ids share this one
    dialog class (TransformationDialogFactory.DIALOG_MAPPING), but the
    factory used to construct it identically regardless of which one was
    requested - choosing "Local Outlier Factor" by name from a menu still
    opened on the Isolation Forest tab, the first one, every time."""

    @pytest.mark.parametrize("operation_id,expected_tab", [
        ("ml_anomaly_iforest", "Isolation Forest"),
        ("ml_anomaly_zscore", "Z-Score"),
        ("ml_anomaly_iqr", "IQR"),
        ("ml_anomaly_lof", "Local Outlier Factor"),
    ])
    def test_factory_opens_matching_tab(self, qtbot, sample_df, operation_id, expected_tab):
        from gui.dialogs.transformation_dialog_factory import TransformationDialogFactory

        dlg = TransformationDialogFactory.create_dialog(operation_id, sample_df, parent=None)
        qtbot.addWidget(dlg)
        actual_tab = dlg.tabs.tabText(dlg.tabs.currentIndex())
        assert actual_tab == expected_tab


class TestPreviewMatchesRealApply:
    def _select_column(self, selector, column: str):
        selector.combo.setCurrentText(column)

    def test_iforest_preview_matches_data_processor_output(self, dialog, sample_df):
        from core.data_processor import DataProcessor

        dialog.tabs.setCurrentIndex(0)
        self._select_column(dialog.iforest_col, "amount")
        dialog.iforest_contamination.setValue(0.1)
        dialog.preview()

        params = dialog.get_parameters()
        expected = DataProcessor().ml_anomaly_iforest(
            sample_df, column="amount",
            contamination=params["contamination"],
            n_estimators=params["n_estimators"],
            max_samples=params["max_samples"],
        )
        assert dialog.output_flag_label.text() == "amount_is_anomaly"
        assert dialog.output_score_label.text() == "amount_anomaly_score"
        n_expected = int(expected["amount_is_anomaly"].sum())
        assert f"Anomalies found: {n_expected:,}" in dialog.stats_label.text()

    def test_zscore_preview_honors_direction(self, dialog, sample_df):
        from core.data_processor import DataProcessor

        dialog.tabs.setCurrentIndex(1)
        self._select_column(dialog.zscore_col, "amount")
        dialog.zscore_threshold.setValue(1.5)
        dialog.zscore_direction.setCurrentText("Above Mean Only")
        dialog.preview()

        expected = DataProcessor().ml_anomaly_zscore(
            sample_df, column="amount", threshold=1.5, direction="above"
        )
        n_expected = int(expected["amount_is_outlier"].sum())
        assert f"Anomalies found: {n_expected:,}" in dialog.stats_label.text()

    def test_iqr_preview_honors_extreme_bounds_mode(self, dialog, sample_df):
        from core.data_processor import DataProcessor

        dialog.tabs.setCurrentIndex(2)
        self._select_column(dialog.iqr_col, "amount")
        dialog.iqr_multiplier.setValue(1.5)
        dialog.iqr_mode.setCurrentIndex(1)  # Extreme Bounds (3x IQR)
        dialog.preview()

        expected = DataProcessor().ml_anomaly_iqr(sample_df, column="amount", multiplier=3.0)
        n_expected = int(expected["amount_is_outlier"].sum())
        assert f"Anomalies found: {n_expected:,}" in dialog.stats_label.text()

    def test_lof_preview_matches_data_processor_output(self, dialog, sample_df):
        from core.data_processor import DataProcessor

        dialog.tabs.setCurrentIndex(3)
        self._select_column(dialog.lof_col, "amount")
        dialog.lof_neighbors.setValue(20)
        dialog.lof_contamination.setValue(0.1)
        dialog.preview()

        expected = DataProcessor().ml_anomaly_lof(
            sample_df, column="amount", n_neighbors=20, contamination=0.1
        )
        n_expected = int(expected["amount_is_outlier"].sum())
        assert f"Anomalies found: {n_expected:,}" in dialog.stats_label.text()
        assert dialog.output_flag_label.text() == "amount_is_outlier"
        assert dialog.output_score_label.text() == "amount_lof_score"
