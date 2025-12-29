"""
Applied Steps Panel for CAATmaster
Power Query-style transformation pipeline UI
"""

from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QIcon, QPainter, QColor, QFont, QAction, QContextMenuEvent, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QListWidget,
    QListWidgetItem, QPushButton, QToolButton, QCheckBox, QMenu,
    QScrollArea, QInputDialog, QMessageBox
)

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class StepStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
    PROCESSING = "processing"


@dataclass
class TransformationStep:
    """Represents a single transformation step"""
    id: str
    name: str
    operation: str
    parameters: Dict[str, Any]
    enabled: bool = True
    status: StepStatus = StepStatus.PENDING
    output_columns: List[str] = field(default_factory=list)
    row_count: Optional[int] = None
    error_message: Optional[str] = None
    description: str = ""
    created_at: float = 0.0

    def __post_init__(self):
        self.id = self.id or str(uuid.uuid4())

    def copy(self) -> 'TransformationStep':
        """Create a copy of this step"""
        return TransformationStep(
            id=str(uuid.uuid4()),
            name=self.name,
            operation=self.operation,
            parameters=self.parameters.copy(),
            enabled=self.enabled,
            status=StepStatus.PENDING,
            output_columns=self.output_columns.copy(),
            row_count=self.row_count,
            error_message=self.error_message,
            description=self.description,
            created_at=self.created_at
        )


class StepItemWidget(QFrame):
    """Widget representing a single step in the list"""

    toggleRequested = Signal(str, bool)  # step_id, enabled
    editRequested = Signal(str)  # step_id
    deleteRequested = Signal(str)  # step_id
    duplicateRequested = Signal(str)  # step_id
    moveRequested = Signal(str, int)  # step_id, direction (-1 up, 1 down)

    def __init__(self, step: TransformationStep, parent: QWidget = None):
        super().__init__(parent)
        self.step = step
        self._setup_ui()
        self._update_state()

    def _setup_ui(self):
        """Setup the step item UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Toggle checkbox
        self.toggle = QCheckBox()
        self.toggle.setChecked(self.step.enabled)
        self.toggle.setFixedWidth(20)
        self.toggle.toggled.connect(
            lambda checked: self.toggleRequested.emit(self.step.id, checked)
        )
        layout.addWidget(self.toggle)

        # Step icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        layout.addWidget(self.icon_label)

        # Step info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Step name
        self.name_label = QLabel(self.step.name)
        self.name_label.setStyleSheet("font-weight: 500; font-size: 13px;")
        info_layout.addWidget(self.name_label)

        # Step description (operation type)
        self.type_label = QLabel(self.step.operation)
        self.type_label.setStyleSheet("font-size: 11px; color: var(--color-text-tertiary);")
        info_layout.addWidget(self.type_label)

        # Error message if any
        self.error_label = QLabel()
        self.error_label.setStyleSheet("font-size: 11px; color: var(--color-danger);")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        info_layout.addWidget(self.error_label)

        layout.addLayout(info_layout)

        layout.addStretch()

        # Status indicator
        self.status_label = QLabel()
        self.status_label.setFixedSize(16, 16)
        layout.addWidget(self.status_label)

        # Actions menu button
        self.menu_button = QToolButton()
        self.menu_button.setIcon(QIcon.fromTheme("application-menu"))
        self.menu_button.setFixedSize(24, 24)
        self.menu_button.setPopupMode(QToolButton.InstantPopup)
        self.menu_button.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.menu_button)

        # Setup context menu
        self._setup_menu()

    def _setup_menu(self):
        """Setup the actions menu"""
        menu = QMenu(self.menu_button)

        edit_action = QAction("Edit Step", self)
        edit_action.setIcon(QIcon.fromTheme("edit"))
        edit_action.triggered.connect(
            lambda: self.editRequested.emit(self.step.id)
        )
        menu.addAction(edit_action)

        duplicate_action = QAction("Duplicate", self)
        duplicate_action.setIcon(QIcon.fromTheme("edit-copy"))
        duplicate_action.triggered.connect(
            lambda: self.duplicateRequested.emit(self.step.id)
        )
        menu.addAction(duplicate_action)

        menu.addSeparator()

        move_up_action = QAction("Move Up", self)
        move_up_action.setIcon(QIcon.fromTheme("arrow-up"))
        move_up_action.triggered.connect(
            lambda: self.moveRequested.emit(self.step.id, -1)
        )
        menu.addAction(move_up_action)

        move_down_action = QAction("Move Down", self)
        move_down_action.setIcon(QIcon.fromTheme("arrow-down"))
        move_down_action.triggered.connect(
            lambda: self.moveRequested.emit(self.step.id, 1)
        )
        menu.addAction(move_down_action)

        menu.addSeparator()

        delete_action = QAction("Delete Step", self)
        delete_action.setIcon(QIcon.fromTheme("edit-delete"))
        delete_action.setStyleSheet("color: var(--color-danger);")
        delete_action.triggered.connect(
            lambda: self.deleteRequested.emit(self.step.id)
        )
        menu.addAction(delete_action)

        self.menu_button.setMenu(menu)

    def _update_state(self):
        """Update the visual state based on step status"""
        # Update icon based on operation type
        icon_map = {
            "calculate": "accessories-calculator",
            "filter": "funnel",
            "sort": "view-sort",
            "ml_predict": "chart",
            "ml_train": "train",
            "ai_enrich": "sparkles",
            "audit_flag": "flag",
            "aggregate": "view-group",
            "pivot": "view-column",
            "unpivot": "view-row",
            "join": "merge",
        }

        icon_name = icon_map.get(self.step.operation, "transform")
        self.icon_label.setPixmap(
            QIcon.fromTheme(icon_name).pixmap(20, 20)
        )

        # Update status indicator
        status_colors = {
            StepStatus.PENDING: QColor(113, 113, 122),  # muted
            StepStatus.PROCESSING: QColor(59, 130, 246),  # blue
            StepStatus.SUCCESS: QColor(34, 197, 94),  # green
            StepStatus.ERROR: QColor(239, 68, 68),  # red
        }

        color = status_colors.get(self.step.status, QColor(113, 113, 122))
        self.status_label.setPixmap(
            self._create_status_icon(color)
        )

        # Show error message if any
        if self.step.status == StepStatus.ERROR and self.step.error_message:
            self.error_label.setText(self.step.error_message)
            self.error_label.show()
        else:
            self.error_label.hide()

        # Update opacity if disabled
        self.setEnabled(self.step.enabled)
        self.setProperty("disabled", not self.step.enabled)
        self.style().unpolish(self)
        self.style().polish(self)

    def _create_status_icon(self, color: QColor) -> QPixmap:
        """Create a circular status icon"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(8, 8, 12, 12)
        painter.end()

        return pixmap

    def update_step(self, step: TransformationStep):
        """Update with new step data"""
        self.step = step
        self.toggle.setChecked(step.enabled)
        self._update_state()


class StepsListWidget(QListWidget):
    """Custom list widget for steps"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setSpacing(4)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def contextMenuEvent(self, event):
        """Handle context menu on the list"""
        item = self.itemAt(event.pos())
        if item:
            # Show context menu for the item
            pass  # Let the item widget handle it


class AppliedStepsPanel(QFrame):
    """
    Power Query-style applied steps panel
    Shows transformation pipeline with ability to add, edit, reorder, toggle steps
    """

    # Signals
    stepAdded = Signal(TransformationStep)
    stepRemoved = Signal(str)
    stepUpdated = Signal(TransformationStep)
    stepToggled = Signal(str, bool)
    stepReordered = Signal(str, int)  # step_id, new_index
    pipelineApplied = Signal()
    undoRequested = Signal()
    redoRequested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("StepsPanel")
        self._setup_ui()

        # State
        self._steps: List[TransformationStep] = []
        self._can_undo = False
        self._can_redo = False

    def _setup_ui(self):
        """Setup the panel UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setObjectName("StepsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Applied Steps")
        title.setObjectName("StepsTitle")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Add step button
        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(28, 28)
        self.add_button.setToolTip("Add Step")
        self.add_button.clicked.connect(self._on_add_step)
        header_layout.addWidget(self.add_button)

        layout.addWidget(header)

        # Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet("background: var(--color-bg-tertiary);")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(4)

        # Undo/Redo
        self.undo_btn = QToolButton()
        self.undo_btn.setIcon(QIcon.fromTheme("edit-undo"))
        self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self.undoRequested.emit)
        toolbar_layout.addWidget(self.undo_btn)

        self.redo_btn = QToolButton()
        self.redo_btn.setIcon(QIcon.fromTheme("edit-redo"))
        self.redo_btn.setToolTip("Redo (Ctrl+Shift+Z)")
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self.redoRequested.emit)
        toolbar_layout.addWidget(self.redo_btn)

        toolbar_layout.addStretch()

        # Apply button
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setObjectName("PrimaryButton")
        self.apply_btn.clicked.connect(self.pipelineApplied.emit)
        toolbar_layout.addWidget(self.apply_btn)

        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("SecondaryButton")
        self.clear_btn.clicked.connect(self._on_clear_all)
        toolbar_layout.addWidget(self.clear_btn)

        layout.addWidget(toolbar)

        # Steps list
        self.steps_list = QListWidget()
        self.steps_list.setObjectName("StepsList")
        self.steps_list.setFrameShape(QFrame.NoFrame)
        self.steps_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        layout.addWidget(self.steps_list)

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def add_step(self, step: TransformationStep):
        """Add a new step to the pipeline"""
        self._steps.append(step)
        self._insert_step_item(step)
        self._update_state()

    def remove_step(self, step_id: str):
        """Remove a step from the pipeline"""
        self._steps = [s for s in self._steps if s.id != step_id]

        # Remove from list widget
        for i in range(self.steps_list.count()):
            item = self.steps_list.item(i)
            widget = self.steps_list.itemWidget(item)
            if widget and widget.step.id == step_id:
                self.steps_list.takeItem(i)
                break

        self._update_state()

    def update_step(self, step: TransformationStep):
        """Update an existing step"""
        for i, s in enumerate(self._steps):
            if s.id == step.id:
                self._steps[i] = step
                break

        # Update list widget
        for i in range(self.steps_list.count()):
            item = self.steps_list.item(i)
            widget = self.steps_list.itemWidget(item)
            if widget and widget.step.id == step.id:
                widget.update_step(step)
                break

        self._update_state()

    def set_steps(self, steps: List[TransformationStep]):
        """Set all steps at once"""
        self._steps = steps.copy()
        self._refresh_list()

    def get_steps(self) -> List[TransformationStep]:
        """Get all steps"""
        return self._steps.copy()

    def get_enabled_steps(self) -> List[TransformationStep]:
        """Get only enabled steps"""
        return [s for s in self._steps if s.enabled]

    def clear_steps(self):
        """Clear all steps"""
        self._steps.clear()
        self.steps_list.clear()
        self._update_state()

    def set_undo_available(self, available: bool):
        """Set whether undo is available"""
        self._can_undo = available
        self.undo_btn.setEnabled(available)
        self.undo_btn.setIcon(
            QIcon.fromTheme("edit-undo") if available else QIcon.fromTheme("edit-undo")
        )

    def set_redo_available(self, available: bool):
        """Set whether redo is available"""
        self._can_redo = available
        self.redo_btn.setEnabled(available)

    def set_step_status(self, step_id: str, status: StepStatus, error_message: str = None):
        """Update step status"""
        for step in self._steps:
            if step.id == step_id:
                step.status = status
                step.error_message = error_message
                break

        # Update UI
        for i in range(self.steps_list.count()):
            item = self.steps_list.item(i)
            widget = self.steps_list.itemWidget(item)
            if widget and widget.step.id == step_id:
                widget.update_step(step)
                break

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    def _insert_step_item(self, step: TransformationStep):
        """Insert a step into the list widget"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(200, 60))

        widget = StepItemWidget(step)
        widget.toggleRequested.connect(self._on_toggle)
        widget.editRequested.connect(self._on_edit)
        widget.deleteRequested.connect(self._on_delete)
        widget.duplicateRequested.connect(self._on_duplicate)
        widget.moveRequested.connect(self._on_move)

        self.steps_list.addItem(item)
        self.steps_list.setItemWidget(item, widget)

    def _refresh_list(self):
        """Refresh the entire list"""
        self.steps_list.clear()
        for step in self._steps:
            self._insert_step_item(step)
        self._update_state()

    def _update_state(self):
        """Update overall state"""
        # Update step count
        total = len(self._steps)
        enabled = sum(1 for s in self._steps if s.enabled)

        # Could add a label showing "3 of 5 steps applied"
        pass

    def _on_add_step(self):
        """Handle add step button click"""
        # Emit signal for the main window to show a transformation dialog
        # This will be connected to the transformation dialog system
        from .context_menus import ColumnContextMenu
        # For now, just emit a signal that a new step is needed
        pass  # The main view should handle this

    def _on_toggle(self, step_id: str, enabled: bool):
        """Handle step toggle"""
        for step in self._steps:
            if step.id == step_id:
                step.enabled = enabled
                break
        self.stepToggled.emit(step_id, enabled)
        self._update_state()

    def _on_edit(self, step_id: str):
        """Handle step edit request"""
        for step in self._steps:
            if step.id == step_id:
                # Emit signal to edit the step
                # The parent should handle showing a dialog
                break

    def _on_delete(self, step_id: str):
        """Handle step delete request"""
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Step",
            "Are you sure you want to delete this step?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.remove_step(step_id)
            self.stepRemoved.emit(step_id)

    def _on_duplicate(self, step_id: str):
        """Handle step duplicate request"""
        for step in self._steps:
            if step.id == step_id:
                new_step = step.copy()
                self.add_step(new_step)
                self.stepAdded.emit(new_step)
                break

    def _on_move(self, step_id: str, direction: int):
        """Handle step move request"""
        for i, step in enumerate(self._steps):
            if step.id == step_id:
                new_index = i + direction
                if 0 <= new_index < len(self._steps):
                    # Swap steps
                    self._steps[i], self._steps[new_index] = (
                        self._steps[new_index],
                        self._steps[i]
                    )
                    self._refresh_list()
                    self.stepReordered.emit(step_id, new_index)
                break

    def _on_clear_all(self):
        """Handle clear all steps"""
        reply = QMessageBox.question(
            self,
            "Clear All Steps",
            "Are you sure you want to clear all transformation steps?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.clear_steps()

    # =========================================================================
    # CONTEXT MENU FOR EMPTY AREA
    # =========================================================================

    def contextMenuEvent(self, event):
        """Show context menu for the panel"""
        menu = QMenu(self)

        add_action = QAction("Add Step", self)
        add_action.setIcon(QIcon.fromTheme("list-add"))
        add_action.triggered.connect(self._on_add_step)
        menu.addAction(add_action)

        menu.exec(event.globalPos())
