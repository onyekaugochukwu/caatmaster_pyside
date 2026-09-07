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
    QWidget, QMessageBox, QTabWidget, QWidget, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer

from ..components.common_modals import (
    BaseModal, PreviewTable, NumberInput, ColumnSelector, StatusLabel, create_primary_button
)
from ..theme import Colors


class AnomalyDetectionDialog(BaseModal):
    """
    Anomaly Detection dialog with multiple method options
    """

    # Every one of the four "ml_anomaly_*" operation ids maps to this
    # same dialog class (see TransformationDialogFactory.DIALOG_MAPPING) -
    # this tells __init__ which tab actually corresponds to the specific
    # one the user picked, whether from the right-click "Machine
    # Learning" submenu or the top menu bar's ML > Anomaly Detection
    # submenu. Without it, choosing "Local Outlier Factor" by name still
    # opened on the Isolation Forest tab every time.
    _TAB_BY_OPERATION_ID = {
        "ml_anomaly_iforest": 0,
        "ml_anomaly_zscore": 1,
        "ml_anomaly_iqr": 2,
        "ml_anomaly_lof": 3,
    }

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None,
                 operation_id: str = None):
        self.original_df = dataframe
        super().__init__("Anomaly Detection", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(700, 650)
        if operation_id in self._TAB_BY_OPERATION_ID:
            self.tabs.setCurrentIndex(self._TAB_BY_OPERATION_ID[operation_id])
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

        # Method selection tabs - styling inherited from the app-wide
        # QTabWidget rule in theme.py.
        self.tabs = QTabWidget()

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

        # Output columns - read-only, since every method here always names
        # its own output columns from the source column
        # ({column}_is_anomaly, {column}_zscore, ...), the same convention
        # every other operation in this application uses. Earlier versions
        # of this box were editable QLineEdits that fed only this dialog's
        # own dead apply_detection() method - a reviewer could type a
        # custom name here, watch it appear to accept the change, and get
        # the default name anyway once Run Detection actually applied the
        # operation. These labels show the real name instead of promising
        # a rename that never happened.
        output_group = QGroupBox("Output Columns")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Anomaly Flag Column:"), 0, 0)
        self.output_flag_label = QLabel("-")
        output_layout.addWidget(self.output_flag_label, 0, 1)

        output_layout.addWidget(QLabel("Score Column:"), 1, 0)
        self.output_score_label = QLabel("-")
        output_layout.addWidget(self.output_score_label, 1, 1)

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

        self.run_btn = create_primary_button("Run Detection")
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

        # Contamination - same meaning as the Isolation Forest tab's own
        # Contamination control above, so the two behave predictably the
        # same way when left at their defaults.
        params_layout.addWidget(QLabel("Contamination:"), 1, 0)
        self.lof_contamination = QDoubleSpinBox()
        self.lof_contamination.setRange(0.01, 0.5)
        self.lof_contamination.setValue(0.1)
        self.lof_contamination.setSingleStep(0.01)
        self.lof_contamination.setSuffix(" (1-50%)")
        params_layout.addWidget(self.lof_contamination, 1, 1)

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
        """The parameters actually sent to DataProcessor - both for this
        dialog's own preview() below and, via
        TransformView.apply_transformation, for the real applied
        operation. One dict feeds both, by construction, so a preview can
        no longer promise a result the real run does not deliver, the way
        an earlier version of this dialog did: its own preview()
        recomputed every method as a local distance-from-mean heuristic
        while the real applied operation called scikit-learn directly, and
        its "Direction" and "Detection Mode" dropdowns adjusted only that
        local preview, silently doing nothing to the value actually
        written to the dataset once Run Detection was clicked."""
        method = self.get_method()
        params = {"method": method}

        if method == "iforest":
            params["column"] = self.iforest_col.get_column()
            params["contamination"] = self.iforest_contamination.value()
            params["n_estimators"] = self.iforest_trees.value()
            max_samples_value = self.iforest_max_samples.value()
            params["max_samples"] = "auto" if max_samples_value == 0 else max_samples_value
        elif method == "zscore":
            params["column"] = self.zscore_col.get_column()
            params["threshold"] = self.zscore_threshold.value()
            direction_map = {"Both": "both", "Above Mean Only": "above", "Below Mean Only": "below"}
            params["direction"] = direction_map.get(self.zscore_direction.currentText(), "both")
        elif method == "iqr":
            params["column"] = self.iqr_col.get_column()
            base_multiplier = self.iqr_multiplier.value()
            # "Extreme Bounds" is a preset that doubles the multiplier
            # rather than a separate parameter - ml_anomaly_iqr only ever
            # took one multiplier, so folding the preset in here keeps
            # that single value the one truth both preview and apply share,
            # instead of two controls that could disagree.
            params["multiplier"] = base_multiplier * 2 if self.iqr_mode.currentIndex() == 1 else base_multiplier
        elif method == "lof":
            params["column"] = self.lof_col.get_column()
            params["n_neighbors"] = self.lof_neighbors.value()
            params["contamination"] = self.lof_contamination.value()

        return params

    def validate(self) -> bool:
        """Validate parameters"""
        params = self.get_parameters()
        if not params.get("column"):
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column to analyze.")
            return False
        return True

    # The real output column names each method actually creates - the
    # same convention DataProcessor uses everywhere, {column}_suffix.
    _OUTPUT_COLUMNS = {
        "iforest": ("_is_anomaly", "_anomaly_score"),
        "zscore": ("_is_outlier", "_zscore"),
        "iqr": ("_is_outlier", "_iqr_distance"),
        "lof": ("_is_outlier", "_lof_score"),
    }

    def preview(self):
        """Generate a preview by calling the exact same DataProcessor
        method, with the exact same parameters, that Run Detection will
        call to actually apply the operation - see get_parameters()'s
        docstring for why that used not to be true."""
        from core.data_processor import DataProcessor

        try:
            params = self.get_parameters()
            column = params.get("column")
            method = params["method"]

            if not column:
                self.stats_label.setStatus("error")
                self.stats_label.setText("Please select a column to analyze.")
                return

            flag_suffix, score_suffix = self._OUTPUT_COLUMNS[method]
            flag_col = f"{column}{flag_suffix}"
            score_col = f"{column}{score_suffix}"

            processor = DataProcessor()
            if method == "iforest":
                result = processor.ml_anomaly_iforest(
                    self.original_df, column=column,
                    contamination=params["contamination"],
                    n_estimators=params["n_estimators"],
                    max_samples=params["max_samples"],
                )
            elif method == "zscore":
                result = processor.ml_anomaly_zscore(
                    self.original_df, column=column,
                    threshold=params["threshold"], direction=params["direction"],
                )
            elif method == "iqr":
                result = processor.ml_anomaly_iqr(
                    self.original_df, column=column, multiplier=params["multiplier"],
                )
            elif method == "lof":
                result = processor.ml_anomaly_lof(
                    self.original_df, column=column,
                    n_neighbors=params["n_neighbors"], contamination=params["contamination"],
                )
            else:
                return

            self.output_flag_label.setText(flag_col)
            self.output_score_label.setText(score_col)

            is_anomaly = result[flag_col].to_numpy()
            scores = result[score_col].to_numpy()
            n_anomalies = int(np.sum(is_anomaly))
            total = len(is_anomaly)
            percentage = (n_anomalies / total * 100) if total > 0 else 0

            self.stats_label.setStatus("warning" if n_anomalies > 0 else "success")
            self.stats_label.setText(
                f"Total rows: {total:,} | Anomalies found: {n_anomalies:,} ({percentage:.1f}%)"
            )

            anomaly_indices = np.where(is_anomaly)[0][:10]
            if len(anomaly_indices) > 0:
                preview_df = self.original_df[anomaly_indices.tolist()].select([column]).clone()
                preview_df = preview_df.with_columns(
                    pl.Series(name="Anomaly Score", values=scores[anomaly_indices])
                )
                self.preview_table.load_dataframe(preview_df)
            else:
                self.preview_table.clear()

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")
