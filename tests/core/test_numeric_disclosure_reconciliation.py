"""
Tests for Numeric Disclosure Reconciliation - parsing figures from
narrative text and comparing them against real computed dataset values.
"""
import pytest
import polars as pl


class TestParseNumeric:
    def test_percent(self):
        from core.numeric_disclosure_reconciliation import parse_numeric
        assert parse_numeric("20%") == 20.0

    def test_currency_with_commas(self):
        from core.numeric_disclosure_reconciliation import parse_numeric
        assert parse_numeric("$1,234,000") == 1234000.0

    def test_parenthesized_negative(self):
        from core.numeric_disclosure_reconciliation import parse_numeric
        assert parse_numeric("(500)") == -500.0

    def test_plain_years(self):
        from core.numeric_disclosure_reconciliation import parse_numeric
        assert parse_numeric("5 years") == 5.0

    def test_range_returns_none(self):
        from core.numeric_disclosure_reconciliation import parse_numeric
        assert parse_numeric("3 to 5 years") is None
        assert parse_numeric("3-5%") is None

    def test_empty_or_none_returns_none(self):
        from core.numeric_disclosure_reconciliation import parse_numeric
        assert parse_numeric("") is None
        assert parse_numeric(None) is None

    def test_non_numeric_text_returns_none(self):
        from core.numeric_disclosure_reconciliation import parse_numeric
        assert parse_numeric("straight-line basis") is None

    def test_decimal_percent(self):
        from core.numeric_disclosure_reconciliation import parse_numeric
        assert parse_numeric("12.5%") == pytest.approx(12.5)


class TestNormalizeToDecimal:
    def test_percent_divided_by_100(self):
        from core.numeric_disclosure_reconciliation import normalize_to_decimal
        assert normalize_to_decimal(20.0, "percent") == pytest.approx(0.20)

    def test_non_percent_passthrough(self):
        from core.numeric_disclosure_reconciliation import normalize_to_decimal
        assert normalize_to_decimal(5.0, "years") == 5.0


class TestComputeActualValueStats:
    def test_basic_stats(self):
        from core.numeric_disclosure_reconciliation import compute_actual_value_stats

        df = pl.DataFrame({"rate": [0.1, 0.1, 0.2, None]})
        stats = compute_actual_value_stats(df, "rate")
        assert stats["mean"] == pytest.approx((0.1 + 0.1 + 0.2) / 3)
        assert stats["min"] == pytest.approx(0.1)
        assert stats["max"] == pytest.approx(0.2)
        assert stats["distinct_count"] == 2
        assert stats["non_null_count"] == 3
        assert stats["total_count"] == 4

    def test_missing_column_returns_none(self):
        from core.numeric_disclosure_reconciliation import compute_actual_value_stats

        df = pl.DataFrame({"rate": [0.1]})
        assert compute_actual_value_stats(df, "missing") is None

    def test_non_numeric_column_returns_none(self):
        from core.numeric_disclosure_reconciliation import compute_actual_value_stats

        df = pl.DataFrame({"label": ["a", "b"]})
        assert compute_actual_value_stats(df, "label") is None

    def test_all_null_column_returns_none(self):
        from core.numeric_disclosure_reconciliation import compute_actual_value_stats

        df = pl.DataFrame({"rate": pl.Series([None, None], dtype=pl.Float64)})
        assert compute_actual_value_stats(df, "rate") is None


class TestReconcileDisclosedFigure:
    def test_matching_value_not_flagged(self):
        from core.numeric_disclosure_reconciliation import reconcile_disclosed_figure

        item = {"label": "Discount rate", "value_text": "8%", "unit": "percent"}
        actual_stats = {"mean": 0.08, "min": 0.08, "max": 0.08, "distinct_count": 1,
                         "non_null_count": 3, "total_count": 3}
        result = reconcile_disclosed_figure(item, actual_stats)
        assert result["computable"] is True
        assert result["flag"] is False
        assert result["deviation"] == pytest.approx(0.0)

    def test_mismatched_value_flagged(self):
        from core.numeric_disclosure_reconciliation import reconcile_disclosed_figure

        item = {"label": "Depreciation rate", "value_text": "20%", "unit": "percent"}
        actual_stats = {"mean": 0.10, "min": 0.10, "max": 0.10, "distinct_count": 1,
                         "non_null_count": 5, "total_count": 5}
        result = reconcile_disclosed_figure(item, actual_stats)
        assert result["computable"] is True
        assert result["flag"] is True
        assert result["deviation"] == pytest.approx(0.10)
        assert result["deviation_pct"] == pytest.approx(100.0)

    def test_small_deviation_within_tolerance_not_flagged(self):
        from core.numeric_disclosure_reconciliation import reconcile_disclosed_figure

        item = {"label": "Rate", "value_text": "20.1%", "unit": "percent"}
        actual_stats = {"mean": 0.20, "min": 0.20, "max": 0.20, "distinct_count": 1,
                         "non_null_count": 5, "total_count": 5}
        result = reconcile_disclosed_figure(item, actual_stats, tolerance_abs=0.005, tolerance_pct=10.0)
        assert result["flag"] is False

    def test_unmapped_item_not_computable(self):
        from core.numeric_disclosure_reconciliation import reconcile_disclosed_figure

        item = {"label": "Rate", "value_text": "20%", "unit": "percent"}
        result = reconcile_disclosed_figure(item, None)
        assert result["computable"] is False
        assert result["flag"] is False
        assert "Not mapped" in result["reason"]

    def test_unparseable_disclosed_value_not_computable(self):
        from core.numeric_disclosure_reconciliation import reconcile_disclosed_figure

        item = {"label": "Useful life", "value_text": "3 to 5 years", "unit": "years"}
        actual_stats = {"mean": 4.0, "min": 3.0, "max": 5.0, "distinct_count": 2,
                         "non_null_count": 2, "total_count": 2}
        result = reconcile_disclosed_figure(item, actual_stats)
        assert result["computable"] is False

    def test_zero_actual_mean_skips_relative_deviation(self):
        from core.numeric_disclosure_reconciliation import reconcile_disclosed_figure

        item = {"label": "Rate", "value_text": "5%", "unit": "percent"}
        actual_stats = {"mean": 0.0, "min": 0.0, "max": 0.0, "distinct_count": 1,
                         "non_null_count": 3, "total_count": 3}
        result = reconcile_disclosed_figure(item, actual_stats)
        assert result["deviation_pct"] is None
        # Absolute deviation (0.05) still exceeds the default 0.005 tolerance.
        assert result["flag"] is True


class TestReconcileAll:
    def test_only_mapped_items_reconciled(self):
        from core.numeric_disclosure_reconciliation import reconcile_all

        items = [
            {"label": "Depreciation rate", "value_text": "20%", "unit": "percent"},
            {"label": "Useful life", "value_text": "5 years", "unit": "years"},
        ]
        datasets = {"FAR": pl.DataFrame({"depreciation_rate": [0.10] * 5})}
        mappings = {0: {"dataset": "FAR", "column": "depreciation_rate"}}
        results = reconcile_all(items, mappings, datasets)

        assert results[0]["computable"] is True
        assert results[0]["flag"] is True
        assert results[1]["computable"] is False

    def test_mapping_to_unknown_dataset_not_computable(self):
        from core.numeric_disclosure_reconciliation import reconcile_all

        items = [{"label": "Rate", "value_text": "20%", "unit": "percent"}]
        mappings = {0: {"dataset": "DoesNotExist", "column": "rate"}}
        results = reconcile_all(items, mappings, {})
        assert results[0]["computable"] is False
