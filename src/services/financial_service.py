"""
Financial Analysis Service for CAATmaster
Implements standard financial ratios and metrics for audit analytics.
"""
import polars as pl
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class MultiDatasetMapping:
    """Mapping information when using multiple datasets"""
    column_name: str
    dataset_name: str
    dataset: Optional[pl.DataFrame] = None


class FinancialService:
    """Service for calculating financial ratios and metrics"""

    def calculate_ratios_multi_dataset(
        self,
        primary_df: pl.DataFrame,
        mapping: Dict[str, str],
        dataset_mapping: Dict[str, str],
        all_datasets: Dict[str, pl.DataFrame],
        ratios_to_calculate: List[str]
    ) -> pl.DataFrame:
        """
        Calculate financial ratios using data from multiple datasets.

        Args:
            primary_df: The primary DataFrame (for output structure)
            mapping: Dict mapping concepts to column names
            dataset_mapping: Dict mapping concepts to source dataset names
            all_datasets: Dict of {dataset_name: DataFrame}
            ratios_to_calculate: List of ratio IDs to generate

        Returns:
            DataFrame with ratio columns appended to primary_df
        """
        # Helper to get column from correct dataset
        def get_col_from_dataset(concept: str) -> tuple[Optional[str], Optional[pl.DataFrame]]:
            """Get column name and source dataset for a concept"""
            col_name = mapping.get(concept)
            if not col_name:
                return None, None

            ds_name = dataset_mapping.get(concept, "Current Dataset")
            if ds_name and ds_name in all_datasets:
                return col_name, all_datasets[ds_name]
            return col_name, primary_df

        # Get required columns from their datasets
        cols = {}
        datasets = {}

        # P&L items
        cols['revenue'], datasets['revenue'] = get_col_from_dataset('revenue')
        cols['net_income'], datasets['net_income'] = get_col_from_dataset('net_income')
        cols['gross_profit'], datasets['gross_profit'] = get_col_from_dataset('gross_profit')
        cols['cogs'], datasets['cogs'] = get_col_from_dataset('cogs')
        cols['ebitda'], datasets['ebitda'] = get_col_from_dataset('ebitda')
        cols['ebit'], datasets['ebit'] = get_col_from_dataset('ebit')

        # Balance Sheet items
        cols['current_assets'], datasets['current_assets'] = get_col_from_dataset('current_assets')
        cols['current_liabilities'], datasets['current_liabilities'] = get_col_from_dataset('current_liabilities')
        cols['cash'], datasets['cash'] = get_col_from_dataset('cash')
        cols['inventory'], datasets['inventory'] = get_col_from_dataset('inventory')
        cols['total_assets'], datasets['total_assets'] = get_col_from_dataset('total_assets')
        cols['total_liabilities'], datasets['total_liabilities'] = get_col_from_dataset('total_liabilities')
        cols['total_equity'], datasets['total_equity'] = get_col_from_dataset('total_equity')

        # Cash Flow items
        cols['interest_expense'], datasets['interest_expense'] = get_col_from_dataset('interest_expense')

        expressions = []

        # --- LIQUIDITY RATIOS ---
        if 'current_ratio' in ratios_to_calculate:
            ca = cols['current_assets']
            cl = cols['current_liabilities']
            if ca and cl:
                df_ca = datasets.get('current_assets', primary_df)
                df_cl = datasets.get('current_liabilities', primary_df)
                if ca in df_ca.columns and cl in df_cl.columns:
                    # Handle cross-dataset by using values from respective datasets
                    expr = self._cross_dataset_div(df_ca, ca, df_cl, cl, 'ratio_current')
                    if expr: expressions.append(expr)

        if 'quick_ratio' in ratios_to_calculate:
            ca = cols['current_assets']
            inv = cols['inventory']
            cl = cols['current_liabilities']
            if ca and cl:
                df_ca = datasets.get('current_assets', primary_df)
                df_inv = datasets.get('inventory', primary_df)
                df_cl = datasets.get('current_liabilities', primary_df)
                if ca in df_ca.columns and cl in df_cl.columns:
                    if inv and inv in df_inv.columns:
                        expr = self._cross_dataset_expr(
                            df_ca, ca, df_cl, cl,
                            lambda a, c: (a - pl.col(inv)) / c,
                            'ratio_quick'
                        )
                    else:
                        expr = self._cross_dataset_div(df_ca, ca, df_cl, cl, 'ratio_quick_approx')
                    if expr: expressions.append(expr)

        if 'cash_ratio' in ratios_to_calculate:
            cash = cols['cash']
            cl = cols['current_liabilities']
            if cash and cl:
                df_cash = datasets.get('cash', primary_df)
                df_cl = datasets.get('current_liabilities', primary_df)
                if cash in df_cash.columns and cl in df_cl.columns:
                    expr = self._cross_dataset_div(df_cash, cash, df_cl, cl, 'ratio_cash')
                    if expr: expressions.append(expr)

        # --- SOLVENCY RATIOS ---
        if 'debt_to_equity' in ratios_to_calculate:
            tl = cols['total_liabilities']
            eq = cols['total_equity']
            if tl and eq:
                df_tl = datasets.get('total_liabilities', primary_df)
                df_eq = datasets.get('total_equity', primary_df)
                if tl in df_tl.columns and eq in df_eq.columns:
                    expr = self._cross_dataset_div(df_tl, tl, df_eq, eq, 'ratio_debt_to_equity')
                    if expr: expressions.append(expr)

        if 'debt_ratio' in ratios_to_calculate:
            tl = cols['total_liabilities']
            ta = cols['total_assets']
            if tl and ta:
                df_tl = datasets.get('total_liabilities', primary_df)
                df_ta = datasets.get('total_assets', primary_df)
                if tl in df_tl.columns and ta in df_ta.columns:
                    expr = self._cross_dataset_div(df_tl, tl, df_ta, ta, 'ratio_debt_ratio')
                    if expr: expressions.append(expr)

        if 'interest_coverage' in ratios_to_calculate:
            ni = cols['net_income']
            ie = cols['interest_expense']
            if ni and ie:
                df_ni = datasets.get('net_income', primary_df)
                df_ie = datasets.get('interest_expense', primary_df)
                if ni in df_ni.columns and ie in df_ie.columns:
                    expr = self._cross_dataset_expr(
                        df_ni, ni, df_ie, ie,
                        lambda n, i: (n + i) / i,
                        'ratio_interest_coverage'
                    )
                    if expr: expressions.append(expr)

        # --- PROFITABILITY RATIOS ---
        if 'net_profit_margin' in ratios_to_calculate:
            ni = cols['net_income']
            rev = cols['revenue']
            if ni and rev:
                df_ni = datasets.get('net_income', primary_df)
                df_rev = datasets.get('revenue', primary_df)
                if ni in df_ni.columns and rev in df_rev.columns:
                    expr = self._cross_dataset_div(df_ni, ni, df_rev, rev, 'ratio_net_profit_margin')
                    if expr: expressions.append(expr)

        if 'gross_margin' in ratios_to_calculate:
            rev = cols['revenue']
            gp = cols['gross_profit']
            cogs = cols['cogs']
            if rev:
                df_rev = datasets.get('revenue', primary_df)
                if rev in df_rev.columns:
                    if gp and gp in datasets.get('gross_profit', primary_df).columns:
                        expr = self._cross_dataset_div(
                            datasets.get('gross_profit', primary_df), gp,
                            df_rev, rev,
                            'ratio_gross_margin'
                        )
                    elif cogs and cogs in datasets.get('cogs', primary_df).columns:
                        expr = self._cross_dataset_expr(
                            df_rev, rev, datasets.get('cogs', primary_df), cogs,
                            lambda r, c: (r - c) / r,
                            'ratio_gross_margin'
                        )
                    if expr: expressions.append(expr)

        if 'return_on_assets' in ratios_to_calculate:
            ni = cols['net_income']
            ta = cols['total_assets']
            if ni and ta:
                df_ni = datasets.get('net_income', primary_df)
                df_ta = datasets.get('total_assets', primary_df)
                if ni in df_ni.columns and ta in df_ta.columns:
                    expr = self._cross_dataset_div(df_ni, ni, df_ta, ta, 'ratio_roa')
                    if expr: expressions.append(expr)

        if 'return_on_equity' in ratios_to_calculate:
            ni = cols['net_income']
            eq = cols['total_equity']
            if ni and eq:
                df_ni = datasets.get('net_income', primary_df)
                df_eq = datasets.get('total_equity', primary_df)
                if ni in df_ni.columns and eq in df_eq.columns:
                    expr = self._cross_dataset_div(df_ni, ni, df_eq, eq, 'ratio_roe')
                    if expr: expressions.append(expr)

        if 'ebitda_margin' in ratios_to_calculate:
            ebitda = cols['ebitda']
            rev = cols['revenue']
            if ebitda and rev:
                df_ebitda = datasets.get('ebitda', primary_df)
                df_rev = datasets.get('revenue', primary_df)
                if ebitda in df_ebitda.columns and rev in df_rev.columns:
                    expr = self._cross_dataset_div(df_ebitda, ebitda, df_rev, rev, 'ratio_ebitda_margin')
                    if expr: expressions.append(expr)

        # --- EFFICIENCY RATIOS ---
        if 'asset_turnover' in ratios_to_calculate:
            rev = cols['revenue']
            ta = cols['total_assets']
            if rev and ta:
                df_rev = datasets.get('revenue', primary_df)
                df_ta = datasets.get('total_assets', primary_df)
                if rev in df_rev.columns and ta in df_ta.columns:
                    expr = self._cross_dataset_div(df_rev, rev, df_ta, ta, 'ratio_asset_turnover')
                    if expr: expressions.append(expr)

        # Apply calculations
        if expressions:
            return primary_df.with_columns(expressions)

        return primary_df

    def _cross_dataset_div(
        self,
        df1: pl.DataFrame, col1: str,
        df2: pl.DataFrame, col2: str,
        alias: str
    ) -> Optional[pl.Expr]:
        """Create division expression when columns may be from different datasets"""
        # Get values as literals (both datasets must have same number of rows)
        val1 = df1[col1] if col1 in df1.columns else None
        val2 = df2[col2] if col2 in df2.columns else None

        if val1 is None or val2 is None:
            return None

        # If same dataset, use simple division
        if df1 is df2:
            return (pl.col(col1) / pl.col(col2)).fill_nan(None).alias(alias)

        # Cross-dataset: extract values (assumes single-row datasets or matching indices)
        # For now, use first value from each
        v1 = val1[0] if len(val1) > 0 else None
        v2 = val2[0] if len(val2) > 0 else None

        if v1 is not None and v2 is not None and v2 != 0:
            return pl.lit(v1 / v2).alias(alias)
        return pl.lit(None).alias(alias)

    def _cross_dataset_expr(
        self,
        df1: pl.DataFrame, col1: str,
        df2: pl.DataFrame, col2: str,
        func,
        alias: str
    ) -> Optional[pl.Expr]:
        """Create expression when columns may be from different datasets"""
        val1 = df1[col1] if col1 in df1.columns else None
        val2 = df2[col2] if col2 in df2.columns else None

        if val1 is None or val2 is None:
            return None

        if df1 is df2:
            return func(pl.col(col1), pl.col(col2)).fill_nan(None).alias(alias)

        # Cross-dataset: extract values
        v1 = val1[0] if len(val1) > 0 else None
        v2 = val2[0] if len(val2) > 0 else None

        if v1 is not None and v2 is not None:
            result = func(v1, v2)
            return pl.lit(result).alias(alias)
        return pl.lit(None).alias(alias)

    def calculate_ratios(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        ratios_to_calculate: List[str]
    ) -> pl.DataFrame:
        """
        Calculate selected financial ratios based on column mapping.
        
        Args:
            df: Input DataFrame
            mapping: Dictionary mapping standard concepts to actual column names
                     Keys: 'assets', 'liabilities', 'equity', 'revenue', 'expenses', 
                           'net_income', 'current_assets', 'current_liabilities', 
                           'inventory', 'cash', 'interest_expense', 'ebitda'
            ratios_to_calculate: List of ratio IDs to generate
            
        Returns:
            DataFrame with new ratio columns appended
        """
        # Helper to get column name or None
        def get_col(concept):
            return mapping.get(concept)

        # Helper to safely divide two EXPRESSIONS (not yet column names) -
        # guards the denominator being exactly 0 directly, rather than
        # dividing first and mopping up afterward. That distinction
        # matters: x/0 is +/-inf in IEEE-754, not NaN, so a later
        # .fill_nan(None) (the previous approach) never actually caught
        # it - only the 0/0 case produces NaN. An unguarded inf ratio
        # silently poisons every downstream mean/chart/threshold check it
        # touches instead of failing visibly anywhere.
        def safe_div_expr(numerator: pl.Expr, denominator: pl.Expr) -> pl.Expr:
            return pl.when(denominator != 0).then(numerator / denominator).otherwise(None)

        # Helper to safely divide two COLUMNS by name
        def safe_div(num_col, den_col, alias):
            if num_col and den_col and num_col in df.columns and den_col in df.columns:
                return safe_div_expr(pl.col(num_col), pl.col(den_col)).alias(alias)
            return None

        expressions = []

        # --- LIQUIDITY RATIOS ---
        if 'current_ratio' in ratios_to_calculate:
            expr = safe_div(get_col('current_assets'), get_col('current_liabilities'), 'ratio_current')
            if expr is not None: expressions.append(expr)

        if 'quick_ratio' in ratios_to_calculate:
            # Quick Ratio = (Current Assets - Inventory) / Current Liabilities
            ca = get_col('current_assets')
            inv = get_col('inventory')
            cl = get_col('current_liabilities')

            if ca and cl and ca in df.columns and cl in df.columns:
                if inv and inv in df.columns:
                    expr = safe_div_expr(pl.col(ca) - pl.col(inv), pl.col(cl)).alias('ratio_quick')
                else:
                    # Fallback if inventory missing: assume CA is mostly quick or user didn't map it
                    expr = safe_div_expr(pl.col(ca), pl.col(cl)).alias('ratio_quick_approx')
                if expr is not None: expressions.append(expr)

        if 'cash_ratio' in ratios_to_calculate:
            expr = safe_div(get_col('cash'), get_col('current_liabilities'), 'ratio_cash')
            if expr is not None: expressions.append(expr)

        # --- SOLVENCY RATIOS ---
        if 'debt_to_equity' in ratios_to_calculate:
            # If total liabilities is not mapped, try current + non-current?
            # For now assume simple mapping
            expr = safe_div(get_col('total_liabilities'), get_col('total_equity'), 'ratio_debt_to_equity')
            if expr is not None: expressions.append(expr)

        if 'debt_ratio' in ratios_to_calculate:
            expr = safe_div(get_col('total_liabilities'), get_col('total_assets'), 'ratio_debt_ratio')
            if expr is not None: expressions.append(expr)

        if 'interest_coverage' in ratios_to_calculate:
            # EBIT / Interest Expense
            # Approx EBIT as Net Income + Interest + Tax (if tax mapped, else just Net + Interest)
            ni = get_col('net_income')
            ie = get_col('interest_expense')

            if ni and ie and ni in df.columns and ie in df.columns:
                expr = safe_div_expr(pl.col(ni) + pl.col(ie), pl.col(ie)).alias('ratio_interest_coverage')
                expressions.append(expr)

        # --- PROFITABILITY RATIOS ---
        if 'net_profit_margin' in ratios_to_calculate:
            expr = safe_div(get_col('net_income'), get_col('revenue'), 'ratio_net_profit_margin')
            if expr is not None: expressions.append(expr)

        if 'gross_margin' in ratios_to_calculate:
            # (Revenue - COGS) / Revenue
            # or Gross Profit / Revenue
            # We'll use inputs directly if mapped, or derive
            rev = get_col('revenue')
            cogs = get_col('cogs')
            gp = get_col('gross_profit')

            if rev and rev in df.columns:
                if gp and gp in df.columns:
                     expressions.append(safe_div_expr(pl.col(gp), pl.col(rev)).alias('ratio_gross_margin'))
                elif cogs and cogs in df.columns:
                     expressions.append(safe_div_expr(pl.col(rev) - pl.col(cogs), pl.col(rev)).alias('ratio_gross_margin'))

        if 'return_on_assets' in ratios_to_calculate:
            expr = safe_div(get_col('net_income'), get_col('total_assets'), 'ratio_roa')
            if expr is not None: expressions.append(expr)

        if 'return_on_equity' in ratios_to_calculate:
            expr = safe_div(get_col('net_income'), get_col('total_equity'), 'ratio_roe')
            if expr is not None: expressions.append(expr)
            
        if 'ebitda_margin' in ratios_to_calculate:
            expr = safe_div(get_col('ebitda'), get_col('revenue'), 'ratio_ebitda_margin')
            if expr is not None: expressions.append(expr)

        # --- EFFICIENCY RATIOS ---
        if 'asset_turnover' in ratios_to_calculate:
            expr = safe_div(get_col('revenue'), get_col('total_assets'), 'ratio_asset_turnover')
            if expr is not None: expressions.append(expr)

        # Apply calculations
        if expressions:
            return df.with_columns(expressions)
        
        return df

    def calculate_vertical_analysis(
        self,
        df: pl.DataFrame,
        base_column: str,
        columns_to_analyze: List[str]
    ) -> pl.DataFrame:
        """
        Perform vertical analysis (common-size) where each column is expressed 
        as a percentage of the base column (e.g., Total Assets or Revenue).
        """
        if base_column not in df.columns:
            return df

        expressions = []
        for col in columns_to_analyze:
            if col in df.columns and col != base_column:
                # Use pl.when to handle division by zero
                expr = (
                    pl.when(pl.col(base_column) != 0)
                    .then(pl.col(col) / pl.col(base_column))
                    .otherwise(None)
                    .alias(f"v_perc_{col}")
                )
                expressions.append(expr)
        
        if expressions:
            return df.with_columns(expressions)
        return df

    def calculate_horizontal_analysis(
        self,
        df: pl.DataFrame,
        period_column: str,
        value_columns: List[str]
    ) -> pl.DataFrame:
        """
        Perform horizontal analysis (trend analysis) calculating percentage 
        change from the previous period.
        """
        if period_column not in df.columns:
            return df

        # Ensure sorted by period
        df_sorted = df.sort(period_column)
        
        expressions = []
        for col in value_columns:
            if col in df_sorted.columns:
                # Calculate % change: (current - prev) / prev
                prev_val = pl.col(col).shift(1)
                expr = (
                    pl.when(prev_val != 0)
                    .then((pl.col(col) - prev_val) / prev_val)
                    .otherwise(None)
                    .alias(f"h_trend_{col}")
                )
                expressions.append(expr)

        if expressions:
            return df_sorted.with_columns(expressions)
        return df_sorted

    def calculate_altman_z_score(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        is_public: bool = False
    ) -> pl.DataFrame:
        """
        Calculate Altman Z-Score for bankruptcy prediction.
        
        X1 = Working Capital / Total Assets
        X2 = Retained Earnings / Total Assets
        X3 = EBIT / Total Assets
        X4 = Market Value Equity / Total Liabilities (or Book Value if not public)
        X5 = Sales / Total Assets
        """
        # Required concepts
        ca = mapping.get('current_assets')
        cl = mapping.get('current_liabilities')
        ta = mapping.get('total_assets')
        re = mapping.get('retained_earnings')
        ebit = mapping.get('ebitda') # Using EBITDA as proxy if EBIT not available
        eq = mapping.get('total_equity')
        tl = mapping.get('total_liabilities')
        rev = mapping.get('revenue')

        # Check if we have enough to calculate
        required = [ca, cl, ta, eq, tl, rev]
        if not all(r and r in df.columns for r in required):
            return df

        # X1: Working Capital / Total Assets
        x1 = (pl.col(ca) - pl.col(cl)) / pl.col(ta)
        
        # X2: Retained Earnings / Total Assets
        # Fallback to a fraction of equity if retained earnings not mapped
        if re and re in df.columns:
            x2 = pl.col(re) / pl.col(ta)
        else:
            x2 = (pl.col(eq) * 0.5) / pl.col(ta) # Rough estimate fallback
            
        # X3: EBIT / Total Assets
        if ebit and ebit in df.columns:
            x3 = pl.col(ebit) / pl.col(ta)
        else:
            # Try deriving from net income if possible (proxied)
            ni = mapping.get('net_income')
            if ni and ni in df.columns:
                x3 = pl.col(ni) / pl.col(ta)
            else:
                x3 = pl.lit(0)
                
        # X4: Equity / Total Liabilities
        x4 = pl.col(eq) / pl.col(tl)
        
        # X5: Sales / Total Assets
        x5 = pl.col(rev) / pl.col(ta)

        if is_public:
            z_score = (1.2 * x1) + (1.4 * x2) + (3.3 * x3) + (0.6 * x4) + (0.999 * x5)
        else:
            # Private firm model
            z_score = (0.717 * x1) + (0.847 * x2) + (3.107 * x3) + (0.420 * x4) + (0.998 * x5)

        return df.with_columns([
            z_score.alias("altman_z_score"),
            pl.when(z_score > (2.99 if is_public else 2.9))
            .then(pl.lit("Safe"))
            .when(z_score > (1.81 if is_public else 1.23))
            .then(pl.lit("Grey Zone"))
            .otherwise(pl.lit("Distress"))
            .alias("z_score_zone")
        ])
