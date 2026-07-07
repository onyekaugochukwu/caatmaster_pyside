"""
AI Operations Dialog for CAATmaster
AI-powered text analysis: explain, sentiment, entity extraction, classify
"""
import polars as pl
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QWidget, QMessageBox, QLineEdit,
    QRadioButton, QButtonGroup, QTabWidget, QProgressBar, QTextEdit, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, create_primary_button
from ..theme import Colors


class AIExplainDialog(BaseModal):
    """
    Dialog for AI column explanation
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        super().__init__("AI Explain Column", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(600, 500)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'column_selector') and column_name:
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_explanation")

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        if hasattr(self, 'column_selector'):
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_explanation")

    def _setup_ui(self):
        """Setup the AI explain dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Source Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column to Explain:")
        col_layout.addWidget(self.column_selector)

        layout.addWidget(col_group)

        # Options
        options_group = QGroupBox("Explanation Options")
        options_layout = QVBoxLayout(options_group)

        self.explain_type = QButtonGroup()

        explain_types = [
            ("Data Type & Meaning", "dtype"),
            ("Business Context", "business"),
            ("Data Quality Assessment", "quality"),
            ("Pattern Analysis", "pattern"),
            ("Full Analysis", "full"),
        ]

        # QButtonGroup ids are always ints in Qt (addButton(button, id: int)),
        # never strings - map each button to a sequential int id here and
        # translate back to the real string value in get_parameters() below.
        self.explain_type_values = {}
        for i, (label, value) in enumerate(explain_types):
            radio = QRadioButton(label)
            self.explain_type.addButton(radio, i)
            self.explain_type_values[i] = value
            options_layout.addWidget(radio)
            if value == "full":
                radio.setChecked(True)

        layout.addWidget(options_group)

        # Output column
        output_group = QGroupBox("Output")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Name:"), 0, 0)
        self.output_col_edit = QLineEdit("explanation")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Sample Explanation")
        preview_layout = QVBoxLayout(preview_group)

        self.explanation_text = QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setMaximumHeight(150)
        self.explanation_text.setPlaceholderText("Explanation will appear here...")
        preview_layout.addWidget(self.explanation_text)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.explain_btn = create_primary_button("Generate Explanation")
        self.explain_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.explain_btn)

        layout.addLayout(btn_layout)

    def get_parameters(self) -> dict:
        """Get the explain parameters"""
        return {
            "column": self.column_selector.get_column(),
            "output_column": self.output_col_edit.text() or "explanation",
            "explain_type": self.explain_type_values[self.explain_type.checkedId()],
        }

    def validate(self) -> bool:
        """Validate parameters"""
        if not self.column_selector.get_column():
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column.")
            return False
        return True


class AISentimentDialog(BaseModal):
    """
    Dialog for AI sentiment analysis
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        super().__init__("AI Sentiment Analysis", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(600, 500)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'column_selector') and column_name:
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_sentiment")
            self.score_col_edit.setText(f"{column_name}_sentiment_score")

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        if hasattr(self, 'column_selector'):
            self.column_selector.set_current_column(column_name)
            self.output_col_edit.setText(f"{column_name}_sentiment")
            self.score_col_edit.setText(f"{column_name}_sentiment_score")

    def _setup_ui(self):
        """Setup the sentiment analysis dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Source Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Text Column:")
        col_layout.addWidget(self.column_selector)

        layout.addWidget(col_group)

        # Output options
        output_group = QGroupBox("Output Columns")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Sentiment Column:"), 0, 0)
        self.output_col_edit = QLineEdit("sentiment")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        output_layout.addWidget(QLabel("Score Column:"), 1, 0)
        self.score_col_edit = QLineEdit("sentiment_score")
        output_layout.addWidget(self.score_col_edit, 1, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-style: italic;")
        preview_layout.addWidget(self.stats_label)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.analyze_btn = create_primary_button("Analyze")
        self.analyze_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.analyze_btn)

        layout.addLayout(btn_layout)

    def get_parameters(self) -> dict:
        """Get the sentiment parameters"""
        return {
            "column": self.column_selector.get_column(),
            "output_column": self.output_col_edit.text() or "sentiment",
            "score_column": self.score_col_edit.text() or "sentiment_score",
        }

    def validate(self) -> bool:
        """Validate parameters"""
        if not self.column_selector.get_column():
            QMessageBox.warning(self, "Validation Error",
                              "Please select a text column.")
            return False
        return True

    def preview(self):
        """Generate preview of sentiment analysis"""
        try:
            params = self.get_parameters()
            column = params["column"]

            if not column:
                return

            # Simple sentiment analysis based on keywords
            col_data = self.original_df[column].to_list()

            sentiments = []
            scores = []
            positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'best', 'happy', 'positive', 'success', 'profit']
            negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'sad', 'negative', 'loss', 'error', 'fail']

            for val in col_data[:10]:
                text = str(val).lower()
                pos_count = sum(1 for w in positive_words if w in text)
                neg_count = sum(1 for w in negative_words if w in text)

                if pos_count > neg_count:
                    sentiments.append("Positive")
                    score = min(1.0, 0.5 + (pos_count - neg_count) * 0.1)
                elif neg_count > pos_count:
                    sentiments.append("Negative")
                    score = max(-1.0, -0.5 - (neg_count - pos_count) * 0.1)
                else:
                    sentiments.append("Neutral")
                    score = 0.0
                scores.append(round(score, 3))

            preview_df = self.original_df[:10].clone()
            preview_df = preview_df.with_columns(
                pl.Series(name=params["output_column"], values=sentiments),
                pl.Series(name=params["score_column"], values=scores)
            )
            self.preview_table.load_dataframe(preview_df)

            self.stats_label.setText("Sample results shown")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")


class AIEntityExtractionDialog(BaseModal):
    """
    Dialog for AI entity extraction (emails, phones, dates, etc.)
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None, selected_column: str = None):
        self.original_df = dataframe
        super().__init__("AI Extract Entities", dataframe, parent, selected_column=selected_column)
        self.setMinimumSize(600, 550)
        self.set_selected_column(selected_column) if selected_column else None

    def set_selected_column(self, column_name: str):
        """Auto-select the column when opened from context menu"""
        self.selected_column = column_name
        if hasattr(self, 'column_selector') and column_name:
            self.column_selector.set_current_column(column_name)

    def _on_column_selected(self, column_name: str):
        """Called when column is selected from context menu"""
        if hasattr(self, 'column_selector'):
            self.column_selector.set_current_column(column_name)

    def _setup_ui(self):
        """Setup the entity extraction dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Source Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Text Column:")
        col_layout.addWidget(self.column_selector)

        layout.addWidget(col_group)

        # Entity types to extract
        entities_group = QGroupBox("Entity Types to Extract")
        entities_layout = QGridLayout(entities_group)

        self.entity_checkboxes = {}

        entity_types = [
            ("Email Addresses", "email", True),
            ("Phone Numbers", "phone", True),
            ("Dates", "date", False),
            ("Times", "time", False),
            ("Currency/Money", "money", False),
            ("URLs", "url", False),
            ("Credit Card Numbers", "credit_card", False),
            ("Social Security Numbers", "ssn", False),
            ("IP Addresses", "ip_address", False),
            ("Postal Codes", "postal_code", False),
        ]

        row, col = 0, 0
        for label, value, checked in entity_types:
            checkbox = QCheckBox(label)
            checkbox.setChecked(checked)
            entities_layout.addWidget(checkbox, row, col)
            self.entity_checkboxes[value] = checkbox
            col += 1
            if col > 1:
                col = 0
                row += 1

        layout.addWidget(entities_group)

        # Output column
        output_group = QGroupBox("Output")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("New Column Name:"), 0, 0)
        self.output_col_edit = QLineEdit("entities")
        output_layout.addWidget(self.output_col_edit, 0, 1)

        self.combine_check = QCheckBox("Combine all entities in one column")
        self.combine_check.setChecked(True)
        output_layout.addWidget(self.combine_check, 1, 0, 1, 2)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-style: italic;")
        preview_layout.addWidget(self.stats_label)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.clicked.connect(self.preview)
        btn_layout.addWidget(self.preview_btn)

        self.extract_btn = create_primary_button("Extract")
        self.extract_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.extract_btn)

        layout.addLayout(btn_layout)

    def get_parameters(self) -> dict:
        """Get the entity extraction parameters"""
        selected_entities = [k for k, v in self.entity_checkboxes.items() if v.isChecked()]

        return {
            "column": self.column_selector.get_column(),
            "output_column": self.output_col_edit.text() or "entities",
            "entity_types": selected_entities,
            "combine": self.combine_check.isChecked(),
        }

    def validate(self) -> bool:
        """Validate parameters"""
        if not self.column_selector.get_column():
            QMessageBox.warning(self, "Validation Error",
                              "Please select a text column.")
            return False
        return True

    def preview(self):
        """Generate preview of entity extraction"""
        try:
            params = self.get_parameters()
            column = params["column"]
            entities = params["entity_types"]

            if not column:
                return

            import re

            col_data = self.original_df[column].to_list()

            # Regex patterns for entities
            patterns = {
                "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                "phone": r'(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}',
                "date": r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}',
                "time": r'\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?',
                "money": r'\$[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP)',
                "url": r'https?://[^\s<>"{}|\\^`\[\]]+',
                "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
                "ssn": r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
                "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
                "postal_code": r'\b\d{5}(?:-\d{4})?\b',
            }

            results = []
            for val in col_data[:10]:
                text = str(val)
                found = []
                for entity in entities:
                    if entity in patterns:
                        matches = re.findall(patterns[entity], text, re.IGNORECASE)
                        for m in matches:
                            found.append(str(m))
                results.append(", ".join(found) if found else "")

            preview_df = self.original_df[:10].clone()
            preview_df = preview_df.with_columns(
                pl.Series(name=params["output_column"], values=results)
            )
            self.preview_table.load_dataframe(preview_df)

            count = sum(1 for r in results if r)
            self.stats_label.setText(f"Found entities in {count} of 10 rows")

        except Exception as e:
            QMessageBox.warning(self, "Preview Error",
                              f"Could not generate preview:\n{str(e)}")
