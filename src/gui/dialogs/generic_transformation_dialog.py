"""
Generic Transformation Dialog
Dynamically generates a form based on a parameter schema from the Operation Registry.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
    QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QListWidget, QListWidgetItem, QHBoxLayout, QPushButton, QGroupBox
)
from PySide6.QtCore import Qt
from typing import Dict, Any, List, Union


class GenericTransformationDialog(QDialog):
    """A dialog that dynamically builds a form for a transformation."""

    def __init__(self, operation_id: str, param_schema: Dict, dataframe=None, parent=None, initial_params: Dict = None):
        super().__init__(parent if parent else None)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.param_schema = param_schema
        self.operation_id = operation_id
        self.dataframe = dataframe
        self.initial_params = initial_params or {}
        self.input_widgets = {}

        self.setWindowTitle(f"Parameters for {operation_id}")
        self.setMinimumWidth(400)

        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()

        self.build_form()

        self.layout.addLayout(self.form_layout)

        # Standard buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _create_column_multiselect(self, available_columns: List[str], selected_columns: List[str] = None) -> QListWidget:
        """
        Create a multi-select list widget for column selection.

        Args:
            available_columns: List of all available column names
            selected_columns: List of pre-selected column names

        Returns:
            QListWidget configured for multi-selection
        """
        list_widget = QListWidget()
        list_widget.setSelectionMode(QListWidget.MultiSelection)

        selected_columns = selected_columns or []

        for col in available_columns:
            item = QListWidgetItem(col)
            item.setSelected(col in selected_columns)
            list_widget.addItem(item)

        return list_widget

    def build_form(self):
        """Creates form widgets based on the parameter schema."""
        for param_name, schema in self.param_schema.items():
            label_text = schema.get('label', param_name)

            # Use initial value if provided, otherwise use default
            initial_value = self.initial_params.get(param_name, schema.get('default'))

            # Don't create a widget for the main 'column' if it's pre-filled
            if param_name == 'column' and 'column' in self.initial_params:
                # Still add it to the initial_params, but don't show it as an editable field
                continue

            param_type = schema['type']
            widget = None

            if param_type == 'string':
                if 'options' in schema:
                    widget = QComboBox()
                    widget.addItems(schema['options'])
                    if initial_value:
                        widget.setCurrentText(str(initial_value))
                else:
                    widget = QLineEdit()
                    if initial_value:
                        widget.setText(str(initial_value).format(col=self.initial_params.get('column')))
            elif param_type == 'int':
                widget = QSpinBox()
                widget.setRange(-1000000, 1000000)
                if initial_value:
                    widget.setValue(int(initial_value))
            elif param_type == 'float':
                widget = QDoubleSpinBox()
                widget.setRange(-1000000.0, 1000000.0)
                widget.setDecimals(3)
                if initial_value:
                    widget.setValue(float(initial_value))
            elif param_type == 'bool':
                widget = QCheckBox()
                if initial_value:
                    widget.setChecked(bool(initial_value))
            elif param_type == 'list[str]':
                widget = QLineEdit() # Simple comma-separated list
                widget.setPlaceholderText("e.g., item1, item2, item3")
                if initial_value:
                     widget.setText(", ".join(initial_value))
            elif param_type == 'column':
                if self.dataframe is not None:
                    widget = QComboBox()
                    widget.addItems(self.dataframe.columns)
                    if initial_value:
                        widget.setCurrentText(str(initial_value))
                else:
                    widget = QLineEdit()
                    if initial_value:
                        widget.setText(str(initial_value))
            elif param_type == 'list[column]':
                if self.dataframe is not None:
                    # Create a group box with multi-select list
                    group_box = QGroupBox(f"{label_text}")
                    group_layout = QVBoxLayout(group_box)

                    # Create the multi-select list
                    selected_cols = initial_value if isinstance(initial_value, list) else []
                    list_widget = self._create_column_multiselect(
                        self.dataframe.columns,
                        selected_cols
                    )

                    group_layout.addWidget(list_widget)
                    widget = group_box
                    self.input_widgets[param_name] = list_widget  # Store the list widget, not the group
                else:
                    # Fallback to text input
                    widget = QLineEdit()
                    widget.setPlaceholderText("Select columns (comma-separated)")
                    if initial_value:
                        if isinstance(initial_value, list):
                            widget.setText(", ".join(initial_value))
                        else:
                            widget.setText(str(initial_value))
            else:
                # Fallback for unknown types
                widget = QLineEdit()
                if initial_value:
                    widget.setText(str(initial_value))

            if widget:
                self.input_widgets[param_name] = widget
                self.form_layout.addRow(QLabel(label_text), widget)

        # Add output_col field if this operation creates columns and it's in initial_params
        if 'output_col' in self.initial_params and 'output_col' not in self.input_widgets:
            output_label = QLabel("Output Column Name:")
            output_widget = QLineEdit()
            output_widget.setText(self.initial_params['output_col'])
            self.input_widgets['output_col'] = output_widget
            self.form_layout.addRow(output_label, output_widget)

    def get_parameters(self) -> Dict[str, Any]:
        """Extracts parameter values from the form widgets."""
        params = self.initial_params.copy()

        for param_name, widget in self.input_widgets.items():
            # Check if this parameter is in the schema (output_col may be added separately)
            if param_name not in self.param_schema:
                # Handle special cases like output_col which isn't in the schema
                if isinstance(widget, QLineEdit):
                    params[param_name] = widget.text()
                elif isinstance(widget, QComboBox):
                    params[param_name] = widget.currentText()
                elif isinstance(widget, QCheckBox):
                    params[param_name] = widget.isChecked()
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    params[param_name] = widget.value()
                else:
                    params[param_name] = widget.text()
                continue

            schema = self.param_schema[param_name]
            param_type = schema['type']
            value = None

            if isinstance(widget, QListWidget):
                # Handle multi-select list widget for columns
                selected_items = widget.selectedItems()
                value = [item.text() for item in selected_items]
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                value = widget.value()
            elif isinstance(widget, QLineEdit):
                if param_type == 'list[str]' or param_type == 'list[column]':
                    value = [item.strip() for item in widget.text().split(',') if item.strip()]
                else:
                    value = widget.text()
            elif isinstance(widget, QGroupBox):
                # For QGroupBox containing a list widget, get the selected items from the list
                # Find the QListWidget child
                list_widget = widget.findChild(QListWidget)
                if list_widget:
                    selected_items = list_widget.selectedItems()
                    value = [item.text() for item in selected_items]
                else:
                    value = []
            else:
                # For any other widget type, try to get text or use str()
                if hasattr(widget, 'text'):
                    value = widget.text()
                else:
                    value = str(widget)

            params[param_name] = value

        return params
