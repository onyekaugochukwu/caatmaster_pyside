"""Agent Dataset Preview Dialog - preview a query result the AI proposed
before deciding whether to materialize it as a new dataset directly, or
hand the query off to the SQL editor for manual review/execution instead."""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class AgentDatasetPreviewDialog(QDialog):
    """Preview an AI-proposed query result before deciding whether to
    materialize it as a new dataset or open it in the SQL editor instead.
    Never creates anything itself - the caller reads .choice after exec()
    and acts on it."""

    OPEN_IN_SQL_EDITOR = "open_in_sql_editor"
    CREATE_DATASET = "create_dataset"

    def __init__(self, sql: str, name: str, reason: str, result_df: pl.DataFrame, parent=None):
        super().__init__(parent)
        self.sql = sql
        self.suggested_name = name
        self.result_df = result_df
        self.choice = None  # set to OPEN_IN_SQL_EDITOR or CREATE_DATASET on accept

        self.setWindowTitle("Review: New Dataset")
        self.resize(800, 620)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        icon = QLabel("🤖")
        icon.setStyleSheet("font-size: 20px;")
        title_row.addWidget(icon)
        title = QLabel("Proposed dataset")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        if reason:
            reason_label = QLabel(reason)
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet(
                "color: #4b5563; padding: 8px; background-color: #edebe9; border-radius: 4px;"
            )
            layout.addWidget(reason_label)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Dataset name:"))
        self.name_edit = QLineEdit(name)
        name_row.addWidget(self.name_edit, 1)
        layout.addLayout(name_row)

        sql_group = QGroupBox("Query")
        sql_layout = QVBoxLayout(sql_group)
        sql_view = QTextEdit()
        sql_view.setReadOnly(True)
        sql_view.setPlainText(sql)
        sql_view.setMaximumHeight(90)
        sql_view.setFont(QFont("Consolas", 10))
        sql_layout.addWidget(sql_view)
        layout.addWidget(sql_group)

        self.summary_label = QLabel(f"{result_df.height:,} rows × {len(result_df.columns)} columns")
        self.summary_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.summary_label)

        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self._populate_preview()
        layout.addWidget(self.preview_table, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        sql_editor_btn = QPushButton("Open in SQL Editor")
        sql_editor_btn.setToolTip("Paste this query into the SQL editor so you can review, tweak, and run it yourself.")
        sql_editor_btn.clicked.connect(self._on_open_in_sql_editor)
        button_row.addWidget(sql_editor_btn)

        create_btn = QPushButton("Create Dataset")
        create_btn.setStyleSheet("""
            QPushButton { padding: 10px 20px; background-color: #10b981; color: white;
                          border: none; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background-color: #059669; }
        """)
        create_btn.clicked.connect(self._on_create_dataset)
        button_row.addWidget(create_btn)
        layout.addLayout(button_row)

    def _populate_preview(self):
        preview_rows = min(50, self.result_df.height)
        self.preview_table.setRowCount(preview_rows)
        self.preview_table.setColumnCount(len(self.result_df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in self.result_df.columns])
        for r in range(preview_rows):
            row_vals = self.result_df.row(r)
            for c, val in enumerate(row_vals):
                self.preview_table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))

    def _on_open_in_sql_editor(self):
        self.choice = self.OPEN_IN_SQL_EDITOR
        self.accept()

    def _on_create_dataset(self):
        self.choice = self.CREATE_DATASET
        self.accept()

    def get_dataset_name(self) -> str:
        return self.name_edit.text().strip() or self.suggested_name or "AI Dataset"
