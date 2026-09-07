"""
Pivot Table Dialog for CAATmaster
Pivot table creation with drag-drop column selection
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QCheckBox, QGroupBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame, QScrollArea,
    QWidget, QApplication, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QPixmap, QFont, QColor

from ..components.common_modals import BaseModal, PreviewTable, create_primary_button
from ..theme import Colors


class DraggableColumnLabel(QLabel):
    """
    Column label that can be dragged to drop zones
    """

    def __init__(self, column_name: str, parent=None):
        super().__init__(column_name, parent)
        self.setFixedHeight(30)
        self.setFixedWidth(120)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.ACCENT_SOFT};
                border: 1px solid {Colors.ACCENT};
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
            }}
            QLabel:hover {{
                background-color: {Colors.BG_SELECTED_STRONG};
            }}
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

    _IDLE_STYLE = f"""
        QFrame {{
            background-color: {Colors.BG_SECONDARY};
            border: 2px dashed {Colors.BORDER_STRONG};
            border-radius: 4px;
            min-height: 60px;
        }}
    """
    _DRAG_OVER_STYLE = f"""
        QFrame {{
            background-color: {Colors.ACCENT_SOFT};
            border: 2px dashed {Colors.ACCENT};
            border-radius: 4px;
            min-height: 60px;
        }}
    """

    def _setup_ui(self):
        self.setAcceptDrops(True)
        self.setStyleSheet(self._IDLE_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.title_label = QLabel(self.title)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                font-weight: bold;
                color: {Colors.TEXT_SECONDARY};
                font-size: 11px;
            }}
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
            self.setStyleSheet(self._DRAG_OVER_STYLE)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._IDLE_STYLE)

    def dropEvent(self, event):
        column_name = event.mimeData().text()
        if column_name and column_name not in self.columns:
            self.columns.append(column_name)
            self._add_column_label(column_name)

        self.setStyleSheet(self._IDLE_STYLE)

    def _add_column_label(self, column_name: str):
        """Add a column label to the drop zone"""
        label = QLabel(column_name)
        label.setFixedHeight(24)
        label.setFixedWidth(100)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.ACCENT};
                color: {Colors.TEXT_ON_ACCENT};
                border-radius: 12px;
                padding: 2px 8px;
                font-size: 11px;
            }}
        """)
        self.columns_layout.addWidget(label)

        # Add remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.DANGER};
                color: {Colors.TEXT_ON_ACCENT};
                border-radius: 10px;
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Colors.DANGER_HOVER};
            }}
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
    Pivot Table dialog with drag-drop column selection
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
        zones_layout.addWidget(self.values_zone, 1, 0, 1, 2)

        top_layout.addWidget(zones_frame, 2)

        splitter.addWidget(top_frame)

        # Middle section: Aggregation options
        agg_frame = QGroupBox("Value Field Settings")
        agg_layout = QHBoxLayout(agg_frame)

        agg_layout.addWidget(QLabel("Aggregation:"))
        self.agg_combo = QComboBox()
        self.agg_combo.addItems(["Sum", "Count", "Average", "Min", "Max", "Count Rows", "Distinct Count"])
        agg_layout.addWidget(self.agg_combo)

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

        self.create_btn = create_primary_button("Create Pivot")
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
            placeholder.setStyleSheet(f"color: {Colors.TEXT_TERTIARY};")
            self.columns_grid.addWidget(placeholder, 0, 0, 1, 3)

    def _on_search_changed(self, text):
        """Filter columns based on search text"""
        self._populate_columns(text)

    def get_parameters(self) -> dict:
        """The parameters sent to DataProcessor.pivot(), both for this
        dialog's own preview() below and, via
        TransformView.apply_transformation, for the applied operation.
        Key names match pivot()'s signature exactly ("index"/"aggregate",
        not "rows"/"aggregation")."""
        return {
            "index": self.rows_zone.get_columns(),
            "columns": self.columns_zone.get_columns(),
            "values": self.values_zone.get_columns(),
            "aggregate": self.agg_combo.currentText().lower().replace(" ", "_"),
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
        """Generate a preview by calling the same DataProcessor.pivot()
        that Run/Apply uses."""
        from core.data_processor import DataProcessor

        try:
            params = self.get_parameters()
            index = params["index"]
            values = params["values"]

            if not index or not values:
                self.preview_table.clear()
                return

            pivot_df = DataProcessor().pivot(
                self.original_df, index=index, columns=params["columns"],
                values=values, aggregate=params["aggregate"],
            )
            self.preview_table.load_dataframe(pivot_df.head(100))

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

