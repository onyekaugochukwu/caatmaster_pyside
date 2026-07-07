"""AI Settings Dialog - Configure AI providers and settings"""
import asyncio
from typing import Dict, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTabWidget, QWidget, QFormLayout,
    QSpinBox, QDoubleSpinBox, QGroupBox, QGridLayout, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QFrame, QScrollArea,
    QStackedWidget
)
from PySide6.QtCore import Qt, QSize, Signal, Slot, QThread
from PySide6.QtGui import QFont, QColor

from src.services.ai_service import AIProviderFactory, BaseAIProvider
from ..theme import Colors
from ..components.common_modals import StatusLabel, create_success_button, create_primary_button


class ProviderConfigWidget(QWidget):
    """Widget for configuring a specific AI provider"""

    def __init__(self, provider_name: str, parent=None):
        super().__init__(parent)
        self.provider_name = provider_name
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(16)

        # Check if this is a local provider (no API key needed)
        is_local = AIProviderFactory.is_local_provider(self.provider_name)

        # API Key input (not shown for local providers) - sizing overrides
        # only, colors/border/focus inherited from the app-wide QLineEdit
        # rule in theme.py.
        input_style = "QLineEdit { padding: 12px 16px; min-width: 300px; }"
        if not is_local:
            self.api_key_edit = QLineEdit()
            self.api_key_edit.setPlaceholderText("Enter API key")
            self.api_key_edit.setEchoMode(QLineEdit.Password)
            self.api_key_edit.setMinimumWidth(350)
            self.api_key_edit.setStyleSheet(input_style)
            layout.addRow("API Key:", self.api_key_edit)
        else:
            self.api_key_edit = None
            api_note = QLabel("(Local provider - no API key required)")
            api_note.setStyleSheet(f"""
                QLabel {{
                    font-size: 13px;
                    color: {Colors.TEXT_SECONDARY};
                    font-style: italic;
                    padding: 8px 0;
                }}
            """)
            layout.addRow("", api_note)

        # Base URL input (optional, shows default)
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("Leave empty for default or enter custom URL")
        self.base_url_edit.setMinimumWidth(350)
        self.base_url_edit.setStyleSheet(input_style)

        # Set default URL
        default_config = AIProviderFactory.get_default_config(self.provider_name)
        if default_config:
            self.base_url_edit.setText(default_config.get("base_url", ""))

        layout.addRow("API URL:", self.base_url_edit)

        # Model selection - editable line edit
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("Enter model name (e.g., gpt-4o, llama3.2)")
        self.model_edit.setMinimumWidth(350)
        self.model_edit.setStyleSheet(input_style)

        # Pre-fill with default model if available
        if default_config:
            models = default_config.get("models", [])
            if models:
                self.model_edit.setText(models[0])

        layout.addRow("Model:", self.model_edit)

        # Test button
        test_btn = create_success_button("Test Connection")
        layout.addRow("", test_btn)
        test_btn.clicked.connect(self.test_connection)

        # Status label - reuses StatusLabel's existing normal/success/
        # warning/error color states instead of hand-rolling the same
        # four-state color switch locally.
        self.status_label = StatusLabel()
        layout.addRow("Status:", self.status_label)

    def setup_models(self):
        """Setup available models for provider - kept for compatibility"""
        # Model is now an editable line edit, so no setup needed
        pass

    def get_config(self) -> Dict:
        """Get current configuration"""
        api_key = ""
        if self.api_key_edit:
            api_key = self.api_key_edit.text()

        base_url = self.base_url_edit.text().strip()
        if not base_url:
            base_url = None  # Use default

        model = self.model_edit.text().strip()
        if not model:
            # Get default model
            default_config = AIProviderFactory.get_default_config(self.provider_name)
            if default_config:
                models = default_config.get("models", [])
                if models:
                    model = models[0]

        return {
            "provider": self.provider_name,
            "api_key": api_key,
            "model": model,
            "base_url": base_url
        }

    def set_config(self, config: Dict):
        """Set configuration"""
        if config.get("provider") == self.provider_name:
            if self.api_key_edit:
                self.api_key_edit.setText(config.get("api_key", ""))
            if config.get("base_url"):
                self.base_url_edit.setText(config.get("base_url"))
            if config.get("model"):
                self.model_edit.setText(config.get("model"))

    def test_connection(self):
        """Test the connection to the provider"""
        from src.services.ai_service import AIProviderFactory

        config = self.get_config()

        # Check if this is a local provider
        is_local = AIProviderFactory.is_local_provider(config["provider"])

        # Validate API key for non-local providers
        if not is_local and not config["api_key"]:
            self.status_label.setText("Please enter an API key")
            self.status_label.setStatus("error")
            return

        self.status_label.setText("Testing connection...")
        self.status_label.setStatus("warning")

        async def run_test():
            success, message = await AIProviderFactory.test_connection(
                config["provider"],
                config["api_key"],
                config["model"],
                config["base_url"]
            )
            return success, message

        # Run the async test
        try:
            loop = asyncio.new_event_loop()
            try:
                success, message = loop.run_until_complete(run_test())
            finally:
                loop.close()

            self.status_label.setText(message)
            self.status_label.setStatus("success" if success else "error")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)[:100]}")
            self.status_label.setStatus("error")


class CustomProviderWidget(QWidget):
    """Widget for configuring a custom OpenAI-compatible provider"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        layout.setSpacing(16)

        input_style = "QLineEdit { padding: 12px 16px; min-width: 300px; }"

        # Provider name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My Custom Provider")
        self.name_edit.setMinimumWidth(350)
        self.name_edit.setStyleSheet(input_style)
        layout.addRow("Provider Name:", self.name_edit)

        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Enter API key (optional for some servers)")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setMinimumWidth(350)
        self.api_key_edit.setStyleSheet(input_style)
        layout.addRow("API Key:", self.api_key_edit)

        # Base URL
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.example.com/v1")
        self.base_url_edit.setMinimumWidth(350)
        self.base_url_edit.setStyleSheet(input_style)
        layout.addRow("Base URL:", self.base_url_edit)

        # Model
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("e.g., llama3.2, my-model-name")
        self.model_edit.setMinimumWidth(350)
        self.model_edit.setStyleSheet(input_style)
        layout.addRow("Model:", self.model_edit)

        # Test button
        test_btn = create_success_button("Test Connection")
        layout.addRow("", test_btn)
        test_btn.clicked.connect(self.test_connection)

        # Status label
        self.status_label = StatusLabel()
        layout.addRow("Status:", self.status_label)

    def get_config(self) -> Dict:
        """Get configuration"""
        name = self.name_edit.text().strip().lower().replace(" ", "_")
        if not name:
            name = "custom"

        return {
            "provider": name,
            "display_name": self.name_edit.text().strip() or "Custom Provider",
            "api_key": self.api_key_edit.text(),
            "base_url": self.base_url_edit.text().strip(),
            "model": self.model_edit.text().strip()
        }

    def test_connection(self):
        """Test the custom connection"""
        config = self.get_config()

        if not config["base_url"]:
            self.status_label.setText("Please enter a base URL")
            self.status_label.setStatus("error")
            return

        if not config["model"]:
            self.status_label.setText("Please enter a model name")
            self.status_label.setStatus("error")
            return

        self.status_label.setText("Testing connection...")
        self.status_label.setStatus("warning")

        from src.services.ai_service import AIProviderFactory

        async def run_test():
            success, message = await AIProviderFactory.test_connection(
                "custom",
                config["api_key"],
                config["model"],
                config["base_url"]
            )
            return success, message

        # Run the async test
        try:
            loop = asyncio.new_event_loop()
            try:
                success, message = loop.run_until_complete(run_test())
            finally:
                loop.close()

            self.status_label.setText(message)
            self.status_label.setStatus("success" if success else "error")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)[:100]}")
            self.status_label.setStatus("error")


class AISettingsDialog(QDialog):
    """Dialog for configuring AI settings"""

    # Signal emitted when settings change
    settingsChanged = Signal()

    def __init__(self, ai_manager=None, parent=None):
        super().__init__(parent)
        self.ai_manager = ai_manager
        self.provider_widgets: Dict[str, ProviderConfigWidget] = {}
        self.custom_provider_widget = None
        self.setup_ui()
        self.load_settings()  # Load saved configurations

    def setup_ui(self):
        self.setWindowTitle("AI Settings")
        self.setMinimumSize(750, 680)
        # Dialog background inherited from the app-wide QDialog rule in theme.py.

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("AI Configuration")
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 20px;
                font-weight: 700;
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(title)

        # Provider tabs (configuration first) - pane/tab chrome inherited
        # from the app-wide QTabWidget rule in theme.py; only sizing here.
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                padding: 12px 24px;
                min-width: 100px;
            }
        """)

        # Standard providers
        providers = ["openai", "anthropic", "google", "deepseek", "huggingface", "openrouter"]
        for provider in providers:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)

            widget = ProviderConfigWidget(provider)
            self.provider_widgets[provider] = widget
            display_name = AIProviderFactory.get_display_name(provider)

            scroll.setWidget(widget)
            self.tabs.addTab(scroll, display_name)

        # Local providers (Ollama, LlamaCPP)
        local_scroll = QScrollArea()
        local_scroll.setWidgetResizable(True)
        local_scroll.setFrameShape(QFrame.NoFrame)

        local_frame = QWidget()
        local_layout = QVBoxLayout(local_frame)
        local_layout.setContentsMargins(16, 16, 16, 16)
        local_layout.setSpacing(20)

        # Ollama widget
        ollama_widget = ProviderConfigWidget("ollama")
        self.provider_widgets["ollama"] = ollama_widget
        local_layout.addWidget(ollama_widget)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        local_layout.addWidget(separator)

        # LlamaCPP widget
        llamacpp_widget = ProviderConfigWidget("llamacpp")
        self.provider_widgets["llamacpp"] = llamacpp_widget
        local_layout.addWidget(llamacpp_widget)

        local_scroll.setWidget(local_frame)
        self.tabs.addTab(local_scroll, "Local Providers")

        # Custom provider tab
        custom_scroll = QScrollArea()
        custom_scroll.setWidgetResizable(True)
        custom_scroll.setFrameShape(QFrame.NoFrame)
        custom_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
            QScrollBar:vertical {
                width: 10px;
            }
        """)

        self.custom_provider_widget = CustomProviderWidget()
        custom_scroll.setWidget(self.custom_provider_widget)
        self.tabs.addTab(custom_scroll, "Add Custom")

        layout.addWidget(self.tabs)

        # Active Provider Selection Section (after configuration) -
        # QGroupBox/QComboBox chrome inherited from the app-wide rules.
        active_group = QGroupBox("Select Active Provider")
        active_layout = QHBoxLayout(active_group)
        active_layout.setContentsMargins(16, 20, 16, 16)

        active_label = QLabel("Use this provider for AI features:")
        active_label.setStyleSheet(f"font-size: 14px; color: {Colors.TEXT_SECONDARY};")
        active_layout.addWidget(active_label)

        self.active_provider_combo = QComboBox()
        self.active_provider_combo.setMinimumWidth(250)
        self.active_provider_combo.setStyleSheet("QComboBox { min-width: 200px; }")
        active_layout.addWidget(self.active_provider_combo)
        active_layout.addStretch()

        layout.addWidget(active_group)

        # Usage section
        usage_group = QGroupBox("Usage & Costs")
        usage_layout = QVBoxLayout(usage_group)

        self.usage_label = QLabel("No usage data available")
        self.usage_label.setStyleSheet(f"""
            QLabel {{
                color: {Colors.TEXT_SECONDARY};
                font-size: 13px;
                padding: 8px;
            }}
        """)
        usage_layout.addWidget(self.usage_label)

        # Refresh usage button
        refresh_btn = QPushButton("Refresh Usage")
        usage_layout.addWidget(refresh_btn, alignment=Qt.AlignRight)

        layout.addWidget(usage_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = create_primary_button("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def save_settings(self):
        """Save all provider configurations"""
        from src.services.ai_service import save_ai_credentials, AIProviderFactory, FERNET_AVAILABLE

        # Any real (non-local) API key about to be saved while the
        # cryptography package is missing would previously be written to
        # disk in PLAINTEXT with only a console-only warning — easy to miss
        # entirely. Ask explicitly instead of silently downgrading security.
        if not FERNET_AVAILABLE:
            has_real_key = any(
                widget.get_config()["api_key"] and not AIProviderFactory.is_local_provider(provider)
                for provider, widget in self.provider_widgets.items()
            )
            if self.custom_provider_widget:
                custom_config = self.custom_provider_widget.get_config()
                has_real_key = has_real_key or bool(custom_config.get("api_key"))
            if has_real_key:
                proceed = QMessageBox.warning(
                    self, "Encryption Unavailable",
                    "The 'cryptography' package isn't installed, so API keys "
                    "will be saved in PLAIN TEXT on disk instead of encrypted.\n\n"
                    "Install it first for encrypted storage:\n"
                    "    pip install cryptography\n\n"
                    "Save the key(s) in plain text anyway?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if proceed != QMessageBox.Yes:
                    return

        configs = {}
        saved_providers = []

        # Save standard providers
        for provider, widget in self.provider_widgets.items():
            config = widget.get_config()
            # Save if API key present OR it's a local provider
            if config["api_key"] or AIProviderFactory.is_local_provider(provider):
                save_ai_credentials(
                    provider,
                    config["api_key"],
                    config["model"],
                    config["base_url"]
                )
                configs[provider] = config
                saved_providers.append(provider)

        # Save custom provider if configured
        if self.custom_provider_widget:
            custom_config = self.custom_provider_widget.get_config()
            if custom_config["base_url"] and custom_config["model"]:
                save_ai_credentials(
                    custom_config["provider"],
                    custom_config["api_key"],
                    custom_config["model"],
                    custom_config["base_url"]
                )
                configs[custom_config["provider"]] = custom_config
                saved_providers.append(custom_config["provider"])

        # Save active provider
        active_index = self.active_provider_combo.currentIndex()
        if active_index >= 0:
            active_provider = self.active_provider_combo.itemData(active_index)
            if active_provider:
                save_ai_credentials("default_provider", active_provider, None, None)
                if self.ai_manager:
                    self.ai_manager.default_provider = active_provider

        print(f"Saving AI configs: {saved_providers}")

        # Refresh the active provider combo
        self._refresh_active_providers(saved_providers)

        self.settingsChanged.emit()
        self.accept()

    def _refresh_active_providers(self, just_saved_providers=None):
        """Refresh the active provider combo box"""
        from src.services.ai_service import get_ai_credentials, AIProviderFactory

        self.active_provider_combo.clear()

        # Get default provider
        default_creds = get_ai_credentials("default_provider")
        default_provider = default_creds.get("api_key") if default_creds else None
        if not default_provider and self.ai_manager:
            default_provider = self.ai_manager.default_provider

        # Collect all providers (standard + custom)
        all_providers = set(self.provider_widgets.keys())

        # Check if custom provider was saved
        if self.custom_provider_widget:
            custom_config = self.custom_provider_widget.get_config()
            if custom_config.get("base_url") and custom_config.get("model"):
                all_providers.add(custom_config["provider"])

        # Add all configured providers to the combo
        for provider in all_providers:
            config = None
            # Get config from widget if it exists
            if provider in self.provider_widgets:
                config = self.provider_widgets[provider].get_config()
            # Or check credentials
            if config is None:
                creds = get_ai_credentials(provider)
                if creds:
                    config = creds

            if config:
                has_key = config.get("api_key") or AIProviderFactory.is_local_provider(provider)
                if has_key:
                    display_name = AIProviderFactory.get_display_name(provider)
                    self.active_provider_combo.addItem(display_name, provider)

        # Try to set the active provider
        if default_provider:
            idx = self.active_provider_combo.findData(default_provider)
            if idx >= 0:
                self.active_provider_combo.setCurrentIndex(idx)
        elif self.active_provider_combo.count() > 0:
            self.active_provider_combo.setCurrentIndex(0)

    def load_settings(self):
        """Load saved configurations"""
        from src.services.ai_service import get_ai_credentials

        all_providers = list(self.provider_widgets.keys())

        # Load configurations for each provider
        for provider in all_providers:
            widget = self.provider_widgets[provider]
            creds = get_ai_credentials(provider)
            if creds:
                widget.set_config({
                    "provider": provider,
                    "api_key": creds.get("api_key", ""),
                    "model": creds.get("model", ""),
                    "base_url": creds.get("base_url", "")
                })

        # Populate active provider combo using shared method
        self._refresh_active_providers()

    def update_usage_display(self, usage: Dict):
        """Update usage display"""
        if usage:
            self.usage_label.setText(
                f"Requests: {usage.get('total_requests', 0)} | "
                f"Tokens: {usage.get('total_tokens', 0):,} | "
                f"Est. Cost: ${usage.get('estimated_cost', 0):.4f}"
            )
        else:
            self.usage_label.setText("No usage data available")


# Usage tracking dialog
class AIUsageDialog(QDialog):
    """Dialog showing AI usage statistics"""

    def __init__(self, usage_data: Dict, parent=None):
        super().__init__(parent)
        self.usage_data = usage_data
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("AI Usage & Costs")
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title = QLabel("AI Usage Statistics")
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 700;
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        layout.addWidget(title)

        # Summary cards
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        # Requests card
        requests_card = self.create_stat_card(
            "Total Requests",
            str(self.usage_data.get("total_requests", 0)),
            Colors.ACCENT
        )
        cards_layout.addWidget(requests_card)

        # Tokens card
        tokens_card = self.create_stat_card(
            "Total Tokens",
            f"{self.usage_data.get('total_tokens', 0):,}",
            Colors.WARNING_STRONG
        )
        cards_layout.addWidget(tokens_card)

        # Cost card
        cost_card = self.create_stat_card(
            "Est. Cost",
            f"${self.usage_data.get('estimated_cost', 0):.4f}",
            Colors.SUCCESS
        )
        cards_layout.addWidget(cost_card)

        layout.addLayout(cards_layout)

        # By provider breakdown
        by_provider = self.usage_data.get("by_provider", {})
        if by_provider:
            provider_group = QGroupBox("Usage by Provider")
            provider_layout = QVBoxLayout(provider_group)

            for provider, stats in by_provider.items():
                label = QLabel(f"{provider}: {stats.get('requests', 0)} requests, "
                              f"{stats.get('tokens', 0):,} tokens")
                label.setStyleSheet(f"""
                    QLabel {{
                        padding: 8px;
                        font-size: 13px;
                        color: {Colors.TEXT_SECONDARY};
                    }}
                """)
                provider_layout.addWidget(label)

            layout.addWidget(provider_group)

        layout.addStretch()

        # Close button
        close_btn = create_primary_button("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def create_stat_card(self, title: str, value: str, color: str) -> QWidget:
        """Create a statistics card"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                padding: 16px;
            }}
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(title)
        label.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {Colors.TEXT_SECONDARY};
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
        """)
        layout.addWidget(label)

        value_label = QLabel(value)
        value_label.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: 700;
                color: {color};
            }}
        """)
        layout.addWidget(value_label)

        return card
