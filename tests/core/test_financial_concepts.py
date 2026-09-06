"""
Tests for core.financial_concepts - concept-detection regex patterns and
suggest_concept_for_text()'s specificity-based, ambiguity-safe matching.

Several of these encode bugs found by direct investigation: overlapping
patterns that made a real line item silently map to the WRONG concept
with no visible error (e.g. "Retained Earnings" always resolving to
Total Equity), which is a root cause of "ratios never correctly parsed"
independent of any numeric-parsing issue.
"""
import pytest

from core.financial_concepts import suggest_concept_for_text, is_likely_total_row


class TestRetainedEarningsVsTotalEquity:
    """Both concepts used to share the pattern r"retained.?earn" - dict
    iteration order meant total_equity's copy always won, so the
    dedicated retained_earnings concept could never actually be reached."""

    def test_retained_earnings_maps_to_its_own_concept(self):
        assert suggest_concept_for_text("Retained Earnings") == "retained_earnings"

    def test_accumulated_profit_maps_to_retained_earnings(self):
        assert suggest_concept_for_text("Accumulated Profit") == "retained_earnings"

    def test_total_equity_still_detected_on_its_own(self):
        assert suggest_concept_for_text("Total Equity") == "total_equity"
        assert suggest_concept_for_text("Shareholders Equity") == "total_equity"


class TestOperatingIncomeVsRevenue:
    """Both concepts used to share r"operating.?income" - dict order made
    "Operating Income" always resolve to revenue instead of ebit,
    feeding an EBIT-sized figure into every ratio that uses top-line
    revenue."""

    def test_operating_income_maps_to_ebit_not_revenue(self):
        assert suggest_concept_for_text("Operating Income") == "ebit"

    def test_revenue_labels_still_map_to_revenue(self):
        for label in ["Revenue", "Total Revenue", "Net Sales", "Turnover"]:
            assert suggest_concept_for_text(label) == "revenue"


class TestOverlyBroadPatternsRemoved:
    """"reserve" and a bare "earn" used to be broad enough to catch
    non-equity/non-net-income line items that merely contain those
    substrings."""

    def test_warranty_reserve_is_not_equity(self):
        # No "warranty" concept exists in the taxonomy at all - before the
        # fix, this matched total_equity purely because of the bare
        # "reserve" pattern, not because of anything to do with equity.
        assert suggest_concept_for_text("Warranty Reserve") is None

    def test_earnings_per_share_is_not_net_income(self):
        assert suggest_concept_for_text("Earnings Per Share") is None

    def test_net_income_still_detected(self):
        assert suggest_concept_for_text("Net Income") == "net_income"
        assert suggest_concept_for_text("Profit After Tax") == "net_income"


class TestProfitForTheYearVariants:
    """r"profit.?for.?year" only allowed a single optional character
    between "for" and "year", so the extremely common IFRS-style label
    "Profit for the Year" (with "the" in between) never matched at all."""

    def test_profit_for_the_year(self):
        assert suggest_concept_for_text("Profit for the Year") == "net_income"

    def test_profit_for_year_without_the(self):
        assert suggest_concept_for_text("Profit for Year") == "net_income"


class TestSpecificityRanking:
    def test_total_current_assets_prefers_current_assets_over_total_assets(self):
        assert suggest_concept_for_text("Total Current Assets") == "current_assets"

    def test_total_assets_alone_maps_to_total_assets(self):
        assert suggest_concept_for_text("Total Assets") == "total_assets"

    def test_total_current_liabilities_prefers_current_liabilities(self):
        assert suggest_concept_for_text("Total Current Liabilities") == "current_liabilities"


class TestNoMatchAndAmbiguity:
    def test_unrelated_text_returns_none(self):
        assert suggest_concept_for_text("Employee Headcount") is None

    def test_empty_text_returns_none(self):
        assert suggest_concept_for_text("") is None
        assert suggest_concept_for_text(None) is None


class TestIsLikelyTotalRow:
    def test_total_row_detected(self):
        assert is_likely_total_row("Total Assets") is True

    def test_net_row_detected(self):
        assert is_likely_total_row("Net Income") is True

    def test_detail_row_not_total(self):
        assert is_likely_total_row("Cash") is False
        assert is_likely_total_row("Accounts Receivable") is False
