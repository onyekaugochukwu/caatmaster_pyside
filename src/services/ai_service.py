"""
AI Service for CAATmaster
Multi-provider AI architecture for audit analytics

Features:
- Multi-provider support (OpenAI, Anthropic, Google, DeepSeek, Hugging Face, Ollama, LlamaCPP)
- Custom provider support with user-defined API endpoints
- Secure credential storage (OS Keyring with Fernet encryption fallback)
- Dataset interpretation and analysis
- AI-powered column generation
- Compliance report generation
- Post-audit report assistance

Note: AI features require API keys from providers
"""
import polars as pl
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from pathlib import Path
import os


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class AIResponse:
    """Standardized AI response"""
    content: str
    model: str
    provider: str
    usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    raw_response: Any = None


@dataclass
class DatasetSummary:
    """AI-generated dataset summary"""
    executive_summary: str
    data_quality: Dict[str, Any]
    key_fields: List[str]
    audit_insights: List[Dict[str, Any]]
    suggested_procedures: List[str]
    compliance_score: Optional[float] = None


@dataclass
class ColumnSuggestion:
    """AI-generated column suggestion"""
    column_name: str
    code: str
    explanation: str
    example_values: List[Any] = field(default_factory=list)


@dataclass
class ComplianceFinding:
    """AI-generated compliance finding"""
    title: str
    severity: str  # high, medium, low
    policy_requirement: str
    finding: str
    evidence: List[str]
    recommendation: str
    affected_count: int = 0
    affected_amount: float = 0.0


@dataclass
class ComplianceReport:
    """AI-generated compliance report"""
    overall_compliance_score: float
    executive_summary: str
    risk_summary: Dict[str, int]
    findings: List[ComplianceFinding]
    compliance_by_rule: List[Dict[str, Any]]


# =============================================================================
# Provider Base Classes
# =============================================================================

class BaseAIProvider(ABC):
    """Abstract base class for all AI providers"""

    # Default API configurations for known providers
    DEFAULT_CONFIGS = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "chat_endpoint": "/chat/completions",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "chat_endpoint": "/chat/completions",
            "models": ["deepseek-chat"]
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "chat_endpoint": "/messages",
            "models": ["claude-sonnet-4-20250514", "claude-haiku-4-20250514", "claude-opus-4-20250514"]
        },
        "google": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "chat_endpoint": "/models:generateContent",
            "models": ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "chat_endpoint": "/chat/completions",
            "models": ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "deepseek/deepseek-chat"]
        },
        "ollama": {
            "base_url": "http://localhost:11434",
            "chat_endpoint": "/api/chat",
            "models": ["llama3.2", "mistral", "codellama", "qwen2.5", "llama3.1"]
        },
        "llamacpp": {
            "base_url": "http://localhost:8080",
            "chat_endpoint": "/v1/chat/completions",
            "models": ["llama3.2", "mistral-7b", "codellama-7b"]
        }
    }

    def __init__(self, api_key: str, model: str = None, base_url: str = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = None

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the provider client"""
        pass

    @abstractmethod
    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        """Send a chat completion request"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name"""
        pass

    async def test_connection(self) -> tuple[bool, str]:
        """Test the connection to verify API key works.

        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Make a simple test request
            messages = [
                {"role": "user", "content": "Hello"}
            ]
            response = await self.complete(messages, max_tokens=5)
            if response and response.content:
                return True, "Connected successfully"
            else:
                return False, "Empty response from API"
        except Exception as e:
            error_msg = str(e)
            # Check for common authentication errors
            if "authentication" in error_msg.lower() or "api key" in error_msg.lower() or "invalid" in error_msg.lower():
                return False, f"Authentication failed: {error_msg}"
            elif "connection" in error_msg.lower() or "network" in error_msg.lower():
                return False, f"Connection error: {error_msg}"
            else:
                return False, f"Error: {error_msg[:100]}"

    def format_system_prompt(self, task_type: str) -> str:
        """Get system prompt for task type"""
        prompts = {
            "general": """You are CaatMaster AI, an intelligent assistant for audit professionals.
You help with data analysis, compliance checking, and report generation.
Always be precise, cite data sources, and provide actionable insights.
Never make up data or statistical values.""",

            "column_generation": """You are helping an auditor create a derived column.
Generate clean, correct Polars or Python pandas code.
Always handle edge cases and null values appropriately.
Explain your reasoning clearly.""",

            "dataset_interpretation": """You are a senior auditor analyzing a dataset.
Provide actionable insights for audit purposes.
Focus on data quality issues, anomalies, and audit risks.
Suggest relevant audit procedures.""",

            "compliance": """You are a senior auditor reviewing compliance with policies.
Identify specific instances of non-compliance with evidence.
Risk-rate findings appropriately.
Provide clear recommendations.""",

            "report_generation": """You are drafting audit report content.
Use formal audit language appropriate for management reports.
Be factual, objective, and constructive.
Include specific evidence where available.""",
        }
        base_prompt = prompts.get(task_type, prompts["general"])
        return base_prompt


class OpenAIProvider(BaseAIProvider):
    """OpenAI compatible provider implementation (supports custom base URLs)"""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str = None):
        super().__init__(api_key, model, base_url)
        self._client = None

    def initialize(self) -> bool:
        try:
            from openai import OpenAI
            if self.base_url:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=30.0)
            else:
                self.client = OpenAI(api_key=self.api_key, timeout=30.0)
            return True
        except ImportError:
            print("Warning: openai package not installed. Run: pip install openai")
            return False

    @property
    def provider_name(self) -> str:
        return "openai"

    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        import time
        start_time = time.time()

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)

        latency_ms = (time.time() - start_time) * 1000

        return AIResponse(
            content=response.choices[0].message.content,
            model=self.model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            latency_ms=latency_ms,
            raw_response=response
        )


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude provider implementation"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        super().__init__(api_key, model)
        self._client = None

    def initialize(self) -> bool:
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            return True
        except ImportError:
            print("Warning: anthropic package not installed. Run: pip install anthropic")
            return False

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        import time
        start_time = time.time()

        # Convert messages format
        system_msg = None
        user_msgs = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_msgs.append(msg)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_msg,
            messages=user_msgs,
            temperature=temperature
        )

        latency_ms = (time.time() - start_time) * 1000

        return AIResponse(
            content=response.content[0].text if response.content else "",
            model=self.model,
            provider=self.provider_name,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            },
            latency_ms=latency_ms,
            raw_response=response
        )


class GoogleProvider(BaseAIProvider):
    """Google Gemini provider implementation"""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-exp"):
        super().__init__(api_key, model)
        self._client = None

    def initialize(self) -> bool:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(self.model)
            return True
        except ImportError:
            print("Warning: google-generativeai package not installed. Run: pip install google-generativeai")
            return False

    @property
    def provider_name(self) -> str:
        return "google"

    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        import time
        start_time = time.time()

        # Convert messages format
        combined_prompt = ""
        for msg in messages:
            role = msg["role"].upper()
            content = msg["content"]
            combined_prompt += f"{role}: {content}\n"

        response = self.client.generate_content(
            combined_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens
            }
        )

        latency_ms = (time.time() - start_time) * 1000

        return AIResponse(
            content=response.text,
            model=self.model,
            provider=self.provider_name,
            latency_ms=latency_ms,
            raw_response=response
        )


class DeepSeekProvider(BaseAIProvider):
    """DeepSeek provider - OpenAI compatible API"""

    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        super().__init__(api_key, model, base_url="https://api.deepseek.com")
        self._client = None

    def initialize(self) -> bool:
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url or "https://api.deepseek.com",
                timeout=30.0
            )
            return True
        except ImportError:
            print("Warning: openai package not installed. Run: pip install openai")
            return False

    @property
    def provider_name(self) -> str:
        return "deepseek"

    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        import time
        start_time = time.time()

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)

        latency_ms = (time.time() - start_time) * 1000

        return AIResponse(
            content=response.choices[0].message.content,
            model=self.model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            latency_ms=latency_ms,
            raw_response=response
        )


class HuggingFaceProvider(BaseAIProvider):
    """Hugging Face Inference API provider"""

    def __init__(self, api_key: str, model: str = "meta-llama/Llama-3.2-3B-Instruct"):
        super().__init__(api_key, model)
        self._client = None

    def initialize(self) -> bool:
        try:
            from huggingface_hub import InferenceClient
            self.client = InferenceClient(token=self.api_key)
            return True
        except ImportError:
            print("Warning: huggingface_hub package not installed. Run: pip install huggingface_hub")
            return False

    @property
    def provider_name(self) -> str:
        return "huggingface"

    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        import time
        start_time = time.time()

        # Convert messages to single prompt for HF
        prompt = self._format_prompt(messages)

        response = self.client.text_generation(
            prompt,
            model=self.model,
            max_new_tokens=max_tokens,
            temperature=temperature,
            return_full_text=False
        )

        latency_ms = (time.time() - start_time) * 1000

        return AIResponse(
            content=response,
            model=self.model,
            provider=self.provider_name,
            latency_ms=latency_ms
        )

    def _format_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Format messages as a single prompt"""
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "system":
                parts.append(f"System: {content}")
            else:
                parts.append(f"User: {content}")
        return "\n\n".join(parts) + "\n\nAssistant:"


class OllamaProvider(BaseAIProvider):
    """Ollama local LLM provider"""

    def __init__(self, api_key: str = "", model: str = "llama3.2"):
        # Ollama doesn't require API key for local instances
        super().__init__(api_key or "", model, base_url="http://localhost:11434")
        self._client = None

    def initialize(self) -> bool:
        try:
            import httpx
            self._http_client = httpx.AsyncClient(timeout=120.0)
            return True
        except ImportError:
            print("Warning: httpx package not installed. Run: pip install httpx")
            return False

    @property
    def provider_name(self) -> str:
        return "ollama"

    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        import time
        start_time = time.time()

        # Convert messages format for Ollama
        formatted_messages = []
        for msg in messages:
            if msg["role"] != "system":
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        response = await self._http_client.post(
            f"{self.base_url}/api/chat",
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        latency_ms = (time.time() - start_time) * 1000

        content = data.get("message", {}).get("content", "")

        return AIResponse(
            content=content,
            model=self.model,
            provider=self.provider_name,
            latency_ms=latency_ms
        )


class LlamaCPPProvider(BaseAIProvider):
    """LlamaCPP server provider (OpenAI compatible API)"""

    def __init__(self, api_key: str = "", model: str = "llama3.2"):
        # LlamaCPP server doesn't require API key
        super().__init__(api_key or "", model, base_url="http://localhost:8080/v1")
        self._client = None

    def initialize(self) -> bool:
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key or "not-needed",
                base_url=self.base_url,
                timeout=30.0
            )
            return True
        except ImportError:
            print("Warning: openai package not installed. Run: pip install openai")
            return False

    @property
    def provider_name(self) -> str:
        return "llamacpp"

    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        import time
        start_time = time.time()

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)

        latency_ms = (time.time() - start_time) * 1000

        return AIResponse(
            content=response.choices[0].message.content,
            model=self.model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            latency_ms=latency_ms,
            raw_response=response
        )


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter AI aggregator - OpenAI compatible"""

    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet"):
        super().__init__(api_key, model, base_url="https://openrouter.ai/api/v1")
        self._client = None

    def initialize(self) -> bool:
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0,
                default_headers={
                    "HTTP-Referer": "https://caatmaster.app",
                    "X-Title": "CaatMaster Audit Software"
                }
            )
            return True
        except ImportError:
            print("Warning: openai package not installed. Run: pip install openai")
            return False

    @property
    def provider_name(self) -> str:
        return "openrouter"

    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        import time
        start_time = time.time()

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)

        latency_ms = (time.time() - start_time) * 1000

        return AIResponse(
            content=response.choices[0].message.content,
            model=self.model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            latency_ms=latency_ms,
            raw_response=response
        )


class CustomProvider(BaseAIProvider):
    """Custom OpenAI-compatible API provider with user-defined endpoint"""

    def __init__(self, api_key: str, model: str, base_url: str):
        super().__init__(api_key, model, base_url)
        self._client = None

    def initialize(self) -> bool:
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=30.0  # 30 second timeout
            )
            return True
        except ImportError:
            print("Warning: openai package not installed. Run: pip install openai")
            return False

    @property
    def provider_name(self) -> str:
        return "custom"

    async def complete(self, messages: List[Dict[str, str]],
                       temperature: float = 0.1,
                       max_tokens: int = 4000,
                       response_format: Dict = None) -> AIResponse:
        import time
        start_time = time.time()

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)

        latency_ms = (time.time() - start_time) * 1000

        return AIResponse(
            content=response.choices[0].message.content,
            model=self.model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            latency_ms=latency_ms,
            raw_response=response
        )


# =============================================================================
# Provider Factory
# =============================================================================

class AIProviderFactory:
    """Factory for creating AI providers"""

    _providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
        "deepseek": DeepSeekProvider,
        "huggingface": HuggingFaceProvider,
        "ollama": OllamaProvider,
        "llamacpp": LlamaCPPProvider,
        "openrouter": OpenRouterProvider,
    }

    # Provider display names
    DISPLAY_NAMES = {
        "openai": "OpenAI",
        "anthropic": "Anthropic Claude",
        "google": "Google Gemini",
        "deepseek": "DeepSeek",
        "huggingface": "Hugging Face",
        "ollama": "Ollama (Local)",
        "llamacpp": "LlamaCPP (Local)",
        "openrouter": "OpenRouter",
        "custom": "Custom Provider"
    }

    # Provider requiring API key
    REQUIRES_API_KEY = {
        "openai", "anthropic", "google", "deepseek", "huggingface", "openrouter"
    }

    # Local providers (no API key needed)
    LOCAL_PROVIDERS = {"ollama", "llamacpp"}

    @classmethod
    def create(cls, provider_name: str, api_key: str = "", model: str = None,
               base_url: str = None) -> Optional[BaseAIProvider]:
        """Create a provider instance"""
        provider_name = provider_name.lower()

        # Handle custom provider
        if provider_name == "custom":
            if not base_url or not model:
                raise ValueError("Custom provider requires base_url and model")
            provider = CustomProvider(api_key, model, base_url)
            if provider.initialize():
                return provider
            return None

        provider_class = cls._providers.get(provider_name)
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(cls._providers.keys())}")

        # Get default model if not provided
        if model is None:
            config = BaseAIProvider.DEFAULT_CONFIGS.get(provider_name, {})
            models = config.get("models", [])
            if models:
                model = models[0]

        # For local providers, api_key is not needed
        if provider_name in cls.LOCAL_PROVIDERS:
            api_key = ""

        provider = provider_class(api_key, model)
        if provider.initialize():
            return provider

        return None

    @classmethod
    def list_providers(cls) -> List[str]:
        """List available providers"""
        return list(cls._providers.keys())

    @classmethod
    def get_display_name(cls, provider_name: str) -> str:
        """Get display name for provider"""
        return cls.DISPLAY_NAMES.get(provider_name.lower(), provider_name)

    @classmethod
    def get_default_config(cls, provider_name: str) -> Optional[Dict]:
        """Get default configuration for a provider"""
        return BaseAIProvider.DEFAULT_CONFIGS.get(provider_name.lower())

    @classmethod
    def requires_api_key(cls, provider_name: str) -> bool:
        """Check if provider requires API key"""
        return provider_name.lower() in cls.REQUIRES_API_KEY

    @classmethod
    def is_local_provider(cls, provider_name: str) -> bool:
        """Check if provider is a local/self-hosted instance"""
        return provider_name.lower() in cls.LOCAL_PROVIDERS

    @classmethod
    async def test_connection(cls, provider_name: str, api_key: str = "", model: str = None,
                               base_url: str = None) -> tuple[bool, str]:
        """Test if a provider connection works with the given credentials.

        Args:
            provider_name: Name of the provider
            api_key: API key (optional for local providers)
            model: Model name (optional)
            base_url: Custom base URL (optional)

        Returns:
            tuple: (success: bool, message: str)
        """
        # For local providers, no API key needed
        if provider_name.lower() in cls.LOCAL_PROVIDERS:
            api_key = ""

        try:
            provider = cls.create(provider_name, api_key, model, base_url)
            if provider is None:
                return False, "Failed to initialize provider client"

            # Run the actual test
            return await provider.test_connection()
        except Exception as e:
            return False, f"Connection test failed: {str(e)[:100]}"


# =============================================================================
# AI Manager
# =============================================================================

class AIManager:
    """
    Central manager for all AI operations

    Usage:
        manager = AIManager()
        manager.add_provider("openai", "sk-...")
        response = manager.complete("What is 2+2?")
    """

    def __init__(self):
        self.providers: Dict[str, BaseAIProvider] = {}
        self.default_provider = "openai"
        self.system_prompt = self._get_default_system_prompt()
        self.usage_tracker: List[Dict] = []

    def _get_default_system_prompt(self) -> str:
        return """You are CaatMaster AI, an intelligent assistant for audit professionals.
You help with data analysis, compliance checking, and report generation.
Always be precise, cite data sources, and provide actionable insights.
Never make up data or statistical values - calculate them from provided information."""

    def add_provider(self, name: str, api_key: str = "", model: str = None, base_url: str = None) -> bool:
        """Add a provider configuration"""
        provider = AIProviderFactory.create(name, api_key, model, base_url)
        if provider:
            self.providers[name.lower()] = provider
            if not self.default_provider:
                self.default_provider = name.lower()
            return True
        return False

    def remove_provider(self, name: str):
        """Remove a provider"""
        name = name.lower()
        if name in self.providers:
            del self.providers[name]
            if self.default_provider == name:
                self.default_provider = list(self.providers.keys())[0] if self.providers else None

    def set_default_provider(self, name: str):
        """Set the default provider"""
        name = name.lower()
        if name in self.providers:
            self.default_provider = name

    def get_provider(self, name: str = None) -> Optional[BaseAIProvider]:
        """Get a provider by name"""
        name = (name or self.default_provider).lower()
        return self.providers.get(name)

    async def complete(self, prompt: str,
                       provider: str = None,
                       task_type: str = "general",
                       temperature: float = 0.1,
                       force_json: bool = False) -> AIResponse:
        """Send a completion request"""
        prov = self.get_provider(provider)
        if not prov:
            raise ValueError(f"No provider available. Add a provider first.")

        # Build messages
        system_prompt = prov.format_system_prompt(task_type)
        if force_json:
            # OpenAI requires "json" to appear in messages when using json_object mode
            system_prompt = system_prompt.strip() + " You must respond with valid JSON output."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        # Use response_format for OpenAI-compatible providers when JSON is forced
        response_format = None
        if force_json:
            response_format = {"type": "json_object"}

        response = await prov.complete(messages, temperature=temperature, response_format=response_format)

        # Track usage
        self.usage_tracker.append({
            "provider": prov.provider_name,
            "model": prov.model,
            "timestamp": datetime.now().isoformat(),
            "tokens": response.usage,
            "latency_ms": response.latency_ms
        })

        return response

    async def structured_complete(self, prompt: str,
                                   provider: str = None,
                                   task_type: str = "general",
                                   response_format: str = "json") -> Dict:
        """
        Send a completion request and parse as structured response

        Args:
            prompt: The prompt to send
            provider: Provider name (uses default if not specified)
            task_type: Type of task (affects system prompt)
            response_format: Expected format (json, etc.)

        Returns:
            Parsed response as dictionary
        """
        prov = self.get_provider(provider)
        if not prov:
            raise ValueError(f"No provider available. Add a provider first.")

        messages = [
            {"role": "system", "content": prov.format_system_prompt(task_type) +
             f"\n\nRespond in {response_format} format only. No additional text."},
            {"role": "user", "content": prompt}
        ]

        response = await prov.complete(messages, temperature=0.1)

        # Parse response
        content = response.content.strip()

        # Try to extract JSON
        if response_format == "json":
            # Remove markdown code blocks if present
            content = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
            content = re.sub(r'\s*```$', '', content)

            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON response: {e}")
                print(f"Raw content: {content[:500]}")
                raise

        return {"content": content}

    def get_usage_stats(self) -> Dict:
        """Get usage statistics"""
        total_tokens = sum(
            t.get("tokens", {}).get("total_tokens", 0)
            for t in self.usage_tracker
        )
        total_cost = sum(
            t.get("tokens", {}).get("total_tokens", 0) * 0.00001  # Rough estimate
            for t in self.usage_tracker
        )

        return {
            "total_requests": len(self.usage_tracker),
            "total_tokens": total_tokens,
            "estimated_cost": round(total_cost, 4),
            "by_provider": {}
        }


# =============================================================================
# Dataset Interpreter
# =============================================================================

class DatasetInterpreter:
    """AI-powered dataset interpretation and analysis"""

    def __init__(self, ai_manager: AIManager):
        self.ai = ai_manager

    def get_schema_info(self, df: pl.DataFrame) -> Dict:
        """Get dataset schema information"""
        return {
            "columns": [
                {
                    "name": col,
                    "dtype": str(df[col].dtype),
                    "null_count": int(df[col].null_count()),
                    "null_pct": round(df[col].null_count() / len(df) * 100, 2) if len(df) > 0 else 0,
                    "unique_count": int(df[col].n_unique()),
                    "sample_values": df[col].head(5).to_list()
                }
                for col in df.columns
            ],
            "row_count": len(df),
            "column_count": len(df.columns),
            "shape": list(df.shape)
        }

    async def analyze_dataset(self, df: pl.DataFrame,
                               audit_context: str = "") -> DatasetSummary:
        """Generate comprehensive dataset analysis"""

        schema_info = self.get_schema_info(df)

        prompt = f"""
Analyze this dataset for an audit engagement.

Audit Context: {audit_context or "General audit review"}

Dataset Information:
- Rows: {schema_info['row_count']}
- Columns: {schema_info['column_count']}

Column Details:
{self._format_columns(schema_info['columns'])}

Provide your analysis as JSON:
{{
    "executive_summary": "2-3 paragraph summary of what this dataset contains",
    "data_quality": {{
        "overall_score": 0-100,
        "null_percentage": overall null rate,
        "issues": [
            {{"column": "name", "issue": "description", "severity": "high/medium/low"}}
        ]
    }},
    "key_fields": ["field1", "field2"],
    "audit_insights": [
        {{
            "type": "outlier/trend/anomaly/pattern",
            "title": "Brief title",
            "description": "Detailed description",
            "severity": "high/medium/low",
            "recommendation": "Suggested audit action"
        }}
    ],
    "suggested_procedures": ["procedure1", "procedure2"]
}}

Only respond with valid JSON.
"""

        result = await self.ai.structured_complete(
            prompt=prompt,
            task_type="dataset_interpretation",
            response_format="json"
        )

        return DatasetSummary(
            executive_summary=result.get("executive_summary", ""),
            data_quality=result.get("data_quality", {}),
            key_fields=result.get("key_fields", []),
            audit_insights=result.get("audit_insights", []),
            suggested_procedures=result.get("suggested_procedures", [])
        )

    def _format_columns(self, columns: List[Dict]) -> str:
        """Format columns for prompt"""
        lines = []
        for col in columns:
            lines.append(
                f"- {col['name']}: {col['dtype']} "
                f"(nulls: {col['null_pct']}%, unique: {col['unique_count']})"
            )
        return "\n".join(lines)


# =============================================================================
# Column Generator
# =============================================================================

class ColumnGenerator:
    """AI-powered column generation from natural language"""

    def __init__(self, ai_manager: AIManager):
        self.ai = ai_manager

    async def generate_column(self, instruction: str,
                              df: pl.DataFrame,
                              column_name: str = None) -> ColumnSuggestion:
        """Generate a new column based on natural language instruction"""

        schema_info = self._get_schema_info(df)

        # Build column name instruction
        if column_name:
            name_instruction = f'The column MUST be named "{column_name}".'
            name_in_code = f'alias("{column_name}")'
        else:
            name_instruction = 'Provide a clear, descriptive column name.'
            name_in_code = 'alias("new_column")'

        prompt = f"""
You are helping an auditor create a new derived column.

Dataset Schema:
{schema_info}

Instruction: "{instruction}"

{name_instruction}

Provide your response as JSON:
{{
    "column_name": "{column_name if column_name else "your_suggested_name"}",
    "code": "Complete Polars code to create this column with {name_in_code}",
    "explanation": "Brief explanation of what this column contains",
    "example_values": ["value1", "value2", "value3"]
}}

Requirements:
- Use Polars (pl.) library
- Handle null values appropriately
- Use method chaining with .with_columns()
- The code MUST create a column named "{column_name if column_name else 'your_suggested_name'}"
- Return only valid JSON
"""

        result = await self.ai.structured_complete(
            prompt=prompt,
            task_type="column_generation",
            response_format="json"
        )

        return ColumnSuggestion(
            column_name=result.get("column_name", "new_column"),
            code=result.get("code", ""),
            explanation=result.get("explanation", ""),
            example_values=result.get("example_values", [])
        )

    def apply_column(self, df: pl.DataFrame, code: str) -> pl.DataFrame:
        """Apply generated column code to dataframe"""
        try:
            exec_globals = {"pl": pl}

            # Check if code reassigns df (e.g., "df = df.with_columns(...)")
            lines = code.strip().split("\n")
            first_line = lines[0] if lines else ""
            reassigns_df = "=" in first_line and first_line.split("=")[0].strip() in ("df", "_df")

            if not reassigns_df:
                # Code doesn't reassign df - wrap it to capture result
                # The code likely uses df.with_columns(...) pattern
                # We need to wrap it so the result is captured
                wrapped = "_result = (" + code.strip() + ")\n_result"
                code = wrapped

            exec_locals = {"df": df}

            # Execute the code
            exec(code, exec_globals, exec_locals)

            # Check if we have a captured result
            if "_result" in exec_locals:
                result = exec_locals["_result"]
                if isinstance(result, pl.DataFrame):
                    return result

            # Check if df was reassigned
            if "df" in exec_locals:
                result_df = exec_locals["df"]
                if isinstance(result_df, pl.DataFrame):
                    return result_df

            return df

        except Exception as e:
            print(f"Error applying column code: {e}")
            raise

    def _get_schema_info(self, df: pl.DataFrame) -> str:
        """Get schema info for prompt"""
        lines = [f"Dataset has {len(df.columns)} columns:"]
        for col in df.columns:
            dtype = df[col].dtype
            sample = str(df[col].head(3).to_list())
            lines.append(f"  - {col} ({dtype}): {sample}")
        return "\n".join(lines)


# =============================================================================
# Compliance Report Generator
# =============================================================================

class ComplianceReportGenerator:
    """AI-powered compliance report generation"""

    def __init__(self, ai_manager: AIManager):
        self.ai = ai_manager

    async def generate_report(self, policy_text: str,
                              data_summary: Dict,
                              findings: List[Dict]) -> ComplianceReport:
        """Generate compliance report from policy and findings"""

        prompt = f"""
You are a senior auditor preparing a compliance assessment report.

POLICY DOCUMENT:
{policy_text[:3000]}  # Truncate if too long

DATA ANALYZED:
{json.dumps(data_summary, indent=2)}

IDENTIFIED FINDINGS:
{self._format_findings(findings)}

Provide your analysis as JSON:
{{
    "overall_compliance_score": 0-100,
    "executive_summary": "2-3 paragraph summary",
    "risk_summary": {{
        "high_risk_count": 0,
        "medium_risk_count": 0,
        "low_risk_count": 0
    }},
    "findings": [
        {{
            "title": "Finding title",
            "severity": "high/medium/low",
            "policy_requirement": "The relevant policy rule",
            "finding": "What was identified",
            "evidence": ["TXN-123", "TXN-456"],
            "recommendation": "Suggested remediation",
            "affected_count": 10,
            "affected_amount": 50000
        }}
    ],
    "compliance_by_rule": [
        {{
            "rule_name": "Rule name",
            "compliant_pct": 95,
            "exception_pct": 5
        }}
    ]
}}

Only respond with valid JSON.
"""

        result = await self.ai.structured_complete(
            prompt=prompt,
            task_type="compliance",
            response_format="json"
        )

        findings = []
        for f in result.get("findings", []):
            findings.append(ComplianceFinding(
                title=f.get("title", ""),
                severity=f.get("severity", "medium"),
                policy_requirement=f.get("policy_requirement", ""),
                finding=f.get("finding", ""),
                evidence=f.get("evidence", []),
                recommendation=f.get("recommendation", ""),
                affected_count=f.get("affected_count", 0),
                affected_amount=f.get("affected_amount", 0.0)
            ))

        return ComplianceReport(
            overall_compliance_score=result.get("overall_compliance_score", 0),
            executive_summary=result.get("executive_summary", ""),
            risk_summary=result.get("risk_summary", {}),
            findings=findings,
            compliance_by_rule=result.get("compliance_by_rule", [])
        )

    async def detect_violations(self, df: pl.DataFrame,
                                 policy_rules: List[Dict]) -> List[ComplianceFinding]:
        """Detect potential compliance violations from data"""

        # Sample data for analysis
        sample_size = min(100, len(df))
        sample_data = df.sample(sample_size).to_dicts()

        rules_context = "\n".join([
            f"- {rule.get('name', 'Unknown')}: {rule.get('description', '')}\n  Condition: {rule.get('condition', '')}"
            for rule in policy_rules
        ])

        prompt = f"""
You are analyzing transaction data for compliance with these rules:

{rules_context}

Sample Data ({sample_size} records):
{json.dumps(sample_data[:10], indent=2)}  # First 10 records for context

Identify potential compliance violations. Respond as JSON:
{{
    "violations": [
        {{
            "rule_name": "Rule name",
            "finding": "Description of violation",
            "severity": "high/medium/low",
            "evidence": ["example transaction IDs"],
            "affected_count": estimated_count,
            "recommendation": "Suggested action"
        }}
    ]
}}

Only respond with valid JSON.
"""

        result = await self.ai.structured_complete(
            prompt=prompt,
            task_type="compliance",
            response_format="json"
        )

        violations = []
        for v in result.get("violations", []):
            violations.append(ComplianceFinding(
                title=v.get("rule_name", ""),
                severity=v.get("severity", "medium"),
                policy_requirement="",  # Will be filled from rules
                finding=v.get("finding", ""),
                evidence=v.get("evidence", []),
                recommendation=v.get("recommendation", ""),
                affected_count=v.get("affected_count", 0)
            ))

        return violations

    def _format_findings(self, findings: List[Dict]) -> str:
        """Format findings for prompt"""
        return "\n".join([
            f"- {f.get('title', 'Unknown')}: {f.get('description', '')} "
            f"(severity: {f.get('severity', 'unknown')})"
            for f in findings
        ])


# =============================================================================
# Report Assistant
# =============================================================================

class ReportAssistant:
    """AI-assisted report generation for post-audit reports"""

    def __init__(self, ai_manager: AIManager):
        self.ai = ai_manager

    async def draft_section(self, section: str,
                            audit_results: Dict,
                            tone: str = "professional") -> str:
        """Draft a section of a post-audit report"""

        prompt = f"""
Draft the {section} section of a post-audit management report.

Audit Results:
{json.dumps(audit_results, indent=2)}

Requirements:
- Tone: {tone}
- Audience: Client management
- Include specific data and evidence
- Be factual and constructive
- Maximum 300 words

Draft this section now:
"""

        response = await self.ai.complete(
            prompt=prompt,
            task_type="report_generation",
            temperature=0.3
        )

        return response.content

    async def summarize_findings(self, findings: List[Dict]) -> str:
        """Generate a summary of audit findings"""

        findings_text = "\n".join([
            f"- {f.get('title', 'Unknown')}: {f.get('description', '')} (Risk: {f.get('severity', 'unknown')})"
            for f in findings
        ])

        prompt = f"""
Summarize these audit findings for an executive summary:

{findings_text}

Provide:
1. One paragraph summary (max 200 words)
2. Key themes across findings
3. Overall risk assessment

Keep it concise and suitable for executive readers.
"""

        response = await self.ai.complete(
            prompt=prompt,
            task_type="report_generation",
            temperature=0.2
        )

        return response.content


# =============================================================================
# Credential Storage (Encrypted fallback for when keyring is unavailable)
# Uses Fernet encryption with system-derived key
# =============================================================================

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    FERNET_AVAILABLE = True
except ImportError:
    FERNET_AVAILABLE = False
    print("Warning: cryptography library not installed. Install with: pip install cryptography")


def _derive_encryption_key() -> bytes:
    """Derive a Fernet encryption key from system information.

    This creates a unique key per machine/user installation without requiring
    the user to remember a master password. The key is derived using PBKDF2
    from system-specific identifiers.

    Note: This provides reasonable security for local desktop applications.
    For higher security, use OS Keyring which integrates with the OS vault.
    """
    import hashlib
    import base64

    # Get system-specific identifiers
    salt_parts = []

    # Machine ID (Linux)
    try:
        with open('/etc/machine-id', 'r') as f:
            salt_parts.append(f.read().strip())
    except:
        pass

    # User ID
    salt_parts.append(str(os.getuid()))

    # Home directory (user-specific)
    salt_parts.append(str(Path.home()))

    # Application salt (makes it unique to CaatMaster)
    salt_parts.append('caatmaster-ai-credentials-v1')

    # Combine and hash to get a consistent seed
    combined = '|'.join(salt_parts).encode('utf-8')
    seed = hashlib.sha256(combined).digest()

    # Use PBKDF2 to derive a proper 32-byte Fernet key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # Fernet requires 32 bytes
        salt=b'caatmaster-fernet-salt-v1',
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(seed))
    return key


class EncryptedCredentialStore:
    """Secure file-based credential storage using Fernet encryption.

    Credentials are encrypted before storage and decrypted when retrieved.
    Uses a system-derived encryption key that is unique to the installation.
    """

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "caatmaster"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.credentials_file = self.config_dir / "ai_credentials.json"
        self._fernet = None
        self._init_fernet()

    def _init_fernet(self):
        """Initialize Fernet cipher with derived key"""
        if not FERNET_AVAILABLE:
            return

        try:
            key = _derive_encryption_key()
            # Use the key directly as Fernet key (requires 32 bytes url-safe base64)
            self._fernet = Fernet(key)
        except Exception as e:
            print(f"Warning: Could not initialize encryption: {e}")
            self._fernet = None

    def _encrypt(self, data: str) -> str:
        """Encrypt a string value"""
        if self._fernet:
            return self._fernet.encrypt(data.encode('utf-8')).decode('utf-8')
        return data  # Fallback to plain text if encryption fails

    def _decrypt(self, data: str) -> str:
        """Decrypt a string value"""
        if self._fernet:
            try:
                return self._fernet.decrypt(data.encode('utf-8')).decode('utf-8')
            except Exception:
                # Data might be plain text (legacy format)
                return data
        return data

    def save_credentials(self, provider: str, api_key: str, model: str = None, base_url: str = None):
        """Save credentials to file (encrypted)"""
        credentials = self._load_all()

        # Encrypt the API key and base_url
        credentials[provider] = {
            "api_key": self._encrypt(api_key) if api_key else "",
            "model": model,
            "base_url": self._encrypt(base_url) if base_url else ""
        }

        with open(self.credentials_file, 'w') as f:
            json.dump(credentials, f, indent=2)
        os.chmod(self.credentials_file, 0o600)  # Restrict to user only

    def _save_raw(self, provider: str, data: Dict):
        """Save data without encryption (for non-sensitive data like default_provider)"""
        credentials = self._load_all()
        credentials[provider] = data
        with open(self.credentials_file, 'w') as f:
            json.dump(credentials, f, indent=2)
        os.chmod(self.credentials_file, 0o600)

    def get_credentials(self, provider: str) -> Optional[Dict]:
        """Get credentials for a provider (decrypted)"""
        credentials = self._load_all()

        if provider not in credentials:
            return None

        data = credentials[provider]

        # Handle legacy plain text format
        api_key = data.get("api_key", "")
        if api_key and not self._is_encrypted(data):
            # Legacy format - key is not encrypted
            pass
        elif api_key:
            # New encrypted format
            api_key = self._decrypt(api_key)

        base_url = data.get("base_url", "")
        if base_url and self._is_encrypted(data):
            base_url = self._decrypt(base_url)

        return {
            "api_key": api_key,
            "model": data.get("model"),
            "base_url": base_url
        }

    def _is_encrypted(self, data: Dict) -> bool:
        """Check if data appears to be encrypted (Fernet tokens are base64 with specific length)"""
        api_key = data.get("api_key", "")
        if not api_key:
            return False
        # Fernet tokens are url-safe base64 and typically 88+ bytes when decoded
        # (includes version byte, timestamp, ciphertext, and signature)
        try:
            import base64
            decoded = base64.urlsafe_b64decode(api_key)
            # Fernet tokens are at least 88 bytes (1 version + 8 timestamp + 16 min IV + 1 block + 32 tag)
            return len(decoded) >= 88
        except:
            return False

    def get_all_credentials(self) -> Dict:
        """Get all stored credentials (without API keys for security)"""
        credentials = self._load_all()
        result = {}
        for p, c in credentials.items():
            result[p] = {
                "model": c.get("model"),
                "base_url": c.get("base_url")  # May be empty for non-encrypted
            }
        return result

    def delete_credentials(self, provider: str):
        """Delete credentials for a provider"""
        credentials = self._load_all()
        if provider in credentials:
            del credentials[provider]
            with open(self.credentials_file, 'w') as f:
                json.dump(credentials, f, indent=2)

    def _load_all(self) -> Dict:
        """Load all credentials from file"""
        if self.credentials_file.exists():
            try:
                with open(self.credentials_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, PermissionError):
                return {}
        return {}


# Keep old class name for backward compatibility
SimpleCredentialStore = EncryptedCredentialStore


# Try to import keyring, fall back to encrypted storage
try:
    import keyring
    _use_keyring = True
except ImportError:
    _use_keyring = False

_credential_store = SimpleCredentialStore()


# =============================================================================
# Utility Functions
# =============================================================================

def save_ai_credentials(provider: str, api_key: str, model: str = None, base_url: str = None):
    """Save AI provider credentials"""
    # Special case: default_provider stores just the provider name, not an API key
    if provider == "default_provider":
        if _use_keyring:
            keyring.set_password("caatmaster", f"ai_{provider}", api_key)  # Store as plain provider name
        else:
            _credential_store._save_raw(provider, {"api_key": api_key, "model": None, "base_url": ""})  # No encryption
        return

    if _use_keyring:
        keyring.set_password("caatmaster", f"ai_{provider}", api_key)
        if model:
            keyring.set_password("caatmaster", f"ai_{provider}_model", model)
        if base_url:
            keyring.set_password("caatmaster", f"ai_{provider}_base_url", base_url)
    else:
        _credential_store.save_credentials(provider, api_key, model, base_url)


def get_ai_credentials(provider: str) -> Optional[Dict]:
    """Get AI provider credentials"""
    if _use_keyring:
        api_key = keyring.get_password("caatmaster", f"ai_{provider}")
        model = keyring.get_password("caatmaster", f"ai_{provider}_model")
        base_url = keyring.get_password("caatmaster", f"ai_{provider}_base_url")
        # Return dict even if api_key is None (for local providers)
        if api_key or model or base_url:
            return {"api_key": api_key, "model": model, "base_url": base_url}
        return None
    else:
        # Special case: default_provider stores just the provider name
        if provider == "default_provider":
            creds = _credential_store._load_all().get(provider)
            if creds:
                return {"api_key": creds.get("api_key"), "model": None, "base_url": ""}
            return None
        return _credential_store.get_credentials(provider)


def load_stored_providers(manager: AIManager):
    """Load all stored providers into the manager"""
    # Define local providers (no API key needed)
    local_providers = {"ollama", "llamacpp"}

    if _use_keyring:
        # keyring doesn't easily list all passwords, so we try known providers
        providers = ["openai", "anthropic", "google", "deepseek", "huggingface", "openrouter", "ollama", "llamacpp"]
        for provider in providers:
            creds = get_ai_credentials(provider)
            if provider in local_providers:
                # Local providers don't need API key
                model = creds.get("model") if creds else None
                base_url = creds.get("base_url") if creds else None
                if model or base_url:  # Has some configuration
                    manager.add_provider(provider, "", model, base_url)
            elif creds and creds.get("api_key"):
                manager.add_provider(provider, creds["api_key"], creds.get("model"))

        # Load default provider setting
        default_creds = get_ai_credentials("default_provider")
        if default_creds and default_creds.get("api_key"):
            manager.default_provider = default_creds["api_key"]
    else:
        # Simple storage can list all
        all_creds = _credential_store._load_all()
        for provider, info in all_creds.items():
            # Skip the default_provider setting - it's not an actual provider
            if provider == "default_provider":
                # Load default provider from stored setting (no encryption)
                default_data = all_creds.get("default_provider")
                if default_data and default_data.get("api_key"):
                    manager.default_provider = default_data["api_key"]
                continue

            creds = _credential_store.get_credentials(provider)
            if creds:
                api_key = creds.get("api_key", "")
                base_url = creds.get("base_url")
                model = creds.get("model")
                # Add if there's an API key OR it's a local provider (no key needed)
                if api_key or provider in local_providers:
                    manager.add_provider(provider, api_key, model, base_url)


def create_ai_manager() -> AIManager:
    """Create and configure AI manager with stored credentials"""
    manager = AIManager()
    load_stored_providers(manager)
    return manager


# =============================================================================
# Legacy Compatibility (keep existing methods)
# =============================================================================

class AIService:
    """Legacy service - maintained for backward compatibility"""

    def __init__(self, api_key: str = None, provider: str = "openai"):
        self.api_key = api_key
        self.provider = provider

        # Initialize new architecture
        self.manager = AIManager()
        if api_key:
            self.manager.add_provider(provider, api_key)

        # Legacy attributes
        self.client = None
        if api_key and provider == "openai":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key, timeout=30.0)
            except ImportError:
                print("Warning: openai package not installed")

    def classify_text(self, df: pl.DataFrame, column: str,
                      categories: List[str], output_column: str = None,
                      confidence_column: str = None, batch_size: int = 10) -> pl.DataFrame:
        """Legacy method - preserved for compatibility"""
        # This would need to be reimplemented with new architecture
        # For now, return original dataframe
        return df

    def extract_entity(self, df: pl.DataFrame, column: str,
                       entity_type: str, output_column: str = None,
                       custom_prompt: str = None) -> pl.DataFrame:
        """Legacy method - preserved for compatibility"""
        return df

    def analyze_sentiment(self, df: pl.DataFrame, column: str,
                          score_column: str = None, label_column: str = None) -> pl.DataFrame:
        """Legacy method - preserved for compatibility"""
        return df

    def learn_pattern(self, df: pl.DataFrame, source_column: str,
                      examples: Dict[str, str], output_columns: List[str]) -> pl.DataFrame:
        """Legacy method - preserved for compatibility"""
        return df
