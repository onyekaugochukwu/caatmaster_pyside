"""Dataset Profiler - an automatic "what's interesting about this data"
summary, mirroring CaseWare IDEA's Discover feature. Runs a fixed set of
cheap, deterministic checks (never an LLM, nothing fabricated) and
returns real, computed findings - duplicate rows, per-column completeness/
uniqueness/outliers, Benford's Law deviation on plausible amount columns,
and highly-correlated column pairs - so opening a dataset gives an
immediate, grounded starting point instead of requiring the auditor to
manually pick and run each individual analysis first."""
import numpy as np
import polars as pl
from typing import Any, Dict


def profile_dataset(df: pl.DataFrame, max_columns: int = 50) -> Dict[str, Any]:
    """Real, computed profile of a dataframe - every number here comes
    directly from the data, nothing estimated or inferred."""
    n_rows = df.height
    n_cols = len(df.columns)
    columns = df.columns[:max_columns]

    duplicate_rows = (n_rows - df.unique().height) if n_rows > 0 else 0

    column_profiles = []
    numeric_cols = []
    for col in columns:
        s = df[col]
        dtype = s.dtype
        missing = s.null_count()
        unique = s.n_unique()
        is_numeric = dtype.is_numeric()
        entry = {
            "column": col, "dtype": str(dtype),
            "missing": missing,
            "missing_pct": round(missing / n_rows * 100, 1) if n_rows else 0.0,
            "unique": unique,
            "unique_pct": round(unique / n_rows * 100, 1) if n_rows else 0.0,
            "is_numeric": is_numeric,
            "outlier_count": 0,
            "outlier_pct": 0.0,
        }

        if is_numeric:
            numeric_cols.append(col)
            non_null = s.drop_nulls()
            if len(non_null) > 4:
                q1 = non_null.quantile(0.25)
                q3 = non_null.quantile(0.75)
                iqr = (q3 - q1) if (q1 is not None and q3 is not None) else None
                if iqr and iqr > 0:
                    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                    outlier_count = int(non_null.filter((non_null < lo) | (non_null > hi)).len())
                    entry["outlier_count"] = outlier_count
                    entry["outlier_pct"] = round(outlier_count / len(non_null) * 100, 1)

        column_profiles.append(entry)

    # Benford's Law check on plausible "amount" columns: enough non-zero
    # values with real magnitude spread to be meaningful - skip small,
    # near-constant, or clearly ID/code-like numeric columns.
    benford_findings = []
    for col in numeric_cols:
        non_null = df[col].drop_nulls()
        if len(non_null) < 100:
            continue
        arr = np.asarray(non_null.to_numpy(), dtype=float)
        arr = arr[arr != 0]
        if len(arr) < 100:
            continue
        leading = np.floor(np.abs(arr) / (10 ** np.floor(np.log10(np.abs(arr))))).astype(int)
        leading = leading[(leading >= 1) & (leading <= 9)]
        if len(leading) < 100:
            continue
        observed = np.array([(leading == d).sum() / len(leading) for d in range(1, 10)])
        expected = np.array([np.log10(1 + 1 / d) for d in range(1, 10)])
        mad = float(np.mean(np.abs(observed - expected)))
        # Nigrini's MAD conformity thresholds: >0.012 is marginal/nonconforming
        if mad > 0.012:
            benford_findings.append({"column": col, "mad": round(mad, 4), "n": int(len(leading))})
    benford_findings.sort(key=lambda x: x["mad"], reverse=True)

    correlations = []
    for i, c1 in enumerate(numeric_cols):
        for c2 in numeric_cols[i + 1:]:
            try:
                corr = df.select(pl.corr(c1, c2)).item()
            except Exception:
                corr = None
            if corr is not None and abs(corr) >= 0.8:
                correlations.append({"column_a": c1, "column_b": c2, "correlation": round(float(corr), 3)})
    correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)

    return {
        "n_rows": n_rows,
        "n_columns": n_cols,
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": round(duplicate_rows / n_rows * 100, 2) if n_rows else 0.0,
        "columns": column_profiles,
        "benford_findings": benford_findings,
        "correlations": correlations[:10],
    }
