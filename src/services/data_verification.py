"""Data Verification - validates column contents against declared
expectations. Unlike a dtype cast (which
silently nulls or crashes on a bad value), this is a deliberate, reviewable
check: "this column should be numeric/a valid date/unique/positive/in
range - how many values actually violate that, and which check failed."
Returns a report (one row per check), never modifies the dataset."""
from typing import Any, Dict, List

import polars as pl


CHECK_TYPES = ["numeric", "date", "no_nulls", "unique", "positive", "in_range"]


def verify_data_integrity(df: pl.DataFrame, checks: List[Dict[str, Any]]) -> pl.DataFrame:
    """Run a list of {"column", "check_type", ...} checks against df and
    return one row per check: fail_count, pass/fail, and a plain-text
    detail. Every number here is directly computed from the real data."""
    results = []

    for check in checks:
        column = check.get("column")
        check_type = check.get("check_type")
        s = df[column]
        non_null = s.drop_nulls()
        n = len(df)
        fail_count = None
        detail = ""

        if check_type == "numeric":
            if s.dtype.is_numeric():
                fail_count = 0
            else:
                parsed = non_null.cast(pl.Utf8).str.strip_chars().cast(pl.Float64, strict=False)
                fail_count = int(parsed.is_null().sum())
            detail = f"{fail_count:,} value(s) don't parse as numeric"

        elif check_type == "date":
            if s.dtype in (pl.Date, pl.Datetime):
                fail_count = 0
            else:
                parsed = non_null.cast(pl.Utf8).str.to_date(strict=False)
                fail_count = int(parsed.is_null().sum())
            detail = f"{fail_count:,} value(s) don't parse as a date"

        elif check_type == "no_nulls":
            fail_count = int(s.null_count())
            detail = f"{fail_count:,} null value(s) found"

        elif check_type == "unique":
            fail_count = int(n - s.n_unique())
            detail = f"{fail_count:,} duplicate occurrence(s) found"

        elif check_type == "positive":
            if s.dtype.is_numeric():
                fail_count = int(non_null.filter(non_null <= 0).len())
                detail = f"{fail_count:,} non-positive value(s) found"
            else:
                detail = "column is not numeric - check skipped"

        elif check_type == "in_range":
            lo, hi = check.get("min"), check.get("max")
            if s.dtype.is_numeric() and lo is not None and hi is not None:
                fail_count = int(non_null.filter((non_null < lo) | (non_null > hi)).len())
                detail = f"{fail_count:,} value(s) outside [{lo}, {hi}]"
            else:
                detail = "column is not numeric or min/max not given - check skipped"

        else:
            detail = f"Unknown check type '{check_type}'"

        results.append({
            "column": column,
            "check": check_type,
            "fail_count": fail_count,
            "status": "PASS" if fail_count == 0 else ("FAIL" if fail_count is not None else "SKIPPED"),
            "detail": detail,
        })

    return pl.DataFrame(results)
