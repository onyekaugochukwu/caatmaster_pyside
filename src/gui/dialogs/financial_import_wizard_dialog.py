"""Financial Data Import Wizard dialog - reviews a deterministic import
plan (core.financial_import_wizard) for GL/JE detail, trial balances,
financial statements, and charts of accounts. Same contract as the
generic Cleaning Wizard dialog: every proposed step maps to a real,
existing operation, nothing is applied until Apply is clicked, and every
AI-assisted suggestion is shown for review/edit before it becomes a step
- never applied silently. Works fully with no AI provider configured;
the AI-assist buttons simply don't appear in that case.
"""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QGroupBox, QScrollArea, QWidget, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QRadioButton, QButtonGroup,
    QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt, QThread, Signal

from core.cleaning_wizard import CleaningStep
from core.financial_import_wizard import DOCUMENT_TYPES, build_financial_import_plan
from gui.theme import Colors
from gui.components.common_modals import create_primary_button
from core.data_processor import DataProcessor
from core.operation_registry import OPERATION_REGISTRY


class _AIWorker(QThread):
    """Runs an async AI call on a background thread and hands the result
    back via a Qt signal. A bare QThreadPool callback would invoke the
    result callback directly on the worker thread - and that callback
    builds/shows a QDialog to review the suggestion, which Qt widgets
    cannot do off the main thread (surfaces as QObject::setParent /
    QBasicTimer::start "different thread" errors, and the dialog never
    actually appearing)."""
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, coro_factory):
        super().__init__()
        self.coro_factory = coro_factory

    def run(self):
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self.coro_factory())
            self.result_ready.emit(result)
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            loop.close()


class _MappingReviewDialog(QDialog):
    """Small popup for reviewing/editing an AI-suggested value mapping
    before it's folded into the plan as a real step. Used for both
    column-identification and account-category suggestions."""

    def __init__(self, title: str, intro: str, mapping: dict, value_options: list = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 500)
        self.mapping = dict(mapping)
        self.value_options = value_options
        self._edits = {}

        layout = QVBoxLayout(self)
        intro_label = QLabel(intro)
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        self.table = QTableWidget(len(mapping), 2)
        self.table.setHorizontalHeaderLabels(["Item", "Suggested Mapping (edit if wrong)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row, (key, value) in enumerate(mapping.items()):
            key_item = QTableWidgetItem(str(key))
            key_item.setFlags(key_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, key_item)
            edit = QLineEdit(str(value) if value is not None else "")
            self.table.setCellWidget(row, 1, edit)
            self._edits[key] = edit
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        accept_btn = QPushButton("Use This Mapping")
        accept_btn.clicked.connect(self.accept)
        btn_row.addWidget(accept_btn)
        layout.addLayout(btn_row)

    def get_mapping(self) -> dict:
        return {key: edit.text().strip() or None for key, edit in self._edits.items()}


class FinancialImportWizardDialog(QDialog):
    def __init__(self, raw_df: pl.DataFrame, ai_manager=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Financial Data Import Wizard")
        self.resize(1050, 750)

        self.raw_df = raw_df
        self.ai_manager = ai_manager
        self.doc_type = None
        self.plan = None
        self.step_checkboxes = []
        self.data_processor = DataProcessor()
        self._working_df = None  # cache for _get_working_df()

        self.layout = QVBoxLayout(self)
        self._build_doc_type_screen()

    # ---------------------------------------------------------------- Screen 1

    def _build_doc_type_screen(self):
        self.doc_type_widget = QWidget()
        layout = QVBoxLayout(self.doc_type_widget)

        intro = QLabel(
            "What kind of financial document is this? Knowing the type lets each detector be aggressive "
            "and confident instead of guessing - other audit tools don't attempt this "
            "kind of structural cleanup with zero context about what the file represents."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; padding: 6px;")
        layout.addWidget(intro)

        doc_group = QGroupBox("Document Type")
        doc_layout = QVBoxLayout(doc_group)
        self.doc_type_group = QButtonGroup()
        self.doc_type_radios = {}
        descriptions = {
            "gl_je": "General ledger / journal entry line detail - one row per JE line, "
                    "possibly with header fields (entry #, date, preparer) sparse per entry "
                    "and separate Debit/Credit columns.",
            "trial_balance": "Account balances, usually with an account hierarchy and "
                             "Debit/Credit or Beginning/Ending Balance columns.",
            "financial_statement": "Income statement, balance sheet, or cash flow statement - "
                                   "line-item hierarchy, often wide with one column per period.",
            "chart_of_accounts": "The account list itself - parent/child rollup hierarchy, "
                                 "usually no transactional amounts.",
        }
        for i, (doc_type, display_name) in enumerate(DOCUMENT_TYPES.items()):
            radio = QRadioButton(display_name)
            radio.setToolTip(descriptions[doc_type])
            if i == 0:
                radio.setChecked(True)
            self.doc_type_group.addButton(radio)
            self.doc_type_radios[doc_type] = radio
            doc_layout.addWidget(radio)
            desc_label = QLabel(descriptions[doc_type])
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; margin-left: 24px; font-size: 11px;")
            doc_layout.addWidget(desc_label)
        layout.addWidget(doc_group)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        detect_btn = create_primary_button("Detect Structure →")
        detect_btn.clicked.connect(self._on_detect_structure)
        btn_row.addWidget(detect_btn)
        layout.addLayout(btn_row)

        self.layout.addWidget(self.doc_type_widget)

    def _on_detect_structure(self):
        self.doc_type = next(dt for dt, radio in self.doc_type_radios.items() if radio.isChecked())
        self.plan = build_financial_import_plan(self.raw_df, self.doc_type)
        self.doc_type_widget.setVisible(False)
        self.layout.removeWidget(self.doc_type_widget)
        self._build_review_screen()

    # ---------------------------------------------------------------- Screen 2

    def _build_review_screen(self):
        self.review_widget = QWidget()
        layout = QVBoxLayout(self.review_widget)

        intro = QLabel(
            f"Document type: <b>{DOCUMENT_TYPES[self.doc_type]}</b>. Every step below was detected by a "
            f"checkable structural rule. Steps marked REVIEW involve a judgment call and start unchecked; "
            f"everything else starts checked. Nothing is applied until Apply is clicked."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; padding: 6px;")
        layout.addWidget(intro)

        if self.plan.notes:
            notes_box = QGroupBox("Notes")
            notes_layout = QVBoxLayout(notes_box)
            for note in self.plan.notes:
                note_label = QLabel(f"⚠ {note}")
                note_label.setWordWrap(True)
                note_label.setStyleSheet(f"color: {Colors.WARNING_STRONG};")
                notes_layout.addWidget(note_label)
            layout.addWidget(notes_box)

        # AI-assist row - only offered where heuristics came up short, and
        # only if an AI provider is actually configured. Never shown as a
        # requirement to use the wizard.
        ai_row = self._build_ai_assist_row()
        if ai_row is not None:
            layout.addWidget(ai_row)

        splitter = QSplitter(Qt.Vertical)

        steps_scroll = QScrollArea()
        steps_scroll.setWidgetResizable(True)
        steps_container = QWidget()
        self.steps_layout = QVBoxLayout(steps_container)

        if not self.plan.steps:
            self.steps_layout.addWidget(QLabel("No structural issues detected - nothing to clean up."))
        for step in self.plan.steps:
            self.steps_layout.addWidget(self._build_step_widget(step))
        self.steps_layout.addStretch()
        steps_scroll.setWidget(steps_container)
        splitter.addWidget(steps_scroll)

        preview_frame = QFrame()
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.addWidget(QLabel("<b>Preview after accepted steps:</b>"))
        self.preview_summary = QLabel()
        preview_layout.addWidget(self.preview_summary)
        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        preview_layout.addWidget(self.preview_table)
        splitter.addWidget(preview_frame)
        splitter.setSizes([350, 350])

        layout.addWidget(splitter)

        button_row = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(self._on_back)
        button_row.addWidget(back_btn)
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self.apply_btn = QPushButton()
        self.apply_btn.clicked.connect(self.accept)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

        self.layout.addWidget(self.review_widget)
        self._update_preview()

    def _on_back(self):
        self.review_widget.setVisible(False)
        self.layout.removeWidget(self.review_widget)
        self.review_widget.deleteLater()
        self.doc_type_widget.setVisible(True)
        self.layout.addWidget(self.doc_type_widget)

    def _build_step_widget(self, step: CleaningStep) -> QWidget:
        box = QGroupBox()
        box_layout = QVBoxLayout(box)

        display_name = OPERATION_REGISTRY.get(step.operation_id, {}).get("display_name", step.operation_id)
        checkbox = QCheckBox(f"{display_name}  [{step.confidence.upper()} CONFIDENCE]")
        checkbox.setChecked(step.confidence == "high")
        checkbox.stateChanged.connect(self._update_preview)
        if step.confidence == "review":
            checkbox.setStyleSheet(f"font-weight: bold; color: {Colors.WARNING_STRONG};")
        box_layout.addWidget(checkbox)

        desc = QLabel(step.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; margin-left: 20px;")
        box_layout.addWidget(desc)

        self.step_checkboxes.append((checkbox, step))
        return box

    def get_accepted_steps(self):
        return [(step.operation_id, step.params) for checkbox, step in self.step_checkboxes if checkbox.isChecked()]

    def _update_preview(self, *_):
        accepted = self.get_accepted_steps()
        if accepted:
            self.apply_btn.setText(f"Apply {len(accepted)} Accepted Step{'s' if len(accepted) != 1 else ''}")
        else:
            self.apply_btn.setText("Import As-Is (No Steps)")
        self.apply_btn.setEnabled(True)

        df = self.raw_df
        error = None
        for operation_id, params in accepted:
            try:
                df = self.data_processor.apply_operation(df, operation_id, dict(params))
            except Exception as e:
                error = f"Step '{operation_id}' failed to preview: {e}"
                break

        if error:
            self.preview_summary.setText(f"<span style='color:{Colors.DANGER}'>{error}</span>")
            self.apply_btn.setEnabled(False)
            return

        self.preview_summary.setText(f"{df.height:,} rows × {len(df.columns)} columns")
        preview_rows = min(50, df.height)
        self.preview_table.setRowCount(preview_rows)
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(preview_rows):
            row_vals = df.row(r)
            for c, val in enumerate(row_vals):
                self.preview_table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))

    # ------------------------------------------------------------- AI assist

    def _build_ai_assist_row(self):
        """Only ever offered where a heuristic came up short for this
        document type, and only if AI is actually configured - the wizard
        is fully usable without any of this."""
        if self.ai_manager is None or not getattr(self.ai_manager, "providers", None):
            return None

        buttons = []
        has_debit_credit_step = any(s.operation_id == "combine_debit_credit" for s in self.plan.steps)
        has_hierarchy_step = any(s.operation_id == "extract_hierarchy_level" for s in self.plan.steps)
        has_period_unpivot = any(s.operation_id == "unpivot_table" for s in self.plan.steps)

        if self.doc_type in ("gl_je", "trial_balance") and not has_debit_credit_step:
            btn = QPushButton("✨ Ask AI to identify Debit/Credit columns")
            btn.clicked.connect(self._on_ask_ai_column_mapping)
            buttons.append(btn)

        if self.doc_type in ("trial_balance", "financial_statement", "chart_of_accounts") and has_hierarchy_step:
            btn = QPushButton("✨ Ask AI to classify accounts into categories")
            btn.clicked.connect(self._on_ask_ai_category_mapping)
            buttons.append(btn)

        if self.doc_type == "financial_statement" and not has_period_unpivot:
            btn = QPushButton("✨ Ask AI to identify period columns")
            btn.clicked.connect(self._on_ask_ai_period_columns)
            buttons.append(btn)

        if not buttons:
            return None

        box = QGroupBox("AI Assist (optional)")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(QLabel(
            "Heuristics didn't find these automatically - AI can suggest a mapping to review before "
            "it's added as a step. Nothing here is applied without your confirmation."
        ))
        for btn in buttons:
            box_layout.addWidget(btn)
        return box

    def _run_ai_task(self, coro_factory, on_success):
        """Runs an async AI call on a background QThread; on_success is
        invoked on the MAIN thread via the worker's result_ready signal,
        since it builds/shows a QDialog to review the suggestion and Qt
        widgets can only be created on the GUI thread. Keeps a reference
        to the worker on self so it isn't garbage-collected mid-run."""
        worker = _AIWorker(coro_factory)
        worker.result_ready.connect(on_success)
        worker.failed.connect(lambda msg: QMessageBox.warning(self, "AI Request Failed", msg))
        if not hasattr(self, '_ai_workers'):
            self._ai_workers = []
        self._ai_workers.append(worker)
        worker.finished.connect(lambda: self._ai_workers.remove(worker) if worker in self._ai_workers else None)
        worker.start()

    def _get_working_df(self) -> pl.DataFrame:
        """self.raw_df is read with no header assumed, so its columns are
        always generic placeholders (column_1, column_2, ...) - every
        detector in build_financial_import_plan() instead works off
        column/account names AFTER the proposed row-removal and header-
        promotion steps are simulated (see raw_data_view in
        core.financial_import_wizard.build_financial_import_plan). Replay
        just those structural steps here, in plan order, so every AI-
        assist method sees the same names the plan's own steps (like
        extract_hierarchy_level) refer to - regardless of whether the
        user has checked those steps' boxes yet. Cached since the plan
        doesn't change after the dialog is built."""
        if self._working_df is not None:
            return self._working_df

        df = self.raw_df
        for step in self.plan.steps:
            if step.operation_id in ("remove_rows", "promote_row_header"):
                try:
                    df = self.data_processor.apply_operation(df, step.operation_id, step.params)
                except Exception:
                    pass
        self._working_df = df
        return df

    def _on_ask_ai_column_mapping(self):
        from services.ai_service import FinancialImportAI
        ai = FinancialImportAI(self.ai_manager)
        working_df = self._get_working_df()
        column_names = list(working_df.columns)
        sample_rows = working_df.head(5).to_dicts()
        target_fields = {"debit_column": "the debit amount column", "credit_column": "the credit amount column"}

        def on_result(mapping):
            dialog = _MappingReviewDialog(
                "Suggested Debit/Credit Columns",
                "Review the suggested mapping - edit any field that's wrong, then confirm.",
                mapping, value_options=column_names, parent=self,
            )
            if dialog.exec() == QDialog.Accepted:
                confirmed = dialog.get_mapping()
                if confirmed.get("debit_column") and confirmed.get("credit_column"):
                    self._add_step(CleaningStep(
                        operation_id="combine_debit_credit",
                        params={"debit_column": confirmed["debit_column"], "credit_column": confirmed["credit_column"], "output_column": "amount"},
                        description=f"AI-suggested (reviewed): '{confirmed['debit_column']}' and '{confirmed['credit_column']}' are the debit/credit columns.",
                        confidence="review",
                    ))

        self._run_ai_task(lambda: ai.suggest_column_mapping(column_names, sample_rows, target_fields), on_result)

    def _on_ask_ai_category_mapping(self):
        from services.ai_service import FinancialImportAI
        hierarchy_step = next((s for s in self.plan.steps if s.operation_id == "extract_hierarchy_level"), None)
        if hierarchy_step is None:
            QMessageBox.information(
                self, "Not Available",
                "No account/line-item hierarchy was detected in this file, so there's no "
                "account column to classify."
            )
            return
        account_col = hierarchy_step.params["column"]
        working_df = self._get_working_df()
        if account_col not in working_df.columns:
            QMessageBox.warning(
                self, "Not Available",
                f"Expected an account column named '{account_col}' after the proposed structural "
                "steps, but it isn't there. Please map columns manually."
            )
            return

        account_names = [str(v).strip() for v in working_df[account_col].drop_nulls().unique().to_list()]
        categories = ["Current Assets", "Non-Current Assets", "Current Liabilities",
                     "Non-Current Liabilities", "Equity", "Revenue", "Expense"]
        ai = FinancialImportAI(self.ai_manager)

        def on_result(mapping):
            dialog = _MappingReviewDialog(
                "Suggested Account Categories",
                "Review each account's suggested category - edit any that's wrong, then confirm.",
                mapping, value_options=categories, parent=self,
            )
            if dialog.exec() == QDialog.Accepted:
                confirmed = {k: v for k, v in dialog.get_mapping().items() if v}
                if confirmed:
                    self._add_step(CleaningStep(
                        operation_id="map_column_values",
                        params={"column": account_col, "mapping": confirmed, "output_column": "fs_category"},
                        description=f"AI-suggested (reviewed): map '{account_col}' values to financial-statement categories.",
                        confidence="review",
                    ))

        self._run_ai_task(lambda: ai.suggest_account_category_mapping(account_names, categories), on_result)

    def _on_ask_ai_period_columns(self):
        from services.ai_service import FinancialImportAI
        column_names = list(self._get_working_df().columns)
        ai = FinancialImportAI(self.ai_manager)

        def on_result(period_cols):
            if not period_cols:
                QMessageBox.information(self, "No Suggestions", "AI didn't identify any additional period columns.")
                return
            non_period_cols = [c for c in column_names if c not in period_cols]
            self._add_step(CleaningStep(
                operation_id="unpivot_table",
                params={"id_vars": non_period_cols, "value_vars": period_cols, "var_name": "period", "value_name": "amount"},
                description=f"AI-suggested (reviewed): {', '.join(period_cols)} look like period columns - unpivot into a tidy (line item, period, amount) table.",
                confidence="review",
            ))

        self._run_ai_task(lambda: ai.suggest_period_columns(column_names), on_result)

    def _add_step(self, step: CleaningStep):
        self.plan.steps.append(step)
        self.steps_layout.insertWidget(self.steps_layout.count() - 1, self._build_step_widget(step))
        self._update_preview()
