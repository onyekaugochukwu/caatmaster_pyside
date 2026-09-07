"""
PDF text extraction, tested against a real filing.

Exercises the actual pypdf extraction step against a real, messy,
professionally-typeset PDF of the kind an auditor would genuinely
attach, rather than synthetic or hand-typed narrative text, so that a
change to pypdf's API, the page-cap/length-cap logic, or a PDF whose
layout defeats extraction entirely is caught.

The fixture (test_data/pdf/sec_edgar_rpm_ars_2026.pdf) is RPM
International Inc.'s FY2026 Annual Report to Security Holders (SEC EDGAR
form ARS), downloaded directly from
https://www.sec.gov/Archives/edgar/data/110621/000119312526365282/d79676dars.pdf
- a real, public, multi-column financial document with a mix of narrative
text and a tabular income statement, not a document built to be
extraction-friendly.
"""
from pathlib import Path

import pytest

PDF_FIXTURE = Path(__file__).parent.parent.parent / "test_data" / "pdf" / "sec_edgar_rpm_ars_2026.pdf"


@pytest.fixture(scope="module")
def extracted_text():
    from gui.dialogs.numeric_disclosure_dialog import _read_pdf_text
    return _read_pdf_text(str(PDF_FIXTURE))


class TestRealFilingExtraction:
    def test_extracts_a_substantial_amount_of_text(self, extracted_text):
        """A 24-page filing should yield well beyond a trivial amount of
        text; a near-empty result would mean extraction silently failed
        rather than raised."""
        assert len(extracted_text) > 20000

    def test_extracts_recognizable_narrative_content(self, extracted_text):
        assert "RPM" in extracted_text
        assert "Annual Report" in extracted_text

    def test_extracts_real_numeric_disclosures(self, extracted_text):
        """The filing's income statement is a real table, not narrative
        prose - confirms extraction survives tabular layout, not just
        running text, since this is the same shape of content
        NumericDisclosureDialog is built to reconcile against."""
        assert "Net Sales" in extracted_text
        assert "Net Income" in extracted_text

    def test_respects_the_documented_length_cap(self, extracted_text):
        assert len(extracted_text) <= 100000
