"""Supervised Learning Dialog for ML operations"""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QListWidget, QCheckBox, QMessageBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QFormLayout, QFrame,
    QScrollArea, QWidget
)
from PySide6.QtCore import Signal


class MLSupervisedDialog(QDialog):
    """Dialog for supervised ML operations (regression and classification)"""

    transform_requested = Signal(str, dict)  # operation_id, params

    # Algorithm definitions with all hyperparameters
    ALGORITHMS = {
        "Linear Regression": {
            "id": "ml_linear_regression",
            "type": "regression",
            "params": ["features", "target", "output_column", "fit_intercept"],
            "hyperparams": {
                "fit_intercept": {"type": "bool", "default": True, "label": "Fit Intercept"}
            },
            "description": "Predict continuous values using linear regression"
        },
        "GLM": {
            "id": "ml_glm",
            "type": "regression",
            "params": ["features", "target", "output_column", "family"],
            "hyperparams": {
                "family": {"type": "combo", "options": ["gaussian", "binomial", "poisson", "gamma"],
                          "default": "gaussian", "label": "Family"}
            },
            "description": "Generalized Linear Models"
        },
        "Decision Tree": {
            "id": "ml_decision_tree",
            "type": "both",
            "params": ["features", "target", "output_column", "max_depth", "min_samples_split", "min_samples_leaf"],
            "hyperparams": {
                "max_depth": {"type": "spin", "min": 1, "max": 100, "default": 10, "label": "Max Depth"},
                "min_samples_split": {"type": "spin", "min": 2, "max": 1000, "default": 2, "label": "Min Samples Split"},
                "min_samples_leaf": {"type": "spin", "min": 1, "max": 500, "default": 1, "label": "Min Samples Leaf"}
            },
            "description": "Tree-based classification/regression"
        },
        "Random Forest": {
            "id": "ml_random_forest",
            "type": "both",
            "params": ["features", "target", "output_column", "n_estimators", "max_depth", "min_samples_split", "min_samples_leaf"],
            "hyperparams": {
                "n_estimators": {"type": "spin", "min": 10, "max": 500, "default": 100, "label": "Number of Trees"},
                "max_depth": {"type": "spin", "min": 1, "max": 100, "default": 10, "label": "Max Depth"},
                "min_samples_split": {"type": "spin", "min": 2, "max": 1000, "default": 2, "label": "Min Samples Split"},
                "min_samples_leaf": {"type": "spin", "min": 1, "max": 500, "default": 1, "label": "Min Samples Leaf"}
            },
            "description": "Ensemble of decision trees"
        },
        "Gradient Boosting": {
            "id": "ml_gradient_boosting",
            "type": "both",
            "params": ["features", "target", "output_column", "n_estimators", "learning_rate", "max_depth", "min_samples_split", "min_samples_leaf"],
            "hyperparams": {
                "n_estimators": {"type": "spin", "min": 10, "max": 500, "default": 100, "label": "Number of Estimators"},
                "learning_rate": {"type": "double", "min": 0.01, "max": 1.0, "step": 0.01, "default": 0.1, "label": "Learning Rate"},
                "max_depth": {"type": "spin", "min": 1, "max": 20, "default": 5, "label": "Max Depth"},
                "min_samples_split": {"type": "spin", "min": 2, "max": 1000, "default": 2, "label": "Min Samples Split"},
                "min_samples_leaf": {"type": "spin", "min": 1, "max": 500, "default": 1, "label": "Min Samples Leaf"}
            },
            "description": "Sequential ensemble boosting"
        },
        "XGBoost": {
            "id": "ml_xgboost",
            "type": "both",
            "params": ["features", "target", "output_column", "n_estimators", "learning_rate", "max_depth", "subsample", "colsample_bytree"],
            "hyperparams": {
                "n_estimators": {"type": "spin", "min": 10, "max": 500, "default": 100, "label": "Number of Trees"},
                "learning_rate": {"type": "double", "min": 0.01, "max": 1.0, "step": 0.01, "default": 0.1, "label": "Learning Rate"},
                "max_depth": {"type": "spin", "min": 1, "max": 20, "default": 6, "label": "Max Depth"},
                "subsample": {"type": "double", "min": 0.1, "max": 1.0, "step": 0.05, "default": 0.8, "label": "Subsample"},
                "colsample_bytree": {"type": "double", "min": 0.1, "max": 1.0, "step": 0.05, "default": 0.8, "label": "Column Sample by Tree"}
            },
            "description": "Extreme Gradient Boosting"
        },
        "LightGBM": {
            "id": "ml_lightgbm",
            "type": "both",
            "params": ["features", "target", "output_column", "n_estimators", "learning_rate", "num_leaves", "min_child_samples"],
            "hyperparams": {
                "n_estimators": {"type": "spin", "min": 10, "max": 500, "default": 100, "label": "Number of Leaves"},
                "learning_rate": {"type": "double", "min": 0.01, "max": 1.0, "step": 0.01, "default": 0.1, "label": "Learning Rate"},
                "num_leaves": {"type": "spin", "min": 2, "max": 200, "default": 31, "label": "Number of Leaves"},
                "min_child_samples": {"type": "spin", "min": 1, "max": 500, "default": 20, "label": "Min Child Samples"}
            },
            "description": "Light Gradient Boosting Machine"
        }
    }

    def __init__(self, df: pl.DataFrame, parent=None):
        super().__init__(parent)
        self.df = df
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Supervised Learning")
        self.setMinimumSize(650, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #f9fafb;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f9fafb;
            }
        """)

        # Content widget
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #f9fafb;")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        title_layout = QHBoxLayout()
        title_icon = QLabel("🤖")
        title_icon.setStyleSheet("font-size: 24px;")
        title_layout.addWidget(title_icon)

        title = QLabel("Supervised Learning")
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
        algo_group = QGroupBox("Algorithm")
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

        self.algo_desc = QLabel("Predict continuous values using linear regression")
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

        # Target column
        self.target_combo = QComboBox()
        self.target_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 13px;
            }
        """)
        for col in self.df.columns:
            self.target_combo.addItem(col)
        params_layout.addRow("Target Column:", self.target_combo)

        # Features list
        self.features_list = QListWidget()
        self.features_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px;
                min-height: 80px;
            }
        """)
        self.features_list.setSelectionMode(QListWidget.ExtendedSelection)
        for col in self.df.columns:
            self.features_list.addItem(col)
        params_layout.addRow("Features:", self.features_list)

        # Output column
        self.output_edit = QLineEdit("prediction")
        self.output_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 13px;
            }
        """)
        params_layout.addRow("Output Column:", self.output_edit)

        # Algorithm-specific parameters (hyperparameters)
        self.hyper_params_frame = QFrame()
        self.hyper_params_layout = QFormLayout(self.hyper_params_frame)
        params_layout.addRow("Hyperparameters:", self.hyper_params_frame)

        layout.addWidget(params_group)

        # Set content widget
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Button bar at bottom
        button_bar = QFrame()
        button_bar.setStyleSheet("""
            QFrame {
                background-color: #f3f4f6;
                border-top: 1px solid #e5e7eb;
                padding: 10px;
            }
        """)
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(20, 5, 20, 5)

        button_layout.addStretch()

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                padding: 10px 24px;
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
                padding: 10px 24px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        main_layout.addWidget(button_bar)

        # Initialize algorithm parameters
        self.hyper_widgets = {}
        self._on_algo_changed(0)

    def _on_algo_changed(self, index: int):
        """Handle algorithm selection change"""
        algo_name = self.algo_combo.currentText()
        algo_info = self.ALGORITHMS[algo_name]

        # Update description
        self.algo_desc.setText(algo_info["description"])

        # Clear and rebuild algorithm-specific parameters
        while self.hyper_params_layout.count():
            item = self.hyper_params_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.hyper_widgets = {}

        hyperparams = algo_info.get("hyperparams", {})

        for param_name, param_config in hyperparams.items():
            label = param_config.get("label", param_name)
            param_type = param_config.get("type", "spin")

            if param_type == "bool":
                widget = QCheckBox()
                widget.setChecked(param_config.get("default", True))
                self.hyper_params_layout.addRow(label + ":", widget)
                self.hyper_widgets[param_name] = widget

            elif param_type == "spin":
                widget = QSpinBox()
                widget.setRange(param_config.get("min", 0), param_config.get("max", 100))
                widget.setValue(param_config.get("default", 10))
                self.hyper_params_layout.addRow(label + ":", widget)
                self.hyper_widgets[param_name] = widget

            elif param_type == "double":
                widget = QDoubleSpinBox()
                widget.setRange(param_config.get("min", 0.0), param_config.get("max", 1.0))
                widget.setSingleStep(param_config.get("step", 0.01))
                widget.setValue(param_config.get("default", 0.1))
                self.hyper_params_layout.addRow(label + ":", widget)
                self.hyper_widgets[param_name] = widget

            elif param_type == "combo":
                widget = QComboBox()
                for opt in param_config.get("options", []):
                    widget.addItem(opt)
                widget.setCurrentText(param_config.get("default", "gaussian"))
                self.hyper_params_layout.addRow(label + ":", widget)
                self.hyper_widgets[param_name] = widget

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

        # Get target
        target_col = self.target_combo.currentText()

        # Build params
        params = {
            "features": selected_features,
            "target": target_col,
            "output_column": self.output_edit.text().strip() or "prediction"
        }

        # Add algorithm-specific hyperparams
        for key, widget in self.hyper_widgets.items():
            if isinstance(widget, QCheckBox):
                params[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QComboBox):
                params[key] = widget.currentText()

        # Emit signal
        self.transform_requested.emit(algo_id, params)
        self.accept()
