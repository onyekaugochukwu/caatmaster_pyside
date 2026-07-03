"""
Column Quality / Distribution / Profile dialog.

Column quality bars, distribution charts, and profile detail are really one
feature seen from different angles. This dialog implements all three as tabs
over the same computed stats, rather than three disconnected stubs.
"""
import polars as pl
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QLabel, QListWidget, QListWidgetItem,
    QSplitter, QSizePolicy
)
from PySide6.QtGui import QPainter, QColor

from gui.theme import Colors

try:
    import pyqtgraph as pg
    _HAS_PYQTGRAPH = True
except ImportError:
    _HAS_PYQTGRAPH = False


def compute_column_quality(df: pl.DataFrame, col: str) -> dict:
    """Valid vs. empty percentage for a column. Empty = null or blank string.

    Note: this doesn't report a separate "error" bucket — that would require
    per-cell type-conversion failure tracking from the transformation
    pipeline, which isn't captured today. Valid/empty is real signal from
    what we actually have; a fabricated error count would not be.
    """
    total = df.height
    if total == 0:
        return {"valid_pct": 0.0, "empty_pct": 0.0, "distinct": 0}

    series = df[col]
    empty_count = series.null_count()
    if series.dtype == pl.Utf8:
        try:
            empty_count = df.select(
                (pl.col(col).is_null() | (pl.col(col).str.strip_chars() == "")).sum()
            ).item()
        except Exception:
            pass

    valid_count = total - empty_count
    try:
        distinct = series.n_unique()
    except Exception:
        distinct = 0

    return {
        "valid_pct": 100.0 * valid_count / total,
        "empty_pct": 100.0 * empty_count / total,
        "distinct": distinct,
    }


def compute_column_profile(df: pl.DataFrame, col: str) -> dict:
    """Detailed stats for one column, split by numeric vs. categorical/text."""
    series = df[col]
    total = df.height
    null_count = series.null_count()
    is_numeric = series.dtype in (
        pl.Int8, pl.Int16, pl.Int32, pl.Int64,
        pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
        pl.Float32, pl.Float64,
    )

    profile = {
        "dtype": str(series.dtype),
        "count": total,
        "nulls": null_count,
        "distinct": series.n_unique() if total else 0,
        "is_numeric": is_numeric,
    }

    if is_numeric:
        non_null = series.drop_nulls()
        if len(non_null) > 0:
            profile.update({
                "min": non_null.min(),
                "max": non_null.max(),
                "mean": non_null.mean(),
                "std": non_null.std(),
            })
            values = non_null.to_numpy()
            counts, edges = np.histogram(values, bins=min(10, max(1, len(np.unique(values)))))
            labels = [f"{edges[i]:.2g}–{edges[i+1]:.2g}" for i in range(len(counts))]
            profile["histogram"] = (labels, counts.tolist())
    else:
        non_null = series.drop_nulls().cast(pl.Utf8, strict=False)
        if len(non_null) > 0:
            vc = (
                non_null.value_counts(sort=True)
                .head(15)
            )
            labels = vc[col if col in vc.columns else vc.columns[0]].cast(pl.Utf8).to_list()
            counts = vc[vc.columns[-1]].to_list()
            profile["histogram"] = (labels, counts)

    return profile


class QualityBar(QWidget):
    """Small horizontal stacked bar: valid (green) vs. empty (gray)."""

    def __init__(self, valid_pct: float, empty_pct: float, parent=None):
        super().__init__(parent)
        self.valid_pct = valid_pct
        self.empty_pct = empty_pct
        self.setFixedHeight(16)
        self.setMinimumWidth(80)
        self.setToolTip(f"Valid: {valid_pct:.1f}%   Empty: {empty_pct:.1f}%")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        width = rect.width()

        valid_width = int(width * self.valid_pct / 100.0)
        painter.fillRect(0, 0, valid_width, rect.height(), QColor(Colors.QUALITY_VALID))
        painter.fillRect(valid_width, 0, width - valid_width, rect.height(), QColor(Colors.QUALITY_EMPTY))


class ColumnProfileDialog(QDialog):
    """Column Quality / Distribution / Profile — tabs over the same dataset."""

    def __init__(self, df: pl.DataFrame, parent=None, selected_column: str = None, initial_tab: str = "quality"):
        super().__init__(parent)
        self.df = df
        self.setWindowTitle("Column Profile")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._build_quality_tab(), "Column Quality")
        self.tabs.addTab(self._build_profile_tab(selected_column), "Column Profile & Distribution")

        self.tabs.setCurrentIndex(1 if initial_tab == "profile" else 0)

    # ------------------------------------------------------------------
    # Quality tab: one row per column with a quality bar
    # ------------------------------------------------------------------
    def _build_quality_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(f"{self.df.height:,} rows × {len(self.df.columns)} columns")
        info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; padding: 4px;")
        layout.addWidget(info)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Column", "Quality", "Valid %", "Distinct"])
        table.setRowCount(len(self.df.columns))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        table.setColumnWidth(1, 140)

        for row, col in enumerate(self.df.columns):
            quality = compute_column_quality(self.df, col)
            table.setItem(row, 0, QTableWidgetItem(col))
            table.setCellWidget(row, 1, QualityBar(quality["valid_pct"], quality["empty_pct"]))
            table.setItem(row, 2, QTableWidgetItem(f"{quality['valid_pct']:.1f}%"))
            table.setItem(row, 3, QTableWidgetItem(f"{quality['distinct']:,}"))

        layout.addWidget(table)
        return widget

    # ------------------------------------------------------------------
    # Profile tab: column list + detail/distribution for the selection
    # ------------------------------------------------------------------
    def _build_profile_tab(self, selected_column: str = None) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)

        self.column_list = QListWidget()
        self.column_list.setFixedWidth(200)
        for col in self.df.columns:
            self.column_list.addItem(QListWidgetItem(col))
        self.column_list.currentTextChanged.connect(self._on_column_selected)
        layout.addWidget(self.column_list)

        self.detail_container = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_container)
        layout.addWidget(self.detail_container, 1)

        if selected_column and selected_column in self.df.columns:
            self.column_list.setCurrentRow(self.df.columns.index(selected_column))
        elif self.df.columns:
            self.column_list.setCurrentRow(0)

        return widget

    def _on_column_selected(self, col: str):
        # Clear previous detail widgets
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not col:
            return

        profile = compute_column_profile(self.df, col)

        header = QLabel(f"{col}  —  {profile['dtype']}")
        header.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {Colors.TEXT_PRIMARY};")
        self.detail_layout.addWidget(header)

        stats_lines = [
            f"Count: {profile['count']:,}",
            f"Nulls: {profile['nulls']:,}",
            f"Distinct: {profile['distinct']:,}",
        ]
        if profile["is_numeric"] and "mean" in profile:
            stats_lines += [
                f"Min: {profile['min']:.4g}",
                f"Max: {profile['max']:.4g}",
                f"Mean: {profile['mean']:.4g}",
                f"Std Dev: {profile['std']:.4g}" if profile['std'] is not None else "Std Dev: n/a",
            ]
        stats_label = QLabel("   •   ".join(stats_lines))
        stats_label.setWordWrap(True)
        stats_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; padding: 8px 0;")
        self.detail_layout.addWidget(stats_label)

        if "histogram" in profile:
            self.detail_layout.addWidget(self._build_chart(*profile["histogram"]))
        else:
            self.detail_layout.addWidget(QLabel("No distribution available for this column."))

        self.detail_layout.addStretch()

    def _build_chart(self, labels, counts) -> QWidget:
        if not _HAS_PYQTGRAPH or not labels:
            fallback = QLabel("\n".join(f"{l}: {c:,}" for l, c in zip(labels, counts)))
            fallback.setStyleSheet(f"color: {Colors.TEXT_PRIMARY};")
            return fallback

        plot = pg.PlotWidget(background=Colors.BG_PRIMARY)
        plot.setMinimumHeight(240)
        plot.showGrid(x=False, y=True, alpha=0.2)
        x = list(range(len(counts)))
        bars = pg.BarGraphItem(x=x, height=counts, width=0.6, brush=Colors.ACCENT)
        plot.addItem(bars)
        axis = plot.getAxis("bottom")
        axis.setTicks([[(i, str(l)) for i, l in enumerate(labels)]])
        plot.getPlotItem().getAxis("bottom").setStyle(tickTextOffset=8)
        return plot
