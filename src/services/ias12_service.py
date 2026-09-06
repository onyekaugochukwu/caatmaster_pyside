"""
IAS 12 Service for CAATmaster
Implements a deferred tax asset (DTA) recoverability check: given a
recognized DTA balance, the applicable tax rate, and the number of years
available to utilize it, solves for the average annual taxable profit the
balance requires - then compares that to a benchmark (historical or
forecast) profit figure.
"""
import polars as pl
from typing import Dict, Optional, Any


class IAS12Service:
    """Service for IAS 12 income tax analytics"""

    def calculate_required_taxable_profit(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        benchmark_profit_col: Optional[str] = None,
        benchmark_profit_value: Optional[float] = None,
        flag_threshold_pct: float = 20.0,
    ) -> pl.DataFrame:
        """
        Solve for the average annual taxable profit a recognized DTA
        balance requires to be fully utilized within its available
        window, then flag where that requirement exceeds a benchmark
        profit figure by more than a threshold - a starting point for
        follow-up on recoverability (IAS 12.24/.34), not a standalone
        proof that a DTA is unsupportable.

        required_annual_taxable_profit = dta_balance / (tax_rate * utilization_years)

        This is straight algebra (no discounting - DTAs are not
        discounted under IAS 12, unlike a lease liability or an
        impairment cash flow model), so no root-finding is needed.

        Args:
            df: Input DataFrame, one row per DTA balance (e.g. per
                jurisdiction or per temporary difference/loss carryforward).
            mapping: Column mapping.
                Required: 'dta_balance', 'tax_rate' (decimal, e.g. 0.25),
                          'utilization_years' (years remaining to use the
                          balance, e.g. a loss carryforward expiry window).
                Optional: 'benchmark_profit' - a per-row benchmark taxable
                          profit column (e.g. that entity's own historical
                          average); used instead of benchmark_profit_value
                          when mapped.
            benchmark_profit_col: Same as mapping['benchmark_profit'] but
                supplied directly - kept as a separate parameter (not
                folded into mapping) for the same reason IAS36's
                benchmark_growth_col is separate: a single population-wide
                benchmark is a different kind of input than a per-row one.
            benchmark_profit_value: A single benchmark applied to every
                row, used only when neither benchmark column is given.
            flag_threshold_pct: % by which the required profit must exceed
                the benchmark before flagging.

        Returns:
            DataFrame with 'ias12_required_annual_taxable_profit' (null
            where tax_rate or utilization_years is 0), and, if a benchmark
            is supplied, 'ias12_benchmark_profit', 'ias12_shortfall_pct'
            (positive means the required profit exceeds the benchmark),
            and 'ias12_recoverability_flag'.
        """
        dta_col = mapping.get('dta_balance')
        rate_col = mapping.get('tax_rate')
        years_col = mapping.get('utilization_years')
        required = [dta_col, rate_col, years_col]
        if not all(required) or not all(c in df.columns for c in required):
            return df

        df = df.with_columns(
            pl.when((pl.col(rate_col) != 0) & (pl.col(years_col) != 0))
            .then(pl.col(dta_col) / (pl.col(rate_col) * pl.col(years_col)))
            .otherwise(None)
            .alias("ias12_required_annual_taxable_profit")
        )

        benchmark_col = benchmark_profit_col or mapping.get('benchmark_profit')
        if benchmark_col and benchmark_col in df.columns:
            df = df.with_columns(pl.col(benchmark_col).cast(pl.Float64).alias("ias12_benchmark_profit"))
        elif benchmark_profit_value is not None:
            df = df.with_columns(pl.lit(float(benchmark_profit_value)).alias("ias12_benchmark_profit"))
        else:
            return df

        df = df.with_columns(
            pl.when(pl.col("ias12_benchmark_profit") != 0)
            .then(
                (pl.col("ias12_required_annual_taxable_profit") - pl.col("ias12_benchmark_profit"))
                / pl.col("ias12_benchmark_profit").abs() * 100
            )
            .otherwise(None)
            .alias("ias12_shortfall_pct")
        )
        df = df.with_columns(
            (pl.col("ias12_shortfall_pct") > flag_threshold_pct).fill_null(False)
            .alias("ias12_recoverability_flag")
        )
        return df
