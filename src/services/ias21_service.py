"""
IAS 21 Service for CAATmaster
Implements a foreign-currency rate consistency check: each transaction's
booked FX rate is compared against a benchmark rate (e.g. the published
spot/closing rate for that date/currency pair), quantifying the resulting
$ misstatement from using the wrong rate.
"""
import polars as pl
from typing import Dict, Optional, Any


class IAS21Service:
    """Service for IAS 21 foreign currency analytics"""

    def detect_fx_rate_deviations(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        tolerance_pct: float = 1.0,
    ) -> pl.DataFrame:
        """
        Flag a transaction whose booked FX rate deviates from a benchmark
        rate by more than a tolerance. Expects the benchmark rate to
        already be present on each row - typically via joining the
        transaction log to a daily rate table on date/currency first
        (e.g. via the existing Join Datasets step) - this does not itself
        look up or fetch any rate.

        Args:
            df: Input DataFrame, one row per FX-denominated transaction.
            mapping: Column mapping.
                Required: 'booked_rate' (the rate actually used to record
                          the transaction), 'benchmark_rate' (the rate it
                          should have used).
                Optional: 'local_amount' (the transaction amount in local/
                          foreign currency - when mapped, quantifies the
                          $ variance between the booked and benchmark-rate
                          restated amounts).
            tolerance_pct: % deviation from the benchmark rate above which
                ifrs21_fx_rate_flag... (see ias21_fx_rate_flag) is raised.

        Returns:
            DataFrame with 'ias21_rate_deviation_pct' (null where the
            benchmark rate is 0) and 'ias21_fx_rate_flag'; if local_amount
            is mapped, also 'ias21_fx_amount_variance' (benchmark-rate
            restated amount minus the booked-rate amount - positive means
            the booked amount was understated relative to the benchmark
            rate).
        """
        booked_col = mapping.get('booked_rate')
        benchmark_col = mapping.get('benchmark_rate')
        if not booked_col or not benchmark_col or booked_col not in df.columns or benchmark_col not in df.columns:
            return df

        df = df.with_columns(
            pl.when(pl.col(benchmark_col) != 0)
            .then((pl.col(booked_col) - pl.col(benchmark_col)) / pl.col(benchmark_col) * 100)
            .otherwise(None)
            .alias("ias21_rate_deviation_pct")
        )
        df = df.with_columns(
            (pl.col("ias21_rate_deviation_pct").abs() > tolerance_pct).fill_null(False)
            .alias("ias21_fx_rate_flag")
        )

        local_amount_col = mapping.get('local_amount')
        if local_amount_col and local_amount_col in df.columns:
            df = df.with_columns(
                (
                    (pl.col(local_amount_col) * pl.col(benchmark_col))
                    - (pl.col(local_amount_col) * pl.col(booked_col))
                ).alias("ias21_fx_amount_variance")
            )

        return df
