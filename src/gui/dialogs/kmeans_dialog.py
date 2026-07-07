"""
K-Means Clustering Dialog for CAATmaster
Configure K-Means clustering parameters with elbow method visualization
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QSlider, QWidget, QMessageBox, QLineEdit, QRadioButton, QButtonGroup,
    QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

from ..components.common_modals import (
    BaseModal, PreviewTable, MultiColumnSelector, ElbowMethodChart, StatusLabel, create_primary_button
)


class KMeansDialog(BaseModal):
    """
    K-Means Clustering dialog with elbow method and preview
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("K-Means Clustering", dataframe, parent)
        self.setMinimumSize(800, 700)

    def _setup_ui(self):
        """Setup the K-Means dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Feature columns selection
        features_group = QGroupBox("Feature Columns (Numeric)")
        features_layout = QVBoxLayout(features_group)

        self.features_selector = MultiColumnSelector(self.original_df)
        self.features_selector.set_label("Select columns for clustering:")
        self.features_selector.columnsSelected.connect(self._on_features_changed)
        features_layout.addWidget(self.features_selector)

        layout.addWidget(features_group)

        # K value selection
        k_group = QGroupBox("Number of Clusters (K)")
        k_layout = QGridLayout(k_group)

        k_layout.addWidget(QLabel("K Value:"), 0, 0)
        self.k_slider = QSlider(Qt.Horizontal)
        self.k_slider.setRange(2, 10)
        self.k_slider.setValue(3)
        self.k_slider.valueChanged.connect(self._on_k_changed)
        k_layout.addWidget(self.k_slider, 0, 1)

        self.k_label = QLabel("3")
        self.k_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        k_layout.addWidget(self.k_label, 0, 2)

        # Elbow chart
        k_layout.addWidget(QLabel("Elbow Method:"), 1, 0)
        self.elbow_chart = ElbowMethodChart()
        k_layout.addWidget(self.elbow_chart, 1, 1, 1, 2)

        # Run elbow analysis button
        self.elbow_btn = QPushButton("Find Optimal K (Run Elbow Analysis)")
        self.elbow_btn.clicked.connect(self._run_elbow_analysis)
        k_layout.addWidget(self.elbow_btn, 2, 0, 1, 3)

        layout.addWidget(k_group)

        # Advanced options
        advanced_group = QGroupBox("Advanced Options")
        advanced_layout = QGridLayout(advanced_group)

        # Initialization method
        advanced_layout.addWidget(QLabel("Initialization:"), 0, 0)
        self.init_combo = QComboBox()
        self.init_combo.addItems(["k-means++", "random"])
        advanced_layout.addWidget(self.init_combo, 0, 1)

        # Max iterations
        advanced_layout.addWidget(QLabel("Max Iterations:"), 1, 0)
        self.max_iter_spin = QSpinBox()
        self.max_iter_spin.setRange(10, 1000)
        self.max_iter_spin.setValue(300)
        advanced_layout.addWidget(self.max_iter_spin, 1, 1)

        # Random seed
        advanced_layout.addWidget(QLabel("Random Seed:"), 2, 0)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(42)
        advanced_layout.addWidget(self.seed_spin, 2, 1)

        # Normalize data
        self.normalize_check = QCheckBox("Normalize data (StandardScaler)")
        self.normalize_check.setChecked(True)
        advanced_layout.addWidget(self.normalize_check, 3, 0, 1, 2)

        layout.addWidget(advanced_group)

        # Output columns
        output_group = QGroupBox("Output Columns")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Cluster Column:"), 0, 0)
        self.cluster_col_edit = QLineEdit("cluster")
        output_layout.addWidget(self.cluster_col_edit, 0, 1)

        output_layout.addWidget(QLabel("Distance Column:"), 1, 0)
        self.distance_col_edit = QLineEdit("distance_to_center")
        output_layout.addWidget(self.distance_col_edit, 1, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview (First 10 Rows)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        # Cluster distribution
        self.cluster_stats = StatusLabel("No data previewed")
        preview_layout.addWidget(self.cluster_stats)

        layout.addWidget(preview_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.run_btn = create_primary_button("Run Clustering")
        self.run_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.run_btn)

        layout.addLayout(btn_layout)

    def _on_k_changed(self, value):
        """Handle K value change"""
        self.k_label.setText(str(value))
        self._update_elbow_highlight(value)

    def _on_features_changed(self, columns: List[str]):
        """Handle feature selection change"""
        pass  # Will be updated on preview

    def _run_elbow_analysis(self):
        """Run elbow method analysis to find optimal K"""
        selected = self.features_selector.get_selected_columns()
        if len(selected) < 2:
            QMessageBox.warning(self, "Warning",
                              "Please select at least 2 columns for elbow analysis.")
            return

        try:
            # Get numeric data
            numeric_df = self.original_df.select(selected)
            numeric_data = numeric_df.to_numpy()
            valid_mask = ~np.isnan(numeric_data.astype(float))
            valid_data = numeric_data[valid_mask].reshape(-1, len(selected))

            if len(valid_data) < 10:
                QMessageBox.warning(self, "Warning",
                                  "Not enough valid data for analysis.")
                return

            # Normalize if needed
            if self.normalize_check.isChecked():
                mean = np.mean(valid_data, axis=0)
                std = np.std(valid_data, axis=0)
                std[std == 0] = 1
                valid_data = (valid_data - mean) / std

            # Run K-Means for K=2 to 10
            k_range = range(2, 11)
            inertias = []

            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(2, 10)
            self.progress_bar.setValue(2)

            for k in k_range:
                from sklearn.cluster import KMeans
                kmeans = KMeans(n_clusters=k, init='k-means++', n_init=10,
                               max_iter=300, random_state=42)
                kmeans.fit(valid_data)
                inertias.append(kmeans.inertia_)

                self.progress_bar.setValue(k)
                QApplication.processEvents()

            self.progress_bar.setVisible(False)

            # Update chart
            self.elbow_chart.set_data(list(k_range), inertias)
            self.elbow_chart.setVisible(True)

        except ImportError:
            QMessageBox.warning(self, "Missing Dependency",
                              "scikit-learn is required for elbow analysis.\n"
                              "Install with: pip install scikit-learn")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Elbow analysis failed:\n{str(e)}")

    def _update_elbow_highlight(self, k):
        """Highlight the selected K on the elbow chart"""
        self.elbow_chart.set_highlighted_k(k)

    def get_parameters(self) -> dict:
        """Get the K-Means parameters"""
        return {
            "features": self.features_selector.get_selected_columns(),
            "k": self.k_slider.value(),
            "initialization": self.init_combo.currentText(),
            "max_iterations": self.max_iter_spin.value(),
            "seed": self.seed_spin.value(),
            "normalize": self.normalize_check.isChecked(),
            "output_cluster_col": self.cluster_col_edit.text() or "cluster",
            "output_distance_col": self.distance_col_edit.text() or "distance_to_center",
        }

    def validate(self) -> bool:
        """Validate parameters"""
        params = self.get_parameters()
        features = params["features"]

        if len(features) < 2:
            QMessageBox.warning(self, "Validation Error",
                              "Please select at least 2 columns for clustering.")
            return False

        if len(features) > 20:
            QMessageBox.warning(self, "Validation Error",
                              "Maximum 20 columns allowed for clustering.")
            return False

        return True

    def preview(self):
        """Generate preview of clustering"""
        try:
            params = self.get_parameters()
            features = params["features"]
            k = params["k"]

            if len(features) < 2:
                self.cluster_stats.setStatus("error")
                self.cluster_stats.setText("Select at least 2 columns")
                return

            # Get numeric data
            numeric_df = self.original_df.select(features)
            numeric_data = numeric_df.to_numpy()
            valid_mask = ~np.isnan(numeric_data.astype(float))

            if np.sum(valid_mask) == 0:
                self.cluster_stats.setStatus("error")
                self.cluster_stats.setText("No valid numeric data")
                return

            # Apply K-Means
            from sklearn.cluster import KMeans

            valid_data = numeric_data[valid_mask].reshape(-1, len(features))

            # Normalize if needed
            if params["normalize"]:
                mean = np.mean(valid_data, axis=0)
                std = np.std(valid_data, axis=0)
                std[std == 0] = 1
                valid_data = (valid_data - mean) / std

            # Fit K-Means
            kmeans = KMeans(
                n_clusters=k,
                init=params["initialization"],
                n_init=10,
                max_iter=params["max_iterations"],
                random_state=params["seed"]
            )
            labels = kmeans.fit_predict(valid_data)
            distances = kmeans.transform(valid_data).min(axis=1)

            # Create preview dataframe
            preview_df = self.original_df[valid_mask][:20].clone()
            preview_df = preview_df.with_columns([
                pl.Series(name=params["output_cluster_col"], values=labels),
                pl.Series(name=params["output_distance_col"], values=distances)
            ])

            self.preview_table.load_dataframe(preview_df)

            # Update stats
            unique, counts = np.unique(labels, return_counts=True)
            cluster_dist = ", ".join([f"C{c}:{cnt}" for c, cnt in zip(unique, counts)])
            self.cluster_stats.setStatus("success")
            self.cluster_stats.setText(f"K={k} | Distribution: {cluster_dist}")

        except ImportError:
            QMessageBox.warning(self, "Missing Dependency",
                              "scikit-learn is required for K-Means clustering.\n"
                              "Install with: pip install scikit-learn")
        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")

    def apply_clustering(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply K-Means clustering to dataframe"""
        params = self.get_parameters()
        features = params["features"]
        k = params["k"]

        # Get numeric data
        numeric_df = df.select(features)
        numeric_data = numeric_df.to_numpy()
        valid_mask = ~np.isnan(numeric_data.astype(float))
        valid_data = numeric_data[valid_mask].reshape(-1, len(features))

        if len(valid_data) == 0:
            return df.with_columns([
                pl.lit(0).alias(params["output_cluster_col"]),
                pl.lit(0.0).alias(params["output_distance_col"])
            ])

        # Normalize if needed
        if params["normalize"]:
            mean = np.mean(valid_data, axis=0)
            std = np.std(valid_data, axis=0)
            std[std == 0] = 1
            valid_data = (valid_data - mean) / std

        # Fit K-Means
        from sklearn.cluster import KMeans
        kmeans = KMeans(
            n_clusters=k,
            init=params["initialization"],
            n_init=10,
            max_iter=params["max_iterations"],
            random_state=params["seed"]
        )
        labels = kmeans.fit_predict(valid_data)
        distances = kmeans.transform(valid_data).min(axis=1)

        # Create result columns
        cluster_series = np.full(len(df), 0, dtype=int)
        distance_series = np.full(len(df), 0.0, dtype=float)

        cluster_series[valid_mask] = labels
        distance_series[valid_mask] = distances

        return df.with_columns([
            pl.Series(name=params["output_cluster_col"], values=cluster_series),
            pl.Series(name=params["output_distance_col"], values=distance_series)
        ])
