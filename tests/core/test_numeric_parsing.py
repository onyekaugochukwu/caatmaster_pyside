"""
Tests for core.numeric_parsing - the shared numeric-string cleaner for
financial-statement-formatted figures (thousands separators, currency
symbols, parenthesized negatives).
"""
import pytest
import polars as pl

from core.numeric_parsing import clean_numeric_series, clean_numeric_string_expr


class TestCleanNumericSeries:
    def test_thousands_separator(self):
        result = clean_numeric_series(pl.Series(["1,234,567"]))
        assert result.to_list() == [1234567.0]

    def test_parenthesized_negative(self):
        result = clean_numeric_series(pl.Series(["(800,000)"]))
        assert result.to_list() == [-800000.0]

    def test_currency_symbol_prefix(self):
        result = clean_numeric_series(pl.Series(["$1,234"]))
        assert result.to_list() == [1234.0]

    def test_currency_symbol_with_parens(self):
        result = clean_numeric_series(pl.Series(["$(50,000)"]))
        assert result.to_list() == [-50000.0]

    def test_currency_code_with_space_and_parens(self):
        result = clean_numeric_series(pl.Series(["USD (500)"]))
        assert result.to_list() == [-500.0]

    def test_currency_code_no_space_with_parens(self):
        result = clean_numeric_series(pl.Series(["GBP(500)"]))
        assert result.to_list() == [-500.0]

    def test_decimal_with_thousands(self):
        result = clean_numeric_series(pl.Series(["434,567.89"]))
        assert result.to_list() == [pytest.approx(434567.89)]

    def test_trailing_minus(self):
        result = clean_numeric_series(pl.Series(["1234-"]))
        assert result.to_list() == [-1234.0]

    def test_leading_minus(self):
        result = clean_numeric_series(pl.Series(["-1234"]))
        assert result.to_list() == [-1234.0]

    def test_whitespace_padding(self):
        result = clean_numeric_series(pl.Series(["  1,000  "]))
        assert result.to_list() == [1000.0]

    def test_plain_integer_still_works(self):
        result = clean_numeric_series(pl.Series(["1234"]))
        assert result.to_list() == [1234.0]

    def test_non_numeric_placeholder_returns_null_not_zero(self):
        for placeholder in ["N/A", "-", "", "n/a", "TBD"]:
            result = clean_numeric_series(pl.Series([placeholder]))
            assert result.to_list() == [None], f"{placeholder!r} should parse to None"

    def test_none_stays_none(self):
        result = clean_numeric_series(pl.Series([None], dtype=pl.Utf8))
        assert result.to_list() == [None]

    def test_zero(self):
        result = clean_numeric_series(pl.Series(["0"]))
        assert result.to_list() == [0.0]

    def test_already_numeric_dtype_passes_through(self):
        result = clean_numeric_series(pl.Series([1234.5]))
        assert result.to_list() == [1234.5]

    def test_batch_of_mixed_values(self):
        values = ["1,234,567", "(800,000)", "434,567.89", None, "N/A"]
        result = clean_numeric_series(pl.Series(values))
        assert result.to_list() == [1234567.0, -800000.0, pytest.approx(434567.89), None, None]

    def test_trailing_percent(self):
        result = clean_numeric_series(pl.Series(["100%"]))
        assert result.to_list() == [100.0]

    def test_unrecognized_currency_code_not_stripped(self):
        # Only a small explicit allowlist of ISO codes is treated as a
        # currency prefix - anything else must fail closed to None rather
        # than guess.
        result = clean_numeric_series(pl.Series(["XYZ 100"]))
        assert result.to_list() == [None]


class TestFalsePositiveGuards:
    """A label that happens to contain digits must never be silently
    misread as a number - this is the exact failure mode that made a
    naive 'strip every non-digit character' approach turn "Q1" into 1.0
    and "FY2023" into 2023.0, corrupting numeric-column detection."""

    def test_quarter_label(self):
        result = clean_numeric_series(pl.Series(["Q1"]))
        assert result.to_list() == [None]

    def test_fiscal_year_label(self):
        result = clean_numeric_series(pl.Series(["FY2023"]))
        assert result.to_list() == [None]

    def test_invoice_number(self):
        result = clean_numeric_series(pl.Series(["INV-2024-001"]))
        assert result.to_list() == [None]

    def test_alphanumeric_code(self):
        result = clean_numeric_series(pl.Series(["A123"]))
        assert result.to_list() == [None]

    def test_trailing_letter(self):
        result = clean_numeric_series(pl.Series(["12A"]))
        assert result.to_list() == [None]

    def test_three_letter_code_prefix_not_in_allowlist(self):
        result = clean_numeric_series(pl.Series(["ABC123"]))
        assert result.to_list() == [None]

    def test_indian_lakh_grouping_not_misparsed(self):
        # "1,23,456" (Indian-style grouping = 123,456) doesn't match the
        # western thousands-grouping pattern - correctly fails closed to
        # None rather than silently misreading the grouping.
        result = clean_numeric_series(pl.Series(["1,23,456"]))
        assert result.to_list() == [None]


class TestCleanNumericStringExpr:
    def test_works_inside_with_columns(self):
        df = pl.DataFrame({"amount": ["1,234,567", "(800,000)", "N/A"]})
        result = df.with_columns(clean_numeric_string_expr("amount"))
        assert result["amount"].to_list() == [1234567.0, -800000.0, None]

    def test_preserves_column_name(self):
        df = pl.DataFrame({"revenue": ["1,000"]})
        result = df.select(clean_numeric_string_expr("revenue"))
        assert result.columns == ["revenue"]
        assert result["revenue"].to_list() == [1000.0]
