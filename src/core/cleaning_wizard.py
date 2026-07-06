"""
Data Cleaning Wizard — deterministic structure detection for messy imports.

Every detector here answers a checkable, verifiable question ("does this
row's value equal the sum of these other rows"), never a probabilistic
guess dressed up as a fact. When a detector can't confirm something with
confidence, it says nothing rather than forcing a low-confidence answer —
matching the same "don't fabricate" principle used throughout the AI
features. The wizard's UI (cleaning_wizard_dialog.py) presents whatever is
detected as a plan of ordinary, inspectable Applied Steps for a human to
accept, edit, or reject — never an automatically-executed black box.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import polars as pl


@dataclass
class CleaningStep:
    """One proposed step, expressed as a real operation_id + params the
    Applied Steps pipeline already knows how to execute."""
    operation_id: str
    params: Dict[str, Any]
    description: str
    confidence: str  # "high" (exact/verifiable) or "review" (needs a human call)
    accepted: bool = True


@dataclass
class CleaningPlan:
    steps: List[CleaningStep] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# Common ad-hoc missing-value markers seen in real spreadsheets — treated
# as equivalent to null for header/data detection, not as "a real
# non-numeric value". Without this, a single "???" placeholder in an
# early DATA row's numeric column drops that row's numeric fraction low
# enough to be misread as another header row — which doesn't just
# mislabel it, it gets that real data row REMOVED as "header junk".
_MISSING_VALUE_SENTINELS = {"", "na", "n/a", "null", "none", "nan", "-", "--",
                            "???", "??", "?", "unknown", "tbd", "#n/a", "#na"}


def _is_missing_marker(v) -> bool:
    return v is None or str(v).strip().lower() in _MISSING_VALUE_SENTINELS


def _is_numeric_value(v) -> bool:
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return True
    try:
        float(str(v))
        return True
    except (TypeError, ValueError):
        return False


def _is_multi_value_like(v) -> bool:
    """A cell containing a common multi-value delimiter (pipe/semicolon,
    see _MULTI_VALUE_DELIMITERS) is itself strong evidence of being real
    DATA, not a header label — column headers are essentially never
    delimiter-joined lists of values the way "Binders | Art | Phones" is.
    Without this, a dataset whose numeric column happens to ALSO be
    crammed into delimited multi-value cells (so it never parses as a
    single clean float) looks equally "non-numeric" in every row, header
    or data alike, and the row-count detector below can never find the
    transition between them."""
    if v is None:
        return False
    s = str(v)
    return any(d in s for d in _MULTI_VALUE_DELIMITERS)


def _is_row_header_like(df: pl.DataFrame, row_idx: int, numeric_threshold: float = 0.3) -> bool:
    """A row is 'header-like' if few of its non-null, non-placeholder
    values parse as numbers (or as multi-value delimited data) — real
    transactional data rows are mostly numbers/IDs/delimited value lists,
    labels and category headers are mostly plain text. Ad-hoc
    missing-value markers ("???", "-", "N/A", ...) are excluded from
    consideration entirely rather than counted as "present but
    non-numeric" — a row with a few blanks shouldn't be penalized as if
    it were made of real text values."""
    row = df.row(row_idx)
    non_null = [v for v in row if not _is_missing_marker(v)]
    if not non_null:
        return True
    data_like_count = sum(1 for v in non_null if _is_numeric_value(v) or _is_multi_value_like(v))
    return (data_like_count / len(non_null)) < numeric_threshold


def detect_header_row_count(df: pl.DataFrame, max_scan: int = 10) -> int:
    """How many leading rows look like header/label rows rather than data.
    Requires two consecutive data-like rows to confirm the transition, so
    a single stray text value in an early data row doesn't cause a false
    stop."""
    n = min(max_scan, len(df))
    for i in range(n):
        if not _is_row_header_like(df, i):
            if i + 1 >= n or not _is_row_header_like(df, i + 1):
                return i
    return 0


def detect_spanning_header_row(df: pl.DataFrame, row_idx: int) -> bool:
    """A merged-cell/spanning header row has a non-null label followed by
    a run of nulls (the merge's other cells), repeated across at least two
    separate groups — not just an occasional isolated blank."""
    row = df.row(row_idx)
    n = len(row)
    groups = 0
    i = 0
    while i < n:
        val = row[i]
        if val is not None and str(val).strip() != "":
            j = i + 1
            null_run = 0
            while j < n and (row[j] is None or str(row[j]).strip() == ""):
                null_run += 1
                j += 1
            if null_run >= 1:
                groups += 1
            i = j
        else:
            i += 1
    return groups >= 2


def detect_blank_rows(df: pl.DataFrame) -> List[int]:
    """Row indices where every value is null."""
    if df.height == 0:
        return []
    mask = df.select(pl.all_horizontal(pl.all().is_null()).alias("_blank"))["_blank"]
    return [i for i, v in enumerate(mask) if v]


def detect_blank_columns(df: pl.DataFrame) -> List[str]:
    return [c for c in df.columns if df[c].null_count() == df.height]


def detect_missing_value_markers(data_view: pl.DataFrame) -> Dict[str, List[str]]:
    """For each column, find which known missing-value sentinel tokens
    (e.g. "???", "-", "N/A") appear as an exact, whole-value match in the
    data. Deliberately narrow: only the well-known conventions in
    _MISSING_VALUE_SENTINELS count, not just any low-cardinality or
    unusual token — a column could legitimately use a short code like
    "-" as a real business value, so this is a candidate list for the
    wizard to propose (review confidence, never auto-applied), not a
    verified fact the way the row/column removal detectors are."""
    result: Dict[str, List[str]] = {}
    if data_view.height == 0:
        return result
    for col in data_view.columns:
        series = data_view[col].cast(pl.Utf8, strict=False).str.strip_chars()
        distinct_vals = series.drop_nulls().unique().to_list()
        found = [v for v in distinct_vals if v and v.lower() in _MISSING_VALUE_SENTINELS]
        if found:
            result[col] = found
    return result


def build_numeric_view(df: pl.DataFrame, data_row_indices: List[int]) -> pl.DataFrame:
    """Extract the data rows and cast each column to Float64 where
    possible (non-numeric values become null in this VIEW only — the
    original dataframe is untouched). A raw, no-header import reads every
    column as strings, so subtotal/footer detection needs this cast
    before it can check any real numeric relationship."""
    if not data_row_indices:
        return df.clear()
    sub = df[data_row_indices]
    return sub.with_columns([
        pl.col(c).cast(pl.Float64, strict=False).alias(c) for c in sub.columns
    ])


def detect_footer_subtotal_row(numeric_view: pl.DataFrame, data_row_indices: List[int],
                                tolerance: float = 0.01) -> Optional[int]:
    """Is the LAST data row a grand-total footer? For each numeric column,
    check whether its value equals the sum of that column across every
    OTHER data row, within floating-point tolerance — an exact, checkable
    fact. Requires a strong majority of numeric columns to agree before
    concluding it's a footer, so one coincidental match doesn't trigger a
    false positive. Returns the ORIGINAL dataframe's row index (mapped via
    data_row_indices), not a position within numeric_view."""
    if numeric_view.height < 4:
        return None
    last_pos = numeric_view.height - 1
    other_view = numeric_view[:-1]

    numeric_cols = [c for c in numeric_view.columns if numeric_view[c].null_count() < numeric_view.height]
    if not numeric_cols:
        return None

    matches = 0
    checked = 0
    for col in numeric_cols:
        last_val = numeric_view[col][last_pos]
        if last_val is None:
            continue
        other_sum = other_view[col].sum()
        if other_sum is None:
            continue
        checked += 1
        if abs(float(last_val) - float(other_sum)) <= tolerance * max(abs(float(other_sum)), 1.0):
            matches += 1

    if checked == 0 or checked / len(numeric_cols) < 0.5:
        return None
    if matches / checked >= 0.8:
        return data_row_indices[last_pos]
    return None


# The classic structural multi-value separators - deliberately narrow.
# Comma is excluded: it's routinely a real character in ordinary text
# fields (addresses, names) or a thousands separator, so treating it as a
# "this cell holds multiple values" signal would false-positive constantly.
_MULTI_VALUE_DELIMITERS = ['|', ';']


def detect_multi_value_columns(raw_data_view: pl.DataFrame, candidate_cols: List[str]) -> Optional[Dict[str, Any]]:
    """Do 2+ columns hold delimiter-separated multiple values per row, with
    MATCHING item counts row-by-row — e.g. a "Category" column and an
    "Amount" column both pipe-separated with the same number of items in
    every row, meaning position i in one pairs with position i in the
    other and the row actually represents multiple observations (multiple
    line items on one order) crammed into one. Verified exactly: every
    candidate row's delimiter count must match across the columns being
    proposed, and a meaningful fraction of rows must actually be
    multi-valued, or there's nothing worth splitting."""
    if raw_data_view.height == 0:
        return None

    for delimiter in _MULTI_VALUE_DELIMITERS:
        candidates = [
            c for c in candidate_cols
            if raw_data_view[c].dtype == pl.Utf8
            and bool(raw_data_view[c].str.contains(delimiter, literal=True).fill_null(False).any())
        ]
        if len(candidates) < 2:
            continue

        counts = {c: raw_data_view[c].fill_null("").str.count_matches(delimiter, literal=True) for c in candidates}

        base_col = candidates[0]
        matching = [base_col]
        for c in candidates[1:]:
            if (counts[c] == counts[base_col]).all():
                matching.append(c)
        if len(matching) < 2:
            continue

        multi_value_rows = int((counts[base_col] > 0).sum())
        if multi_value_rows == 0 or multi_value_rows / raw_data_view.height < 0.2:
            continue

        return {"delimiter": delimiter, "columns": matching, "multi_value_rows": multi_value_rows}

    return None


def detect_subtotal_columns(numeric_view: pl.DataFrame,
                             max_group_size: int = 8, tolerance: float = 0.01) -> Dict[str, List[str]]:
    """For each numeric column, check whether it equals the row-wise sum
    of a contiguous block of the columns immediately preceding it — the
    standard pivot-table-export pattern (a subtotal column right after its
    group). Verified per-row against numeric_view (already cast to
    Float64), not assumed from column position or name."""
    col_order = numeric_view.columns
    numeric_cols = {c for c in col_order if numeric_view[c].null_count() < numeric_view.height}
    subtotal_map: Dict[str, List[str]] = {}
    consumed = set()  # a column already claimed as part of another group

    if numeric_view.height == 0:
        return {}

    for idx, col in enumerate(col_order):
        if col not in numeric_cols or col in consumed:
            continue
        target = numeric_view[col].fill_null(0)
        # Sparse pivot-export data (like this one) is mostly zero/null per
        # column, so a naive "diff <= tolerance" check trivially matches
        # 0≈0 across almost any candidate group — that's not evidence of a
        # real subtotal relationship, just sparsity. Only rows where the
        # candidate column has a genuine non-zero value count as evidence,
        # and there must be enough of them to mean something. Groups are
        # tried LARGEST-first so a real 4-column group wins over a
        # coincidentally-matching 3-column subset of it.
        nonzero_mask = target.abs() > 1e-9
        nonzero_count = int(nonzero_mask.sum())
        if nonzero_count < 3:
            continue
        for group_size in range(max_group_size, 1, -1):
            start = idx - group_size
            if start < 0:
                continue
            group_cols = col_order[start:idx]
            if not all(c in numeric_cols for c in group_cols) or any(c in consumed for c in group_cols):
                continue
            row_sum = numeric_view.select(
                pl.sum_horizontal([pl.col(c).fill_null(0) for c in group_cols]).alias("_s")
            )["_s"]
            diffs = (row_sum - target).abs()
            denom = target.abs().clip(lower_bound=1.0)
            within_tol = (diffs <= tolerance * denom)
            # Only score the rows where the candidate column is genuinely
            # non-zero — those are the only rows that actually test the
            # relationship rather than trivially matching on sparsity.
            evidence = within_tol.filter(nonzero_mask)
            match_frac = evidence.sum() / len(evidence) if len(evidence) else 0
            if match_frac >= 0.95:
                subtotal_map[col] = list(group_cols)
                consumed.add(col)
                consumed.update(group_cols)
                break
    return subtotal_map


def _first_spanning_column(row: list) -> int:
    """Index of the first column where this row has a genuine merge
    group — a label immediately followed by 1+ blanks (e.g. "Consumer"
    followed by 3 blanks it covers). Columns before this point sit
    entirely outside any spanning region: either leading identifier
    columns (e.g. "Order ID"/"Order Date"), or a leading row-caption
    label (e.g. "Segment>>", "Ship Mode>>", "Month") that describes the
    row as a whole rather than being a per-column value itself — such a
    caption is always immediately followed by ANOTHER real value, not a
    blank, which is exactly what distinguishes it here. Returns len(row)
    if the row has no genuine merge group at all."""
    n = len(row)
    i = 0
    while i < n:
        val = row[i]
        if val is not None and str(val).strip() != "":
            j = i + 1
            null_run = 0
            while j < n and (row[j] is None or str(row[j]).strip() == ""):
                null_run += 1
                j += 1
            if null_run >= 1:
                return i
            i = j
        else:
            i += 1
    return n


def _fill_row_blanks(row: list) -> list:
    """Plain forward-fill: each blank gets the nearest preceding real
    value. Never touches a position that already has its own value —
    unlike an earlier version of this logic, which tried to also exclude
    "caption" cells here and ended up excluding legitimate, densely
    packed per-column labels too (a row like "Region/Product, Range
    Rover, Toyota, ..." has no blanks between its labels, but each one
    is a real value for its own column, not a caption to be discarded).
    That distinction is handled once, upstream, via
    _first_spanning_column — this function just fills blanks."""
    filled = list(row)
    last = None
    for i, v in enumerate(row):
        if v is not None and str(v).strip() != "":
            last = v
        elif last is not None:
            filled[i] = last
    return filled


def _combine_header_hint(df: pl.DataFrame, header_row_count: int) -> Dict[str, str]:
    """Suggested combined column names from a multi-row header — offered
    as a candidate rename_columns step (review confidence: the user
    should see and confirm it, but it's the whole point of the feature,
    not just a note telling them to go do 12 renames by hand themselves).

    Uses the TOP header row (row 0) to find where the genuine spanning
    region starts (see _first_spanning_column). Columns before that
    boundary are identifier columns: each gets its own single,
    most-specific label, found by searching the header rows bottom-up.
    Columns at or after the boundary combine every header row's
    (blank-filled) value for that position, top to bottom."""
    if header_row_count < 1:
        return {}

    top_row = list(df.row(0))
    boundary = _first_spanning_column(top_row)
    # Only fill rows that are genuinely spanning (a real merge group
    # somewhere in them) — a non-spanning row like a lone "Order ID"
    # label followed by blanks everywhere else would otherwise have that
    # label smeared across every remaining column with nothing to stop
    # it, since plain forward-fill has no way to tell "this row simply
    # has nothing else" apart from "this row's one real value applies
    # to everything after it".
    filled_rows = [
        _fill_row_blanks(list(df.row(r))) if detect_spanning_header_row(df, r) else list(df.row(r))
        for r in range(header_row_count)
    ]

    hints = {}
    name_seen: Dict[str, int] = {}

    def _dedupe(name: str) -> str:
        # Stripping whitespace can reveal that two columns' header text is
        # actually identical (e.g. one had a trailing space that made it
        # look different before) - suffix rather than collide, the same
        # duplicate-handling promote_row_as_header already does, so this
        # never raises on a plain df.rename() collision downstream.
        if name in name_seen:
            name_seen[name] += 1
            return f"{name}_{name_seen[name]}"
        name_seen[name] = 0
        return name

    for col_idx, col in enumerate(df.columns):
        if col_idx < boundary:
            for r in range(header_row_count - 1, -1, -1):
                val = df.row(r)[col_idx]
                stripped = str(val).strip() if val is not None else ""
                if stripped:
                    hints[col] = _dedupe(stripped)
                    break
        else:
            parts = []
            for r in range(header_row_count):
                val = filled_rows[r][col_idx]
                stripped = str(val).strip() if val is not None else ""
                if stripped and (not parts or stripped != parts[-1]):
                    parts.append(stripped)
            if parts:
                hints[col] = _dedupe(" | ".join(parts))
    return hints


def _simulate_promoted_columns(df: pl.DataFrame, row_index: int) -> List[str]:
    """Compute the column names promote_row_as_header (data_processor.py)
    would produce, without running it — so later detection (blank/
    subtotal columns, unpivot candidates) can reference the names that
    will ACTUALLY exist once an earlier promote_row_header step has run,
    not the raw pre-promotion 'column_N' names. Must match
    DataProcessor.promote_row_as_header's renaming exactly, including its
    duplicate-handling, or a later step could reference a name that
    doesn't exist."""
    row = df.row(row_index)
    new_headers = []
    seen: Dict[str, int] = {}
    for i, h in enumerate(row):
        h_str = str(h).strip() if h is not None else f"col_{i}"
        if h_str in seen:
            seen[h_str] += 1
            h_str = f"{h_str}_{seen[h_str]}"
        else:
            seen[h_str] = 0
        new_headers.append(h_str)
    return new_headers


def build_cleaning_plan(df: pl.DataFrame) -> CleaningPlan:
    """Run all detectors over a raw (no-header-assumed) dataframe and
    assemble a plan of proposed Applied Steps. Every step maps to a real,
    existing operation — this function never touches the data itself.

    All row-removal candidates (header junk, blank rows, footer row) are
    combined into ONE remove_rows step, with indices computed relative to
    the original, still-untouched dataframe. This matters: if these were
    separate sequential steps, each one would shift every row position
    after it, silently invalidating the row indices any later step was
    computed against. A single combined removal sidesteps that entirely.
    promote_row_header (used only in the single-header-row case) is safe
    to run after it, since every row it removes sits at or after row 0 —
    row 0 itself is never touched by the removal, so its position doesn't
    shift."""
    plan = CleaningPlan()

    header_row_count = detect_header_row_count(df)
    rows_to_remove: set = set()
    promote_single_header = False
    header_hints: Dict[str, str] = {}

    if header_row_count == 0:
        plan.notes.append("No header rows detected above the data — the first row looks like it's already a proper single header.")
        data_start = 0
    elif header_row_count == 1:
        promote_single_header = True
        data_start = 1
    else:
        plan.notes.append(
            f"Rows 1-{header_row_count} all look like header/label rows spanning multiple layers, not a "
            f"single usable header — removing them and applying the suggested combined names below."
        )
        header_hints = _combine_header_hint(df, header_row_count)
        if header_hints:
            renames = [{"old_name": col, "new_name": name} for col, name in header_hints.items() if name != col]
            if renames:
                preview = "; ".join(f'{r["old_name"]} → "{r["new_name"]}"' for r in renames[:6])
                more = f", and {len(renames) - 6} more" if len(renames) > 6 else ""
                plan.steps.append(CleaningStep(
                    operation_id="rename_columns",
                    params={"renames": renames},
                    description=(
                        f"Combine the {header_row_count} header rows' labels into one meaningful name per "
                        f"column, e.g. {preview}{more} — otherwise this information (which segment, which "
                        f"ship mode, ...) only exists as generic 'column_N' names and is effectively lost "
                        f"once the data is unpivoted."
                    ),
                    confidence="review",
                ))
        rows_to_remove.update(range(header_row_count))
        data_start = header_row_count

    data_row_indices = [r for r in range(data_start, df.height) if r not in rows_to_remove]

    blank_rows = [r for r in detect_blank_rows(df) if r in data_row_indices]
    rows_to_remove.update(blank_rows)
    data_row_indices = [r for r in data_row_indices if r not in blank_rows]

    # Numeric-cast view of the data rows only, needed because a raw
    # (no-header) import reads every column as strings — the subtotal/
    # footer detectors need real numeric comparisons.
    numeric_view = build_numeric_view(df, data_row_indices)

    footer_row = detect_footer_subtotal_row(numeric_view, data_row_indices)
    if footer_row is not None:
        rows_to_remove.add(footer_row)
        data_row_indices = [r for r in data_row_indices if r != footer_row]
        numeric_view = build_numeric_view(df, data_row_indices)

    if rows_to_remove:
        reasons = []
        if header_row_count > 1:
            reasons.append(f"{header_row_count} header/label row(s)")
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

    # From here on, every column-name-based detection must reference the
    # names columns will ACTUALLY have once the steps above have run, not
    # df's raw pre-promotion names — promote_row_header renames every
    # column, so a later step (e.g. unpivot) naming a raw "column_N" would
    # silently reference something that no longer exists by the time it
    # executes. This single rename keeps every detector below consistent
    # with reality regardless of whether promotion happened.
    if promote_single_header:
        plan.steps.append(CleaningStep(
            operation_id="promote_row_header",
            params={"row_index": 0},
            description="Row 1 is a single, clean header row — promote it to column names.",
            confidence="high",
        ))
        effective_columns = _simulate_promoted_columns(df, 0)
    else:
        # If a rename_columns step was proposed above (combining the
        # multi-row header into meaningful names), everything downstream
        # should reference those names — not the raw "column_N" ones that
        # will no longer exist once that step runs.
        effective_columns = [header_hints.get(c, c) for c in df.columns]
    rename_map = dict(zip(df.columns, effective_columns))
    numeric_view = numeric_view.rename(rename_map)

    # Raw (un-cast) view of the data rows, with effective column names —
    # needed anywhere the actual string values matter, not just whether
    # something casts to a number.
    raw_data_view = df[data_row_indices].rename(rename_map) if data_row_indices else df.rename(rename_map)

    # Missing-value marker columns — a different KIND of dirt than the
    # structural checks around it (it's about cell VALUES, not shape), but
    # cheap to detect from the same raw_data_view and worth surfacing here
    # rather than leaving entirely to a separate pass. Always "review"
    # confidence: recognizing "???" as a stand-in for missing data is a
    # judgment call, not a verified fact like a subtotal-column sum match.
    missing_marker_map = detect_missing_value_markers(raw_data_view)
    for col, markers in missing_marker_map.items():
        plan.steps.append(CleaningStep(
            operation_id="standardize_missing_values",
            params={"column": col, "markers": markers, "case_sensitive": False},
            description=(
                f"Column '{col}' contains {', '.join(repr(m) for m in markers)} — common stand-ins for "
                f"missing data. Replace them with a true null (in place) rather than leaving them as text "
                f"that a later type conversion would trip over."
            ),
            confidence="review",
        ))

    # Blank columns — checked over the DATA rows only (post row-removal),
    # not the raw dataframe, which still has header/label text sitting in
    # what will become row 0 of the header-promoted view and would mask a
    # genuinely all-null data column.
    blank_cols = detect_blank_columns(numeric_view) if numeric_view.height else []
    # detect_blank_columns on a Float64-cast view only proves a column is
    # blank of NUMBERS, not blank of everything (a text column would show
    # as "all null" post-cast even with real values) — recheck against
    # the real un-cast values before proposing removal.
    if blank_cols:
        blank_cols = [c for c in blank_cols if raw_data_view[c].null_count() == raw_data_view.height]
    if blank_cols:
        plan.steps.append(CleaningStep(
            operation_id="choose_columns",
            params={"action": "remove", "columns_to_remove": blank_cols},
            description=f"Remove {len(blank_cols)} fully blank column(s): {', '.join(blank_cols)}.",
            confidence="high",
        ))

    # Subtotal columns — exact, checkable (row-wise sum match)
    subtotal_map = detect_subtotal_columns(numeric_view)
    if subtotal_map:
        cols_to_remove = list(subtotal_map.keys())
        detail = "; ".join(f"'{k}' = sum of {v}" for k, v in subtotal_map.items())
        plan.steps.append(CleaningStep(
            operation_id="choose_columns",
            params={"action": "remove", "columns_to_remove": cols_to_remove},
            description=(
                f"{len(cols_to_remove)} column(s) exactly equal the row-wise sum of their neighboring "
                f"columns ({detail}) — these are subtotal columns, not independent measures. Removing them "
                f"avoids double-counting once the data is unpivoted."
            ),
            confidence="high",
        ))

    # Wide-format candidate: after the cleanup above, if most of the
    # remaining columns are numeric with only a couple of non-numeric
    # "identifier" columns, this looks like a pivoted/wide table that
    # wants to be long/tidy — one row per (id, measure) instead of one
    # column per measure. This is proposed, not auto-executed: unlike the
    # steps above (each verified by an exact arithmetic check), "these
    # columns are the identifiers and those are the values" is a judgment
    # call about what the data MEANS, not something to confirm mechanically.
    remaining_cols = [c for c in effective_columns if c not in blank_cols and c not in subtotal_map]

    # Multi-value delimited columns — exact, checkable (matching delimiter
    # counts row-by-row across 2+ columns), and structural like the steps
    # above: the row genuinely represents multiple observations, not one.
    multi_value = detect_multi_value_columns(raw_data_view, remaining_cols)
    if multi_value:
        mv_cols = multi_value["columns"]
        delimiter_option = "pipe" if multi_value["delimiter"] == "|" else "semicolon"
        plan.steps.append(CleaningStep(
            operation_id="split_into_rows",
            params={"columns": mv_cols, "delimiter": delimiter_option},
            description=(
                f"{', '.join(mv_cols)} are consistently '{multi_value['delimiter']}'-separated with matching "
                f"item counts in {multi_value['multi_value_rows']} row(s) — each such row actually represents "
                f"multiple observations crammed into one (e.g. multiple line items on one order). Splitting "
                f"these into separate rows, one per item, turns each into its own proper observation."
            ),
            confidence="high",
        ))

    if len(remaining_cols) >= 3:
        numeric_remaining = [c for c in remaining_cols if numeric_view[c].null_count() < numeric_view.height]
        non_numeric_remaining = [c for c in remaining_cols if c not in numeric_remaining]
        numeric_frac = len(numeric_remaining) / len(remaining_cols)
        if numeric_frac >= 0.6 and non_numeric_remaining:
            plan.steps.append(CleaningStep(
                operation_id="unpivot_table",
                params={
                    "id_vars": non_numeric_remaining,
                    "value_vars": numeric_remaining,
                    "var_name": "variable",
                    "value_name": "value",
                },
                description=(
                    f"{len(numeric_remaining)} of the {len(remaining_cols)} remaining columns are numeric "
                    f"measures spread across separate columns, with {', '.join(non_numeric_remaining)} as the "
                    f"only identifier column(s) — this looks like a wide/pivoted table. Proposing an unpivot "
                    f"into long format (one row per identifier + measure). Review the id/value column split "
                    f"before accepting — this is the one judgment call in this plan, not an exact check like "
                    f"the steps above."
                ),
                confidence="review",
            ))
            if header_row_count > 1:
                plan.notes.append(
                    "This table's column names came from a single header row, so the unpivoted 'variable' "
                    "column will hold whatever that row's labels were (e.g. combined Segment/Ship-Mode names "
                    "if you merged header layers manually) — Split Column can break it back apart if needed."
                )

            # A wide/pivoted table's value columns are typically sparse —
            # each row real belongs to exactly one of them — so unpivoting
            # produces mostly-null "value" rows that need filtering out.
            # This is bundled with the unpivot rather than proposed
            # separately: if you accept the unpivot, this cleanup follows
            # directly from it rather than being its own judgment call.
            null_fracs = [numeric_view[c].null_count() / numeric_view.height for c in numeric_remaining] if numeric_view.height else []
            if null_fracs and (sum(null_fracs) / len(null_fracs)) > 0.3:
                plan.steps.append(CleaningStep(
                    operation_id="filter_rows",
                    params={"column": "value", "operator": "is_not_null", "value": ""},
                    description=(
                        "The value columns above are mostly null per row (each row only really belongs to "
                        "one of them) — after unpivoting, filter out the null 'value' rows this produces, "
                        "matching the pattern you'd want for any sparse pivot-table export."
                    ),
                    confidence="review",
                ))

    if not plan.steps:
        plan.notes.append("No structural issues detected — this data already looks clean (single header row, no blank rows/columns, no subtotal rows/columns).")

    return plan
