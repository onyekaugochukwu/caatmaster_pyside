"""
Generic viewer for any AnalysisReport — one dialog reused by every
reportable operation (Find Duplicates, Benford's Law, Gap Analysis, ML
models, etc.). Non-modal-feeling by design: it's informational, dismissible,
and never blocks the transformation it's reporting on (which already
succeeded before this dialog is shown).
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QWidget, QFormLayout, QFileDialog,
    QMessageBox
)

from core.analysis_report import AnalysisReport
from core.report_exporter import EXPORTERS
from gui.theme import Colors


class AnalysisReportDialog(QDialog):
    """Shows an AnalysisReport's summary + tables, with Export buttons."""

    def __init__(self, report: AnalysisReport, parent=None):
        super().__init__(parent)
        self.report = report
        self.setWindowTitle(report.title)
        self.setMinimumSize(700, 520)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel(self.report.title)
        header.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(header)

        timestamp = QLabel(self.report.generated_at.strftime("Generated %Y-%m-%d %H:%M:%S"))
        timestamp.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 11px;")
        layout.addWidget(timestamp)

        tabs = QTabWidget()

        if self.report.summary:
            summary_widget = QWidget()
            summary_layout = QFormLayout(summary_widget)
            summary_layout.setSpacing(8)
            for label, value in self.report.summary:
                value_label = QLabel(str(value))
                value_label.setWordWrap(True)
                value_label.setStyleSheet("font-weight: 600;")
                summary_layout.addRow(f"{label}:", value_label)
            tabs.addTab(summary_widget, "Summary")

        for name, df in self.report.tables:
            table = QTableWidget()
            table.setAlternatingRowColors(True)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            display_df = df.head(500)
            table.setRowCount(display_df.height)
            table.setColumnCount(display_df.width)
            table.setHorizontalHeaderLabels(display_df.columns)
            for row_idx in range(display_df.height):
                for col_idx, value in enumerate(display_df.row(row_idx)):
                    table.setItem(row_idx, col_idx, QTableWidgetItem(str(value) if value is not None else ""))
            table.resizeColumnsToContents()
            tabs.addTab(table, name)

        layout.addWidget(tabs, 1)

        if self.report.notes:
            notes_label = QLabel("\n".join(f"- {n}" for n in self.report.notes))
            notes_label.setWordWrap(True)
            notes_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-style: italic;")
            layout.addWidget(notes_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        for label, fmt in (("Export TXT", "txt"), ("Export CSV", "csv"), ("Export XLSX", "xlsx")):
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked=False, f=fmt: self._export(f))
            btn_layout.addWidget(btn)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _export(self, fmt: str):
        default_name = self.report.operation_id or "analysis_report"
        file_path, _ = QFileDialog.getSaveFileName(
            self, f"Export Report ({fmt.upper()})",
            str(Path.home() / "Documents" / default_name),
            f"{fmt.upper()} Files (*.{fmt})"
        )
        if not file_path:
            return
        if not file_path.endswith(f".{fmt}"):
            file_path += f".{fmt}"

        try:
            EXPORTERS[fmt](self.report, file_path)
            QMessageBox.information(self, "Export Complete", f"Report exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export report:\n{str(e)}")
