"""Dataset Profile Dialog - shows the automatic "what's interesting about
this data" summary computed by services/dataset_profiler.py, mirroring
CaseWare IDEA's Discover feature. Read-only: never modifies the dataset,
just surfaces real, already-computed findings (duplicates, per-column
completeness/outliers, Benford's Law deviation, correlated column pairs)
so opening a dataset gives an immediate, grounded starting point."""
from typing import Any, Dict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QWidget, QFrame
)
from PySide6.QtCore import Qt

from ..theme import Colors


def _stat_card(title: str, value: str, color: str = None) -> QWidget:
    color = color or Colors.TEXT_PRIMARY
    card = QFrame()
    card.setStyleSheet(
        f"QFrame {{ background-color: {Colors.BG_SECONDARY}; border: 1px solid {Colors.BORDER}; "
        f"border-radius: 8px; padding: 10px; }}"
    )
    layout = QVBoxLayout(card)
    layout.setSpacing(2)
    value_label = QLabel(value)
    value_label.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {color};")
    title_label = QLabel(title)
    title_label.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_SECONDARY};")
    layout.addWidget(value_label)
    layout.addWidget(title_label)
    return card


class DatasetProfileDialog(QDialog):
    """Read-only dashboard of a dataset's auto-computed profile."""

    def __init__(self, dataset_name: str, profile: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Dataset Profile - {dataset_name}")
        self.resize(820, 700)
        self._setup_ui(dataset_name, profile)

    def _setup_ui(self, dataset_name: str, profile: Dict[str, Any]):
        outer = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(16)

        title = QLabel(f"🔎 {dataset_name}")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)

        cards_row = QHBoxLayout()
        cards_row.addWidget(_stat_card("Rows", f"{profile['n_rows']:,}"))
        cards_row.addWidget(_stat_card("Columns", f"{profile['n_columns']:,}"))
        dup_color = Colors.DANGER if profile["duplicate_rows"] > 0 else Colors.TEXT_PRIMARY
        cards_row.addWidget(_stat_card("Duplicate Rows", f"{profile['duplicate_rows']:,} ({profile['duplicate_pct']}%)", dup_color))
        cards_row.addWidget(_stat_card("Benford Flags", str(len(profile["benford_findings"])),
                                        Colors.DANGER if profile["benford_findings"] else Colors.TEXT_PRIMARY))
        layout.addLayout(cards_row)

        # Column profile table
        col_group = QGroupBox("Column Profile")
        col_layout = QVBoxLayout(col_group)
        table = QTableWidget()
        headers = ["Column", "Type", "Missing", "Missing %", "Unique", "Unique %", "Outliers", "Outliers %"]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        columns = profile["columns"]
        table.setRowCount(len(columns))
        for r, c in enumerate(columns):
            table.setItem(r, 0, QTableWidgetItem(c["column"]))
            table.setItem(r, 1, QTableWidgetItem(c["dtype"]))
            table.setItem(r, 2, QTableWidgetItem(f"{c['missing']:,}"))
            table.setItem(r, 3, QTableWidgetItem(f"{c['missing_pct']}%"))
            table.setItem(r, 4, QTableWidgetItem(f"{c['unique']:,}"))
            table.setItem(r, 5, QTableWidgetItem(f"{c['unique_pct']}%"))
            table.setItem(r, 6, QTableWidgetItem(f"{c['outlier_count']:,}" if c["is_numeric"] else "-"))
            table.setItem(r, 7, QTableWidgetItem(f"{c['outlier_pct']}%" if c["is_numeric"] else "-"))
        table.setMinimumHeight(min(300, 40 + 28 * len(columns)))
        col_layout.addWidget(table)
        layout.addWidget(col_group)

        # Benford findings
        if profile["benford_findings"]:
            benford_group = QGroupBox("⚠ Benford's Law - Possible Non-Conformity")
            benford_layout = QVBoxLayout(benford_group)
            benford_layout.addWidget(QLabel(
                "These numeric columns' leading-digit distribution deviates from Benford's expected "
                "pattern more than Nigrini's acceptable threshold (Mean Absolute Deviation > 0.012) - "
                "worth a closer look, not proof of an issue on its own."
            ))
            for f in profile["benford_findings"]:
                benford_layout.addWidget(QLabel(f"  • {f['column']}: MAD = {f['mad']} (n={f['n']:,})"))
            layout.addWidget(benford_group)

        # Correlations
        if profile["correlations"]:
            corr_group = QGroupBox("Highly Correlated Column Pairs (|r| ≥ 0.8)")
            corr_layout = QVBoxLayout(corr_group)
            for c in profile["correlations"]:
                corr_layout.addWidget(QLabel(f"  • {c['column_a']} ↔ {c['column_b']}: r = {c['correlation']}"))
            layout.addWidget(corr_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)
