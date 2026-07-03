"""
Transform View - Data transformations using a pipeline model
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QMessageBox, QMenu, QListWidget, QListWidgetItem,
    QGroupBox, QTextEdit, QTreeWidget, QTreeWidgetItem, QTabWidget, QScrollArea, QDialog,
    QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
import polars as pl
from collections import defaultdict
from typing import Dict, Any

# Import the new architecture components
from core.data_processor import TransformationPipeline
from core.operation_registry import OPERATION_REGISTRY, TransformationStepType

# Import dialog factory
from gui.dialogs.transformation_dialog_factory import TransformationDialogFactory
from gui.theme import Colors
from gui.components.column_filter import FilterableHeaderView, ColumnFilterPopup, BLANKS_LABEL




class TransformView(QWidget):
    """Transform data view using a pipeline-based approach"""

    dataChanged = Signal(pl.DataFrame)
    pipelineChanged = Signal(object)  # Signal when pipeline is updated (emits the pipeline)

    def __init__(self, applied_steps_panel=None, parent=None):
        super().__init__(parent)
        self.pipeline: TransformationPipeline = None
        self.original_dataframe: pl.DataFrame = None

        # Applied Steps rendering lives in a shared, persistent panel (see
        # gui.components.applied_steps_panel) so it stays visible across
        # every data-workspace page, not just this one — it never hides just
        # because you switched pages. Falls back to a private instance if
        # none is supplied, so this view remains independently
        # constructible/testable.
        from gui.components.applied_steps_panel import AppliedStepsPanel
        self.steps_panel = applied_steps_panel or AppliedStepsPanel()
        self.steps_panel.undoRequested.connect(self.undo_last_step)
        self.steps_panel.clearRequested.connect(self.clear_all_steps)
        self.steps_panel.exportRequested.connect(self.export_transformations)
        self.steps_panel.stepToggled.connect(self._on_step_toggled)
        self.steps_panel.stepSelectionChanged.connect(self._on_step_selection_changed)

        self.setup_ui()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # No left panel here anymore — Applied Steps AND the Step Inspector
        # both render in the shared, persistent AppliedStepsPanel (see
        # __init__ and gui.components.applied_steps_panel), so this view is
        # just the data grid.

        # --- Right Panel: Data Preview ---
        preview_widget = QWidget()
        preview_widget.setObjectName("PreviewPanel")
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(10, 10, 10, 10)

        # Formula bar — hidden until toggled from View > Formula Bar.
        # Type an expression using col('Name') to reference columns, same
        # syntax as Custom Column, just entered inline instead of in a
        # dialog — the muscle memory Excel users already have.
        self.formula_bar = QWidget()
        formula_layout = QHBoxLayout(self.formula_bar)
        formula_layout.setContentsMargins(0, 0, 0, 8)
        fx_label = QLabel("fx")
        fx_label.setStyleSheet(f"font-weight: 600; color: {Colors.ACCENT}; padding: 0 4px;")
        formula_layout.addWidget(fx_label)
        self.formula_output_edit = QLineEdit()
        self.formula_output_edit.setPlaceholderText("New column name")
        self.formula_output_edit.setFixedWidth(160)
        formula_layout.addWidget(self.formula_output_edit)
        self.formula_expr_edit = QLineEdit()
        self.formula_expr_edit.setPlaceholderText("e.g. col('Amount') * 1.1")
        self.formula_expr_edit.returnPressed.connect(self._on_formula_apply)
        formula_layout.addWidget(self.formula_expr_edit, 1)
        formula_apply_btn = QPushButton("Apply")
        formula_apply_btn.clicked.connect(self._on_formula_apply)
        formula_layout.addWidget(formula_apply_btn)
        self.formula_bar.setVisible(False)
        preview_layout.addWidget(self.formula_bar)

        # Wrap data table in scroll area for proper horizontal scrolling
        data_scroll = QScrollArea()
        data_scroll.setWidgetResizable(True)
        data_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        data_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        data_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
        """)

        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setEditTriggers(QTableWidget.NoEditTriggers)

        filterable_header = FilterableHeaderView(self.data_table)
        filterable_header.filterButtonClicked.connect(self._on_filter_button_clicked)
        self.data_table.setHorizontalHeader(filterable_header)
        self.data_table.horizontalHeader().setStretchLastSection(False)
        self.data_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)

        self.data_table.horizontalHeader().setContextMenuPolicy(Qt.CustomContextMenu)
        self.data_table.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

        # Column AutoFilter state: column name -> set of allowed values
        # (as displayed strings; None key absent = no filter on that column)
        self.column_filters = {}
        self._last_full_df = None

        data_scroll.setWidget(self.data_table)
        preview_layout.addWidget(data_scroll)

        self.info_label = QLabel("Load data via the sidebar to begin transforming.")
        preview_layout.addWidget(self.info_label)

        main_layout.addWidget(preview_widget, 1)

    @Slot(pl.DataFrame)
    def set_dataframe(self, df: pl.DataFrame, pipeline: TransformationPipeline = None):
        """Initializes the view with a new DataFrame.

        Args:
            df: The DataFrame to display
            pipeline: Optional existing transformation pipeline to restore
        """
        self.original_dataframe = df.clone()

        # Restore existing pipeline if provided, otherwise create new one
        if pipeline is not None:
            self.pipeline = pipeline
        else:
            self.pipeline = TransformationPipeline(initial_df=self.original_dataframe)

        # Bind the shared Applied Steps panel to this pipeline and render it
        self.steps_panel.set_pipeline(self.pipeline)

        self.populate_table(self.pipeline.apply())  # Use apply() to show transformed data
        self.update_info()

    def _on_step_toggled(self, step_number: int, enabled: bool):
        """Handle a step's enable/disable checkbox being toggled (signal
        from the shared Applied Steps panel)."""
        if not self.pipeline:
            return
        try:
            self.pipeline.set_step_enabled(step_number, enabled)
            transformed_df = self.pipeline.apply()
            self.populate_table(transformed_df)
            self.update_info()
            self.steps_panel.refresh()
            self.dataChanged.emit(transformed_df)
            self.pipelineChanged.emit(self.pipeline)
        except Exception as e:
            QMessageBox.critical(self, "Toggle Error", f"Failed to toggle step:\n{str(e)}")

    def show_header_context_menu(self, pos):
        """Shows a context menu when right-clicking a table header."""
        if not self.pipeline:
            return

        header = self.data_table.horizontalHeader()
        column_index = header.logicalIndexAt(pos)
        column_name = self.data_table.horizontalHeaderItem(column_index).text()

        menu = QMenu(self)

        # Sort Ascending/Descending and Remove Column — immediate, no
        # dialog (the column is already known from the right-click), same
        # one-click convention as most spreadsheet tools.
        sort_asc_action = menu.addAction(f'Sort "{column_name}" Ascending')
        sort_asc_action.triggered.connect(
            lambda checked=False, col=column_name: self.apply_transformation(
                'sort_column', {'column': col, 'ascending': True}
            )
        )
        sort_desc_action = menu.addAction(f'Sort "{column_name}" Descending')
        sort_desc_action.triggered.connect(
            lambda checked=False, col=column_name: self.apply_transformation(
                'sort_column', {'column': col, 'ascending': False}
            )
        )
        menu.addSeparator()

        remove_action = menu.addAction(f'Remove "{column_name}"')
        remove_action.triggered.connect(
            lambda checked=False, col=column_name: self.apply_transformation(
                'choose_columns', {'action': 'remove', 'columns_to_remove': [col]}
            )
        )
        menu.addSeparator()

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
            'column': 'Column',
            'table': 'Table',
            'statistics': 'Statistics',
            'financial': 'Financial',
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
            # For column category (new column/table operations)
            elif category_key == 'column':
                self._add_column_submenu(category_menu, grouped_ops[category_key], column_name)
            # For table category (split, combine, etc.)
            elif category_key == 'table':
                self._add_table_submenu(category_menu, grouped_ops[category_key], column_name)
            # For ml category, create sub-submenus for Supervised, Unsupervised, Time Series, etc.
            elif category_key == 'ml':
                self._add_ml_submenu(category_menu, grouped_ops[category_key], column_name)
            # For financial category
            elif category_key == 'financial':
                self._add_financial_submenu(category_menu, grouped_ops[category_key], column_name)
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

    def _add_column_submenu(self, parent_menu, operations, column_name):
        """Add column operations (split, rename, dtype, etc.) with submenus"""
        # Group column operations by function type
        split_ops = []
        rename_ops = []
        dtype_ops = []
        structure_ops = []  # choose_columns, calculated_columns
        other_ops = []

        for op_id, op_data in operations:
            if 'split' in op_id.lower() or 'split' in op_data['display_name'].lower():
                split_ops.append((op_id, op_data))
            elif 'rename' in op_id.lower():
                rename_ops.append((op_id, op_data))
            elif 'dtype' in op_id.lower() or 'change' in op_id.lower():
                dtype_ops.append((op_id, op_data))
            elif 'choose' in op_id.lower() or 'calculated' in op_id.lower():
                structure_ops.append((op_id, op_data))
            else:
                other_ops.append((op_id, op_data))

        # Split submenu
        if split_ops:
            split_menu = parent_menu.addMenu("Split")
            for op_id, op_data in sorted(split_ops, key=lambda x: x[1]['display_name']):
                action = split_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Rename submenu
        if rename_ops:
            rename_menu = parent_menu.addMenu("Rename")
            for op_id, op_data in sorted(rename_ops, key=lambda x: x[1]['display_name']):
                action = rename_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Data Type submenu
        if dtype_ops:
            dtype_menu = parent_menu.addMenu("Data Type")
            for op_id, op_data in sorted(dtype_ops, key=lambda x: x[1]['display_name']):
                action = dtype_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Structure submenu (Choose Columns, Calculated Columns)
        if structure_ops:
            struct_menu = parent_menu.addMenu("Structure")
            for op_id, op_data in sorted(structure_ops, key=lambda x: x[1]['display_name']):
                action = struct_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Other operations
        for op_id, op_data in sorted(other_ops, key=lambda x: x[1]['display_name']):
            action = parent_menu.addAction(op_data['display_name'])
            action.triggered.connect(
                lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
            )

    def _add_table_submenu(self, parent_menu, operations, column_name):
        """Add table operations (split, combine, transpose, etc.)"""
        # Group table operations by function type
        split_ops = []  # split_sheet
        combine_ops = []  # combine_sheets, append_datasets
        join_ops = []  # join_datasets
        transform_ops = []  # transpose, select_n_rows, query_sheet, promote_row_header
        filter_ops = []  # remove_rows, filter_rows
        other_ops = []

        for op_id, op_data in operations:
            if 'split' in op_id.lower() and 'sheet' in op_data['display_name'].lower():
                split_ops.append((op_id, op_data))
            elif 'combine' in op_id.lower() or 'union' in op_id.lower() or 'append' in op_id.lower():
                combine_ops.append((op_id, op_data))
            elif 'join' in op_id.lower():
                join_ops.append((op_id, op_data))
            elif 'transpose' in op_id.lower() or 'select' in op_id.lower() or 'query' in op_id.lower():
                transform_ops.append((op_id, op_data))
            elif 'promote' in op_id.lower() or 'remove_rows' in op_id or 'filter_rows' in op_id:
                transform_ops.append((op_id, op_data))
            else:
                other_ops.append((op_id, op_data))

        # Split submenu
        if split_ops:
            split_menu = parent_menu.addMenu("Split")
            for op_id, op_data in sorted(split_ops, key=lambda x: x[1]['display_name']):
                action = split_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Join submenu
        if join_ops:
            join_menu = parent_menu.addMenu("Join")
            for op_id, op_data in sorted(join_ops, key=lambda x: x[1]['display_name']):
                action = join_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Combine submenu
        if combine_ops:
            combine_menu = parent_menu.addMenu("Combine")
            for op_id, op_data in sorted(combine_ops, key=lambda x: x[1]['display_name']):
                action = combine_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Transform submenu
        if transform_ops:
            transform_menu = parent_menu.addMenu("Transform")
            for op_id, op_data in sorted(transform_ops, key=lambda x: x[1]['display_name']):
                action = transform_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Other operations
        for op_id, op_data in sorted(other_ops, key=lambda x: x[1]['display_name']):
            action = parent_menu.addAction(op_data['display_name'])
            action.triggered.connect(
                lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
            )

    def _add_financial_submenu(self, parent_menu, operations, column_name):
        """Add financial operations"""
        for op_id, op_data in operations:
            action = parent_menu.addAction(op_data['display_name'])
            action.triggered.connect(
                lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
            )
            
    def _add_ml_submenu(self, parent_menu, operations, column_name):
        """Add ML operations with sub-submenus organized by category"""
        # Operations to exclude from the menu (no-ops or duplicates)
        exclude_ops = {'ml_classify', 'ml_predict', 'ml_outlier', 'ml_forecast', 'ml_train'}

        # Group ML operations by subcategory
        supervised_linear = []   # Linear Regression, GLM
        supervised_tree = []     # Decision Tree, Random Forest, Gradient Boosting, XGBoost, LightGBM
        clustering = []          # K-Means, DBSCAN, Gaussian Mixture
        time_series = []         # ARIMA, ETS
        anomaly_detection = []   # Isolation Forest, Z-Score, IQR, LOF
        audit_ops = []           # ML Risk Score

        for op_id, op_data in operations:
            # Skip excluded operations
            if op_id in exclude_ops:
                continue

            if op_id in ('ml_linear_regression', 'ml_glm'):
                supervised_linear.append((op_id, op_data))
            elif op_id in ('ml_decision_tree', 'ml_random_forest', 'ml_gradient_boosting',
                           'ml_xgboost', 'ml_lightgbm'):
                supervised_tree.append((op_id, op_data))
            elif op_id in ('ml_cluster', 'ml_dbscan', 'ml_gmm'):
                clustering.append((op_id, op_data))
            elif op_id in ('ml_arima', 'ml_ets'):
                time_series.append((op_id, op_data))
            elif op_id in ('ml_anomaly_iforest', 'ml_anomaly_zscore', 'ml_anomaly_iqr', 'ml_anomaly_lof'):
                anomaly_detection.append((op_id, op_data))
            elif op_id in ('ml_risk_score',):
                audit_ops.append((op_id, op_data))

        # Anomaly Detection submenu
        if anomaly_detection:
            anomaly_menu = parent_menu.addMenu("Anomaly Detection")
            for op_id, op_data in sorted(anomaly_detection, key=lambda x: x[1]['display_name']):
                action = anomaly_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Clustering submenu
        if clustering:
            cluster_menu = parent_menu.addMenu("Clustering")
            for op_id, op_data in sorted(clustering, key=lambda x: x[1]['display_name']):
                action = cluster_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Supervised → Linear submenu
        if supervised_linear:
            linear_menu = parent_menu.addMenu("Supervised → Linear")
            for op_id, op_data in sorted(supervised_linear, key=lambda x: x[1]['display_name']):
                action = linear_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Supervised → Tree-Based submenu
        if supervised_tree:
            tree_menu = parent_menu.addMenu("Supervised → Tree-Based")
            for op_id, op_data in sorted(supervised_tree, key=lambda x: x[1]['display_name']):
                action = tree_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Time Series submenu
        if time_series:
            ts_menu = parent_menu.addMenu("Time Series")
            for op_id, op_data in sorted(time_series, key=lambda x: x[1]['display_name']):
                action = ts_menu.addAction(op_data['display_name'])
                action.triggered.connect(
                    lambda checked=False, op=op_id, col=column_name: self.on_transformation_selected(op, col)
                )

        # Audit submenu
        if audit_ops:
            audit_menu = parent_menu.addMenu("Audit")
            for op_id, op_data in sorted(audit_ops, key=lambda x: x[1]['display_name']):
                action = audit_menu.addAction(op_data['display_name'])
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
        # Use the transformed dataframe so newly created columns appear in the dialog
        current_df = self.pipeline.apply() if self.pipeline else self.original_dataframe
        dialog = TransformationDialogFactory.create_dialog(
            operation_id=operation_id,
            dataframe=current_df,
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

            # Update the shared Applied Steps panel
            self.steps_panel.refresh()

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

    def toggle_formula_bar(self, visible: bool = None):
        """Show/hide the formula bar (View > Formula Bar)."""
        if visible is None:
            visible = not self.formula_bar.isVisible()
        self.formula_bar.setVisible(visible)
        if visible:
            self.formula_expr_edit.setFocus()

    def _on_formula_apply(self):
        """Add a calculated column from the formula bar's expression."""
        if not self.pipeline:
            QMessageBox.warning(self, "No Data", "No data pipeline is active.")
            return

        output_column = self.formula_output_edit.text().strip()
        expression = self.formula_expr_edit.text().strip()
        if not output_column or not expression:
            QMessageBox.warning(self, "Formula Bar", "Enter both a column name and an expression.")
            return

        current_df = self.pipeline.apply()
        self.apply_transformation('custom_column_from_math', {
            'expression': expression,
            'output_column': output_column,
            'columns': list(current_df.columns),
        })
        self.formula_expr_edit.clear()

    def undo_last_step(self):
        """Removes the last transformation step."""
        if not self.pipeline or len(self.pipeline.get_steps()) == 0:
            return

        try:
            self.pipeline.remove_last_step()
            transformed_df = self.pipeline.apply()

            # Rebuild the shared Applied Steps panel (also cleans up the removed row's checkbox widget)
            self.steps_panel.refresh()

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
                self.steps_panel.refresh()
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
        """Populates the table with data from a Polars DataFrame, applying
        any active column AutoFilters first."""
        if df is None:
            self._last_full_df = None
            self.data_table.setRowCount(0)
            self.data_table.setColumnCount(0)
            return

        self._last_full_df = df
        filtered_df = self._apply_column_filters(df)
        display_df = filtered_df.head(1000)

        self.data_table.setRowCount(display_df.height)
        self.data_table.setColumnCount(display_df.width)
        self.data_table.setHorizontalHeaderLabels(display_df.columns)

        for row_idx in range(display_df.height):
            for col_idx, value in enumerate(display_df.row(row_idx)):
                item = QTableWidgetItem(str(value) if value is not None else "")
                self.data_table.setItem(row_idx, col_idx, item)

        self.data_table.resizeColumnsToContents()

        header = self.data_table.horizontalHeader()
        if hasattr(header, "set_filtered_columns"):
            filtered_indices = {
                display_df.columns.index(col) for col in self.column_filters
                if col in display_df.columns
            }
            header.set_filtered_columns(filtered_indices)

        if filtered_df.height != df.height:
            self.info_label.setText(
                f"Showing {filtered_df.height:,} of {df.height:,} rows (AutoFilter active) — "
                f"click a header's funnel icon to change it."
            )

    def _apply_column_filters(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply active AutoFilter selections (view-level only — does not
        modify the pipeline or its steps)."""
        if not self.column_filters:
            return df

        import polars as pl
        mask = None
        for col, allowed in self.column_filters.items():
            if col not in df.columns:
                continue
            allow_blank = BLANKS_LABEL in allowed
            text_allowed = [v for v in allowed if v != BLANKS_LABEL]
            col_expr = pl.col(col).cast(pl.Utf8, strict=False)
            col_mask = col_expr.is_in(text_allowed)
            if allow_blank:
                col_mask = col_mask | col_expr.is_null()
            mask = col_mask if mask is None else (mask & col_mask)

        return df.filter(mask) if mask is not None else df

    def _get_unique_display_values(self, column_name: str):
        """Unique values for a column, as displayed strings, for the filter popup."""
        if self._last_full_df is None or column_name not in self._last_full_df.columns:
            return []
        series = self._last_full_df[column_name]
        raw_values = series.cast(pl.Utf8, strict=False).unique().to_list()
        values = [v if v is not None else BLANKS_LABEL for v in raw_values]
        return sorted(values, key=str)

    @Slot(int)
    def _on_filter_button_clicked(self, column_index: int):
        """Show the AutoFilter checklist popup for the clicked column."""
        if self._last_full_df is None or column_index >= len(self._last_full_df.columns):
            return

        column_name = self._last_full_df.columns[column_index]
        values = self._get_unique_display_values(column_name)
        if not values:
            return

        current_selection = self.column_filters.get(column_name)

        popup = ColumnFilterPopup(column_name, values, current_selection, parent=self)
        popup.filtersApplied.connect(self._on_column_filter_applied)

        header = self.data_table.horizontalHeader()
        section_pos = header.sectionViewportPosition(column_index)
        global_pos = header.mapToGlobal(header.rect().bottomLeft())
        global_pos.setX(global_pos.x() + section_pos)
        popup.show_at(global_pos)

    def _on_column_filter_applied(self, column_name: str, selected):
        """Apply or clear a column's filter and refresh the grid."""
        if selected is None:
            self.column_filters.pop(column_name, None)
        else:
            self.column_filters[column_name] = selected

        if self._last_full_df is not None:
            self.populate_table(self._last_full_df)

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

    def _on_step_selection_changed(self, step_number):
        """Handle step selection changing in the shared Applied Steps panel."""
        if not self.pipeline or step_number is None:
            self.clear_inspector()
            return

        try:
            self.update_inspector(int(step_number))
        except (ValueError, TypeError):
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
        self.steps_panel.params_text.setPlainText(params_text)

        # Update Columns tab
        self.steps_panel.columns_tree.clear()
        if step.created_columns:
            for col in step.created_columns:
                col_info = self.pipeline.get_column_info(col)
                item = QTreeWidgetItem([col])
                if col_info:
                    item.setToolTip(0, f"Created by: {col_info['operation']} at step {col_info['created_by_step']}")
                self.steps_panel.columns_tree.addTopLevelItem(item)
        else:
            no_cols_item = QTreeWidgetItem(["No columns created"])
            self.steps_panel.columns_tree.addTopLevelItem(no_cols_item)

        # Update Preview tab
        step_df = self.pipeline.get_dataframe_at_step(step_number)
        self.populate_step_preview_table(step_df)

    def clear_inspector(self):
        """Clear all inspector tabs."""
        self.steps_panel.params_text.clear()
        self.steps_panel.columns_tree.clear()
        self.steps_panel.step_preview_table.setRowCount(0)
        self.steps_panel.step_preview_table.setColumnCount(0)

    def populate_step_preview_table(self, df: pl.DataFrame):
        """Populate the step preview table with a subset of the dataframe."""
        table = self.steps_panel.step_preview_table
        if df is None:
            table.setRowCount(0)
            table.setColumnCount(0)
            return

        # Show first 50 rows and first 10 columns for preview
        preview_df = df.head(50).select(df.columns[:10])

        table.setRowCount(preview_df.height)
        table.setColumnCount(preview_df.width)
        table.setHorizontalHeaderLabels(preview_df.columns)

        for row_idx in range(preview_df.height):
            for col_idx, value in enumerate(preview_df.row(row_idx)):
                item = QTableWidgetItem(str(value) if value is not None else "")
                table.setItem(row_idx, col_idx, item)

        table.resizeColumnsToContents()

    def export_transformations(self):
        """Export transformed data to file (CSV, JSON, or Parquet)."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox, QDialog, QVBoxLayout, QLabel, QRadioButton, QDialogButtonBox
        from pathlib import Path
        import json
        import polars as pl

        if not self.pipeline or self.pipeline.original_df is None:
            QMessageBox.warning(self, "No Data", "No data to export.")
            return

        # Show format selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Transformed Data")
        dialog.setMinimumWidth(300)
        layout = QVBoxLayout(dialog)

        label = QLabel("Select export format:")
        layout.addWidget(label)

        csv_radio = QRadioButton("CSV (.csv)")
        csv_radio.setChecked(True)
        layout.addWidget(csv_radio)

        json_radio = QRadioButton("JSON (.json)")
        layout.addWidget(json_radio)

        parquet_radio = QRadioButton("Parquet (.parquet)")
        layout.addWidget(parquet_radio)

        # Add metadata export option
        steps_radio = QRadioButton("Transformation Steps Only (.json)")
        layout.addWidget(steps_radio)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        # Determine format
        if csv_radio.isChecked():
            format = 'csv'
            ext = '.csv'
            filter_str = "CSV Files (*.csv)"
        elif json_radio.isChecked():
            format = 'json'
            ext = '.json'
            filter_str = "JSON Files (*.json)"
        elif parquet_radio.isChecked():
            format = 'parquet'
            ext = '.parquet'
            filter_str = "Parquet Files (*.parquet)"
        else:
            format = 'steps'
            ext = '.json'
            filter_str = "JSON Files (*.json)"

        # Get file path from user
        default_name = "transformed_data" if format != 'steps' else "transformation_steps"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            str(Path.home() / "Documents" / default_name),
            filter_str
        )

        if not file_path:
            return

        # Add extension if not present
        if not file_path.endswith(ext):
            file_path += ext

        try:
            if format == 'csv':
                # Export transformed data as CSV
                transformed_df = self.pipeline.apply()
                transformed_df.write_csv(file_path)
                msg = f"Data exported successfully.\nRows: {transformed_df.height:,}\nColumns: {transformed_df.width}"

            elif format == 'json':
                # Export transformed data as JSON
                transformed_df = self.pipeline.apply()
                transformed_df.write_json(file_path)
                msg = f"Data exported successfully.\nRows: {transformed_df.height:,}\nColumns: {transformed_df.width}"

            elif format == 'parquet':
                # Export transformed data as Parquet
                transformed_df = self.pipeline.apply()
                transformed_df.write_parquet(file_path)
                msg = f"Data exported successfully.\nRows: {transformed_df.height:,}\nColumns: {transformed_df.width}"

            else:  # steps export
                # Export transformation steps as JSON
                steps_data = []
                for i, step in enumerate(self.pipeline.get_steps()):
                    step_info = {
                        "step_number": i + 1,
                        "operation_id": step.operation_id,
                        "operation_name": OPERATION_REGISTRY.get(step.operation_id, {}).get('display_name', step.operation_id),
                        "parameters": step.params,
                        "timestamp": step.timestamp.isoformat() if step.timestamp else None,
                        "created_columns": step.created_columns
                    }
                    steps_data.append(step_info)

                export_data = {
                    "transformation_steps": steps_data,
                    "column_tracking": self.pipeline._column_tracking,
                    "total_steps": len(steps_data)
                }
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
                msg = f"Transformation steps exported.\nTotal steps: {len(steps_data)}"

            QMessageBox.information(self, "Export Successful", msg)

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{str(e)}")
