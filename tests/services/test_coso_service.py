"""
Tests for COSO Service - risk heatmap aggregation.
"""
import pytest
import polars as pl


class TestBuildHeatmapFromFindings:
    def test_aggregates_by_component(self):
        from services.coso_service import CosoService

        findings = [
            {"coso_component": "Control Activities", "severity": "high", "title": "A", "affected_pct": 20.0},
            {"coso_component": "Control Activities", "severity": "high", "title": "B", "affected_pct": 40.0},
            {"coso_component": "Control Activities", "severity": "medium", "title": "C", "affected_pct": 20.0},
            {"coso_component": "Risk Assessment", "severity": "high", "title": "D", "affected_pct": 5.0},
        ]
        result = CosoService().build_heatmap_from_findings(findings)
        by_component = {row["coso_component"]: row for row in result.to_dicts()}

        assert by_component["Control Activities"]["issue_count"] == 3
        assert by_component["Control Activities"]["high_count"] == 2
        assert by_component["Control Activities"]["medium_count"] == 1
        assert by_component["Risk Assessment"]["issue_count"] == 1
        assert by_component["Risk Assessment"]["high_count"] == 1

    def test_sorted_by_avg_risk_weight_descending(self):
        from services.coso_service import CosoService

        findings = [
            {"coso_component": "Low Risk Area", "severity": "low", "title": "A"},
            {"coso_component": "High Risk Area", "severity": "high", "title": "B"},
        ]
        result = CosoService().build_heatmap_from_findings(findings)
        components_in_order = result["coso_component"].to_list()
        assert components_in_order[0] == "High Risk Area"

    def test_empty_findings_returns_empty_dataframe(self):
        from services.coso_service import CosoService

        result = CosoService().build_heatmap_from_findings([])
        assert result.height == 0
        assert "coso_component" in result.columns

    def test_missing_coso_component_falls_back_to_unmapped(self):
        from services.coso_service import CosoService

        findings = [{"severity": "medium", "title": "No component given"}]
        result = CosoService().build_heatmap_from_findings(findings)
        assert result["coso_component"].to_list() == ["Unmapped"]

    def test_unknown_severity_treated_as_default_weight(self):
        from services.coso_service import CosoService

        findings = [{"coso_component": "X", "severity": "weird", "title": "A"}]
        result = CosoService().build_heatmap_from_findings(findings)
        assert result["avg_risk_weight"].to_list() == [1.0]
