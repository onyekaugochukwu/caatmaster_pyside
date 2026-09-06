"""
Tests for IFRS 15 Service - CUSUM margin-shift detection and revenue
timing-gap check.
"""
import pytest
import polars as pl
from datetime import date, timedelta


class TestDetectMarginShiftsCusum:
    def _dates(self, n, start=date(2024, 1, 1), step_days=30):
        d = start
        out = [d]
        for _ in range(n - 1):
            d = d + timedelta(days=step_days)
            out.append(d)
        return out

    def test_stable_margin_never_flagged(self):
        from services.ifrs15_service import IFRS15Service

        n = 12
        revenue = [1000.0] * n
        cost = [700.0] * n  # constant 30% margin, no shift at all
        df = pl.DataFrame({"revenue": revenue, "cost": cost, "period": self._dates(n)})
        result = IFRS15Service().detect_margin_shifts_cusum(df, "revenue", "cost", "period")
        assert not any(result["ifrs15_cusum_flag"].to_list())

    def test_sustained_shift_eventually_flagged(self):
        from services.ifrs15_service import IFRS15Service

        stable_margin = [0.30] * 10
        shifted_margin = [0.05] * 8  # large, sustained drop
        margins = stable_margin + shifted_margin
        revenue = [1000.0] * len(margins)
        cost = [r * (1 - m) for r, m in zip(revenue, margins)]
        df = pl.DataFrame({
            "contract": ["C1"] * len(margins), "revenue": revenue, "cost": cost,
            "period": self._dates(len(margins)),
        })
        result = IFRS15Service().detect_margin_shifts_cusum(df, "revenue", "cost", "period", group_col="contract")
        flags = result.sort("period")["ifrs15_cusum_flag"].to_list()
        # Should never flag during the stable run, and should flag at least
        # once somewhere in the shifted tail.
        assert not any(flags[:10])
        assert any(flags[10:])

    def test_independent_baseline_per_group(self):
        from services.ifrs15_service import IFRS15Service

        n = 12
        # Two contracts with genuinely different, but each internally
        # stable, margins - grouping must not let one contract's baseline
        # bleed into the other's.
        df = pl.DataFrame({
            "contract": ["A"] * n + ["B"] * n,
            "revenue": [1000.0] * (n * 2),
            "cost": [700.0] * n + [200.0] * n,
            "period": self._dates(n) + self._dates(n),
        })
        result = IFRS15Service().detect_margin_shifts_cusum(df, "revenue", "cost", "period", group_col="contract")
        assert not any(result["ifrs15_cusum_flag"].to_list())

    def test_zero_revenue_produces_null_margin_not_crash(self):
        from services.ifrs15_service import IFRS15Service

        df = pl.DataFrame({
            "revenue": [1000.0, 0.0, 1000.0], "cost": [700.0, 0.0, 700.0],
            "period": self._dates(3),
        })
        result = IFRS15Service().detect_margin_shifts_cusum(df, "revenue", "cost", "period")
        margins = result.sort("period")["ifrs15_margin"].to_list()
        assert margins[1] is None

    def test_missing_columns_returns_unchanged(self):
        from services.ifrs15_service import IFRS15Service

        df = pl.DataFrame({"revenue": [1.0]})
        result = IFRS15Service().detect_margin_shifts_cusum(df, "revenue", "cost", "period")
        assert "ifrs15_margin" not in result.columns

    def test_row_order_preserved(self):
        from services.ifrs15_service import IFRS15Service

        n = 5
        df = pl.DataFrame({
            "id": list(range(n)), "revenue": [1000.0] * n, "cost": [700.0] * n,
            "period": self._dates(n),
        })
        result = IFRS15Service().detect_margin_shifts_cusum(df, "revenue", "cost", "period")
        assert result["id"].to_list() == list(range(n))


class TestDetectRevenueTimingGap:
    def test_recognized_before_delivery_flagged(self):
        from services.ifrs15_service import IFRS15Service

        df = pl.DataFrame({
            "rev_date": [date(2024, 1, 1)], "delivery_date": [date(2024, 1, 15)],
        })
        result = IFRS15Service().detect_revenue_timing_gap(df, "rev_date", "delivery_date")
        assert result["ifrs15_timing_gap_days"].to_list() == [-14]
        assert result["ifrs15_premature_recognition_flag"].to_list() == [True]

    def test_same_day_not_flagged(self):
        from services.ifrs15_service import IFRS15Service

        df = pl.DataFrame({"rev_date": [date(2024, 1, 10)], "delivery_date": [date(2024, 1, 10)]})
        result = IFRS15Service().detect_revenue_timing_gap(df, "rev_date", "delivery_date")
        assert result["ifrs15_premature_recognition_flag"].to_list() == [False]

    def test_threshold_allows_small_buffer(self):
        from services.ifrs15_service import IFRS15Service

        df = pl.DataFrame({"rev_date": [date(2024, 1, 8)], "delivery_date": [date(2024, 1, 10)]})
        result = IFRS15Service().detect_revenue_timing_gap(df, "rev_date", "delivery_date", threshold_days=3)
        assert result["ifrs15_premature_recognition_flag"].to_list() == [False]

    def test_recognized_after_delivery_not_flagged(self):
        from services.ifrs15_service import IFRS15Service

        df = pl.DataFrame({"rev_date": [date(2024, 1, 20)], "delivery_date": [date(2024, 1, 10)]})
        result = IFRS15Service().detect_revenue_timing_gap(df, "rev_date", "delivery_date")
        assert result["ifrs15_timing_gap_days"].to_list() == [10]
        assert result["ifrs15_premature_recognition_flag"].to_list() == [False]

    def test_missing_columns_returns_unchanged(self):
        from services.ifrs15_service import IFRS15Service

        df = pl.DataFrame({"rev_date": [date(2024, 1, 1)]})
        result = IFRS15Service().detect_revenue_timing_gap(df, "rev_date", "delivery_date")
        assert "ifrs15_timing_gap_days" not in result.columns
