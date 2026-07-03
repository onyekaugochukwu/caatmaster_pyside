"""
Applied Steps panel — Power Query style: a persistent side panel (not tied
to a single page) showing the active dataset's transformation pipeline,
with per-step enable/disable and timing.

This widget only renders steps and emits signals — TransformView still owns
the actual TransformationPipeline and all mutation logic (undo/clear/toggle),
the same way it did before this panel was pulled out into something shared
across pages. That keeps this component a thin, reusable view.
"""
import qtawesome as qta
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QCheckBox, QGroupBox
)

from gui.theme import Colors


class AppliedStepsPanel(QWidget):
    """Persistent Applied Steps list + toolbar, shared across every
    data-workspace page (Data, Transform, SQL, Visualizations, Reports,
    Query) so it never disappears just because you switched pages."""

    undoRequested = Signal()
    clearRequested = Signal()
    exportRequested = Signal()
    stepToggled = Signal(int, bool)  # step_number (1-based), enabled
    stepSelectionChanged = Signal(object)  # step_number (1-based) or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AppliedStepsPanel")
        self.setFixedWidth(300)
        self._pipeline = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        self.undo_btn = QPushButton(" Undo")
        self.undo_btn.setIcon(qta.icon("fa5s.undo", color=Colors.TEXT_PRIMARY))
        self.undo_btn.setFixedHeight(28)
        self.undo_btn.clicked.connect(self.undoRequested.emit)
        toolbar_layout.addWidget(self.undo_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setIcon(qta.icon("fa5s.times-circle", color=Colors.DANGER))
        self.clear_btn.setFixedHeight(28)
        self.clear_btn.clicked.connect(self.clearRequested.emit)
        toolbar_layout.addWidget(self.clear_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.setIcon(qta.icon("fa5s.file-export", color=Colors.TEXT_PRIMARY))
        self.export_btn.setFixedHeight(28)
        self.export_btn.clicked.connect(self.exportRequested.emit)
        toolbar_layout.addWidget(self.export_btn)

        layout.addWidget(toolbar)

        steps_group = QGroupBox("Applied Steps")
        steps_layout = QVBoxLayout(steps_group)
        self.steps_list_widget = QListWidget()
        self.steps_list_widget.setObjectName("StepsList")
        self.steps_list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        steps_layout.addWidget(self.steps_list_widget)
        layout.addWidget(steps_group, 1)

    def set_pipeline(self, pipeline):
        """Bind to a (possibly different) pipeline and re-render from it."""
        self._pipeline = pipeline
        self.refresh()

    def refresh(self):
        """Rebuild the list from the currently bound pipeline's steps."""
        self.steps_list_widget.clear()
        if not self._pipeline:
            return
        from core.operation_registry import OPERATION_REGISTRY
        for i, step in enumerate(self._pipeline.get_steps(), start=1):
            self._add_step_item(step, i)

    def _add_step_item(self, step, index: int):
        from core.operation_registry import OPERATION_REGISTRY
        op_name = OPERATION_REGISTRY.get(step.operation_id, {}).get('display_name', step.operation_id)
        step_text = f"{index}. {op_name}"

        # No text/icon on the item itself — the row widget below renders
        # everything, so the item must stay empty or its own delegate paint
        # shows through as overlapping text underneath the widget.
        item = QListWidgetItem()
        item.setData(Qt.UserRole, index)
        item.setSizeHint(QSize(0, 30))
        self.steps_list_widget.addItem(item)

        row = QWidget()
        row.setAutoFillBackground(True)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(6, 2, 6, 2)
        row_layout.setSpacing(6)

        checkbox = QCheckBox()
        checkbox.setChecked(step.enabled)
        checkbox.setToolTip("Disable this step without deleting it")
        checkbox.toggled.connect(lambda checked, idx=index: self.stepToggled.emit(idx, checked))
        row_layout.addWidget(checkbox)

        label = QLabel(step_text)
        if not step.enabled:
            label.setStyleSheet(f"color: {Colors.TEXT_DISABLED};")
        row_layout.addWidget(label, 1)

        if step.execution_time is not None:
            time_label = QLabel(f"{step.execution_time * 1000:.0f} ms")
            time_label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 10px;")
            row_layout.addWidget(time_label)

        self.steps_list_widget.setItemWidget(item, row)

    def _on_selection_changed(self):
        selected = self.steps_list_widget.selectedItems()
        if not selected:
            self.stepSelectionChanged.emit(None)
            return
        step_number = selected[0].data(Qt.UserRole)
        self.stepSelectionChanged.emit(step_number)
