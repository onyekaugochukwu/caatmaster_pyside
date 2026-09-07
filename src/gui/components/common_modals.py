"""
Common UI Components for CAATmaster
Base modal classes, column selectors, preview tables, and reusable components
"""
from typing import Optional, List, Dict, Any, Callable
import polars as pl

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QRadioButton,
    QButtonGroup, QGroupBox, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QTextEdit, QSlider,
    QProgressBar, QMessageBox, QFrame, QSplitter, QWidget, QToolTip
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize, QEvent, QObject
from PySide6.QtGui import QFont, QIcon, QColor, QPalette

from ..theme import Colors


def create_primary_button(text: str) -> QPushButton:
    """A button styled via the app-wide QSS #PrimaryButton rule (theme.py)
    instead of a hand-rolled stylesheet - the ~20 dialogs that currently
    each hardcode their own near-identical "blue Apply button" block can
    switch to this instead, and pick up any future palette change for
    free rather than needing their own edit."""
    button = QPushButton(text)
    button.setObjectName("PrimaryButton")
    return button


def create_secondary_button(text: str) -> QPushButton:
    """A plain button styled entirely from the app-wide QSS default
    QPushButton rule - exists alongside create_primary_button() so a
    dialog's button row can be built from one consistent helper pair."""
    return QPushButton(text)


def create_success_button(text: str) -> QPushButton:
    """For a "commit/apply to dataset" action that needs to read as
    distinct from a primary "run/preview" action in the same button row
    (e.g. Benford's "Run Analysis" vs "Apply to Dataset")."""
    button = QPushButton(text)
    button.setObjectName("SuccessButton")
    return button


class EmptyStateOverlay(QObject):
    """Attach a centered, muted "nothing here yet" message to any
    QAbstractScrollArea-based widget (QListWidget, QTableWidget, ...) -
    same fix as PreviewTable's built-in empty state, generalized for
    widgets that don't have one central "data loaded" method to hook
    (QListWidget's clear()/addItem() aren't as easy to intercept as
    PreviewTable.load_dataframe() was), so the caller explicitly toggles
    visibility after populating/clearing the underlying widget instead.

    Usage:
        self._recent_empty = EmptyStateOverlay(self.recent_list, "No reports yet.")
        ...
        self._recent_empty.set_visible(self.recent_list.count() == 0)
    """

    def __init__(self, view, message: str):
        super().__init__(view)
        self.view = view
        self.label = QLabel(message, view.viewport())
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            f"color: {Colors.TEXT_TERTIARY}; font-size: 12px; padding: 24px; background: transparent;"
        )
        view.viewport().installEventFilter(self)
        self.set_visible(True)

    def eventFilter(self, obj, event):
        # At interpreter shutdown the underlying C++ QListWidget/QTableWidget
        # can already be destroyed while a queued event still reaches this
        # filter - self.view.viewport() would then raise RuntimeError rather
        # than return a stale-but-harmless value, so guard the whole check.
        try:
            if obj is self.view.viewport() and event.type() == QEvent.Resize and self.label.isVisible():
                self.label.setGeometry(self.view.viewport().rect())
        except RuntimeError:
            pass
        return False

    def set_visible(self, visible: bool):
        self.label.setVisible(visible)
        if visible:
            self.label.setGeometry(self.view.viewport().rect())


class BaseModal(QDialog):
    """
    Base class for all modal dialogs
    Provides common functionality: preview, validation, parameter handling
    """

    # Signals
    accepted_params = Signal(dict)  # Emitted with parameters on successful apply

    def __init__(self, title: str, dataframe: pl.DataFrame = None, parent=None,
                 selected_column: str = None):
        # Do not force Qt.Window here: that flag makes a dialog behave
        # like an independent top-level window while still being modal
        # and parented to the main window, a combination that confuses
        # window managers' edge-snap/tiling gestures - dragging the
        # dialog toward a screen edge can resize/restore the main
        # window instead of (or as well as) the dialog, because the WM
        # no longer recognizes it as a normal transient child exempt
        # from those gestures. Qt's default QDialog flags are the
        # well-tested, WM-correct choice.
        super().__init__(parent if parent else None)
        self.setWindowTitle(title)
        self.setModal(True)
        self.dataframe = dataframe
        self.selected_column = selected_column  # Store for auto-selection from context menu
        self._setup_ui()
        self._connect_signals()

    @property
    def original_df(self):
        """Alias for dataframe - for backward compatibility with dialogs"""
        return self.dataframe

    @original_df.setter
    def original_df(self, value):
        self.dataframe = value

    def _setup_ui(self):
        """Setup the dialog UI - override in subclasses"""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Modal: {self.windowTitle()}"))

    def _connect_signals(self):
        """Connect common signals - override in subclasses"""
        pass

    def get_parameters(self) -> dict:
        """Override in subclasses to return parameters"""
        return {}

    def validate(self) -> bool:
        """Validate inputs before accepting. Return False to prevent close."""
        return True

    def preview(self):
        """Update preview - called when parameters change"""
        pass

    def accept(self):
        """Override to validate before accepting"""
        if self.validate():
            params = self.get_parameters()
            self.accepted_params.emit(params)
            super().accept()

    def reject(self):
        """Handle cancel"""
        super().reject()

    def set_dataframe(self, df: pl.DataFrame):
        """Set the dataframe for column selection"""
        self.dataframe = df
        self._on_dataframe_changed()

    def set_selected_column(self, column_name: str):
        """Set the selected column (for context menu auto-selection)"""
        self.selected_column = column_name
        # Try to auto-select the column in any column selectors
        self._on_column_selected(column_name)

    def _on_dataframe_changed(self):
        """Called when dataframe changes - override in subclasses"""
        pass

    def _on_column_selected(self, column_name: str):
        """Called when a column is selected from context menu.
        Override in subclasses to auto-select the column."""
        pass


class ColumnSelector(QWidget):
    """
    Reusable column selector with search functionality
    Auto-populates with columns from the provided dataframe
    """

    columnSelected = Signal(str)

    def __init__(self, dataframe: pl.DataFrame = None, parent=None):
        super().__init__(parent)
        self.dataframe = None
        self._setup_ui()
        if dataframe is not None:
            self.set_dataframe(dataframe)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel("Column:")
        layout.addWidget(self.label)

        self.combo = QComboBox()
        self.combo.setEditable(False)
        self.combo.setInsertPolicy(QComboBox.NoInsert)
        self.combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self.combo)

    def set_dataframe(self, df: pl.DataFrame):
        """Set the dataframe and populate column list"""
        self.dataframe = df
        if df is not None:
            current_text = self.combo.currentText()
            self.combo.clear()
            for col in df.columns:
                self.combo.addItem(col)
            # Restore selection if column still exists
            if current_text in df.columns:
                self.combo.setCurrentText(current_text)

    def set_label(self, text: str):
        """Set the label text"""
        self.label.setText(text)

    def set_current_column(self, column_name: str):
        """Set the currently selected column"""
        if self.dataframe is not None and column_name in self.dataframe.columns:
            self.combo.setCurrentText(column_name)

    def get_column(self) -> Optional[str]:
        """Get the currently selected column"""
        if self.combo.currentIndex() >= 0:
            return self.combo.currentText()
        return None

    def is_valid(self) -> bool:
        """Check if a valid column is selected"""
        return self.get_column() is not None

    def _on_selection_changed(self, index):
        if index >= 0:
            self.columnSelected.emit(self.get_column() or "")


class MultiColumnSelector(QWidget):
    """
    Widget for selecting multiple columns via checkboxes
    """

    columnsSelected = Signal(list)

    def __init__(self, dataframe: pl.DataFrame = None, parent=None):
        super().__init__(parent)
        self.dataframe = None
        self._setup_ui()
        if dataframe is not None:
            self.set_dataframe(dataframe)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Optional title label, hidden until set_label() is called - kept
        # invisible-by-default rather than an empty visible QLabel, so
        # callers that don't need a title (e.g. UnpivotDialog) don't get
        # a blank line above the search box.
        self.title_label = QLabel()
        self.title_label.setVisible(False)
        layout.addWidget(self.title_label)

        # Search/filter
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Select all/none buttons
        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all)
        btn_layout.addWidget(self.select_all_btn)

        self.select_none_btn = QPushButton("Clear")
        self.select_none_btn.clicked.connect(self._select_none)
        btn_layout.addWidget(self.select_none_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Column list with checkboxes
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        layout.addWidget(self.list_widget)

    def set_label(self, text: str):
        """Set an optional title above the search box - mirrors
        ColumnSelector.set_label() so both selector widgets share the
        same API."""
        self.title_label.setText(text)
        self.title_label.setVisible(bool(text))

    def set_dataframe(self, df: pl.DataFrame):
        """Set the dataframe and populate column list"""
        self.dataframe = df
        self.list_widget.clear()
        if df is not None:
            for col in df.columns:
                item = QListWidgetItem(col)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.list_widget.addItem(item)

    def get_selected_columns(self) -> List[str]:
        """Get list of selected column names"""
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected

    def set_selected_columns(self, columns: List[str]):
        """Set which columns are selected"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.text() in columns:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def _on_search_changed(self, text):
        """Filter columns based on search text"""
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text and text not in item.text().lower())

    def _select_all(self):
        """Select all visible items"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)

    def _select_none(self):
        """Deselect all items"""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(Qt.Unchecked)


class PreviewTable(QTableWidget):
    """
    Table widget for displaying preview of transformation results
    Shows first N rows of a dataframe

    Defaults to a real empty state ("no preview yet") rather than a blank
    rectangle - found several dialogs (GroupSummaryDialog, TopBottomDialog,
    StratificationDialog, TrendAnalysisDialog) that build a PreviewTable
    but never actually call load_dataframe() on it, which meant the
    "Preview" panel just rendered as an indistinguishable-from-broken
    empty box. Defaulting the empty state here fixes all of them at once,
    without needing to touch each dialog's own logic.
    """

    def __init__(self, max_rows: int = 5, parent=None,
                 empty_message: str = "Nothing to preview yet."):
        super().__init__(parent)
        self.max_rows = max_rows
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)
        self.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: {Colors.BORDER};
            }}
            QTableWidget::item {{
                padding: 4px;
            }}
        """)

        # Parented to the viewport, not self - QTableWidget/QAbstractScrollArea
        # paints its viewport as a child that sits above any widget parented
        # directly to the table itself, so a label parented to `self` here
        # renders invisibly, behind the (empty) grid.
        self._empty_label = QLabel(empty_message, self.viewport())
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(
            f"color: {Colors.TEXT_TERTIARY}; font-size: 12px; padding: 24px; background: transparent;"
        )
        # The viewport can be resized by QAbstractScrollArea's own internal
        # layout (e.g. a scrollbar appearing/disappearing) without the outer
        # QTableWidget's own resizeEvent firing again - watching the
        # viewport's own resize events directly is what actually keeps the
        # label's geometry correct, not overriding resizeEvent() here.
        self.viewport().installEventFilter(self)
        self._show_empty_state(True)
        # Belt-and-suspenders: when this table sits inside a dialog that's
        # still laying out sibling group boxes above/below it, its final
        # size isn't settled yet at construction time, and not every
        # intermediate size change reliably reaches the event filter above
        # before the dialog is first shown. Re-syncing once after the
        # event loop actually settles catches that gap.
        #
        # Guarded: several dialogs replace/rebuild their preview table
        # synchronously during their own setup (e.g. a combo box's
        # currentIndexChanged firing once as it's populated, triggering
        # an immediate preview refresh) - if THIS instance is already
        # gone by the time the event loop gets back around to firing this
        # callback, touching self._empty_label raises RuntimeError
        # ("Internal C++ object already deleted") instead of silently
        # doing nothing, which is what a deferred "re-check later" should
        # do when "later" never comes for this particular instance.
        def _resync_empty_state():
            try:
                self._show_empty_state(self._empty_label.isVisible())
            except RuntimeError:
                pass
        QTimer.singleShot(0, _resync_empty_state)

    def set_empty_message(self, message: str):
        """Customize the empty-state text for a specific dialog, e.g.
        "Configure options above, then click Generate to see a preview"."""
        self._empty_label.setText(message)

    def _show_empty_state(self, show: bool):
        self._empty_label.setVisible(show)
        if show:
            self._empty_label.setGeometry(self.viewport().rect())

    def eventFilter(self, obj, event):
        try:
            if obj is self.viewport() and event.type() == QEvent.Resize and self._empty_label.isVisible():
                self._empty_label.setGeometry(self.viewport().rect())
        except RuntimeError:
            pass
        return super().eventFilter(obj, event)

    def clear(self):
        """A few dialogs call .clear() directly rather than going through
        load_dataframe(None) - route it through the same empty-state
        logic so it isn't a second way to end up with a blank box."""
        super().clear()
        self._show_empty_state(True)

    def load_dataframe(self, df: pl.DataFrame):
        """Load preview data from dataframe"""
        if df is None or df.height == 0:
            self.clear()
            self.setRowCount(0)
            self.setColumnCount(0)
            self._show_empty_state(True)
            return

        self._show_empty_state(False)

        preview = df.head(self.max_rows)

        self.setRowCount(preview.height)
        self.setColumnCount(preview.width)
        self.setHorizontalHeaderLabels(preview.columns)

        for row_idx in range(preview.height):
            for col_idx, value in enumerate(preview.row(row_idx)):
                item = QTableWidgetItem(str(value) if value is not None else "")
                self.setItem(row_idx, col_idx, item)

        self.resizeColumnsToContents()


class NumberInput(QWidget):
    """
    Reusable number input with label and optional spin/double spin
    """

    valueChanged = Signal(float)

    def __init__(self, label: str, min_val: float = 0, max_val: float = 100,
                 decimals: int = 2, default_value: float = None, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(label)
        layout.addWidget(self.label)

        if decimals == 0:
            self.spin = QSpinBox()
            self.spin.setMinimum(int(min_val))
            self.spin.setMaximum(int(max_val))
        else:
            self.spin = QDoubleSpinBox()
            self.spin.setMinimum(min_val)
            self.spin.setMaximum(max_val)
            self.spin.setDecimals(decimals)

        if default_value is not None:
            self.spin.setValue(default_value)

        self.spin.valueChanged.connect(self.valueChanged.emit)
        layout.addWidget(self.spin)

        layout.addStretch()

    def get_value(self) -> float:
        return self.spin.value()

    def set_value(self, value: float):
        self.spin.setValue(value)

    def set_range(self, min_val: float, max_val: float):
        self.spin.setMinimum(min_val)
        self.spin.setMaximum(max_val)


class RadioButtonGroup(QWidget):
    """
    Group of radio buttons with label
    """

    selectionChanged = Signal(str)

    def __init__(self, title: str, options: List[tuple], parent=None):
        """
        Args:
            title: Group title
            options: List of (label, value) tuples
        """
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.group_box = QGroupBox(title)
        group_layout = QVBoxLayout(self.group_box)

        self.button_group = QButtonGroup(self)

        for label, value in options:
            radio = QRadioButton(label)
            self.button_group.addButton(radio, value)
            group_layout.addWidget(radio)
            if value == options[0][1]:
                radio.setChecked(True)

        self.button_group.buttonClicked.connect(self._on_button_clicked)
        layout.addWidget(self.group_box)

    def _on_button_clicked(self, button):
        self.selectionChanged.emit(self.button_group.id(button))

    def get_selected_value(self) -> str:
        button = self.button_group.checkedButton()
        if button:
            return self.button_group.id(button)
        return None

    def set_selected_value(self, value: str):
        for button in self.button_group.buttons():
            if self.button_group.id(button) == value:
                button.setChecked(True)
                break


class StatusLabel(QLabel):
    """
    Label that shows status with color coding
    """

    def __init__(self, text: str = "", status: str = "normal", parent=None):
        super().__init__(text, parent)
        self.setStatus(status)

    def setStatus(self, status: str):
        """Set status and update color"""
        colors = {
            "normal": (Colors.TEXT_PRIMARY, Colors.BG_SECONDARY),
            "success": (Colors.SUCCESS, Colors.SUCCESS_SOFT),
            "warning": (Colors.WARNING_STRONG, Colors.WARNING_SOFT),
            "error": (Colors.DANGER, Colors.DANGER_SOFT),
            "info": (Colors.ACCENT, Colors.ACCENT_SOFT),
        }
        fg_color, bg_color = colors.get(status, colors["normal"])
        self.setStyleSheet(f"""
            QLabel {{
                color: {fg_color};
                background-color: {bg_color};
                padding: 8px;
                border-radius: 4px;
                border: 1px solid {fg_color};
            }}
        """)


class ProgressPanel(QWidget):
    """
    Progress panel with status label and progress bar
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.hide()

    def show_progress(self, message: str = "Processing..."):
        """Show progress panel"""
        self.status_label.setText(message)
        self.progress_bar.setValue(0)
        self.show()

    def update_progress(self, value: int, message: str = None):
        """Update progress"""
        self.progress_bar.setValue(value)
        if message:
            self.status_label.setText(message)

    def hide_progress(self, message: str = "Complete"):
        """Hide progress panel"""
        self.status_label.setText(message)
        self.progress_bar.setValue(100)
        QTimer.singleShot(1500, self.hide)


class InfoToolButton(QPushButton):
    """
    Button that shows tooltip with information
    """

    def __init__(self, info_text: str, parent=None):
        super().__init__(parent)
        self.setText("ⓘ")
        self.setToolTipDuration(0)  # Show until dismissed
        self.setStyleSheet(f"""
            QPushButton {{
                border: none;
                background: transparent;
                color: {Colors.ACCENT};
                font: bold 14px;
                max-width: 24px;
                max-height: 24px;
            }}
            QPushButton:hover {{
                color: {Colors.ACCENT_HOVER};
            }}
        """)

        class TooltipWidget(QFrame):
            def __init__(self, text):
                super().__init__()
                # Same inverted (dark-on-light-bg / light-on-dark-bg)
                # convention as the app-wide QToolTip rule in theme.py -
                # one tooltip visual language, not two.
                self.setStyleSheet(
                    f"QFrame {{"
                    f"background: {Colors.TEXT_PRIMARY};"
                    f"color: {Colors.BG_PRIMARY};"
                    f"padding: 12px;"
                    f"border-radius: 6px;"
                    f"max-width: 300px;"
                    f"}}"
                )
                layout = QVBoxLayout(self)
                label = QLabel(text)
                label.setWordWrap(True)
                label.setStyleSheet(f"color: {Colors.BG_PRIMARY};")
                layout.addWidget(label)

        self.tooltip_widget = TooltipWidget(info_text)


class ElbowMethodChart(QWidget):
    """
    Simple elbow method visualization for K-Means
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.k_values = list(range(2, 11))
        self.inertias = []
        self.recommended_k = 3

    def set_data(self, inertias: List[float], recommended_k: int):
        """Set the inertia values and recommended K"""
        self.inertias = inertias
        self.recommended_k = recommended_k
        self.update()

    def paintEvent(self, event):
        """Draw the elbow chart"""
        from PySide6.QtGui import QPainter, QPen, QBrush, QColor

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.inertias:
            return

        # Calculate positions
        margin = 40
        width = self.width() - 2 * margin
        height = self.height() - 2 * margin

        # Find min/max for scaling
        min_inertia = min(self.inertias)
        max_inertia = max(self.inertias)
        if max_inertia == min_inertia:
            max_inertia = min_inertia + 1

        # Draw axes
        painter.setPen(QPen(Qt.black, 1))
        painter.drawLine(margin, self.height() - margin,
                         self.width() - margin, self.height() - margin)  # X-axis
        painter.drawLine(margin, self.height() - margin,
                         margin, margin)  # Y-axis

        # Draw points and lines
        for i, (k, inertia) in enumerate(zip(self.k_values, self.inertias)):
            x = margin + (i / (len(self.k_values) - 1)) * width
            y = self.height() - margin - ((inertia - min_inertia) / (max_inertia - min_inertia)) * height

            # Draw point
            if k == self.recommended_k:
                painter.setBrush(QBrush(QColor(0, 150, 0)))
            else:
                painter.setBrush(QBrush(QColor(0, 100, 200)))
            painter.setPen(QPen(Qt.black, 1))
            painter.drawEllipse(int(x - 5), int(y - 5), 10, 10)

            # Draw label
            painter.setFont(QFont("Arial", 8))
            painter.drawText(int(x - 5), int(y - 10), str(k))

            # Draw line to next point
            if i < len(self.k_values) - 1:
                next_inertia = self.inertias[i + 1]
                next_x = margin + ((i + 1) / (len(self.k_values) - 1)) * width
                next_y = self.height() - margin - ((next_inertia - min_inertia) / (max_inertia - min_inertia)) * height
                painter.setPen(QPen(QColor(0, 100, 200), 2))
                painter.drawLine(int(x), int(y), int(next_x), int(next_y))

        # Draw labels
        painter.setPen(QPen(Qt.black, 1))
        painter.drawText(self.width() // 2 - 20, self.height() - 10, "K (Clusters)")

        # Draw recommended K label
        for i, (k, inertia) in enumerate(zip(self.k_values, self.inertias)):
            if k == self.recommended_k:
                x = margin + (i / (len(self.k_values) - 1)) * width
                painter.setPen(QPen(QColor(0, 150, 0), 1))
                painter.drawText(int(x - 30), int(self.height() - 25),
                                 f"Recommended: K={k}")


class BenfordChart(QWidget):
    """
    Bar chart comparing expected distribution vs actual Benford
    Supports 1, 2, or 3 digit analysis
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.n_digits = 1
        self.expected = [30.1, 17.6, 12.5, 9.7, 7.9, 6.7, 5.8, 5.1, 4.6]
        self.actual = []
        self.deviations = []
        self.digit_labels = [str(i) for i in range(1, 10)]

    def set_data(self, expected: list, actual: list, deviations: list = None):
        """Set actual values and deviations

        Args:
            expected: List of expected percentages
            actual: List of actual percentages
            deviations: List of deviations (actual - expected)
        """
        self.expected = expected
        self.actual = actual if actual else []
        self.deviations = deviations if deviations else []

        # Determine n_digits from data length
        if len(expected) == 9:
            self.n_digits = 1
            self.digit_labels = [str(i) for i in range(1, 10)]
        else:
            self.n_digits = 2
            self.digit_labels = [f"{i:02d}" for i in range(10, 10 + len(expected))]

        self.update()

    def paintEvent(self, event):
        """Draw the Benford comparison chart"""
        from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.actual:
            painter.drawText(self.rect(), Qt.AlignCenter, "Run analysis to see chart")
            return

        margin = 50
        bar_width = max(15, 400 // len(self.expected))
        spacing = max(5, bar_width // 3)
        chart_width = (bar_width * 2 + spacing) * len(self.expected)
        chart_height = self.height() - 2 * margin

        # Scale chart to fit
        if chart_width > self.width() - 2 * margin:
            # Need horizontal scrolling - draw what fits
            visible_bars = min(len(self.expected), max(1, (self.width() - 2 * margin) // (bar_width * 2 + spacing)))
            chart_width = (bar_width * 2 + spacing) * visible_bars
        else:
            visible_bars = len(self.expected)

        max_pct = max(max(self.expected[:visible_bars]), max(self.actual[:visible_bars]) if self.actual else 0) * 1.2

        # Draw expected bars (gray)
        for i in range(visible_bars):
            if i >= len(self.expected):
                break
            x = margin + i * (bar_width * 2 + spacing)
            bar_height = (self.expected[i] / max_pct) * chart_height
            painter.setBrush(QBrush(QColor(150, 150, 150)))
            painter.setPen(QPen(Qt.black, 1))
            painter.drawRect(int(x), int(self.height() - margin - bar_height),
                           bar_width, int(bar_height))

        # Draw actual bars (blue, if data available)
        if self.actual:
            for i in range(visible_bars):
                if i >= len(self.actual):
                    break
                x = margin + i * (bar_width * 2 + spacing) + bar_width
                bar_height = (self.actual[i] / max_pct) * chart_height
                dev = self.deviations[i] if i < len(self.deviations) else 0
                if abs(dev) > 5:
                    painter.setBrush(QBrush(QColor(220, 53, 69)))  # Red for high deviation
                elif abs(dev) > 2:
                    painter.setBrush(QBrush(QColor(255, 193, 7)))  # Yellow for moderate deviation
                else:
                    painter.setBrush(QBrush(QColor(0, 123, 255)))  # Blue for normal
                painter.setPen(QPen(Qt.black, 1))
                painter.drawRect(int(x), int(self.height() - margin - bar_height),
                               bar_width, int(bar_height))

        # Draw X-axis labels
        painter.setFont(QFont("Arial", 7))
        for i in range(visible_bars):
            if i >= len(self.digit_labels):
                break
            x = margin + i * (bar_width * 2 + spacing) + bar_width // 2
            # Alternate label orientation for 2/3 digit analysis
            if self.n_digits > 1:
                painter.save()
                painter.translate(int(x), int(self.height() - margin + 15))
                painter.rotate(-45)
                painter.drawText(-15, 0, self.digit_labels[i])
                painter.restore()
            else:
                painter.drawText(int(x - 5), int(self.height() - margin + 15), self.digit_labels[i])

        # Draw Y-axis
        painter.setPen(QPen(Qt.black, 1))
        painter.drawLine(margin, margin, margin, self.height() - margin)  # Y-axis
        painter.drawLine(margin, self.height() - margin, self.width() - margin, self.height() - margin)  # X-axis

        # Draw Y-axis labels
        painter.setFont(QFont("Arial", 8))
        for i in range(5):
            pct = max_pct * i / 4
            y = self.height() - margin - (pct / max_pct) * chart_height
            painter.drawText(5, int(y + 4), f"{pct:.0f}%")

        # Draw legend
        legend_y = 15
        painter.setBrush(QBrush(QColor(150, 150, 150)))
        painter.drawRect(10, legend_y, 15, 15)
        painter.setPen(QPen(Qt.black, 1))
        painter.drawText(30, legend_y + 12, "Expected")

        if self.actual:
            painter.setBrush(QBrush(QColor(0, 123, 255)))
            painter.drawRect(100, legend_y, 15, 15)
            painter.drawText(120, legend_y + 12, "Actual")


class TimeSeriesChart(QWidget):
    """
    Simple time series chart showing historical data and forecast
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.historical_data = []
        self.forecast_data = []
        self.confidence_lower = []
        self.confidence_upper = []
        self.show_confidence = True

    def set_data(self, historical: List[float], forecast: List[float],
                 confidence_lower: List[float] = None, confidence_upper: List[float] = None):
        """Set historical and forecast data"""
        self.historical_data = historical
        self.forecast_data = forecast
        self.confidence_lower = confidence_lower or []
        self.confidence_upper = confidence_upper or []
        self.update()

    def paintEvent(self, event):
        """Draw the time series chart"""
        from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QLinearGradient

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self.historical_data and not self.forecast_data:
            painter.drawText(self.rect(), Qt.AlignCenter, "No data to display")
            return

        margin = 40
        width = self.width() - 2 * margin
        height = self.height() - 2 * margin

        all_data = self.historical_data + self.forecast_data
        min_val = min(all_data) * 0.9
        max_val = max(all_data) * 1.1
        if max_val == min_val:
            max_val = min_val + 1

        # Draw confidence interval (if enabled)
        if self.show_confidence and self.confidence_lower and self.confidence_upper:
            painter.setPen(Qt.NoPen)
            gradient = QLinearGradient(0, 0, 0, height)
            gradient.setColorAt(0, QColor(0, 123, 255, 100))
            gradient.setColorAt(1, QColor(0, 123, 255, 30))
            painter.setBrush(gradient)

            # Draw shaded area
            start_hist = len(self.historical_data)
            for i in range(len(self.confidence_lower)):
                x = margin + (start_hist + i) * (width / (len(self.historical_data) + len(self.forecast_data) - 1))
                next_x = margin + (start_hist + i + 1) * (width / (len(self.historical_data) + len(self.forecast_data) - 1))

                y_lower = self.height() - margin - ((self.confidence_lower[i] - min_val) / (max_val - min_val)) * height
                y_upper = self.height() - margin - ((self.confidence_upper[i] - min_val) / (max_val - min_val)) * height

                painter.drawRect(int(x), int(y_upper), int(next_x - x), int(y_lower - y_upper))

        # Draw historical line
        if self.historical_data:
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            for i in range(len(self.historical_data) - 1):
                x1 = margin + i * (width / max(1, len(self.historical_data) + len(self.forecast_data) - 1))
                x2 = margin + (i + 1) * (width / max(1, len(self.historical_data) + len(self.forecast_data) - 1))
                y1 = self.height() - margin - ((self.historical_data[i] - min_val) / (max_val - min_val)) * height
                y2 = self.height() - margin - ((self.historical_data[i + 1] - min_val) / (max_val - min_val)) * height
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Draw forecast line (dashed)
        if self.forecast_data:
            painter.setPen(QPen(QColor(0, 123, 255), 2))
            painter.setDashPattern([5, 3])
            for i in range(len(self.forecast_data) - 1):
                start_x = len(self.historical_data)
                x1 = margin + (start_x + i) * (width / max(1, len(self.historical_data) + len(self.forecast_data) - 1))
                x2 = margin + (start_x + i + 1) * (width / max(1, len(self.historical_data) + len(self.forecast_data) - 1))
                y1 = self.height() - margin - ((self.forecast_data[i] - min_val) / (max_val - min_val)) * height
                y2 = self.height() - margin - ((self.forecast_data[i + 1] - min_val) / (max_val - min_val)) * height
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            painter.setDashPattern([])  # Reset

        # Draw divider between historical and forecast
        if self.historical_data and self.forecast_data:
            divider_x = margin + len(self.historical_data) * (width / (len(self.historical_data) + len(self.forecast_data)))
            painter.setPen(QPen(QColor(255, 0, 0), 1, Qt.DashLine))
            painter.drawLine(int(divider_x), margin, int(divider_x), self.height() - margin)

    def set_forecast_data(self, historical_dates: list, historical_values: list,
                          forecast_dates: list, forecast_values: list,
                          lower_bounds: list = None, upper_bounds: list = None):
        """Set historical and forecast data with dates"""
        self.historical_data = historical_values
        self.forecast_data = forecast_values
        self.confidence_lower = lower_bounds or []
        self.confidence_upper = upper_bounds or []
        self.update()
