"""
Numeric Disclosure Reconciliation Dialog - extracts numeric disclosures
(rates, useful lives, discount rates, ...) from pasted or PDF narrative
text via AI, then reconciles each one against a real computed value from
a mapped dataset column, entirely in Python (never asked of the AI).
"""
from typing import Dict, List, Optional

import polars as pl
from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QProgressBar, QFileDialog, QDoubleSpinBox, QWidget
)

from gui.theme import Colors
from gui.components.common_modals import create_primary_button, create_secondary_button


def _read_pdf_text(filepath: str) -> str:
    """Extract text from a PDF (first 50 pages, capped length) - same
    approach as ai_panel.py's _read_pdf, duplicated locally since that one
    is a private method of a different component."""
    try:
        import pypdf
        reader = pypdf.PdfReader(filepath)
        text = ""
        for page in reader.pages[:50]:
            text += (page.extract_text() or "") + "\n"
        return text[:100000]
    except ImportError:
        raise RuntimeError("pypdf is required to read PDF files. Install it with: pip install pypdf")


class NumericDisclosureDialog(QDialog):
    """Dialog for extracting numeric disclosures from narrative text and
    reconciling them against real dataset figures."""

    _extractReady = Signal(list)
    _extractFailed = Signal(str)
    _reconcileReady = Signal(list)

    def __init__(self, dataframes: Dict[str, pl.DataFrame], ai_manager, parent=None):
        super().__init__(parent)
        self.dataframes = dataframes
        self.ai_manager = ai_manager
        self.extracted_items: List[dict] = []
        self.thread_pool = QThreadPool()
        self.setWindowTitle("Numeric Disclosure Reconciliation")
        self.setMinimumSize(950, 650)
        self._setup_ui()

        self._extractReady.connect(self._on_extract_ready, Qt.QueuedConnection)
        self._extractFailed.connect(self._on_extract_failed, Qt.QueuedConnection)
        self._reconcileReady.connect(self._on_reconcile_ready, Qt.QueuedConnection)

    def closeEvent(self, event):
        self.thread_pool.waitForDone(3000)
        event.accept()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Numeric Disclosure Reconciliation")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)

        hint = QLabel(
            "Extracts numeric disclosures (rates, useful lives, discount rates, ...) from narrative "
            "text via AI, then reconciles each one against a real computed value from a dataset "
            "column you map below - entirely in Python, never asked of the AI. Extraction is "
            "AI-drafted; always verify a flagged item against the context snippet shown."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(hint)

        text_group = QGroupBox("Disclosure Text")
        text_layout = QVBoxLayout(text_group)
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Paste the notes to the financial statements here, or load a PDF..."
        )
        self.text_edit.setStyleSheet("QTextEdit { min-height: 100px; }")
        text_layout.addWidget(self.text_edit)

        load_pdf_btn = create_secondary_button("Load PDF...")
        load_pdf_btn.setCursor(Qt.PointingHandCursor)
        load_pdf_btn.clicked.connect(self._load_pdf)
        text_layout.addWidget(load_pdf_btn, alignment=Qt.AlignLeft)
        layout.addWidget(text_group)

        self.extract_btn = create_primary_button("Extract Figures")
        self.extract_btn.clicked.connect(self._run_extraction)
        layout.addWidget(self.extract_btn)

        self.extract_progress = QProgressBar()
        self.extract_progress.setVisible(False)
        layout.addWidget(self.extract_progress)

        self.status_label = QLabel()
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet(
            f"font-size: 12px; color: {Colors.TEXT_SECONDARY}; padding: 6px; "
            f"background-color: {Colors.BG_SECONDARY}; border-radius: 4px;"
        )
        layout.addWidget(self.status_label)

        table_group = QGroupBox("Extracted Figures - Map Each to a Real Dataset Column")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Label", "Disclosed Value", "Unit", "Context Snippet",
            "Dataset", "Column", "Actual (mean)", "Deviation", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table_layout.addWidget(self.table)
        layout.addWidget(table_group, 1)

        tolerance_row = QHBoxLayout()
        tolerance_row.addWidget(QLabel("Flag if absolute deviation exceeds:"))
        self.tolerance_abs_spin = QDoubleSpinBox()
        self.tolerance_abs_spin.setRange(0.0, 1000000.0)
        self.tolerance_abs_spin.setDecimals(4)
        self.tolerance_abs_spin.setValue(0.005)
        tolerance_row.addWidget(self.tolerance_abs_spin)
        tolerance_row.addWidget(QLabel("AND relative deviation exceeds:"))
        self.tolerance_pct_spin = QDoubleSpinBox()
        self.tolerance_pct_spin.setRange(0.0, 1000.0)
        self.tolerance_pct_spin.setValue(10.0)
        self.tolerance_pct_spin.setSuffix("%")
        tolerance_row.addWidget(self.tolerance_pct_spin)
        tolerance_row.addStretch()
        layout.addLayout(tolerance_row)

        reconcile_btn = create_primary_button("Reconcile Against Real Data")
        reconcile_btn.clicked.connect(self._run_reconciliation)
        layout.addWidget(reconcile_btn)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _load_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load PDF", "", "PDF Files (*.pdf)")
        if not file_path:
            return
        try:
            text = _read_pdf_text(file_path)
        except Exception as e:
            QMessageBox.critical(self, "PDF Error", str(e))
            return
        self.text_edit.setPlainText(text)

    def _run_extraction(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "No Text", "Paste disclosure text or load a PDF first.")
            return
        if not self.ai_manager or not self.ai_manager.providers:
            QMessageBox.warning(self, "AI Not Configured", "Please configure an AI provider in Settings > AI Settings first.")
            return

        self.extract_btn.setEnabled(False)
        self.extract_progress.setVisible(True)
        self.extract_progress.setRange(0, 0)
        self.status_label.setVisible(True)
        self.status_label.setText("Extracting numeric disclosures...")

        async def do_extract():
            try:
                from services.ai_service import NumericDisclosureExtractor
                extractor = NumericDisclosureExtractor(self.ai_manager)
                figures = await extractor.extract_disclosed_figures(text)
                self._extractReady.emit(figures)
            except Exception as e:
                self._extractFailed.emit(str(e))

        def run_async():
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(do_extract())
            finally:
                loop.close()

        self.thread_pool.start(run_async)

    def _on_extract_ready(self, figures: list):
        self.extract_btn.setEnabled(True)
        self.extract_progress.setVisible(False)
        self.extracted_items = figures
        self.status_label.setText(
            f"Extracted {len(figures)} figure(s). Map each to a dataset/column, then Reconcile."
            if figures else "No numeric disclosures found in this text."
        )
        self._populate_table(figures)

    def _on_extract_failed(self, error: str):
        self.extract_btn.setEnabled(True)
        self.extract_progress.setVisible(False)
        self.status_label.setText(f"Error: {error}")
        QMessageBox.critical(self, "Extraction Error", error)

    def _populate_table(self, figures: list):
        self.table.setRowCount(len(figures))
        dataset_names = list(self.dataframes.keys())

        for row, item in enumerate(figures):
            self.table.setItem(row, 0, QTableWidgetItem(item.get("label", "")))
            self.table.setItem(row, 1, QTableWidgetItem(item.get("value_text", "")))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("unit", "")))
            snippet_item = QTableWidgetItem(item.get("context_snippet", ""))
            snippet_item.setFlags(snippet_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, snippet_item)

            dataset_combo = QComboBox()
            dataset_combo.addItem("— Not mapped —", None)
            for name in dataset_names:
                dataset_combo.addItem(name, name)
            column_combo = QComboBox()
            column_combo.addItem("", None)

            def on_dataset_changed(index, ds_combo=dataset_combo, col_combo=column_combo):
                ds_name = ds_combo.currentData()
                col_combo.clear()
                col_combo.addItem("", None)
                if ds_name and ds_name in self.dataframes:
                    numeric_cols = [
                        c for c in self.dataframes[ds_name].columns
                        if self.dataframes[ds_name][c].dtype.is_numeric()
                    ]
                    for c in numeric_cols:
                        col_combo.addItem(c, c)

            dataset_combo.currentIndexChanged.connect(on_dataset_changed)
            self.table.setCellWidget(row, 4, dataset_combo)
            self.table.setCellWidget(row, 5, column_combo)

            for col in (6, 7, 8):
                self.table.setItem(row, col, QTableWidgetItem(""))

    def _run_reconciliation(self):
        if not self.extracted_items:
            QMessageBox.warning(self, "No Figures", "Extract figures first.")
            return

        mappings = {}
        for row in range(self.table.rowCount()):
            dataset_combo = self.table.cellWidget(row, 4)
            column_combo = self.table.cellWidget(row, 5)
            ds_name = dataset_combo.currentData() if dataset_combo else None
            col_name = column_combo.currentData() if column_combo else None
            if ds_name and col_name:
                mappings[row] = {"dataset": ds_name, "column": col_name}

        from core.numeric_disclosure_reconciliation import reconcile_all
        results = reconcile_all(
            self.extracted_items, mappings, self.dataframes,
            tolerance_abs=self.tolerance_abs_spin.value(),
            tolerance_pct=self.tolerance_pct_spin.value(),
        )
        self._reconcileReady.emit(results)

    def _on_reconcile_ready(self, results: list):
        flagged = 0
        for row, result in enumerate(results):
            if not result["computable"]:
                self.table.setItem(row, 6, QTableWidgetItem(""))
                self.table.setItem(row, 7, QTableWidgetItem(""))
                status_item = QTableWidgetItem(f"Not computable: {result.get('reason', '')}")
                status_item.setForeground(Qt.gray)
                self.table.setItem(row, 8, status_item)
                continue

            self.table.setItem(row, 6, QTableWidgetItem(f"{result['actual_mean']:.6g}"))
            deviation_text = f"{result['deviation']:.6g}"
            if result.get("deviation_pct") is not None:
                deviation_text += f" ({result['deviation_pct']:.1f}%)"
            self.table.setItem(row, 7, QTableWidgetItem(deviation_text))

            status_item = QTableWidgetItem("FLAGGED" if result["flag"] else "OK")
            if result["flag"]:
                status_item.setForeground(Qt.red)
                flagged += 1
            else:
                status_item.setForeground(Qt.darkGreen)
            self.table.setItem(row, 8, status_item)

        self.status_label.setVisible(True)
        computable = sum(1 for r in results if r["computable"])
        self.status_label.setText(
            f"Reconciled {computable} of {len(results)} figure(s) against real data — {flagged} flagged."
        )
