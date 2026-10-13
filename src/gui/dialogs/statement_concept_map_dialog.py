"""
Statement-to-Concept Reshape Dialog

Bridges a row-based financial statement (accounts as rows - "Cash",
"Accounts Receivable", "Total Assets", ...) to the wide, concept-as-
column format Financial Ratios needs (total_assets/revenue/... as
literal columns). This closes the gap between core.financial_import_wizard
(structural parsing that produces exactly this row-based shape) and
financial_service.py's ratio engine (which needs concept columns). A
plain transpose is not sufficient, since it turns each individual
account into its own column rather than rolling multiple accounts up
into the concept buckets the ratio engine needs.
"""
import asyncio
from typing import List, Optional
import polars as pl
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QComboBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QLabel, QMessageBox
)
from PySide6.QtCore import Qt, QThread, Signal

from ..components.common_modals import BaseModal, create_primary_button
from ..theme import Colors
from core.financial_concepts import (
    FINANCIAL_CONCEPTS, suggest_concept_for_text, is_likely_total_row,
)

# Flat list of (concept_key, display_label) across every statement
# grouping, for the per-account concept dropdown.
_ALL_CONCEPTS = [item for concepts in FINANCIAL_CONCEPTS.values() for item in concepts]
_IGNORE = "Ignore"


class _AccountConceptAIThread(QThread):
    """Runs FinancialImportAI.suggest_account_category_mapping() in the
    background - mirrors the self-contained AIManager-construction
    pattern used by FinancialRatiosDialog's own AI-assist thread, just
    reusing the existing, simpler suggest_account_category_mapping()
    helper instead of a bespoke prompt/JSON-parsing pair."""
    result_ready = Signal(dict)

    def __init__(self, account_names, concept_keys):
        super().__init__()
        self.account_names = account_names
        self.concept_keys = concept_keys

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            from services.ai_service import AIManager, load_stored_providers, FinancialImportAI
            manager = AIManager()
            load_stored_providers(manager)

            provider = manager.get_provider()
            if not provider:
                self.result_ready.emit({"error": "No AI provider configured. Please add a provider in AI Settings."})
                return
            if hasattr(provider, 'initialize'):
                if not provider.initialize():
                    self.result_ready.emit({"error": f"Failed to initialize provider: {provider.provider_name}"})
                    return

            ai = FinancialImportAI(manager)
            mappings = loop.run_until_complete(
                ai.suggest_account_category_mapping(self.account_names, self.concept_keys)
            )
            self.result_ready.emit({"mappings": mappings})
        except Exception as e:
            self.result_ready.emit({"error": str(e)})


class StatementConceptMapDialog(BaseModal):
    """Dialog for mapping a row-based statement's accounts to ratio
    concepts, then pivoting into the wide format Financial Ratios needs."""

    def __init__(self, dataframe: pl.DataFrame, parent=None, statement_types: Optional[List[str]] = None):
        self._concept_combos = {}
        self._ai_thread = None
        # Optionally scope the concept dropdown to only the statement
        # type(s) this call cares about (e.g. just "Balance Sheet") -
        # used when FinancialRatiosDialog opens this per-statement, so
        # the account-mapping table doesn't offer irrelevant Income
        # Statement concepts while mapping a Balance Sheet. Defaults to
        # every concept across every statement type (original behavior).
        if statement_types:
            self._concepts = [
                item for stmt in statement_types for item in FINANCIAL_CONCEPTS.get(stmt, [])
            ]
        else:
            self._concepts = _ALL_CONCEPTS
        super().__init__("Reshape Statement to Ratio Inputs", dataframe, parent)
        self.setMinimumSize(750, 650)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        intro = QLabel(
            "Map this statement's line items (rows) to the financial concepts Ratio "
            "Analysis needs. Only rows you map to a concept are included in the result - "
            "everything else is left out. Map more than one row to the same concept if "
            "your statement has no explicit subtotal line; they'll be summed."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(intro)

        # Statement layout pickers
        layout_group = QGroupBox("Statement Layout")
        layout_form = QFormLayout(layout_group)
        layout_form.setLabelAlignment(Qt.AlignRight)

        self.account_combo = QComboBox()
        self.account_combo.addItems(list(self.dataframe.columns))
        layout_form.addRow("Account/Line Item Column:", self.account_combo)

        # Value column(s) - checklist (NoSelection mode, checkbox-only
        # interaction) matching the app-wide checklist pattern, not a
        # selection-highlight-driven multi-select.
        self.value_list = QListWidget()
        self.value_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.value_list.setMaximumHeight(90)
        for col in self.dataframe.columns:
            item = QListWidgetItem(col)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.value_list.addItem(item)
        layout_form.addRow("Value Column(s):", self.value_list)
        value_hint = QLabel(
            "Check one column if the statement is already one-row-per-account-per-period "
            "(pick a Period column below too), or check multiple still-wide period columns "
            "(e.g. FY22, FY23) if periods are still separate columns."
        )
        value_hint.setWordWrap(True)
        value_hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        layout_form.addRow("", value_hint)

        self.period_combo = QComboBox()
        self.period_combo.addItem("(none - single period)")
        self.period_combo.addItems(list(self.dataframe.columns))
        layout_form.addRow("Period Column (optional):", self.period_combo)

        layout.addWidget(layout_group)

        # Account -> concept mapping table
        map_group = QGroupBox("Map Accounts to Ratio Concepts")
        map_layout = QVBoxLayout(map_group)

        btn_row = QHBoxLayout()
        self.build_table_btn = QPushButton("Load Unique Accounts")
        self.build_table_btn.setStyleSheet("min-width: 150px; padding: 4px 8px;")
        self.build_table_btn.setCursor(Qt.PointingHandCursor)
        self.build_table_btn.clicked.connect(self._build_account_table)
        btn_row.addWidget(self.build_table_btn)

        self.ai_btn = QPushButton("AI Suggest")
        self.ai_btn.setStyleSheet("min-width: 100px; padding: 4px 8px;")
        self.ai_btn.setCursor(Qt.PointingHandCursor)
        self.ai_btn.clicked.connect(self._on_ai_suggest)
        btn_row.addWidget(self.ai_btn)
        btn_row.addStretch()
        map_layout.addLayout(btn_row)

        self.account_table = QTableWidget(0, 2)
        self.account_table.setHorizontalHeaderLabels(["Account", "Concept"])
        self.account_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.account_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.account_table.verticalHeader().setVisible(False)
        map_layout.addWidget(self.account_table)

        layout.addWidget(map_group, 1)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        self.apply_btn = create_primary_button("Reshape Dataset")
        self.apply_btn.setStyleSheet("min-width: 150px; padding: 4px 8px;")
        self.apply_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.apply_btn)
        layout.addLayout(btn_layout)

    def _account_col(self) -> str:
        return self.account_combo.currentText()

    def _selected_value_cols(self):
        return [
            self.value_list.item(i).text()
            for i in range(self.value_list.count())
            if self.value_list.item(i).checkState() == Qt.Checked
        ]

    def _concept_options(self):
        return [_IGNORE] + [key for key, _label in self._concepts]

    def _build_account_table(self):
        """(Re)populate the table with one row per unique account value,
        pre-selecting a concept only for rows that look like a subtotal/
        aggregate line - detail rows default to Ignore. This is the
        safety default that stops a subtotal ("Total Assets") and its own
        detail rows ("Cash", "Inventory", ...) both ending up mapped to
        the same concept and double-counted; the user can still map
        several detail rows to one concept deliberately."""
        account_col = self._account_col()
        value_cols = self._selected_value_cols()
        if not account_col or not value_cols:
            QMessageBox.warning(self, "Missing Selection", "Pick an Account column and at least one Value column first.")
            return

        unique_accounts = [
            str(v) for v in self.dataframe[account_col].unique().drop_nulls().to_list()
        ]
        concept_options = self._concept_options()

        self.account_table.setRowCount(len(unique_accounts))
        self._concept_combos = {}
        for row, account in enumerate(unique_accounts):
            item = QTableWidgetItem(account)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.account_table.setItem(row, 0, item)

            combo = QComboBox()
            combo.addItems(concept_options)
            if is_likely_total_row(account):
                suggested = suggest_concept_for_text(account)
                if suggested and suggested in concept_options:
                    combo.setCurrentText(suggested)
            self.account_table.setCellWidget(row, 1, combo)
            self._concept_combos[account] = combo

    def _on_ai_suggest(self):
        if not self._concept_combos:
            QMessageBox.warning(self, "Load Accounts First", "Click 'Load Unique Accounts' before requesting AI suggestions.")
            return

        self.ai_btn.setEnabled(False)
        self.ai_btn.setText("AI Analyzing...")

        account_names = list(self._concept_combos.keys())
        concept_keys = [key for key, _label in self._concepts]

        self._ai_thread = _AccountConceptAIThread(account_names, concept_keys)
        self._ai_thread.result_ready.connect(self._on_ai_result)
        self._ai_thread.start()

    def _on_ai_result(self, result: dict):
        self.ai_btn.setEnabled(True)
        self.ai_btn.setText("AI Suggest")

        if "error" in result:
            QMessageBox.warning(self, "AI Error", f"AI suggestion failed:\n{result['error']}")
            return

        mappings = result.get("mappings", {})
        concept_options = self._concept_options()
        applied = 0
        for account, concept in mappings.items():
            combo = self._concept_combos.get(account)
            if combo and concept and concept in concept_options:
                combo.setCurrentText(concept)
                applied += 1

        if applied:
            QMessageBox.information(self, "AI Suggestions Applied", f"AI suggested a concept for {applied} account(s). Review before applying.")
        else:
            QMessageBox.warning(self, "No Suggestions", "AI could not confidently map any accounts. Please map manually.")

    def get_parameters(self) -> dict:
        account_concept_map = {
            account: combo.currentText()
            for account, combo in self._concept_combos.items()
            if combo.currentText() and combo.currentText() != _IGNORE
        }

        period_col = self.period_combo.currentText()
        if period_col == "(none - single period)":
            period_col = None

        return {
            "account_col": self._account_col(),
            "value_cols": self._selected_value_cols(),
            "period_col": period_col,
            "account_concept_map": account_concept_map,
        }

    def validate(self) -> bool:
        if not self._selected_value_cols():
            QMessageBox.warning(self, "No Value Column", "Select at least one Value column.")
            return False
        if not self._concept_combos:
            QMessageBox.warning(self, "No Mapping", "Click 'Load Unique Accounts' and map at least one account to a concept first.")
            return False
        if not any(combo.currentText() != _IGNORE for combo in self._concept_combos.values()):
            QMessageBox.warning(self, "No Mapping", "Map at least one account to a concept (not all left as 'Ignore').")
            return False
        return True
