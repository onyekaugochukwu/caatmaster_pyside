"""
COSO Service for CAATmaster
Implements COSO Internal Control Framework mapping and risk scoring.
"""
import polars as pl
from typing import Dict, List, Optional, Any

class CosoService:
    """Service for COSO framework analytics"""

    def generate_risk_heatmap(
        self,
        df: pl.DataFrame,
        category_col: str,
        risk_score_col: str,
        mapping: Dict[str, str] = None
    ) -> pl.DataFrame:
        """
        Aggregate risk scores by COSO component.
        
        Args:
            df: Input DataFrame (e.g., Audit Findings)
            category_col: Column containing business process or area
            risk_score_col: Column containing numeric risk score
            mapping: Dictionary mapping categories to COSO components:
                     e.g. {"IT Security": "Control Environment", "Sales": "Control Activities"}
                     
        Returns:
            DataFrame with aggregated risk by COSO Component
        """
        # COSO Components
        components = [
            "Control Environment",
            "Risk Assessment",
            "Control Activities",
            "Information & Communication",
            "Monitoring Activities"
        ]
        
        # If mapping provided, map category to component
        if mapping and category_col in df.columns:
            # Create a mapping expression
            map_expr = pl.col(category_col).map_dict(mapping, default="Unmapped").alias("coso_component")
            working_df = df.with_columns(map_expr)
        else:
            # Assume category_col ALREADY contains COSO components or similar
            working_df = df.with_columns(pl.col(category_col).alias("coso_component"))
            
        # Aggregate
        # Calculate Mean Risk, Max Risk, Count of Issues
        summary = (
            working_df.lazy()
            .group_by("coso_component")
            .agg([
                pl.col(risk_score_col).mean().alias("avg_risk_score"),
                pl.col(risk_score_col).max().alias("max_risk_score"),
                pl.col(risk_score_col).count().alias("issue_count")
            ])
            .collect()
        )
        
        return summary
