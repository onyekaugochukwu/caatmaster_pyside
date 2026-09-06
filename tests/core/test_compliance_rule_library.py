"""
Tests for Compliance Rule Libraries - deterministic SOX/COSO/IFRS-adjacent
checks that skip the AI translation step entirely.
"""
import pytest
import polars as pl


class TestLibraryCatalog:
    def test_list_libraries(self):
        from core.compliance_rule_library import list_libraries

        libraries = list_libraries()
        ids = {lib["id"] for lib in libraries}
        assert "sox_itgc_ap" in ids
        assert "coso_expense_travel" in ids
        assert "period_end_je_risk" in ids
        for lib in libraries:
            assert lib["rule_count"] > 0

    def test_get_library_unknown_raises(self):
        from core.compliance_rule_library import get_library

        with pytest.raises(KeyError):
            get_library("does_not_exist")

    def test_get_field_specs_unions_all_rules(self):
        from core.compliance_rule_library import get_field_specs

        specs = get_field_specs("sox_itgc_ap")
        assert "amount" in specs["required_fields"]
        assert "approver" in specs["required_fields"]
        assert "vendor" in specs["required_fields"]
        assert "threshold" in specs["params"]


class TestSuggestMapping:
    def test_exact_and_substring_match(self):
        from core.compliance_rule_library import suggest_mapping

        mapping = suggest_mapping(
            df_columns=["Amount", "ApproverName", "Vendor"],
            required_fields={"amount": "", "approver": "", "vendor": ""},
            optional_fields={},
        )
        assert mapping["amount"] == "Amount"
        assert mapping["approver"] == "ApproverName"
        assert mapping["vendor"] == "Vendor"

    def test_no_match_omitted(self):
        from core.compliance_rule_library import suggest_mapping

        mapping = suggest_mapping(
            df_columns=["Amount"],
            required_fields={"amount": "", "approver": ""},
            optional_fields={},
        )
        assert "amount" in mapping
        assert "approver" not in mapping


class TestApplyLibrarySoxAP:
    @pytest.fixture
    def ap_dataframe(self):
        return pl.DataFrame({
            "Amount": [15000.0, 5000.0, 9500.0, 15000.0, 200.0],
            "Approver": [None, "Jane", None, "Bob", "Jane"],
            "Vendor": ["Acme", "Acme", "Globex", "Acme", "Initech"],
            "InvoiceRef": ["INV1", "INV2", "INV3", "INV1", "INV5"],
        })

    def test_payment_without_approval(self, ap_dataframe):
        from core.compliance_rule_library import apply_library

        mapping = {"amount": "Amount", "approver": "Approver", "vendor": "Vendor", "reference": "InvoiceRef"}
        results = apply_library(ap_dataframe, "sox_itgc_ap", mapping)
        by_id = {r["rule"]["id"]: r["result"] for r in results}

        approval = by_id["payment_without_approval"]
        assert approval["computable"] is True
        assert approval["affected_count"] == 1
        assert approval["evidence"] == ["INV1"]

    def test_duplicate_vendor_payment(self, ap_dataframe):
        from core.compliance_rule_library import apply_library

        mapping = {"amount": "Amount", "approver": "Approver", "vendor": "Vendor", "reference": "InvoiceRef"}
        results = apply_library(ap_dataframe, "sox_itgc_ap", mapping)
        by_id = {r["rule"]["id"]: r["result"] for r in results}

        dup = by_id["duplicate_vendor_payment"]
        assert dup["computable"] is True
        assert dup["affected_count"] == 2
        assert dup["affected_amount"] == pytest.approx(30000.0)

    def test_split_purchase_proxy_uses_derived_param(self, ap_dataframe):
        from core.compliance_rule_library import apply_library

        mapping = {"amount": "Amount", "approver": "Approver", "vendor": "Vendor", "reference": "InvoiceRef"}
        results = apply_library(ap_dataframe, "sox_itgc_ap", mapping, params={"threshold": 10000})
        by_id = {r["rule"]["id"]: r["result"] for r in results}

        split = by_id["split_purchase_proxy"]
        assert split["computable"] is True
        # 9500 is within [9000, 10000) at the default 10000 threshold
        assert split["affected_count"] == 1
        assert split["evidence"] == ["INV3"]

    def test_missing_required_field_marks_not_computable(self, ap_dataframe):
        from core.compliance_rule_library import apply_library

        # "approver" deliberately left unmapped
        mapping = {"amount": "Amount", "vendor": "Vendor", "reference": "InvoiceRef"}
        results = apply_library(ap_dataframe, "sox_itgc_ap", mapping)
        by_id = {r["rule"]["id"]: r["result"] for r in results}

        approval = by_id["payment_without_approval"]
        assert approval["computable"] is False
        assert "approver" in approval["reason"]

    def test_never_calls_ai(self, ap_dataframe, monkeypatch):
        """apply_library must be fully computable with no AI provider
        configured - ComplianceReportGenerator is instantiated with
        ai_manager=None and compute_rule_violation() never touches it."""
        from core.compliance_rule_library import apply_library

        mapping = {"amount": "Amount", "approver": "Approver", "vendor": "Vendor", "reference": "InvoiceRef"}
        # Should not raise despite no AI provider ever being configured.
        results = apply_library(ap_dataframe, "sox_itgc_ap", mapping)
        assert len(results) == 3


class TestApplyLibraryEmptyDataframe:
    def test_empty_dataframe_is_computable_with_zero_matches(self):
        from core.compliance_rule_library import apply_library

        df = pl.DataFrame({"Amount": pl.Series([], dtype=pl.Float64), "Approver": pl.Series([], dtype=pl.Utf8),
                            "Vendor": pl.Series([], dtype=pl.Utf8), "InvoiceRef": pl.Series([], dtype=pl.Utf8)})
        mapping = {"amount": "Amount", "approver": "Approver", "vendor": "Vendor", "reference": "InvoiceRef"}
        results = apply_library(df, "sox_itgc_ap", mapping)
        for r in results:
            assert r["result"]["affected_count"] == 0
