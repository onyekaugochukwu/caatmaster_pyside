"""
Shared financial-concept definitions and detection heuristics.

Used by both the Financial Ratios dialog (mapping a COLUMN name to a
concept, e.g. "TotalAssetsUSD" -> total_assets) and the statement-to-
concept reshape operation (mapping an ACCOUNT/line-item's TEXT LABEL to a
concept, e.g. the string "Total Assets" -> total_assets). Consolidated
here (in core, not gui) so both the dialog and the data_processor
transformation can use the exact same patterns instead of two dialog-only
copies drifting apart.
"""
import re
from typing import Dict, List, Optional

# Financial statement groupings with required concepts - (concept_key, display_label)
FINANCIAL_CONCEPTS: Dict[str, List[tuple]] = {
    "Income Statement (P&L)": [
        ("revenue", "Revenue / Sales"),
        ("gross_profit", "Gross Profit"),
        ("cogs", "Cost of Goods Sold"),
        ("ebitda", "EBITDA"),
        ("ebit", "EBIT"),
        ("net_income", "Net Income"),
    ],
    "Balance Sheet": [
        ("current_assets", "Current Assets"),
        ("current_liabilities", "Current Liabilities"),
        ("cash", "Cash & Equivalents"),
        ("inventory", "Inventory"),
        ("total_assets", "Total Assets"),
        ("total_liabilities", "Total Liabilities"),
        ("total_equity", "Total Equity"),
        ("retained_earnings", "Retained Earnings"),
    ],
    "Cash Flow Statement": [
        ("interest_expense", "Interest Expense"),
        ("depreciation_amortization", "Depreciation & Amortization"),
    ]
}

# Consolidated superset of both regex-pattern dicts that used to live
# separately in financial_ratios_dialog.py's _auto_detect_for_statement()
# and _auto_detect_columns().
CONCEPT_DETECTION_PATTERNS: Dict[str, List[str]] = {
    # Liquidity
    "current_assets": [
        r"\bcurrent.?asset", r"\btotal.?current.?asset",
        r"\breceivable", r"\bdebtor", r"\btrade.?receive"
    ],
    "current_liabilities": [
        r"\bcurrent.?liabil", r"\btotal.?current.?liabil",
        r"\bpayable", r"\bcreditor", r"\btrade.?payable",
        r"\bshort.?term.?debt"
    ],
    "cash": [
        r"\bcash", r"\bbanks?\b", r"\bcash.?equival"
        # "bank" is a complete word given a trailing \b too (banks?\b),
        # unlike the leading-only \b every other pattern here uses -
        # without it, this matched inside "Bankruptcy", a real GAAP
        # label/tag context (LiabilitiesSubjectToCompromise filings,
        # going-concern disclosures) with nothing to do with cash.
    ],
    "inventory": [
        r"\binvent", r"\bstocks?\b", r"\bgoods"
        # Same reasoning as "bank" above: bare "stock" unanchored on the
        # right matched inside "StockholdersEquity", "TreasuryStockValue",
        # and "CommonStockValue" - every one of them an equity concept,
        # not inventory. "stock" itself is kept (not deleted) because it
        # is genuine, common terminology for inventory outside US usage
        # (IFRS/UK-style statements label the line item "Stock").
    ],
    # Solvency
    "total_assets": [
        r"\btotal.?asset", r"\basset.?total"
    ],
    "total_liabilities": [
        r"\btotal.?liabil", r"\bliabil.?total",
        r"\bnon.?current.?liabil"
    ],
    "total_equity": [
        r"\btotal.?equit", r"\bequit.?total",
        r"\bshareholder", r"\bstockholder"
        # Deliberately NOT "reserve" or "retained.?earn": "reserve" alone
        # also appears in non-equity contexts ("Inventory Reserve",
        # "Warranty Reserve" are contra-asset/liability accounts, not
        # equity), and "retained earnings" already has its own dedicated
        # concept below - having the same pattern under both meant
        # "Retained Earnings" always matched total_equity first (dict
        # iteration order), so the retained_earnings concept could never
        # actually be reached for the one line item it exists to detect.
    ],
    "interest_expense": [
        r"\binterest.?expense", r"\bfinance.?cost",
        r"\binterest.?cost"
    ],
    # Profitability
    "revenue": [
        r"\brevenues?\b", r"\bsales?\b", r"\bturnover\b"
        # Regression test, found against a real SEC filing (Apple's FY2025
        # 10-K, parsed through the real XBRL import path): bare, unanchored
        # "sale" and "revenue" (no \b) matched inside XBRL element LOCAL
        # NAMES built by concatenating unrelated GAAP terms -
        # "PaymentsToAcquireAvailableForSaleSecuritiesDebt" and
        # "ContractWithCustomerLiabilityRevenueRecognized" both matched
        # and got summed into "revenue" alongside the genuine
        # RevenueFromContractWithCustomerExcludingAssessedTax fact,
        # inflating Apple's real ~$416B reported annual revenue to a
        # nonsensical ~$1.75T. Every pattern in this file now leads with
        # \b for the same reason: this class of false positive is general
        # to matching short, common-English-word patterns against
        # compact, concatenated identifiers with no word separators, not
        # unique to "sale" or to this one filing.
        #
        # \b alone was not enough, though: XBRL concepts also carry a
        # human-readable LABEL (spaced, not concatenated), and two of the
        # three real false positives above are standalone, correctly-
        # spaced occurrences of the word "sale"/"revenue" that still mean
        # something else entirely - "Available-for-Sale" is a securities
        # classification, not a sales transaction, and "Contract with
        # Customer, Liability, Revenue Recognized" describes a deferred-
        # revenue BALANCE SHEET LIABILITY, not the period's recognized
        # top-line revenue. CONCEPT_EXCLUSION_PATTERNS below rules out
        # both phrasings explicitly, rather than trying to make the
        # positive pattern itself somehow smarter.
        #
        # Deliberately NOT "operating.?income" - that pattern already
        # belongs to "ebit" below (operating income/profit IS
        # essentially EBIT), and having it duplicated here meant
        # "Operating Income" always matched revenue first (dict
        # iteration order), silently feeding an EBIT-sized number into
        # every ratio that uses top-line revenue - gross margin, net
        # margin, asset turnover, all wrong at once.
    ],
    "net_income": [
        r"\bnet.?income", r"\bprofit.?after.?tax",
        r"\bprofit.?for.?(the.?)?year"
        # Deliberately NOT a bare "earn": it matches "Earnings Per
        # Share", "Retained Earnings", and any other line that merely
        # contains the substring "earn", none of which are Net Income.
    ],
    "gross_profit": [
        r"\bgross.?profit", r"\bgross.?margin"
    ],
    "cogs": [
        r"\bcost.?of.?good", r"\bcogs\b", r"\bcost.?of.?sale",
        r"\bdirect.?cost", r"\boperational.?expense"
    ],
    "ebitda": [
        r"\bebitda\b", r"\bearning.?before.?interest",
        r"\boperating.?profit.?before.?deprec"
    ],
    "ebit": [
        r"\bebit\b", r"\boperating.?income",
        r"\boperating.?profit", r"\bearning.?before.?interest.?tax"
    ],
    "retained_earnings": [
        r"\bretained.?earn", r"\baccumulat\w*.?profit"
    ],
    # Cash Flow
    "depreciation_amortization": [
        r"\bdepreciat", r"\bamortiz"
    ],
}

# Per-concept phrases that disqualify an otherwise-matching text from that
# concept entirely, checked before CONCEPT_DETECTION_PATTERNS' positive
# patterns in suggest_concept_for_text(). Exists for phrases that contain
# a real, correctly-spaced occurrence of a concept's keyword while meaning
# something else - a case \b word-boundary matching cannot distinguish,
# since the word genuinely is there as its own word.
CONCEPT_EXCLUSION_PATTERNS: Dict[str, List[str]] = {
    "revenue": [
        r"available.?for.?sale", r"held.?for.?sale",
        # "Available-for-Sale"/"Held-for-Sale" are securities/asset
        # classifications ("Payments to Acquire Debt Securities,
        # Available-for-Sale"), not a sales transaction - confirmed
        # against Apple's real FY2025 10-K, where this phrase was the
        # source of two of the four facts wrongly summed into "revenue".
        r"contract.*liabilit", r"liabilit.*revenue",
        # "Contract with Customer, Liability, Revenue Recognized" is a
        # deferred-revenue BALANCE SHEET LIABILITY figure, not the
        # period's recognized top-line revenue - also confirmed against
        # the same real filing.
        r"reclassification.?adjustment", r"other.?comprehensive.?income",
        # "Other Comprehensive Income (Loss), Reclassification Adjustment
        # from AOCI for Sale of Securities, Net of Tax" - an OCI
        # reclassification line, not a sale of goods/services. Also
        # found in the same real filing.
    ],
}


def _is_excluded(concept: str, text_lower: str) -> bool:
    return any(re.search(p, text_lower) for p in CONCEPT_EXCLUSION_PATTERNS.get(concept, []))


# Rows whose text looks like a subtotal/aggregate line (vs. a detail
# account) - used to decide which account rows a reshape's concept
# mapping should default to pre-selecting, so a subtotal ("Total Assets")
# and its own detail rows ("Cash", "Inventory", ...) don't both end up
# mapped to the same concept and double-counted.
_TOTAL_ROW_PATTERN = re.compile(r"total|net\s|^net$", re.IGNORECASE)


def suggest_concept_for_text(text: str) -> Optional[str]:
    """Suggest which financial concept a piece of text - a column name or
    an account/line-item label - most likely represents. Returns None if
    nothing matches, OR if two DIFFERENT concepts match equally
    specifically - picking one arbitrarily in a genuine tie is worse than
    admitting the ambiguity, since a silently wrong guess here feeds
    straight into every ratio built from it. This is a suggestion only in
    any case; callers should always let the user confirm/override rather
    than treating it as authoritative.

    Ranks by the length of the matching pattern as a specificity proxy -
    a longer, more qualified pattern ("total.?current.?asset") beats a
    shorter, more generic one ("total.?asset") for the same text, which
    is what correctly prefers current_assets over total_assets for a
    label like "Total Current Assets" without needing the two concepts'
    patterns to be manually ordered against each other.
    """
    if not text:
        return None
    text_lower = str(text).lower()

    best_len_by_concept: Dict[str, int] = {}
    for concept, patterns in CONCEPT_DETECTION_PATTERNS.items():
        if _is_excluded(concept, text_lower):
            continue
        for pattern in patterns:
            if re.search(pattern, text_lower):
                best_len_by_concept[concept] = max(best_len_by_concept.get(concept, 0), len(pattern))
                break

    if not best_len_by_concept:
        return None

    ranked = sorted(best_len_by_concept.items(), key=lambda item: item[1], reverse=True)
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None  # genuine tie between two different concepts - don't guess
    return ranked[0][0]


def is_likely_total_row(text: str) -> bool:
    """Whether an account/line-item label looks like a subtotal/aggregate
    row (e.g. "Total Assets", "Net Income") rather than a detail account
    (e.g. "Cash", "Accounts Receivable")."""
    return bool(text) and bool(_TOTAL_ROW_PATTERN.search(str(text)))
