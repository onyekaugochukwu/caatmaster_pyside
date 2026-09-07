"""
IFRS 15 Service for CAATmaster
Implements CUSUM change-point detection on a contract's revenue-to-cost
margin over time, and a revenue-recognition-timing gap check against
delivery/shipment date.
"""
import polars as pl
from typing import Dict, List, Optional, Any


def _linear_percentile(sorted_values: List[float], pct: float) -> float:
    """Linear-interpolation percentile (matches numpy's default 'linear'
    method) over an already-sorted list, without adding a numpy
    dependency to this module for a single call site."""
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (n - 1)
    lo = int(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def _cusum_flags(values: List[Optional[float]], k_multiplier: float, h_multiplier: float) -> List[bool]:
    """Two-sided CUSUM control-chart test for a shift in the level of a
    sequence. k (the "slack") and h (the decision threshold) are both
    expressed as multiples of the sequence's own scale estimate, so the
    same multipliers work regardless of the margin's magnitude. Returns
    one flag per input position (False for the first position and any
    null values, which can't establish a baseline or be evaluated).

    The baseline location is the median, and the baseline scale is the
    interquartile range, scaled by 1/1.349 for consistency with the
    standard deviation of a normal distribution - not the mean and
    standard deviation. This is a retrospective, whole-history scan, not
    a monitoring chart with a known-good baseline period established
    ahead of time - the shift being searched for is necessarily included
    in the very data used to decide what "normal" looks like. The mean
    and standard deviation are themselves pulled toward and inflated by
    a real shift, which can mask the shift that inflated them: a single
    sharp period-over-period collapse can widen the standard deviation
    enough that the collapse itself no longer clears a multiple of it,
    so a genuine shift can go undetected specifically because it was
    large enough to distort its own baseline. Verified directly against
    exactly this failure mode - a sustained ~40% margin collapsing to
    15% in the final period of a short, six-period contract history,
    which the mean/standard-deviation version missed entirely at the
    default threshold.

    The median and the interquartile range are far more resistant to
    this self-contamination, since a single outlying period has to be
    one of the majority of points before it can move either one much.
    The median absolute deviation (MAD) was tried first and rejected: it
    shares the interquartile range's resistance to a small, short-lived
    outlier, but degenerates to exactly zero whenever a sustained shift
    covers close to half or more of the population - a longer-running,
    evenly-split shift is exactly the case this check most needs to
    catch, and MAD goes blind to it in a way the interquartile range,
    which only degenerates past a 25% split rather than a 50% split,
    does not. Both failure modes are covered by this module's own tests."""
    n = len(values)
    flags = [False] * n
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return flags

    clean_sorted = sorted(clean)
    m = len(clean_sorted)
    median = (clean_sorted[m // 2] if m % 2 else (clean_sorted[m // 2 - 1] + clean_sorted[m // 2]) / 2)
    q1 = _linear_percentile(clean_sorted, 25)
    q3 = _linear_percentile(clean_sorted, 75)
    scale = (q3 - q1) / 1.349
    # A genuinely constant sequence's interquartile range is theoretically
    # 0, but repeated floating-point addition rarely lands on exactly 0 -
    # an unguarded "== 0" left scale at a near-zero value for a perfectly
    # flat margin, which made k/h themselves near-zero and let pure
    # rounding noise in (v - median) accumulate past that threshold,
    # flagging a "shift" in data that never moved at all.
    if scale < 1e-9:
        return flags

    k = k_multiplier * scale
    h = h_multiplier * scale
    pos = 0.0
    neg = 0.0
    for i, v in enumerate(values):
        if v is None:
            continue
        pos = max(0.0, pos + (v - median) - k)
        neg = min(0.0, neg + (v - median) + k)
        if pos > h or abs(neg) > h:
            flags[i] = True
    return flags


class IFRS15Service:
    """Service for IFRS 15 revenue recognition analytics"""

    def detect_margin_shifts_cusum(
        self,
        df: pl.DataFrame,
        revenue_col: str,
        cost_col: str,
        date_col: str,
        group_col: Optional[str] = None,
        k_multiplier: float = 0.5,
        h_multiplier: float = 4.0,
    ) -> pl.DataFrame:
        """
        Detect a change point in a contract's revenue-to-cost margin over
        time via a CUSUM control chart - catches a sudden, sustained shift
        (e.g. cost-shifting between periods to manage recognized margin)
        that a simple period-over-period threshold would miss, without
        needing a labeled training set the way an ML change-point model
        would.

        Args:
            df: Input DataFrame, one row per contract per period.
            revenue_col, cost_col: Numeric columns for the period.
            date_col: Period date/sequence column - rows are sorted by
                this within each group before the CUSUM is computed.
            group_col: Optional contract/customer id - when given, the
                CUSUM baseline (mean/std) and detection run independently
                per group rather than across the whole population.
            k_multiplier / h_multiplier: CUSUM slack/threshold as
                multiples of the margin's own standard deviation. Higher
                h means fewer, more confident flags.

        Returns:
            DataFrame with 'ifrs15_margin' ((revenue-cost)/revenue; null
            where revenue is 0) and 'ifrs15_cusum_flag'.
        """
        required = [revenue_col, cost_col, date_col] + ([group_col] if group_col else [])
        if not all(c and c in df.columns for c in required):
            return df

        working = df.with_row_index("_ifrs15_row_idx")
        working = working.with_columns(
            pl.when(pl.col(revenue_col) != 0)
            .then((pl.col(revenue_col) - pl.col(cost_col)) / pl.col(revenue_col))
            .otherwise(None)
            .alias("ifrs15_margin")
        )

        groups = working.partition_by(group_col, maintain_order=True) if group_col else [working]

        result_frames = []
        for group_df in groups:
            group_df = group_df.sort(date_col)
            margins = group_df["ifrs15_margin"].to_list()
            flags = _cusum_flags(margins, k_multiplier, h_multiplier)
            group_df = group_df.with_columns(pl.Series("ifrs15_cusum_flag", flags, dtype=pl.Boolean))
            result_frames.append(group_df)

        combined = pl.concat(result_frames).sort("_ifrs15_row_idx").drop("_ifrs15_row_idx")
        return combined

    def detect_revenue_timing_gap(
        self,
        df: pl.DataFrame,
        revenue_date_col: str,
        delivery_date_col: str,
        threshold_days: int = 0,
    ) -> pl.DataFrame:
        """
        Flag revenue recognized materially before the performance
        obligation was satisfied (delivery/shipment) - a premature
        (bill-and-hold-style) recognition risk under the IFRS 15 transfer-
        of-control test.

        Args:
            revenue_date_col: Date revenue was recognized/booked.
            delivery_date_col: Date the performance obligation was
                satisfied (shipment/delivery/acceptance).
            threshold_days: Recognized-before-delivery gap, in days,
                before flagging. 0 flags any recognition before delivery
                at all; a positive value allows a small, explainable
                buffer (e.g. same-week paperwork lag).

        Returns:
            DataFrame with 'ifrs15_timing_gap_days' (recognition date
            minus delivery date; negative means recognized early) and
            'ifrs15_premature_recognition_flag'.
        """
        if revenue_date_col not in df.columns or delivery_date_col not in df.columns:
            return df

        df = df.with_columns(
            (pl.col(revenue_date_col) - pl.col(delivery_date_col)).dt.total_days()
            .alias("ifrs15_timing_gap_days")
        )
        df = df.with_columns(
            (pl.col("ifrs15_timing_gap_days") < -threshold_days).fill_null(False)
            .alias("ifrs15_premature_recognition_flag")
        )
        return df
