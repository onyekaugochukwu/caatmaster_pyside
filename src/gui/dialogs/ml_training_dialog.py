"""
ML Model Training Dialog
Dialog for configuring and training ML models that can be used in the pipeline.
"""

import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
    QLabel, QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QGroupBox, QHBoxLayout, QPushButton, QProgressBar, QTextEdit,
    QScrollArea, QFrame, QWidget
)
from PySide6.QtCore import Qt, Signal, Slot
from typing import Dict, Any, List, Optional


class MLTrainingDialog(QDialog):
    """
    Dialog for configuring ML model training operations.
    Supports training models that can be saved and reused in the pipeline.
    """

    # Signal emitted when training is complete
    trainingComplete = Signal(str, dict)  # model_id, training_metrics

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        super().__init__(parent if parent else None)
        self.dataframe = dataframe
        self.model_id = None
        self.training_metrics = {}

        self.setWindowTitle("Train ML Model")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)

        self.setup_ui()
        self.populate_columns()

    def setup_ui(self):
        """Set up the dialog UI."""
        # Four stacked group boxes (incl. a multi-select feature list and
        # a training-progress/results text box) push this dialog's
        # natural height to ~760px with no scroll area - risking the
        # OK/Cancel buttons landing off-screen on shorter displays or
        # under Windows DPI scaling, the same bug the Benford dialog
        # had. Content goes in a scroll area; the button box stays a
        # fixed footer outside it.
        main_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)

        # Model configuration section
        config_group = QGroupBox("Model Configuration")
        config_layout = QFormLayout(config_group)

        # Model name
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setPlaceholderText("e.g., fraud_detection_v1")
        config_layout.addRow("Model Name:", self.model_name_edit)

        # Algorithm selection
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems([
            "Random Forest",
            "Logistic Regression",
            "SVM",
            "Gradient Boosting",
            "Neural Network"
        ])
        config_layout.addRow("Algorithm:", self.algorithm_combo)

        # Target column
        self.target_combo = QComboBox()
        config_layout.addRow("Target Column:", self.target_combo)

        layout.addWidget(config_group)

        # Feature selection section
        features_group = QGroupBox("Feature Columns")
        features_layout = QVBoxLayout(features_group)

        self.features_list = QListWidget()
        self.features_list.setSelectionMode(QListWidget.MultiSelection)
        features_layout.addWidget(self.features_list)

        # Select/Deselect buttons - explicit min-width so a narrow
        # dialog (or Windows' wider DPI-scaled font metrics) can't
        # force this text below a readable size.
        btn_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setStyleSheet("min-width: 90px; padding: 4px 8px;")
        select_all_btn.clicked.connect(self.select_all_features)
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setStyleSheet("min-width: 100px; padding: 4px 8px;")
        deselect_all_btn.clicked.connect(self.deselect_all_features)

        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        btn_layout.addStretch()
        features_layout.addLayout(btn_layout)

        layout.addWidget(features_group)

        # Training parameters section
        params_group = QGroupBox("Training Parameters")
        params_layout = QFormLayout(params_group)

        # Test split ratio
        self.test_split_edit = QLineEdit("0.2")
        params_layout.addRow("Test Split Ratio:", self.test_split_edit)

        # Random seed
        self.random_seed_edit = QLineEdit("42")
        params_layout.addRow("Random Seed:", self.random_seed_edit)

        layout.addWidget(params_group)

        # Progress and results section
        results_group = QGroupBox("Training Progress")
        results_layout = QVBoxLayout(results_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        results_layout.addWidget(self.progress_bar)

        self.results_text = QTextEdit()
        self.results_text.setMaximumHeight(150)
        self.results_text.setReadOnly(True)
        results_layout.addWidget(self.results_text)

        layout.addWidget(results_group)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        # Dialog buttons - fixed footer, outside the scroll area
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def populate_columns(self):
        """Populate column selection widgets."""
        columns = self.dataframe.columns

        # Populate target column combo
        self.target_combo.addItems(columns)

        # Populate features list
        for col in columns:
            item = QListWidgetItem(col)
            # Item must be added to the list before setSelected() has any
            # effect — a QListWidgetItem's selection state is tracked by its
            # parent widget's model, so calling setSelected() on a
            # not-yet-added item silently does nothing.
            self.features_list.addItem(item)
            # Auto-select numeric columns as features
            if self.dataframe[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]:
                item.setSelected(True)

    @Slot()
    def select_all_features(self):
        """Select all feature columns."""
        for i in range(self.features_list.count()):
            self.features_list.item(i).setSelected(True)

    @Slot()
    def deselect_all_features(self):
        """Deselect all feature columns."""
        for i in range(self.features_list.count()):
            self.features_list.item(i).setSelected(False)

    def get_parameters(self) -> Dict[str, Any]:
        """
        Get the training parameters from the dialog.

        Returns:
            Dictionary containing training configuration
        """
        # Get selected features
        selected_features = []
        for i in range(self.features_list.count()):
            item = self.features_list.item(i)
            if item.isSelected():
                selected_features.append(item.text())

        # Get target column
        target_column = self.target_combo.currentText()

        # Remove target from features if present
        if target_column in selected_features:
            selected_features.remove(target_column)

        # Build parameters
        params = {
            "model_name": self.model_name_edit.text().strip(),
            "algorithm": self.algorithm_combo.currentText().lower().replace(" ", "_"),
            "features": selected_features,
            "target": target_column,
            "test_split": float(self.test_split_edit.text() or "0.2"),
            "random_seed": int(self.random_seed_edit.text() or "42")
        }

        return params

    def validate_parameters(self) -> bool:
        """
        Validate the training parameters.

        Returns:
            True if parameters are valid, False otherwise
        """
        params = self.get_parameters()

        if not params["model_name"]:
            self.results_text.append("Error: Model name is required")
            return False

        if not params["features"]:
            self.results_text.append("Error: At least one feature column must be selected")
            return False

        if not params["target"]:
            self.results_text.append("Error: Target column must be selected")
            return False

        if params["target"] in params["features"]:
            self.results_text.append("Warning: Target column was removed from features")

        return True

    def accept(self):
        """Handle dialog acceptance with validation."""
        if self.validate_parameters():
            super().accept()
        # Don't close dialog if validation fails