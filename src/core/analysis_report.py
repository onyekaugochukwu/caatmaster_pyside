"""
Shared report structure for "analysis" operations (Find Duplicates, Benford's
Law, Gap Analysis, Outlier Detection, ML models, etc.) whose result columns
alone don't tell the full story of what the analysis found.

One structure, reused by every operation's report builder (core/report_builders.py)
and rendered by one generic dialog (gui/dialogs/analysis_report_dialog.py) and
exported by one shared exporter (core/report_exporter.py) — so adding a new
report for a new operation only ever means writing one small builder function.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import polars as pl


@dataclass
class AnalysisReport:
    """A single analysis's report: some headline summary lines, plus zero or
    more supporting tables (e.g. "Duplicate Groups", "Digit Frequencies")."""

    title: str
    operation_id: str
    summary: list[tuple[str, str]] = field(default_factory=list)
    tables: list[tuple[str, pl.DataFrame]] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    notes: list[str] = field(default_factory=list)

    def add_summary(self, label: str, value: Any):
        self.summary.append((label, str(value)))

    def add_table(self, name: str, df: pl.DataFrame):
        self.tables.append((name, df))
