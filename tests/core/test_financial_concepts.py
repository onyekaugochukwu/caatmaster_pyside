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


class TestCompactIdentifiersDoNotMatchInsideAnotherWord:
    """Regression tests, found against a real filing (Apple's FY2025
    10-K, parsed through the actual XBRL import path from SEC EDGAR):
    every pattern here used to be unanchored, so a short common-English-
    word pattern like "sale" matched anywhere it appeared as a substring
    - including inside an unrelated XBRL element name/label built by
    concatenating several GAAP terms with no separator. This summed four
    unrelated facts into "revenue" and inflated a real company's actual
    ~$416B reported annual revenue to a nonsensical ~$1.75T."""

    def test_available_for_sale_is_not_revenue(self):
        assert suggest_concept_for_text(
            "Payments to Acquire Debt Securities, Available-for-Sale"
        ) is None
        assert suggest_concept_for_text(
            "PaymentsToAcquireAvailableForSaleSecuritiesDebt"
        ) is None

    def test_held_for_sale_is_not_revenue(self):
        assert suggest_concept_for_text("Assets Held-for-Sale") is None

    def test_contract_liability_revenue_recognized_is_not_revenue(self):
        # A deferred-revenue BALANCE SHEET LIABILITY, not the period's
        # recognized top-line revenue.
        assert suggest_concept_for_text(
            "Contract with Customer, Liability, Revenue Recognized"
        ) is None

    def test_oci_reclassification_for_sale_of_securities_is_not_revenue(self):
        assert suggest_concept_for_text(
            "Other Comprehensive Income (Loss), Reclassification Adjustment "
            "from AOCI for Sale of Securities, Net of Tax"
        ) is None

    def test_genuine_revenue_labels_still_match(self):
        assert suggest_concept_for_text("Revenue") == "revenue"
        assert suggest_concept_for_text("Net Sales") == "revenue"
        assert suggest_concept_for_text("Total Revenues") == "revenue"
        assert suggest_concept_for_text("Turnover") == "revenue"

    def test_stockholders_equity_is_not_inventory(self):
        # Bare "stock" (kept because "Stock" alone is genuine IFRS/UK
        # terminology for inventory) must not match inside "Stockholders"
        # or "TreasuryStock" - both equity, not inventory.
        assert suggest_concept_for_text("StockholdersEquity") != "inventory"
        assert suggest_concept_for_text("TreasuryStockValue") != "inventory"
        assert suggest_concept_for_text("Stock") == "inventory"

    def test_bankruptcy_is_not_cash(self):
        assert suggest_concept_for_text("LiabilitiesSubjectToCompromiseBankruptcy") != "cash"
        assert suggest_concept_for_text("Cash and Cash Equivalents") == "cash"


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
