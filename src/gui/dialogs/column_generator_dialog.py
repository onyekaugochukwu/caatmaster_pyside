"""AI Column Generator Dialog - Create derived columns using natural language"""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QGroupBox, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QFrame,
    QSizePolicy, QGridLayout, QSpacerItem
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QFont

from gui.theme import Colors


class ColumnGeneratorDialog(QDialog):
    """Dialog for generating new columns using AI"""

    column_applied = Signal(dict)  # Emitted when column is applied: {column_name, code, instruction}
    # Thread-safe signals for UI updates
    _codeReady = Signal(str)  # Code generated
    _explanationReady = Signal(str)  # Explanation ready
    _examplesReady = Signal(list)  # Example values ready
    _columnNameReady = Signal(str)  # Column name ready
    _statusReady = Signal(str)  # Status message
    _generationComplete = Signal()  # Generation complete
    _generationFailed = Signal(str)  # Generation failed with error

    def __init__(self, dataframes: dict, column_generator, parent=None, selected_key: str = None):
        """Initialize dialog with multiple datasets

        Args:
            dataframes: Dictionary of {dataset_name: polars DataFrame}
            column_generator: AI column generator instance
            parent: Parent widget
            selected_key: Key of initially selected dataset
        """
        super().__init__(parent)
        self.dataframes = dataframes
        self.df = dataframes.get(selected_key, list(dataframes.values())[0]) if selected_key else list(dataframes.values())[0]
        self.generator = column_generator
        self.suggestion = None
        # Thread pool for async operations (no parent to avoid thread issues)
        from PySide6.QtCore import QThreadPool
        self.thread_pool = QThreadPool()
        self.setup_ui()

        # Connect thread-safe signals for UI updates
        self._codeReady.connect(self._on_code_ready, Qt.QueuedConnection)
        self._explanationReady.connect(self._on_explanation_ready, Qt.QueuedConnection)
        self._examplesReady.connect(self._on_examples_ready, Qt.QueuedConnection)
        self._columnNameReady.connect(self._on_column_name_ready, Qt.QueuedConnection)
        self._statusReady.connect(self._on_status_ready, Qt.QueuedConnection)
        self._generationComplete.connect(self._on_generation_complete, Qt.QueuedConnection)
        self._generationFailed.connect(self._on_generation_failed, Qt.QueuedConnection)

    def closeEvent(self, event):
        """Handle dialog close - wait for threads to finish"""
        self.thread_pool.waitForDone(3000)
        event.accept()

    # Thread-safe signal handlers (called from main thread)
    def _on_code_ready(self, code: str):
        """Handle code ready signal"""
        self.code_edit.setText(code)

    def _on_explanation_ready(self, explanation: str):
        """Handle explanation ready signal"""
        self.explanation_label.setText(f"Explanation: {explanation}")

    def _on_examples_ready(self, values: list):
        """Handle examples ready signal"""
        self.examples_list.clear()
        for val in values[:10]:
            item = QListWidgetItem(str(val))
            self.examples_list.addItem(item)

    def _on_column_name_ready(self, name: str):
        """Handle column name ready signal"""
        self.name_edit.setText(name)

    def _on_status_ready(self, status: str):
        """Handle status ready signal"""
        self.status_label.setText(status)

    def _on_generation_complete(self):
        """Handle generation complete signal"""
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

    def _on_generation_failed(self, error: str):
        """Handle generation failed signal"""
        self.status_label.setText(f"Error: {error}")
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Generation Error", error)

    def _on_dataset_changed(self, index: int):
        """Handle dataset selection change"""
        key = self.dataset_combo.itemData(index)
        if key and key in self.dataframes:
            self.df = self.dataframes[key]
            self._current_dataset_name = key
            # Update dataset info label
            self.dataset_info_label.setText(f"Rows: {len(self.df):,} | Columns: {len(self.df.columns)}")
            # Clear previous results
            self.code_edit.clear()
            self.explanation_label.setText("Explanation:")
            self.examples_list.clear()
            self.suggestion = None

    def setup_ui(self):
        self.setWindowTitle("AI Column Generator")
        self.setMinimumSize(700, 550)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {Colors.BG_SECONDARY};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title section
        title_layout = QHBoxLayout()
        title_icon = QLabel("🤖")
        title_icon.setStyleSheet("font-size: 24px;")
        title_layout.addWidget(title_icon)

        title = QLabel("Generate Column with AI")
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 700;
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        title_layout.addWidget(title)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Track current dataset name
        self._current_dataset_name = None

        # Dataset selector
        dataset_group = QGroupBox("Dataset")
        dataset_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)
        dataset_layout = QHBoxLayout(dataset_group)
        dataset_layout.setContentsMargins(16, 20, 16, 16)

        dataset_layout.addWidget(QLabel("Dataset:"))

        # Store mapping of keys to dataframe objects for lookup
        self._key_for_dataframe = {}
        for key, df_obj in self.dataframes.items():
            self._key_for_dataframe[id(df_obj)] = key

        self.dataset_combo = QComboBox()
        self.dataset_combo.setStyleSheet(f"""
            QComboBox {{
                padding: 8px 12px;
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                font-size: 13px;
                min-width: 200px;
            }}
        """)
        for key in self.dataframes.keys():
            self.dataset_combo.addItem(key, key)
        # Find and set current dataset
        current_key = self._key_for_dataframe.get(id(self.df))
        if current_key:
            self.dataset_combo.setCurrentText(current_key)
            self._current_dataset_name = current_key
        self.dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
        dataset_layout.addWidget(self.dataset_combo)

        # Add dataset info label
        self.dataset_info_label = QLabel(f"Rows: {len(self.df):,} | Columns: {len(self.df.columns)}")
        self.dataset_info_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {Colors.TEXT_SECONDARY};
                padding: 4px 8px;
                background-color: {Colors.BG_SECONDARY};
                border-radius: 4px;
            }}
        """)
        dataset_layout.addWidget(self.dataset_info_label)
        dataset_layout.addStretch()
        layout.addWidget(dataset_group)

        # Main content area - split into left and right panels
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left panel - Input and options
        left_panel = QVBoxLayout()
        left_panel.setSpacing(12)

        # Instruction input
        instruction_group = QGroupBox("What should the column contain?")
        instruction_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)

        instruction_layout = QVBoxLayout(instruction_group)

        self.instruction_edit = QTextEdit()
        self.instruction_edit.setPlaceholderText(
            "Describe the column you want to create...\n\n"
            "Examples:\n"
            "• 'Extract the email domain from the email address'\n"
            "• 'Calculate the age from the birth date'\n"
            "• 'Categorize transaction amounts as High, Medium, or Low'\n"
            "• 'Extract the first name from the full name'"
        )
        self.instruction_edit.setMaximumHeight(120)
        self.instruction_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                background-color: {Colors.BG_PRIMARY};
            }}
            QTextEdit:focus {{
                border-color: {Colors.ACCENT};
            }}
        """)
        instruction_layout.addWidget(self.instruction_edit)

        # Quick suggestions
        suggestions_label = QLabel("Quick Suggestions:")
        suggestions_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {Colors.TEXT_SECONDARY};
                font-weight: 600;
            }}
        """)
        instruction_layout.addWidget(suggestions_label)

        suggestions_layout = QHBoxLayout()
        suggestions_layout.setSpacing(8)

        suggestion_buttons = [
            ("📧 Extract Email", "Extract email domain from email column"),
            ("📅 Calculate Age", "Calculate age from birth date column"),
            ("💰 Categorize", "Categorize amounts as High/Medium/Low"),
            ("📝 Extract Name", "Extract first name from full name"),
        ]

        for icon_text, instruction in suggestion_buttons:
            btn = QPushButton(icon_text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 6px 10px;
                    background-color: {Colors.ACCENT_SOFT};
                    border: 1px solid {Colors.ACCENT};
                    border-radius: 4px;
                    font-size: 11px;
                    color: {Colors.ACCENT};
                }}
                QPushButton:hover {{
                    background-color: {Colors.ACCENT_SOFT};
                }}
            """)
            btn.clicked.connect(lambda checked, inst=instruction: self.instruction_edit.setText(inst))
            suggestions_layout.addWidget(btn)

        instruction_layout.addLayout(suggestions_layout)
        left_panel.addWidget(instruction_group)

        # Column name input
        name_layout = QHBoxLayout()
        name_label = QLabel("New Column Name:")
        name_label.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
            }}
        """)
        name_layout.addWidget(name_label)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., email_domain, age, risk_level")
        self.name_edit.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                font-size: 13px;
                background-color: {Colors.BG_PRIMARY};
            }}
            QLineEdit:focus {{
                border-color: {Colors.ACCENT};
            }}
        """)
        name_layout.addWidget(self.name_edit)
        left_panel.addLayout(name_layout)

        # Generate button
        self.generate_btn = QPushButton("✨ Generate Column")
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 12px 20px;
                background-color: {Colors.ACCENT};
                color: {Colors.TEXT_ON_ACCENT};
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {Colors.TEXT_TERTIARY};
            }}
        """)
        self.generate_btn.clicked.connect(self.generate_column)
        left_panel.addWidget(self.generate_btn)

        # Progress indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: transparent;
            }}
            QProgressBar::chunk {{
                background-color: {Colors.ACCENT};
            }}
        """)
        self.progress_bar.setVisible(False)
        left_panel.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel()
        self.status_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {Colors.TEXT_SECONDARY};
                padding: 8px;
                border-radius: 4px;
                background-color: {Colors.BG_SECONDARY};
            }}
        """)
        self.status_label.setVisible(False)
        left_panel.addWidget(self.status_label)

        left_panel.addStretch()
        content_layout.addLayout(left_panel, 1)

        # Right panel - Preview and code
        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)

        # Code preview
        code_group = QGroupBox("Generated Code")
        code_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)

        code_layout = QVBoxLayout(code_group)

        self.code_edit = QTextEdit()
        self.code_edit.setPlaceholderText("AI-generated code will appear here...")
        self.code_edit.setReadOnly(True)
        self.code_edit.setStyleSheet(f"""
            QTextEdit {{
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
                background-color: #201f1e;
                color: #e1dfdd;
            }}
        """)
        code_layout.addWidget(self.code_edit)

        # Explanation
        self.explanation_label = QLabel()
        self.explanation_label.setWordWrap(True)
        self.explanation_label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {Colors.TEXT_SECONDARY};
                padding: 8px;
                background-color: {Colors.BG_SECONDARY};
                border-radius: 4px;
            }}
        """)
        code_layout.addWidget(self.explanation_label)

        right_panel.addWidget(code_group)

        # Example values preview
        examples_group = QGroupBox("Example Values")
        examples_group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)

        examples_layout = QVBoxLayout(examples_group)

        self.examples_list = QListWidget()
        self.examples_list.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                background-color: {Colors.BG_PRIMARY};
                padding: 8px;
            }}
        """)
        examples_layout.addWidget(self.examples_list)

        right_panel.addWidget(examples_group)

        # Action buttons
        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("✓ Apply Column")
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 10px 20px;
                background-color: {Colors.SUCCESS};
                color: {Colors.TEXT_ON_ACCENT};
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {Colors.SUCCESS_HOVER};
            }}
            QPushButton:disabled {{
                background-color: {Colors.TEXT_TERTIARY};
            }}
        """)
        self.apply_btn.clicked.connect(self.apply_column)
        button_layout.addWidget(self.apply_btn)

        self.preview_btn = QPushButton("👁 Preview")
        self.preview_btn.setEnabled(False)
        self.preview_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 10px 20px;
                background-color: {Colors.BG_SECONDARY};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                color: {Colors.TEXT_SECONDARY};
            }}
            QPushButton:hover {{
                background-color: {Colors.BORDER};
            }}
            QPushButton:disabled {{
                background-color: {Colors.BG_SECONDARY};
                color: {Colors.TEXT_TERTIARY};
            }}
        """)
        self.preview_btn.clicked.connect(self.preview_column)
        button_layout.addWidget(self.preview_btn)

        button_layout.addStretch()

        close_btn = QPushButton("✕ Close")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                padding: 10px 20px;
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER_STRONG};
                border-radius: 6px;
                font-size: 13px;
                color: {Colors.TEXT_SECONDARY};
            }}
            QPushButton:hover {{
                background-color: {Colors.BG_SECONDARY};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        right_panel.addLayout(button_layout)

        content_layout.addLayout(right_panel, 1)
        layout.addLayout(content_layout)

    def generate_column(self):
        """Generate the column code using AI"""
        instruction = self.instruction_edit.toPlainText().strip()
        if not instruction:
            QMessageBox.warning(self, "No Instruction", "Please enter an instruction for the column.")
            return

        column_name = self.name_edit.text().strip() or None

        # Check if AI is configured
        if not self.generator.ai.providers:
            QMessageBox.warning(
                self,
                "AI Not Configured",
                "Please configure an AI provider in Settings > AI Settings first."
            )
            return

        # Show progress
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.status_label.setVisible(True)
        self.status_label.setText("Generating column code...")

        async def do_generate():
            try:
                suggestion = await self.generator.generate_column(
                    instruction=instruction,
                    df=self.df,
                    column_name=column_name
                )
                self.suggestion = suggestion

                # Emit signals for thread-safe UI updates
                self._codeReady.emit(suggestion.code)
                self._explanationReady.emit(suggestion.explanation)
                self._examplesReady.emit(suggestion.example_values)
                self._statusReady.emit("Column code generated successfully!")

                # Update column name if it was auto-generated (emit signal)
                if not column_name and suggestion.column_name:
                    self._columnNameReady.emit(suggestion.column_name)

                # Enable buttons via signal
                self.apply_btn.setEnabled(True)
                self.preview_btn.setEnabled(True)

            except Exception as e:
                self._generationFailed.emit(str(e))
                return

            self._generationComplete.emit()

        def run_async():
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(do_generate())
            finally:
                loop.close()

        self.thread_pool.start(run_async)

    def preview_column(self):
        """Preview the new column on sample data"""
        if not self.suggestion:
            return

        try:
            # Apply to sample data (first 100 rows)
            sample_df = self.df.head(100)
            result_df = self.generator.apply_column(sample_df, self.suggestion.code)

            # Use user's column name if provided, otherwise AI's name
            user_name = self.name_edit.text().strip()
            ai_name = self.suggestion.column_name

            # Find which name exists in the result
            if user_name and user_name in result_df.columns:
                new_col = user_name
            elif ai_name in result_df.columns:
                new_col = ai_name
            else:
                QMessageBox.warning(self, "Preview Error", "Could not find generated column in output.")
                return

            preview_values = result_df[new_col].to_list()[:10]
            preview_text = f"First 10 values of '{new_col}':\n\n"
            for i, v in enumerate(preview_values):
                preview_text += f"{i+1}. {v}\n"

            QMessageBox.information(self, "Column Preview", preview_text)

        except Exception as e:
            QMessageBox.critical(self, "Preview Error", str(e))

    def apply_column(self):
        """Apply the generated column to the dataframe"""
        if not self.suggestion:
            return

        # User's preferred column name
        user_name = self.name_edit.text().strip()
        # AI suggested column name (what the code actually creates)
        ai_name = self.suggestion.column_name

        try:
            # Apply to full dataframe
            result_df = self.generator.apply_column(self.df, self.suggestion.code)

            # Check if AI's column name exists in output (most likely)
            if ai_name in result_df.columns:
                result_col = ai_name
            elif user_name and user_name in result_df.columns:
                # User provided a different name and it exists
                result_col = user_name
            else:
                QMessageBox.warning(self, "Apply Error",
                    f"Could not find generated column in output.\n"
                    f"Expected: '{ai_name}' or '{user_name}'")
                return

            # Rename column if user provided different name
            if user_name and user_name != ai_name and ai_name in result_df.columns:
                result_df = result_df.rename({ai_name: user_name})
                result_col = user_name

            # Update the original dataframe reference
            self.df = result_df

            # Get the instruction (user's original request)
            instruction = self.instruction_edit.toPlainText().strip()

            # Emit signal with all necessary info for pipeline step
            self.column_applied.emit({
                "column_name": result_col,
                "code": self.suggestion.code,
                "instruction": instruction,
                "original_ai_name": ai_name
            })

            QMessageBox.information(
                self,
                "Column Applied",
                f"Column '{result_col}' has been added to your dataset.\n\n"
                f"Rows: {len(self.df):,}\n"
                f"Columns: {len(self.df.columns)}"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Apply Error", str(e))

    def get_dataframe(self) -> pl.DataFrame:
        """Get the modified dataframe"""
        return self.df
