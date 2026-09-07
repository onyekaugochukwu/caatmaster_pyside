"""
XBRL / Inline XBRL (iXBRL) Service for CAATmaster
Parses an XBRL instance document or an inline XBRL filing (a standard
.xhtml/.htm document with embedded ix: tags, as filed with the SEC or
under ESEF) via Arelle (https://arelle.org - a mature, actively
maintained open-source XBRL processor used by regulators), and maps the
tagged facts onto this app's existing internal concept keys (the same
"revenue"/"total_assets"/... keys core.financial_concepts and
FinancialService already use), so XBRL-sourced data flows through the
exact same ratio/reshape pipeline a CSV/Excel import does.

Why Arelle rather than a direct XML parse: real filings reference their
taxonomy's schema and linkbases (definition, calculation, presentation,
label), which a bare lxml parse of just the instance document cannot
resolve - Arelle handles schema/linkbase resolution, dimensional
(segment/member) contexts, unit/decimals semantics, and inline XBRL's
transform registry correctly, all of which a hand-rolled parser would
otherwise have to reimplement (and likely get subtly wrong for real
filings, which is exactly the "ratios are never correctly parsed"
complaint this whole effort is trying to eliminate, not reintroduce in a
new form).

Concept mapping here is a small, EXPLICIT dictionary of standard US-GAAP/
IFRS taxonomy element names, not fuzzy regex text-matching - a real
strength of XBRL over a spreadsheet label: "us-gaap:Assets" or
"ifrs-full:Assets" IS the standardized concept identifier, so there is no
"Total Assets" vs. "Total Current Assets" ambiguity to resolve the way
there is for freeform column/row labels. An unmapped (custom extension,
or not-yet-listed standard) tag falls back to fuzzy-matching its label/
local name via financial_concepts.suggest_concept_for_text() rather than
being silently dropped.

Local-first taxonomy resolution: a real filing's schemaRef points at its
taxonomy publisher's own URL (e.g. the SEC's or IFRS Foundation's own
servers). The FIRST time Arelle ever sees a given taxonomy version, it
has to fetch those schema/linkbase files over the network - on a machine
with no internet at that moment (an air-gapped client site, a laptop with
a downloaded filing and no connectivity), parsing fails outright. Arelle
does cache what it successfully resolves (permanently, under
~/.config/arelle/cache), so it's a one-time cost per taxonomy version,
not per file - but that's not good enough for a genuinely offline-capable
tool, since US-GAAP/IFRS publish a new taxonomy version every year.

The real fix is XBRL's own Taxonomy Packages mechanism: a pre-built zip
bundle of a taxonomy (published by the SEC, the IFRS Foundation, and
others for exactly this reason) that Arelle can register once via
add_taxonomy_package() below. Traced directly in Arelle's own source
(arelle/FileSource.py) to confirm this claim rather than assume it: every
schema/linkbase URL is passed through PackageManager.mappedUrl() BEFORE
the web-cache/network-fetch code path is ever reached - a registered
package's mapping is checked FIRST and, when it matches, the network is
never attempted at all. This was verified end-to-end with a real,
spec-compliant taxonomy package pointing at a non-resolvable test domain
(https://test.example, which cannot be reached at all) and confirmed to
resolve purely from the local package with zero network activity and
zero errors.

One Arelle quirk this module works around: Cntlr only auto-loads and
auto-saves the persisted package registry when constructed with
hasGui=True - which also tries to initialize a platform GUI clipboard/
toolkit (win32clipboard, gtk, ...), not something to trigger from a
background thread in a Qt app. _make_cntlr() below stays headless
(hasGui=False, the default) and instead force-reloads the persisted
registry directly, bypassing that gate without any GUI side effects.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import polars as pl

# =============================================================================
# Concept mapping - standard taxonomy element (local) names -> this app's
# internal concept keys (core.financial_concepts.CONCEPT_DETECTION_PATTERNS).
# Deliberately covers the stable, most-commonly-tagged element per concept
# across taxonomy years, not every historical variant that has ever existed.
# =============================================================================

US_GAAP_CONCEPT_MAP: Dict[str, str] = {
    "Revenues": "revenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "RevenueFromContractWithCustomerIncludingAssessedTax": "revenue",
    "SalesRevenueNet": "revenue",
    "CostOfGoodsAndServicesSold": "cogs",
    "CostOfRevenue": "cogs",
    "CostOfGoodsSold": "cogs",
    "GrossProfit": "gross_profit",
    "OperatingIncomeLoss": "ebit",
    "NetIncomeLoss": "net_income",
    "ProfitLoss": "net_income",
    "NetIncomeLossAvailableToCommonStockholdersBasic": "net_income",
    "Assets": "total_assets",
    "AssetsCurrent": "current_assets",
    "Liabilities": "total_liabilities",
    "LiabilitiesCurrent": "current_liabilities",
    "StockholdersEquity": "total_equity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "total_equity",
    "CashAndCashEquivalentsAtCarryingValue": "cash",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": "cash",
    "InventoryNet": "inventory",
    "RetainedEarningsAccumulatedDeficit": "retained_earnings",
    "InterestExpense": "interest_expense",
    "InterestExpenseDebt": "interest_expense",
    "DepreciationDepletionAndAmortization": "depreciation_amortization",
    "DepreciationAmortizationAndAccretionNet": "depreciation_amortization",
    "DepreciationAndAmortization": "depreciation_amortization",
}

IFRS_CONCEPT_MAP: Dict[str, str] = {
    "Revenue": "revenue",
    "RevenueFromContractsWithCustomers": "revenue",
    "CostOfSales": "cogs",
    "GrossProfit": "gross_profit",
    "ProfitLossFromOperatingActivities": "ebit",
    "ProfitLoss": "net_income",
    "ProfitLossAttributableToOwnersOfParent": "net_income",
    "Assets": "total_assets",
    "CurrentAssets": "current_assets",
    "Liabilities": "total_liabilities",
    "CurrentLiabilities": "current_liabilities",
    "Equity": "total_equity",
    "EquityAttributableToOwnersOfParent": "total_equity",
    "CashAndCashEquivalents": "cash",
    "Inventories": "inventory",
    "RetainedEarnings": "retained_earnings",
    "InterestExpense": "interest_expense",
    "InterestExpenseOnBorrowings": "interest_expense",
    "DepreciationAndAmortisationExpense": "depreciation_amortization",
}

# Substrings identifying a namespace as one of the two supported standard
# taxonomies - matched against the namespace URI rather than an exact
# string, since the year/version segment of the URI changes every release
# ("http://fasb.org/us-gaap/2024", ".../2023", ...) while the taxonomy
# identity itself doesn't.
_US_GAAP_NAMESPACE_HINTS = ("fasb.org/us-gaap",)
_IFRS_NAMESPACE_HINTS = ("xbrl.ifrs.org", "ifrs-full")


def _detect_taxonomy(namespace_uri: str) -> Optional[str]:
    if not namespace_uri:
        return None
    if any(hint in namespace_uri for hint in _US_GAAP_NAMESPACE_HINTS):
        return "us-gaap"
    if any(hint in namespace_uri for hint in _IFRS_NAMESPACE_HINTS):
        return "ifrs-full"
    return None


# Substrings that, alongside a URL, suggest an Arelle log line is a
# failed network fetch of a schema/linkbase (a raw socket/urllib
# exception string) rather than a content/validation problem with the
# filing itself.
_NETWORK_FAILURE_HINTS = (
    "unable to open", "urlopen", "getaddrinfo", "connection", "timed out",
    "network is unreachable", "failed to load", "http error",
    "name or service not known", "errno", "temporary failure in name resolution",
)


def _clarify_log_message(text: str) -> str:
    """Append a plain-English hint to an Arelle log line that looks like
    a failed network fetch of a taxonomy schema/linkbase - Arelle's own
    message for this is a raw exception string (a URL plus a socket/
    urllib error), not something a reviewer would necessarily recognize
    as "no internet and no local taxonomy package for this filing's
    taxonomy version." Only APPENDS a hint when it looks like a network
    failure - never rewrites or hides the original diagnostic text."""
    if not text:
        return text
    lower = text.lower()
    looks_like_network_failure = ("http://" in lower or "https://" in lower) and any(
        hint in lower for hint in _NETWORK_FAILURE_HINTS
    )
    if looks_like_network_failure:
        return (
            f"{text}\n"
            "    -> This looks like a failed attempt to fetch a taxonomy schema/linkbase over "
            "the network. If this machine has no internet access, register a local XBRL "
            "Taxonomy Package for this filing's taxonomy (Manage Taxonomy Packages)."
        )
    return text


def map_xbrl_concept(local_name: str, namespace_uri: str, label: Optional[str] = None) -> Optional[str]:
    """Map one XBRL element to this app's internal concept key.

    Tries the explicit US-GAAP/IFRS dictionary first (exact, since a
    standard tag name IS the concept identifier); falls back to fuzzy
    text matching the concept's human-readable label (or its local name,
    if no label is available) via the same suggest_concept_for_text()
    used for spreadsheet column/row labels - this is what lets a
    filer-defined custom/extension element still get picked up, at the
    same (lower) confidence level a spreadsheet label always has.
    """
    taxonomy = _detect_taxonomy(namespace_uri)
    if taxonomy == "us-gaap" and local_name in US_GAAP_CONCEPT_MAP:
        return US_GAAP_CONCEPT_MAP[local_name]
    if taxonomy == "ifrs-full" and local_name in IFRS_CONCEPT_MAP:
        return IFRS_CONCEPT_MAP[local_name]

    from core.financial_concepts import suggest_concept_for_text
    return suggest_concept_for_text(label or local_name)


def _make_cntlr():
    """Build a headless Arelle controller with the persisted taxonomy-
    package registry force-loaded, regardless of Cntlr's own hasGui gate
    (see this module's docstring for why hasGui=True isn't used here)."""
    from arelle import Cntlr
    cntlr = Cntlr.Cntlr(logFileName="logToBuffer")
    cntlr._packageManager.init(cntlr, loadPackagesConfig=True)
    cntlr._packageManager.rebuildRemappings(cntlr)
    return cntlr


@dataclass
class TaxonomyPackageInfo:
    """One registered local taxonomy package - see add_taxonomy_package()."""
    name: str
    version: Optional[str]
    publisher: Optional[str]
    url: str
    status: str


def list_taxonomy_packages() -> List[TaxonomyPackageInfo]:
    """List every taxonomy package currently registered for local-first
    resolution. Persisted across app runs in Arelle's own config file
    (~/.config/arelle/taxonomyPackages.json), independent of this app's
    own database/config locations - it's Arelle's registry, shared by any
    tool using this Arelle installation."""
    cntlr = _make_cntlr()
    return [
        TaxonomyPackageInfo(
            name=p.name or "(unnamed package)", version=p.version,
            publisher=p.publisher, url=p.url, status=p.status or "enabled",
        )
        for p in cntlr.packages.get_packages()
    ]


def add_taxonomy_package(package_path: str) -> TaxonomyPackageInfo:
    """Register a local XBRL Taxonomy Package (a .zip, per the Taxonomy
    Packages 1.0 spec - the format the SEC, the IFRS Foundation, and
    other taxonomy publishers distribute for exactly this purpose) so
    every future parse resolves that taxonomy's schema/linkbase
    references from this local file FIRST, before any network attempt -
    see this module's docstring for how that was verified directly
    against Arelle's source and confirmed with a real test package.

    Raises ValueError if the file isn't a valid taxonomy package (e.g. a
    plain schema zip with no META-INF/taxonomyPackage.xml manifest).
    """
    cntlr = _make_cntlr()
    result = cntlr.packages.add(package_path)
    if result is None:
        raise ValueError(
            f"'{Path(package_path).name}' does not look like a valid XBRL taxonomy package "
            "(expected a .zip containing META-INF/taxonomyPackage.xml)."
        )
    # Order matters: add() alone doesn't rebuild the effective URL
    # remappings, and rebuild() alone doesn't mark the config dirty for
    # saving - only add()/remove() do. add -> rebuild -> save is the only
    # ordering that both takes effect immediately AND persists.
    cntlr.packages.rebuild()
    cntlr._packageManager.save(cntlr)
    return TaxonomyPackageInfo(
        name=result.name or Path(package_path).stem, version=result.version,
        publisher=result.publisher, url=package_path, status=result.status or "enabled",
    )


def remove_taxonomy_package(name: str) -> bool:
    """Unregister a previously-added taxonomy package by name. Returns
    False if no package with that name was registered."""
    cntlr = _make_cntlr()
    removed = cntlr._packageManager.removePackageModule(cntlr, name)
    if removed:
        cntlr.packages.rebuild()
        cntlr._packageManager.save(cntlr)
    return removed


@dataclass
class XBRLParseResult:
    facts_df: pl.DataFrame
    periods: List[str] = field(default_factory=list)
    entity_identifier: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def _period_label(context) -> str:
    """A human-readable, sortable period label. XBRL represents an
    instant/endDate as midnight of the FOLLOWING day (the exclusive upper
    bound of the period) - e.g. "as of 2024-12-31" is stored internally
    as 2025-01-01T00:00:00 - so every date used for display/labeling here
    subtracts one day back to the actual reported date."""
    if context.isInstantPeriod:
        d = context.instantDatetime.date() - timedelta(days=1)
        return d.isoformat()
    start = context.startDatetime.date()
    end = context.endDatetime.date() - timedelta(days=1)
    return f"{start.isoformat()} to {end.isoformat()}"


def parse_xbrl_file(file_path: str) -> XBRLParseResult:
    """
    Load an XBRL instance document or an inline XBRL (iXBRL) filing and
    extract every numeric fact into a long-format table: one row per
    (period, concept) fact, mapped to this app's internal concept keys
    where possible.

    Arelle auto-detects instance vs. inline XBRL from the file's own
    content, so both formats go through the same load call.

    Args:
        file_path: Path to a .xbrl/.xml instance document, or a
            .htm/.xhtml inline XBRL filing.

    Returns:
        XBRLParseResult. facts_df columns:
            period, period_type ("instant"/"duration"), concept_local_name,
            taxonomy ("us-gaap"/"ifrs-full"/None), app_concept (mapped
            internal concept key, or null if unmapped), value (float),
            unit, decimals, is_dimensional (bool - true for a segment/
            member-qualified fact, excluded from ratio-ready totals by
            default), entity_identifier.
        Never raises for a taxonomy resolution problem or a malformed
        fact - those are collected into `errors`/`warnings` instead, so a
        partially-taggable filing still returns whatever facts DID load
        cleanly rather than failing the entire import over one bad tag.
    """
    from core.numeric_parsing import clean_numeric_series

    path = Path(file_path)
    if not path.exists():
        return XBRLParseResult(facts_df=pl.DataFrame(), errors=[f"File not found: {file_path}"])

    cntlr = _make_cntlr()
    try:
        model_xbrl = cntlr.modelManager.load(str(path))
    except Exception as e:
        return XBRLParseResult(facts_df=pl.DataFrame(), errors=[f"Failed to load {path.name}: {e}"])

    warnings: List[str] = []
    errors: List[str] = []
    try:
        import json
        log = json.loads(cntlr.logHandler.getJson())
        for entry in log.get("log", []):
            text = (entry.get("message") or {}).get("text", "") or entry.get("code", "")
            level = (entry.get("level") or "").lower()
            (errors if level in ("error", "critical") else warnings).append(_clarify_log_message(text))
    except Exception:
        pass  # log parsing is best-effort - never block on it

    if model_xbrl is None:
        errors.append(f"Arelle could not load {path.name} as XBRL or inline XBRL.")
        return XBRLParseResult(facts_df=pl.DataFrame(), warnings=warnings, errors=errors)

    rows: List[Dict[str, Any]] = []
    entity_identifiers = set()

    for xbrl_fact in model_xbrl.facts:
        if xbrl_fact.concept is None or not xbrl_fact.concept.isNumeric:
            continue  # text blocks, entity metadata, etc. - not ratio inputs
        if xbrl_fact.isNil or xbrl_fact.context is None:
            continue

        context = xbrl_fact.context
        entity_id = context.entityIdentifier[1] if context.entityIdentifier else None
        if entity_id:
            entity_identifiers.add(entity_id)

        raw_value = xbrl_fact.value
        parsed = clean_numeric_series(pl.Series([raw_value], dtype=pl.Utf8))[0]

        namespace_uri = xbrl_fact.qname.namespaceURI
        local_name = xbrl_fact.qname.localName
        taxonomy = _detect_taxonomy(namespace_uri)
        try:
            label = xbrl_fact.concept.label(preferredLabel=None, fallbackToQname=False)
        except Exception:
            label = None
        app_concept = map_xbrl_concept(local_name, namespace_uri, label)

        unit_measures = None
        if xbrl_fact.unit is not None and xbrl_fact.unit.measures:
            numerators = xbrl_fact.unit.measures[0]
            if numerators:
                unit_measures = str(numerators[0])

        rows.append({
            "period": _period_label(context),
            "period_type": "instant" if context.isInstantPeriod else "duration",
            "concept_local_name": local_name,
            "taxonomy": taxonomy,
            "app_concept": app_concept,
            "value": parsed,
            "unit": unit_measures,
            "decimals": xbrl_fact.decimals,
            "is_dimensional": bool(context.qnameDims),
            "entity_identifier": entity_id,
        })

    facts_df = pl.DataFrame(rows) if rows else pl.DataFrame(schema={
        "period": pl.Utf8, "period_type": pl.Utf8, "concept_local_name": pl.Utf8,
        "taxonomy": pl.Utf8, "app_concept": pl.Utf8, "value": pl.Float64,
        "unit": pl.Utf8, "decimals": pl.Utf8, "is_dimensional": pl.Boolean,
        "entity_identifier": pl.Utf8,
    })

    periods = sorted(facts_df["period"].unique().to_list()) if facts_df.height else []
    entity_identifier = next(iter(entity_identifiers)) if len(entity_identifiers) == 1 else None
    if len(entity_identifiers) > 1:
        warnings.append(
            f"Multiple entity identifiers found in this filing ({', '.join(sorted(entity_identifiers))}) "
            "- facts from more than one reporting entity may be present."
        )

    return XBRLParseResult(
        facts_df=facts_df, periods=periods, entity_identifier=entity_identifier,
        warnings=warnings, errors=errors,
    )


def build_wide_concept_table(
    facts_df: pl.DataFrame,
    include_dimensional: bool = False,
    periods: Optional[List[str]] = None,
) -> pl.DataFrame:
    """
    Pivot the long facts table into the wide, one-row-per-period table
    the rest of the app's financial pipeline expects (one column per
    concept key: revenue, total_assets, ...) - the same shape
    DataProcessor.reshape_statement_to_concepts() produces from a
    spreadsheet import, so FinancialService.calculate_ratios()/
    calculate_altman_z_score() work identically regardless of source.

    Only facts with a resolved app_concept are included (an unmapped
    custom-extension tag has nothing to pivot into); by default only
    non-dimensional (whole-entity) facts are included too, so a segment-
    level "Revenue" fact doesn't get summed together with consolidated
    Revenue for the same period - multiple facts mapped to the same
    concept in the same period ARE summed (mirrors
    reshape_statement_to_concepts' behavior for several detail rows
    rolling up to one concept), which is correct for dimensional facts
    that together partition the whole (e.g. segment revenues), but set
    include_dimensional=True deliberately, not by default.
    """
    if facts_df.height == 0 or "app_concept" not in facts_df.columns:
        return pl.DataFrame()

    working = facts_df.filter(pl.col("app_concept").is_not_null())
    aggregate_function = "sum"
    if not include_dimensional:
        working = working.filter(~pl.col("is_dimensional"))
        # A real filing routinely tags the exact same whole-entity fact
        # more than once - once in the primary statement, again in MD&A
        # prose, a selected-financial-data table, a segment
        # reconciliation's own "Total" row, ... - all non-dimensional,
        # all the same period, all the same value. These are duplicate
        # REPORTS of one real number, not separate additive quantities,
        # and summing them (this function's behavior before this fix)
        # multiplies a real figure by however many times the filing
        # happens to repeat it. Confirmed against a real filing (Apple's
        # FY2025 10-K, fetched from SEC EDGAR): revenue was tagged 4
        # times for the same period at the identical value and summing
        # inflated the real ~$416B to ~$1.66T; net income was tagged 4
        # times the same way, cost of goods twice. Dropping exact
        # (period, concept, value) duplicates first removes the multiple
        # reports of the same number without needing to know in advance
        # how many times any given filing happens to repeat a fact.
        working = working.unique(subset=["period", "app_concept", "value"])
        # If a genuine conflict remains after that (two DIFFERENT values
        # for the same whole-entity concept and period - a restatement,
        # or two distinct line items that both happened to map to the
        # same concept), summing them is the same wrong assumption that
        # caused the bug above: two different whole-entity totals for one
        # period are not additive. Taking the first is not perfect, but a
        # real reported number is always safer here than a manufactured
        # sum that cannot correspond to anything the filer actually
        # reported.
        aggregate_function = "first"
    if periods:
        working = working.filter(pl.col("period").is_in(periods))
    if working.height == 0:
        return pl.DataFrame()

    return working.pivot(
        index="period", on="app_concept", values="value", aggregate_function=aggregate_function
    ).sort("period")
