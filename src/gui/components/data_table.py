"""
Modern Data Table for CAATmaster
Virtualized table with sorting, filtering, and column operations
"""

from PySide6.QtCore import Qt, Signal, QSize, QTimer, QModelIndex, Property
from PySide6.QtGui import QFont, QColor, QPainter, QCursor, QIcon, QKeySequence, QAction
from PySide6.QtWidgets import (
    QWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QScrollArea, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QToolButton, QMenu,
    QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem
)

import polars as pl
from typing import Optional, List, Callable, Any
import numpy as np


class DataTableItem(QTableWidgetItem):
    """Custom table item with proper data handling"""

    def __init__(self, text: str = ""):
        super().__init__(str(text))
        self.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)

    def setData(self, role: int, value: Any):
        """Handle different data roles"""
        if role == Qt.DisplayRole or role == Qt.EditRole:
            super().setData(role, str(value) if value is not None else "")
        else:
            super().setData(role, value)


class ColumnHeaderDelegate(QStyledItemDelegate):
    """Custom delegate for column headers"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex
    ):
        """Paint the header with sort indicators"""
        # Draw background
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        # Get style
        style = QApplication.style()

        # Draw background
        style.drawControl(QStyle.CE_PanelHeader, opt, painter)

        # Draw text with sort indicator
        text = opt.text
        rect = opt.rect

        # Adjust for sort indicator
        icon_rect = QRect()
        sort_indicator = opt.sortIndicator

        if sort_indicator != 0:
            # Find the icon rect
            icon_rect = QRect(
                rect.right() - 20,
                rect.top() + (rect.height() - 16) // 2,
                16,
                16
            )
            rect.setRight(rect.right() - 24)

        # Draw text
        painter.save()
        font = QFont()
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        painter.setPen(opt.palette.color(QPalette.Text))
        painter.drawText(rect, Qt.AlignVCenter | Qt.AlignLeft, text)
        painter.restore()

        # Draw sort indicator
        if sort_indicator != 0:
            icon = QIcon.fromTheme(
                "arrow-up" if sort_indicator == QStyleOptionViewItem.Ascending
                else "arrow-down"
            )
            icon.paint(painter, icon_rect)


class ModernDataTable(QFrame):
    """
    Modern data table with virtualized scrolling, sorting, and filtering
    """

    # Signals
    cellClicked = Signal(int, int)
    cellDoubleClicked = Signal(int, int)
    columnHeaderClicked = Signal(int)
    columnContextMenu = Signal(str, int)  # column_name, column_index
    rowContextMenu = Signal(int)  # row_index
    filterChanged = Signal(str, str)  # column, filter_text
    sortingChanged = Signal(str, bool)  # column, ascending
    dataChanged = Signal()

    def __init__(
        self,
        parent: QWidget = None,
        max_rows: int = 10000,
        page_size: int = 100
    ):
        super().__init__(parent)
        self.setObjectName("DataPreviewContainer")

        self._max_rows = max_rows
        self._page_size = page_size
        self._current_page = 0
        self._total_rows = 0
        self._data: Optional[pl.DataFrame] = None
        self._filtered_data: Optional[pl.DataFrame] = None
        self._display_data: Optional[pl.DataFrame] = None
        self._sort_column: Optional[str] = None
        self._sort_ascending: bool = True
        self._column_types = {}

        self._setup_ui()

    def _setup_ui(self):
        """Setup the table UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with row count and pagination
        header = QFrame()
        header.setObjectName("DataPreviewHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        # Row count label
        self.row_count_label = QLabel("0 rows")
        self.row_count_label.setObjectName("RowCountLabel")
        header_layout.addWidget(self.row_count_label)

        header_layout.addStretch()

        # Search/filter input
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter...")
        self.filter_input.setObjectName("FilterInput")
        self.filter_input.setFixedWidth(200)
        self.filter_input.textChanged.connect(self._on_filter_changed)
        header_layout.addWidget(self.filter_input)

        # Refresh button
        refresh_btn = QToolButton()
        refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        refresh_btn.setToolTip("Refresh Data")
        refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(refresh_btn)

        layout.addWidget(header)

        # Table container
        table_container = QFrame()
        table_container.setObjectName("DataTableScrollArea")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        # Table widget
        self.table = QTableWidget()
        self.table.setObjectName("DataTableWidget")
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)

        # Configure header
        self.header = self.table.horizontalHeader()
        self.header.setSectionsClickable(True)
        self.header.sectionClicked.connect(self._on_column_header_click)
        self.header.setSectionResizeMode(QHeaderView.Interactive)
        self.header.setStretchLastSection(True)
        self.header.setDefaultSectionSize(120)
        self.header.setMinimumSectionSize(50)

        # Connect signals
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.customContextMenuRequested.connect(self._on_context_menu)

        table_layout.addWidget(self.table)

        layout.addWidget(table_container)

        # Footer with pagination
        footer = QFrame()
        footer.setStyleSheet("background: var(--color-bg-tertiary);")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 8, 12, 8)

        # Page info
        self.page_label = QLabel("Page 1 of 1")
        footer_layout.addWidget(self.page_label)

        footer_layout.addStretch()

        # Pagination controls
        self.prev_btn = QToolButton()
        self.prev_btn.setIcon(QIcon.fromTheme("go-previous"))
        self.prev_btn.setEnabled(False)
        self.prev_btn.clicked.connect(self._on_prev_page)
        footer_layout.addWidget(self.prev_btn)

        self.page_input = QLabel("1")
        footer_layout.addWidget(self.page_input)

        self.next_btn = QToolButton()
        self.next_btn.setIcon(QIcon.fromTheme("go-next"))
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._on_next_page)
        footer_layout.addWidget(self.next_btn)

        layout.addWidget(footer)

        # Initialize empty table
        self._clear_table()

    # =========================================================================
    # DATA MANAGEMENT
    # =========================================================================

    def set_dataframe(self, df: pl.DataFrame):
        """Set the data to display"""
        if df is None:
            self._clear_table()
            return

        self._data = df
        self._column_types = {col: dtype for col, dtype in df.schema.items()}
        self._total_rows = len(df)
        self._current_page = 0

        # Apply filter if any
        self._apply_filter()

    def _apply_filter(self):
        """Apply the current filter to the data"""
        filter_text = self.filter_input.text().strip()

        if filter_text and self._data is not None:
            try:
                # Simple text filter - checks all columns
                mask = pl.Series(
                    [False] * len(self._data),
                    name="filter"
                )

                for col in self._data.columns:
                    col_data = self._data[col].cast(pl.Utf8)
                    mask = mask | col_data.str.contains(filter_text, literal=False)

                self._filtered_data = self._data.filter(mask)
            except Exception:
                self._filtered_data = self._data
        else:
            self._filtered_data = self._data

        self._refresh_display()

    def _refresh_display(self):
        """Refresh the display with current data and settings"""
        if self._filtered_data is None:
            self._clear_table()
            return

        # Apply sorting
        if self._sort_column:
            try:
                ascending = self._sort_ascending
                self._display_data = self._filtered_data.sort(
                    self._sort_column,
                    descending=not ascending
                )
            except Exception:
                self._display_data = self._filtered_data
        else:
            self._display_data = self._filtered_data

        # Get visible rows (pagination)
        start = self._current_page * self._page_size
        end = min(start + self._page_size, len(self._display_data))
        page_data = self._display_data[start:end]

        # Update row count
        total_filtered = len(self._filtered_data)
        self.row_count_label.setText(
            f"{total_filtered:,} rows"
            + (f" of {len(self._data):,}" if self._data and total_filtered != len(self._data) else "")
        )

        # Populate table
        self._populate_table(page_data)

        # Update pagination
        self._update_pagination()

    def _populate_table(self, df: pl.DataFrame):
        """Populate the table with data from a DataFrame"""
        self.table.clear()

        if df is None or df.height == 0:
            self._clear_table()
            return

        rows = df.height
        cols = df.width

        self.table.setRowCount(rows)
        self.table.setColumnCount(cols)

        # Set column headers
        headers = df.columns
        self.table.setHorizontalHeaderLabels(headers)

        # Populate cells
        for r in range(rows):
            for c, col in enumerate(headers):
                value = df[col][r]
                display_value = "" if value is None else str(value)

                item = DataTableItem(display_value)
                self.table.setItem(r, c, item)

        # Adjust column widths
        for c in range(cols):
            self.header.setSectionResizeMode(c, QHeaderView.Interactive)

    def _clear_table(self):
        """Clear the table"""
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.row_count_label.setText("0 rows")
        self._update_pagination()

    def refresh_data(self):
        """Refresh the data display"""
        self._refresh_display()

    # =========================================================================
    # SORTING
    # =========================================================================

    def _on_column_header_click(self, index: int):
        """Handle column header click for sorting"""
        column = self.table.horizontalHeaderItem(index).text()

        # Toggle sort if same column, otherwise new column
        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True

        # Update header visual
        self._update_sort_indicators()

        # Emit signal
        self.sortingChanged.emit(column, self._sort_ascending)

        # Refresh
        self._refresh_display()

    def _update_sort_indicators(self):
        """Update sort indicators in headers"""
        for i in range(self.table.columnCount()):
            header_item = self.table.horizontalHeaderItem(i)
            if header_item.text() == self._sort_column:
                header_item.setData(
                    Qt.DecorationRole,
                    Qt.AlignRight | Qt.AlignVCenter
                )
            else:
                header_item.setData(Qt.DecorationRole, None)

    # =========================================================================
    # FILTERING
    # =========================================================================

    def _on_filter_changed(self, text: str):
        """Handle filter text change"""
        self._current_page = 0
        self._apply_filter()
        self.filterChanged.emit("", text)

    # =========================================================================
    # PAGINATION
    # =========================================================================

    def _update_pagination(self):
        """Update pagination controls"""
        if self._display_data is None:
            total_pages = 0
        else:
            total_pages = (len(self._display_data) + self._page_size - 1) // self._page_size

        current_page = self._current_page + 1

        self.page_label.setText(f"Page {current_page} of {max(1, total_pages)}")
        self.page_input.setText(str(current_page))

        self.prev_btn.setEnabled(current_page > 1)
        self.next_btn.setEnabled(current_page < total_pages)

    def _on_prev_page(self):
        """Go to previous page"""
        if self._current_page > 0:
            self._current_page -= 1
            self._refresh_display()

    def _on_next_page(self):
        """Go to next page"""
        if self._display_data is not None:
            total_pages = (len(self._display_data) + self._page_size - 1) // self._page_size
            if self._current_page < total_pages - 1:
                self._current_page += 1
                self._refresh_display()

    def set_page_size(self, size: int):
        """Set the number of rows per page"""
        self._page_size = size
        self._current_page = 0
        self._refresh_display()

    # =========================================================================
    # CONTEXT MENUS
    # =========================================================================

    def _on_cell_clicked(self, row: int, column: int):
        """Handle cell click"""
        self.cellClicked.emit(row, column)

    def _on_cell_double_clicked(self, row: int, column: int):
        """Handle cell double click"""
        self.cellDoubleClicked.emit(row, column)

    def _on_context_menu(self, pos):
        """Show context menu"""
        # Determine if we clicked on a header or cell
        from PySide6.QtGui import QContextMenuEvent

        # Get the widget under cursor
        widget = self.childAt(pos)

        if widget == self.header:
            # Column header context menu
            index = self.header.logicalIndexAt(pos)
            if index >= 0:
                column = self.table.horizontalHeaderItem(index).text()
                self._show_column_context_menu(pos, column, index)
        else:
            # Cell context menu
            row = self.table.rowAt(pos.y())
            if row >= 0:
                self._show_row_context_menu(pos, row)

    def _show_column_context_menu(self, pos, column: str, index: int):
        """Show context menu for column header"""
        from .context_menus import ColumnContextMenu

        menu = ColumnContextMenu(column, self)

        # Connect signals
        menu.transformRequested.connect(
            lambda op, params: self._handle_transform(op, params)
        )
        menu.sortRequested.connect(
            lambda col, asc: self.sortingChanged.emit(col, asc)
        )
        menu.pivotRequested.connect(
            lambda col: self.columnContextMenu.emit(col, index)
        )
        menu.unpivotRequested.connect(
            lambda col: self.columnContextMenu.emit(col, index)
        )

        menu.exec(pos)

    def _show_row_context_menu(self, pos, row: int):
        """Show context menu for row"""
        from .context_menus import RowContextMenu

        menu = RowContextMenu(self)
        menu.exec(pos)

    def _handle_transform(self, operation: str, params: dict):
        """Handle transformation request"""
        # Emit signal with operation and parameters
        self.dataChanged.emit()  # Placeholder

    # =========================================================================
    # EXPORT
    # =========================================================================

    def get_selected_data(self) -> Optional[pl.DataFrame]:
        """Get data from selected rows"""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows or self._display_data is None:
            return None

        # Convert to Polars
        rows = sorted(selected_rows)
        start = self._current_page * self._page_size
        adjusted_rows = [r + start for r in rows]

        return self._display_data[adjusted_rows]

    def get_all_data(self) -> Optional[pl.DataFrame]:
        """Get all displayed data (filtered and sorted)"""
        return self._display_data

    def get_column_names(self) -> List[str]:
        """Get list of column names"""
        return list(self._column_types.keys()) if self._column_types else []

    def get_column_type(self, column: str):
        """Get the type of a column"""
        return self._column_types.get(column)

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    def get_row_count(self) -> int:
        return self._total_rows

    def get_column_count(self) -> int:
        return len(self._column_types) if self._column_types else 0

    rowCount = Property(int, get_row_count)
    columnCount = Property(int, get_column_count)
