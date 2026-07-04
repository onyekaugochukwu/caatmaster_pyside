"""
Exporters for AnalysisReport — plain text, CSV, and Excel. All three formats
are meant for "easy, non-complicated, downstream analytics use" (per the
original request): TXT for a quick human-readable summary, CSV for a single
table pulled into another tool, XLSX for the full report (summary sheet plus
one sheet per table) in one file.
"""
from pathlib import Path

import pandas as pd

from core.analysis_report import AnalysisReport


def export_txt(report: AnalysisReport, file_path: str):
    """Plain-text summary + every table rendered as simple aligned text."""
    lines = [report.title, "=" * len(report.title), ""]
    lines.append(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    if report.summary:
        lines.append("Summary")
        lines.append("-" * 7)
        for label, value in report.summary:
            lines.append(f"{label}: {value}")
        lines.append("")

    for name, df in report.tables:
        lines.append(name)
        lines.append("-" * len(name))
        lines.append(df.to_pandas().to_string(index=False))
        lines.append("")

    if report.notes:
        lines.append("Notes")
        lines.append("-" * 5)
        for note in report.notes:
            lines.append(f"- {note}")
        lines.append("")

    Path(file_path).write_text("\n".join(lines), encoding="utf-8")


def export_csv(report: AnalysisReport, file_path: str):
    """A single CSV: summary rows first (as a 2-column label/value table),
    then each table appended below its own header row — the simplest format
    for pulling straight into another spreadsheet or analytics tool."""
    lines = []
    if report.summary:
        lines.append("Summary")
        for label, value in report.summary:
            lines.append(f'"{label}","{value}"')
        lines.append("")

    for name, df in report.tables:
        lines.append(name)
        lines.append(df.write_csv())
        lines.append("")

    Path(file_path).write_text("\n".join(lines), encoding="utf-8")


def export_xlsx(report: AnalysisReport, file_path: str):
    """One workbook: a Summary sheet, then one sheet per table."""
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        summary_df = pd.DataFrame(report.summary, columns=["Metric", "Value"]) \
            if report.summary else pd.DataFrame(columns=["Metric", "Value"])
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

        used_names = {"summary"}
        for name, df in report.tables:
            sheet_name = _safe_sheet_name(name, used_names)
            df.to_pandas().to_excel(writer, sheet_name=sheet_name, index=False)


def _safe_sheet_name(name: str, used_lower: set) -> str:
    """Excel sheet names: max 31 chars, no []:*?/\\, and must be unique."""
    safe = "".join(c for c in name if c not in '[]:*?/\\')[:31] or "Sheet"
    candidate = safe
    n = 2
    while candidate.lower() in used_lower:
        suffix = f" ({n})"
        candidate = safe[:31 - len(suffix)] + suffix
        n += 1
    used_lower.add(candidate.lower())
    return candidate


EXPORTERS = {
    "txt": export_txt,
    "csv": export_csv,
    "xlsx": export_xlsx,
}
