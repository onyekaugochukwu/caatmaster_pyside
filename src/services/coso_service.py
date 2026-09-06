"""
COSO Service for CAATmaster
Implements COSO Internal Control Framework mapping and risk scoring.
"""
import polars as pl
from typing import Dict, List, Optional, Any

# Severity -> numeric risk weight used by build_heatmap_from_findings().
# Deliberately a small, fixed, transparent scale (not a derived/opaque
# score) so a reviewer can see exactly how the aggregate was built rather
# than trusting a black-box number.
_SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1, "info": 0}


class CosoService:
    """Service for COSO framework analytics"""

    def build_heatmap_from_findings(
        self,
        findings: List[Dict[str, Any]],
    ) -> pl.DataFrame:
        """
        Build a COSO component risk heatmap directly from real findings
        already produced elsewhere in the app (compliance_rule_library
        results, SOX SoD conflicts, audit_service flags, ...) - rather than
        requiring the user to have already computed and supplied a numeric
        risk-score column, which generate_risk_heatmap() below needs.

        Args:
            findings: list of dicts, each with at least:
                - "coso_component": one of the 5 COSO 2013 components
                - "severity": "high" / "medium" / "low" / "info"
                - "title": short finding name (for issue counts/labels)
                Optional:
                - "affected_pct": float 0-100, shown as a separate column
                  (never folded into the risk score - keeps the aggregate
                  explainable rather than a single opaque number).

        Returns:
            DataFrame with one row per COSO component actually referenced:
            coso_component, issue_count, high_count, medium_count,
            low_count, avg_risk_weight, max_risk_weight, avg_affected_pct
        """
        if not findings:
            return pl.DataFrame(schema={
                "coso_component": pl.Utf8, "issue_count": pl.Int64,
                "high_count": pl.Int64, "medium_count": pl.Int64, "low_count": pl.Int64,
                "avg_risk_weight": pl.Float64, "max_risk_weight": pl.Int64,
                "avg_affected_pct": pl.Float64,
            })

        rows = []
        for f in findings:
            severity = (f.get("severity") or "info").lower()
            rows.append({
                "coso_component": f.get("coso_component") or "Unmapped",
                "severity": severity,
                "risk_weight": _SEVERITY_WEIGHT.get(severity, 1),
                "affected_pct": float(f.get("affected_pct") or 0.0),
            })

        working_df = pl.DataFrame(rows)

        summary = (
            working_df.lazy()
            .group_by("coso_component")
            .agg([
                pl.len().alias("issue_count"),
                (pl.col("severity") == "high").sum().alias("high_count"),
                (pl.col("severity") == "medium").sum().alias("medium_count"),
                (pl.col("severity") == "low").sum().alias("low_count"),
                pl.col("risk_weight").mean().alias("avg_risk_weight"),
                pl.col("risk_weight").max().alias("max_risk_weight"),
                pl.col("affected_pct").mean().alias("avg_affected_pct"),
            ])
            .sort("avg_risk_weight", descending=True)
            .collect()
        )
        return summary

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
            # map_dict was renamed to replace_strict in current polars -
            # the old call raised AttributeError on every real use of this
            # dialog, since it always builds and passes a mapping.
            map_expr = pl.col(category_col).replace_strict(mapping, default="Unmapped").alias("coso_component")
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
