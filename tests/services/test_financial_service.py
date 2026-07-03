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
