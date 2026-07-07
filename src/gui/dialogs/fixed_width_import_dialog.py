"""Fixed-Width Text Import Dialog - review and adjust the column
boundaries CaatMaster auto-detects in a .txt/.dat file before import.
Auto-detection (pandas' column-alignment inference) is a good starting
point but not perfectly reliable - a value in one row that's wider than
what earlier rows suggested for that column can shift the inferred
boundaries, so this dialog lets the auditor see the parsed result and
override the column widths/names before anything is imported."""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QTextEdit,
    QRadioButton, QButtonGroup, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from core.data_processor import LegacyDataProcessor
from gui.theme import Colors
from gui.components.common_modals import create_success_button


class FixedWidthImportDialog(QDialog):
    """Preview and adjust a fixed-width text file's column boundaries
    before import. .result_df holds the final parsed dataframe once
    accepted - the caller reads it after exec()."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.result_df = None

        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            self.raw_lines = [f.readline().rstrip('\n') for _ in range(15)]
        self.raw_lines = [l for l in self.raw_lines if l]

        self.setWindowTitle("Import Fixed-Width Text File")
        self.resize(820, 640)
        self._setup_ui()
        self._do_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(
            "This file doesn't look like a delimited CSV - it's being read as fixed-width text "
            "(columns aligned by character position, common in legacy/mainframe report exports). "
            "Review the parsed result below and adjust column widths/names if anything looks off."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY};")
        layout.addWidget(info)

        raw_group = QGroupBox("Raw File (first lines)")
        raw_layout = QVBoxLayout(raw_group)
        ruler = "".join(str(i % 10) if i % 10 else "|" for i in range(120))
        raw_view = QTextEdit()
        raw_view.setReadOnly(True)
        raw_view.setFont(QFont("Consolas", 9))
        raw_view.setPlainText(ruler + "\n" + "\n".join(self.raw_lines))
        raw_view.setMaximumHeight(160)
        raw_layout.addWidget(raw_view)
        layout.addWidget(raw_group)

        mode_group = QGroupBox("Column Widths")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_group = QButtonGroup()
        self.auto_radio = QRadioButton("Auto-detect from column alignment (default)")
        self.auto_radio.setChecked(True)
        self.manual_radio = QRadioButton("Manual - specify column boundaries")
        self.mode_group.addButton(self.auto_radio)
        self.mode_group.addButton(self.manual_radio)
        mode_layout.addWidget(self.auto_radio)
        mode_layout.addWidget(self.manual_radio)

        self.colspecs_edit = QLineEdit()
        self.colspecs_edit.setPlaceholderText("e.g. 0-6, 6-26, 26-36, 36-46 (character positions, 0-indexed)")
        self.colspecs_edit.setEnabled(False)
        mode_layout.addWidget(self.colspecs_edit)

        self.names_edit = QLineEdit()
        self.names_edit.setPlaceholderText("Optional: comma-separated column names, e.g. id, name, region, amount")
        mode_layout.addWidget(QLabel("Column names (optional - leave blank to keep detected headers):"))
        mode_layout.addWidget(self.names_edit)

        self.auto_radio.toggled.connect(lambda checked: self.colspecs_edit.setEnabled(not checked))

        preview_btn = QPushButton("Re-Preview")
        preview_btn.clicked.connect(self._do_preview)
        mode_layout.addWidget(preview_btn)

        layout.addWidget(mode_group)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        preview_layout.addWidget(self.preview_table)
        layout.addWidget(preview_group, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.import_btn = create_success_button("Import")
        self.import_btn.clicked.connect(self._on_import)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

    def _parse_colspecs(self):
        text = self.colspecs_edit.text().strip()
        if not text:
            return "infer"
        specs = []
        for part in text.split(","):
            part = part.strip()
            if "-" not in part:
                raise ValueError(f"'{part}' isn't a valid 'start-end' range.")
            start_s, end_s = part.split("-", 1)
            specs.append((int(start_s.strip()), int(end_s.strip())))
        return specs

    def _parse_names(self):
        text = self.names_edit.text().strip()
        if not text:
            return None
        return [n.strip() for n in text.split(",") if n.strip()]

    def _do_preview(self):
        try:
            colspecs = "infer" if self.auto_radio.isChecked() else self._parse_colspecs()
            names = self._parse_names()
            df = LegacyDataProcessor.read_fixed_width_file(self.file_path, colspecs=colspecs, column_names=names)
            self._populate_preview(df.head(20))
        except Exception as e:
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(1)
            self.preview_table.setHorizontalHeaderLabels(["Error"])
            self.preview_table.setRowCount(1)
            self.preview_table.setItem(0, 0, QTableWidgetItem(str(e)))

    def _populate_preview(self, df: pl.DataFrame):
        self.preview_table.setRowCount(df.height)
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(df.height):
            row_vals = df.row(r)
            for c, val in enumerate(row_vals):
                self.preview_table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))

    def _on_import(self):
        try:
            colspecs = "infer" if self.auto_radio.isChecked() else self._parse_colspecs()
            names = self._parse_names()
            self.result_df = LegacyDataProcessor.read_fixed_width_file(
                self.file_path, colspecs=colspecs, column_names=names
            )
        except Exception as e:
            QMessageBox.warning(self, "Import Failed", f"Could not parse the file with these settings:\n{str(e)}")
            return

        if self.result_df is None or len(self.result_df.columns) == 0:
            QMessageBox.warning(self, "Empty Data", "No columns were parsed - adjust the column widths and try again.")
            return

        self.accept()
