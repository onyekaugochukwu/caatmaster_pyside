"""
Transform View - Data transformations using a pipeline model
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QMessageBox, QMenu, QListWidget, QListWidgetItem,
    QGroupBox, QTextEdit, QTreeWidget, QTreeWidgetItem, QTabWidget, QScrollArea, QDialog
)
from PySide6.QtCore import Qt, Signal, Slot
import polars as pl
from collections import defaultdict
from typing import Dict, Any

# Import the new architecture components
from core.data_processor import TransformationPipeline
from core.operation_registry import OPERATION_REGISTRY, TransformationStepType

# Import dialog factory
from gui.dialogs.transformation_dialog_factory import TransformationDialogFactory




class TransformView(QWidget):
    """Transform data view using a pipeline-based approach"""

    dataChanged = Signal(pl.DataFrame)
    pipelineChanged = Signal(object)  # Signal when pipeline is updated (emits the pipeline)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pipeline: TransformationPipeline = None
        self.original_dataframe: pl.DataFrame = None

        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Left Panel: Steps and Inspector (scrollable) ---
        left_panel = QWidget()
        left_panel.setObjectName("LeftPanel")
        left_panel.setFixedWidth(350)

        # Wrap left panel content in scroll area
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setWidget(left_panel)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)

        # Steps section
        steps_group = QGroupBox("Applied Steps")
        steps_layout = QVBoxLayout(steps_group)

        self.steps_list_widget = QListWidget()
        self.steps_list_widget.setObjectName("StepsList")
        self.steps_list_widget.itemSelectionChanged.connect(self.on_step_selected)
        steps_layout.addWidget(self.steps_list_widget)

        # Add undo/redo buttons
        btn_layout = QHBoxLayout()
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undo_last_step)
        btn_layout.addWidget(self.undo_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_all_steps)
        btn_layout.addWidget(self.clear_btn)

        steps_layout.addLayout(btn_layout)
        left_layout.addWidget(steps_group)

        # Step Inspector section
        inspector_group = QGroupBox("Step Inspector")
        inspector_layout = QVBoxLayout(inspector_group)

        self.inspector_tabs = QTabWidget()
        self.inspector_tabs.setMaximumHeight(300)

        # Parameters tab
        self.params_text = QTextEdit()
        self.params_text.setReadOnly(True)
        self.params_text.setMaximumHeight(200)
        self.inspector_tabs.addTab(self.params_text, "Parameters")

        # Created Columns tab
        self.columns_tree = QTreeWidget()
        self.columns_tree.setHeaderLabel("Created Columns")
        self.columns_tree.setMaximumHeight(200)
        self.inspector_tabs.addTab(self.columns_tree, "Columns")

        # Data Preview tab
        self.step_preview_table = QTableWidget()
        self.step_preview_table.setMaximumHeight(200)
        self.step_preview_table.setAlternatingRowColors(True)
        self.step_preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.step_preview_table.horizontalHeader().setStretchLastSection(True)
        self.inspector_tabs.addTab(self.step_preview_table, "Preview")

        inspector_layout.addWidget(self.inspector_tabs)
        left_layout.addWidget(inspector_group)

        left_layout.addStretch()  # Add stretch to push content to top
        main_layout.addWidget(left_scroll)

        # --- Right Panel: Data Preview ---
        preview_widget = QWidget()
        preview_widget.setObjectName("PreviewPanel")
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(10, 10, 10, 10)

        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.data_table.horizontalHeader().setStretchLastSection(True)

        self.data_table.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.data_table.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

        preview_layout.addWidget(self.data_table)

        self.info_label = QLabel("Load data via the sidebar to begin transforming.")
        preview_layout.addWidget(self.info_label)

        main_layout.addWidget(preview_widget)
        main_layout.setStretch(1, 1)  # Make the right panel expand

    @Slot(pl.DataFrame)
    def set_dataframe(self, df: pl.DataFrame):
        """Initializes the view with a new DataFrame."""
        self.original_dataframe = df.clone()
        self.pipeline = TransformationPipeline(initial_df=self.original_dataframe)

        self.steps_list_widget.clear()
        self.populate_table(self.pipeline.original_df)
        self.update_info()

    def show_header_context_menu(self, pos):
        """Shows a context menu when right-clicking a table header."""
        if not self.pipeline:
            return

        header = self.data_table.horizontalHeader()
        column_index = header.logicalIndexAt(pos)
        column_name = self.data_table.horizontalHeaderItem(column_index).text()

        menu = QMenu(self)

        # Group operations by category (matching Ribbon structure)
        grouped_ops = defaultdict(list)
        for op_id, op_data in OPERATION_REGISTRY.items():
            category = op_data.get('category', 'other')
            grouped_ops[category].append((op_id, op_data))

        # Define category display names and order
        category_order = {
            'text': 'Text',
            'math': 'Math',
            'datetime': 'Date & Time',
            'statistical': 'Statistics',
            'audit': 'Audit',
            'ml': 'Machine Learning',
            'ai': 'AI',
            'other': 'Other'
        }

        # Process each category in order
        for category_key, category_display in category_order.items():
            if category_key not in grouped_ops or not grouped_ops[category_key]:
                continue

            # Create submenu for this category
            category_menu = menu.addMenu(category_display)

            # For datetime category, create sub-submenus for Extract, Calculate, etc.
            if category_key == 'datetime':
                self._add_datetime_submenu(category_menu, grouped_ops[category_key], column_name)
            # For text category, create sub-submenus for Case, Extract, etc.
            elif category_key == 'text':
                self._add_text_submenu(category_menu, grouped_ops[category_key], column_name)
            # For math category, create sub-submenus for Basic, Trig, etc.
            elif category_key == 'math':
                self._add_math_submenu(category_menu, grouped_ops[category_key], column_name)
            else:
                # For other categories, just list operations directly
                for op_id, op_data in sorted(grouped_ops[category_key], key=lambda x: x[1]['display_name']):
                    action = category_menu.addAction(op_data['display_name'])
                    action.triggered.connect(
                        lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                    )

        menu.exec(header.mapToGlobal(pos))

    def _add_datetime_submenu(self, parent_menu, operations, column_name):
        """Add datetime operations with sub-submenus"""
        # Group datetime operations by function type
        extract_ops = []
        calc_ops = []
        other_ops = []

        for op_id, op_data in operations:
            if 'extract' in op_data['display_name'].lower() or op_id.startswith('datetime_'):
                if any(x in op_id for x in ['year', 'month', 'day', 'hour', 'minute', 'second', 'weekday', 'quarter']):
                    extract_ops.append((op_id, op_data))
                else:
                    calc_ops.append((op_id, op_data))
            else:
                other_ops.append((op_id, op_data))

        # Extract submenu
        if extract_ops:
            extract_menu = parent_menu.addMenu("Extract")
            for op_id, op_data in sorted(extract_ops, key=lambda x: x[1]['display_name']):
                action = extract_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Calculate submenu
        if calc_ops:
            calc_menu = parent_menu.addMenu("Calculate")
            for op_id, op_data in sorted(calc_ops, key=lambda x: x[1]['display_name']):
                action = calc_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Other operations
        for op_id, op_data in sorted(other_ops, key=lambda x: x[1]['display_name']):
            action = parent_menu.addAction(op_data['display_name'])
            action.triggered.connect(
                lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
            )

    def _add_text_submenu(self, parent_menu, operations, column_name):
        """Add text operations with sub-submenus"""
        # Group text operations
        case_ops = []
        extract_ops = []
        clean_ops = []
        other_ops = []

        for op_id, op_data in operations:
            name = op_data['display_name'].lower()
            if 'case' in name or 'upper' in name or 'lower' in name or 'title' in name:
                case_ops.append((op_id, op_data))
            elif 'extract' in name:
                extract_ops.append((op_id, op_data))
            elif 'trim' in name or 'clean' in name or 'whitespace' in name:
                clean_ops.append((op_id, op_data))
            else:
                other_ops.append((op_id, op_data))

        # Case submenu
        if case_ops:
            case_menu = parent_menu.addMenu("Case")
            for op_id, op_data in sorted(case_ops, key=lambda x: x[1]['display_name']):
                action = case_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Extract submenu
        if extract_ops:
            extract_menu = parent_menu.addMenu("Extract")
            for op_id, op_data in sorted(extract_ops, key=lambda x: x[1]['display_name']):
                action = extract_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Clean submenu
        if clean_ops:
            clean_menu = parent_menu.addMenu("Clean")
            for op_id, op_data in sorted(clean_ops, key=lambda x: x[1]['display_name']):
                action = clean_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Other operations
        for op_id, op_data in sorted(other_ops, key=lambda x: x[1]['display_name']):
            action = parent_menu.addAction(op_data['display_name'])
            action.triggered.connect(
                lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
            )

    def _add_math_submenu(self, parent_menu, operations, column_name):
        """Add math operations with sub-submenus"""
        # Group math operations
        basic_ops = []
        trig_ops = []
        other_ops = []

        for op_id, op_data in operations:
            if op_id.startswith('trig_'):
                trig_ops.append((op_id, op_data))
            elif op_id.startswith('math_'):
                basic_ops.append((op_id, op_data))
            else:
                other_ops.append((op_id, op_data))

        # Basic submenu
        if basic_ops:
            basic_menu = parent_menu.addMenu("Basic")
            for op_id, op_data in sorted(basic_ops, key=lambda x: x[1]['display_name']):
                action = basic_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Trigonometric submenu
        if trig_ops:
            trig_menu = parent_menu.addMenu("Trigonometric")
            for op_id, op_data in sorted(trig_ops, key=lambda x: x[1]['display_name']):
                action = trig_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Other operations
        for op_id, op_data in sorted(other_ops, key=lambda x: x[1]['display_name']):
            action = parent_menu.addAction(op_data['display_name'])
            action.triggered.connect(
                lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
            )

    def _extract_placeholders(self, template: str):
        """Extract placeholder names from a template string.

        Returns a list of placeholder names (without braces).
        """
        import re
        return re.findall(r'\{([^}]+)\}', template)

    def _format_column_name(self, template: str, values: dict):
        """Format a column name template with provided values.

        Missing placeholders are replaced with the placeholder name (without braces).
        """
        import re
        # Find all placeholders
        placeholders = set(re.findall(r'\{([^}]+)\}', template))
        # Build mapping
        mapping = {}
        for ph in placeholders:
            if ph in values and values[ph] is not None:
                mapping[ph] = str(values[ph])
            else:
                # Fallback to placeholder name
                mapping[ph] = ph
        # Replace placeholders
        result = template
        for ph, val in mapping.items():
            result = result.replace('{' + ph + '}', val)
        return result

    def _should_generate_output_cols(self, creates_columns, default_values):
        """Determine whether to generate output_cols automatically.

        Returns False if column name templates contain placeholders other than
        'column' or 'operation', since those placeholders depend on user input
        that may change in the dialog.
        """
        safe_placeholders = {'column', 'operation'}
        if isinstance(creates_columns, list):
            for template in creates_columns:
                placeholders = self._extract_placeholders(template)
                for ph in placeholders:
                    if ph not in safe_placeholders:
                        # This placeholder may be changed by user, skip generation
                        return False
        # All placeholders are safe, or creates_columns is not a list
        return True

    def _get_default_param_values(self, operation_id: str, column_name: str):
        """Generate default parameter values for an operation.

        Returns a dictionary mapping parameter names to default values,
        suitable for formatting column name templates.
        """
        op_data = OPERATION_REGISTRY[operation_id]
        param_schema = op_data.get('parameter_schema', {})
        defaults = {'column': column_name}

        # Add operation suffix for use in column naming patterns
        operation_name = operation_id.split('_')[-1]
        defaults['operation'] = operation_name

        for param_name, schema in param_schema.items():
            # Skip 'column' as we already set it
            if param_name == 'column':
                continue

            # Use default from schema if available
            if 'default' in schema:
                defaults[param_name] = schema['default']
            else:
                # Generate a sensible default based on parameter name
                if param_name.endswith('_column'):
                    # For parameters like 'output_column', 'target_column', etc.
                    # Use column_name with suffix
                    suffix = param_name.replace('_column', '')
                    if suffix:
                        defaults[param_name] = f"{column_name}_{suffix}"
                    else:
                        defaults[param_name] = f"{column_name}_output"
                elif param_name in ('output_col', 'probability_column', 'confidence_column',
                                   'deviation_column', 'score_column', 'flag_column',
                                   'missing_count_column', 'var_name', 'value_name'):
                    # Common output column parameters
                    defaults[param_name] = f"{column_name}_{param_name}"
                else:
                    # For other parameters, leave as None (will be filled by user)
                    defaults[param_name] = None

        return defaults

    def on_transformation_selected(self, operation_id: str, column_name: str):
        """Handles the selection of a transformation from the context menu."""
        if not self.pipeline:
            QMessageBox.warning(self, "No Data", "Please load data first.")
            return

        op_data = OPERATION_REGISTRY[operation_id]

        # Prepare initial parameters with defaults
        default_values = self._get_default_param_values(operation_id, column_name)
        initial_params = {k: v for k, v in default_values.items() if v is not None}
        # Ensure column is set (should already be)
        initial_params['column'] = column_name

        # Filter out keys not in parameter schema (except special keys like output_col, output_cols)
        param_schema = op_data.get('parameter_schema', {})
        special_keys = {'output_col', 'output_cols'}
        filtered_params = {}
        for key, value in initial_params.items():
            if key in param_schema or key in special_keys:
                filtered_params[key] = value
            # else: drop the key (e.g., 'operation' used for formatting)
        initial_params = filtered_params

        # Set default output column name(s) based on operation
        creates_columns = op_data.get('creates_columns', False)
        if creates_columns:
            if isinstance(creates_columns, list):
                # Multiple columns created - generate output_cols list only if all placeholders are safe
                if self._should_generate_output_cols(creates_columns, default_values):
                    output_cols = [self._format_column_name(col_name, default_values) for col_name in creates_columns]
                    initial_params['output_cols'] = output_cols
                    # If only one column, also set output_col for backward compatibility
                    if len(output_cols) == 1:
                        initial_params['output_col'] = output_cols[0]
            else:
                # Single column created - generate output_col only if all placeholders are safe
                naming_pattern = op_data.get('column_naming_pattern', '{column}_{operation}')
                placeholders = self._extract_placeholders(naming_pattern)
                safe_placeholders = {'column', 'operation'}
                if all(ph in safe_placeholders for ph in placeholders):
                    initial_params['output_col'] = self._format_column_name(naming_pattern, default_values)

        # Create dialog using the factory with selected_column for auto-selection
        dialog = TransformationDialogFactory.create_dialog(
            operation_id=operation_id,
            dataframe=self.original_dataframe,
            parent=self,
            initial_params=initial_params,
            selected_column=column_name
        )

        if dialog:
            result = dialog.exec()
            if result == QDialog.Accepted:
                params = dialog.get_parameters()
                if params is not None:
                    self.apply_transformation(operation_id, params)

    def apply_transformation(self, operation_id: str, params: dict):
        """Adds a step to the pipeline and refreshes the view."""
        if not self.pipeline:
            QMessageBox.warning(self, "No Data", "No data pipeline is active.")
            return

        try:
            self.pipeline.add_step(operation_id, params)
            transformed_df = self.pipeline.apply()

            self.populate_table(transformed_df)
            self.update_info()

            # Update the "Applied Steps" list
            op_name = OPERATION_REGISTRY[operation_id]['display_name']
            step_text = f"{self.steps_list_widget.count() + 1}. {op_name}"
            QListWidgetItem(step_text, self.steps_list_widget)

            # Clear inspector when new step is added
            self.clear_inspector()

            # Emit signals for parent views
            self.dataChanged.emit(transformed_df)
            self.pipelineChanged.emit(self.pipeline)

        except Exception as e:
            QMessageBox.critical(
                self, "Transformation Error",
                f"Failed to apply '{operation_id}':\n{str(e)}"
            )

    def undo_last_step(self):
        """Removes the last transformation step."""
        if not self.pipeline or len(self.pipeline.get_steps()) == 0:
            return

        try:
            self.pipeline.remove_last_step()
            transformed_df = self.pipeline.apply()

            # Remove last item from list
            last_row = self.steps_list_widget.count() - 1
            self.steps_list_widget.takeItem(last_row)

            # Clear inspector
            self.clear_inspector()

            self.populate_table(transformed_df)
            self.update_info()
            self.dataChanged.emit(transformed_df)
            self.pipelineChanged.emit(self.pipeline)

        except Exception as e:
            QMessageBox.critical(self, "Undo Error", f"Failed to undo step:\n{str(e)}")

    def clear_all_steps(self):
        """Removes all transformation steps."""
        if not self.pipeline:
            return

        reply = QMessageBox.question(
            self, "Clear All Steps",
            "Are you sure you want to remove all transformation steps?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.pipeline.clear_steps()
                self.steps_list_widget.clear()
                self.clear_inspector()
                self.populate_table(self.pipeline.original_df)
                self.update_info()
                self.dataChanged.emit(self.pipeline.original_df)
                self.pipelineChanged.emit(self.pipeline)
            except Exception as e:
                QMessageBox.critical(
                    self, "Clear Error", f"Failed to clear steps:\n{str(e)}"
                )

    def populate_table(self, df: pl.DataFrame):
        """Populates the table with data from a Polars DataFrame."""
        if df is None:
            self.data_table.setRowCount(0)
            self.data_table.setColumnCount(0)
            return

        display_df = df.head(1000)

        self.data_table.setRowCount(display_df.height)
        self.data_table.setColumnCount(display_df.width)
        self.data_table.setHorizontalHeaderLabels(display_df.columns)

        for row_idx in range(display_df.height):
            for col_idx, value in enumerate(display_df.row(row_idx)):
                item = QTableWidgetItem(str(value) if value is not None else "")
                self.data_table.setItem(row_idx, col_idx, item)

        self.data_table.resizeColumnsToContents()

    def update_info(self):
        """Updates the info label with details about the current DataFrame."""
        if self.pipeline is None or self.pipeline.original_df is None:
            self.info_label.setText("Load data to begin transforming.")
            return

        current_df = self.pipeline.apply()
        rows, cols = current_df.shape
        memory = current_df.estimated_size('mb')
        num_steps = len(self.pipeline.get_steps())

        self.info_label.setText(
            f"Shape: {rows:,} rows x {cols} columns | "
            f"Memory: {memory:.2f} MB | "
            f"Transformations: {num_steps}"
        )

    @Slot()
    def on_step_selected(self):
        """Handle step selection in the steps list."""
        if not self.pipeline:
            return

        selected_items = self.steps_list_widget.selectedItems()
        if not selected_items:
            self.clear_inspector()
            return

        # Get the step number from the selected item text
        selected_text = selected_items[0].text()
        try:
            step_number = int(selected_text.split('.')[0])  # Extract number from "1. Operation Name"
            self.update_inspector(step_number)
        except (ValueError, IndexError):
            self.clear_inspector()

    def update_inspector(self, step_number: int):
        """Update the step inspector with information for the selected step."""
        if not self.pipeline or step_number < 1 or step_number > len(self.pipeline.get_steps()):
            self.clear_inspector()
            return

        step = self.pipeline.get_steps()[step_number - 1]

        # Update Parameters tab
        params_text = f"Operation: {step.operation_id}\n\n"
        params_text += "Parameters:\n"
        for key, value in step.params.items():
            if isinstance(value, list):
                params_text += f"  {key}: {', '.join(str(v) for v in value)}\n"
            else:
                params_text += f"  {key}: {value}\n"

        params_text += f"\nTimestamp: {step.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        self.params_text.setPlainText(params_text)

        # Update Columns tab
        self.columns_tree.clear()
        if step.created_columns:
            for col in step.created_columns:
                col_info = self.pipeline.get_column_info(col)
                item = QTreeWidgetItem([col])
                if col_info:
                    item.setToolTip(0, f"Created by: {col_info['operation']} at step {col_info['created_by_step']}")
                self.columns_tree.addTopLevelItem(item)
        else:
            no_cols_item = QTreeWidgetItem(["No columns created"])
            self.columns_tree.addTopLevelItem(no_cols_item)

        # Update Preview tab
        step_df = self.pipeline.get_dataframe_at_step(step_number)
        self.populate_step_preview_table(step_df)

    def clear_inspector(self):
        """Clear all inspector tabs."""
        self.params_text.clear()
        self.columns_tree.clear()
        self.step_preview_table.setRowCount(0)
        self.step_preview_table.setColumnCount(0)

    def populate_step_preview_table(self, df: pl.DataFrame):
        """Populate the step preview table with a subset of the dataframe."""
        if df is None:
            self.step_preview_table.setRowCount(0)
            self.step_preview_table.setColumnCount(0)
            return

        # Show first 50 rows and first 10 columns for preview
        preview_df = df.head(50).select(df.columns[:10])

        self.step_preview_table.setRowCount(preview_df.height)
        self.step_preview_table.setColumnCount(preview_df.width)
        self.step_preview_table.setHorizontalHeaderLabels(preview_df.columns)

        for row_idx in range(preview_df.height):
            for col_idx, value in enumerate(preview_df.row(row_idx)):
                item = QTableWidgetItem(str(value) if value is not None else "")
                self.step_preview_table.setItem(row_idx, col_idx, item)

        self.step_preview_table.resizeColumnsToContents()
