"""
ML Model Inventory View - Manage saved ML models
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QComboBox, QDialog, QFormLayout,
    QLineEdit, QTextEdit, QFileDialog, QProgressDialog
)
from PySide6.QtCore import Qt, Signal
from pathlib import Path


class MLModelInventoryView(QWidget):
    """ML Model management and inventory view"""

    model_selected = Signal(object)  # Signal when model is selected

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ml_model_service = None
        self.current_models = []
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("ML Model Inventory")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Filter by type
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Models", "Anomaly Detection", "Classification", "Clustering"])
        self.filter_combo.currentIndexChanged.connect(self.load_models)
        header_layout.addWidget(QLabel("Filter:"))
        header_layout.addWidget(self.filter_combo)

        main_layout.addLayout(header_layout)

        # Statistics cards
        stats_layout = QHBoxLayout()

        self.total_label = self.create_stat_card("Total Models", "0", "#0078d4")
        stats_layout.addWidget(self.total_label)

        self.anomaly_label = self.create_stat_card("Anomaly Detection", "0", "#28a745")
        stats_layout.addWidget(self.anomaly_label)

        self.classification_label = self.create_stat_card("Classification", "0", "#ff6b35")
        stats_layout.addWidget(self.classification_label)

        self.storage_label = self.create_stat_card("Storage", "0 MB", "#6c757d")
        stats_layout.addWidget(self.storage_label)

        main_layout.addLayout(stats_layout)

        # Models table
        table_group = QGroupBox("Saved Models")
        table_layout = QVBoxLayout()

        self.models_table = QTableWidget()
        self.models_table.setColumnCount(7)
        self.models_table.setHorizontalHeaderLabels([
            "Name", "Type", "Target Column", "Features", "Metrics", "Created", "Actions"
        ])
        self.models_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.models_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.models_table.itemSelectionChanged.connect(self.on_selection_changed)
        table_layout.addWidget(self.models_table)

        # Table controls
        table_controls = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_models)
        table_controls.addWidget(self.refresh_btn)

        self.load_model_btn = QPushButton("Load Model")
        self.load_model_btn.clicked.connect(self.load_selected_model)
        self.load_model_btn.setEnabled(False)
        table_controls.addWidget(self.load_model_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_model)
        self.delete_btn.setEnabled(False)
        table_controls.addWidget(self.delete_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self.export_model)
        self.export_btn.setEnabled(False)
        table_controls.addWidget(self.export_btn)

        self.import_btn = QPushButton("Import Model")
        self.import_btn.clicked.connect(self.import_model)
        table_controls.addWidget(self.import_btn)

        table_controls.addStretch()

        table_layout.addLayout(table_controls)
        table_group.setLayout(table_layout)
        main_layout.addWidget(table_group)

        # Model details panel
        details_group = QGroupBox("Model Details")
        details_layout = QVBoxLayout()

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        details_layout.addWidget(self.details_text)

        details_group.setLayout(details_layout)
        main_layout.addWidget(details_group)

        # Load models on init
        self.init_service()

    def create_stat_card(self, title: str, value: str, color: str) -> QLabel:
        """Create a statistics card label"""
        label = QLabel()
        label.setStyleSheet(f"""
            background: {color};
            color: white;
            padding: 15px;
            border-radius: 6px;
            font-weight: bold;
        """)
        label.setText(f"<div style='font-size: 12px; opacity: 0.9;'>{title}</div>"
                    f"<div style='font-size: 24px;'>{value}</div>")
        return label

    def init_service(self):
        """Initialize the ML model service"""
        from services.ml_model_service import MLModelService
        if self.ml_model_service is None:
            self.ml_model_service = MLModelService()

        self.load_models()

    def load_models(self):
        """Load models into the table"""
        if not self.ml_model_service:
            return

        try:
            # Get filter
            filter_idx = self.filter_combo.currentIndex()
            model_type = None
            if filter_idx == 1:
                model_type = "anomaly"
            elif filter_idx == 2:
                model_type = "classification"
            elif filter_idx == 3:
                model_type = "clustering"

            # Load models
            models = self.ml_model_service.get_models(model_type=model_type)
            self.current_models = models

            # Clear table
            self.models_table.setRowCount(len(models))

            for row, model in enumerate(models):
                # Name
                self.models_table.setItem(row, 0, QTableWidgetItem(model.name))

                # Type
                self.models_table.setItem(row, 1, QTableWidgetItem(model.model_type))

                # Target column
                self.models_table.setItem(row, 2, QTableWidgetItem(model.target_column))

                # Features
                import json
                feature_cols = json.loads(model.feature_columns)
                features_text = f"{len(feature_cols)} columns"
                self.models_table.setItem(row, 3, QTableWidgetItem(features_text))

                # Metrics
                metrics = json.loads(model.metrics)
                metrics_text = ", ".join(f"{k}: {v:.3f}" if isinstance(v, float) else f"{k}: {v}"
                                        for k, v in list(metrics.items())[:3])
                self.models_table.setItem(row, 4, QTableWidgetItem(metrics_text))

                # Created
                created = model.created_at.strftime("%Y-%m-%d %H:%M") if model.created_at else "-"
                self.models_table.setItem(row, 5, QTableWidgetItem(created))

                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(5, 0, 5, 0)

                view_btn = QPushButton("View")
                view_btn.setStyleSheet("padding: 2px 8px;")
                view_btn.clicked.connect(lambda checked, m=model: self.view_model_details(m))
                actions_layout.addWidget(view_btn)

                actions_layout.addStretch()
                self.models_table.setCellWidget(row, 6, actions_widget)

            # Update statistics
            self.update_statistics()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load models:\n{str(e)}")

    def update_statistics(self):
        """Update statistics display"""
        if not self.ml_model_service:
            return

        try:
            stats = self.ml_model_service.get_model_statistics()

            # Update stat cards
            self.total_label.setText(
                f"<div style='font-size: 12px; opacity: 0.9;'>Total Models</div>"
                f"<div style='font-size: 24px;'>{stats['total_models']}</div>"
            )

            anomaly_count = stats['models_by_type'].get('isolation_forest', 0) + \
                           stats['models_by_type'].get('local_outlier_factor', 0)
            self.anomaly_label.setText(
                f"<div style='font-size: 12px; opacity: 0.9;'>Anomaly Detection</div>"
                f"<div style='font-size: 24px;'>{anomaly_count}</div>"
            )

            class_count = stats['models_by_type'].get('random_forest', 0) + \
                          stats['models_by_type'].get('logistic_regression', 0)
            self.classification_label.setText(
                f"<div style='font-size: 12px; opacity: 0.9;'>Classification</div>"
                f"<div style='font-size: 24px;'>{class_count}</div>"
            )

            self.storage_label.setText(
                f"<div style='font-size: 12px; opacity: 0.9;'>Storage</div>"
                f"<div style='font-size: 24px;'>{stats['disk_usage_mb']:.1f} MB</div>"
            )

        except Exception as e:
            print(f"Error updating statistics: {e}")

    def on_selection_changed(self):
        """Handle table selection change"""
        has_selection = len(self.models_table.selectedItems()) > 0
        self.load_model_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.export_btn.setEnabled(has_selection)

    def load_selected_model(self):
        """Load the selected model"""
        current_row = self.models_table.currentRow()
        if current_row < 0:
            return

        model = self.current_models[current_row]

        try:
            model_obj, metadata = self.ml_model_service.load_model(model.id)

            QMessageBox.information(
                self,
                "Model Loaded",
                f"Model '{metadata['name']}' loaded successfully!\n\n"
                f"Type: {metadata['model_type']}\n"
                f"Target: {metadata['target_column']}\n"
                f"Features: {len(metadata['feature_columns'])}"
            )

            self.model_selected.emit(metadata)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load model:\n{str(e)}")

    def view_model_details(self, model):
        """Show detailed information about a model"""
        import json

        details = f"""
<b>Model Details</b>

Name: {model.name}
Type: {model.model_type}
Target Column: {model.target_column}

Feature Columns ({len(json.loads(model.feature_columns))}):
{json.dumps(json.loads(model.feature_columns), indent=2)}

Performance Metrics:
{json.dumps(json.loads(model.metrics), indent=2)}

Description:
{model.description or 'No description'}

Created: {model.created_at.strftime('%Y-%m-%d %H:%M:%S') if model.created_at else 'N/A'}
        """

        self.details_text.setHtml(details)

    def delete_model(self):
        """Delete the selected model"""
        current_row = self.models_table.currentRow()
        if current_row < 0:
            return

        model = self.current_models[current_row]

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete model '{model.name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.ml_model_service.delete_model(model.id)
                QMessageBox.information(self, "Success", "Model deleted successfully!")
                self.load_models()
                self.details_text.clear()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete model:\n{str(e)}")

    def export_model(self):
        """Export the selected model"""
        current_row = self.models_table.currentRow()
        if current_row < 0:
            return

        model = self.current_models[current_row]

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Model",
            str(Path.home() / f"{model.name}.pkl"),
            "Pickle Files (*.pkl)"
        )

        if file_path:
            try:
                self.ml_model_service.export_model(model.id, file_path)
                QMessageBox.information(self, "Success", f"Model exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export model:\n{str(e)}")

    def import_model(self):
        """Import a model from file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Model",
            "",
            "Pickle Files (*.pkl)"
        )

        if file_path:
            # Get model info
            dialog = ModelImportDialog(file_path, self)
            if dialog.exec():
                info = dialog.get_model_info()

                try:
                    self.ml_model_service.import_model(
                        model_path=file_path,
                        model_name=info['name'],
                        model_type=info['type'],
                        target_column=info['target'],
                        feature_columns=info['features'],
                        description=info.get('description')
                    )

                    QMessageBox.information(self, "Success", "Model imported successfully!")
                    self.load_models()

                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to import model:\n{str(e)}")


class ModelImportDialog(QDialog):
    """Dialog for importing a model"""

    def __init__(self, model_path: str, parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.model_info = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Import Model")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Model name
        self.name_input = QLineEdit()
        self.name_input.setText(Path(self.model_path).stem)
        form_layout.addRow("Model Name*:", self.name_input)

        # Model type
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "isolation_forest", "local_outlier_factor", "one_class_svm",
            "random_forest", "logistic_regression", "knn",
            "kmeans", "dbscan", "other"
        ])
        form_layout.addRow("Model Type*:", self.type_combo)

        # Target column
        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("e.g., anomaly, class, cluster")
        form_layout.addRow("Target Column*:", self.target_input)

        # Feature columns
        self.features_input = QLineEdit()
        self.features_input.setPlaceholderText("Comma-separated: col1, col2, col3")
        form_layout.addRow("Feature Columns*:", self.features_input)

        # Description
        self.desc_input = QTextEdit()
        self.desc_input.setMaximumHeight(80)
        self.desc_input.setPlaceholderText("Optional description...")
        form_layout.addRow("Description:", self.desc_input)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QHBoxLayout()
        import_btn = QPushButton("Import")
        import_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #106ebe;
            }
        """)
        import_btn.clicked.connect(self.validate_and_accept)
        buttons.addWidget(import_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        buttons.addStretch()
        layout.addLayout(buttons)

    def validate_and_accept(self):
        """Validate inputs and accept"""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter a model name")
            return

        target = self.target_input.text().strip()
        if not target:
            QMessageBox.warning(self, "Validation Error", "Please enter a target column")
            return

        features_str = self.features_input.text().strip()
        if not features_str:
            QMessageBox.warning(self, "Validation Error", "Please enter feature columns")
            return

        features = [f.strip() for f in features_str.split(',')]

        self.model_info = {
            'name': name,
            'type': self.type_combo.currentText(),
            'target': target,
            'features': features,
            'description': self.desc_input.toPlainText().strip()
        }

        self.accept()

    def get_model_info(self):
        return self.model_info
