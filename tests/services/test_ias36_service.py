"""
Tests for IAS 36 Service - reverse-DCF implied growth rate.
"""
import pytest
import polars as pl


class TestCalculateImpliedGrowthRate:
    def test_known_single_year_case_recovers_exact_growth_rate(self):
        """CF1=100, r=0.10, g=0.03 forward-computes to CV=1428.57 -
        solving backward from that CV should recover g=0.03."""
        from services.ias36_service import IAS36Service

        df = pl.DataFrame({
            "carrying_value": [1428.57],
            "discount_rate": [0.10],
            "cf1": [100.0],
        })
        result = IAS36Service().calculate_implied_growth_rate(
            df, "carrying_value", "discount_rate", ["cf1"]
        )
        assert result["ias36_implied_growth_rate"].to_list()[0] == pytest.approx(0.03, abs=1e-4)

    def test_higher_carrying_value_implies_higher_growth(self):
        from services.ias36_service import IAS36Service

        df = pl.DataFrame({
            "carrying_value": [1428.57, 5000.0],
            "discount_rate": [0.10, 0.10],
            "cf1": [100.0, 100.0],
        })
        result = IAS36Service().calculate_implied_growth_rate(
            df, "carrying_value", "discount_rate", ["cf1"]
        )
        rates = result["ias36_implied_growth_rate"].to_list()
        assert rates[1] > rates[0]
        assert rates[1] == pytest.approx(0.08, abs=1e-4)

    def test_benchmark_flag_raised_above_threshold(self):
        from services.ias36_service import IAS36Service

        df = pl.DataFrame({
            "carrying_value": [1428.57, 5000.0],
            "discount_rate": [0.10, 0.10],
            "cf1": [100.0, 100.0],
        })
        result = IAS36Service().calculate_implied_growth_rate(
            df, "carrying_value", "discount_rate", ["cf1"],
            benchmark_growth_value=0.02, flag_threshold_pp=2.0,
        )
        assert result["ias36_flag"].to_list() == [False, True]

    def test_per_row_benchmark_column(self):
        from services.ias36_service import IAS36Service

        df = pl.DataFrame({
            "carrying_value": [1428.57, 1428.57],
            "discount_rate": [0.10, 0.10],
            "cf1": [100.0, 100.0],
            "country_gdp": [0.05, 0.005],  # first benchmark above implied g, second below
        })
        result = IAS36Service().calculate_implied_growth_rate(
            df, "carrying_value", "discount_rate", ["cf1"],
            benchmark_growth_col="country_gdp", flag_threshold_pp=1.0,
        )
        assert result["ias36_flag"].to_list() == [False, True]

    def test_multi_year_explicit_cash_flows(self):
        from services.ias36_service import IAS36Service

        df = pl.DataFrame({
            "carrying_value": [1000.0],
            "discount_rate": [0.12],
            "cf1": [100.0], "cf2": [110.0], "cf3": [121.0],
        })
        result = IAS36Service().calculate_implied_growth_rate(
            df, "carrying_value", "discount_rate", ["cf1", "cf2", "cf3"]
        )
        g = result["ias36_implied_growth_rate"].to_list()[0]
        assert g is not None
        assert -0.5 < g < 0.12

    def test_no_root_in_range_returns_null_not_fabricated(self):
        """Cash flows alone already exceed the (tiny) carrying value even
        at 0% terminal growth - no meaningful implied rate exists."""
        from services.ias36_service import IAS36Service

        df = pl.DataFrame({"carrying_value": [1.0], "discount_rate": [0.10], "cf1": [100.0]})
        result = IAS36Service().calculate_implied_growth_rate(df, "carrying_value", "discount_rate", ["cf1"])
        assert result["ias36_implied_growth_rate"].to_list() == [None]

    def test_missing_columns_returns_unchanged(self):
        from services.ias36_service import IAS36Service

        df = pl.DataFrame({"carrying_value": [1000.0]})
        result = IAS36Service().calculate_implied_growth_rate(
            df, "carrying_value", "discount_rate", ["cf1"]
        )
        assert "ias36_implied_growth_rate" not in result.columns

    def test_no_benchmark_supplied_skips_flag_columns(self):
        from services.ias36_service import IAS36Service

        df = pl.DataFrame({"carrying_value": [1428.57], "discount_rate": [0.10], "cf1": [100.0]})
        result = IAS36Service().calculate_implied_growth_rate(df, "carrying_value", "discount_rate", ["cf1"])
        assert "ias36_implied_growth_rate" in result.columns
        assert "ias36_flag" not in result.columns

    def test_negative_or_zero_discount_rate_returns_null(self):
        from services.ias36_service import IAS36Service

        df = pl.DataFrame({"carrying_value": [1000.0], "discount_rate": [0.0], "cf1": [100.0]})
        result = IAS36Service().calculate_implied_growth_rate(df, "carrying_value", "discount_rate", ["cf1"])
        assert result["ias36_implied_growth_rate"].to_list() == [None]
