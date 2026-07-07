"""
Financial Data Import Wizard — deterministic structure detection for
GL/JE detail, trial balances, financial statements, and chart-of-accounts
files, which routinely break the "features in columns, observations in
rows" assumption the generic Data Cleaning Wizard is built around
(cleaning_wizard.py).

Deliberately a SEPARATE module rather than more detectors bolted onto the
generic wizard: those detectors have to work with zero knowledge of what
the data represents, so they're tuned conservatively to avoid false
positives on ordinary data. Financial-document detectors get to be far
more confident BECAUSE the caller already knows (or is told, via the
document-type picker in the dialog) what kind of file this is - a
forward-fill check that would be reckless to run on an arbitrary CSV is
exactly right once you know you're looking at journal-entry line detail.

Reuses the generic wizard's structural detectors (header-row detection,
blank rows/columns, footer subtotal rows, subtotal columns) where they're
still exactly the right check - a trial balance can have a title row and
a grand-total row exactly like any other messy import - and adds new
detectors specific to financial documents on top:

  - forward-fill candidates (GL/JE header fields populated once per entry)
  - debit/credit column pairing (collapse to one signed amount)
  - indentation-encoded account/line-item hierarchy
  - period-labeled columns (wide financial statements wanting an unpivot)

Every detector here answers a checkable, structural question and stops
where the question becomes semantic/judgment-based - see
services/financial_import_ai.py for the narrow, explicitly-optional AI
layer that picks up exactly at that point (ambiguous column names,
account-to-category classification, unusual period labels), never
silently in the middle of this module.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from core.cleaning_wizard import (
    CleaningStep, CleaningPlan,
    detect_blank_rows, detect_blank_columns,
    build_numeric_view, detect_footer_subtotal_row, detect_subtotal_columns,
    detect_missing_value_markers,
    _simulate_promoted_columns,
)

DOCUMENT_TYPES = {
    "gl_je": "General Ledger / Journal Entry Detail",
    "trial_balance": "Trial Balance",
    "financial_statement": "Financial Statement",
    "chart_of_accounts": "Chart of Accounts",
}


# =============================================================================
# New, financial-document-specific detectors
# =============================================================================

def detect_forward_fill_candidates(df: pl.DataFrame, min_fraction: float = 0.05,
                                    max_fraction: float = 0.8) -> List[str]:
    """Columns populated only sporadically - non-null on a minority of
    rows, with no leading null run - are the classic GL/JE export
    artifact: header fields (entry number, date, description, preparer)
    printed only on the first line of a multi-line entry, everything
    after left blank rather than repeated. Marked "review" confidence by
    the caller regardless - this is a strong structural signal, not a
    verified fact, and the preview table is what actually confirms it."""
    candidates = []
    n = df.height
    if n < 3:
        return candidates
    for col in df.columns:
        s = df[col]
        non_null = n - s.null_count()
        if non_null == 0:
            continue
        frac = non_null / n
        if not (min_fraction <= frac <= max_fraction):
            continue
        values = s.to_list()
        if values[0] is None:
            continue  # leading null breaks forward-fill semantics for row 0
        candidates.append(col)
    return candidates


_DEBIT_NAME_HINTS = ("debit", "dr_amt", "dr amt", "dramt")
_CREDIT_NAME_HINTS = ("credit", "cr_amt", "cr amt", "cramt")


def _numeric_like_columns(df: pl.DataFrame) -> Dict[str, pl.Series]:
    """Columns that are already numeric, or are text that casts cleanly
    to numeric for most of its non-null values - a fresh raw import (or
    anything that's been through promote_row_header, which casts every
    column to String) never arrives already numeric-typed, so relying on
    dtype.is_numeric() alone would mean this never matches in practice.
    Returns {column: cast_to_float64_series} for every match."""
    result = {}
    for col in df.columns:
        s = df[col]
        if s.dtype.is_numeric():
            result[col] = s.cast(pl.Float64, strict=False)
            continue
        non_null = s.drop_nulls()
        if non_null.len() == 0:
            continue
        cast = non_null.cast(pl.Utf8).str.strip_chars().cast(pl.Float64, strict=False)
        if (cast.null_count() / non_null.len()) <= 0.05:
            result[col] = s.cast(pl.Utf8).str.strip_chars().cast(pl.Float64, strict=False)
    return result


def detect_debit_credit_pair(df: pl.DataFrame) -> Optional[Tuple[str, str]]:
    """A pair of numeric(-looking) columns where, for the large majority
    of rows, at most one of the two is non-zero, is the classic GL
    Debit/Credit column layout rather than one signed Amount column -
    every downstream amount-based test (Benford, outliers, sampling)
    needs one signed column to run against at all. Name-hinted pairs are
    tried first (fast, usually right); falls back to a purely structural
    check across every numeric-looking column pair if no name hints are
    found."""
    numeric_like = _numeric_like_columns(df)
    numeric_cols = list(numeric_like.keys())
    if len(numeric_cols) < 2:
        return None

    def name_matches(col: str, hints: Tuple[str, ...]) -> bool:
        low = col.lower()
        return any(h in low for h in hints)

    debit_names = [c for c in numeric_cols if name_matches(c, _DEBIT_NAME_HINTS)]
    credit_names = [c for c in numeric_cols if name_matches(c, _CREDIT_NAME_HINTS)]
    candidates = [(d, c) for d in debit_names for c in credit_names if d != c]
    if not candidates:
        candidates = [(a, b) for i, a in enumerate(numeric_cols) for b in numeric_cols[i + 1:]]

    n = df.height
    if n == 0:
        return None

    for d, c in candidates:
        d_vals = numeric_like[d].fill_null(0).to_list()
        c_vals = numeric_like[c].fill_null(0).to_list()
        # Only rows where AT LEAST ONE side actually has something are
        # informative about whether the pair is mutually exclusive - a
        # trial balance's pure category/rollup rows ("Assets", "Current
        # Assets") legitimately have NEITHER debit nor credit populated,
        # and counting those against the pair (as "both usually empty,
        # so maybe unrelated") would wrongly rule out a real pair on
        # exactly the document type that needs this detector most.
        either_nonzero = sum(1 for dv, cv in zip(d_vals, c_vals) if dv != 0 or cv != 0)
        if either_nonzero == 0:
            continue
        both_nonzero = sum(1 for dv, cv in zip(d_vals, c_vals) if dv != 0 and cv != 0)
        if (both_nonzero / either_nonzero) < 0.05:
            return (d, c)
    return None


def detect_hierarchy_indentation(df: pl.DataFrame, candidate_cols: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """A text column where a meaningful share of values carry leading
    whitespace, at more than one distinct depth, is a strong signal of an
    account/line-item hierarchy encoded via indentation rather than an
    explicit level column - the standard way trial balances and financial
    statements represent "Total Current Assets" as a parent of "Cash",
    "Accounts Receivable", etc."""
    candidate_cols = candidate_cols or [c for c in df.columns if df[c].dtype == pl.Utf8]
    for col in candidate_cols:
        values = [v for v in df[col].to_list() if v is not None]
        if len(values) < 3:
            continue
        indents = [len(v) - len(v.lstrip(' ')) for v in values]
        if max(indents) == 0:
            continue
        distinct_levels = sorted(set(indents))
        if len(distinct_levels) < 2:
            continue
        indented_frac = sum(1 for i in indents if i > 0) / len(indents)
        if indented_frac < 0.1:
            continue
        return {"column": col, "distinct_indents": distinct_levels}
    return None


_PERIOD_PATTERNS = [
    re.compile(r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-_/.]?\d{2,4}$', re.IGNORECASE),
    re.compile(r'^q[1-4][\s\-_/.]?(fy)?\d{2,4}$', re.IGNORECASE),
    re.compile(r'^fy[\s\-_/.]?\d{2,4}$', re.IGNORECASE),
    re.compile(r'^\d{4}[\-/]\d{2}$'),
    re.compile(r'^(19|20)\d{2}$'),
]


def detect_period_columns(df: pl.DataFrame) -> List[str]:
    """Column names matching common period-label conventions (month-year,
    quarter, fiscal year, bare year, YYYY-MM) - candidates for unpivoting
    a wide financial statement (one column per period) into a tidy
    (line_item, period, amount) table. Deliberately name-pattern-based,
    not date-parsing - financial statement period headers are almost
    never real parseable dates ("FY24", "Q1 2024")."""
    return [col for col in df.columns if any(p.match(str(col).strip()) for p in _PERIOD_PATTERNS)]


def _looks_numeric(v) -> bool:
    if v is None:
        return False
    try:
        float(str(v))
        return True
    except (TypeError, ValueError):
        return False


def detect_single_header_row(df: pl.DataFrame, sample_rows: int = 20) -> bool:
    """Whether row 0 looks like column headers rather than data - a
    narrower, more targeted check than the generic wizard's multi-row
    heuristic (few numeric values in a row = header-like), which breaks
    down for financial documents in two different ways: GL/JE detail
    routinely alternates between text-heavy rows (an entry's header
    line: number, date, description) and number-heavy rows (its
    continuation lines), which defeats the generic detector's "two
    consecutive data-like rows" confirmation entirely; trial balances
    and financial statements have pure category/rollup rows with no
    amount of their own ("Assets"), which the generic detector can't
    tell apart from a genuine second header row. This checks a single,
    targeted signal instead: is there any column where row 0's value is
    NOT numeric, while most of that same column's other values ARE?
    That's exactly what a real header row looks like ("Debit" sitting
    above a column of real numbers) regardless of how the rest of the
    data is shaped."""
    if df.height < 2:
        return False
    height = min(df.height, sample_rows)
    for col in df.columns:
        values = df[col][:height].to_list()
        row0_value = values[0]
        other_values = [v for v in values[1:] if v is not None]
        if len(other_values) < 2:
            continue
        other_numeric_frac = sum(1 for v in other_values if _looks_numeric(v)) / len(other_values)
        if other_numeric_frac >= 0.5 and not _looks_numeric(row0_value):
            return True
    return False


# =============================================================================
# Orchestration
# =============================================================================

def build_financial_import_plan(df: pl.DataFrame, doc_type: str) -> CleaningPlan:
    """Run structural detection over a raw (no-header-assumed) dataframe,
    scoped to the given document type, and assemble a plan of proposed
    Applied Steps - the same reviewable, nothing-auto-applied contract as
    the generic wizard's build_cleaning_plan(). Which NEW detectors run is
    deliberately gated by doc_type: a debit/credit check has no business
    running against a chart-of-accounts file, and running it anyway is
    exactly the false-positive risk that justified a separate wizard in
    the first place."""
    if doc_type not in DOCUMENT_TYPES:
        raise ValueError(f"Unknown document type '{doc_type}' - use one of {list(DOCUMENT_TYPES)}.")

    plan = CleaningPlan()

    # ---- Reused structural cleanup (header rows, blank rows, footer/subtotal rows) ----
    # The generic wizard's multi-row-header heuristic (few numeric values
    # in a row = header-like, confirmed by two consecutive data-like rows
    # after it) breaks down for every one of these document types, just
    # in different ways: GL/JE detail alternates between text-heavy entry
    # header lines and number-heavy continuation lines, which defeats the
    # "two consecutive data-like rows" confirmation outright; trial
    # balances/financial statements/charts of accounts have pure
    # category/rollup rows with no amount of their own ("Assets"),
    # indistinguishable from a genuine second header row under that same
    # heuristic. All four document types use the narrower, targeted
    # single-header check instead - real financial exports essentially
    # always have exactly one header row, so this doesn't give up
    # anything real in exchange for not misfiring on the structure these
    # documents actually have.
    promote_single_header = detect_single_header_row(df)
    data_start = 1 if promote_single_header else 0
    rows_to_remove: set = set()
    header_hints: Dict[str, str] = {}

    data_row_indices = [r for r in range(data_start, df.height) if r not in rows_to_remove]

    blank_rows = [r for r in detect_blank_rows(df) if r in data_row_indices]
    rows_to_remove.update(blank_rows)
    data_row_indices = [r for r in data_row_indices if r not in blank_rows]

    numeric_view = build_numeric_view(df, data_row_indices)
    footer_row = detect_footer_subtotal_row(numeric_view, data_row_indices)
    if footer_row is not None:
        rows_to_remove.add(footer_row)
        data_row_indices = [r for r in data_row_indices if r != footer_row]
        numeric_view = build_numeric_view(df, data_row_indices)

    if rows_to_remove:
        reasons = []
        if blank_rows:
            reasons.append(f"{len(blank_rows)} blank row(s)")
        if footer_row is not None:
            reasons.append("1 grand-total footer row")
        plan.steps.append(CleaningStep(
            operation_id="remove_rows",
            params={"row_indices": sorted(rows_to_remove), "remove": True},
            description="Remove " + ", ".join(reasons) + ".",
            confidence="high",
        ))

    if promote_single_header:
        plan.steps.append(CleaningStep(
            operation_id="promote_row_header",
            params={"row_index": 0},
            description="Row 1 is a single, clean header row - promote it to column names.",
            confidence="high",
        ))
        effective_columns = _simulate_promoted_columns(df, 0)
    else:
        effective_columns = [header_hints.get(c, c) for c in df.columns]
    rename_map = dict(zip(df.columns, effective_columns))
    numeric_view = numeric_view.rename(rename_map)
    raw_data_view = df[data_row_indices].rename(rename_map) if data_row_indices else df.rename(rename_map)

    missing_marker_map = detect_missing_value_markers(raw_data_view)
    for col, markers in missing_marker_map.items():
        plan.steps.append(CleaningStep(
            operation_id="standardize_missing_values",
            params={"column": col, "markers": markers, "case_sensitive": False},
            description=f"Column '{col}' contains {', '.join(repr(m) for m in markers)} - replace with a true null.",
            confidence="review",
        ))

    blank_cols = detect_blank_columns(numeric_view) if numeric_view.height else []
    if blank_cols:
        blank_cols = [c for c in blank_cols if raw_data_view[c].null_count() == raw_data_view.height]
    if blank_cols:
        plan.steps.append(CleaningStep(
            operation_id="choose_columns",
            params={"action": "remove", "columns_to_remove": blank_cols},
            description=f"Remove {len(blank_cols)} fully blank column(s): {', '.join(blank_cols)}.",
            confidence="high",
        ))

    subtotal_map = detect_subtotal_columns(numeric_view)
    if subtotal_map:
        cols_to_remove = list(subtotal_map.keys())
        plan.steps.append(CleaningStep(
            operation_id="choose_columns",
            params={"action": "remove", "columns_to_remove": cols_to_remove},
            description=f"{len(cols_to_remove)} column(s) exactly equal the row-wise sum of their neighbors - subtotal columns, not independent measures.",
            confidence="high",
        ))

    remaining_cols = [c for c in raw_data_view.columns if c not in blank_cols and c not in subtotal_map]

    # ---- New, document-type-gated financial detectors ----

    if doc_type == "gl_je":
        # Debit/Credit pair detection runs FIRST and its two columns are
        # excluded from forward-fill candidacy: a debit/credit pair is
        # naturally sparse for a completely different reason (each row is
        # either a debit or a credit line, never both) - without this
        # exclusion, both columns look exactly like a forward-fill
        # candidate too, and forward-filling them would be wrong (an
        # amount doesn't carry forward from the row above).
        dc_pair = detect_debit_credit_pair(raw_data_view.select(remaining_cols))
        dc_cols = set(dc_pair) if dc_pair else set()

        fill_candidate_cols = [c for c in remaining_cols if c not in dc_cols]
        fill_candidates = detect_forward_fill_candidates(raw_data_view.select(fill_candidate_cols)) if fill_candidate_cols else []
        for col in fill_candidates:
            plan.steps.append(CleaningStep(
                operation_id="forward_fill_column",
                params={"column": col},
                description=(
                    f"'{col}' is populated on only some rows, with no gap before its first value - the "
                    f"classic pattern of a journal-entry header field (entry number, date, description, "
                    f"preparer) printed once per entry and left blank on continuation lines. Forward-fill "
                    f"carries each value down until the next one, so every line of an entry carries its "
                    f"header info."
                ),
                confidence="review",
            ))

        if dc_pair:
            debit_col, credit_col = dc_pair
            plan.steps.append(CleaningStep(
                operation_id="combine_debit_credit",
                params={"debit_column": debit_col, "credit_column": credit_col, "output_column": "amount"},
                description=(
                    f"'{debit_col}' and '{credit_col}' are rarely both non-zero on the same row - the "
                    f"standard Debit/Credit column layout. Collapsing them into one signed 'amount' column "
                    f"(debit positive, credit negative) is what every amount-based test (Benford, outliers, "
                    f"sampling) needs to run against this data at all."
                ),
                confidence="review",
            ))

    elif doc_type == "trial_balance":
        dc_pair = detect_debit_credit_pair(raw_data_view.select(remaining_cols))
        if dc_pair:
            debit_col, credit_col = dc_pair
            plan.steps.append(CleaningStep(
                operation_id="combine_debit_credit",
                params={"debit_column": debit_col, "credit_column": credit_col, "output_column": "amount"},
                description=(
                    f"'{debit_col}' and '{credit_col}' look like a Debit/Credit column pair - collapse into "
                    f"one signed 'amount' column (debit positive, credit negative)."
                ),
                confidence="review",
            ))

        hierarchy = detect_hierarchy_indentation(raw_data_view.select(remaining_cols))
        if hierarchy:
            plan.steps.append(CleaningStep(
                operation_id="extract_hierarchy_level",
                params={"column": hierarchy["column"], "level_column": "account_level", "strip_indent": True},
                description=(
                    f"'{hierarchy['column']}' has {len(hierarchy['distinct_indents'])} distinct indentation "
                    f"depths - this looks like an account hierarchy (e.g. 'Total Current Assets' as a "
                    f"parent of 'Cash', 'Accounts Receivable') encoded via leading spaces rather than an "
                    f"explicit level column. Extracting the indent depth into its own column preserves the "
                    f"hierarchy so detail rows can be told apart from subtotal/rollup rows."
                ),
                confidence="review",
            ))

    elif doc_type == "financial_statement":
        hierarchy = detect_hierarchy_indentation(raw_data_view.select(remaining_cols))
        if hierarchy:
            plan.steps.append(CleaningStep(
                operation_id="extract_hierarchy_level",
                params={"column": hierarchy["column"], "level_column": "line_item_level", "strip_indent": True},
                description=(
                    f"'{hierarchy['column']}' has {len(hierarchy['distinct_indents'])} distinct indentation "
                    f"depths - a line-item hierarchy encoded via leading spaces. Extracting the indent depth "
                    f"lets you separate detail lines from subtotal/total rows."
                ),
                confidence="review",
            ))

        period_cols = detect_period_columns(raw_data_view.select(remaining_cols))
        non_period_cols = [c for c in remaining_cols if c not in period_cols]
        if len(period_cols) >= 2 and non_period_cols:
            plan.steps.append(CleaningStep(
                operation_id="unpivot_table",
                params={
                    "id_vars": non_period_cols,
                    "value_vars": period_cols,
                    "var_name": "period",
                    "value_name": "amount",
                },
                description=(
                    f"{len(period_cols)} columns ({', '.join(period_cols[:6])}{', ...' if len(period_cols) > 6 else ''}) "
                    f"look like period labels (month/quarter/fiscal year) - this is a wide financial "
                    f"statement with one column per period. Unpivoting into a tidy (line item, period, "
                    f"amount) table is what trend/ratio analysis across periods needs."
                ),
                confidence="review",
            ))

    elif doc_type == "chart_of_accounts":
        hierarchy = detect_hierarchy_indentation(raw_data_view.select(remaining_cols))
        if hierarchy:
            plan.steps.append(CleaningStep(
                operation_id="extract_hierarchy_level",
                params={"column": hierarchy["column"], "level_column": "account_level", "strip_indent": True},
                description=(
                    f"'{hierarchy['column']}' has {len(hierarchy['distinct_indents'])} distinct indentation "
                    f"depths - the account hierarchy (parent accounts containing child accounts) encoded "
                    f"via leading spaces. Extracting the indent depth preserves the rollup structure."
                ),
                confidence="review",
            ))

    if not plan.steps:
        plan.notes.append(
            f"No structural issues detected for this {DOCUMENT_TYPES[doc_type]} - it already looks clean."
        )

    return plan
