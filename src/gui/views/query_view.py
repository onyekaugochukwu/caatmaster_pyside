"""
SQL Query Editor View - Execute SQL queries on loaded data
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QSplitter, QTextEdit, QComboBox, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QFileDialog, QProgressBar, QGroupBox
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextDocument, QIcon
from pathlib import Path
import re


class SQLHighlighter(QSyntaxHighlighter):
    """SQL syntax highlighter"""

    def __init__(self, document: QTextDocument):
        super().__init__(document)

        # Define SQL keywords
        self.keywords = [
            'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'LIKE',
            'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'AS',
            'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET',
            'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER',
            'UNION', 'INTERSECT', 'EXCEPT', 'DISTINCT', 'CASE', 'WHEN',
            'THEN', 'ELSE', 'END', 'NULL', 'IS', 'BETWEEN', 'EXISTS',
            'AVG', 'COUNT', 'SUM', 'MIN', 'MAX', 'CAST', 'COALESCE'
        ]

        # Keyword format
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#0000FF"))
        self.keyword_format.setFontWeight(QFont.Bold)

        # String format
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#008000"))

        # Comment format
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#808080"))
        self.comment_format.setFontItalic(True)

        # Number format
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#FF0000"))

    def highlightBlock(self, text: str):
        """Highlight a block of text"""
        # Highlight keywords
        for keyword in self.keywords:
            pattern = re.compile(r'\b' + keyword + r'\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), self.keyword_format)

        # Highlight strings
        pattern = re.compile(r"'[^']*'")
        for match in pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self.string_format)

        # Highlight comments
        pattern = re.compile(r'--[^\n]*')
        for match in pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self.comment_format)

        # Highlight numbers
        pattern = re.compile(r'\b\d+\.?\d*\b')
        for match in pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(), self.number_format)


class QueryView(QWidget):
    """SQL query editor and execution view"""

    query_executed = Signal(object)  # Signal when query is executed successfully

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_dataframe = None
        self.sql_service = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Header with actions
        header_layout = QHBoxLayout()

        title = QLabel("SQL Query Editor")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Table selector
        self.table_combo = QComboBox()
        self.table_combo.setMinimumWidth(200)
        self.table_combo.currentTextChanged.connect(self.on_table_changed)
        header_layout.addWidget(QLabel("Active Table:"))
        header_layout.addWidget(self.table_combo)

        main_layout.addLayout(header_layout)

        # Create horizontal splitter
        h_splitter = QSplitter(Qt.Horizontal)

        # Left panel - Schema browser
        schema_panel = QGroupBox("Schema Browser")
        schema_layout = QVBoxLayout()

        schema_label = QLabel("Tables and Columns:")
        schema_label.setStyleSheet("font-weight: bold;")
        schema_layout.addWidget(schema_label)

        self.schema_tree = QTreeWidget()
        self.schema_tree.setHeaderLabels(["Name", "Type"])
        self.schema_tree.setColumnWidth(0, 200)
        self.schema_tree.itemDoubleClicked.connect(self.insert_column_name)
        schema_layout.addWidget(self.schema_tree)

        schema_panel.setLayout(schema_layout)
        h_splitter.addWidget(schema_panel)

        # Right panel - Query editor and results
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Sample queries
        sample_layout = QHBoxLayout()
        sample_layout.addWidget(QLabel("Sample Queries:"))

        self.sample_combo = QComboBox()
        self.sample_combo.addItems([
            "Select Sample Query...",
            "SELECT - All data",
            "FILTER - Where clause",
            "AGGREGATE - Group by",
            "JOIN - Multiple tables",
            "ORDER - Sort data",
            "CALCULATE - New columns"
        ])
        self.sample_combo.currentIndexChanged.connect(self.insert_sample_query)
        sample_layout.addWidget(self.sample_combo)
        sample_layout.addStretch()

        right_layout.addLayout(sample_layout)

        # Query editor
        editor_label = QLabel("SQL Query:")
        editor_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(editor_label)

        self.query_editor = QTextEdit()
        self.query_editor.setMinimumHeight(200)
        self.query_editor.setMaximumHeight(300)
        self.query_editor.setPlaceholderText(
            "-- Write your SQL query here\n-- Use the active table name from the dropdown\n-- Double-click columns in schema browser to insert them\n\nSELECT * FROM <table_name> LIMIT 1000;"
        )
        # Apply syntax highlighting
        self.highlighter = SQLHighlighter(self.query_editor.document())
        self.query_editor.setFont(QFont("Courier", 10))
        right_layout.addWidget(self.query_editor)

        # Action buttons
        button_layout = QHBoxLayout()

        self.execute_btn = QPushButton("▶ Execute Query")
        self.execute_btn.setStyleSheet("""
            QPushButton {
                background: #28a745;
                color: white;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #218838;
            }
        """)
        self.execute_btn.clicked.connect(self.execute_query)
        button_layout.addWidget(self.execute_btn)

        self.validate_btn = QPushButton("✓ Validate")
        self.validate_btn.clicked.connect(self.validate_query)
        button_layout.addWidget(self.validate_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_editor)
        button_layout.addWidget(self.clear_btn)

        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()

        right_layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        # Results table
        results_label = QLabel("Query Results:")
        results_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(results_label)

        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                selection-background-color: #0078d4;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        right_layout.addWidget(self.results_table)

        # Results info
        self.results_info = QLabel("")
        self.results_info.setStyleSheet("color: #666; font-size: 12px; padding: 5px;")
        right_layout.addWidget(self.results_info)

        h_splitter.addWidget(right_panel)
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 3)

        main_layout.addWidget(h_splitter)

    def set_dataframe(self, df):
        """Set the current data for SQL queries"""
        self.current_dataframe = df
        table_name = "data"  # Default table name

        # Initialize SQL service
        from services.sql_query_service import SQLQueryService
        if self.sql_service is None:
            self.sql_service = SQLQueryService()

        # Register DataFrame
        self.sql_service.register_dataframe(table_name, df)

        # Update UI
        self.update_table_combo(table_name)
        self.update_schema_browser(table_name)

    def update_table_combo(self, active_table: str):
        """Update table dropdown"""
        self.table_combo.clear()
        if self.sql_service:
            tables = self.sql_service.get_registered_tables()
            self.table_combo.addItems(tables)
            if active_table in tables:
                self.table_combo.setCurrentText(active_table)

    def update_schema_browser(self, table_name: str):
        """Update schema browser with table columns"""
        self.schema_tree.clear()

        if not self.sql_service:
            return

        try:
            # Get table schema
            schema = self.sql_service.get_table_schema(table_name)

            # Create table item with folder icon
            table_item = QTreeWidgetItem([table_name, "TABLE"])
            try:
                from PySide6.QtWidgets import QApplication
                style = QApplication.style()
                # Try to use standard icons (SP_DirIcon might not exist in all styles)
                table_item.setIcon(0, style.standardIcon(style.SP_DirIcon))
            except (AttributeError, TypeError):
                # Fallback to folder icon
                table_item.setIcon(0, QIcon.fromTheme("folder"))
            self.schema_tree.addTopLevelItem(table_item)

            # Add columns
            for col_info in schema:
                col_item = QTreeWidgetItem([
                    col_info['name'],
                    col_info['type']
                ])
                try:
                    from PySide6.QtWidgets import QApplication
                    style = QApplication.style()
                    col_item.setIcon(0, style.standardIcon(style.SP_FileIcon))
                except (AttributeError, TypeError):
                    col_item.setIcon(0, QIcon.fromTheme("text-x-generic"))
                table_item.addChild(col_item)

            table_item.setExpanded(True)

        except Exception as e:
            print(f"Error updating schema browser: {e}")

    def on_table_changed(self, table_name: str):
        """Handle table selection change"""
        if table_name and self.sql_service:
            self.update_schema_browser(table_name)

    def insert_column_name(self, item: QTreeWidgetItem, column: int):
        """Insert column name into query editor"""
        if item.parent():  # It's a column, not a table
            col_name = item.text(0)
            cursor = self.query_editor.textCursor()
            cursor.insertText(col_name)
            self.query_editor.setFocus()

    def insert_sample_query(self, index: int):
        """Insert sample query into editor"""
        if index <= 0 or not self.sql_service:
            return

        query_types = {
            1: "select",
            2: "filter",
            3: "aggregate",
            4: "join",
            5: "order",
            6: "calculate"
        }

        query_type = query_types.get(index, "select")
        sample_query = self.sql_service.get_sample_query(query_type)

        self.query_editor.setText(sample_query)

        # Reset combo
        self.sample_combo.blockSignals(True)
        self.sample_combo.setCurrentIndex(0)
        self.sample_combo.blockSignals(False)

    def execute_query(self):
        """Execute the SQL query"""
        query = self.query_editor.toPlainText().strip()

        if not query:
            QMessageBox.warning(self, "No Query", "Please enter a SQL query")
            return

        if not self.sql_service or not self.sql_service.registered_tables:
            QMessageBox.warning(self, "No Data", "Please load data first")
            return

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.execute_btn.setEnabled(False)

        try:
            # Execute query
            result_df = self.sql_service.execute_query(query)

            # Populate results table
            self.populate_results(result_df)

            # Enable export
            self.export_btn.setEnabled(True)

            # Emit signal
            self.query_executed.emit(result_df)

            # Update info
            self.results_info.setText(
                f"Query returned {len(result_df):,} row(s) and {len(result_df.columns)} column(s)"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Query Error",
                f"Failed to execute query:\n{str(e)}"
            )
            self.results_info.setText("Query failed")

        finally:
            self.progress_bar.setVisible(False)
            self.execute_btn.setEnabled(True)

    def validate_query(self):
        """Validate SQL query syntax"""
        query = self.query_editor.toPlainText().strip()

        if not query:
            QMessageBox.warning(self, "No Query", "Please enter a SQL query")
            return

        if not self.sql_service or not self.sql_service.registered_tables:
            QMessageBox.warning(self, "No Data", "Please load data first")
            return

        try:
            is_valid, error = self.sql_service.validate_query(query)

            if is_valid:
                QMessageBox.information(self, "Validation", "Query syntax is valid!")
            else:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    f"Query validation failed:\n{error}"
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Validation Error",
                f"Validation failed:\n{str(e)}"
            )

    def clear_editor(self):
        """Clear the query editor"""
        self.query_editor.clear()
        self.results_table.setRowCount(0)
        self.results_table.setColumnCount(0)
        self.export_btn.setEnabled(False)
        self.results_info.setText("")

    def populate_results(self, df):
        """Populate results table with query results"""
        # Limit display to first 5000 rows
        display_df = df.head(5000)

        self.results_table.setRowCount(len(display_df))
        self.results_table.setColumnCount(len(df.columns))
        self.results_table.setHorizontalHeaderLabels(df.columns)

        for row_idx in range(len(display_df)):
            for col_idx, col_name in enumerate(df.columns):
                value = display_df[row_idx, col_idx]
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setData(Qt.UserRole, value)
                self.results_table.setItem(row_idx, col_idx, item)

        # Resize columns
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

    def export_results(self):
        """Export query results"""
        if self.results_table.rowCount() == 0:
            QMessageBox.warning(self, "No Results", "No query results to export")
            return

        from ..dialogs.export_dialog import ExportDialog

        dialog = ExportDialog(row_count=self.results_table.rowCount(), parent=self)
        if dialog.exec():
            settings = dialog.get_export_settings()

            try:
                # Re-execute query to get full results
                query = self.query_editor.toPlainText()

                # Export
                file_path = self.sql_service.export_query_result(
                    query,
                    settings['file_path'],
                    settings['format']
                )

                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Query results exported to:\n{file_path}"
                )

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Export Error",
                    f"Failed to export results:\n{str(e)}"
                )
