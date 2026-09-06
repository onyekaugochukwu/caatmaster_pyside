"""
Robust parsing of numeric figures as they actually appear in exported
financial statements - thousands separators, currency symbols, and the
standard accounting convention of showing a negative in parentheses.

Polars' native numeric cast only understands a bare numeric string
("1234" or "1234.56"). Every one of the formats below fails that cast,
and - critically - a lenient/"coerce" cast doesn't raise an error for the
failure, it silently turns the value into null. That is the actual
mechanism behind "ratios are never correctly parsed" for a real-world
financial statement export: a column of "1,234,567" / "(800,000)" /
"$1,234" values casts to nulls (or drops out of numeric-column detection
entirely, since every value in it "failed"), and every ratio computed
from that column comes out null or silently wrong - with no visible
error anywhere in the pipeline to point at.

This deliberately VALIDATES rather than blindly strips: a naive "remove
every character that isn't a digit/dot/minus" approach turns "Q1" into
"1" and "FY2023" into "2023" - a real, tested failure mode that would
misclassify a period label or invoice number as a numeric column. Only a
recognized currency symbol or an explicit, small allowlist of ISO
currency codes is stripped as a prefix (never an arbitrary letter run),
along with a trailing "%" and the sign markers; whatever remains must be
EXACTLY a signed, thousands-grouped decimal number or the whole value is
null.

Scope/caveat: assumes the common English-language convention where ","
is the thousands separator and "." is the decimal point (e.g.
"1,234,567.89"). A statement using the continental-European convention
("1.234.567,89") needs the opposite treatment and is NOT auto-detected
here - mixing both conventions into one heuristic produces silently wrong
numbers for whichever convention it guesses wrong, which is worse than
requiring an explicit choice. If continental-format statements are a real
need, add a separate `locale` parameter rather than trying to guess.
"""
import polars as pl

# A currency symbol, or one of a small, explicit set of ISO codes -
# deliberately NOT a generic [A-Za-z]{3} class, which would just as
# happily treat the first three letters of "INV-2024-001" or "ABC123" as
# a "currency code" and misparse the rest as a number.
_CURRENCY_CODES = (
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD",
    "INR", "CNY", "SGD", "HKD", "ZAR", "AED", "SAR",
)
_CURRENCY_PREFIX_PATTERN = r"^(?:[$€£¥₹]|(?:" + "|".join(_CURRENCY_CODES) + r"))\s*"
_TRAILING_PERCENT_PATTERN = r"\s*%\s*$"

# What must remain after sign markers, a currency prefix, and a trailing
# percent sign are removed: an optional leading minus, thousands-comma-
# grouped digits, and an optional decimal part. Anything else (letters,
# a second decimal point, stray punctuation) means this was never a
# number to begin with.
_CLEAN_NUMBER_PATTERN = r"^-?\d{1,3}(,\d{3})*(\.\d+)?$|^-?\d+(\.\d+)?$"


def clean_numeric_string_expr(column: str) -> pl.Expr:
    """Polars expression: parse `column` (any dtype) into a Float64,
    handling thousands separators, a recognized leading currency symbol/
    code, a trailing "%", a parenthesized negative ("(1,234)" -> -1234.0,
    "$(50,000)" -> -50000.0), and a trailing-minus convention some ERP
    exports use ("1234-" -> -1234.0).

    Returns null - never 0, never a fabricated value - for anything that
    isn't cleanly a single number even after removing those decorations:
    a blank cell, "N/A", a lone "-" placeholder, a range, or ordinary text
    that happens to contain a digit ("Q1", "FY2023", an invoice number) -
    the same as a normal failed cast, so it composes with strict/coerce
    semantics exactly like cast() does, just without misreading letters.
    """
    original = pl.col(column).cast(pl.Utf8, strict=False).str.strip_chars()

    is_paren_negative = original.str.contains(r"^[^0-9(]*\(") & original.str.ends_with(")")
    is_trailing_negative = original.str.ends_with("-") & ~is_paren_negative
    is_negative = is_paren_negative | is_trailing_negative

    core = (
        pl.when(is_paren_negative)
        .then(original.str.replace_all(r"^[^0-9(]*\(", "").str.replace_all(r"\)$", ""))
        .when(is_trailing_negative)
        .then(original.str.slice(0, original.str.len_chars() - 1))
        .otherwise(original)
    )
    core = core.str.replace_all(_CURRENCY_PREFIX_PATTERN, "")
    core = core.str.replace_all(_TRAILING_PERCENT_PATTERN, "")
    core = core.str.strip_chars()

    is_clean_number = core.str.contains(_CLEAN_NUMBER_PATTERN)
    digits_only = core.str.replace_all(",", "", literal=True)
    numeric = (
        pl.when(is_clean_number)
        .then(digits_only.cast(pl.Float64, strict=False))
        .otherwise(None)
    )

    return (
        pl.when(is_negative)
        .then(-numeric.abs())
        .otherwise(numeric)
    ).alias(column)


def clean_numeric_series(series: pl.Series) -> pl.Series:
    """Same parsing as clean_numeric_string_expr(), for a standalone
    Series rather than inside a lazy/eager DataFrame expression - used
    where only a Series (not a full DataFrame) is available, e.g. numeric-
    column detection over an already-selected column."""
    return (
        pl.DataFrame({"_v": series})
        .select(clean_numeric_string_expr("_v"))
        .to_series()
    )
