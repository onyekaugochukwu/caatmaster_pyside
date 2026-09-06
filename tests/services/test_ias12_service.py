"""
Tests for IAS 12 Service - deferred tax asset recoverability check.
"""
import pytest
import polars as pl


class TestCalculateRequiredTaxableProfit:
    def test_required_profit_calculation(self):
        from services.ias12_service import IAS12Service

        df = pl.DataFrame({"dta": [1000000.0], "rate": [0.25], "years": [5]})
        result = IAS12Service().calculate_required_taxable_profit(
            df, {"dta_balance": "dta", "tax_rate": "rate", "utilization_years": "years"},
            benchmark_profit_value=500000.0,
        )
        assert result["ias12_required_annual_taxable_profit"].to_list() == [pytest.approx(800000.0)]

    def test_shortfall_flagged_above_threshold(self):
        from services.ias12_service import IAS12Service

        df = pl.DataFrame({"dta": [1000000.0], "rate": [0.25], "years": [5]})
        result = IAS12Service().calculate_required_taxable_profit(
            df, {"dta_balance": "dta", "tax_rate": "rate", "utilization_years": "years"},
            benchmark_profit_value=500000.0, flag_threshold_pct=20.0,
        )
        assert result["ias12_shortfall_pct"].to_list() == [pytest.approx(60.0)]
        assert result["ias12_recoverability_flag"].to_list() == [True]

    def test_benchmark_exceeding_required_not_flagged(self):
        from services.ias12_service import IAS12Service

        df = pl.DataFrame({"dta": [1000000.0], "rate": [0.25], "years": [5]})
        result = IAS12Service().calculate_required_taxable_profit(
            df, {"dta_balance": "dta", "tax_rate": "rate", "utilization_years": "years"},
            benchmark_profit_value=900000.0,
        )
        assert result["ias12_shortfall_pct"].to_list() == [pytest.approx(-11.111111, rel=1e-4)]
        assert result["ias12_recoverability_flag"].to_list() == [False]

    def test_per_row_benchmark_column(self):
        from services.ias12_service import IAS12Service

        df = pl.DataFrame({
            "dta": [1000000.0, 1000000.0], "rate": [0.25, 0.25], "years": [5, 5],
            "hist_profit": [500000.0, 900000.0],
        })
        result = IAS12Service().calculate_required_taxable_profit(
            df, {"dta_balance": "dta", "tax_rate": "rate", "utilization_years": "years",
                 "benchmark_profit": "hist_profit"},
        )
        assert result["ias12_recoverability_flag"].to_list() == [True, False]

    def test_explicit_benchmark_col_param_overrides_mapping(self):
        from services.ias12_service import IAS12Service

        df = pl.DataFrame({
            "dta": [1000000.0], "rate": [0.25], "years": [5], "alt_benchmark": [500000.0],
        })
        result = IAS12Service().calculate_required_taxable_profit(
            df, {"dta_balance": "dta", "tax_rate": "rate", "utilization_years": "years"},
            benchmark_profit_col="alt_benchmark",
        )
        assert result["ias12_recoverability_flag"].to_list() == [True]

    def test_zero_tax_rate_returns_null_not_infinite(self):
        from services.ias12_service import IAS12Service

        df = pl.DataFrame({"dta": [1000000.0], "rate": [0.0], "years": [5]})
        result = IAS12Service().calculate_required_taxable_profit(
            df, {"dta_balance": "dta", "tax_rate": "rate", "utilization_years": "years"},
            benchmark_profit_value=500000.0,
        )
        assert result["ias12_required_annual_taxable_profit"].to_list() == [None]
        assert result["ias12_recoverability_flag"].to_list() == [False]

    def test_no_benchmark_supplied_skips_flag_columns(self):
        from services.ias12_service import IAS12Service

        df = pl.DataFrame({"dta": [1000000.0], "rate": [0.25], "years": [5]})
        result = IAS12Service().calculate_required_taxable_profit(
            df, {"dta_balance": "dta", "tax_rate": "rate", "utilization_years": "years"}
        )
        assert "ias12_required_annual_taxable_profit" in result.columns
        assert "ias12_recoverability_flag" not in result.columns

    def test_missing_required_columns_returns_unchanged(self):
        from services.ias12_service import IAS12Service

        df = pl.DataFrame({"dta": [1000000.0]})
        result = IAS12Service().calculate_required_taxable_profit(
            df, {"dta_balance": "dta", "tax_rate": "missing", "utilization_years": "missing2"}
        )
        assert "ias12_required_annual_taxable_profit" not in result.columns
