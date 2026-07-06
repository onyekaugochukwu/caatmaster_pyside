"""AI Panel Component - Interactive AI assistant for CaatMaster"""
from typing import Dict, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFrame, QScrollArea, QGraphicsDropShadowEffect,
    QListWidget, QListWidgetItem, QComboBox, QSizePolicy,
    QProgressBar, QToolButton, QSpacerItem
)
from PySide6.QtCore import Qt, QSize, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QColor, QIcon, QTextCursor, QKeyEvent, QAction, QPixmap


class _AutoHeightTextEdit(QTextEdit):
    """A read-only QTextEdit that always sizes its height to fit its
    content at whatever width it actually ends up with. The previous
    approach measured height against a hardcoded assumed width (500px)
    that was wider than the panel itself (440px) could ever give it -
    text wrapped to more lines than were measured for, so the fixed
    height came out too short and clipped the last line(s) of longer
    messages. Recomputing on resizeEvent keeps it correct regardless of
    the panel's actual width, including if the window is resized."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFrameStyle(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.document().setDocumentMargin(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_height()

    def _update_height(self):
        self.document().setTextWidth(self.viewport().width())
        doc_height = self.document().size().height()
        self.setFixedHeight(int(doc_height) + 8)


class AIMessageWidget(QFrame):
    """Widget for displaying a single AI message"""

    def __init__(self, message: str, is_user: bool = False, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.setup_ui(message)

    def setup_ui(self, message: str):
        # Color scheme based on sender
        if self.is_user:
            bg_color = "#3b82f6"  # Blue for user
            text_color = "white"
            bubble_style = """
                QFrame {{
                    background-color: {0};
                    border-radius: 14px;
                    padding: 12px 14px;
                }}
            """.format(bg_color)
        else:
            bg_color = "#f3f4f6"  # Light gray for AI
            text_color = "#1f2937"
            bubble_style = """
                QFrame {{
                    background-color: {0};
                    border-radius: 14px;
                    border: 1px solid #e5e7eb;
                    padding: 12px 14px;
                }}
            """.format(bg_color)

        self.setStyleSheet(bubble_style)
        # Comfortably inside the AI panel's fixed 440px width, leaving room
        # for the scroll area's margins/scrollbar and (for AI messages)
        # the avatar icon column - a bubble that assumes it can be wider
        # than the panel ever gives it is exactly what caused the clipped-
        # text bug above.
        self.setMaximumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Avatar/Icon
        icon_label = QLabel("👤" if self.is_user else "🤖")
        icon_label.setStyleSheet("font-size: 15px;")
        icon_label.setFixedSize(22, 22)
        icon_label.setAlignment(Qt.AlignCenter)

        # Message text — AI responses are markdown (headers, bold, bullet
        # lists — see e.g. _on_ai_analyze_dataset's "## Dataset Analysis"
        # response), which a plain QLabel just showed as literal ##/**
        # characters. QTextEdit.setMarkdown() is a native Qt feature (5.14+,
        # no external dependency, not related to the web-only CodeMirror)
        # that renders it properly. User messages stay plain text so a
        # literally-typed "**word**" doesn't get reinterpreted as bold.
        message_label = _AutoHeightTextEdit()
        # theme.py's global stylesheet has a blanket "QTextEdit { color: ...;
        # background-color: ...; border: ... }" rule that otherwise wins
        # over a same-specificity bare-type selector here (the same class
        # of bug fixed earlier for tooltips) - on a user bubble this made
        # the text render in the global dark color against the blue
        # background instead of white, effectively invisible. Scoping to
        # this instance's objectName makes the override unambiguous, and
        # every property the global rule sets is repeated here so nothing
        # leaks through from it.
        message_label.setObjectName("chatMessageText")
        message_label.setStyleSheet(f"""
            QTextEdit#chatMessageText {{
                background-color: transparent;
                color: {text_color};
                font-size: 13.5px;
                line-height: 1.4;
                border: none;
                padding: 0px;
            }}
        """)
        if self.is_user:
            message_label.setPlainText(message)
        else:
            message_label.setMarkdown(message)

        # Timestamp
        from datetime import datetime
        time_label = QLabel(datetime.now().strftime("%H:%M"))
        time_label.setStyleSheet("""
            QLabel {
                color: #9ca3af;
                font-size: 10px;
            }
        """)
        time_label.setAlignment(Qt.AlignRight if self.is_user else Qt.AlignLeft)

        # Add to layout - both branches now actually add their icon row,
        # unlike before where the AI-message icon row was built and then
        # silently never attached to the layout.
        row = QHBoxLayout()
        row.setSpacing(8)
        if self.is_user:
            row.addWidget(message_label, 1)
        else:
            icon_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            row.addWidget(icon_label, 0, Qt.AlignTop)
            row.addWidget(message_label, 1)
        layout.addLayout(row)
        layout.addWidget(time_label)


class AIChartMessageWidget(QFrame):
    """Shows an AI-generated chart image inline in the chat, styled like a
    normal AI message bubble. Charts are read-only (never mutate the
    dataset), so unlike a proposed operation or dataset, there's no
    approval gate - this is purely a display widget."""

    def __init__(self, image_bytes: bytes, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #f3f4f6;
                border-radius: 14px;
                border: 1px solid #e5e7eb;
                padding: 12px 14px;
            }
        """)
        self.setMaximumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(8)
        icon_label = QLabel("🤖")
        icon_label.setStyleSheet("font-size: 15px;")
        icon_label.setFixedSize(22, 22)
        icon_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        row.addWidget(icon_label, 0, Qt.AlignTop)

        image_label = QLabel()
        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)
        available_width = 340 - 22 - 8 - 28  # bubble max width minus icon/spacing/padding
        if not pixmap.isNull():
            scaled = pixmap.scaledToWidth(available_width, Qt.SmoothTransformation)
            image_label.setPixmap(scaled)
        else:
            image_label.setText("(chart failed to render)")
        row.addWidget(image_label, 1)
        layout.addLayout(row)

        from datetime import datetime
        time_label = QLabel(datetime.now().strftime("%H:%M"))
        time_label.setStyleSheet("QLabel { color: #9ca3af; font-size: 10px; }")
        time_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(time_label)


class QuickActionButton(QPushButton):
    """Quick action button for AI panel"""

    def __init__(self, text: str, icon: str, description: str, parent=None):
        super().__init__(text, parent)
        self.icon = icon
        self.description = description
        self.setCursor(Qt.PointingHandCursor)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 12px 16px;
                background-color: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                color: #1f2937;
            }
            QPushButton:hover {
                background-color: #f9fafb;
                border-color: #3b82f6;
            }
            QPushButton:pressed {
                background-color: #f3f4f6;
            }
        """)


class AIPanel(QWidget):
    """AI Assistant Panel - Right sidebar component"""

    # Signals (thread-safe for cross-thread communication)
    sendMessage = Signal(str)  # When user sends a message
    cancelRequest = Signal()  # When user wants to cancel ongoing request
    clearChat = Signal()  # When user wants to clear the chat
    analyzeDataset = Signal()  # When user wants to analyze current dataset
    generateColumn = Signal()  # When user wants to generate a column
    complianceCheck = Signal()  # When user wants to run compliance check
    showSettings = Signal()  # When user wants to open AI settings
    actionProposed = Signal(str, dict, str)  # operation_id, params, reason - AI proposed a dataset change to review
    datasetProposed = Signal(str, str, str)  # sql, name, reason - AI proposed materializing a query as a new dataset
    # Thread-safe signals for UI updates
    _typingIndicatorNeeded = Signal()  # Internal signal for adding typing indicator
    _responseReady = Signal(str)  # Internal signal for showing response
    _errorReady = Signal(str)  # Internal signal for showing error
    _clearChatRequested = Signal()  # Internal signal for clearing chat
    _actionProposedInternal = Signal(str, dict, str)  # Internal: emitted from the background AI thread
    _datasetProposedInternal = Signal(str, str, str)  # Internal: emitted from the background AI thread
    _chartReadyInternal = Signal(bytes)  # Internal: a rendered chart image, ready to show inline

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_provider = "openai"
        self.messages: List[Dict] = []
        self.uploaded_files: List[Dict] = []  # {"name", "type", "path", "data"}
        self.is_processing = False
        self.typing_indicator = None  # Track typing indicator widget
        self.setup_ui()

        # Connect internal signals for thread-safe UI updates (queued for thread safety)
        self._typingIndicatorNeeded.connect(self._add_typing_indicator, Qt.QueuedConnection)
        self._responseReady.connect(self._on_response_received, Qt.QueuedConnection)
        self._errorReady.connect(self._on_error_received, Qt.QueuedConnection)
        self._clearChatRequested.connect(self._do_clear_chat, Qt.QueuedConnection)
        self._actionProposedInternal.connect(self._on_action_proposed_internal, Qt.QueuedConnection)
        self._datasetProposedInternal.connect(self._on_dataset_proposed_internal, Qt.QueuedConnection)
        self._chartReadyInternal.connect(self._on_chart_ready_internal, Qt.QueuedConnection)

    def setup_ui(self):
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = self.create_header()
        layout.addWidget(header)

        # Messages scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                width: 6px;
            }
        """)

        # Messages container
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(16, 16, 16, 16)
        self.messages_layout.setSpacing(12)
        self.messages_layout.addStretch()

        scroll.setWidget(self.messages_widget)
        layout.addWidget(scroll, 1)

        # Welcome message
        self.add_welcome_message()

        # Attached files (PDF/CSV/Excel become part of the chat context) —
        # ported from the standalone AI Chat dialog, which duplicated this
        # panel's general chat capability while being the only place file
        # upload existed. One chat surface now instead of two.
        attachments = self.create_attachments_area()
        layout.addWidget(attachments)

        # Input area
        input_frame = self.create_input_area()
        layout.addWidget(input_frame)

        # Quick actions
        quick_actions = self.create_quick_actions()
        layout.addWidget(quick_actions)

    def create_header(self) -> QWidget:
        """Create the panel header"""
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background-color: white;
                border-bottom: 1px solid #e5e7eb;
            }
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 12, 16, 12)

        # Title with icon
        title_layout = QHBoxLayout()
        icon_label = QLabel("🤖")
        icon_label.setStyleSheet("font-size: 20px;")
        title_layout.addWidget(icon_label)

        title = QLabel("AI Assistant")
        title.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: 700;
                color: #1f2937;
            }
        """)
        title_layout.addWidget(title)
        layout.addLayout(title_layout, 1)

        # Settings button (using QToolButton for better icon visibility)
        settings_btn = QToolButton()
        settings_btn.setFixedSize(32, 32)
        settings_btn.setText("⚙")
        settings_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                color: #374151;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #e5e7eb;
                border-color: #9ca3af;
                color: #1f2937;
            }
            QToolButton:pressed {
                background-color: #d1d5db;
            }
        """)
        settings_btn.clicked.connect(self.showSettings.emit)
        settings_btn.setToolTip("AI Settings")
        layout.addWidget(settings_btn)

        # Clear chat button
        clear_btn = QToolButton()
        clear_btn.setFixedSize(32, 32)
        clear_btn.setText("✕")
        clear_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
                color: #374151;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #fee2e2;
                border-color: #fca5a5;
                color: #991b1b;
            }
            QToolButton:pressed {
                background-color: #fecaca;
            }
        """)
        clear_btn.clicked.connect(self._on_clear_chat)
        clear_btn.setToolTip("Clear Chat")
        layout.addWidget(clear_btn)

        return header

    def create_input_area(self) -> QWidget:
        """Create the message input area"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-top: 1px solid #e5e7eb;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Processing indicator
        self.processing_label = QLabel("AI is thinking...")
        self.processing_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 12px;
                font-style: italic;
            }
        """)
        self.processing_label.hide()
        layout.addWidget(self.processing_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: transparent;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Input field
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("Ask AI about your data...")
        self.input_edit.setMaximumHeight(100)
        self.input_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 10px;
                font-size: 13px;
                background-color: #f9fafb;
            }
            QTextEdit:focus {
                border-color: #3b82f6;
                background-color: white;
            }
        """)
        self.input_edit.textChanged.connect(self.on_text_changed)
        # Handle Enter key for sending messages
        self.input_edit.keyPressEvent = self._on_input_keypress
        layout.addWidget(self.input_edit)

        # Button row
        button_layout = QHBoxLayout()

        # Provider indicator
        self.provider_label = QLabel("Model: Not configured")
        self.provider_label.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 11px;
            }
        """)
        button_layout.addWidget(self.provider_label)

        button_layout.addStretch()

        # Cancel button (hidden by default, shown during processing)
        self.cancel_btn = QPushButton("Stop")
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancelRequest.emit)
        self.cancel_btn.hide()
        button_layout.addWidget(self.cancel_btn)

        # Send button
        self.send_btn = QPushButton("Send")
        self.send_btn.setEnabled(False)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:disabled {
                background-color: #9ca3af;
            }
        """)
        self.send_btn.clicked.connect(self.send_message)
        button_layout.addWidget(self.send_btn)

        layout.addLayout(button_layout)

        return frame

    def create_attachments_area(self) -> QWidget:
        """PDF/CSV/Excel upload — content becomes part of the chat context
        via get_attachment_context(), which main_window._get_ai_context()
        folds into every message sent from this panel."""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: white;
                border-top: 1px solid #e5e7eb;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        label = QLabel("Attached Files")
        label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: 600;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
        """)
        header_row.addWidget(label)
        header_row.addStretch()

        small_btn_style = """
            QPushButton {
                padding: 4px 10px;
                font-size: 11px;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                background-color: white;
                color: #374151;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
            }
        """

        pdf_btn = QPushButton("+ PDF")
        pdf_btn.setCursor(Qt.PointingHandCursor)
        pdf_btn.setStyleSheet(small_btn_style)
        pdf_btn.clicked.connect(lambda: self._upload_file("pdf"))
        header_row.addWidget(pdf_btn)

        data_btn = QPushButton("+ CSV/Excel")
        data_btn.setCursor(Qt.PointingHandCursor)
        data_btn.setStyleSheet(small_btn_style)
        data_btn.clicked.connect(lambda: self._upload_file("data"))
        header_row.addWidget(data_btn)

        layout.addLayout(header_row)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(70)
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                font-size: 11px;
            }
        """)
        self.file_list.setVisible(False)
        layout.addWidget(self.file_list)

        self.clear_files_btn = QPushButton("Clear Files")
        self.clear_files_btn.setCursor(Qt.PointingHandCursor)
        self.clear_files_btn.setStyleSheet("""
            QPushButton {
                padding: 4px 10px;
                font-size: 11px;
                color: #991b1b;
                border: none;
                text-align: left;
            }
            QPushButton:hover {
                text-decoration: underline;
            }
        """)
        self.clear_files_btn.setVisible(False)
        self.clear_files_btn.clicked.connect(self._clear_files)
        layout.addWidget(self.clear_files_btn)

        return frame

    def _upload_file(self, file_type: str):
        """Upload a PDF/CSV/Excel file so its content becomes part of the
        chat context for subsequent messages."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path

        filters = "PDF Files (*.pdf)" if file_type == "pdf" else "Data Files (*.csv *.xlsx *.xls)"
        filename, _ = QFileDialog.getOpenFileName(self, "Upload File", "", filters)
        if not filename:
            return

        try:
            if file_type == "pdf":
                data = self._read_pdf(filename)
                file_ext = "pdf"
            else:
                data = self._read_data_file(filename)
                file_ext = Path(filename).suffix.lower()

            self.uploaded_files.append({
                "name": Path(filename).name, "type": file_ext, "path": filename, "data": data
            })
            self.file_list.addItem(QListWidgetItem(f"📄 {Path(filename).name}"))
            self.file_list.setVisible(True)
            self.clear_files_btn.setVisible(True)
            self.add_message(f"Attached: {Path(filename).name} — ask me anything about it.", is_user=False)
        except Exception as e:
            QMessageBox.warning(self, "Upload Error", f"Could not read file:\n{str(e)}")

    def _read_pdf(self, filepath: str) -> str:
        """Read a PDF and extract its text (first 50 pages, capped length)."""
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            text = ""
            for page in reader.pages[:50]:
                text += page.extract_text() + "\n"
            return text[:100000]
        except ImportError:
            return f"[PDF file: {filepath}]\nInstall pypdf to enable PDF text extraction."

    def _read_data_file(self, filepath: str):
        """Read a CSV/Excel file into a Polars DataFrame."""
        import polars as pl
        from pathlib import Path
        path = Path(filepath)
        if path.suffix.lower() == '.csv':
            return pl.read_csv(filepath)
        elif path.suffix.lower() in ('.xlsx', '.xls'):
            return pl.read_excel(filepath)
        raise ValueError(f"Unsupported file format: {path.suffix}")

    def _clear_files(self):
        self.uploaded_files = []
        self.file_list.clear()
        self.file_list.setVisible(False)
        self.clear_files_btn.setVisible(False)
        self.add_message("Attached files cleared.", is_user=False)

    def get_attachment_context(self) -> str:
        """Build a context string describing uploaded files, for the
        caller (main_window._get_ai_context) to fold into the prompt sent
        with the next chat message."""
        import polars as pl
        if not self.uploaded_files:
            return ""
        parts = []
        for f in self.uploaded_files:
            parts.append(f"Attached file: {f['name']} ({f['type']})")
            data = f.get('data')
            if isinstance(data, str):
                parts.append(f"Content:\n{data[:2000]}")
            elif isinstance(data, pl.DataFrame):
                parts.append(f"Rows: {data.height}, Columns: {list(data.columns)}")
        return "\n\n".join(parts)

    def create_quick_actions(self) -> QWidget:
        """Create quick action buttons"""
        frame = QWidget()
        frame.setStyleSheet("""
            QWidget {
                background-color: white;
                border-top: 1px solid #e5e7eb;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        label = QLabel("Quick Actions")
        label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 600;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
        """)
        layout.addWidget(label)

        # Action buttons grid
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        # Analyze dataset button
        analyze_btn = QPushButton("📊 Analyze")
        analyze_btn.setCursor(Qt.PointingHandCursor)
        analyze_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 12px;
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                color: #1e40af;
            }
            QPushButton:hover {
                background-color: #dbeafe;
            }
        """)
        analyze_btn.clicked.connect(self.analyzeDataset.emit)
        actions_layout.addWidget(analyze_btn)

        # Generate column button
        column_btn = QPushButton("📝 New Column")
        column_btn.setCursor(Qt.PointingHandCursor)
        column_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 12px;
                background-color: #f0fdf4;
                border: 1px solid #bbf7d0;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                color: #166534;
            }
            QPushButton:hover {
                background-color: #dcfce7;
            }
        """)
        column_btn.clicked.connect(self.generateColumn.emit)
        actions_layout.addWidget(column_btn)

        # Compliance check button
        compliance_btn = QPushButton("⚠️ Compliance")
        compliance_btn.setCursor(Qt.PointingHandCursor)
        compliance_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 12px;
                background-color: #fefce8;
                border: 1px solid #fde047;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                color: #854d0e;
            }
            QPushButton:hover {
                background-color: #fef9c3;
            }
        """)
        compliance_btn.clicked.connect(self.complianceCheck.emit)
        actions_layout.addWidget(compliance_btn)

        layout.addLayout(actions_layout)

        return frame

    def add_welcome_message(self):
        """Add welcome message to chat"""
        welcome = """Hello! I'm CaatMaster AI, your audit analytics assistant.

I can help you with:
• **Data Analysis** - Understand your datasets, find anomalies
• **Column Generation** - Create derived columns from natural language
• **Compliance Checking** - Test data against policies
• **Report Writing** - Draft audit findings and memos
• **Document Analysis** - Attach a PDF, CSV, or Excel file below and ask me about it

What would you like to do?"""
        self.add_message(welcome, is_user=False)

    def add_message(self, message: str, is_user: bool = False):
        """Add a message to the chat"""
        self.messages.append({"text": message, "is_user": is_user})

        widget = AIMessageWidget(message, is_user)
        # Without an explicit alignment, QVBoxLayout stretches/left-aligns
        # every child by default - user messages never actually appeared on
        # the right the way a chat UI needs to visually distinguish "you"
        # from "the AI" at a glance.
        alignment = Qt.AlignRight if is_user else Qt.AlignLeft
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, widget, 0, alignment)

        # Scroll to bottom
        QTimer.singleShot(50, self.scroll_to_bottom)

    def add_chart_message(self, image_bytes: bytes):
        """Show an AI-generated chart inline in the chat, the same way a
        text response appears."""
        widget = AIChartMessageWidget(image_bytes)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, widget, 0, Qt.AlignLeft)
        QTimer.singleShot(50, self.scroll_to_bottom)

    def add_typing_indicator(self):
        """Add typing indicator"""
        # Remove any existing typing indicator first
        self._remove_typing_indicator()

        widget = QLabel("🤖 AI is typing...")
        widget.setStyleSheet("""
            QLabel {
                color: #6b7280;
                font-size: 12px;
                font-style: italic;
                padding: 8px 16px;
            }
        """)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, widget)
        QTimer.singleShot(50, self.scroll_to_bottom)
        self.typing_indicator = widget

    def _remove_typing_indicator(self):
        """Remove typing indicator if exists"""
        if self.typing_indicator:
            self.messages_layout.removeWidget(self.typing_indicator)
            self.typing_indicator.deleteLater()
            self.typing_indicator = None

    def scroll_to_bottom(self):
        """Scroll messages to bottom"""
        scroll = self.parent().findChild(QScrollArea) if self.parent() else None
        if scroll:
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())

    def on_text_changed(self):
        """Handle text input changes"""
        text = self.input_edit.toPlainText().strip()
        self.send_btn.setEnabled(bool(text) and not self.is_processing)

    # Thread-safe internal methods (called via signals from other threads)
    def _add_typing_indicator(self):
        """Internal: add typing indicator (called from main thread via signal)"""
        self.add_typing_indicator()

    def _on_response_received(self, response: str):
        """Internal: handle response received (called from main thread via signal)"""
        self.receive_response(response)

    def _on_error_received(self, error: str):
        """Internal: handle error received (called from main thread via signal)"""
        self.show_error(error)

    def _do_clear_chat(self):
        """Internal: clear chat (called from main thread via signal)"""
        self._clear_all_messages()
        self.add_welcome_message()

    def _on_action_proposed_internal(self, operation_id: str, params: dict, reason: str):
        """Internal: re-emit as the public actionProposed signal now that
        we're safely on the main thread - main_window.py owns the actual
        dataset/pipeline and is what should react to this, not this panel."""
        self.actionProposed.emit(operation_id, params, reason)

    def _on_dataset_proposed_internal(self, sql: str, name: str, reason: str):
        """Internal: re-emit as the public datasetProposed signal now that
        we're safely on the main thread."""
        self.datasetProposed.emit(sql, name, reason)

    def _on_chart_ready_internal(self, image_bytes: bytes):
        """Internal: charts are read-only (never mutate the dataset), so
        they render straight into the chat once on the main thread -
        no approval gate needed, unlike a proposed operation or dataset."""
        self.add_chart_message(image_bytes)

    def _clear_all_messages(self):
        """Clear all message widgets"""
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.messages.clear()

    def _on_input_keypress(self, event):
        """Handle key press in input field"""
        # Send message on Enter (without Shift)
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            if self.send_btn.isEnabled():
                self.send_message()
            event.accept()
        else:
            # Pass to default handler
            QTextEdit.keyPressEvent(self.input_edit, event)

    def _on_clear_chat(self):
        """Handle clear chat button click (from UI thread)"""
        # Clear all messages and show welcome message directly (we're on main thread)
        self._clear_all_messages()
        self.add_welcome_message()
        # Emit signal in case main window needs to know
        self.clearChat.emit()

    def send_message(self):
        """Send user message"""
        text = self.input_edit.toPlainText().strip()
        if not text or self.is_processing:
            return

        # Add user message
        self.add_message(text, is_user=True)
        self.input_edit.clear()
        self.send_btn.setEnabled(False)

        # Show processing state
        self.set_processing(True)

        # Emit signal
        self.sendMessage.emit(text)

    def set_processing(self, processing: bool):
        """Set processing state"""
        self.is_processing = processing
        self.processing_label.setVisible(processing)
        self.progress_bar.setVisible(processing)

        # Toggle between cancel and send buttons
        if processing:
            self.progress_bar.setRange(0, 0)  # Indeterminate
            self.cancel_btn.show()
            self.send_btn.hide()
            self.input_edit.setEnabled(False)
        else:
            self.progress_bar.setRange(0, 100)
            self.cancel_btn.hide()
            self.send_btn.show()
            self.input_edit.setEnabled(True)
            # Re-check if there's text to enable send button
            self.on_text_changed()

    def receive_response(self, response: str):
        """Receive AI response"""
        self._remove_typing_indicator()
        self.set_processing(False)
        self.add_message(response, is_user=False)

    def show_error(self, error: str):
        """Show error message"""
        self._remove_typing_indicator()
        self.set_processing(False)
        self.add_message(f"Error: {error}", is_user=False)

    def set_provider(self, provider_name: str, model_name: str):
        """Update provider display"""
        self.current_provider = provider_name
        self.provider_label.setText(f"Model: {model_name}")

    def clear_chat(self):
        """Clear all messages and show welcome again (thread-safe)"""
        # Reset processing state first
        self.set_processing(False)

        # Emit signal to clear on main thread
        self._clearChatRequested.emit()
