"""Agent Action Preview Dialog - the required stop before any AI-proposed
change to the working dataset becomes real. Shows exactly what the operation
would do (run once, on a copy, never on the real pipeline) and requires an
explicit Apply click - mirrors the Cleaning Wizard's propose/preview/accept
pattern rather than introducing a new one."""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt

from core.operation_registry import OPERATION_REGISTRY
from gui.theme import Colors
from gui.components.common_modals import create_success_button


class AgentActionPreviewDialog(QDialog):
    """Preview an AI-proposed operation against the active dataset before
    it's applied. Apply only ever calls back with (operation_id, params) -
    it never touches the real pipeline itself."""

    def __init__(self, df: pl.DataFrame, operation_id: str, params: dict, reason: str,
                 data_processor, parent=None):
        super().__init__(parent)
        self.df = df
        self.operation_id = operation_id
        self.params = params
        self.data_processor = data_processor
        self.approved = False

        op = OPERATION_REGISTRY.get(operation_id, {})
        self.setWindowTitle(f"Review: {op.get('display_name', operation_id)}")
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        icon = QLabel("🤖")
        icon.setStyleSheet("font-size: 20px;")
        title_row.addWidget(icon)
        title = QLabel(op.get("display_name", operation_id))
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        if reason:
            reason_label = QLabel(reason)
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet(
                f"color: {Colors.TEXT_SECONDARY}; padding: 8px; background-color: {Colors.BG_SECONDARY}; border-radius: 4px;"
            )
            layout.addWidget(reason_label)

        params_group = QGroupBox("Parameters")
        params_layout = QVBoxLayout(params_group)
        params_label = QLabel(self._format_params(params))
        params_label.setWordWrap(True)
        params_label.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        params_layout.addWidget(params_label)
        layout.addWidget(params_group)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.summary_label)

        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        layout.addWidget(self.preview_table, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        reject_btn = QPushButton("Not this one")
        reject_btn.clicked.connect(self.reject)
        button_row.addWidget(reject_btn)
        self.apply_btn = create_success_button("Apply")
        self.apply_btn.clicked.connect(self._on_apply)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

        self._run_preview()

    def _format_params(self, params: dict) -> str:
        return "\n".join(f"{k}: {v}" for k, v in params.items()) or "(no parameters)"

    def _run_preview(self):
        """Dry run only - apply_operation returns a new dataframe, the
        original self.df (and the real pipeline) is never touched here."""
        try:
            result_df = self.data_processor.apply_operation(self.df, self.operation_id, dict(self.params))
        except Exception as e:
            self.summary_label.setText(f"⚠ This operation failed to preview: {e}")
            self.summary_label.setStyleSheet(f"color: {Colors.DANGER}; font-weight: 600;")
            self.apply_btn.setEnabled(False)
            return

        self.result_df = result_df
        self.summary_label.setText(
            f"Before: {self.df.height:,} rows × {len(self.df.columns)} columns  →  "
            f"After: {result_df.height:,} rows × {len(result_df.columns)} columns"
        )

        preview_rows = min(50, result_df.height)
        self.preview_table.setRowCount(preview_rows)
        self.preview_table.setColumnCount(len(result_df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in result_df.columns])
        for r in range(preview_rows):
            row_vals = result_df.row(r)
            for c, val in enumerate(row_vals):
                self.preview_table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))

    def _on_apply(self):
        self.approved = True
        self.accept()
