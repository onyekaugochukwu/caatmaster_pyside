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
        r"current.?asset", r"total.?current.?asset",
        r"receivable", r"debtor", r"trade.?receive"
    ],
    "current_liabilities": [
        r"current.?liabil", r"total.?current.?liabil",
        r"payable", r"creditor", r"trade.?payable",
        r"short.?term.?debt"
    ],
    "cash": [
        r"cash", r"bank", r"cash.?equival"
    ],
    "inventory": [
        r"invent", r"stock", r"goods"
    ],
    # Solvency
    "total_assets": [
        r"total.?asset", r"asset.?total"
    ],
    "total_liabilities": [
        r"total.?liabil", r"liabil.?total",
        r"non.?current.?liabil"
    ],
    "total_equity": [
        r"total.?equit", r"equit.?total",
        r"shareholder", r"stockholder",
        r"reserve", r"retained.?earn"
    ],
    "interest_expense": [
        r"interest.?expense", r"finance.?cost",
        r"interest.?cost"
    ],
    # Profitability
    "revenue": [
        r"revenue", r"sale", r"turnover",
        r"income.?from.?oper", r"operating.?income"
    ],
    "net_income": [
        r"net.?income", r"profit.?after.?tax",
        r"profit.?for.?year", r"earn"
    ],
    "gross_profit": [
        r"gross.?profit", r"gross.?margin"
    ],
    "cogs": [
        r"cost.?of.?good", r"cogs", r"cost.?of.?sale",
        r"direct.?cost", r"operational.?expense"
    ],
    "ebitda": [
        r"ebitda", r"earning.?before.?interest",
        r"operating.?profit.?before.?deprec"
    ],
    "ebit": [
        r"ebit", r"operating.?income",
        r"operating.?profit", r"earning.?before.?interest.?tax"
    ],
    "retained_earnings": [
        r"retained.?earn", r"accumulate.?profit"
    ],
    # Cash Flow
    "depreciation_amortization": [
        r"depreciat", r"amortiz"
    ],
}

# Rows whose text looks like a subtotal/aggregate line (vs. a detail
# account) - used to decide which account rows a reshape's concept
# mapping should default to pre-selecting, so a subtotal ("Total Assets")
# and its own detail rows ("Cash", "Inventory", ...) don't both end up
# mapped to the same concept and double-counted.
_TOTAL_ROW_PATTERN = re.compile(r"total|net\s|^net$", re.IGNORECASE)


def suggest_concept_for_text(text: str) -> Optional[str]:
    """Suggest which financial concept a piece of text - a column name or
    an account/line-item label - most likely represents. Returns None if
    nothing matches. This is a suggestion only; callers should always let
    the user confirm/override rather than treating it as authoritative."""
    if not text:
        return None
    text_lower = str(text).lower()
    for concept, patterns in CONCEPT_DETECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return concept
    return None


def is_likely_total_row(text: str) -> bool:
    """Whether an account/line-item label looks like a subtotal/aggregate
    row (e.g. "Total Assets", "Net Income") rather than a detail account
    (e.g. "Cash", "Accounts Receivable")."""
    return bool(text) and bool(_TOTAL_ROW_PATTERN.search(str(text)))
