"""
Excel-style column filter dropdowns for the data grid.

A small filter icon is drawn at the right edge of each header section;
clicking it opens a checklist of the column's unique values (with a search
box), matching Excel's AutoFilter — discoverable without needing to already
know to right-click the header.
"""
from typing import List, Optional

import qtawesome as qta
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtWidgets import (
    QHeaderView, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QCheckBox, QLabel
)
from PySide6.QtGui import QPainter

from gui.theme import Colors

ICON_ZONE_WIDTH = 20
BLANKS_LABEL = "(Blanks)"


class FilterableHeaderView(QHeaderView):
    """Horizontal header that draws a small filter icon per section and
    emits `filterButtonClicked(column_index)` when it's clicked, instead of
    treating that click as a resize/sort drag."""

    filterButtonClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setSectionsClickable(True)
        self._filtered_columns = set()  # logical indices with an active filter

    def set_filtered_columns(self, indices):
        self._filtered_columns = set(indices)
        self.viewport().update()

    def _icon_rect(self, logical_index: int) -> QRect:
        section_rect = QRect(self.sectionViewportPosition(logical_index), 0,
                              self.sectionSize(logical_index), self.height())
        return QRect(section_rect.right() - ICON_ZONE_WIDTH, 0, ICON_ZONE_WIDTH, section_rect.height())

    def paintSection(self, painter: QPainter, rect: QRect, logicalIndex: int):
        super().paintSection(painter, rect, logicalIndex)
        color = Colors.ACCENT if logicalIndex in self._filtered_columns else Colors.TEXT_TERTIARY
        icon = qta.icon("fa5s.filter", color=color)
        icon_rect = QRect(rect.right() - ICON_ZONE_WIDTH + 4, rect.top() + (rect.height() - 12) // 2, 12, 12)
        icon.paint(painter, icon_rect)

    def mousePressEvent(self, event):
        logical_index = self.logicalIndexAt(event.pos())
        if logical_index >= 0:
            icon_rect = self._icon_rect(logical_index)
            if icon_rect.contains(event.pos()):
                self.filterButtonClicked.emit(logical_index)
                event.accept()
                return
        super().mousePressEvent(event)


class ColumnFilterPopup(QWidget):
    """Checklist popup for one column's unique values, Excel AutoFilter style."""

    filtersApplied = Signal(str, set)  # column_name, selected values (or None = clear filter)

    def __init__(self, column_name: str, values: List[str], selected: Optional[set], parent=None):
        super().__init__(parent, Qt.Popup)
        self.column_name = column_name
        self.all_values = values
        self.setFixedWidth(240)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_STRONG};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel(f"Filter: {column_name}")
        header.setStyleSheet(f"font-weight: 600; color: {Colors.TEXT_PRIMARY}; border: none;")
        layout.addWidget(header)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search values...")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        select_row = QHBoxLayout()
        self.select_all_cb = QCheckBox("Select All")
        self.select_all_cb.setChecked(selected is None)
        self.select_all_cb.stateChanged.connect(self._on_select_all)
        select_row.addWidget(self.select_all_cb)
        layout.addLayout(select_row)

        self.value_list = QListWidget()
        self.value_list.setMaximumHeight(220)
        self.value_list.setStyleSheet("border: none;")
        active = selected if selected is not None else set(values)
        for v in values:
            item = QListWidgetItem(v)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if v in active else Qt.Unchecked)
            self.value_list.addItem(item)
        layout.addWidget(self.value_list)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Clear Filter")
        clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("PrimaryButton")
        ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _on_search(self, text: str):
        text = text.lower()
        for i in range(self.value_list.count()):
            item = self.value_list.item(i)
            item.setHidden(text not in item.text().lower())

    def _on_select_all(self, state):
        # stateChanged passes 0 (unchecked) / 1 (partial) / 2 (checked)
        check_state = Qt.Checked if int(state) != 0 else Qt.Unchecked
        for i in range(self.value_list.count()):
            self.value_list.item(i).setCheckState(check_state)

    def _on_clear(self):
        self.filtersApplied.emit(self.column_name, None)
        self.close()

    def _on_ok(self):
        selected = {
            self.value_list.item(i).text()
            for i in range(self.value_list.count())
            if self.value_list.item(i).checkState() == Qt.Checked
        }
        if len(selected) == len(self.all_values):
            # Everything selected == no filter
            self.filtersApplied.emit(self.column_name, None)
        else:
            self.filtersApplied.emit(self.column_name, selected)
        self.close()

    def show_at(self, global_pos: QPoint):
        self.move(global_pos)
        self.show()
