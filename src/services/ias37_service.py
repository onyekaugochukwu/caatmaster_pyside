"""
IAS 37 Service for CAATmaster
Implements a YoY provision trend-break check, optionally corroborated
against a joined-in legal-claims/settlement indicator.
"""
import polars as pl
from typing import Dict, Optional, Any


class IAS37Service:
    """Service for IAS 37 provisions analytics"""

    def detect_provision_trend_breaks(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        change_threshold_pct: float = 30.0,
    ) -> pl.DataFrame:
        """
        Flag a provision category whose year-over-year balance changed by
        more than a threshold in either direction. A large unexplained
        DECREASE is the higher-risk case (potential under-provisioning /
        income smoothing), but a large increase is also worth follow-up,
        so both directions are flagged.

        Args:
            df: Input DataFrame, one row per provision category (or per
                category per subsidiary/period).
            mapping: {'prior_year': col, 'current_year': col} balance
                columns.
            change_threshold_pct: Absolute % change above which
                ias37_trend_break_flag is raised. A heuristic starting
                point for follow-up, not a standard-defined bright line -
                a genuine settlement or reassessed obligation can legitimately
                move a provision by more than this.

        Returns:
            DataFrame with 'ias37_yoy_change_pct' (null where prior_year
            is 0 - percentage change is undefined, not "infinite") and
            'ias37_trend_break_flag'.
        """
        prior_col = mapping.get('prior_year')
        current_col = mapping.get('current_year')
        if not prior_col or not current_col or prior_col not in df.columns or current_col not in df.columns:
            return df

        df = df.with_columns(
            pl.when(pl.col(prior_col) != 0)
            .then((pl.col(current_col) - pl.col(prior_col)) / pl.col(prior_col) * 100)
            .otherwise(None)
            .alias("ias37_yoy_change_pct")
        )
        df = df.with_columns(
            (pl.col("ias37_yoy_change_pct").abs() > change_threshold_pct).fill_null(False)
            .alias("ias37_trend_break_flag")
        )
        return df

    def cross_check_legal_claims(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        change_threshold_pct: float = 30.0,
    ) -> pl.DataFrame:
        """
        Runs detect_provision_trend_breaks(), then narrows the flagged
        DECREASES to those with no corroborating settlement on the same
        row - i.e. a drop that lines up with a recorded legal settlement
        is left flagged but distinguished from one that has no apparent
        cause. Expects the provision population to already be joined to
        settlement/legal-claims data (e.g. via the existing Join Datasets
        step); this does not itself join or search any text for evidence
        of an obligation.

        Args:
            mapping: Same as detect_provision_trend_breaks(), plus
                'settlement_flag' - a boolean/truthy column already
                present on the row indicating a settlement was recorded
                for that category/period.

        Returns:
            DataFrame with everything detect_provision_trend_breaks()
            returns, plus 'ias37_unexplained_decrease_flag' - true only
            for a flagged decrease with no recorded settlement.
        """
        df = self.detect_provision_trend_breaks(df, mapping, change_threshold_pct)
        settlement_col = mapping.get('settlement_flag')
        if settlement_col and settlement_col in df.columns and "ias37_trend_break_flag" in df.columns:
            is_decrease = pl.col("ias37_yoy_change_pct") < 0
            has_settlement = pl.col(settlement_col).cast(pl.Boolean, strict=False).fill_null(False)
            df = df.with_columns(
                (pl.col("ias37_trend_break_flag") & is_decrease & ~has_settlement)
                .alias("ias37_unexplained_decrease_flag")
            )
        return df
