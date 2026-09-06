"""
Tests for Financial Service
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
import polars as pl
from services.financial_service import FinancialService

@pytest.fixture
def financial_df():
    return pl.DataFrame({
        "assets_curr": [1000.0, 1200.0, 1100.0],
        "liab_curr": [500.0, 400.0, 600.0],
        "inventory": [200.0, 300.0, 250.0],
        "cash": [100.0, 150.0, 50.0],
        "total_liab": [800.0, 700.0, 900.0],
        "total_equity": [1200.0, 1500.0, 1100.0],
        "net_income": [100.0, 150.0, 80.0],
        "revenue": [2000.0, 2500.0, 1800.0]
    })

def test_liquidity_ratios(financial_df):
    service = FinancialService()
    mapping = {
        "current_assets": "assets_curr",
        "current_liabilities": "liab_curr",
        "inventory": "inventory",
        "cash": "cash"
    }
    ratios = ["current_ratio", "quick_ratio", "cash_ratio"]
    
    result = service.calculate_ratios(financial_df, mapping, ratios)
    
    # Check columns created
    assert "ratio_current" in result.columns
    assert "ratio_quick" in result.columns
    assert "ratio_cash" in result.columns
    
    # Check calculations
    # Current Ratio row 0: 1000 / 500 = 2.0
    assert result["ratio_current"][0] == 2.0
    # Quick Ratio row 0: (1000 - 200) / 500 = 1.6
    assert result["ratio_quick"][0] == 1.6
    # Cash Ratio row 0: 100 / 500 = 0.2
    assert result["ratio_cash"][0] == 0.2

def test_profitability_ratios(financial_df):
    service = FinancialService()
    mapping = {
        "net_income": "net_income",
        "revenue": "revenue"
    }
    ratios = ["net_profit_margin"]
    
    result = service.calculate_ratios(financial_df, mapping, ratios)
    
    assert "ratio_net_profit_margin" in result.columns
    # 100 / 2000 = 0.05
    assert result["ratio_net_profit_margin"][0] == 0.05

def test_missing_columns_safe(financial_df):
    """Test that missing mapping doesn't crash but skips"""
    service = FinancialService()
    # Missing 'current_liabilities'
    mapping = {
        "current_assets": "assets_curr"
    }
    ratios = ["current_ratio"]

    result = service.calculate_ratios(financial_df, mapping, ratios)

    # Column should not be created if inputs missing
    assert "ratio_current" not in result.columns
    assert len(result.columns) == len(financial_df.columns)


class TestDivisionByZero:
    """x/0 is +/-inf in IEEE-754, not NaN - only 0/0 produces NaN. The
    previous implementation's .fill_nan(None) only ever caught the 0/0
    case, leaving a raw inf in every ratio whose denominator was zero but
    numerator wasn't - and an inf silently poisons any later mean/chart/
    threshold check built from it, with no visible error anywhere."""

    def test_current_ratio_zero_denominator_is_null_not_inf(self):
        df = pl.DataFrame({"ca": [100.0], "cl": [0.0]})
        result = FinancialService().calculate_ratios(
            df, {"current_assets": "ca", "current_liabilities": "cl"}, ["current_ratio"]
        )
        value = result["ratio_current"][0]
        assert value is None
        # Belt and suspenders: even if a future refactor reintroduces the
        # bug, explicitly assert it isn't infinite either.
        import math
        assert value is None or not math.isinf(value)

    def test_quick_ratio_zero_denominator_is_null(self):
        df = pl.DataFrame({"ca": [100.0], "cl": [0.0], "inv": [20.0]})
        result = FinancialService().calculate_ratios(
            df, {"current_assets": "ca", "current_liabilities": "cl", "inventory": "inv"}, ["quick_ratio"]
        )
        assert result["ratio_quick"][0] is None

    def test_interest_coverage_zero_interest_expense_is_null(self):
        df = pl.DataFrame({"ni": [10.0], "ie": [0.0]})
        result = FinancialService().calculate_ratios(
            df, {"net_income": "ni", "interest_expense": "ie"}, ["interest_coverage"]
        )
        assert result["ratio_interest_coverage"][0] is None

    def test_gross_margin_zero_revenue_is_null(self):
        df = pl.DataFrame({"rev": [0.0], "cogs": [10.0]})
        result = FinancialService().calculate_ratios(
            df, {"revenue": "rev", "cogs": "cogs"}, ["gross_margin"]
        )
        assert result["ratio_gross_margin"][0] is None

    def test_zero_over_zero_still_null(self):
        """The original 0/0 case (NaN) must still resolve to null too,
        not just the newly-fixed x/0 case."""
        df = pl.DataFrame({"ca": [0.0], "cl": [0.0]})
        result = FinancialService().calculate_ratios(
            df, {"current_assets": "ca", "current_liabilities": "cl"}, ["current_ratio"]
        )
        assert result["ratio_current"][0] is None

    def test_nonzero_division_unaffected(self):
        """The fix must not change any ordinary, non-zero-denominator
        result."""
        df = pl.DataFrame({"ca": [100.0], "cl": [50.0]})
        result = FinancialService().calculate_ratios(
            df, {"current_assets": "ca", "current_liabilities": "cl"}, ["current_ratio"]
        )
        assert result["ratio_current"][0] == 2.0
