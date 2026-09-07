"""
XBRL / Inline XBRL (iXBRL) Import Dialog - parses a filing via
services.xbrl_import_service (Arelle-backed), lets the user review/
override the auto-mapped concept for each tagged element and choose
which periods to include, then hands back both the long (every tagged
fact - an audit trail down to the raw filing) and wide (one row per
period, one column per concept - ready for FinancialService's ratio/
Altman Z-score calculations, and for any other concept-keyed module in
the app, e.g. the IFRS 9/15/16 dialogs' column mapping) tables for
main_window.py to turn into project datasets, matching how
FinancialImportWizardDialog hands back accepted steps rather than
creating datasets itself.
"""
from typing import Dict, List, Optional

import polars as pl
from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QListWidget, QListWidgetItem, QCheckBox, QMessageBox, QProgressBar,
    QFileDialog, QTextEdit, QSplitter, QWidget
)

from gui.theme import Colors
from gui.components.common_modals import create_primary_button, create_secondary_button

# Concept keys a user might want to assign/override, matching
# core.financial_concepts.CONCEPT_DETECTION_PATTERNS - kept as an
# explicit list here (not imported) so the combo box order is stable and
# curated, rather than following dict iteration order.
_APP_CONCEPTS = [
    "revenue", "cogs", "gross_profit", "ebit", "ebitda", "net_income",
    "current_assets", "current_liabilities", "cash", "inventory",
    "total_assets", "total_liabilities", "total_equity", "retained_earnings",
    "interest_expense", "depreciation_amortization",
]


class XBRLImportDialog(QDialog):
    """Dialog for importing an XBRL instance document or inline XBRL
    (iXBRL) filing into the project."""

    _parseReady = Signal(object)  # XBRLParseResult
    _parseFailed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import XBRL / iXBRL Filing")
        self.setMinimumSize(900, 700)
        self.thread_pool = QThreadPool()
        self.parse_result = None
        self.concept_overrides: Dict[str, Optional[str]] = {}  # "local_name|taxonomy" -> concept
        self._setup_ui()

        self._parseReady.connect(self._on_parse_ready, Qt.QueuedConnection)
        self._parseFailed.connect(self._on_parse_failed, Qt.QueuedConnection)

    def closeEvent(self, event):
        self.thread_pool.waitForDone(3000)
        event.accept()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Import XBRL / iXBRL Filing")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)

        hint = QLabel(
            "Parses a plain XBRL instance document (.xbrl/.xml) or an inline XBRL filing "
            "(.htm/.xhtml, the standard SEC/ESEF format) and maps its tagged facts onto this "
            "app's standard financial concepts (revenue, total_assets, ...) - the same concepts a "
            "spreadsheet import maps to, so ratio calculations and other modules work identically "
            "regardless of source. Standard US-GAAP/IFRS tags are mapped exactly; anything else "
            "falls back to the same fuzzy label matching a spreadsheet column gets, and can always "
            "be corrected below before import."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(hint)

        file_row = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("Select an XBRL instance or inline XBRL (iXBRL) file...")
        self.file_path_edit.setReadOnly(True)
        file_row.addWidget(self.file_path_edit, 1)
        browse_btn = create_secondary_button("Browse...")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        self.parse_btn = create_primary_button("Parse File")
        self.parse_btn.setEnabled(False)
        self.parse_btn.clicked.connect(self._run_parse)
        file_row.addWidget(self.parse_btn)
        layout.addLayout(file_row)

        packages_row = QHBoxLayout()
        packages_row.addStretch()
        packages_btn = create_secondary_button("Manage Taxonomy Packages...")
        packages_btn.setToolTip(
            "Register a local taxonomy package so this filing's taxonomy resolves without "
            "internet access - needed if this machine has no network connection."
        )
        packages_btn.clicked.connect(self._open_package_manager)
        packages_row.addWidget(packages_btn)
        layout.addLayout(packages_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel()
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet(
            f"font-size: 12px; color: {Colors.TEXT_SECONDARY}; padding: 6px; "
            f"background-color: {Colors.BG_SECONDARY}; border-radius: 4px;"
        )
        layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Horizontal)

        concepts_group = QGroupBox("Tagged Elements - Review/Override Concept Mapping")
        concepts_layout = QVBoxLayout(concepts_group)
        self.concepts_table = QTableWidget()
        self.concepts_table.setColumnCount(4)
        self.concepts_table.setHorizontalHeaderLabels(["Element", "Taxonomy", "Facts", "Mapped Concept"])
        self.concepts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        concepts_layout.addWidget(self.concepts_table)
        splitter.addWidget(concepts_group)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        periods_group = QGroupBox("Periods to Include")
        periods_layout = QVBoxLayout(periods_group)
        self.periods_list = QListWidget()
        periods_layout.addWidget(self.periods_list)
        right_layout.addWidget(periods_group)

        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        self.include_dimensional_check = QCheckBox(
            "Include segment/dimensional facts (summed into the same concept)"
        )
        options_layout.addWidget(self.include_dimensional_check)
        right_layout.addWidget(options_group)

        info_group = QGroupBox("Filing Info")
        info_layout = QVBoxLayout(info_group)
        self.info_label = QLabel("Parse a file to see entity and period details.")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        right_layout.addWidget(info_group)

        warnings_group = QGroupBox("Warnings / Errors")
        warnings_layout = QVBoxLayout(warnings_group)
        self.warnings_text = QTextEdit()
        self.warnings_text.setReadOnly(True)
        self.warnings_text.setPlaceholderText("Any taxonomy resolution or validation issues will appear here.")
        warnings_layout.addWidget(self.warnings_text)
        right_layout.addWidget(warnings_group, 1)

        splitter.addWidget(right_panel)
        splitter.setSizes([550, 350])
        layout.addWidget(splitter, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self.import_btn = create_primary_button("Create Dataset(s)")
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._finalize_import)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

    def _open_package_manager(self):
        from gui.dialogs.taxonomy_package_dialog import TaxonomyPackageDialog
        TaxonomyPackageDialog(parent=self).exec()

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select XBRL / iXBRL File", "",
            "XBRL Files (*.xbrl *.xml *.htm *.html *.xhtml);;All Files (*)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
            self.parse_btn.setEnabled(True)

    def _run_parse(self):
        file_path = self.file_path_edit.text().strip()
        if not file_path:
            return

        self.parse_btn.setEnabled(False)
        self.import_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setVisible(True)
        self.status_label.setText(
            "Parsing filing... this can take a while the first time a taxonomy needs to be "
            "downloaded and cached."
        )

        def run():
            try:
                from services.xbrl_import_service import parse_xbrl_file
                result = parse_xbrl_file(file_path)
                self._parseReady.emit(result)
            except Exception as e:
                self._parseFailed.emit(str(e))

        self.thread_pool.start(run)

    def _on_parse_failed(self, error: str):
        self.parse_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.status_label.setText(f"Error: {error}")
        QMessageBox.critical(self, "Parse Error", error)

    def _on_parse_ready(self, result):
        self.parse_result = result
        self.parse_btn.setEnabled(True)
        self.progress.setVisible(False)

        if result.errors:
            self.status_label.setText(f"Parsed with {len(result.errors)} error(s) - see Warnings/Errors panel.")
        elif result.facts_df.height == 0:
            self.status_label.setText("No numeric facts found in this file.")
        else:
            self.status_label.setText(
                f"Parsed {result.facts_df.height} fact(s) across {len(result.periods)} period(s)."
            )

        self.info_label.setText(
            f"Entity identifier: {result.entity_identifier or '(multiple or none found)'}\n"
            f"Periods found: {len(result.periods)}\n"
            f"Total facts: {result.facts_df.height}"
        )

        messages = []
        if result.errors:
            messages.append("ERRORS:\n" + "\n".join(f"- {e}" for e in result.errors))
        if result.warnings:
            messages.append("WARNINGS:\n" + "\n".join(f"- {w}" for w in result.warnings))
        self.warnings_text.setPlainText("\n\n".join(messages) if messages else "None.")

        self.periods_list.clear()
        for period in result.periods:
            item = QListWidgetItem(period)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.periods_list.addItem(item)

        self._populate_concepts_table(result.facts_df)
        self.import_btn.setEnabled(result.facts_df.height > 0)

    def _populate_concepts_table(self, facts_df: pl.DataFrame):
        self.concept_overrides.clear()
        if facts_df.height == 0:
            self.concepts_table.setRowCount(0)
            return

        summary = (
            facts_df.group_by(["concept_local_name", "taxonomy", "app_concept"])
            .agg(pl.len().alias("fact_count"))
            .sort("concept_local_name")
        )

        self.concepts_table.setRowCount(summary.height)
        for row, record in enumerate(summary.to_dicts()):
            local_name = record["concept_local_name"]
            taxonomy = record["taxonomy"] or "(custom)"
            key = f"{local_name}|{record['taxonomy']}"

            self.concepts_table.setItem(row, 0, QTableWidgetItem(local_name))
            self.concepts_table.setItem(row, 1, QTableWidgetItem(taxonomy))
            self.concepts_table.setItem(row, 2, QTableWidgetItem(str(record["fact_count"])))

            combo = QComboBox()
            combo.addItem("— Not mapped —", None)
            for concept in _APP_CONCEPTS:
                combo.addItem(concept, concept)
            current = record["app_concept"]
            if current:
                idx = combo.findData(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            def on_change(index, k=key, c=combo):
                self.concept_overrides[k] = c.currentData()

            combo.currentIndexChanged.connect(on_change)
            self.concept_overrides[key] = current
            self.concepts_table.setCellWidget(row, 3, combo)

    def _selected_periods(self) -> List[str]:
        return [
            self.periods_list.item(i).text()
            for i in range(self.periods_list.count())
            if self.periods_list.item(i).checkState() == Qt.Checked
        ]

    def _apply_concept_overrides(self, facts_df: pl.DataFrame) -> pl.DataFrame:
        """Rebuild the app_concept column from whatever the user left in
        each row's combo box - a local_name/taxonomy pair with no row in
        the table (shouldn't happen) keeps its original mapping."""
        mapping_df = pl.DataFrame({
            "concept_local_name": [k.split("|", 1)[0] for k in self.concept_overrides],
            "taxonomy": [k.split("|", 1)[1] if k.split("|", 1)[1] != "None" else None
                         for k in self.concept_overrides],
            "app_concept_override": list(self.concept_overrides.values()),
        })
        return (
            facts_df.drop("app_concept")
            # nulls_equal=True: `taxonomy` is null for any custom/
            # unrecognized element (see _detect_taxonomy) - polars'
            # default join behavior never matches null-to-null, which
            # would silently drop every override made for a custom-
            # taxonomy element back to unmapped.
            .join(mapping_df, on=["concept_local_name", "taxonomy"], how="left", nulls_equal=True)
            .rename({"app_concept_override": "app_concept"})
        )

    def _finalize_import(self):
        if self.parse_result is None or self.parse_result.facts_df.height == 0:
            return
        periods = self._selected_periods()
        if not periods:
            QMessageBox.warning(self, "No Periods Selected", "Select at least one period to include.")
            return
        self.accept()

    def get_result(self) -> Dict:
        """Called by main_window.py after accept() - returns the long
        (all tagged facts, unfiltered by period/dimensional choice - a
        full audit trail) and wide (ratio-ready, honoring the period
        selection/dimensional/override choices made in this dialog)
        tables, plus filing metadata."""
        from services.xbrl_import_service import build_wide_concept_table

        facts_df = self._apply_concept_overrides(self.parse_result.facts_df)
        wide_df = build_wide_concept_table(
            facts_df,
            include_dimensional=self.include_dimensional_check.isChecked(),
            periods=self._selected_periods(),
        )
        return {
            "facts_df": facts_df,
            "wide_df": wide_df,
            "entity_identifier": self.parse_result.entity_identifier,
            "source_file": self.file_path_edit.text().strip(),
        }
