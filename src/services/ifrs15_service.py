"""
IFRS 15 Service for CAATmaster
Implements CUSUM change-point detection on a contract's revenue-to-cost
margin over time, and a revenue-recognition-timing gap check against
delivery/shipment date.
"""
import polars as pl
from typing import Dict, List, Optional, Any


def _cusum_flags(values: List[Optional[float]], k_multiplier: float, h_multiplier: float) -> List[bool]:
    """Two-sided CUSUM control-chart test for a shift in the mean of a
    sequence. k (the "slack") and h (the decision threshold) are both
    expressed as multiples of the sequence's own standard deviation, so
    the same multipliers work regardless of the margin's scale. Returns
    one flag per input position (False for the first position and any
    null values, which can't establish a baseline or be evaluated)."""
    n = len(values)
    flags = [False] * n
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return flags

    mean = sum(clean) / len(clean)
    variance = sum((v - mean) ** 2 for v in clean) / len(clean)
    std = variance ** 0.5
    # A genuinely constant sequence's std is theoretically 0, but repeated
    # floating-point addition (sum() over many equal floats) rarely lands
    # on exactly 0 - an unguarded "== 0" left std at ~1e-16 for a perfectly
    # flat margin, which made k/h themselves ~1e-16 and let pure rounding
    # noise in (v - mean) accumulate past that threshold, flagging a
    # "shift" in data that never moved at all.
    if std < 1e-9:
        return flags

    k = k_multiplier * std
    h = h_multiplier * std
    pos = 0.0
    neg = 0.0
    for i, v in enumerate(values):
        if v is None:
            continue
        pos = max(0.0, pos + (v - mean) - k)
        neg = min(0.0, neg + (v - mean) + k)
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
