"""
Tests for SOX Service - Segregation of Duties (pairwise and N-way) and
User Access Review.
"""
import pytest
import polars as pl
from datetime import date


class TestAnalyzeSodConflictsPairwise:
    @pytest.fixture
    def transaction_log(self):
        return pl.DataFrame({
            "user": ["u1", "u1", "u1", "u2", "u2", "u3"],
            "action": ["Create Vendor", "Approve Invoice", "Process Payment",
                       "Create Vendor", "Approve Invoice", "Create Vendor"],
        })

    def test_legacy_role_a_role_b_flags_both_users(self, transaction_log):
        from services.sox_service import SoxService

        result = SoxService().analyze_sod_conflicts(
            transaction_log, "user", "action",
            [{"role_a": "Create Vendor", "role_b": "Approve Invoice"}],
        )
        flags = dict(zip(
            result["user"].to_list(), result["sod_conflict_found"].to_list()
        ))
        assert flags["u1"] is True
        assert flags["u2"] is True
        assert flags["u3"] is False

    def test_no_conflicts_returns_all_false(self, transaction_log):
        from services.sox_service import SoxService

        result = SoxService().analyze_sod_conflicts(transaction_log, "user", "action", [])
        assert not result["sod_conflict_found"].any()

    def test_missing_columns_returns_df_unchanged(self, transaction_log):
        from services.sox_service import SoxService

        result = SoxService().analyze_sod_conflicts(transaction_log, "missing_col", "action", [])
        assert "sod_conflict_found" not in result.columns


class TestAnalyzeSodConflictsNWay:
    @pytest.fixture
    def transaction_log(self):
        return pl.DataFrame({
            "user": ["u1", "u1", "u1", "u2", "u2", "u3"],
            "action": ["Create Vendor", "Approve Invoice", "Process Payment",
                       "Create Vendor", "Approve Invoice", "Create Vendor"],
        })

    def test_three_way_combination_requires_all_roles(self, transaction_log):
        from services.sox_service import SoxService

        result = SoxService().analyze_sod_conflicts(
            transaction_log, "user", "action",
            [{"roles": ["Create Vendor", "Approve Invoice", "Process Payment"], "severity": "Critical"}],
        )
        flags = dict(zip(result["user"].to_list(), result["sod_conflict_found"].to_list()))
        # Only u1 holds all three roles - u2 only holds two of them.
        assert flags["u1"] is True
        assert flags["u2"] is False
        assert flags["u3"] is False

    def test_detail_text_includes_severity_and_all_roles(self, transaction_log):
        from services.sox_service import SoxService

        result = SoxService().analyze_sod_conflicts(
            transaction_log, "user", "action",
            [{"roles": ["Create Vendor", "Approve Invoice", "Process Payment"], "severity": "Critical"}],
        )
        detail = dict(zip(result["user"].to_list(), result["sod_conflict_detail"].to_list()))
        assert detail["u1"] == "Critical: Create Vendor + Approve Invoice + Process Payment"


class TestAccessReviewAnalysis:
    @pytest.fixture
    def access_log(self):
        return pl.DataFrame({
            "user": ["a", "b", "c", "d"],
            "status": ["Active", "Terminated", " inactive ", "Active"],
            "activity_date": [date(2024, 1, 1), date(2024, 5, 1), date(2024, 3, 1), date(2024, 2, 1)],
            "termination_date": [None, date(2024, 4, 1), None, date(2024, 6, 1)],
        })

    def test_flags_terminated_status(self, access_log):
        from services.sox_service import SoxService

        result = SoxService().access_review_analysis(access_log, "status")
        flags = dict(zip(result["user"].to_list(), result["access_review_flag"].to_list()))
        assert flags["a"] is False
        assert flags["b"] is True

    def test_status_match_is_case_and_whitespace_insensitive(self, access_log):
        from services.sox_service import SoxService

        result = SoxService().access_review_analysis(access_log, "status")
        flags = dict(zip(result["user"].to_list(), result["access_review_flag"].to_list()))
        assert flags["c"] is True

    def test_activity_after_termination_date_flagged_even_if_status_active(self, access_log):
        from services.sox_service import SoxService

        # d's status is "Active" but has a termination_date in the future
        # relative to activity_date, so should NOT be flagged by the date
        # rule (activity predates termination).
        result = SoxService().access_review_analysis(
            access_log, "status", activity_date_col="activity_date", termination_date_col="termination_date"
        )
        flags = dict(zip(result["user"].to_list(), result["access_review_flag"].to_list()))
        assert flags["d"] is False

    def test_activity_on_or_after_termination_flagged(self):
        from services.sox_service import SoxService

        df = pl.DataFrame({
            "user": ["x"],
            "status": ["Active"],
            "activity_date": [date(2024, 6, 15)],
            "termination_date": [date(2024, 6, 1)],
        })
        result = SoxService().access_review_analysis(
            df, "status", activity_date_col="activity_date", termination_date_col="termination_date"
        )
        assert result["access_review_flag"].to_list() == [True]

    def test_missing_status_column_returns_df_unchanged(self, access_log):
        from services.sox_service import SoxService

        result = SoxService().access_review_analysis(access_log, "does_not_exist")
        assert "access_review_flag" not in result.columns

    def test_custom_terminated_values(self):
        from services.sox_service import SoxService

        df = pl.DataFrame({"user": ["a", "b"], "status": ["OnLeave", "Active"]})
        result = SoxService().access_review_analysis(df, "status", terminated_values=["OnLeave"])
        assert result["access_review_flag"].to_list() == [True, False]
