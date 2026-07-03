"""
SQL Transform View with DuckDB
Provides full SQL interface for data transformations with custom functions.
"""
try:
    import duckdb
except ImportError:
    duckdb = None
    print("Warning: duckdb not installed. SQL functionality will be limited.")
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QMessageBox, QGroupBox, QComboBox, QScrollArea,
    QListWidget, QListWidgetItem, QCheckBox, QCompleter
)
from PySide6.QtCore import Qt, Signal, Slot, QStringListModel
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor
import polars as pl
import pandas as pd
import re
from core.project_manager import Project, Dataset


class SQLSyntaxHighlighter(QSyntaxHighlighter):
    """SQL syntax highlighter for the query editor - Light mode colors."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Define formats - Light mode colors
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#2563eb"))  # Blue
        self.keyword_format.setFontWeight(QFont.Bold)

        self.function_format = QTextCharFormat()
        self.function_format.setForeground(QColor("#9333ea"))  # Purple

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#dc2626"))  # Red
        self.string_format.setFontItalic(True)

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6b7280"))  # Gray
        self.comment_format.setFontItalic(True)

        # SQL keywords
        self.keywords = [
            'SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'FULL',
            'ON', 'GROUP', 'BY', 'HAVING', 'ORDER', 'LIMIT', 'OFFSET', 'UNION',
            'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'AS', 'AND',
            'OR', 'NOT', 'IN', 'IS', 'NULL', 'BETWEEN', 'LIKE', 'CASE', 'WHEN',
            'THEN', 'ELSE', 'END', 'DISTINCT', 'INTO', 'VALUES', 'SET', 'WHERE'
        ]

        # DuckDB specific functions
        self.functions = [
            # String functions
            'UPPER', 'LOWER', 'TRIM', 'LTRIM', 'RTRIM', 'LENGTH', 'SUBSTRING',
            'CONCAT', 'CONCAT_WS', 'REPLACE', 'REVERSE', 'SPLIT_PART',
            'UPPER', 'INITCAP', 'STRPTIME', 'STRFTIME',

            # Math functions
            'ABS', 'ROUND', 'CEIL', 'FLOOR', 'SQRT', 'POWER', 'EXP', 'LOG',
            'LOG10', 'MOD', 'SIGN', 'GREATEST', 'LEAST',

            # Date functions
            'CURRENT_DATE', 'CURRENT_TIMESTAMP', 'NOW', 'DATE', 'INTERVAL',
            'AGE', 'EXTRACT', 'DATE_TRUNC', 'DATE_PART',

            # Type conversion
            'CAST', 'CONVERT', 'TYPEOF',

            # Aggregation
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'MEDIAN', 'STDDEV', 'VARIANCE',
            'FIRST', 'LAST', 'STRING_AGG', 'ARRAY_AGG',

            # Window functions
            'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'PERCENT_RANK', 'CUME_DIST',
            'NTILE', 'LAG', 'LEAD', 'FIRST_VALUE', 'LAST_VALUE', 'NTH_VALUE',

            # Conditional
            'COALESCE', 'NULLIF', 'IFNULL', 'NVL',

            # CaatMaster custom functions (will be registered)
            'ZSCORE', 'PERCENT_RANK', 'RANK', 'ANOMALY_IFOREST', 'ANOMALY_ZSCORE',
            'BENFORD_LAW', 'SOUNDEX'
        ]

    def highlightBlock(self, text):
        """Highlight a block of text."""
        # Comments (-- comments first)
        comment_pattern = re.compile(r'--.*$', re.MULTILINE)
        for match in comment_pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self.comment_format)

        # String literals
        string_pattern = re.compile(r"'(?:[^'\\]|\\.)*'")
        for match in string_pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self.string_format)

        # Keywords
        for keyword in self.keywords:
            pattern = re.compile(r'\b' + keyword + r'\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), self.keyword_format)

        # Functions
        for function in self.functions:
            pattern = re.compile(r'\b' + function + r'\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), self.function_format)


class CompletingTextEdit(QTextEdit):
    """QTextEdit with QCompleter support for SQL keywords and table/column names."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.completer = None
        self.completer_popup = None

    def setCompleter(self, completer):
        """Set the completer for this text edit."""
        if self.completer:
            self.completer.activated.disconnect(self.insertCompletion)

        self.completer = completer
        if completer:
            completer.setWidget(self)
            completer.activated.connect(self.insertCompletion)


    def insertCompletion(self, completion):
        """Insert completion into text at cursor position."""
        if not self.completer:
            return

        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def textUnderCursor(self):
        """Get text under cursor for completion prefix."""
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        return tc.selectedText()

    def keyPressEvent(self, event):
        """Handle key press events for completer."""
        if self.completer and self.completer.popup().isVisible():
            key = event.key()
            if key in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape,
                      Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return

        # Let parent handle the key press
        super().keyPressEvent(event)

        if not self.completer:
            return

        completion_prefix = self.textUnderCursor()
        if completion_prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completion_prefix)
            if len(completion_prefix) >= 2:  # Show completer after 2 chars
                popup = self.completer.popup()
                cursor_rect = self.cursorRect()
                cursor_rect.setWidth(popup.sizeHintForColumn(0)
                                   + popup.verticalScrollBar().sizeHint().width())
                self.completer.complete(cursor_rect)
            else:
                self.completer.popup().hide()


class SQLTransformView(QWidget):
    """SQL interface for data transformations using DuckDB."""

    dataChanged = Signal(pl.DataFrame)
    applyToPipelineRequested = Signal(str, str)  # query, table_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_dataframe = None
        self.duckdb_conn = None
        self.registered_tables = {}
        self.current_project = None
        self.dataset_widgets = {}  # dataset id -> QListWidgetItem
        self.completer = None
        self.current_table_name = None
        self.setup_ui()

    def setup_ui(self):
        """Set up the SQL interface UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create main splitter
        splitter = QSplitter(Qt.Vertical)

        # Top section: Query editor
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)

        # Toolbar for query actions
        toolbar_layout = QHBoxLayout()

        self.run_btn = QPushButton("▶ Execute")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.run_btn.clicked.connect(self.execute_query)
        toolbar_layout.addWidget(self.run_btn)

        from gui.theme import Colors
        self.apply_pipeline_btn = QPushButton("Apply to Dataset")
        self.apply_pipeline_btn.setToolTip(
            "Record this query as a step on the dataset's pipeline, so it shows up in\n"
            "Applied Steps, is part of the audit trail, and replays when the source refreshes."
        )
        self.apply_pipeline_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.ACCENT};
                border: 1px solid {Colors.ACCENT};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.ACCENT_SOFT};
            }}
        """)
        self.apply_pipeline_btn.clicked.connect(self.apply_to_pipeline)
        toolbar_layout.addWidget(self.apply_pipeline_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9fafb;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_query)
        toolbar_layout.addWidget(self.clear_btn)

        self.format_btn = QPushButton("Format SQL")
        self.format_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9fafb;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
            }
        """)
        self.format_btn.clicked.connect(self.format_sql)
        toolbar_layout.addWidget(self.format_btn)

        toolbar_layout.addStretch()

        # Saved queries dropdown
        self.saved_queries_combo = QComboBox()
        self.saved_queries_combo.setStyleSheet("""
            QComboBox {
                min-width: 180px;
                padding: 6px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
            }
        """)
        self.saved_queries_combo.addItem("Saved Queries...")
        self.saved_queries_combo.addItems([
            "Basic SELECT",
            "Filter with WHERE",
            "Group & Aggregate",
            "Join Example",
            "Window Functions",
            "Z-Score Calculation",
            "Anomaly Detection"
        ])
        self.saved_queries_combo.currentIndexChanged.connect(self.load_saved_query)
        toolbar_layout.addWidget(QLabel("Template:"))
        toolbar_layout.addWidget(self.saved_queries_combo)

        editor_layout.addLayout(toolbar_layout)

        # Dataset selector — Model Query: every checked dataset is registered
        # as a table you can JOIN against in a single query (GL-to-subledger
        # ties, three-way matches, etc.) without any Table.Join gymnastics.
        model_query_label = QLabel("Model Query — check datasets to query across them:")
        model_query_label.setToolTip(
            "Every checked dataset becomes a table you can reference by name in the query below.\n"
            "e.g. SELECT g.*, s.vendor FROM GL_Entries g JOIN Subledger s ON g.gl_id = s.gl_id"
        )
        from gui.theme import Colors
        model_query_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-weight: 600;")
        dataset_selector_layout = QHBoxLayout()
        dataset_selector_layout.addWidget(model_query_label)
        self.dataset_list = QListWidget()
        self.dataset_list.setMaximumHeight(80)
        self.dataset_list.setSelectionMode(QListWidget.NoSelection)
        self.dataset_list.itemChanged.connect(self.on_dataset_selection_changed)
        dataset_selector_layout.addWidget(self.dataset_list)
        editor_layout.addLayout(dataset_selector_layout)

        # Query editor with syntax highlighting - Light mode
        self.query_editor = CompletingTextEdit()
        self.query_editor.setFont(QFont("Consolas", 10))
        self.query_editor.setMinimumHeight(120)
        self.query_editor.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #111827;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 8px;
            }
        """)

        # Apply syntax highlighting
        self.highlighter = SQLSyntaxHighlighter(self.query_editor.document())

        # Setup auto-completer
        self.completer = QCompleter(self)
        self.completer.setModelSorting(QCompleter.CaseInsensitivelySortedModel)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setWrapAround(False)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        # Use custom CompletingTextEdit that supports QCompleter
        self.query_editor.setCompleter(self.completer)
        self._update_completer_model()

        editor_layout.addWidget(self.query_editor)

        # Schema info
        self.schema_label = QLabel("No data loaded")
        self.schema_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 12px;
                padding: 4px 8px;
            }
        """)
        editor_layout.addWidget(self.schema_label)

        splitter.addWidget(editor_widget)

        # Bottom section: Results
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)

        # Results header
        results_header = QHBoxLayout()
        results_label = QLabel("Query Results")
        results_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 600;
                color: #111827;
            }
        """)
        results_header.addWidget(results_label)

        results_header.addStretch()

        self.row_count_label = QLabel("0 rows")
        self.row_count_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 12px;
                padding: 4px 8px;
                background-color: #f3f4f6;
                border-radius: 4px;
            }
        """)
        results_header.addWidget(self.row_count_label)

        results_layout.addLayout(results_header)

        # Wrap results table in scroll area for proper horizontal scrolling
        results_scroll = QScrollArea()
        results_scroll.setWidgetResizable(True)
        results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        results_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        results_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background-color: white;
            }
        """)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.horizontalHeader().setStretchLastSection(False)
        self.results_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.results_table.setStyleSheet("""
            QTableWidget {
                border: none;
                background-color: white;
            }
            QTableWidget::item {
                padding: 8px;
                color: #111827;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
            }
        """)
        results_scroll.setWidget(self.results_table)
        results_layout.addWidget(results_scroll)

        splitter.addWidget(results_widget)

        # Info panel
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(80)
        self.info_text.setStyleSheet("""
            QTextEdit {
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                color: #374151;
                font-size: 12px;
            }
        """)
        self.info_text.setPlainText(
            "DuckDB SQL Editor\n"
            "• Load data from the Data Workspace to begin\n"
            "• Write standard SQL queries to transform data\n"
            "• Use templates for common operations"
        )
        info_layout.addWidget(self.info_text)

        splitter.addWidget(info_widget)

        splitter.setSizes([200, 350, 100])
        main_layout.addWidget(splitter)

    def set_project(self, project: Project):
        """Set the current project and update dataset selector."""
        self.current_project = project
        self._update_dataset_selector()

    def _update_dataset_selector(self):
        """Update the dataset list with datasets from current project."""
        self.dataset_list.clear()
        self.dataset_widgets.clear()
        self.registered_tables.clear()

        if not self.current_project:
            return

        # Ensure DuckDB connection exists
        if self.duckdb_conn is None:
            self.duckdb_conn = duckdb.connect(database=':memory:')

        # Automatically register all datasets as tables
        for dataset in self.current_project.list_datasets():
            item = QListWidgetItem(dataset.name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)  # Auto-check to auto-register
            item.setData(Qt.UserRole, dataset.id)
            self.dataset_list.addItem(item)
            self.dataset_widgets[dataset.id] = item

            # Auto-register the dataset as a table
            df = dataset.get_current_dataframe()
            if df is not None:
                table_name = self._sanitize_table_name(dataset.name)
                self._register_dataset_table(table_name, df)

        # Update the completer with all registered tables
        self._update_completer_model()
        self._update_schema_summary()

    def _update_schema_summary(self):
        """Show how many tables are registered so it's obvious a cross-dataset
        (Model) query is possible, not just single-table filtering."""
        n = len(self.registered_tables)
        if n == 0:
            self.schema_label.setText("No data loaded")
        elif n == 1:
            table_name = next(iter(self.registered_tables))
            self.schema_label.setText(f"Table: {table_name}")
        else:
            names = ", ".join(self.registered_tables.keys())
            self.schema_label.setText(f"{n} tables registered — join across them: {names}")

    @Slot(QListWidgetItem)
    def on_dataset_selection_changed(self, item):
        """Handle dataset selection change."""
        if not item:
            return
        dataset_id = item.data(Qt.UserRole)
        dataset = self.current_project.get_dataset(dataset_id) if self.current_project else None
        if dataset:
            if item.checkState() == Qt.Checked:
                # Register dataset as table
                df = dataset.get_current_dataframe()
                if df is not None:
                    table_name = self._sanitize_table_name(dataset.name)
                    self._register_dataset_table(table_name, df)
            else:
                # Unregister table
                table_name = self._sanitize_table_name(dataset.name)
                self._unregister_table(table_name)
            # Update completer
            self._update_completer_model()
            self._update_schema_summary()

    def _sanitize_table_name(self, name: str) -> str:
        """Sanitize dataset name for use as SQL table name - preserves case and most characters."""
        import re
        # Replace spaces and special characters (except underscore) with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure it starts with a letter or underscore
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
            sanitized = '_' + sanitized
        return sanitized

    def _register_dataset_table(self, table_name: str, df: pl.DataFrame):
        """Register a dataset as a table in DuckDB."""
        if self.duckdb_conn is None:
            self.duckdb_conn = duckdb.connect(database=':memory:')
        self.duckdb_conn.register(table_name, df)
        self.registered_tables[table_name] = df

    def refresh_dataset(self, dataset_name: str, df: pl.DataFrame):
        """Re-register one dataset's table with updated data (e.g. after a
        transformation step changes it elsewhere) without touching any other
        registered table — keeps Model Query cross-dataset joins intact."""
        table_name = self._sanitize_table_name(dataset_name)
        self._register_dataset_table(table_name, df)
        self._update_completer_model()
        self._update_schema_summary()

    def _unregister_table(self, table_name: str):
        """Unregister a table from DuckDB."""
        if table_name in self.registered_tables:
            del self.registered_tables[table_name]
        # Note: DuckDB doesn't have unregister; we could close and recreate connection
        # For simplicity, we'll just remove from dict and not query it.

    def _update_completer_model(self):
        """Update completer model with SQL keywords, table names, and column names."""
        if not self.completer:
            return

        completions = []

        # SQL keywords
        sql_keywords = [
            'SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'FULL',
            'ON', 'GROUP', 'BY', 'HAVING', 'ORDER', 'LIMIT', 'OFFSET', 'UNION',
            'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'AS', 'AND',
            'OR', 'NOT', 'IN', 'IS', 'NULL', 'BETWEEN', 'LIKE', 'CASE', 'WHEN',
            'THEN', 'ELSE', 'END', 'DISTINCT', 'INTO', 'VALUES', 'SET', 'WHERE'
        ]
        completions.extend(sql_keywords)

        # Table names
        completions.extend(self.registered_tables.keys())

        # Column names from registered tables
        for table_name, df in self.registered_tables.items():
            completions.extend(df.columns)

        # Remove duplicates while preserving case (convert to lower for comparison)
        seen = set()
        unique_completions = []
        for item in completions:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                unique_completions.append(item)

        # Create and set model
        model = QStringListModel(unique_completions, self.completer)
        self.completer.setModel(model)

    @Slot(pl.DataFrame)
    def set_dataframe(self, df: pl.DataFrame, table_name: str = None):
        """Set the dataframe for SQL operations.

        Args:
            df: The Polars DataFrame to register
            table_name: Optional table name (defaults to 'data' if not provided)
        """
        self.current_dataframe = df

        # Use provided table name or default to 'data'
        if table_name is None:
            table_name = 'data'

        # Sanitize the table name
        sanitized_name = self._sanitize_table_name(table_name)
        self.current_table_name = sanitized_name

        # Clear existing tables before registering new one (to avoid duplicates like 'data' and 'customer')
        self.registered_tables.clear()

        # Register with DuckDB
        self._register_dataframe(df, sanitized_name)

        # Update schema info
        cols = df.columns
        self.schema_label.setText(f"Table: {sanitized_name} | Columns: {len(cols)} | Rows: {len(df):,}")
        self.update_info(f"Data loaded: {len(df):,} rows × {len(cols)} columns")

    def _register_dataframe(self, df: pl.DataFrame, table_name: str):
        """Register a Polars DataFrame with DuckDB."""
        if self.duckdb_conn is None:
            self.duckdb_conn = duckdb.connect(database=':memory:')

        # DuckDB requires at least one column to register a table
        if df is None or len(df.columns) == 0:
            return

        # Register the Polars DataFrame directly with DuckDB using the provided table name
        self.duckdb_conn.register(table_name, df)
        self.registered_tables[table_name] = df

        # Register any columns for custom functions as DuckDB relations
        for col in df.columns:
            # Create a Polars DataFrame with just this column
            col_df = df.select(pl.col(col))
            if len(col_df.columns) > 0:
                self.duckdb_conn.register(f'col_{col}', col_df)

    @Slot()
    def execute_query(self):
        """Execute the current SQL query."""
        if not self.registered_tables:
            QMessageBox.warning(self, "No Data", "Please select datasets first.")
            return

        query = self.query_editor.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "Empty Query", "Please enter a SQL query.")
            return

        try:
            # Execute query
            result_pandas = self.duckdb_conn.execute(query).fetchdf()

            # Convert to Polars
            result_df = pl.from_pandas(result_pandas)

            # Display results
            self.display_results(result_df)

            # Emit data changed signal
            self.dataChanged.emit(result_df)

            self.update_info(
                f"Query executed successfully. Result: {result_df.shape[0]:,} rows × {result_df.shape[1]} columns"
            )

        except Exception as e:
            error_msg = f"Query execution failed:\n{str(e)}"
            self.update_info(error_msg)
            QMessageBox.critical(self, "Query Error", error_msg)

    @Slot()
    def apply_to_pipeline(self):
        """Record the current query as a step on the active dataset's pipeline
        instead of leaving it as a one-off result in this view."""
        query = self.query_editor.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "Empty Query", "Please enter a SQL query.")
            return
        if not self.current_table_name:
            QMessageBox.warning(self, "No Data", "Please select a dataset first.")
            return

        self.applyToPipelineRequested.emit(query, self.current_table_name)

    def display_results(self, df: pl.DataFrame):
        """Display query results in the table."""
        if df is None:
            self.results_table.setRowCount(0)
            self.results_table.setColumnCount(0)
            self.row_count_label.setText("0 rows")
            return

        # Limit to first 1000 rows for display
        display_df = df.head(1000)

        self.results_table.setRowCount(display_df.height)
        self.results_table.setColumnCount(display_df.width)
        self.results_table.setHorizontalHeaderLabels(display_df.columns)

        for row_idx in range(display_df.height):
            for col_idx, value in enumerate(display_df.row(row_idx)):
                item = QTableWidgetItem(str(value) if value is not None else "")
                self.results_table.setItem(row_idx, col_idx, item)

        self.results_table.resizeColumnsToContents()

        self.row_count_label.setText(f"{len(df):,} rows")

    def update_info(self, message: str):
        """Update the information panel."""
        self.info_text.setPlainText(message)

    @Slot()
    def clear_query(self):
        """Clear the query editor."""
        self.query_editor.clear()
        self.update_info("Query editor cleared.")

    @Slot()
    def format_sql(self):
        """Format the SQL query (basic formatting)."""
        query = self.query_editor.toPlainText()

        # Basic formatting: uppercase keywords
        keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'JOIN', 'LEFT', 'RIGHT',
                   'INNER', 'OUTER', 'ON', 'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT',
                   'UNION', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER']

        for keyword in keywords:
            pattern = re.compile(r'\b' + keyword + r'\b', re.IGNORECASE)
            query = pattern.sub(keyword.upper(), query)

        self.query_editor.setPlainText(query)

    @Slot(int)
    def load_saved_query(self, index):
        """Load a saved query template."""
        if index == 0:
            return

        templates = {
            1: """SELECT *
FROM data
LIMIT 100""",

            2: """SELECT *
FROM data
WHERE condition = 'value'
LIMIT 100""",

            3: """SELECT column,
       COUNT(*) as count,
       AVG(numeric_column) as avg_value
FROM data
GROUP BY column
ORDER BY count DESC
LIMIT 50""",

            4: """SELECT a.*, b.*
FROM data a
JOIN data b ON a.id = b.related_id""",

            5: """SELECT *,
       ROW_NUMBER() OVER (PARTITION BY category ORDER BY value DESC) as rank
FROM data
ORDER BY category, rank""",

            6: """SELECT *,
       (value - AVG(value) OVER ()) / STDDEV(value) OVER () as z_score
FROM data""",

            7: """WITH stats AS (
    SELECT AVG(value) as mean,
           STDDEV(value) as std
    FROM data
)
SELECT *,
       CASE
           WHEN ABS((value - mean) / NULLIF(std, 0)) > 2 THEN 'Anomaly'
           ELSE 'Normal'
       END as status
FROM data, stats"""
        }

        if index in templates:
            self.query_editor.setPlainText(templates[index])
            self.update_info(f"Loaded query template. Click 'Execute' to run.")

        # Reset combo to first item
        self.saved_queries_combo.setCurrentIndex(0)
