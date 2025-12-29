"""
Transform View - Data transformations using a pipeline model
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QMessageBox, QMenu, QListWidget, QListWidgetItem,
    QGroupBox, QTextEdit, QTreeWidget, QTreeWidgetItem, QTabWidget
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pipeline: TransformationPipeline = None
        self.original_dataframe: pl.DataFrame = None

        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Left Panel: Steps and Inspector ---
        left_panel = QWidget()
        left_panel.setObjectName("LeftPanel")
        left_panel.setFixedWidth(350)
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

        main_layout.addWidget(left_panel)

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

        grouped_ops = defaultdict(list)
        for op_id, op_data in OPERATION_REGISTRY.items():
            grouped_ops[op_data['type']].append((op_id, op_data))

        for op_type in sorted(grouped_ops.keys(), key=lambda x: x.value):
            if not grouped_ops[op_type]:
                continue

            sub_menu = menu.addMenu(op_type.name.replace("_", " ").title())
            for op_id, op_data in sorted(grouped_ops[op_type], key=lambda x: x[1]['display_name']):
                action = sub_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        menu.exec(header.mapToGlobal(pos))

    def on_transformation_selected(self, operation_id: str, column_name: str):
        """Handles the selection of a transformation from the context menu."""
        op_data = OPERATION_REGISTRY[operation_id]

        # Prepare initial parameters
        initial_params = {'column': column_name}

        # Set default output column name based on operation
        if op_data.get('creates_columns', False):
            naming_pattern = op_data.get('column_naming_pattern', '{column}_{operation}')
            operation_name = operation_id.split('_')[-1]
            initial_params['output_col'] = naming_pattern.format(column=column_name, operation=operation_name)

        # Create dialog using the factory
        dialog = TransformationDialogFactory.create_dialog(
            operation_id=operation_id,
            dataframe=self.original_dataframe,
            parent=self,
            initial_params=initial_params
        )

        if dialog and dialog.exec():
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

            # Emit signal for parent views
            self.dataChanged.emit(transformed_df)

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
