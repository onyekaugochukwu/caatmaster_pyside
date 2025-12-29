"""
Pivot Table Dialog for CAATmaster
Excel-style pivot table creation with drag-drop column selection
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QCheckBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame, QScrollArea,
    QWidget, QApplication
)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QPixmap, QFont, QColor

from ..components.common_modals import BaseModal, PreviewTable


class DraggableColumnLabel(QLabel):
    """
    Column label that can be dragged to drop zones
    """

    def __init__(self, column_name: str, parent=None):
        super().__init__(column_name, parent)
        self.setFixedHeight(30)
        self.setFixedWidth(120)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #e3f2fd;
                border: 1px solid #2196f3;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
            }
            QLabel:hover {
                background-color: #bbdefb;
            }
        """)
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setText(self.text())
            drag.setMimeData(mime_data)
            pixmap = self.grab()
            drag.setPixmap(pixmap.scaled(100, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            drag.setHotSpot(event.pos())
            drag.exec(Qt.CopyAction)


class DropZone(QFrame):
    """
    Drop zone for columns in pivot table dialog
    """

    columnDropped = Signal(str)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.columns = []
        self._setup_ui()

    def _setup_ui(self):
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 2px dashed #bdbdbd;
                border-radius: 4px;
                min-height: 60px;
            }
            QFrame:dragEnter {
                background-color: #e3f2fd;
                border-color: #2196f3;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #666;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.title_label)

        self.columns_widget = QWidget()
        self.columns_layout = QHBoxLayout(self.columns_widget)
        self.columns_layout.setContentsMargins(2, 2, 2, 2)
        self.columns_layout.setSpacing(4)
        layout.addWidget(self.columns_widget)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QFrame {
                    background-color: #e3f2fd;
                    border: 2px dashed #2196f3;
                    border-radius: 4px;
                    min-height: 60px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 2px dashed #bdbdbd;
                border-radius: 4px;
                min-height: 60px;
            }
        """)

    def dropEvent(self, event):
        column_name = event.mimeData().text()
        if column_name and column_name not in self.columns:
            self.columns.append(column_name)
            self._add_column_label(column_name)

        self.setStyleSheet("""
            QFrame {
                background-color: #f5f5f5;
                border: 2px dashed #bdbdbd;
                border-radius: 4px;
                min-height: 60px;
            }
        """)

    def _add_column_label(self, column_name: str):
        """Add a column label to the drop zone"""
        label = QLabel(column_name)
        label.setFixedHeight(24)
        label.setFixedWidth(100)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                background-color: #2196f3;
                color: white;
                border-radius: 12px;
                padding: 2px 8px;
                font-size: 11px;
            }
        """)
        self.columns_layout.addWidget(label)

        # Add remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border-radius: 10px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        remove_btn.clicked.connect(lambda: self._remove_column(column_name, label, remove_btn))
        self.columns_layout.addWidget(remove_btn)

    def _remove_column(self, column_name: str, label: QLabel, btn: QPushButton):
        """Remove a column from the drop zone"""
        if column_name in self.columns:
            self.columns.remove(column_name)
        label.deleteLater()
        btn.deleteLater()

    def get_columns(self) -> List[str]:
        return self.columns.copy()

    def clear(self):
        """Clear all columns"""
        self.columns = []
        for i in reversed(range(self.columns_layout.count())):
            item = self.columns_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()


class PivotTableDialog(BaseModal):
    """
    Excel-style Pivot Table dialog with drag-drop column selection
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Create Pivot Table", dataframe, parent)
        self.setMinimumSize(900, 700)

    def _setup_ui(self):
        """Setup the pivot table dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Main splitter
        splitter = QSplitter(Qt.Vertical)

        # Top section: Column selection
        top_frame = QFrame()
        top_layout = QHBoxLayout(top_frame)

        # Left: Available columns
        cols_group = QGroupBox("Available Columns")
        cols_layout = QVBoxLayout(cols_group)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search columns...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        cols_layout.addWidget(self.search_edit)

        self.columns_scroll = QScrollArea()
        self.columns_scroll.setWidgetResizable(True)
        self.columns_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.columns_widget = QWidget()
        self.columns_grid = QGridLayout(self.columns_widget)
        self.columns_grid.setSpacing(4)
        self.columns_scroll.setWidget(self.columns_widget)
        cols_layout.addWidget(self.columns_scroll)

        top_layout.addWidget(cols_group, 1)

        # Middle: Drop zones
        zones_frame = QFrame()
        zones_layout = QGridLayout(zones_frame)

        # Rows drop zone
        self.rows_zone = DropZone("ROWS (Drag columns here)")
        zones_layout.addWidget(self.rows_zone, 0, 0)

        # Columns drop zone
        self.columns_zone = DropZone("COLUMNS (Drag columns here)")
        zones_layout.addWidget(self.columns_zone, 0, 1)

        # Values drop zone
        self.values_zone = DropZone("VALUES (Drag columns here)")
        zones_layout.addWidget(self.values_zone, 1, 0)

        # Filters drop zone
        self.filters_zone = DropZone("FILTERS (Drag columns here)")
        zones_layout.addWidget(self.filters_zone, 1, 1)

        top_layout.addWidget(zones_frame, 2)

        splitter.addWidget(top_frame)

        # Middle section: Aggregation options
        agg_frame = QGroupBox("Value Field Settings")
        agg_layout = QHBoxLayout(agg_frame)

        agg_layout.addWidget(QLabel("Aggregation:"))
        self.agg_combo = QComboBox()
        self.agg_combo.addItems(["Sum", "Count", "Average", "Min", "Max", "Count Rows", "Distinct Count"])
        agg_layout.addWidget(self.agg_combo)

        agg_layout.addWidget(QLabel("Show Values As:"))
        self.show_as_combo = QComboBox()
        self.show_as_combo.addItems([
            "No Calculation",
            "% of Grand Total",
            "% of Row Total",
            "% of Column Total",
            "% of Parent Row",
            "% of Parent Column",
            "Running Total"
        ])
        agg_layout.addWidget(self.show_as_combo)

        agg_layout.addStretch()
        splitter.addWidget(agg_frame)

        # Bottom section: Preview
        preview_group = QGroupBox("Preview (Top 10 Rows)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        splitter.addWidget(preview_group)

        # Set splitter sizes
        splitter.setSizes([300, 80, 250])

        layout.addWidget(splitter)

        # Button row
        btn_layout = QHBoxLayout()

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Update Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.create_btn = QPushButton("Create Pivot")
        self.create_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.create_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.create_btn)

        layout.addLayout(btn_layout)

        # Populate available columns
        self._populate_columns()

    def _populate_columns(self, filter_text: str = ""):
        """Populate the available columns grid"""
        # Clear existing
        for i in reversed(range(self.columns_grid.count())):
            item = self.columns_grid.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        # Add columns
        columns = self.dataframe.columns
        filter_text = filter_text.lower()

        filtered_cols = [c for c in columns if filter_text in c.lower()]

        for i, col in enumerate(filtered_cols):
            label = DraggableColumnLabel(col)
            self.columns_grid.addWidget(label, i // 3, i % 3)

        # Add placeholder if no columns
        if not filtered_cols:
            placeholder = QLabel("No matching columns")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #999;")
            self.columns_grid.addWidget(placeholder, 0, 0, 1, 3)

    def _on_search_changed(self, text):
        """Filter columns based on search text"""
        self._populate_columns(text)

    def get_parameters(self) -> dict:
        """Get the pivot table parameters"""
        return {
            "rows": self.rows_zone.get_columns(),
            "columns": self.columns_zone.get_columns(),
            "values": self.values_zone.get_columns(),
            "filters": self.filters_zone.get_columns(),
            "aggregation": self.agg_combo.currentText().lower().replace(" ", "_"),
            "show_as": self.show_as_combo.currentText().lower().replace(" ", "_").replace("%", "pct"),
        }

    def validate(self) -> bool:
        """Validate that required fields are filled"""
        rows = self.rows_zone.get_columns()
        values = self.values_zone.get_columns()

        if not rows:
            QMessageBox.warning(self, "Validation Error",
                              "Please drag at least one column to the ROWS zone.")
            return False

        if not values:
            QMessageBox.warning(self, "Validation Error",
                              "Please drag at least one column to the VALUES zone.")
            return False

        return True

    def preview(self):
        """Generate preview of pivot table"""
        try:
            params = self.get_parameters()
            rows = params["rows"]
            columns = params["columns"]
            values = params["values"]
            agg = params["aggregation"]

            if not rows or not values:
                self.preview_table.clear()
                return

            # Build pivot table
            if columns:
                # Pivot with column headers
                pivot_df = self.original_df.pivot(
                    values=values[0],
                    index=rows,
                    columns=columns[0],
                    aggregate_function=agg
                )
            else:
                # Simple aggregation without column headers
                agg_map = {
                    "sum": pl.sum,
                    "count": pl.count,
                    "average": pl.mean,
                    "min": pl.min,
                    "max": pl.max,
                    "count_rows": pl.count,
                    "distinct_count": pl.n_unique,
                }
                agg_func = agg_map.get(agg, pl.sum)
                pivot_df = self.original_df.group_by(rows).agg(
                    agg_func(values[0]).alias(f"{values[0]}_{agg}")
                )

            # Apply filters if any
            filters = params.get("filters", [])
            if filters:
                for f_col in filters:
                    # For preview, just show top rows
                    pivot_df = pivot_df.head(100)

            self.preview_table.load_dataframe(pivot_df)

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

    def get_pivot_result(self) -> pl.DataFrame:
        """Get the pivot table result after dialog is accepted"""
        params = self.get_parameters()
        rows = params["rows"]
        columns = params["columns"]
        values = params["values"]
        agg = params["aggregation"]

        if not rows or not values:
            return None

        try:
            if columns:
                pivot_df = self.original_df.pivot(
                    values=values[0],
                    index=rows,
                    columns=columns[0],
                    aggregate_function=agg
                )
            else:
                agg_map = {
                    "sum": pl.sum,
                    "count": pl.count,
                    "average": pl.mean,
                    "min": pl.min,
                    "max": pl.max,
                    "count_rows": pl.count,
                    "distinct_count": pl.n_unique,
                }
                agg_func = agg_map.get(agg, pl.sum)
                pivot_df = self.original_df.group_by(rows).agg(
                    agg_func(values[0]).alias(f"{values[0]}_{agg}")
                )

            return pivot_df

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create pivot table:\n{str(e)}")
            return None
