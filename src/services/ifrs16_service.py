"""
IFRS 16 Service for CAATmaster
Implements lease liability / ROU asset calculation from a lease schedule,
and an incremental borrowing rate (IBR) reasonableness check against a
user-supplied benchmark rate.
"""
import polars as pl
from typing import Dict, Optional, Any


def _pv_ordinary_annuity(payment: pl.Expr, rate: pl.Expr, periods: pl.Expr) -> pl.Expr:
    """Present value of an ordinary annuity (payments at period end):
    PV = payment * (1 - (1+rate)^-periods) / rate, with the rate=0 case
    (undefined division) handled as a straight sum of payments."""
    return (
        pl.when(rate == 0)
        .then(payment * periods)
        .otherwise(payment * (1 - (1 + rate) ** (-periods)) / rate)
    )


class IFRS16Service:
    """Service for IFRS 16 lease liability and IBR analytics"""

    def calculate_lease_liability(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        threshold_bps: float = 50.0,
    ) -> pl.DataFrame:
        """
        Calculate the lease liability (and ROU asset) as the present value
        of remaining lease payments, one row per lease. Optionally,
        recalculates the same liability using a benchmark rate (e.g.
        risk-free rate + credit spread, supplied by the user - this does
        NOT build or assume a credit-spread model itself) and flags leases
        whose management-selected IBR deviates from it by more than a
        threshold, quantifying the resulting liability difference.

        Args:
            df: Input DataFrame, one row per lease.
            mapping: Column mapping.
                Required: 'payment' (periodic payment amount),
                          'periods' (number of remaining payment periods),
                          'management_ibr' (decimal rate per period, e.g.
                          0.005 for a 6%/yr rate on monthly payments).
                Optional: 'benchmark_ibr' (a rate, in the same periodicity,
                          to compare management's IBR against - triggers
                          the reasonableness check when present),
                          'initial_direct_costs', 'lease_incentives'
                          (both roll into the ROU asset, not the liability).
            threshold_bps: Basis points of IBR deviation above which
                ifrs16_ibr_flag is raised. A deviation this size is a
                starting point for follow-up, not proof of misstatement -
                IBR estimation legitimately varies by lease term/security.

        Returns:
            DataFrame with 'ifrs16_lease_liability', 'ifrs16_rou_asset',
            and - if benchmark_ibr is mapped - 'ifrs16_benchmark_liability',
            'ifrs16_ibr_deviation_bps', 'ifrs16_liability_understatement'
            (benchmark liability minus management's; positive means
            management's higher IBR produced a lower recorded liability
            than the benchmark rate would have), and 'ifrs16_ibr_flag'.
        """
        payment_col = mapping.get('payment')
        periods_col = mapping.get('periods')
        ibr_col = mapping.get('management_ibr')
        required = [payment_col, periods_col, ibr_col]
        if not all(required) or not all(c in df.columns for c in required):
            return df

        df = df.with_columns(
            _pv_ordinary_annuity(pl.col(payment_col), pl.col(ibr_col), pl.col(periods_col))
            .alias("ifrs16_lease_liability")
        )

        rou_expr = pl.col("ifrs16_lease_liability")
        idc_col = mapping.get('initial_direct_costs')
        incentive_col = mapping.get('lease_incentives')
        if idc_col and idc_col in df.columns:
            rou_expr = rou_expr + pl.col(idc_col)
        if incentive_col and incentive_col in df.columns:
            rou_expr = rou_expr - pl.col(incentive_col)
        df = df.with_columns(rou_expr.alias("ifrs16_rou_asset"))

        benchmark_col = mapping.get('benchmark_ibr')
        if benchmark_col and benchmark_col in df.columns:
            df = df.with_columns(
                _pv_ordinary_annuity(pl.col(payment_col), pl.col(benchmark_col), pl.col(periods_col))
                .alias("ifrs16_benchmark_liability")
            )
            df = df.with_columns([
                ((pl.col(ibr_col) - pl.col(benchmark_col)) * 10000).alias("ifrs16_ibr_deviation_bps"),
                (pl.col("ifrs16_benchmark_liability") - pl.col("ifrs16_lease_liability"))
                .alias("ifrs16_liability_understatement"),
            ])
            df = df.with_columns(
                (pl.col("ifrs16_ibr_deviation_bps").abs() > threshold_bps).alias("ifrs16_ibr_flag")
            )

        return df
