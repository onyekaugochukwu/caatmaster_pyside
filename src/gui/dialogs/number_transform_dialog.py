"""
Number Transform Dialog for CAATmaster
Modulo and Power transformations for numeric columns
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QWidget, QMessageBox, QLineEdit, QRadioButton, QButtonGroup,
    QTabWidget, QScrollArea
)
from PySide6.QtCore import Qt, QTimer

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button
from ..theme import Colors


class NumberTransformDialog(BaseModal):
    """
    Dialog for numeric transformations: Modulo, Power, etc.
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None,
                 transform_type: str = "modulo"):
        self.original_df = dataframe
        self.transform_type = transform_type
        super().__init__("Number Transform", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(550, 450)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'column_selector') and column_name:
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_result")
            QTimer.singleShot(100, self.preview)

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        if hasattr(self, 'column_selector'):
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_result")
            QTimer.singleShot(100, self.preview)

    def _setup_ui(self):
        """Setup the number transform dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Container widget for scroll area
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Source Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column:")
        col_layout.addWidget(self.column_selector)

        scroll_layout.addWidget(col_group)

        # Transform type tabs
        self.tabs = QTabWidget()

        # Modulo tab
        self._create_modulo_tab()

        # Power tab
        self._create_power_tab()

        self.tabs.addTab(self.modulo_tab, "Modulo")
        self.tabs.addTab(self.power_tab, "Power")

        # operation_id ('math_modulo'/'math_power') is what actually
        # decides which real method runs on Apply Transform, regardless
        # of which tab is showing - switching tabs only changes this
        # dialog's own preview. Pre-selecting AND disabling the other tab
        # keeps the dialog from implying a choice that Apply won't honor
        # (a real bug: opening this dialog for "Power" used to still
        # default to and preview the Modulo tab).
        modulo_index, power_index = 0, 1
        self.tabs.setCurrentIndex(modulo_index if self.transform_type == "modulo" else power_index)
        self.tabs.setTabEnabled(power_index if self.transform_type == "modulo" else modulo_index, False)

        scroll_layout.addWidget(self.tabs)

        # Output options
        output_group = QGroupBox("Output Column")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Name:"), 0, 0)
        self.output_col_edit = QLineEdit("result")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        scroll_layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        # Stats
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-style: italic;")
        preview_layout.addWidget(self.stats_label)

        scroll_layout.addWidget(preview_group)

        # Set scroll area content
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.transform_btn = create_primary_button("Apply Transform")
        self.transform_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.transform_btn)

        layout.addLayout(btn_layout)

    def _create_modulo_tab(self):
        """Create modulo transformation tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        options_group = QGroupBox("Modulo Options")
        options_layout = QGridLayout(options_group)

        options_layout.addWidget(QLabel("Divisor:"), 0, 0)
        self.modulo_divisor = QDoubleSpinBox()
        self.modulo_divisor.setRange(0.001, 1000000)
        self.modulo_divisor.setValue(10)
        self.modulo_divisor.setDecimals(3)
        options_layout.addWidget(self.modulo_divisor, 0, 1)

        # Store remainder info
        options_info = QLabel("Returns the remainder after division (e.g., 17 mod 10 = 7)")
        options_info.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        options_layout.addWidget(options_info, 1, 0, 1, 2)

        layout.addWidget(options_group)
        layout.addStretch()

        self.modulo_tab = tab

    def _create_power_tab(self):
        """Create power transformation tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        options_group = QGroupBox("Power Options")
        options_layout = QGridLayout(options_group)

        options_layout.addWidget(QLabel("Exponent:"), 0, 0)
        self.power_exponent = QDoubleSpinBox()
        self.power_exponent.setRange(-100, 100)
        self.power_exponent.setValue(2)
        self.power_exponent.setDecimals(2)
        options_layout.addWidget(self.power_exponent, 0, 1)

        # Presets
        preset_group = QGroupBox("Quick Presets")
        preset_layout = QHBoxLayout(preset_group)

        presets = [
            ("Square (x²)", 2),
            ("Cube (x³)", 3),
            ("Square Root (√x)", 0.5),
            ("Reciprocal (1/x)", -1),
        ]
        for label, value in presets:
            btn = QRadioButton(label)
            btn.toggled.connect(lambda checked, v=value, b=btn: self._on_preset_selected(v, b) if checked else None)
            preset_layout.addWidget(btn)

        options_layout.addWidget(preset_group, 1, 0, 1, 2)

        layout.addWidget(options_group)
        layout.addStretch()

        self.power_tab = tab

    def _on_preset_selected(self, value: float, button):
        """Handle preset button selection"""
        self.power_exponent.setValue(value)

    def get_parameters(self) -> dict:
        """Get the transform parameters"""
        tab_index = self.tabs.currentIndex()

        return {
            "column": self.column_selector.get_column(),
            "output_column": self.output_col_edit.text() or "result",
            "transform_type": ["modulo", "power"][tab_index],
            "divisor": self.modulo_divisor.value(),
            "exponent": self.power_exponent.value(),
        }

    def validate(self) -> bool:
        """Validate parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column.")
            return False

        if column in self.original_df.columns:
            dtype = self.original_df[column].dtype
            if dtype not in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]:
                QMessageBox.warning(self, "Validation Error",
                                  "Selected column must be numeric.")
                return False

        return True

    def preview(self):
        """Generate a preview by calling the exact same DataProcessor
        method Apply Transform will call, against just the first 10 rows.
        An earlier version recomputed the transform locally against the
        WHOLE dataframe's valid (non-NaN) values, then tried to splice
        the first 10 of those results back into a fixed 10-row preview
        via valid_mask[:10] - which raised a numpy boolean-index-size
        error and hung this dialog (QMessageBox.warning blocks
        indefinitely with no user present to dismiss it under a headless
        Qt platform) on any real dataset with fewer than 10 rows, and
        even on larger datasets misaligned results with rows whenever a
        NaN appeared before row 10."""
        from core.data_processor import DataProcessor

        try:
            params = self.get_parameters()
            column = params["column"]
            output_col = params["output_column"]

            if not column:
                return

            preview_slice = self.original_df.head(10)
            processor = DataProcessor()
            if params["transform_type"] == "modulo":
                divisor = params["divisor"] or 1
                result = processor.modulo(preview_slice, column=column, divisor=divisor, output_col=output_col)
            else:  # power
                result = processor.power(preview_slice, column=column, exponent=params["exponent"], output_col=output_col)

            self.preview_table.load_dataframe(result)

            mean_val = result[output_col].mean()
            if mean_val is not None:
                self.stats_label.setText(f"Sample mean: {mean_val:.4f}")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")
