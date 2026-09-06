"""
Tests for IAS 37 Service - YoY provision trend-break and legal-claims
cross-check.
"""
import pytest
import polars as pl


class TestDetectProvisionTrendBreaks:
    def test_large_decrease_flagged(self):
        from services.ias37_service import IAS37Service

        df = pl.DataFrame({"prior": [1000.0], "current": [600.0]})
        result = IAS37Service().detect_provision_trend_breaks(
            df, {"prior_year": "prior", "current_year": "current"}
        )
        assert result["ias37_yoy_change_pct"].to_list() == [pytest.approx(-40.0)]
        assert result["ias37_trend_break_flag"].to_list() == [True]

    def test_large_increase_also_flagged(self):
        from services.ias37_service import IAS37Service

        df = pl.DataFrame({"prior": [200.0], "current": [900.0]})
        result = IAS37Service().detect_provision_trend_breaks(
            df, {"prior_year": "prior", "current_year": "current"}
        )
        assert result["ias37_yoy_change_pct"].to_list() == [pytest.approx(350.0)]
        assert result["ias37_trend_break_flag"].to_list() == [True]

    def test_small_change_not_flagged(self):
        from services.ias37_service import IAS37Service

        df = pl.DataFrame({"prior": [500.0], "current": [480.0]})
        result = IAS37Service().detect_provision_trend_breaks(
            df, {"prior_year": "prior", "current_year": "current"}
        )
        assert result["ias37_trend_break_flag"].to_list() == [False]

    def test_zero_prior_year_is_null_not_infinite(self):
        from services.ias37_service import IAS37Service

        df = pl.DataFrame({"prior": [0.0], "current": [500.0]})
        result = IAS37Service().detect_provision_trend_breaks(
            df, {"prior_year": "prior", "current_year": "current"}
        )
        assert result["ias37_yoy_change_pct"].to_list() == [None]
        assert result["ias37_trend_break_flag"].to_list() == [False]

    def test_custom_threshold(self):
        from services.ias37_service import IAS37Service

        df = pl.DataFrame({"prior": [1000.0], "current": [900.0]})  # -10%
        default_result = IAS37Service().detect_provision_trend_breaks(
            df, {"prior_year": "prior", "current_year": "current"}
        )
        assert default_result["ias37_trend_break_flag"].to_list() == [False]

        tight_result = IAS37Service().detect_provision_trend_breaks(
            df, {"prior_year": "prior", "current_year": "current"}, change_threshold_pct=5.0
        )
        assert tight_result["ias37_trend_break_flag"].to_list() == [True]

    def test_missing_columns_returns_unchanged(self):
        from services.ias37_service import IAS37Service

        df = pl.DataFrame({"prior": [1000.0]})
        result = IAS37Service().detect_provision_trend_breaks(df, {"prior_year": "prior", "current_year": "missing"})
        assert "ias37_yoy_change_pct" not in result.columns


class TestCrossCheckLegalClaims:
    @pytest.fixture
    def provisions(self):
        return pl.DataFrame({
            "category": ["Warranty", "Litigation", "Restructuring"],
            "prior": [1000.0, 500.0, 200.0],
            "current": [600.0, 480.0, 900.0],
            "settled": [False, True, False],
        })

    def test_unsettled_large_decrease_flagged(self, provisions):
        from services.ias37_service import IAS37Service

        result = IAS37Service().cross_check_legal_claims(
            provisions, {"prior_year": "prior", "current_year": "current", "settlement_flag": "settled"}
        )
        by_cat = dict(zip(result["category"].to_list(), result["ias37_unexplained_decrease_flag"].to_list()))
        assert by_cat["Warranty"] is True

    def test_settled_decrease_not_unexplained(self, provisions):
        from services.ias37_service import IAS37Service

        result = IAS37Service().cross_check_legal_claims(
            provisions, {"prior_year": "prior", "current_year": "current", "settlement_flag": "settled"}
        )
        by_cat = dict(zip(result["category"].to_list(), result["ias37_unexplained_decrease_flag"].to_list()))
        # Litigation dropped only 4% (below threshold) AND is settled -
        # either reason alone would keep it False.
        assert by_cat["Litigation"] is False

    def test_increase_never_marked_unexplained_decrease(self, provisions):
        from services.ias37_service import IAS37Service

        result = IAS37Service().cross_check_legal_claims(
            provisions, {"prior_year": "prior", "current_year": "current", "settlement_flag": "settled"}
        )
        by_cat = dict(zip(result["category"].to_list(), result["ias37_unexplained_decrease_flag"].to_list()))
        # Restructuring increased 350% and is unsettled - still not a
        # "decrease", so must not be marked as an unexplained decrease.
        assert by_cat["Restructuring"] is False

    def test_no_settlement_column_skips_unexplained_flag(self, provisions):
        from services.ias37_service import IAS37Service

        result = IAS37Service().cross_check_legal_claims(
            provisions, {"prior_year": "prior", "current_year": "current"}
        )
        assert "ias37_trend_break_flag" in result.columns
        assert "ias37_unexplained_decrease_flag" not in result.columns
