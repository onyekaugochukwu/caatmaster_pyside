"""
Tests for IAS 21 Service - FX rate consistency check.
"""
import pytest
import polars as pl


class TestDetectFxRateDeviations:
    def test_matching_rate_not_flagged(self):
        from services.ias21_service import IAS21Service

        df = pl.DataFrame({"booked": [1.10], "benchmark": [1.10]})
        result = IAS21Service().detect_fx_rate_deviations(
            df, {"booked_rate": "booked", "benchmark_rate": "benchmark"}
        )
        assert result["ias21_rate_deviation_pct"].to_list() == [pytest.approx(0.0)]
        assert result["ias21_fx_rate_flag"].to_list() == [False]

    def test_deviating_rate_flagged_and_quantified(self):
        from services.ias21_service import IAS21Service

        df = pl.DataFrame({"booked": [1.35], "benchmark": [1.30], "local_amount": [10000.0]})
        result = IAS21Service().detect_fx_rate_deviations(
            df, {"booked_rate": "booked", "benchmark_rate": "benchmark", "local_amount": "local_amount"},
            tolerance_pct=1.0,
        )
        assert result["ias21_fx_rate_flag"].to_list() == [True]
        assert result["ias21_rate_deviation_pct"].to_list()[0] == pytest.approx(3.846154, rel=1e-4)
        # booked amount (13,500) overstates the benchmark-rate amount (13,000) by 500
        assert result["ias21_fx_amount_variance"].to_list()[0] == pytest.approx(-500.0)

    def test_within_tolerance_not_flagged(self):
        from services.ias21_service import IAS21Service

        df = pl.DataFrame({"booked": [1.105], "benchmark": [1.10]})
        result = IAS21Service().detect_fx_rate_deviations(
            df, {"booked_rate": "booked", "benchmark_rate": "benchmark"}, tolerance_pct=1.0
        )
        assert result["ias21_fx_rate_flag"].to_list() == [False]

    def test_zero_benchmark_rate_is_null_not_infinite(self):
        from services.ias21_service import IAS21Service

        df = pl.DataFrame({"booked": [1.10], "benchmark": [0.0]})
        result = IAS21Service().detect_fx_rate_deviations(
            df, {"booked_rate": "booked", "benchmark_rate": "benchmark"}
        )
        assert result["ias21_rate_deviation_pct"].to_list() == [None]
        assert result["ias21_fx_rate_flag"].to_list() == [False]

    def test_no_local_amount_skips_variance_column(self):
        from services.ias21_service import IAS21Service

        df = pl.DataFrame({"booked": [1.35], "benchmark": [1.30]})
        result = IAS21Service().detect_fx_rate_deviations(
            df, {"booked_rate": "booked", "benchmark_rate": "benchmark"}
        )
        assert "ias21_fx_rate_flag" in result.columns
        assert "ias21_fx_amount_variance" not in result.columns

    def test_missing_required_columns_returns_unchanged(self):
        from services.ias21_service import IAS21Service

        df = pl.DataFrame({"booked": [1.10]})
        result = IAS21Service().detect_fx_rate_deviations(df, {"booked_rate": "booked", "benchmark_rate": "missing"})
        assert "ias21_rate_deviation_pct" not in result.columns
