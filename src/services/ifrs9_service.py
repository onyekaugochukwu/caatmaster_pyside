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
        
        stage_expr = (
            pl.when(pl.col(target_dpd_col) > stage3_thresh).then(3)
            .when(pl.col(target_dpd_col) > stage2_thresh).then(2)
            .otherwise(1)
            .alias("ifrs9_stage")
        )
        
        status_expr = (
            pl.when(pl.col(target_dpd_col) > stage3_thresh).then(pl.lit("Non-Performing"))
            .when(pl.col(target_dpd_col) > stage2_thresh).then(pl.lit("Underperforming"))
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
