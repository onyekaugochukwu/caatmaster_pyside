"""
Anomaly Detection Dialog for CAATmaster
Configure anomaly detection parameters for various methods
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QRadioButton,
    QButtonGroup, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QWidget, QMessageBox, QLineEdit, QTabWidget, QWidget, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer

from ..components.common_modals import (
    BaseModal, PreviewTable, NumberInput, ColumnSelector, StatusLabel
)


class AnomalyDetectionDialog(BaseModal):
    """
    Anomaly Detection dialog with multiple method options
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        super().__init__("Anomaly Detection", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(700, 650)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        # Auto-select in all tabs
        for col_selector in [self.iforest_col, self.zscore_col, self.iqr_col, self.lof_col]:
            if hasattr(col_selector, 'set_current_column'):
                col_selector.set_current_column(column_name)
        QTimer.singleShot(100, self.preview)

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        for col_selector in [self.iforest_col, self.zscore_col, self.iqr_col, self.lof_col]:
            if hasattr(col_selector, 'set_current_column'):
                col_selector.set_current_column(column_name)
        QTimer.singleShot(100, self.preview)

    def _setup_ui(self):
        """Setup the anomaly detection dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Method selection tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #bdbdbd;
            }
            QTabBar::tab {
                padding: 8px 16px;
            }
        """)

        # Isolation Forest tab
        self._create_iforest_tab()

        # Z-Score tab
        self._create_zscore_tab()

        # IQR tab
        self._create_iqr_tab()

        # LOF tab
        self._create_lof_tab()

        self.tabs.addTab(self.iforest_tab, "Isolation Forest")
        self.tabs.addTab(self.zscore_tab, "Z-Score")
        self.tabs.addTab(self.iqr_tab, "IQR")
        self.tabs.addTab(self.lof_tab, "Local Outlier Factor")

        layout.addWidget(self.tabs)

        # Output columns
        output_group = QGroupBox("Output Columns")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Anomaly Flag Column:"), 0, 0)
        self.anomaly_col_edit = QLineEdit("is_anomaly")
        output_layout.addWidget(self.anomaly_col_edit, 0, 1)

        output_layout.addWidget(QLabel("Score Column:"), 1, 0)
        self.score_col_edit = QLineEdit("anomaly_score")
        output_layout.addWidget(self.score_col_edit, 1, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview (Sample Anomalies)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        # Stats
        self.stats_label = StatusLabel("No data previewed")
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

        self.run_btn = QPushButton("Run Detection")
        self.run_btn.setStyleSheet("""
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
        self.run_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.run_btn)

        layout.addLayout(btn_layout)

    def _create_iforest_tab(self):
        """Create Isolation Forest tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        # Column selection
        col_layout = QHBoxLayout()
        self.iforest_col = ColumnSelector(self.original_df)
        self.iforest_col.set_label("Source Column:")
        col_layout.addWidget(self.iforest_col)
        layout.addLayout(col_layout)

        # Parameters
        params_group = QGroupBox("Parameters")
        params_layout = QGridLayout(params_group)

        # Contamination
        params_layout.addWidget(QLabel("Contamination:"), 0, 0)
        self.iforest_contamination = QDoubleSpinBox()
        self.iforest_contamination.setRange(0.01, 0.5)
        self.iforest_contamination.setValue(0.1)
        self.iforest_contamination.setSingleStep(0.01)
        self.iforest_contamination.setSuffix(" (1-50%)")
        params_layout.addWidget(self.iforest_contamination, 0, 1)

        # Number of estimators
        params_layout.addWidget(QLabel("Number of Trees:"), 1, 0)
        self.iforest_trees = QSpinBox()
        self.iforest_trees.setRange(10, 500)
        self.iforest_trees.setValue(100)
        params_layout.addWidget(self.iforest_trees, 1, 1)

        # Max samples
        params_layout.addWidget(QLabel("Max Samples:"), 2, 0)
        self.iforest_max_samples = QSpinBox()
        self.iforest_max_samples.setRange(0, 10000)
        self.iforest_max_samples.setValue(0)
        self.iforest_max_samples.setSpecialValueText("Auto")
        params_layout.addWidget(self.iforest_max_samples, 2, 1)

        layout.addWidget(params_group)
        layout.addStretch()

        self.iforest_tab = tab

    def _create_zscore_tab(self):
        """Create Z-Score tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        # Column selection
        col_layout = QHBoxLayout()
        self.zscore_col = ColumnSelector(self.original_df)
        self.zscore_col.set_label("Source Column:")
        col_layout.addWidget(self.zscore_col)
        layout.addLayout(col_layout)

        # Parameters
        params_group = QGroupBox("Parameters")
        params_layout = QGridLayout(params_group)

        # Threshold
        params_layout.addWidget(QLabel("Threshold (Std Dev):"), 0, 0)
        self.zscore_threshold = QDoubleSpinBox()
        self.zscore_threshold.setRange(1.0, 10.0)
        self.zscore_threshold.setValue(3.0)
        self.zscore_threshold.setSingleStep(0.5)
        params_layout.addWidget(self.zscore_threshold, 0, 1)

        # Direction
        params_layout.addWidget(QLabel("Direction:"), 1, 0)
        self.zscore_direction = QComboBox()
        self.zscore_direction.addItems(["Both", "Above Mean Only", "Below Mean Only"])
        params_layout.addWidget(self.zscore_direction, 1, 1)

        layout.addWidget(params_group)
        layout.addStretch()

        self.zscore_tab = tab

    def _create_iqr_tab(self):
        """Create IQR tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        # Column selection
        col_layout = QHBoxLayout()
        self.iqr_col = ColumnSelector(self.original_df)
        self.iqr_col.set_label("Source Column:")
        col_layout.addWidget(self.iqr_col)
        layout.addLayout(col_layout)

        # Parameters
        params_group = QGroupBox("Parameters")
        params_layout = QGridLayout(params_group)

        # Multiplier
        params_layout.addWidget(QLabel("IQR Multiplier:"), 0, 0)
        self.iqr_multiplier = QDoubleSpinBox()
        self.iqr_multiplier.setRange(0.5, 5.0)
        self.iqr_multiplier.setValue(1.5)
        self.iqr_multiplier.setSingleStep(0.1)
        params_layout.addWidget(self.iqr_multiplier, 0, 1)

        # Bounds type
        params_layout.addWidget(QLabel("Detection Mode:"), 1, 0)
        self.iqr_mode = QComboBox()
        self.iqr_mode.addItems(["Outer Bounds (1.5x IQR)", "Extreme Bounds (3x IQR)"])
        params_layout.addWidget(self.iqr_mode, 1, 1)

        layout.addWidget(params_group)
        layout.addStretch()

        self.iqr_tab = tab

    def _create_lof_tab(self):
        """Create LOF tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)

        # Column selection
        col_layout = QHBoxLayout()
        self.lof_col = ColumnSelector(self.original_df)
        self.lof_col.set_label("Source Column:")
        col_layout.addWidget(self.lof_col)
        layout.addLayout(col_layout)

        # Parameters
        params_group = QGroupBox("Parameters")
        params_layout = QGridLayout(params_group)

        # Number of neighbors
        params_layout.addWidget(QLabel("Number of Neighbors:"), 0, 0)
        self.lof_neighbors = QSpinBox()
        self.lof_neighbors.setRange(5, 100)
        self.lof_neighbors.setValue(20)
        params_layout.addWidget(self.lof_neighbors, 0, 1)

        # Threshold
        params_layout.addWidget(QLabel("Outlier Threshold:"), 1, 0)
        self.lof_threshold = QDoubleSpinBox()
        self.lof_threshold.setRange(0.1, 5.0)
        self.lof_threshold.setValue(0.3)
        self.lof_threshold.setSingleStep(0.1)
        params_layout.addWidget(self.lof_threshold, 1, 1)

        layout.addWidget(params_group)
        layout.addStretch()

        self.lof_tab = tab

    def get_method(self) -> str:
        """Get the selected detection method"""
        method_map = {
            0: "iforest",
            1: "zscore",
            2: "iqr",
            3: "lof",
        }
        return method_map.get(self.tabs.currentIndex(), "iforest")

    def get_parameters(self) -> dict:
        """Get the anomaly detection parameters"""
        method = self.get_method()
        anomaly_col = self.anomaly_col_edit.text() or "is_anomaly"
        score_col = self.score_col_edit.text() or "anomaly_score"

        params = {
            "method": method,
            "output_anomaly_col": anomaly_col,
            "output_score_col": score_col,
        }

        if method == "iforest":
            params["column"] = self.iforest_col.get_column()
            params["contamination"] = self.iforest_contamination.value()
            params["n_estimators"] = self.iforest_trees.value()
            params["max_samples"] = self.iforest_max_samples.value()
        elif method == "zscore":
            params["column"] = self.zscore_col.get_column()
            params["threshold"] = self.zscore_threshold.value()
            params["direction"] = self.zscore_direction.currentText()
        elif method == "iqr":
            params["column"] = self.iqr_col.get_column()
            params["multiplier"] = self.iqr_multiplier.value()
            params["mode"] = "extreme" if self.iqr_mode.currentIndex() == 1 else "outer"
        elif method == "lof":
            params["column"] = self.lof_col.get_column()
            params["n_neighbors"] = self.lof_neighbors.value()
            params["threshold"] = self.lof_threshold.value()

        return params

    def validate(self) -> bool:
        """Validate parameters"""
        params = self.get_parameters()
        if not params.get("column"):
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column to analyze.")
            return False
        return True

    def preview(self):
        """Generate preview of anomaly detection"""
        try:
            params = self.get_parameters()
            column = params["column"]
            method = params["method"]

            # Get column data
            col_data = self.original_df[column].to_numpy()
            valid_mask = ~np.isnan(col_data.astype(float))
            valid_data = col_data[valid_mask]

            if len(valid_data) == 0:
                self.stats_label.setStatus("error")
                self.stats_label.setText("No valid numeric data in selected column")
                return

            # Apply detection based on method
            if method == "iforest":
                mean_val = np.mean(valid_data)
                std_val = np.std(valid_data)
                if std_val == 0:
                    std_val = 1
                distances = np.abs(valid_data - mean_val) / std_val
                threshold = 2.5
                is_anomaly = distances > threshold
                scores = 1 - (1 / (1 + distances))

            elif method == "zscore":
                mean_val = np.mean(valid_data)
                std_val = np.std(valid_data)
                if std_val == 0:
                    std_val = 1
                zscore = (valid_data - mean_val) / std_val
                direction = params.get("direction", "Both")

                if direction == "Above Mean Only":
                    is_anomaly = zscore > params["threshold"]
                elif direction == "Below Mean Only":
                    is_anomaly = zscore < -params["threshold"]
                else:
                    is_anomaly = np.abs(zscore) > params["threshold"]
                scores = np.abs(zscore)

            elif method == "iqr":
                Q1 = np.percentile(valid_data, 25)
                Q3 = np.percentile(valid_data, 75)
                IQR = Q3 - Q1
                mode = params.get("mode", "outer")
                multiplier = params["multiplier"]
                if mode == "extreme":
                    multiplier = multiplier * 2

                lower_bound = Q1 - multiplier * IQR
                upper_bound = Q3 + multiplier * IQR
                is_anomaly = (valid_data < lower_bound) | (valid_data > upper_bound)

                distances = np.zeros_like(valid_data, dtype=float)
                distances[valid_data < lower_bound] = lower_bound - valid_data[valid_data < lower_bound]
                distances[valid_data > upper_bound] = valid_data[valid_data > upper_bound] - upper_bound
                scores = distances / max(IQR, 1)

            elif method == "lof":
                mean_val = np.mean(valid_data)
                distances = np.abs(valid_data - mean_val)
                max_dist = np.max(distances)
                if max_dist == 0:
                    max_dist = 1
                scores = 1 - (distances / max_dist)
                is_anomaly = scores < params["threshold"]

            # Count anomalies
            n_anomalies = np.sum(is_anomaly)
            total = len(is_anomaly)
            percentage = (n_anomalies / total * 100) if total > 0 else 0

            # Show stats
            self.stats_label.setStatus("warning" if n_anomalies > 0 else "success")
            self.stats_label.setText(
                f"Total rows: {total:,} | Anomalies found: {n_anomalies:,} ({percentage:.1f}%)"
            )

            # Show sample anomalies
            anomaly_indices = np.where(is_anomaly)[0][:10]
            if len(anomaly_indices) > 0:
                preview_df = self.original_df[anomaly_indices].select([column]).clone()
                preview_df = preview_df.with_columns(
                    pl.Series(name="Anomaly Score", values=scores[anomaly_indices])
                )
                self.preview_table.load_dataframe(preview_df)
            else:
                self.preview_table.clear()

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

    def apply_detection(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply anomaly detection to dataframe"""
        params = self.get_parameters()
        column = params["column"]
        method = params["method"]
        output_anomaly = params["output_anomaly_col"]
        output_score = params["output_score_col"]

        col_data = df[column].to_numpy()
        valid_mask = ~np.isnan(col_data.astype(float))
        valid_data = col_data[valid_mask]

        if len(valid_data) == 0:
            return df.with_columns([
                pl.lit(False).alias(output_anomaly),
                pl.lit(0.0).alias(output_score)
            ])

        # Apply detection
        if method == "iforest":
            mean_val = np.mean(valid_data)
            std_val = np.std(valid_data)
            if std_val == 0:
                std_val = 1
            distances = np.abs(valid_data - mean_val) / std_val
            threshold = 2.5
            is_anomaly = distances > threshold
            scores = 1 - (1 / (1 + distances))

        elif method == "zscore":
            mean_val = np.mean(valid_data)
            std_val = np.std(valid_data)
            if std_val == 0:
                std_val = 1
            zscore = (valid_data - mean_val) / std_val
            scores = np.abs(zscore)
            direction = params.get("direction", "Both")

            if direction == "Above Mean Only":
                is_anomaly = zscore > params["threshold"]
            elif direction == "Below Mean Only":
                is_anomaly = zscore < -params["threshold"]
            else:
                is_anomaly = np.abs(zscore) > params["threshold"]

        elif method == "iqr":
            Q1 = np.percentile(valid_data, 25)
            Q3 = np.percentile(valid_data, 75)
            IQR = Q3 - Q1
            multiplier = params["multiplier"]
            lower_bound = Q1 - multiplier * IQR
            upper_bound = Q3 + multiplier * IQR
            is_anomaly = (valid_data < lower_bound) | (valid_data > upper_bound)

            distances = np.zeros_like(valid_data, dtype=float)
            distances[valid_data < lower_bound] = lower_bound - valid_data[valid_data < lower_bound]
            distances[valid_data > upper_bound] = valid_data[valid_data > upper_bound] - upper_bound
            scores = distances / max(IQR, 1)

        elif method == "lof":
            mean_val = np.mean(valid_data)
            distances = np.abs(valid_data - mean_val)
            max_dist = np.max(distances)
            if max_dist == 0:
                max_dist = 1
            scores = 1 - (distances / max_dist)
            is_anomaly = scores < params["threshold"]

        # Create result columns
        anomaly_series = np.full(len(df), False, dtype=bool)
        score_series = np.full(len(df), 0.0, dtype=float)

        anomaly_series[valid_mask] = is_anomaly
        score_series[valid_mask] = scores

        return df.with_columns([
            pl.Series(name=output_anomaly, values=anomaly_series),
            pl.Series(name=output_score, values=score_series)
        ])
