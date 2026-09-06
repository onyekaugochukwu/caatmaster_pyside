"""
IAS 2 Service for CAATmaster
Implements a Net Realizable Value (NRV) write-down test: inventory
carried at cost above its NRV must be written down per IAS 2.9.
"""
import polars as pl
from typing import Dict, Optional, Any


class IAS2Service:
    """Service for IAS 2 inventory analytics"""

    def detect_nrv_writedowns(
        self,
        df: pl.DataFrame,
        mapping: Dict[str, str],
        tolerance_pct: float = 0.0,
    ) -> pl.DataFrame:
        """
        Flag inventory lines carried at cost above net realizable value
        (selling price less estimated costs to sell), one row per SKU/
        batch.

        Args:
            df: Input DataFrame.
            mapping: Column mapping.
                Required: 'cost' (carrying cost), 'selling_price'
                          (estimated selling price).
                Optional: 'costs_to_sell' (estimated costs to complete
                          and sell - NRV = selling_price - costs_to_sell
                          when mapped, else NRV = selling_price),
                          'quantity' (multiplies the per-unit write-down
                          into a total $ amount; treated as 1 - i.e. cost/
                          selling_price already being row totals - when
                          not mapped).
            tolerance_pct: A cost-over-NRV excess must exceed NRV by more
                than this % before flagging - a de minimis buffer for
                immaterial rounding differences, not a standard-defined
                threshold (IAS 2 itself has no bright line; 0% flags any
                excess at all).

        Returns:
            DataFrame with 'ias2_nrv', 'ias2_writedown_amount' (0 where
            cost does not exceed NRV), and 'ias2_writedown_flag'.
        """
        cost_col = mapping.get('cost')
        price_col = mapping.get('selling_price')
        if not cost_col or not price_col or cost_col not in df.columns or price_col not in df.columns:
            return df

        costs_to_sell_col = mapping.get('costs_to_sell')
        quantity_col = mapping.get('quantity')

        nrv_expr = pl.col(price_col)
        if costs_to_sell_col and costs_to_sell_col in df.columns:
            nrv_expr = nrv_expr - pl.col(costs_to_sell_col)
        df = df.with_columns(nrv_expr.alias("ias2_nrv"))

        quantity_expr = pl.col(quantity_col) if quantity_col and quantity_col in df.columns else pl.lit(1.0)
        excess = pl.col(cost_col) - pl.col("ias2_nrv")
        df = df.with_columns(
            (pl.when(excess > 0).then(excess).otherwise(0.0) * quantity_expr)
            .alias("ias2_writedown_amount")
        )
        df = df.with_columns(
            (pl.col(cost_col) > (pl.col("ias2_nrv") * (1 + tolerance_pct / 100.0)))
            .alias("ias2_writedown_flag")
        )
        return df
