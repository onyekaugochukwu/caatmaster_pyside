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

# Shared regex patterns for detecting a financial concept from a column
# name or account label.
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
        # "bank" is anchored on both sides (banks?\b) to avoid matching
        # inside "Bankruptcy" and similar unrelated GAAP terms.
    ],
    "inventory": [
        r"\binvent", r"\bstocks?\b", r"\bgoods"
        # "stock" is anchored on both sides to avoid matching inside
        # "StockholdersEquity", "TreasuryStockValue", or "CommonStockValue",
        # which are equity concepts. The bare word "Stock" is retained
        # since it is standard IFRS/UK terminology for inventory.
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
        # Every pattern in this file is word-boundary anchored (\b) to
        # avoid matching inside compact, concatenated XBRL element names
        # with no word separators (e.g. "sale" inside
        # "PaymentsToAcquireAvailableForSaleSecuritiesDebt").
        #
        # Word-boundary anchoring alone is not sufficient for XBRL
        # concepts with human-readable labels, since a label can contain
        # a standalone, correctly-spaced occurrence of "sale"/"revenue"
        # that still means something else - "Available-for-Sale" is a
        # securities classification, not a sales transaction, and
        # "Contract with Customer, Liability, Revenue Recognized"
        # describes a deferred-revenue balance sheet liability, not
        # recognized top-line revenue. CONCEPT_EXCLUSION_PATTERNS below
        # rules out both phrasings explicitly.
        #
        # Deliberately excludes "operating.?income": that pattern belongs
        # to "ebit" below, since operating income/profit is functionally
        # EBIT, and duplicating it here would let "Operating Income"
        # match revenue first by dict iteration order.
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
        # classifications, not a sales transaction.
        r"contract.*liabilit", r"liabilit.*revenue",
        # "Contract with Customer, Liability, Revenue Recognized" is a
        # deferred-revenue balance sheet liability, not recognized
        # top-line revenue.
        r"reclassification.?adjustment", r"other.?comprehensive.?income",
        # Other Comprehensive Income reclassification lines are not
        # revenue from goods or services.
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
