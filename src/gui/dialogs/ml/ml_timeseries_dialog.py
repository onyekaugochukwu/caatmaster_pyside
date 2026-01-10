"""Time Series Dialog for forecasting"""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QMessageBox,
    QLineEdit, QSpinBox, QFormLayout, QFrame
)
from PySide6.QtCore import Signal


class MLTimeSeriesDialog(QDialog):
    """Dialog for time series forecasting operations"""

    transform_requested = Signal(str, dict)  # operation_id, params

    # Algorithm definitions
    ALGORITHMS = {
        "ARIMA": {
            "id": "ml_arima",
            "params": ["column", "output_column", "order_p", "order_d", "order_q", "steps"],
            "description": "AutoRegressive Integrated Moving Average"
        },
        "Exponential Smoothing (ETS)": {
            "id": "ml_ets",
            "params": ["column", "output_column", "trend", "seasonal", "steps"],
            "description": "Exponential Smoothing State Space Models"
        }
    }

    def __init__(self, df: pl.DataFrame, parent=None):
        super().__init__(parent)
        self.df = df
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Time Series Forecasting")
        self.setMinimumSize(500, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #f9fafb;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title_layout = QHBoxLayout()
        title_icon = QLabel("📈")
        title_icon.setStyleSheet("font-size: 24px;")
        title_layout.addWidget(title_icon)

        title = QLabel("Time Series Forecasting")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 700;
                color: #1f2937;
            }
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Algorithm selection
        algo_group = QGroupBox("Forecasting Method")
        algo_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                color: #374151;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        algo_layout = QVBoxLayout(algo_group)
        algo_layout.setContentsMargins(16, 20, 16, 16)

        self.algo_combo = QComboBox()
        self.algo_combo.setStyleSheet("""
            QComboBox {
                padding: 10px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 14px;
            }
        """)
        for algo_name in self.ALGORITHMS.keys():
            self.algo_combo.addItem(algo_name)
        self.algo_combo.currentIndexChanged.connect(self._on_algo_changed)
        algo_layout.addWidget(self.algo_combo)

        self.algo_desc = QLabel("AutoRegressive Integrated Moving Average")
        self.algo_desc.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #6b7280;
                margin-top: 4px;
            }
        """)
        algo_layout.addWidget(self.algo_desc)
        layout.addWidget(algo_group)

        # Parameters group
        params_group = QGroupBox("Parameters")
        params_group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                color: #374151;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        params_layout = QFormLayout(params_group)
        params_layout.setContentsMargins(16, 20, 16, 16)
        params_layout.setSpacing(12)

        # Value column (numeric)
        self.value_combo = QComboBox()
        self.value_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 13px;
            }
        """)
        for col in self.df.columns:
            col_dtype = self.df[col].dtype
            if col_dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32):
                self.value_combo.addItem(col)
        params_layout.addRow("Value Column:", self.value_combo)

        # Output column
        self.output_edit = QLineEdit("forecast")
        self.output_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 13px;
            }
        """)
        params_layout.addRow("Output Column:", self.output_edit)

        # Algorithm-specific parameters
        self.algo_params_frame = QFrame()
        self.algo_params_layout = QFormLayout(self.algo_params_frame)
        params_layout.addRow(self.algo_params_frame)

        layout.addWidget(params_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(self.apply_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Initialize algorithm parameters
        self.algo_widgets = {}
        self._on_algo_changed(0)

    def _on_algo_changed(self, index: int):
        """Handle algorithm selection change"""
        algo_name = self.algo_combo.currentText()
        algo_info = self.ALGORITHMS[algo_name]

        # Update description
        self.algo_desc.setText(algo_info["description"])

        # Clear and rebuild algorithm-specific parameters
        while self.algo_params_layout.count():
            item = self.algo_params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.algo_widgets = {}

        algo_id = algo_info["id"]

        # Add algorithm-specific parameters
        if algo_id == "ml_arima":
            self.order_p_spin = QSpinBox()
            self.order_p_spin.setRange(0, 10)
            self.order_p_spin.setValue(1)
            self.algo_params_layout.addRow("AR Order (p):", self.order_p_spin)
            self.algo_widgets["order_p"] = self.order_p_spin

            self.order_d_spin = QSpinBox()
            self.order_d_spin.setRange(0, 5)
            self.order_d_spin.setValue(1)
            self.algo_params_layout.addRow("Differencing (d):", self.order_d_spin)
            self.algo_widgets["order_d"] = self.order_d_spin

            self.order_q_spin = QSpinBox()
            self.order_q_spin.setRange(0, 10)
            self.order_q_spin.setValue(1)
            self.algo_params_layout.addRow("MA Order (q):", self.order_q_spin)
            self.algo_widgets["order_q"] = self.order_q_spin

        elif algo_id == "ml_ets":
            self.trend_combo = QComboBox()
            self.trend_combo.addItems(["add", "mul", "None"])
            self.trend_combo.setCurrentText("add")
            self.algo_params_layout.addRow("Trend:", self.trend_combo)
            self.algo_widgets["trend"] = self.trend_combo

            self.seasonal_combo = QComboBox()
            self.seasonal_combo.addItems(["None", "add", "mul"])
            self.seasonal_combo.setCurrentText("None")
            self.algo_params_layout.addRow("Seasonal:", self.seasonal_combo)
            self.algo_widgets["seasonal"] = self.seasonal_combo

        # Forecast steps (common)
        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(1, 365)
        self.steps_spin.setValue(12)
        self.algo_params_layout.addRow("Forecast Steps:", self.steps_spin)
        self.algo_widgets["steps"] = self.steps_spin

    def _on_apply(self):
        """Apply the selected time series operation"""
        algo_name = self.algo_combo.currentText()
        algo_info = self.ALGORITHMS[algo_name]
        algo_id = algo_info["id"]

        # Get selected column
        value_col = self.value_combo.currentText()

        # Build params
        params = {
            "column": value_col,
            "output_column": self.output_edit.text().strip() or "forecast"
        }

        # Add algorithm-specific params
        for key, widget in self.algo_widgets.items():
            if isinstance(widget, QSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
                params[key] = None if value == "None" else value

        # Emit signal
        self.transform_requested.emit(algo_id, params)
        self.accept()
