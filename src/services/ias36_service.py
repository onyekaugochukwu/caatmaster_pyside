"""
IAS 36 Service for CAATmaster
Implements a reverse-DCF impairment analytic: given a CGU's carrying
value, discount rate, and explicit-period cash flow forecast, solve for
the terminal growth rate that forecast implicitly requires to avoid
impairment - then compare it to a growth benchmark (e.g. GDP growth).
"""
import polars as pl
from typing import Dict, List, Optional, Any

from scipy.optimize import brentq


def _solve_implied_growth_rate(
    carrying_value: Optional[float],
    discount_rate: Optional[float],
    cash_flows: List[Optional[float]],
) -> Optional[float]:
    """Solve g such that:
        CV = sum_{t=1}^{n} CF_t / (1+r)^t + [CF_n * (1+g) / (r-g)] / (1+r)^n
    via bisection (scipy.optimize.brentq) rather than closed form, since
    the equation isn't linear in g once more than one explicit cash flow
    is involved. Returns None (never a fabricated number) when the
    carrying value, discount rate, or cash flows are missing/invalid, or
    when no root exists in a plausible range - e.g. the explicit cash
    flows alone already exceed the carrying value even at 0% terminal
    growth, meaning no impairment risk exists at any reasonable growth
    assumption.
    """
    clean_flows = [cf for cf in cash_flows if cf is not None]
    if (
        carrying_value is None or discount_rate is None
        or not clean_flows or len(clean_flows) != len(cash_flows)
        or discount_rate <= 0 or carrying_value <= 0
    ):
        return None

    n = len(clean_flows)

    def npv_minus_carrying_value(g: float) -> float:
        pv_explicit = sum(cf / (1 + discount_rate) ** t for t, cf in enumerate(clean_flows, start=1))
        terminal_value = clean_flows[-1] * (1 + g) / (discount_rate - g)
        pv_terminal = terminal_value / (1 + discount_rate) ** n
        return pv_explicit + pv_terminal - carrying_value

    lower_bound, upper_bound = -0.5, discount_rate - 1e-6
    try:
        f_lower = npv_minus_carrying_value(lower_bound)
        f_upper = npv_minus_carrying_value(upper_bound)
    except (ZeroDivisionError, OverflowError):
        return None

    if f_lower * f_upper > 0:
        # No sign change across the search range - either the cash flows
        # already clear the carrying value at every plausible growth rate
        # (no implied-growth risk to report), or a solution would require
        # an implausible rate outside [-50%, discount_rate). Either way,
        # reporting None is more honest than forcing a fit.
        return None

    try:
        return brentq(npv_minus_carrying_value, lower_bound, upper_bound, xtol=1e-6)
    except ValueError:
        return None


class IAS36Service:
    """Service for IAS 36 impairment analytics"""

    def calculate_implied_growth_rate(
        self,
        df: pl.DataFrame,
        carrying_value_col: str,
        discount_rate_col: str,
        cash_flow_columns: List[str],
        benchmark_growth_col: Optional[str] = None,
        benchmark_growth_value: Optional[float] = None,
        flag_threshold_pp: float = 2.0,
    ) -> pl.DataFrame:
        """
        Reverse-DCF: for each CGU/row, solve for the terminal growth rate
        implied by its carrying value, discount rate, and explicit-period
        cash flow forecast - then flag rows whose implied growth exceeds
        a benchmark (e.g. long-run GDP growth) by more than a threshold.

        Args:
            df: Input DataFrame (one row per CGU/testing unit).
            carrying_value_col: Column with the CGU's carrying value.
            discount_rate_col: Column with the discount rate (decimal,
                e.g. 0.10 for 10%).
            cash_flow_columns: Ordered list of explicit forecast-year cash
                flow columns, e.g. ["cf_y1", "cf_y2", "cf_y3", "cf_y4", "cf_y5"].
                A single column is valid too (a one-year "sustainable cash
                flow" model).
            benchmark_growth_col: Optional per-row benchmark growth rate
                column (e.g. the CGU's country/industry long-run growth).
            benchmark_growth_value: A single benchmark value applied to
                every row, used only when benchmark_growth_col isn't given.
            flag_threshold_pp: Percentage points above the benchmark
                before flagging. This is a starting point for follow-up
                audit judgment, not a bright-line pass/fail test by itself
                - a CGU can legitimately have above-benchmark growth
                prospects, and this alone doesn't prove impairment either
                way.

        Returns:
            DataFrame with 'ias36_implied_growth_rate' (decimal; null
            where no root could be solved for - never a fabricated
            number), and, if a benchmark is supplied,
            'ias36_benchmark_growth_rate', 'ias36_growth_gap_pp', and
            'ias36_flag'.
        """
        required = [carrying_value_col, discount_rate_col] + cash_flow_columns
        if not all(col in df.columns for col in required):
            return df

        carrying_values = df[carrying_value_col].to_list()
        discount_rates = df[discount_rate_col].to_list()
        cash_flow_lists = [df[col].to_list() for col in cash_flow_columns]

        implied_rates = []
        for i in range(len(df)):
            row_cash_flows = [cf_col[i] for cf_col in cash_flow_lists]
            implied_rates.append(
                _solve_implied_growth_rate(carrying_values[i], discount_rates[i], row_cash_flows)
            )

        result = df.with_columns(
            pl.Series("ias36_implied_growth_rate", implied_rates, dtype=pl.Float64)
        )

        if benchmark_growth_col and benchmark_growth_col in df.columns:
            result = result.with_columns(
                pl.col(benchmark_growth_col).cast(pl.Float64).alias("ias36_benchmark_growth_rate")
            )
        elif benchmark_growth_value is not None:
            result = result.with_columns(
                pl.lit(float(benchmark_growth_value)).alias("ias36_benchmark_growth_rate")
            )
        else:
            return result

        result = result.with_columns(
            ((pl.col("ias36_implied_growth_rate") - pl.col("ias36_benchmark_growth_rate")) * 100)
            .alias("ias36_growth_gap_pp")
        )
        result = result.with_columns(
            (pl.col("ias36_growth_gap_pp") > flag_threshold_pp).fill_null(False).alias("ias36_flag")
        )
        return result
