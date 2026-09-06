"""
Tests for IAS 2 Service - inventory NRV write-down detection.
"""
import pytest
import polars as pl


class TestDetectNrvWritedowns:
    def test_cost_above_nrv_flagged_with_correct_amount(self):
        from services.ias2_service import IAS2Service

        df = pl.DataFrame({
            "cost": [20.0], "price": [18.0], "costs_to_sell": [1.0], "qty": [50],
        })
        result = IAS2Service().detect_nrv_writedowns(
            df, {"cost": "cost", "selling_price": "price", "costs_to_sell": "costs_to_sell", "quantity": "qty"}
        )
        assert result["ias2_nrv"].to_list() == [17.0]
        assert result["ias2_writedown_amount"].to_list() == [150.0]
        assert result["ias2_writedown_flag"].to_list() == [True]

    def test_cost_below_nrv_not_flagged(self):
        from services.ias2_service import IAS2Service

        df = pl.DataFrame({"cost": [10.0], "price": [15.0]})
        result = IAS2Service().detect_nrv_writedowns(df, {"cost": "cost", "selling_price": "price"})
        assert result["ias2_writedown_amount"].to_list() == [0.0]
        assert result["ias2_writedown_flag"].to_list() == [False]

    def test_cost_exactly_equal_to_nrv_not_flagged(self):
        from services.ias2_service import IAS2Service

        df = pl.DataFrame({"cost": [5.0], "price": [5.0]})
        result = IAS2Service().detect_nrv_writedowns(df, {"cost": "cost", "selling_price": "price"})
        assert result["ias2_writedown_flag"].to_list() == [False]

    def test_no_costs_to_sell_nrv_equals_selling_price(self):
        from services.ias2_service import IAS2Service

        df = pl.DataFrame({"cost": [12.0], "price": [10.0]})
        result = IAS2Service().detect_nrv_writedowns(df, {"cost": "cost", "selling_price": "price"})
        assert result["ias2_nrv"].to_list() == [10.0]
        assert result["ias2_writedown_amount"].to_list() == [2.0]

    def test_no_quantity_defaults_to_row_totals(self):
        from services.ias2_service import IAS2Service

        df = pl.DataFrame({"cost": [1000.0], "price": [800.0]})
        result = IAS2Service().detect_nrv_writedowns(df, {"cost": "cost", "selling_price": "price"})
        assert result["ias2_writedown_amount"].to_list() == [200.0]

    def test_tolerance_pct_absorbs_small_excess(self):
        from services.ias2_service import IAS2Service

        df = pl.DataFrame({"cost": [10.2], "price": [10.0]})
        default_result = IAS2Service().detect_nrv_writedowns(df, {"cost": "cost", "selling_price": "price"})
        assert default_result["ias2_writedown_flag"].to_list() == [True]

        tolerant_result = IAS2Service().detect_nrv_writedowns(
            df, {"cost": "cost", "selling_price": "price"}, tolerance_pct=5.0
        )
        assert tolerant_result["ias2_writedown_flag"].to_list() == [False]

    def test_missing_required_columns_returns_unchanged(self):
        from services.ias2_service import IAS2Service

        df = pl.DataFrame({"cost": [10.0]})
        result = IAS2Service().detect_nrv_writedowns(df, {"cost": "cost", "selling_price": "missing"})
        assert "ias2_nrv" not in result.columns
