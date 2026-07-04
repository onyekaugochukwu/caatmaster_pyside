"""
Standardize Dialog for CAATmaster
Normalization and standardization operations
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QWidget, QMessageBox, QLineEdit, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector


class StandardizeDialog(BaseModal):
    """
    Dialog for data standardization and normalization
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Standardize/Normalize", dataframe, parent)
        self.setMinimumSize(550, 500)

    def _setup_ui(self):
        """Setup the standardize dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Source Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column:")
        col_layout.addWidget(self.column_selector)

        layout.addWidget(col_group)

        # Method selection
        method_group = QGroupBox("Standardization Method")
        method_layout = QVBoxLayout(method_group)

        self.method_group = QButtonGroup()

        methods = [
            ("Z-Score (Standard Score)", "zscore"),
            ("Min-Max Normalization (0-1)", "minmax"),
            ("Min-Max Normalization (-1 to 1)", "minmax_symmetric"),
            ("Decimal Scaling", "decimal"),
            ("Percent Rank", "percent_rank"),
            ("Rank (Dense)", "rank_dense"),
            ("Rank (Ordinal)", "rank_ordinal"),
            ("Robust Z-Score (Median)", "robust_zscore"),
        ]

        for label, value in methods:
            radio = QRadioButton(label)
            radio.setProperty("method_value", value)
            self.method_group.addButton(radio)
            method_layout.addWidget(radio)
            if value == "zscore":
                radio.setChecked(True)

        layout.addWidget(method_group)

        # Output column
        output_group = QGroupBox("Output Column")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Name:"), 0, 0)
        self.output_col_edit = QLineEdit("standardized")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview (First 10 Rows)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        # Statistics
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #666; font-style: italic;")
        preview_layout.addWidget(self.stats_label)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setStyleSheet("""
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
        self.apply_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

    def get_parameters(self) -> dict:
        """Get the standardization parameters"""
        checked = self.method_group.checkedButton()
        return {
            "column": self.column_selector.get_column(),
            "method": checked.property("method_value") if checked else None,
            "output_column": self.output_col_edit.text() or "standardized",
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
            if dtype not in [pl.Float64, pl.Float32, pl.Int64, pl.Int32, pl.Int16, pl.Int8]:
                QMessageBox.warning(self, "Validation Error",
                                  "Selected column must be numeric.")
                return False

        return True

    def preview(self):
        """Generate preview of standardization"""
        try:
            params = self.get_parameters()
            column = params["column"]
            method = params["method"]

            if not column:
                return

            # Get data
            col_data = self.original_df[column].to_numpy()
            valid_mask = ~np.isnan(col_data.astype(float))
            valid_data = col_data[valid_mask]

            if len(valid_data) == 0:
                self.stats_label.setText("No valid numeric data")
                return

            # Apply standardization
            if method == "zscore":
                result = self._zscore(valid_data)
                stats_text = "Mean=0, Std=1"
            elif method == "minmax":
                result = self._minmax(valid_data, 0, 1)
                stats_text = "Range: 0 to 1"
            elif method == "minmax_symmetric":
                result = self._minmax(valid_data, -1, 1)
                stats_text = "Range: -1 to 1"
            elif method == "decimal":
                result = self._decimal_scaling(valid_data)
                stats_text = "Decimal scaled"
            elif method == "percent_rank":
                result = self._percent_rank(valid_data)
                stats_text = "Range: 0% to 100%"
            elif method == "rank_dense":
                result = self._rank_dense(valid_data)
                stats_text = "Dense ranking"
            elif method == "rank_ordinal":
                result = self._rank_ordinal(valid_data)
                stats_text = "Ordinal ranking"
            elif method == "robust_zscore":
                result = self._robust_zscore(valid_data)
                stats_text = "Median=0, MAD-based std"
            else:
                result = valid_data
                stats_text = ""

            # Create preview dataframe
            preview_df = self.original_df[:10].clone()
            output_col = params["output_column"]

            # Map results back to full data
            full_result = np.full(len(self.original_df), np.nan)
            full_result[valid_mask] = result

            preview_df = preview_df.with_columns(
                pl.Series(name=output_col, values=full_result[:10])
            )

            self.preview_table.load_dataframe(preview_df)
            self.stats_label.setText(stats_text)

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

    def _zscore(self, data: np.ndarray) -> np.ndarray:
        """Calculate Z-scores"""
        mean = np.mean(data)
        std = np.std(data)
        if std == 0:
            std = 1
        return (data - mean) / std

    def _minmax(self, data: np.ndarray, min_val: float, max_val: float) -> np.ndarray:
        """Min-Max normalization"""
        data_min = np.min(data)
        data_max = np.max(data)
        data_range = data_max - data_min
        if data_range == 0:
            data_range = 1
        return min_val + (data - data_min) / data_range * (max_val - min_val)

    def _decimal_scaling(self, data: np.ndarray) -> np.ndarray:
        """Decimal scaling normalization"""
        max_abs = np.max(np.abs(data))
        if max_abs == 0:
            return data
        n = len(str(int(max_abs)))
        return data / (10 ** n)

    def _percent_rank(self, data: np.ndarray) -> np.ndarray:
        """Percent rank"""
        sorted_indices = np.argsort(data)
        ranks = np.zeros_like(sorted_indices, dtype=float)
        ranks[sorted_indices] = np.arange(1, len(data) + 1) / len(data) * 100
        return ranks

    def _rank_dense(self, data: np.ndarray) -> np.ndarray:
        """Dense ranking"""
        unique_values = np.unique(data)
        value_to_rank = {v: i + 1 for i, v in enumerate(unique_values)}
        return np.array([value_to_rank[v] for v in data])

    def _rank_ordinal(self, data: np.ndarray) -> np.ndarray:
        """Ordinal ranking (competition ranking)"""
        sorted_indices = np.argsort(data)
        ranks = np.zeros_like(sorted_indices, dtype=int)
        ranks[sorted_indices] = np.arange(1, len(data) + 1)
        return ranks

    def _robust_zscore(self, data: np.ndarray) -> np.ndarray:
        """Robust Z-score using median and MAD"""
        median = np.median(data)
        mad = np.median(np.abs(data - median))
        if mad == 0:
            mad = 1
        return (data - median) / (mad * 1.4826)

    def apply_standardization(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply standardization to dataframe"""
        params = self.get_parameters()
        column = params["column"]
        method = params["method"]
        output_col = params["output_column"]

        # Get data
        col_data = df[column].to_numpy()
        valid_mask = ~np.isnan(col_data.astype(float))
        valid_data = col_data[valid_mask]

        if len(valid_data) == 0:
            return df.with_columns(
                pl.lit(np.nan).alias(output_col)
            )

        # Apply standardization
        if method == "zscore":
            result = self._zscore(valid_data)
        elif method == "minmax":
            result = self._minmax(valid_data, 0, 1)
        elif method == "minmax_symmetric":
            result = self._minmax(valid_data, -1, 1)
        elif method == "decimal":
            result = self._decimal_scaling(valid_data)
        elif method == "percent_rank":
            result = self._percent_rank(valid_data)
        elif method == "rank_dense":
            result = self._rank_dense(valid_data)
        elif method == "rank_ordinal":
            result = self._rank_ordinal(valid_data)
        elif method == "robust_zscore":
            result = self._robust_zscore(valid_data)
        else:
            result = valid_data

        # Map back to full data
        full_result = np.full(len(df), np.nan)
        full_result[valid_mask] = result

        return df.with_columns(
            pl.Series(name=output_col, values=full_result)
        )
