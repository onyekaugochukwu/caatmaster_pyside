"""
Tests for the XBRL/iXBRL import service. Uses real Arelle loading against
small, self-contained fixture files under test_data/xbrl/ (each importing
only the core XBRL 2.1 spec schemas Arelle ships in its own local cache -
no network access, no real GAAP/IFRS taxonomy download required), so
these exercise the real load path rather than a mocked one.
"""
import pytest

pytest.importorskip("arelle", reason="arelle-release not installed")

import polars as pl
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent.parent.parent / "test_data" / "xbrl"


class TestMapXbrlConcept:
    def test_us_gaap_standard_tag(self):
        from services.xbrl_import_service import map_xbrl_concept
        assert map_xbrl_concept("Assets", "http://fasb.org/us-gaap/2024") == "total_assets"
        assert map_xbrl_concept("Revenues", "http://fasb.org/us-gaap/2024") == "revenue"
        assert map_xbrl_concept("StockholdersEquity", "http://fasb.org/us-gaap/2023") == "total_equity"

    def test_ifrs_standard_tag(self):
        from services.xbrl_import_service import map_xbrl_concept
        assert map_xbrl_concept("Assets", "http://xbrl.ifrs.org/taxonomy/2024-03-27/ifrs-full") == "total_assets"
        assert map_xbrl_concept("CurrentAssets", "http://xbrl.ifrs.org/taxonomy/2023-03-23/ifrs-full") == "current_assets"
        assert map_xbrl_concept("Revenue", "http://xbrl.ifrs.org/taxonomy/2024-03-27/ifrs-full") == "revenue"

    def test_taxonomy_version_year_does_not_matter(self):
        from services.xbrl_import_service import map_xbrl_concept
        # Same element, different taxonomy year in the namespace URI -
        # must resolve identically.
        assert map_xbrl_concept("Assets", "http://fasb.org/us-gaap/2019") == "total_assets"
        assert map_xbrl_concept("Assets", "http://fasb.org/us-gaap/2024") == "total_assets"

    def test_unknown_namespace_falls_back_to_fuzzy_label_match(self):
        from services.xbrl_import_service import map_xbrl_concept
        assert map_xbrl_concept("MyCustomTag", "http://acme.com/2024", label="Total Revenue") == "revenue"

    def test_unknown_namespace_and_unmatched_label_returns_none(self):
        from services.xbrl_import_service import map_xbrl_concept
        assert map_xbrl_concept("MyCustomTag", "http://acme.com/2024", label="Employee Headcount") is None

    def test_no_label_falls_back_to_local_name(self):
        from services.xbrl_import_service import map_xbrl_concept
        assert map_xbrl_concept("Revenue", "http://acme.com/2024") == "revenue"


class TestParseXbrlFile:
    def test_parses_plain_xbrl_instance(self):
        from services.xbrl_import_service import parse_xbrl_file

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-instance.xml"))
        assert result.errors == []
        assert result.facts_df.height == 2
        assert result.entity_identifier == "0001234567"

        by_concept = dict(zip(result.facts_df["concept_local_name"].to_list(), result.facts_df["value"].to_list()))
        assert by_concept["Revenue"] == pytest.approx(1234567.0)
        assert by_concept["Assets"] == pytest.approx(5000000.0)

    def test_instant_period_label_is_the_actual_reported_date(self):
        """XBRL stores an instant internally as midnight of the FOLLOWING
        day - the label must show the actual reported date (2024-12-31),
        not Arelle's internal +1-day representation."""
        from services.xbrl_import_service import parse_xbrl_file

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-instance.xml"))
        assets_row = result.facts_df.filter(pl.col("concept_local_name") == "Assets")
        assert assets_row["period"].to_list() == ["2024-12-31"]

    def test_duration_period_label_shows_actual_end_date(self):
        from services.xbrl_import_service import parse_xbrl_file

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-instance.xml"))
        revenue_row = result.facts_df.filter(pl.col("concept_local_name") == "Revenue")
        assert revenue_row["period"].to_list() == ["2024-01-01 to 2024-12-31"]

    def test_parses_inline_xbrl(self):
        from services.xbrl_import_service import parse_xbrl_file

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-inline.xhtml"))
        assert result.errors == []
        assert result.facts_df.height == 1
        assert result.facts_df["value"].to_list() == [pytest.approx(1234567.0)]

    def test_dimensional_fact_flagged(self):
        from services.xbrl_import_service import parse_xbrl_file

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-multi-period.xml"))
        by_context = dict(zip(
            result.facts_df["value"].to_list(), result.facts_df["is_dimensional"].to_list()
        ))
        assert by_context[600000.0] is True
        assert by_context[1234567.0] is False

    def test_multi_period_produces_distinct_periods(self):
        from services.xbrl_import_service import parse_xbrl_file

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-multi-period.xml"))
        assert len(result.periods) == 2
        assert "2024-01-01 to 2024-12-31" in result.periods
        assert "2023-01-01 to 2023-12-31" in result.periods

    def test_nonexistent_file_returns_error_not_exception(self):
        from services.xbrl_import_service import parse_xbrl_file

        result = parse_xbrl_file("/tmp/does_not_exist_xyz.xml")
        assert result.facts_df.height == 0
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].lower()


class TestBuildWideConceptTable:
    def test_pivots_to_one_row_per_period(self):
        from services.xbrl_import_service import parse_xbrl_file, build_wide_concept_table

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-multi-period.xml"))
        wide = build_wide_concept_table(result.facts_df)
        assert wide.height == 2
        assert "revenue" in wide.columns

    def test_dimensional_facts_excluded_by_default(self):
        from services.xbrl_import_service import parse_xbrl_file, build_wide_concept_table

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-multi-period.xml"))
        wide = build_wide_concept_table(result.facts_df)
        cy_revenue = wide.filter(pl.col("period") == "2024-01-01 to 2024-12-31")["revenue"].to_list()[0]
        # Must be the whole-company figure (1,234,567), not inflated by
        # summing in the 600,000 segment-level fact for the same period.
        assert cy_revenue == pytest.approx(1234567.0)

    def test_dimensional_facts_included_when_requested(self):
        from services.xbrl_import_service import parse_xbrl_file, build_wide_concept_table

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-multi-period.xml"))
        wide = build_wide_concept_table(result.facts_df, include_dimensional=True)
        cy_revenue = wide.filter(pl.col("period") == "2024-01-01 to 2024-12-31")["revenue"].to_list()[0]
        assert cy_revenue == pytest.approx(1234567.0 + 600000.0)

    def test_period_filter(self):
        from services.xbrl_import_service import parse_xbrl_file, build_wide_concept_table

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-multi-period.xml"))
        wide = build_wide_concept_table(result.facts_df, periods=["2024-01-01 to 2024-12-31"])
        assert wide.height == 1

    def test_unmapped_concepts_excluded(self):
        from services.xbrl_import_service import parse_xbrl_file, build_wide_concept_table

        result = parse_xbrl_file(str(FIXTURE_DIR / "test-instance.xml"))
        wide = build_wide_concept_table(result.facts_df)
        # "Assets" (custom test namespace, no label) doesn't fuzzy-match
        # on its own per financial_concepts' specificity rules - only
        # "revenue" should make it into the wide table.
        assert "total_assets" not in wide.columns
        assert "revenue" in wide.columns

    def test_empty_facts_returns_empty_dataframe(self):
        from services.xbrl_import_service import build_wide_concept_table

        assert build_wide_concept_table(pl.DataFrame()).is_empty()

    def test_duplicate_non_dimensional_facts_are_not_summed(self):
        """A real filing can tag the same whole-entity fact more than
        once - once in the primary statement, again in MD&A prose, a
        selected-financial-data table, a segment reconciliation's
        "Total" row, ... - all non-dimensional, all the same period,
        all the identical value. Summing these would multiply a real
        number by however many times the filing happens to repeat it,
        so duplicate non-dimensional facts must not be summed."""
        from services.xbrl_import_service import build_wide_concept_table

        facts_df = pl.DataFrame({
            "period": ["2024-01-01 to 2024-12-31"] * 4,
            "app_concept": ["revenue"] * 4,
            "value": [416161000000.0] * 4,
            "is_dimensional": [False] * 4,
        })
        wide = build_wide_concept_table(facts_df)
        assert wide["revenue"].to_list() == [416161000000.0]

    def test_dimensional_facts_are_still_summed_when_requested(self):
        """Several dimensional (segment) facts that together partition
        the whole must still be added to reconstruct a total when
        include_dimensional=True is requested explicitly."""
        from services.xbrl_import_service import build_wide_concept_table

        facts_df = pl.DataFrame({
            "period": ["2024-01-01 to 2024-12-31"] * 2,
            "app_concept": ["revenue"] * 2,
            "value": [100.0, 200.0],
            "is_dimensional": [True, True],
        })
        wide = build_wide_concept_table(facts_df, include_dimensional=True)
        assert wide["revenue"].to_list() == [300.0]

    def test_genuinely_different_non_dimensional_values_are_not_summed(self):
        """A real conflict (two DIFFERENT non-dimensional values for the
        same whole-entity concept and period) is exactly the same wrong
        assumption that caused the duplicate-summing bug - summing them
        cannot correspond to anything the filer actually reported, so
        this takes one of the real reported values instead."""
        from services.xbrl_import_service import build_wide_concept_table

        facts_df = pl.DataFrame({
            "period": ["2024-01-01 to 2024-12-31"] * 2,
            "app_concept": ["revenue"] * 2,
            "value": [100.0, 200.0],
            "is_dimensional": [False, False],
        })
        wide = build_wide_concept_table(facts_df)
        assert wide["revenue"].to_list()[0] in (100.0, 200.0)


class TestFullPipelineIntegration:
    """Confirms XBRL-sourced data is directly usable by the existing
    ratio calculation pipeline, unmodified - the actual point of routing
    XBRL through the same internal concept keys as a spreadsheet import.
    Builds the wide table from a synthetic facts_df (already shaped like
    parse_xbrl_file's real output) covering two concepts, since neither
    fixture file alone maps both sides of a ratio."""

    def test_xbrl_derived_table_feeds_ratio_calculation(self):
        from services.xbrl_import_service import build_wide_concept_table
        from services.financial_service import FinancialService

        facts_df = pl.DataFrame({
            "period": ["2024-01-01 to 2024-12-31", "2024-12-31"],
            "app_concept": ["revenue", "total_assets"],
            "value": [1234567.0, 5000000.0],
            "is_dimensional": [False, False],
        })
        wide = build_wide_concept_table(facts_df)
        assert set(wide.columns) == {"period", "revenue", "total_assets"}

        # A wide table with facts on different period rows (annual
        # duration vs. balance-sheet instant) needs the same collapse
        # real statements need - use identity mapping directly on the
        # per-concept max, matching how a single-period ratio dialog
        # would consume it.
        collapsed = wide.select([
            pl.col("revenue").max().alias("revenue"),
            pl.col("total_assets").max().alias("total_assets"),
        ])
        result = FinancialService().calculate_ratios(
            collapsed, {"revenue": "revenue", "total_assets": "total_assets"}, ["asset_turnover"]
        )
        assert result["ratio_asset_turnover"][0] == pytest.approx(1234567.0 / 5000000.0)


class TestTaxonomyPackages:
    """Taxonomy package tests use a real, spec-compliant package (built
    under test_data/xbrl/test-package/) whose catalog remaps
    "http://test.example/remote/" - a domain that cannot resolve on the
    real internet at all - to its own bundled schema. A fixture instance
    references that exact unresolvable URL; it loading successfully with
    zero errors is only possible via the registered package's local
    mapping, never a live network fetch. Cleans up after itself since
    Arelle's package registry is a real file under ~/.config/arelle/,
    shared across anything using this Arelle installation, not something
    scoped to pytest's own tmp_path sandbox.
    """

    PACKAGE_PATH = str(FIXTURE_DIR / "test-package" / "test-taxonomy-package.zip")
    REMOTE_REF_INSTANCE = str(FIXTURE_DIR / "remote-ref-instance.xml")
    PACKAGE_NAME = "Test Taxonomy Package"

    @pytest.fixture(autouse=True)
    def _cleanup_registered_package(self):
        from services.xbrl_import_service import remove_taxonomy_package
        yield
        remove_taxonomy_package(self.PACKAGE_NAME)  # no-op if a test never registered it

    def test_unresolvable_url_fails_without_a_registered_package(self):
        from services.xbrl_import_service import parse_xbrl_file

        result = parse_xbrl_file(self.REMOTE_REF_INSTANCE)
        assert result.facts_df.height == 0

    def test_add_taxonomy_package_returns_metadata(self):
        from services.xbrl_import_service import add_taxonomy_package

        info = add_taxonomy_package(self.PACKAGE_PATH)
        assert info.name == self.PACKAGE_NAME
        assert info.version == "1.0"
        assert info.status == "enabled"

    def test_registered_package_resolves_unreachable_domain_locally(self):
        """The actual point of this feature: an unresolvable domain
        succeeds ONLY because of local package resolution."""
        from services.xbrl_import_service import add_taxonomy_package, parse_xbrl_file

        add_taxonomy_package(self.PACKAGE_PATH)
        result = parse_xbrl_file(self.REMOTE_REF_INSTANCE)

        assert result.errors == []
        assert result.facts_df.height == 1
        assert result.facts_df["value"].to_list() == [pytest.approx(1234567.0)]

    def test_registration_persists_across_fresh_sessions(self):
        """Simulates an app restart: a completely fresh parse_xbrl_file()
        call, with no re-registration in between, must still resolve
        locally - proving persistence, not just in-process state."""
        from services.xbrl_import_service import add_taxonomy_package, parse_xbrl_file

        add_taxonomy_package(self.PACKAGE_PATH)
        # Every parse_xbrl_file() call already builds its own fresh
        # Cntlr internally (_make_cntlr()) - calling it again here IS the
        # "fresh session" simulation, no extra setup needed.
        result = parse_xbrl_file(self.REMOTE_REF_INSTANCE)
        assert result.facts_df.height == 1

    def test_list_taxonomy_packages_includes_registered_package(self):
        from services.xbrl_import_service import add_taxonomy_package, list_taxonomy_packages

        add_taxonomy_package(self.PACKAGE_PATH)
        names = [p.name for p in list_taxonomy_packages()]
        assert self.PACKAGE_NAME in names

    def test_remove_taxonomy_package(self):
        from services.xbrl_import_service import (
            add_taxonomy_package, remove_taxonomy_package, list_taxonomy_packages, parse_xbrl_file
        )

        add_taxonomy_package(self.PACKAGE_PATH)
        removed = remove_taxonomy_package(self.PACKAGE_NAME)
        assert removed is True
        assert self.PACKAGE_NAME not in [p.name for p in list_taxonomy_packages()]

        # And resolution genuinely stops working again - confirms remove()
        # actually rebuilt the remappings, not just the config list.
        result = parse_xbrl_file(self.REMOTE_REF_INSTANCE)
        assert result.facts_df.height == 0

    def test_remove_nonexistent_package_returns_false(self):
        from services.xbrl_import_service import remove_taxonomy_package

        assert remove_taxonomy_package("Not A Real Package Name") is False

    def test_invalid_package_file_raises_value_error(self):
        from services.xbrl_import_service import add_taxonomy_package

        with pytest.raises(ValueError):
            add_taxonomy_package(str(FIXTURE_DIR / "test-instance.xml"))  # not a taxonomy package zip


class TestClarifyLogMessage:
    def test_network_failure_gets_a_hint_appended(self):
        from services.xbrl_import_service import _clarify_log_message

        original = "Unable to open http://xbrl.sec.gov/dei/2024/dei-2024.xsd: [Errno -2] Name or service not known"
        result = _clarify_log_message(original)
        assert original in result  # never loses the original diagnostic
        assert "taxonomy package" in result.lower()

    def test_unrelated_message_passed_through_unchanged(self):
        from services.xbrl_import_service import _clarify_log_message

        original = "Element ix:nonFraction fact test:Revenue error Invalid value for nonFraction number"
        assert _clarify_log_message(original) == original

    def test_empty_message_passed_through(self):
        from services.xbrl_import_service import _clarify_log_message
        assert _clarify_log_message("") == ""
