"""Unsupervised Learning Dialog for clustering and anomaly detection"""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QListWidget, QMessageBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QFormLayout, QFrame
)
from PySide6.QtCore import Signal


class MLUnsupervisedDialog(QDialog):
    """Dialog for unsupervised ML operations (clustering)"""

    transform_requested = Signal(str, dict)  # operation_id, params

    # Algorithm definitions
    ALGORITHMS = {
        "K-Means": {
            "id": "ml_cluster",
            "params": ["features", "output_column", "n_clusters"],
            "description": "Partition data into K clusters",
            "default_params": {"n_clusters": 3}
        },
        "DBSCAN": {
            "id": "ml_dbscan",
            "params": ["features", "output_column", "eps", "min_samples"],
            "description": "Density-based spatial clustering",
            "default_params": {"eps": 0.5, "min_samples": 5}
        },
        "Gaussian Mixture": {
            "id": "ml_gmm",
            "params": ["features", "output_column", "n_components"],
            "description": "Probabilistic clustering with Gaussian mixtures",
            "default_params": {"n_components": 3}
        }
    }

    def __init__(self, df: pl.DataFrame, parent=None):
        super().__init__(parent)
        self.df = df
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Unsupervised Learning - Clustering")
        self.setMinimumSize(550, 450)
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
        title_icon = QLabel("◈")
        title_icon.setStyleSheet("font-size: 24px;")
        title_layout.addWidget(title_icon)

        title = QLabel("Unsupervised Learning")
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
        algo_group = QGroupBox("Clustering Algorithm")
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

        self.algo_desc = QLabel("Partition data into K clusters")
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

        # Features list
        self.features_list = QListWidget()
        self.features_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px;
                min-height: 100px;
            }
        """)
        self.features_list.setSelectionMode(QListWidget.ExtendedSelection)
        for col in self.df.columns:
            # Only add numeric columns for clustering
            col_dtype = self.df[col].dtype
            if col_dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32):
                self.features_list.addItem(col)
        params_layout.addRow("Features (numeric only):", self.features_list)

        # Output column
        self.output_edit = QLineEdit("cluster")
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
        defaults = algo_info.get("default_params", {})

        # Add algorithm-specific parameters
        if algo_id == "ml_cluster":
            self.n_clusters_spin = QSpinBox()
            self.n_clusters_spin.setRange(2, 20)
            self.n_clusters_spin.setValue(defaults.get("n_clusters", 3))
            self.algo_params_layout.addRow("Number of Clusters:", self.n_clusters_spin)
            self.algo_widgets["n_clusters"] = self.n_clusters_spin

        elif algo_id == "ml_dbscan":
            self.eps_spin = QDoubleSpinBox()
            self.eps_spin.setRange(0.01, 100.0)
            self.eps_spin.setSingleStep(0.1)
            self.eps_spin.setValue(defaults.get("eps", 0.5))
            self.algo_params_layout.addRow("Epsilon (neighborhood):", self.eps_spin)
            self.algo_widgets["eps"] = self.eps_spin

            self.min_samples_spin = QSpinBox()
            self.min_samples_spin.setRange(1, 100)
            self.min_samples_spin.setValue(defaults.get("min_samples", 5))
            self.algo_params_layout.addRow("Min Samples:", self.min_samples_spin)
            self.algo_widgets["min_samples"] = self.min_samples_spin

        elif algo_id == "ml_gmm":
            self.n_components_spin = QSpinBox()
            self.n_components_spin.setRange(2, 20)
            self.n_components_spin.setValue(defaults.get("n_components", 3))
            self.algo_params_layout.addRow("Number of Components:", self.n_components_spin)
            self.algo_widgets["n_components"] = self.n_components_spin

    def _on_apply(self):
        """Apply the selected ML operation"""
        algo_name = self.algo_combo.currentText()
        algo_info = self.ALGORITHMS[algo_name]
        algo_id = algo_info["id"]

        # Get selected features
        selected_features = [item.text() for item in self.features_list.selectedItems()]
        if not selected_features:
            QMessageBox.warning(self, "No Features", "Please select at least one feature column.")
            return

        # Build params
        params = {
            "features": selected_features,
            "output_column": self.output_edit.text().strip() or "cluster"
        }

        # Add algorithm-specific params
        for key, widget in self.algo_widgets.items():
            if isinstance(widget, QSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                params[key] = widget.value()

        # Emit signal
        self.transform_requested.emit(algo_id, params)
        self.accept()
