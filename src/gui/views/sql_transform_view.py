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
    QListWidget, QListWidgetItem, QCheckBox, QCompleter, QInputDialog
)
from PySide6.QtCore import Qt, Signal, Slot, QStringListModel
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor
import polars as pl
import pandas as pd
import re
from core.project_manager import Project, Dataset
from gui.theme import Colors


_SQL_MAJOR_CLAUSES = [
    'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT',
    'LEFT JOIN', 'RIGHT JOIN', 'FULL OUTER JOIN', 'FULL JOIN', 'INNER JOIN',
    'CROSS JOIN', 'JOIN', 'UNION ALL', 'UNION', 'WITH',
]
_SQL_UPPERCASE_KEYWORDS = _SQL_MAJOR_CLAUSES + [
    'AND', 'OR', 'ON', 'AS', 'DISTINCT', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'IN', 'NOT', 'NULL', 'IS', 'LIKE', 'BETWEEN', 'ASC', 'DESC', 'OVER',
    'PARTITION BY', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX',
]
# Longest-first so a multi-word clause (e.g. "GROUP BY") is matched whole,
# not shadowed by a shorter keyword that happens to be a prefix of it.
_SQL_UPPERCASE_KEYWORDS.sort(key=len, reverse=True)


def format_sql_text(query: str) -> str:
    """Pretty-print a SQL query: uppercase keywords, one major clause per
    line, one condition per line under WHERE/ON. String literals are
    protected from keyword replacement so a value like 'Smith and Co' is
    never touched. Falls back to returning the input unchanged if anything
    goes wrong - a formatter should never corrupt a query that already
    runs, even if it can't improve its layout."""
    if not query.strip():
        return query

    # Protect single-quoted string literals (including doubled '' escapes)
    # behind placeholders so clause/keyword detection never touches them.
    literals = []

    def _stash(m):
        literals.append(m.group(0))
        return f"\0LIT{len(literals) - 1}\0"

    protected = re.sub(r"'(?:[^']|'')*'", _stash, query)

    try:
        for kw in _SQL_UPPERCASE_KEYWORDS:
            protected = re.sub(r'(?<!\w)' + re.escape(kw) + r'(?!\w)', kw, protected, flags=re.IGNORECASE)

        for kw in _SQL_MAJOR_CLAUSES:
            protected = re.sub(r'\s*(?<!\w)' + re.escape(kw) + r'(?!\w)', f'\n{kw}', protected)

        protected = re.sub(r'\s+(AND|OR)(?!\w)', r'\n    \1', protected)

        lines = [line.rstrip() for line in protected.split('\n')]
        lines = [line for line in lines if line.strip()]
        result = '\n'.join(lines).strip()
    except Exception:
        return query

    for i, lit in enumerate(literals):
        result = result.replace(f"\0LIT{i}\0", lit)

    return result


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
    createDatasetRequested = Signal(str, object, list)  # name, df, source_table_names

    def __init__(self, parent=None, ai_sql_generator=None):
        super().__init__(parent)
        self.current_dataframe = None
        self.duckdb_conn = None
        self.registered_tables = {}
        self.current_project = None
        self.dataset_widgets = {}  # dataset id -> QListWidgetItem
        self.completer = None
        self.current_table_name = None
        self.last_query_result = None  # full (non-truncated) result of the last executed query
        self.last_query_text = ""
        self.ai_sql_generator = ai_sql_generator
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
        self.run_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                color: {Colors.TEXT_ON_ACCENT};
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.ACCENT_HOVER};
            }}
        """)
        self.run_btn.clicked.connect(self.execute_query)
        toolbar_layout.addWidget(self.run_btn)

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

        self.create_dataset_btn = QPushButton("Create New Dataset")
        self.create_dataset_btn.setToolTip(
            "Create a brand new dataset from this query's results — for cross-dataset\n"
            "queries (joins, unions) where the result doesn't belong to any one\n"
            "source dataset's pipeline."
        )
        self.create_dataset_btn.setStyleSheet(f"""
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
        self.create_dataset_btn.clicked.connect(self.create_dataset_from_results)
        toolbar_layout.addWidget(self.create_dataset_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_SECONDARY};
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
        """)
        self.clear_btn.clicked.connect(self.clear_query)
        toolbar_layout.addWidget(self.clear_btn)

        self.format_btn = QPushButton("Format SQL")
        self.format_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_SECONDARY};
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_TERTIARY};
            }}
        """)
        self.format_btn.clicked.connect(self.format_sql)
        toolbar_layout.addWidget(self.format_btn)

        self.ask_ai_btn = QPushButton("✨ Ask AI")
        self.ask_ai_btn.setToolTip(
            "Describe the query you want in plain language — AI writes the SQL,\n"
            "you review it, and you still click Execute yourself."
        )
        self.ask_ai_btn.setStyleSheet(f"""
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
        self.ask_ai_btn.clicked.connect(self.open_ai_sql_generator)
        toolbar_layout.addWidget(self.ask_ai_btn)

        toolbar_layout.addStretch()

        # Saved queries dropdown
        self.saved_queries_combo = QComboBox()
        self.saved_queries_combo.setStyleSheet(f"""
            QComboBox {{
                min-width: 180px;
                padding: 6px 12px;
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
            }}
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
        self.query_editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG_PRIMARY};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
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
        self.schema_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
                padding: 4px 8px;
            }}
        """)
        editor_layout.addWidget(self.schema_label)

        splitter.addWidget(editor_widget)

        # Bottom section: Results
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)

        # Results header
        results_header = QHBoxLayout()
        results_label = QLabel("Query Results")
        results_label.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 600;
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        results_header.addWidget(results_label)

        results_header.addStretch()

        self.row_count_label = QLabel("0 rows")
        self.row_count_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
                padding: 4px 8px;
                background-color: {Colors.BG_TERTIARY};
                border-radius: 4px;
            }}
        """)
        results_header.addWidget(self.row_count_label)

        results_layout.addLayout(results_header)

        # Wrap results table in scroll area for proper horizontal scrolling
        results_scroll = QScrollArea()
        results_scroll.setWidgetResizable(True)
        results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        results_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        results_scroll.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                background-color: {Colors.BG_PRIMARY};
            }}
        """)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.horizontalHeader().setStretchLastSection(False)
        self.results_table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.results_table.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                background-color: {Colors.BG_PRIMARY};
            }}
            QTableWidget::item {{
                padding: 8px;
                color: {Colors.TEXT_PRIMARY};
            }}
            QTableWidget::item:selected {{
                background-color: {Colors.ACCENT_SOFT};
            }}
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
        self.info_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                color: {Colors.TEXT_SECONDARY};
                font-size: 12px;
            }}
        """)
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
        for table_name in list(self.registered_tables.keys()):
            self._unregister_table(table_name)

        if not self.current_project:
            return

        # Ensure DuckDB connection exists
        if self.duckdb_conn is None:
            self.duckdb_conn = duckdb.connect(database=':memory:')

        # Automatically register all datasets as tables
        for dataset in self.current_project.list_datasets():
            item = self._ensure_dataset_list_item(dataset.id, dataset.name)

            # Auto-register the dataset as a table
            df = dataset.get_current_dataframe()
            if df is not None:
                table_name = self._sanitize_table_name(dataset.name)
                self._register_dataset_table(table_name, df)

        # Update the completer with all registered tables
        self._update_completer_model()
        self._update_schema_summary()

    def _ensure_dataset_list_item(self, dataset_id: str, display_name: str) -> QListWidgetItem:
        """Get (or create, checked by default) the Model Query checklist
        item for a dataset, keyed by its stable project id — not by name,
        since names can be renamed out from under a table registration."""
        item = self.dataset_widgets.get(dataset_id)
        if item is None:
            item = QListWidgetItem(display_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, dataset_id)
            self.dataset_list.addItem(item)
            self.dataset_widgets[dataset_id] = item
        elif item.text() != display_name:
            item.setText(display_name)
        return item

    def _update_schema_summary(self):
        """Show which tables are registered. Cross-dataset joins are
        already explained once, on the Model Query checklist's own
        tooltip - repeating "join across them" here on every table-count
        change was redundant."""
        n = len(self.registered_tables)
        if n == 0:
            self.schema_label.setText("No data loaded")
        elif n == 1:
            table_name = next(iter(self.registered_tables))
            self.schema_label.setText(f"Table: {table_name}")
        else:
            names = ", ".join(self.registered_tables.keys())
            self.schema_label.setText(f"Tables: {names}")

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
        from services.sql_query_service import trim_column_names
        df = trim_column_names(df)
        if self.duckdb_conn is None:
            self.duckdb_conn = duckdb.connect(database=':memory:')
        self.duckdb_conn.register(table_name, df)
        self.registered_tables[table_name] = df

    def refresh_dataset(self, dataset_name: str, df: pl.DataFrame, dataset_id: str = None):
        """Re-register one dataset's table with updated data (e.g. after
        upload, selection, or a transformation step changes it elsewhere)
        without touching any other registered table — keeps Model Query
        cross-dataset joins intact.

        Pass `dataset_id` (the project's stable id, not the display name)
        whenever it's available so the Model Query checklist gets/stays an
        entry for this dataset too — without it, the table is queryable by
        name but won't show up as a checkable join candidate."""
        table_name = self._sanitize_table_name(dataset_name)
        self._register_dataset_table(table_name, df)
        if dataset_id is not None:
            item = self._ensure_dataset_list_item(dataset_id, dataset_name)
            if item.checkState() != Qt.Checked:
                item.setCheckState(Qt.Checked)
        self._update_completer_model()
        self._update_schema_summary()

    def rename_dataset(self, dataset_id: str, old_name: str, new_name: str, df: pl.DataFrame):
        """A dataset was renamed elsewhere — move its table registration
        from the old sanitized name to the new one, and relabel its Model
        Query checklist entry, instead of leaving a stale table behind
        under a name nothing points to anymore."""
        old_table_name = self._sanitize_table_name(old_name)
        if old_table_name in self.registered_tables:
            self._unregister_table(old_table_name)
        self.refresh_dataset(new_name, df, dataset_id=dataset_id)

    def remove_dataset(self, dataset_id: str, name: str):
        """A dataset was deleted elsewhere — unregister its table (so
        querying it correctly fails instead of returning stale data) and
        drop its Model Query checklist entry."""
        table_name = self._sanitize_table_name(name)
        self._unregister_table(table_name)
        item = self.dataset_widgets.pop(dataset_id, None)
        if item is not None:
            row = self.dataset_list.row(item)
            if row >= 0:
                self.dataset_list.takeItem(row)
        self._update_completer_model()
        self._update_schema_summary()

    def _unregister_table(self, table_name: str):
        """Unregister a table from DuckDB, so it doesn't linger in the
        catalog once the dataset it came from is gone or replaced."""
        if table_name in self.registered_tables:
            del self.registered_tables[table_name]
            if self.duckdb_conn is not None:
                try:
                    self.duckdb_conn.unregister(table_name)
                except Exception:
                    pass  # already gone / never actually registered

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
        for old_table_name in list(self.registered_tables.keys()):
            self._unregister_table(old_table_name)

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

        from services.sql_query_service import trim_column_names
        df = trim_column_names(df)

        # Register the Polars DataFrame directly with DuckDB using the provided table name
        self.duckdb_conn.register(table_name, df)
        self.registered_tables[table_name] = df

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
            self.last_query_result = result_df
            self.last_query_text = query

            # Display results
            self.display_results(result_df)

            # Emit data changed signal
            self.dataChanged.emit(result_df)

            self.update_info(
                f"Query executed successfully. Result: {result_df.shape[0]:,} rows × {result_df.shape[1]} columns"
            )

        except Exception as e:
            self.last_query_result = None
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

    @Slot()
    def create_dataset_from_results(self):
        """Create a brand new dataset from the last executed query's full
        result set — the right choice for a cross-dataset Model Query
        (a join/union) whose result doesn't semantically belong to any one
        source dataset's pipeline."""
        if self.last_query_result is None:
            QMessageBox.warning(self, "No Results", "Run a query first.")
            return

        default_name = "Query Result"
        name, ok = QInputDialog.getText(
            self, "Create New Dataset", "Name for the new dataset:", text=default_name
        )
        if not ok or not name.strip():
            return

        # Best-effort lineage: which currently-registered tables does the
        # query text actually reference by name.
        query_lower = self.last_query_text.lower()
        referenced_tables = [
            t for t in self.registered_tables
            if re.search(r'\b' + re.escape(t.lower()) + r'\b', query_lower)
        ]

        self.createDatasetRequested.emit(name.strip(), self.last_query_result, referenced_tables)

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
        """Pretty-print the query: uppercase keywords, one major clause per
        line, one condition per line under WHERE. The previous version only
        uppercased keywords with no layout changes at all - on SQL an LLM
        had already written in uppercase (the common case), it looked and
        behaved like a dead button."""
        query = self.query_editor.toPlainText()
        self.query_editor.setPlainText(format_sql_text(query))

    @Slot()
    def open_ai_sql_generator(self):
        """Open the natural-language-to-SQL dialog. The dialog only ever
        returns text via sql_accepted — nothing is executed until the
        auditor reviews what lands in the editor and clicks Execute
        themselves, same as a query they typed by hand."""
        if not self.ai_sql_generator:
            QMessageBox.warning(
                self, "AI Not Available",
                "AI SQL generation isn't configured for this session."
            )
            return
        if not self.registered_tables:
            QMessageBox.warning(self, "No Data", "Please select at least one dataset first.")
            return

        from gui.dialogs.ai_sql_generator_dialog import AISQLGeneratorDialog
        dialog = AISQLGeneratorDialog(self.registered_tables, self.ai_sql_generator, self)
        dialog.sql_accepted.connect(self._on_ai_sql_accepted)
        dialog.exec()

    def _on_ai_sql_accepted(self, sql: str):
        """Insert AI-generated SQL into the editor and run a quick EXPLAIN-
        based syntax check — the same kind of check the query gets before
        Execute, just surfaced immediately rather than waiting for the
        auditor to click Execute to find out it doesn't parse. The AI SQL
        dialog already runs this same check before Insert is even
        clickable, so reaching a failure here should be rare — but a
        quiet status-bar line is easy to miss, and this is the one point
        where a bad query could otherwise go straight to Execute
        unnoticed, so it's a blocking dialog instead."""
        self.query_editor.setPlainText(sql)

        if self.duckdb_conn is not None:
            try:
                self.duckdb_conn.execute(f"EXPLAIN {sql}")
                self.update_info("AI-generated query inserted — looks syntactically valid. Review it, then click Execute.")
            except Exception as e:
                self.update_info(f"AI-generated query inserted, but failed a syntax check: {e}")
                QMessageBox.warning(
                    self, "Query May Not Run",
                    f"The inserted query failed a syntax/reference check and will likely fail if you "
                    f"click Execute:\n\n{e}\n\nReview and correct it before running."
                )
        else:
            self.update_info("AI-generated query inserted. Review it, then click Execute.")

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
