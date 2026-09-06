"""
Numeric Disclosure Reconciliation - deterministic comparison of a figure
extracted from narrative text (services.ai_service.NumericDisclosureExtractor)
against a real value computed from structured data. Kept entirely separate
from the AI extraction step: nothing here ever asks an LLM what the "actual"
number is - it always comes from the mapped dataset column itself.
"""
import re
import polars as pl
from typing import Any, Dict, List, Optional


def parse_numeric(value_text: str) -> Optional[float]:
    """Parse a figure as written in narrative text into a plain float, on
    a best-effort basis. Handles a percentage sign, currency symbols,
    thousands separators, and parenthesized negatives (the standard
    accounting convention for a negative number) - but deliberately does
    NOT try to resolve a range ("3 to 5 years") to a single number; that
    would be putting words in the disclosure's mouth. Returns None for
    anything it can't confidently parse as one number, rather than a
    fabricated guess.
    """
    if value_text is None:
        return None
    text = str(value_text).strip()
    if not text:
        return None

    # A range ("3 to 5 years", "3-5%") has no single correct value to
    # reconcile against - leave it for the human reviewer.
    if re.search(r"\d\s*(?:-|to|–|—)\s*\d", text):
        return None

    is_negative = text.startswith("(") and text.endswith(")")
    cleaned = text.strip("()")
    cleaned = re.sub(r"[^\d.\-]", "", cleaned)
    if not cleaned or cleaned in ("-", "."):
        return None

    try:
        value = float(cleaned)
    except ValueError:
        return None

    return -abs(value) if is_negative else value


def normalize_to_decimal(value: float, unit: str) -> float:
    """Normalize a parsed value to the same scale a "rate" column in the
    dataset is expected to use (a decimal, e.g. 0.20 for 20%) when the
    unit is a percentage - so "20%" compares correctly against a column
    storing 0.20 rather than literal 20. Non-percentage units pass through
    unchanged; whether that's the right scale for years/currency/count is
    up to the mapped column matching the disclosure's own units."""
    if (unit or "").strip().lower() in ("percent", "%"):
        return value / 100.0
    return value


def compute_actual_value_stats(df: pl.DataFrame, column: str) -> Optional[Dict[str, Any]]:
    """Compute the real summary statistics for a mapped column: mean (the
    "actual" value compared against the disclosure), plus min/max/distinct
    count/non-null count so a reviewer can judge whether "the mean" is even
    a meaningful single figure to compare against (e.g. a column with 3
    wildly different values isn't well-summarized by its average, and this
    surfaces that rather than hiding it behind one deceptively precise
    number)."""
    if column not in df.columns:
        return None
    series = df[column].drop_nulls()
    if series.len() == 0 or not series.dtype.is_numeric():
        return None
    return {
        "mean": float(series.mean()),
        "min": float(series.min()),
        "max": float(series.max()),
        "distinct_count": series.n_unique(),
        "non_null_count": series.len(),
        "total_count": len(df),
    }


def reconcile_disclosed_figure(
    disclosed_item: Dict[str, Any],
    actual_stats: Optional[Dict[str, Any]],
    tolerance_abs: float = 0.005,
    tolerance_pct: float = 10.0,
) -> Dict[str, Any]:
    """Compare one disclosed figure against the real computed statistics
    for its mapped column. Never estimates a missing actual value - if the
    mapping is missing or the column has no valid numeric data, the result
    is marked not computable rather than guessed at.

    Args:
        disclosed_item: {label, value_text, unit, context_snippet} as
            returned by NumericDisclosureExtractor.
        actual_stats: compute_actual_value_stats()'s output for the
            dataset/column this item was mapped to, or None if unmapped.
        tolerance_abs: absolute difference (in the disclosure's own
            normalized units, e.g. 0.005 = half a percentage point for a
            rate) below which a numeric difference is not flagged.
        tolerance_pct: relative % difference (of the actual value) above
            which a match IS flagged, even if the absolute tolerance
            would have let it pass - catches a large relative miss on a
            small-magnitude figure that tolerance_abs alone would miss.

    Returns a dict with the disclosed figure, the actual stats (if any),
    the computed deviation, and a computable/flag verdict.
    """
    disclosed_value = parse_numeric(disclosed_item.get("value_text"))
    result = {
        **disclosed_item,
        "disclosed_value_parsed": disclosed_value,
        "actual_mean": None,
        "actual_min": None,
        "actual_max": None,
        "actual_distinct_count": None,
        "deviation": None,
        "deviation_pct": None,
        "computable": False,
        "flag": False,
        "reason": None,
    }

    if disclosed_value is None:
        result["reason"] = "Could not parse a single numeric value from the disclosed text (e.g. it's a range)."
        return result
    if actual_stats is None:
        result["reason"] = "Not mapped to a numeric dataset column."
        return result

    normalized_disclosed = normalize_to_decimal(disclosed_value, disclosed_item.get("unit", ""))
    actual_mean = actual_stats["mean"]

    deviation = normalized_disclosed - actual_mean
    deviation_pct = (abs(deviation) / abs(actual_mean) * 100) if actual_mean != 0 else None

    flagged = abs(deviation) > tolerance_abs and (
        deviation_pct is None or deviation_pct > tolerance_pct
    )

    result.update({
        "disclosed_value_parsed": normalized_disclosed,
        "actual_mean": actual_mean,
        "actual_min": actual_stats["min"],
        "actual_max": actual_stats["max"],
        "actual_distinct_count": actual_stats["distinct_count"],
        "deviation": deviation,
        "deviation_pct": deviation_pct,
        "computable": True,
        "flag": flagged,
    })
    return result


def reconcile_all(
    disclosed_items: List[Dict[str, Any]],
    mappings: Dict[int, Dict[str, str]],
    datasets: Dict[str, pl.DataFrame],
    tolerance_abs: float = 0.005,
    tolerance_pct: float = 10.0,
) -> List[Dict[str, Any]]:
    """Reconcile every extracted figure against its mapped dataset/column.

    Args:
        disclosed_items: NumericDisclosureExtractor's output.
        mappings: {item_index: {"dataset": name, "column": col}} - only
            items with an entry here are reconciled against real data;
            everything else comes back marked not computable.
        datasets: {name: DataFrame} - every dataset available to map into.
    """
    results = []
    for i, item in enumerate(disclosed_items):
        mapping = mappings.get(i)
        actual_stats = None
        if mapping and mapping.get("dataset") in datasets and mapping.get("column"):
            actual_stats = compute_actual_value_stats(datasets[mapping["dataset"]], mapping["column"])
        results.append(reconcile_disclosed_figure(item, actual_stats, tolerance_abs, tolerance_pct))
    return results
