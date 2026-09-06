"""
Tests for IFRS 9 Service - Staging (DPD + PD-based SICR overlay) and
scenario-weighted ECL.
"""
import pytest
import polars as pl


class TestPerformStagingDpdOnly:
    def test_basic_staging_by_dpd(self):
        from services.ifrs9_service import IFRS9Service

        df = pl.DataFrame({"dpd": [0, 45, 120]})
        result = IFRS9Service().perform_staging(df, {"dpd": "dpd"})
        assert result["ifrs9_stage"].to_list() == [1, 2, 3]
        assert result["ifrs9_status"].to_list() == ["Performing", "Underperforming", "Non-Performing"]

    def test_missing_dpd_and_dates_returns_unchanged(self):
        from services.ifrs9_service import IFRS9Service

        df = pl.DataFrame({"amount": [1, 2, 3]})
        result = IFRS9Service().perform_staging(df, {})
        assert "ifrs9_stage" not in result.columns

    def test_ecl_calculation_when_pd_lgd_mapped(self):
        from services.ifrs9_service import IFRS9Service

        df = pl.DataFrame({"dpd": [0], "exposure": [100000.0], "pd": [0.05], "lgd": [0.4]})
        result = IFRS9Service().perform_staging(
            df, {"dpd": "dpd", "exposure": "exposure", "pd": "pd", "lgd": "lgd"}
        )
        assert result["ifrs9_ecl_amount"].to_list() == [pytest.approx(2000.0)]
        assert result["ifrs9_coverage_ratio"].to_list() == [pytest.approx(0.02)]


class TestPerformStagingSicrOverlay:
    def test_pd_deterioration_escalates_stage1_to_stage2(self):
        from services.ifrs9_service import IFRS9Service

        df = pl.DataFrame({
            "dpd": [0, 0, 100],
            "pd_current": [0.05, 0.20, 0.5],
            "pd_origination": [0.04, 0.05, 0.4],
        })
        result = IFRS9Service().perform_staging(
            df,
            {"dpd": "dpd", "pd_current": "pd_current", "pd_origination": "pd_origination"},
            {"stage2_threshold": 30, "stage3_threshold": 90, "sicr_pd_multiplier": 2.0},
        )
        # Row 0: 0.05/0.04 = 1.25x, below the 2x trigger -> stays Stage 1.
        # Row 1: 0.20/0.05 = 4x, above the trigger -> escalated to Stage 2 despite dpd=0.
        # Row 2: already Stage 3 by DPD -> never downgraded by the PD overlay.
        assert result["ifrs9_stage"].to_list() == [1, 2, 3]
        assert result["ifrs9_status"].to_list() == ["Performing", "Underperforming", "Non-Performing"]

    def test_sicr_overlay_never_downgrades_stage3(self):
        from services.ifrs9_service import IFRS9Service

        df = pl.DataFrame({"dpd": [120], "pd_current": [0.5], "pd_origination": [0.45]})
        result = IFRS9Service().perform_staging(
            df,
            {"dpd": "dpd", "pd_current": "pd_current", "pd_origination": "pd_origination"},
            {"sicr_pd_multiplier": 2.0},
        )
        assert result["ifrs9_stage"].to_list() == [3]

    def test_no_sicr_multiplier_ignores_pd_overlay(self):
        from services.ifrs9_service import IFRS9Service

        df = pl.DataFrame({"dpd": [0], "pd_current": [0.5], "pd_origination": [0.01]})
        result = IFRS9Service().perform_staging(
            df, {"dpd": "dpd", "pd_current": "pd_current", "pd_origination": "pd_origination"}
        )
        assert result["ifrs9_stage"].to_list() == [1]


class TestScenarioWeightedEcl:
    @pytest.fixture
    def portfolio(self):
        return pl.DataFrame({
            "ead": [100000.0, 50000.0],
            "lgd": [0.4, 0.4],
            "pd_base": [0.05, 0.05],
            "pd_upside": [0.02, 0.02],
            "pd_downside": [0.15, 0.15],
            "mgmt_ecl": [1000.0, 500.0],
        })

    def test_weighted_ecl_matches_manual_calculation(self, portfolio):
        from services.ifrs9_service import IFRS9Service

        mapping = {
            "exposure": "ead", "lgd": "lgd", "pd_base": "pd_base",
            "pd_upside": "pd_upside", "pd_downside": "pd_downside",
        }
        result = IFRS9Service().calculate_scenario_weighted_ecl(
            portfolio, mapping, weights={"base": 0.5, "upside": 0.25, "downside": 0.25}
        )
        # weighted_pd = 0.5*0.05 + 0.25*0.02 + 0.25*0.15 = 0.0675
        assert result["ifrs9_weighted_pd"].to_list() == [pytest.approx(0.0675)] * 2
        assert result["ifrs9_scenario_ecl"].to_list() == [pytest.approx(2700.0), pytest.approx(1350.0)]

    def test_variance_flag_raised_above_threshold(self, portfolio):
        from services.ifrs9_service import IFRS9Service

        mapping = {
            "exposure": "ead", "lgd": "lgd", "pd_base": "pd_base",
            "pd_upside": "pd_upside", "pd_downside": "pd_downside", "management_ecl": "mgmt_ecl",
        }
        result = IFRS9Service().calculate_scenario_weighted_ecl(
            portfolio, mapping, variance_threshold_pct=20.0
        )
        assert result["ifrs9_ecl_variance_flag"].to_list() == [True, True]
        assert result["ifrs9_ecl_variance_pct"].to_list()[0] == pytest.approx(62.962963, rel=1e-4)

    def test_variance_not_flagged_when_close(self):
        from services.ifrs9_service import IFRS9Service

        df = pl.DataFrame({"ead": [100000.0], "lgd": [0.4], "pd_base": [0.05], "mgmt_ecl": [2000.0]})
        result = IFRS9Service().calculate_scenario_weighted_ecl(
            df, {"exposure": "ead", "lgd": "lgd", "pd_base": "pd_base", "management_ecl": "mgmt_ecl"},
            weights={"base": 1.0}, variance_threshold_pct=20.0,
        )
        # base-only scenario -> ECL = 100000*0.05*0.4 = 2000, exactly matching mgmt_ecl
        assert result["ifrs9_scenario_ecl"].to_list() == [pytest.approx(2000.0)]
        assert result["ifrs9_ecl_variance_flag"].to_list() == [False]

    def test_missing_required_columns_returns_unchanged(self):
        from services.ifrs9_service import IFRS9Service

        df = pl.DataFrame({"ead": [1.0]})
        result = IFRS9Service().calculate_scenario_weighted_ecl(df, {"exposure": "ead", "lgd": "missing"})
        assert "ifrs9_scenario_ecl" not in result.columns

    def test_no_scenario_pd_mapped_returns_unchanged(self):
        from services.ifrs9_service import IFRS9Service

        df = pl.DataFrame({"ead": [1.0], "lgd": [0.4]})
        result = IFRS9Service().calculate_scenario_weighted_ecl(df, {"exposure": "ead", "lgd": "lgd"})
        assert "ifrs9_scenario_ecl" not in result.columns

    def test_renormalizes_weights_when_scenario_missing(self):
        from services.ifrs9_service import IFRS9Service

        # Only base and downside mapped - upside's weight should be
        # redistributed proportionally, not silently dropped to zero.
        df = pl.DataFrame({"ead": [100000.0], "lgd": [0.4], "pd_base": [0.05], "pd_downside": [0.15]})
        result = IFRS9Service().calculate_scenario_weighted_ecl(
            df, {"exposure": "ead", "lgd": "lgd", "pd_base": "pd_base", "pd_downside": "pd_downside"},
            weights={"base": 0.5, "upside": 0.25, "downside": 0.25},
        )
        # renormalized: base 0.5/0.75=0.6667, downside 0.25/0.75=0.3333
        # weighted_pd = 0.6667*0.05 + 0.3333*0.15 = 0.08333
        assert result["ifrs9_weighted_pd"].to_list()[0] == pytest.approx(0.08333, rel=1e-3)
