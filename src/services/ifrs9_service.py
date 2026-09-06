"""
IFRS 9 Service for CAATmaster
Implements IFRS 9 Staging and Expected Credit Loss (ECL) logic.
"""
import polars as pl
from typing import Dict, List, Optional, Any
from datetime import datetime

class IFRS9Service:
    """Service for IFRS 9 staging and analysis"""

    def perform_staging(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        thresholds: Dict[str, int] = None
    ) -> pl.DataFrame:
        """
        Perform IFRS 9 Staging based on Days Past Due (DPD) or other criteria.

        Args:
            df: Input DataFrame
            mapping: Column mapping
                     Required: 'dpd' (Days Past Due) OR ('payment_date', 'due_date')
                     Optional: 'exposure' (Outstanding Balance), 'pd' (Prob Default), 'lgd' (Loss Given Default)
            thresholds: Staging thresholds
                        {'stage2_threshold': 30, 'stage3_threshold': 90}

        Returns:
            DataFrame with 'ifrs9_stage', 'ifrs9_status', and optional 'ifrs9_ecl' columns
        """
        if thresholds is None:
            thresholds = {'stage2_threshold': 30, 'stage3_threshold': 90}
            
        stage2_thresh = thresholds.get('stage2_threshold', 30)
        stage3_thresh = thresholds.get('stage3_threshold', 90)

        # 1. Calculate DPD if not provided directly
        dpd_col = mapping.get('dpd')
        
        # Helper to get actual col name
        def get_col(key):
            return mapping.get(key)
            
        # Logic to determine DPD column to use
        calc_dpd_col = "ifrs9_calculated_dpd"
        
        if dpd_col and dpd_col in df.columns:
            # Use provided DPD column
            target_dpd_col = dpd_col
            expressions = []
        else:
            # Try to calculate from dates
            payment_date = get_col('payment_date') # Or "as_of_date" / "report_date"
            due_date = get_col('due_date')
            
            if payment_date and due_date and payment_date in df.columns and due_date in df.columns:
                # Calculate DPD
                # Assuming date columns. If string, might need parsing, but we assume ETL handled types or we try cast
                # DPD = (Payment Date - Due Date).days
                # If Payment Date is missing (unpaid), use today or report date? 
                # For simplicity, assume payment_date represents the "As Of" date for the report if the loan is open
                
                # Polars date arithmetic
                expressions = [
                    (pl.col(payment_date) - pl.col(due_date)).dt.total_days().fill_null(0).alias(calc_dpd_col)
                ]
                target_dpd_col = calc_dpd_col
            else:
                # Cannot proceed without DPD
                return df

        # 2. Determine Stage
        # Stage 1: DPD <= 30 (Performing)
        # Stage 2: 30 < DPD <= 90 (Underperforming / SICR)
        # Stage 3: DPD > 90 (Non-Performing / Impaired)

        dpd_stage = (
            pl.when(pl.col(target_dpd_col) > stage3_thresh).then(3)
            .when(pl.col(target_dpd_col) > stage2_thresh).then(2)
            .otherwise(1)
        )

        # Optional: a Significant Increase in Credit Risk (SICR) trigger
        # based on relative PD deterioration since origination, not just
        # days-past-due - a loan can be a real IFRS 9 Stage 2 case (SICR)
        # while still current on payments. This can only ESCALATE a
        # Stage-1 loan to Stage 2; it never downgrades what the DPD test
        # already placed in Stage 3.
        pd_current_col = get_col('pd_current')
        pd_origination_col = get_col('pd_origination')
        sicr_multiplier = (thresholds or {}).get('sicr_pd_multiplier')
        has_sicr_pd_trigger = bool(
            pd_current_col and pd_origination_col and sicr_multiplier
            and pd_current_col in df.columns and pd_origination_col in df.columns
        )

        if has_sicr_pd_trigger:
            sicr_triggered = (pl.col(pd_current_col) / pl.col(pd_origination_col)) > sicr_multiplier
            final_stage = pl.when((dpd_stage == 1) & sicr_triggered).then(2).otherwise(dpd_stage)
        else:
            final_stage = dpd_stage

        stage_expr = final_stage.alias("ifrs9_stage")
        status_expr = (
            pl.when(final_stage == 3).then(pl.lit("Non-Performing"))
            .when(final_stage == 2).then(pl.lit("Underperforming"))
            .otherwise(pl.lit("Performing"))
            .alias("ifrs9_status")
        )

        expressions.append(stage_expr)
        expressions.append(status_expr)
        
        # 3. Calculate ECL (Expected Credit Loss)
        # ECL = EAD * PD * LGD
        # EAD: Exposure at Default (Outstanding Balance)
        # PD: Probability of Default
        # LGD: Loss Given Default
        
        ead_col = get_col('exposure')
        pd_col = get_col('pd')
        lgd_col = get_col('lgd')
        
        if ead_col and pd_col and lgd_col and \
           ead_col in df.columns and pd_col in df.columns and lgd_col in df.columns:
               
            ecl_expr = (pl.col(ead_col) * pl.col(pd_col) * pl.col(lgd_col)).alias("ifrs9_ecl_amount")
            expressions.append(ecl_expr)
            
            # Coverage Ratio = ECL / EAD
            cov_expr = (pl.col("ifrs9_ecl_amount") / pl.col(ead_col)).alias("ifrs9_coverage_ratio")
            # We need to append ecl_expr first to use it, but Polars parallelizes. 
            # Better to add separate list or use with_columns twice.
            # We'll return step 1, then step 2
            
            df_staged = df.with_columns(expressions)
            return df_staged.with_columns([
                (pl.col(ead_col) * pl.col(pd_col) * pl.col(lgd_col)).alias("ifrs9_ecl_amount")
            ]).with_columns([
                (pl.col("ifrs9_ecl_amount") / pl.col(ead_col)).alias("ifrs9_coverage_ratio")
            ])

        return df.with_columns(expressions)

    def calculate_scenario_weighted_ecl(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        weights: Dict[str, float] = None,
        variance_threshold_pct: float = 20.0,
    ) -> pl.DataFrame:
        """
        Calculate a probability-weighted ECL across base/upside/downside
        macro scenarios, rather than a single point-estimate PD - and,
        where management's own booked ECL is available, flag a material
        variance against it.

        This is a deterministic, weighted-average alternative to a full
        Monte Carlo simulation: no random sampling, same reproducible
        result on every run, and it degrades gracefully to a plain
        EAD*PD*LGD calculation if only the base scenario's PD is mapped.

        Args:
            df: Input DataFrame
            mapping: Column mapping. Required: 'exposure' (EAD), 'lgd'.
                     At least one of 'pd_base' / 'pd_upside' / 'pd_downside'.
                     Optional: 'management_ecl' (management's booked ECL,
                     for the variance check).
            weights: Relative weight per scenario, e.g.
                     {'base': 0.5, 'upside': 0.25, 'downside': 0.25}.
                     Renormalized over whichever scenarios are actually
                     mapped, so an unmapped scenario doesn't silently zero
                     out part of the weight.
            variance_threshold_pct: Absolute % difference between the
                     recalculated and management's ECL above which
                     ifrs9_ecl_variance_flag is raised.

        Returns:
            DataFrame with 'ifrs9_weighted_pd', 'ifrs9_scenario_ecl', and
            (if management_ecl is mapped) 'ifrs9_ecl_variance',
            'ifrs9_ecl_variance_pct', 'ifrs9_ecl_variance_flag'.
        """
        ead_col = mapping.get('exposure')
        lgd_col = mapping.get('lgd')
        if not ead_col or not lgd_col or ead_col not in df.columns or lgd_col not in df.columns:
            return df

        weights = weights or {'base': 0.5, 'upside': 0.25, 'downside': 0.25}
        scenario_pd_cols = {
            scenario: mapping[f'pd_{scenario}']
            for scenario in weights
            if mapping.get(f'pd_{scenario}') and mapping[f'pd_{scenario}'] in df.columns
        }
        if not scenario_pd_cols:
            return df

        total_weight = sum(weights[s] for s in scenario_pd_cols)
        if total_weight <= 0:
            return df

        weighted_pd_expr = None
        for scenario, col in scenario_pd_cols.items():
            term = pl.col(col) * (weights[scenario] / total_weight)
            weighted_pd_expr = term if weighted_pd_expr is None else weighted_pd_expr + term

        df = df.with_columns(weighted_pd_expr.alias("ifrs9_weighted_pd"))
        df = df.with_columns(
            (pl.col(ead_col) * pl.col("ifrs9_weighted_pd") * pl.col(lgd_col)).alias("ifrs9_scenario_ecl")
        )

        mgmt_col = mapping.get('management_ecl')
        if mgmt_col and mgmt_col in df.columns:
            df = df.with_columns(
                (pl.col("ifrs9_scenario_ecl") - pl.col(mgmt_col)).alias("ifrs9_ecl_variance")
            )
            df = df.with_columns(
                pl.when(pl.col("ifrs9_scenario_ecl") != 0)
                .then((pl.col("ifrs9_ecl_variance") / pl.col("ifrs9_scenario_ecl")).abs() * 100)
                .otherwise(pl.lit(0.0))
                .alias("ifrs9_ecl_variance_pct")
            )
            df = df.with_columns(
                (pl.col("ifrs9_ecl_variance_pct") > variance_threshold_pct).alias("ifrs9_ecl_variance_flag")
            )

        return df
