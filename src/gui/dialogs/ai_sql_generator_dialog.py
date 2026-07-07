"""AI SQL Generator Dialog - Describe a query in plain language, review the
generated SQL, and insert it into the SQL editor. Never executes anything
itself - Insert only writes the text into the editor; the auditor still has
to click Execute themselves, same as a query they typed by hand."""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThreadPool
from PySide6.QtGui import QFont

from services.sql_query_service import is_safe_readonly_select
from gui.theme import Colors
from gui.components.common_modals import create_primary_button, create_success_button


class AISQLGeneratorDialog(QDialog):
    """Dialog for generating a SQL query from a natural-language description."""

    sql_accepted = Signal(str)  # emitted with the final SQL text on Insert
    # Thread-safe signals for UI updates (mirrors ColumnGeneratorDialog)
    _sqlReady = Signal(str)
    _explanationReady = Signal(str)
    _generationFailed = Signal(str)

    def __init__(self, table_schemas: dict, sql_generator, parent=None):
        """
        Args:
            table_schemas: {table_name: polars DataFrame} for every table
                currently registered in the SQL editor's connection
            sql_generator: an ai_service.SQLGenerator instance
        """
        super().__init__(parent)
        self.table_schemas = table_schemas
        self.generator = sql_generator
        self.suggestion = None
        self.thread_pool = QThreadPool()
        self.setup_ui()

        self._sqlReady.connect(self._on_sql_ready, Qt.QueuedConnection)
        self._explanationReady.connect(self._on_explanation_ready, Qt.QueuedConnection)
        self._generationFailed.connect(self._on_generation_failed, Qt.QueuedConnection)

    def closeEvent(self, event):
        self.thread_pool.waitForDone(3000)
        event.accept()

    def setup_ui(self):
        self.setWindowTitle("Ask AI to Write a Query")
        self.setMinimumSize(560, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title_layout = QHBoxLayout()
        title_icon = QLabel("✨")
        title_icon.setStyleSheet("font-size: 20px;")
        title_layout.addWidget(title_icon)
        title = QLabel("Describe the query you want")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        tables_label = QLabel(
            "Tables available: " + (", ".join(self.table_schemas.keys()) or "(none registered)")
        )
        tables_label.setWordWrap(True)
        tables_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(tables_label)

        self.instruction_edit = QTextEdit()
        self.instruction_edit.setPlaceholderText(
            "e.g. \"Total spend by vendor, approved transactions only, highest first\""
        )
        self.instruction_edit.setMaximumHeight(80)
        layout.addWidget(self.instruction_edit)

        self.generate_btn = create_primary_button("✨ Generate SQL")
        self.generate_btn.clicked.connect(self.generate_sql)
        layout.addWidget(self.generate_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.explanation_label = QLabel()
        self.explanation_label.setWordWrap(True)
        self.explanation_label.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; padding: 8px; background-color: {Colors.BG_SECONDARY}; border-radius: 4px;"
        )
        self.explanation_label.setVisible(False)
        layout.addWidget(self.explanation_label)

        self.sql_edit = QTextEdit()
        self.sql_edit.setReadOnly(True)
        self.sql_edit.setPlaceholderText("Generated SQL will appear here for review...")
        self.sql_edit.setFont(QFont("Consolas", 10))
        # Deliberately dark, code-editor-style regardless of the app's
        # light theme (same convention as VS Code/GitHub code blocks) -
        # not a semantic status color, so kept as a direct pair rather
        # than a Colors token.
        self.sql_edit.setStyleSheet(
            f"background-color: {Colors.TEXT_PRIMARY}; color: {Colors.BG_PRIMARY}; border-radius: 6px; padding: 10px;"
        )
        layout.addWidget(self.sql_edit, 1)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet(
            f"color: {Colors.DANGER}; background-color: {Colors.DANGER_SOFT}; padding: 8px; border-radius: 4px;"
        )
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

        button_layout = QHBoxLayout()
        self.insert_btn = create_success_button("Insert into Editor")
        self.insert_btn.setEnabled(False)
        self.insert_btn.clicked.connect(self._on_insert)
        button_layout.addWidget(self.insert_btn)
        button_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def generate_sql(self):
        instruction = self.instruction_edit.toPlainText().strip()
        if not instruction:
            QMessageBox.warning(self, "No Description", "Please describe the query you want.")
            return
        if not self.table_schemas:
            QMessageBox.warning(self, "No Data", "Register at least one dataset before asking AI to write a query.")
            return
        if not self.generator.ai.providers:
            QMessageBox.warning(
                self, "AI Not Configured",
                "Please configure an AI provider in Settings > AI Settings first."
            )
            return

        self.generate_btn.setEnabled(False)
        self.insert_btn.setEnabled(False)
        self.warning_label.setVisible(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        async def do_generate():
            try:
                suggestion = await self.generator.generate_sql(instruction, self.table_schemas)
                self.suggestion = suggestion
                self._sqlReady.emit(suggestion.sql)
                self._explanationReady.emit(suggestion.explanation)
            except Exception as e:
                self._generationFailed.emit(str(e))

        def run_async():
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(do_generate())
            finally:
                loop.close()

        self.thread_pool.start(run_async)

    def _on_sql_ready(self, sql: str):
        self.sql_edit.setPlainText(sql)
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)

        is_safe, reason = is_safe_readonly_select(sql)
        if not is_safe:
            self.insert_btn.setEnabled(False)
            self.warning_label.setText(
                f"⚠ This response was not inserted — {reason} Try rephrasing the request."
            )
            self.warning_label.setVisible(True)
            return

        resolves, reason = self._check_sql_resolves(sql)
        if not resolves:
            self.insert_btn.setEnabled(False)
            self.warning_label.setText(
                f"⚠ This query doesn't run against your data — {reason} Try rephrasing, or edit it "
                f"manually before inserting."
            )
            self.warning_label.setVisible(True)
            return

        self.insert_btn.setEnabled(True)
        self.warning_label.setVisible(False)

    def _check_sql_resolves(self, sql: str) -> tuple:
        """EXPLAIN the generated query against the real registered tables -
        catches a hallucinated table/column reference (the model inventing
        a plausible-sounding "Customer" table that isn't actually one of
        the tables it was given) before the query ever reaches the main
        editor, rather than leaving that discovery for Execute."""
        try:
            import duckdb
        except ImportError:
            return True, ""  # can't check without duckdb - don't block on that basis
        try:
            conn = duckdb.connect(':memory:')
            for name, df in self.table_schemas.items():
                conn.register(name, df)
            conn.execute(f"EXPLAIN {sql}")
            conn.close()
            return True, ""
        except Exception as e:
            return False, str(e)

    def _on_explanation_ready(self, explanation: str):
        self.explanation_label.setText(explanation)
        self.explanation_label.setVisible(bool(explanation))

    def _on_generation_failed(self, error: str):
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        QMessageBox.critical(self, "Generation Error", error)

    def _on_insert(self):
        if not self.suggestion:
            return
        self.sql_accepted.emit(self.suggestion.sql)
        self.accept()
