"""
AI Chat Dialog for CAATmaster
AI-powered chat interface with file upload support for PDF and CSV files.
"""
import polars as pl
import tempfile
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QWidget, QMessageBox, QLineEdit,
    QRadioButton, QButtonGroup, QTabWidget, QProgressBar, QTextEdit, QCheckBox,
    QFileDialog, QListWidget, QListWidgetItem, QFrame, QSplitter
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QIcon, QTextCursor

from ..components.common_modals import BaseModal


class AIChatDialog(QDialog):
    """
    AI Chat interface with file upload support.
    Users can:
    - Chat with AI about their data
    - Upload PDF files for analysis
    - Upload CSV/Excel files for data extraction
    - Request financial statement extraction
    """

    def __init__(self, dataframe: pl.DataFrame = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Chat Assistant")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        self.original_df = dataframe
        self.uploaded_files = []  # List of (filename, file_type, data)
        self.chat_history = []  # List of (role, message)

        self._setup_ui()
        self._setup_ai()

    def _setup_ui(self):
        """Setup the chat UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Main splitter - chat area and sidebar
        splitter = QSplitter(Qt.Horizontal)

        # Left side - Chat area
        chat_container = QWidget()
        chat_layout = QVBoxLayout(chat_container)
        chat_layout.setContentsMargins(0, 0, 0, 0)

        # Chat display
        chat_group = QGroupBox("Chat")
        chat_layout_inner = QVBoxLayout(chat_group)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        chat_layout_inner.addWidget(self.chat_display)

        # Message input
        input_layout = QHBoxLayout()

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message or request...")
        self.message_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }
        """)
        self.message_input.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.message_input, 1)

        # Send button
        self.send_btn = QPushButton("Send")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)

        chat_layout_inner.addLayout(input_layout)
        chat_layout.addWidget(chat_group)

        # Right side - File uploads and context
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar.setFixedWidth(280)

        # Data context section
        context_group = QGroupBox("Current Data")
        context_layout = QVBoxLayout(context_group)

        if self.original_df is not None:
            info_text = f"Rows: {self.original_df.height}\nCols: {len(self.original_df.columns)}"
            self.context_label = QLabel(info_text)
            self.context_label.setStyleSheet("color: #666; font-size: 12px;")
            context_layout.addWidget(self.context_label)

            # Column list
            self.col_list = QTextEdit()
            self.col_list.setMaximumHeight(100)
            self.col_list.setReadOnly(True)
            cols_str = ", ".join(list(self.original_df.columns)[:10])
            if len(self.original_df.columns) > 10:
                cols_str += "..."
            self.col_list.setText(f"Columns: {cols_str}")
            self.col_list.setStyleSheet("font-size: 11px;")
            context_layout.addWidget(self.col_list)
        else:
            self.context_label = QLabel("No data loaded")
            self.context_label.setStyleSheet("color: #999;")
            context_layout.addWidget(self.context_label)

        sidebar_layout.addWidget(context_group)

        # File uploads section
        upload_group = QGroupBox("Upload Files")
        upload_layout = QVBoxLayout(upload_group)

        # Upload buttons
        btn_layout = QHBoxLayout()

        self.pdf_btn = QPushButton("PDF")
        self.pdf_btn.setToolTip("Upload PDF file for analysis")
        self.pdf_btn.clicked.connect(lambda: self._upload_file("pdf"))
        btn_layout.addWidget(self.pdf_btn)

        self.csv_btn = QPushButton("CSV/Excel")
        self.csv_btn.setToolTip("Upload CSV or Excel file")
        self.csv_btn.clicked.connect(lambda: self._upload_file("data"))
        btn_layout.addWidget(self.csv_btn)

        upload_layout.addLayout(btn_layout)

        # File list
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        """)
        upload_layout.addWidget(self.file_list)

        # Clear files button
        self.clear_files_btn = QPushButton("Clear Files")
        self.clear_files_btn.setEnabled(False)
        self.clear_files_btn.clicked.connect(self._clear_files)
        upload_layout.addWidget(self.clear_files_btn)

        sidebar_layout.addWidget(upload_group)

        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QVBoxLayout(actions_group)

        actions = [
            ("Extract Financial Data", "extract_financial"),
            ("Summarize Document", "summarize"),
            ("Analyze Trends", "analyze_trends"),
            ("Generate Report", "generate_report"),
        ]

        for label, action in actions:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, a=action: self._quick_action(a))
            actions_layout.addWidget(btn)

        sidebar_layout.addWidget(actions_group)

        # Add widgets to splitter
        splitter.addWidget(chat_container)
        splitter.addWidget(sidebar)
        splitter.setSizes([600, 280])

        layout.addWidget(splitter)

        # Initial welcome message
        self._add_system_message("Hello! I'm your AI assistant. You can:\n"
                                 "- Ask questions about your data\n"
                                 "- Upload PDF files for analysis\n"
                                 "- Upload CSV/Excel files for data extraction\n"
                                 "- Use quick actions for common tasks")

    def _setup_ai(self):
        """Setup AI provider"""
        self.provider = None
        self.model = None

        try:
            from services.ai_service import AIManager, load_stored_providers
            manager = AIManager()
            load_stored_providers(manager)
            self.provider = manager.get_provider()
            if self.provider:
                self.model = self.provider.model
        except Exception as e:
            print(f"AI provider not available: {e}")

    def _add_message(self, role: str, message: str):
        """Add a message to the chat display"""
        self.chat_history.append((role, message))

        # Format based on role
        if role == "user":
            color = "#0078d4"
            prefix = "You: "
        elif role == "assistant":
            color = "#28a745"
            prefix = "AI: "
        else:
            color = "#666"
            prefix = ""

        if prefix:
            html = f'<p style="color: {color}; font-weight: bold; margin-bottom: 5px;">{prefix}</p>'
            html += f'<p style="margin-left: 20px; margin-top: 0;">{message}</p>'
        else:
            html = f'<p style="color: {color}; margin: 10px 0;">{message}</p>'

        self.chat_display.append(html)
        self.chat_display.append("<hr style='margin: 10px 0; border: none; border-top: 1px solid #eee;'>")

        # Scroll to bottom
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def _add_system_message(self, message: str):
        """Add a system/informational message"""
        html = f'<p style="color: #666; font-style: italic; margin: 10px 0;">{message}</p>'
        self.chat_display.append(html)
        self.chat_display.append("<hr style='margin: 10px 0; border: none; border-top: 1px solid #eee;'>")

    def _upload_file(self, file_type: str):
        """Upload a file for analysis"""
        if file_type == "pdf":
            filters = "PDF Files (*.pdf)"
        else:
            filters = "Data Files (*.csv *.xlsx *.xls)"

        filename, _ = QFileDialog.getOpenFileName(
            self, "Upload File", "", filters
        )

        if not filename:
            return

        try:
            # Read file based on type
            if file_type == "pdf":
                data = self._read_pdf(filename)
                file_ext = "pdf"
            else:
                data = self._read_data_file(filename)
                file_ext = Path(filename).suffix.lower()

            # Add to list
            item = QListWidgetItem(f"📄 {Path(filename).name}")
            self.file_list.addItem(item)
            self.uploaded_files.append({
                "name": Path(filename).name,
                "type": file_ext,
                "path": filename,
                "data": data
            })

            self.clear_files_btn.setEnabled(True)
            self._add_system_message(f"Uploaded: {Path(filename).name}")

        except Exception as e:
            QMessageBox.warning(self, "Upload Error", f"Could not read file:\n{str(e)}")

    def _read_pdf(self, filepath: str) -> str:
        """Read PDF file and extract text"""
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            text = ""
            for page in reader.pages[:50]:  # Limit to 50 pages
                text += page.extract_text() + "\n"
            return text[:100000]  # Limit text length
        except ImportError:
            # Fallback: return placeholder if pypdf not installed
            return f"[PDF file: {filepath}]\nInstall pypdf to enable PDF text extraction."

    def _read_data_file(self, filepath: str) -> pl.DataFrame:
        """Read CSV/Excel file and return as Polars DataFrame"""
        path = Path(filepath)
        if path.suffix.lower() in ['.csv']:
            return pl.read_csv(filepath)
        elif path.suffix.lower() in ['.xlsx', '.xls']:
            return pl.read_excel(filepath)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

    def _clear_files(self):
        """Clear uploaded files"""
        self.uploaded_files = []
        self.file_list.clear()
        self.clear_files_btn.setEnabled(False)
        self._add_system_message("Files cleared")

    def _quick_action(self, action: str):
        """Execute a quick action"""
        action_prompts = {
            "extract_financial": "Extract all financial data from the uploaded files. List revenues, expenses, assets, liabilities, and any financial metrics you find.",
            "summarize": "Provide a summary of the uploaded documents.",
            "analyze_trends": "Analyze the data for any trends, patterns, or anomalies.",
            "generate_report": "Generate a brief report based on the uploaded data."
        }

        prompt = action_prompts.get(action, "")
        self.message_input.setText(prompt)
        self._send_message()

    def _send_message(self):
        """Send message to AI"""
        message = self.message_input.text().strip()
        if not message:
            return

        # Add user message
        self._add_message("user", message)
        self.message_input.clear()

        # Build context for AI
        context = self._build_context()

        # Generate response
        self._get_ai_response(message, context)

    def _build_context(self) -> str:
        """Build context string for AI"""
        context_parts = []

        # Add data context
        if self.original_df is not None:
            context_parts.append(f"Current dataset: {self.original_df.height} rows, {len(self.original_df.columns)} columns")
            context_parts.append(f"Columns: {list(self.original_df.columns)}")

        # Add uploaded files info
        for f in self.uploaded_files:
            context_parts.append(f"Uploaded file: {f['name']} ({f['type']})")
            if isinstance(f.get('data'), str):
                # PDF text
                text_preview = f['data'][:500] + "..." if len(f['data']) > 500 else f['data']
                context_parts.append(f"Content preview: {text_preview}")
            elif isinstance(f.get('data'), pl.DataFrame):
                # DataFrame info
                df = f['data']
                context_parts.append(f"Data rows: {df.height}, Columns: {list(df.columns)}")

        return "\n\n".join(context_parts)

    def _get_ai_response(self, user_message: str, context: str):
        """Get AI response"""
        if not self.provider:
            self._add_message("assistant", "AI provider not configured. Please add an AI provider in Settings > AI Settings.")
            return

        # Build prompt
        system_prompt = """You are a helpful AI assistant for CAATmaster, an audit analytics platform.
You help users analyze data, understand documents, and extract insights.
Be concise, helpful, and focus on actionable information."""

        full_prompt = f"""
Context:
{context}

User Question:
{user_message}

Provide a helpful response based on the context above. If analyzing data, be specific about the findings.
"""

        # Disable send button during processing
        self.send_btn.setEnabled(False)
        self.send_btn.setText("...")

        try:
            import asyncio
            from services.ai_service import AIManager, load_stored_providers

            async def get_response():
                manager = AIManager()
                load_stored_providers(manager)
                provider = manager.get_provider()

                if not provider:
                    return "No AI provider configured."

                if hasattr(provider, 'initialize'):
                    provider.initialize()

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt}
                ]

                response = await provider.complete(messages, temperature=0.7)
                return response.content

            # Run async
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(get_response())
            loop.close()

            self._add_message("assistant", response)

        except Exception as e:
            self._add_message("assistant", f"Error: {str(e)}")
        finally:
            self.send_btn.setEnabled(True)
            self.send_btn.setText("Send")


def create_ai_chat_dialog(dataframe: pl.DataFrame = None, parent=None) -> AIChatDialog:
    """Factory function to create AI chat dialog"""
    return AIChatDialog(dataframe, parent)
