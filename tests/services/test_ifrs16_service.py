"""
Tests for IFRS 16 Service - lease liability / ROU asset and IBR
reasonableness check.
"""
import pytest
import polars as pl


class TestCalculateLeaseLiability:
    def test_known_annuity_pv(self):
        """PV of a $1000/yr, 5-year ordinary annuity at 5% = 4329.48
        (standard annuity table value)."""
        from services.ifrs16_service import IFRS16Service

        df = pl.DataFrame({"payment": [1000.0], "periods": [5], "mgmt_ibr": [0.05]})
        result = IFRS16Service().calculate_lease_liability(
            df, {"payment": "payment", "periods": "periods", "management_ibr": "mgmt_ibr"}
        )
        assert result["ifrs16_lease_liability"].to_list()[0] == pytest.approx(4329.48, abs=0.01)

    def test_zero_rate_is_straight_sum(self):
        from services.ifrs16_service import IFRS16Service

        df = pl.DataFrame({"payment": [1000.0], "periods": [5], "mgmt_ibr": [0.0]})
        result = IFRS16Service().calculate_lease_liability(
            df, {"payment": "payment", "periods": "periods", "management_ibr": "mgmt_ibr"}
        )
        assert result["ifrs16_lease_liability"].to_list()[0] == pytest.approx(5000.0)

    def test_rou_asset_includes_idc_and_incentives(self):
        from services.ifrs16_service import IFRS16Service

        df = pl.DataFrame({
            "payment": [1000.0], "periods": [5], "mgmt_ibr": [0.05],
            "idc": [200.0], "incentive": [100.0],
        })
        result = IFRS16Service().calculate_lease_liability(
            df, {"payment": "payment", "periods": "periods", "management_ibr": "mgmt_ibr",
                 "initial_direct_costs": "idc", "lease_incentives": "incentive"}
        )
        liability = result["ifrs16_lease_liability"].to_list()[0]
        rou = result["ifrs16_rou_asset"].to_list()[0]
        assert rou == pytest.approx(liability + 200.0 - 100.0)

    def test_higher_management_ibr_flagged_and_quantified(self):
        from services.ifrs16_service import IFRS16Service

        df = pl.DataFrame({
            "payment": [1000.0, 1000.0], "periods": [5, 5],
            "mgmt_ibr": [0.05, 0.09], "benchmark_ibr": [0.05, 0.05],
        })
        result = IFRS16Service().calculate_lease_liability(
            df, {"payment": "payment", "periods": "periods", "management_ibr": "mgmt_ibr",
                 "benchmark_ibr": "benchmark_ibr"}
        )
        flags = result["ifrs16_ibr_flag"].to_list()
        deviations = result["ifrs16_ibr_deviation_bps"].to_list()
        understatements = result["ifrs16_liability_understatement"].to_list()

        assert flags == [False, True]
        assert deviations[0] == pytest.approx(0.0)
        assert deviations[1] == pytest.approx(400.0)
        # A higher IBR discounts more heavily -> lower recorded liability
        # than the benchmark rate would produce -> positive understatement.
        assert understatements[1] > 0
        assert understatements[0] == pytest.approx(0.0)

    def test_no_benchmark_skips_ibr_check_columns(self):
        from services.ifrs16_service import IFRS16Service

        df = pl.DataFrame({"payment": [1000.0], "periods": [5], "mgmt_ibr": [0.05]})
        result = IFRS16Service().calculate_lease_liability(
            df, {"payment": "payment", "periods": "periods", "management_ibr": "mgmt_ibr"}
        )
        assert "ifrs16_lease_liability" in result.columns
        assert "ifrs16_ibr_flag" not in result.columns

    def test_missing_required_columns_returns_unchanged(self):
        from services.ifrs16_service import IFRS16Service

        df = pl.DataFrame({"payment": [1000.0]})
        result = IFRS16Service().calculate_lease_liability(df, {"payment": "payment"})
        assert "ifrs16_lease_liability" not in result.columns

    def test_custom_threshold_bps(self):
        from services.ifrs16_service import IFRS16Service

        df = pl.DataFrame({
            "payment": [1000.0], "periods": [5], "mgmt_ibr": [0.052], "benchmark_ibr": [0.05],
        })
        # 20bps deviation - not flagged at the default 50bps threshold...
        default_result = IFRS16Service().calculate_lease_liability(
            df, {"payment": "payment", "periods": "periods", "management_ibr": "mgmt_ibr",
                 "benchmark_ibr": "benchmark_ibr"}
        )
        assert default_result["ifrs16_ibr_flag"].to_list() == [False]

        # ...but flagged with a tighter 10bps threshold.
        tight_result = IFRS16Service().calculate_lease_liability(
            df, {"payment": "payment", "periods": "periods", "management_ibr": "mgmt_ibr",
                 "benchmark_ibr": "benchmark_ibr"}, threshold_bps=10.0,
        )
        assert tight_result["ifrs16_ibr_flag"].to_list() == [True]
