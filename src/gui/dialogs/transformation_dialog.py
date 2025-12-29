"""
Transformation Dialog - Dialog for applying data transformations
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QListWidget, QListWidgetItem,
    QGroupBox, QScrollArea, QWidget, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from typing import Dict, Any, List
import polars as pl


class TransformationDialog(QDialog):
    """Dialog for applying data transformations"""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, columns: List[str], parent=None):
        super().__init__(parent)
        self.columns = columns
        self.current_dataframe = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Apply Transformation")
        self.setMinimumWidth(600)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Split into two parts: operation selection and parameter configuration
        from PySide6.QtWidgets import QSplitter

        splitter = QSplitter(Qt.Horizontal)

        # Left side: Operation list
        left_panel = self.create_operation_panel()
        splitter.addWidget(left_panel)

        # Right side: Parameter configuration
        right_panel = self.create_parameter_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

        # Buttons at bottom
        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet("""
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
            QPushButton:disabled {
                background: #cccccc;
            }
        """)
        self.apply_btn.clicked.connect(self.apply_transformation)
        button_layout.addWidget(self.apply_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Load operations
        self.load_operations()

    def create_operation_panel(self) -> QWidget:
        """Create the operation selection panel"""
        from core.operation_registry import OPERATION_REGISTRY

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)

        # Title
        title = QLabel("Operations")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        panel_layout.addWidget(title)

        # Category filter
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "All", "Calculate", "Filter", "Aggregate", "Transform",
            "ML Predict", "ML Train", "AI Enrich", "AI Extract", "Audit Flag"
        ])
        self.category_combo.currentTextChanged.connect(self.filter_operations)
        category_layout.addWidget(self.category_combo)
        panel_layout.addLayout(category_layout)

        # Operation list
        self.operation_list = QListWidget()
        self.operation_list.itemClicked.connect(self.on_operation_selected)
        panel_layout.addWidget(self.operation_list)

        # Description
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        panel_layout.addWidget(self.description_label)

        return panel

    def create_parameter_panel(self) -> QWidget:
        """Create the parameter configuration panel"""
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)

        # Title
        title = QLabel("Parameters")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        panel_layout.addWidget(title)

        # Scroll area for parameters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.parameter_widget = QWidget()
        self.parameter_layout = QFormLayout(self.parameter_widget)
        scroll.setWidget(self.parameter_widget)

        panel_layout.addWidget(scroll)

        # Preview section
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("Select an operation to see preview")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("padding: 10px; background: #f5f5f5;")
        preview_layout.addWidget(self.preview_label)

        panel_layout.addWidget(preview_group)
        panel_layout.addStretch()

        return panel

    def load_operations(self):
        """Load operations into the list"""
        from core.operation_registry import OPERATION_REGISTRY

        self.operation_list.clear()

        for op_id, op_def in OPERATION_REGISTRY.items():
            item = QListWidgetItem(op_def['name'])
            item.setData(Qt.UserRole, op_id)
            self.operation_list.addItem(item)

    def filter_operations(self, category: str):
        """Filter operations by category"""
        from core.operation_registry import OPERATION_REGISTRY, OperationCategory

        self.operation_list.clear()

        for op_id, op_def in OPERATION_REGISTRY.items():
            if category == "All" or op_def['category'].value == category.lower():
                item = QListWidgetItem(op_def['name'])
                item.setData(Qt.UserRole, op_id)
                self.operation_list.addItem(item)

    def on_operation_selected(self, item: QListWidgetItem):
        """Handle operation selection"""
        op_id = item.data(Qt.UserRole)

        from core.operation_registry import get_operation

        op_def = get_operation(op_id)
        if not op_def:
            return

        # Update description
        self.description_label.setText(f"<b>{op_def['name']}</b><br>{op_def['description']}")

        # Clear previous parameters
        while self.parameter_layout.count():
            child = self.parameter_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Create parameter inputs
        self.param_widgets = {}
        for param in op_def.get('parameters', []):
            widget = self.create_parameter_widget(param)
            if widget:
                self.parameter_layout.addRow(param['label'] + ":", widget)
                self.param_widgets[param['name']] = {
                    'widget': widget,
                    'def': param
                }

        self.current_operation_id = op_id
        self.apply_btn.setEnabled(True)

    def create_parameter_widget(self, param: Dict[str, Any]):
        """Create input widget for a parameter"""
        param_type = param['type']

        if param_type == 'column':
            combo = QComboBox()
            combo.addItems(self.columns)
            if 'default' in param:
                combo.setCurrentText(param['default'])
            return combo

        elif param_type == 'columns':
            from PySide6.QtWidgets import QListView
            list_widget = QListWidget()
            list_widget.setSelectionMode(QListWidget.MultiSelection)
            list_widget.addItems(self.columns)
            return list_widget

        elif param_type == 'text':
            line = QLineEdit()
            if 'default' in param:
                line.setText(param['default'])
            return line

        elif param_type == 'integer':
            spin = QSpinBox()
            if 'min' in param:
                spin.setMinimum(param['min'])
            if 'max' in param:
                spin.setMaximum(param['max'])
            if 'default' in param:
                spin.setValue(param['default'])
            return spin

        elif param_type == 'number':
            spin = QDoubleSpinBox()
            spin.setRange(-999999999, 999999999)
            if 'default' in param:
                spin.setValue(param['default'])
            return spin

        elif param_type == 'boolean':
            checkbox = QCheckBox()
            if 'default' in param:
                checkbox.setChecked(param['default'])
            return checkbox

        elif param_type == 'select':
            combo = QComboBox()
            combo.addItems(param.get('options', []))
            if 'default' in param:
                combo.setCurrentText(param['default'])
            return combo

        return None

    def get_parameter_values(self) -> Dict[str, Any]:
        """Get values from all parameter widgets"""
        params = {}

        for param_name, param_info in self.param_widgets.items():
            widget = param_info['widget']
            param_def = param_info['def']
            param_type = param_def['type']

            if param_type == 'column':
                params[param_name] = widget.currentText()

            elif param_type == 'columns':
                selected = [item.text() for item in widget.selectedItems()]
                params[param_name] = selected

            elif param_type == 'text':
                params[param_name] = widget.text()

            elif param_type == 'integer':
                params[param_name] = widget.value()

            elif param_type == 'number':
                params[param_name] = widget.value()

            elif param_type == 'boolean':
                params[param_name] = widget.isChecked()

            elif param_type == 'select':
                params[param_name] = widget.currentText()

        return params

    def apply_transformation(self):
        """Apply the transformation"""
        if not hasattr(self, 'current_operation_id'):
            return

        params = self.get_parameter_values()

        # Validate
        from core.operation_registry import validate_operation_parameters

        is_valid, errors = validate_operation_parameters(self.current_operation_id, params)

        if not is_valid:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please fix the following errors:\n\n" + "\n".join(errors)
            )
            return

        # Emit signal
        self.transformation_applied.emit(self.current_operation_id, params)
        self.accept()


class AppliedStepsPanel(QWidget):
    """Panel showing applied transformation steps"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("Applied Steps")
        title.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Steps list
        self.steps_list = QListWidget()
        self.steps_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background: #0078d4;
                color: white;
            }
        """)
        layout.addWidget(self.steps_list)

        # Buttons
        button_layout = QHBoxLayout()

        self.undo_btn = QPushButton("Undo Last")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self.undo_last)
        button_layout.addWidget(self.undo_btn)

        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self.clear_all)
        button_layout.addWidget(self.clear_btn)

        layout.addLayout(button_layout)

    def add_step(self, operation_id: str, operation_name: str, parameters: Dict[str, Any]):
        """Add a transformation step"""
        step = {
            'operation_id': operation_id,
            'operation_name': operation_name,
            'parameters': parameters
        }
        self.steps.append(step)

        # Update UI
        item_text = f"{operation_name}"
        if parameters:
            param_str = ", ".join(f"{k}={v}" for k, v in parameters.items())
            item_text += f"\n  ({param_str})"

        self.steps_list.addItem(item_text)
        self.steps_list.scrollToBottom()

        self.undo_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

    def undo_last(self):
        """Remove the last step"""
        if self.steps:
            self.steps.pop()
            self.steps_list.takeItem(self.steps_list.count() - 1)

            if not self.steps:
                self.undo_btn.setEnabled(False)
                self.clear_btn.setEnabled(False)

    def clear_all(self):
        """Clear all steps"""
        self.steps.clear()
        self.steps_list.clear()
        self.undo_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

    def get_steps(self) -> List[Dict[str, Any]]:
        """Get all steps"""
        return self.steps
