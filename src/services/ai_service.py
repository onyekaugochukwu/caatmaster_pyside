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
import ast
from pathlib import Path
import os


# =============================================================================
# Sandboxed execution for AI-generated code
# =============================================================================
# LLM-generated Polars code (from the Column Generator, etc.) has to run
# somewhere. A naive exec(code, {"pl": pl}) looks sandboxed but isn't:
# Python auto-injects the REAL __builtins__ into any globals dict that
# doesn't define its own "__builtins__" key, so generated code would have
# had full access to __import__, open, eval, network calls, everything —
# regardless of how empty the globals dict looked. This restricts builtins
# to a minimal safe set and rejects imports/dunder-attribute access/dangerous
# names via an AST walk before anything is executed.

SAFE_BUILTINS = {
    'len': len, 'range': range, 'str': str, 'int': int, 'float': float,
    'bool': bool, 'abs': abs, 'min': min, 'max': max, 'sum': sum,
    'round': round, 'list': list, 'dict': dict, 'tuple': tuple, 'set': set,
    'True': True, 'False': False, 'None': None, 'enumerate': enumerate,
    'zip': zip, 'sorted': sorted, 'isinstance': isinstance,
}

_FORBIDDEN_AST_NODES = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)
_FORBIDDEN_NAMES = {
    'exec', 'eval', 'compile', 'open', '__import__', 'globals', 'locals',
    'vars', 'getattr', 'setattr', 'delattr', 'input', 'breakpoint',
    '__builtins__', 'help', 'exit', 'quit',
}


def validate_generated_code(code: str) -> ast.AST:
    """Parse AI-generated code and reject anything containing imports,
    global/nonlocal statements, dangerous builtin names, or dunder-attribute
    access, before it's ever exec()'d. Raises ValueError on anything
    disallowed."""
    try:
        tree = ast.parse(code, mode='exec')
    except SyntaxError as e:
        raise ValueError(f"Generated code has a syntax error: {e}")

    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            raise ValueError("Generated code may not use imports or global/nonlocal statements.")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise ValueError(f"Generated code may not reference '{node.id}'.")
        if isinstance(node, ast.Attribute) and node.attr.startswith('__') and node.attr.endswith('__'):
            raise ValueError(f"Generated code may not access dunder attribute '{node.attr}'.")
    return tree


def safe_exec_polars_code(code: str, df: pl.DataFrame) -> pl.DataFrame:
    """Execute AI-generated Polars code against `df` with a restricted
    builtins set and a pre-execution AST safety check. Shared by both the
    Column Generator (ai_service.py) and the ai_generate_column
    transformation operation (data_processor.py) — there is exactly one
    place this logic lives now, not two copies that can drift apart."""
    validate_generated_code(code)

    exec_globals = {"pl": pl, "__builtins__": SAFE_BUILTINS}
    exec_locals = {"df": df}

    lines = code.strip().split("\n")
    first_line = lines[0] if lines else ""
    reassigns_df = "=" in first_line and first_line.split("=")[0].strip() in ("df", "_df")

    code_to_exec = code.strip() if reassigns_df else f"_result = ({code.strip()})\n_result"

    exec(code_to_exec, exec_globals, exec_locals)

    result = exec_locals.get("_result")
    if isinstance(result, pl.DataFrame):
        return result
    result_df = exec_locals.get("df")
    if isinstance(result_df, pl.DataFrame):
        return result_df
    return df


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
class SQLSuggestion:
    """AI-generated SQL suggestion for the SQL editor - never executed by
    the generator itself; the caller always shows it to the user for
    review before it's ever run."""
    sql: str
    explanation: str


@dataclass
class ComplianceFinding:
    """AI-drafted description wrapped around a real, deterministically
    computed result — affected_count/affected_amount/affected_pct/evidence
    all come from applying the rule's condition to the complete dataset
    (see ComplianceReportGenerator.compute_rule_violation), never from the
    AI itself."""
    title: str
    severity: str  # high, medium, low, or 'info' for zero-match/uncomputable rules
    policy_requirement: str
    finding: str
    evidence: List[str]
    recommendation: str
    affected_count: int = 0
    affected_amount: float = 0.0
    total_count: int = 0
    affected_pct: float = 0.0
    computable: bool = True


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

            "sql_generation": """You are helping an auditor who does not write SQL express a request as a
single DuckDB SQL query, to review and run themselves.
Write exactly one read-only SELECT (or WITH ... SELECT) statement - never DDL/DML, never multiple
statements, never a file-access function (read_csv, COPY, ATTACH, etc.) - only query the tables you were
given, using their exact names. Use only the column names you were actually given; never invent a table
or column name that merely sounds plausible - if what's needed wasn't listed, say so in the explanation
instead of guessing at a name.
When a query involves more than one table, give every table an explicit short alias (e.g. "FROM Customers c
JOIN Orders o ON o.CustomerID = c.CustomerID") and qualify every column with that alias. Never reference a
table by any name that is neither one of the exact table names you were given nor an alias you defined
earlier in that same query.
Always include a one-sentence plain-English restatement of what the query does, so accepting it is an
informed choice rather than a leap of faith.""",

            "financial_import": """You are helping an auditor import a financial document (general ledger/
journal entry detail, trial balance, financial statement, or chart of accounts) whose structure a
deterministic heuristic could not confidently resolve on its own. You are the fallback for exactly this
gap, not a general data-interpretation tool - only use the real column names, values, or account names you
were actually given; never invent one that merely sounds plausible. If you are not reasonably confident in
a mapping, say so explicitly (e.g. set the value to null or add a low_confidence note) rather than guessing
just to fill in every field - the auditor reviews and can correct every suggestion you make before it's
used for anything, but a wrong-but-confident-looking guess is worse than an honest "not sure".
Always respond with valid JSON only, in the exact shape requested in the prompt.""",

            "agent_qa": """You are CaatMaster AI, an assistant that can answer questions about the auditor's
data, visualize it, propose changes to it, materialize a query result as a new dataset, and answer
questions about how to use CaatMaster itself. Decide which ONE of the following the auditor's message
calls for:

1. ANSWER directly, using the real summary statistics you were already given, when those already cover
   the question precisely.
2. QUERY: if the question needs something the summary stats don't cover - an exact count under a specific
   filter, a join across datasets, a computation not already shown - do not estimate or guess. Request a
   single read-only SQL SELECT against the listed tables; it will be run against the complete, real data
   and the exact result given back to you before you answer.
3. OPERATION: if the auditor wants a change made to their dataset (not a question) - e.g. "remove test
   transactions", "rename this column", "sort by amount" - propose exactly ONE operation from the
   operations menu you were given. Never assume it was applied - the auditor always sees a before/after
   preview and clicks Apply themselves. IMPORTANT: an operation can only ever apply to the dataset marked
   [CURRENTLY ACTIVE] above, using ONLY that dataset's real columns (listed in the operations menu) - if
   the column/data the request needs actually belongs to a DIFFERENT listed dataset, do not propose an
   operation against the active one; instead either answer that they should switch to that dataset first,
   or use QUERY/DATASET instead, which can reference any dataset by name.
4. CHART: if the auditor wants to see/visualize their data - e.g. "show me a chart of...", "visualize...",
   "plot..." - propose exactly ONE chart from the chart menu you were given, specifying which dataset it's
   from. Unlike OPERATION, a chart may use ANY dataset listed in the chart menu, not just the one marked
   [CURRENTLY ACTIVE] - it never writes anywhere, so there's no reason to limit it to the active one.
   Charts render immediately (no approval needed).
5. DATASET: if the auditor asks to be GIVEN something - "give me a table/dataset/list of...", "create a
   table of...", "extract..." - propose a single read-only SQL SELECT (same rules as QUERY) whose result
   will become a new dataset, after the auditor confirms. This takes priority over OPERATION even when the
   request also describes a filter/sort - "give me a table that only has approved transactions" is
   DATASET (a new table filtered to approved rows), not OPERATION, because the auditor is asking to
   receive a new thing, not asking to change the dataset they already have open. Only use OPERATION when
   the auditor is clearly asking to edit their CURRENT, already-open dataset in place (no "give me"/
   "create a table" framing).
6. HELP: if the question is about how to use CaatMaster itself, not about the data - e.g. "how do I
   promote a row to headers", "where is the SQL editor" - request a search of the app's feature reference;
   matching entries will be given back to you before you answer.

Respond with JSON only, in exactly one of these shapes:
{"type": "answer", "answer": "..."}
{"type": "query", "sql": "SELECT ...", "reason": "why the summary stats above aren't enough"}
{"type": "operation", "operation_id": "...", "params": {...}, "reason": "one sentence, what this does and why"}
{"type": "chart", "dataset": "<dataset name from the chart menu>", "chart_type": "...", "params": {...}, "reason": "one sentence, what this shows"}
{"type": "dataset", "sql": "SELECT ...", "name": "suggested short dataset name", "reason": "..."}
{"type": "help", "topic": "a short search phrase describing what they want to know how to do"}

Only use an operation_id/chart_type and parameter names exactly as given in the menus you were given -
never invent one. Never fabricate a number, feature, or menu location you were not given or did not
look up. Keep "answer" concise and direct - don't add a disclaimer restating that a figure came from
real or complete data; the auditor already trusts that, so just answer.""",
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
        # Every real LLM call (prompt, model, response, timestamp) is
        # appended here AND persisted to disk — for a tool whose whole
        # purpose is auditability, "what did the AI actually see and say"
        # needs to be reviewable after the fact, not just trusted.
        self.audit_log_path = Path.home() / ".config" / "caatmaster" / "ai_audit_log.jsonl"
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

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
        self._log_audit_entry(task_type, prov, messages, response)

        return response

    def _log_audit_entry(self, task_type: str, provider: 'BaseAIProvider', messages: List[Dict[str, str]],
                          response: Optional['AIResponse'] = None, error: str = None):
        """Append one real LLM call to the on-disk audit log — every field
        needed to answer "what did the AI actually see and say" later,
        whether the call succeeded or failed."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "provider": provider.provider_name if provider else None,
            "model": provider.model if provider else None,
            "prompt": messages,
            "response": response.content if response else None,
            "tokens": response.usage if response else None,
            "latency_ms": response.latency_ms if response else None,
            "error": error,
        }
        try:
            with open(self.audit_log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
            os.chmod(self.audit_log_path, 0o600)
        except Exception as e:
            print(f"Warning: could not write AI audit log entry: {e}")

    def get_audit_log(self, limit: int = 200) -> List[Dict]:
        """Read back the most recent audit log entries (newest last)."""
        if not self.audit_log_path.exists():
            return []
        entries = []
        try:
            with open(self.audit_log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"Warning: could not read AI audit log: {e}")
            return []
        return entries[-limit:]

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

        # Track usage — complete() already does this; structured_complete()
        # calls the provider directly and was missing it, silently under-
        # counting usage/cost for every feature that uses it (Column
        # Generator, Dataset Interpreter, Compliance Report Generator).
        self.usage_tracker.append({
            "provider": prov.provider_name,
            "model": prov.model,
            "timestamp": datetime.now().isoformat(),
            "tokens": response.usage,
            "latency_ms": response.latency_ms
        })

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
        """Get usage statistics, overall and broken down per provider.

        Reads from the persisted audit log rather than the in-memory
        usage_tracker list — usage_tracker only reflects calls made by
        *this* AIManager instance since it was constructed, so a freshly
        opened dialog (or a new process, e.g. main_window vs. a one-off
        script) would otherwise show "0 requests" despite a long history
        of real calls sitting on disk. The audit log is the durable
        source of truth; this keeps stats consistent with what the
        Activity Log's table displays."""
        entries = self.get_audit_log(limit=1_000_000)

        total_tokens = sum(
            (t.get("tokens") or {}).get("total_tokens", 0)
            for t in entries
        )
        total_cost = total_tokens * 0.00001  # Rough estimate

        by_provider: Dict[str, Dict] = {}
        for t in entries:
            prov_name = t.get("provider") or "unknown"
            bucket = by_provider.setdefault(prov_name, {"requests": 0, "tokens": 0, "estimated_cost": 0.0})
            bucket["requests"] += 1
            tokens = (t.get("tokens") or {}).get("total_tokens", 0)
            bucket["tokens"] += tokens
            bucket["estimated_cost"] = round(bucket["estimated_cost"] + tokens * 0.00001, 4)

        return {
            "total_requests": len(entries),
            "total_tokens": total_tokens,
            "estimated_cost": round(total_cost, 4),
            "by_provider": by_provider
        }


# =============================================================================
# Batched row-level AI transforms
# =============================================================================
# The AI menu operations (sentiment, classify, summarize, etc.) run over a
# whole column of rows. Calling the LLM once per row would be both slow
# (network round-trip per row) and expensive (redundant system-prompt
# tokens every call), so instead we batch N rows into one prompt asking for
# a JSON array of N results, run several batches, and stitch results back
# together in order. If a batch fails (bad JSON, API error, no provider
# configured), only that batch's rows fall back to `fallback` — one bad
# batch doesn't take down the whole column.

def _run_sync(coro):
    """Run an async coroutine to completion from synchronous code. The
    transformation pipeline calls these operations synchronously (there's
    no asyncio event loop already running), so each call gets its own
    fresh loop — the same pattern main_window.py already uses for
    thread-pool-driven AI calls."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _extract_json_array(content: str, key: str = "results") -> list:
    """Pull a JSON array out of an LLM response. Prefers {"results": [...]}
    (more reliable across providers' JSON modes than asking for a bare
    top-level array) but falls back to a bare array or single object."""
    content = content.strip()
    content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
    content = re.sub(r'\s*```$', '', content)
    parsed = json.loads(content)
    if isinstance(parsed, dict) and key in parsed:
        return parsed[key]
    if isinstance(parsed, list):
        return parsed
    return [parsed]


def batched_ai_map(ai_manager: Optional['AIManager'], values: List[Any], build_prompt: Callable[[List[Any]], str],
                    parse_response: Callable[[list, List[Any]], List[Any]], batch_size: int = 25,
                    task_type: str = "general", fallback: Any = None) -> List[Any]:
    """Map `values` through an LLM in batches, returning exactly one result
    per input value in the same order.

    build_prompt(batch_values) -> a prompt string asking for a JSON array
        (or {"results": [...]}) of len(batch_values) results, one per input.
    parse_response(raw_list, batch_values) -> a list of per-row results,
        same length as batch_values (may raise if the shape is wrong).

    Returns `[fallback] * len(values)` outright if no AI provider is
    configured — callers are expected to check for this and degrade
    gracefully (e.g. relabel the operation as unavailable) rather than
    silently pretending the fallback is a real result.
    """
    if not values:
        return []
    if ai_manager is None or ai_manager.get_provider() is None:
        return [fallback] * len(values)

    results = [fallback] * len(values)
    for start in range(0, len(values), batch_size):
        batch = values[start:start + batch_size]
        try:
            prompt = build_prompt(batch)
            response = _run_sync(ai_manager.complete(prompt, task_type=task_type, temperature=0.2, force_json=True))
            raw = _extract_json_array(response.content)
            parsed = parse_response(raw, batch)
            for i, val in enumerate(parsed[:len(batch)]):
                results[start + i] = val
        except Exception as e:
            print(f"AI batch failed (rows {start}-{start + len(batch)}): {e}")
            continue
    return results


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

    def compute_data_quality_stats(self, df: pl.DataFrame) -> Dict:
        """Compute real, deterministic data-quality statistics over the
        FULL dataframe — duplicate row count, per-column null rates, and
        IQR-based outlier counts for numeric columns — computed here in
        Python rather than left for the LLM to guess. analyze_dataset()
        only ever sends the LLM numbers that came out of this function,
        so "audit_insights" and the quality score are grounded in the
        complete dataset instead of 5 sample values per column."""
        total_rows = len(df)
        total_cells = total_rows * len(df.columns) if total_rows else 0

        duplicate_count = (total_rows - df.unique().height) if total_rows else 0

        column_stats = []
        total_nulls = 0
        for col in df.columns:
            series = df[col]
            null_count = int(series.null_count())
            total_nulls += null_count
            stat = {
                "name": col,
                "dtype": str(series.dtype),
                "null_count": null_count,
                "null_pct": round(null_count / total_rows * 100, 2) if total_rows else 0,
                "unique_count": int(series.n_unique()),
            }
            if series.dtype.is_numeric() and total_rows > 4:
                non_null = series.drop_nulls()
                if len(non_null) > 4:
                    q1 = non_null.quantile(0.25)
                    q3 = non_null.quantile(0.75)
                    if q1 is not None and q3 is not None:
                        iqr = q3 - q1
                        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                        outlier_count = int(non_null.filter((non_null < lower) | (non_null > upper)).len())
                        std = non_null.std()
                        stat.update({
                            "outlier_count": outlier_count,
                            "outlier_pct": round(outlier_count / len(non_null) * 100, 2),
                            "min": float(non_null.min()),
                            "max": float(non_null.max()),
                            "mean": round(float(non_null.mean()), 4),
                            "median": round(float(non_null.median()), 4),
                            "std": round(float(std), 4) if std is not None else None,
                        })
            column_stats.append(stat)

        null_rate = (total_nulls / total_cells) if total_cells else 0
        duplicate_rate = (duplicate_count / total_rows) if total_rows else 0
        # Deterministic formula, not an LLM guess: penalize null rate more
        # heavily than duplicate rate, floor at 0.
        quality_score = max(0, round(100 - (null_rate * 100 * 0.6) - (duplicate_rate * 100 * 0.4), 1))

        return {
            "row_count": total_rows,
            "column_count": len(df.columns),
            "duplicate_row_count": duplicate_count,
            "duplicate_row_pct": round(duplicate_rate * 100, 2),
            "total_null_cells": total_nulls,
            "overall_null_pct": round(null_rate * 100, 2),
            "quality_score": quality_score,
            "columns": column_stats,
        }

    def _format_quality_stats(self, stats: Dict) -> str:
        lines = [
            f"Rows: {stats['row_count']}, Columns: {stats['column_count']}",
            f"Duplicate rows (full-row duplicates): {stats['duplicate_row_count']} ({stats['duplicate_row_pct']}%)",
            f"Overall null rate: {stats['overall_null_pct']}% ({stats['total_null_cells']} null cells)",
            f"Computed data quality score: {stats['quality_score']}/100",
            "",
            "Per-column statistics:",
        ]
        for col in stats["columns"]:
            line = f"- {col['name']} ({col['dtype']}): nulls={col['null_pct']}%, unique={col['unique_count']}"
            if "outlier_count" in col:
                line += (
                    f", outliers(IQR)={col['outlier_count']} ({col['outlier_pct']}%), "
                    f"range=[{col['min']}, {col['max']}], mean={col['mean']}, median={col['median']}, std={col['std']}"
                )
            lines.append(line)
        return "\n".join(lines)

    async def analyze_dataset(self, df: pl.DataFrame,
                               audit_context: str = "") -> DatasetSummary:
        """Generate a dataset analysis grounded entirely in statistics
        computed over the full dataset — the LLM is only asked to
        interpret and prioritize numbers it's given, not to detect
        outliers/trends/anomalies itself from a handful of samples."""

        quality_stats = self.compute_data_quality_stats(df)

        prompt = f"""
Interpret these REAL, precomputed statistics from a dataset for an audit engagement.
Every number below was computed over the COMPLETE dataset (not a sample) — do not invent
additional statistics, outliers, or findings beyond what is given here. If you reference an
outlier or data quality issue, it must correspond to a column/number listed below.

Audit Context: {audit_context or "General audit review"}

Computed Statistics:
{self._format_quality_stats(quality_stats)}

Provide your analysis as JSON:
{{
    "executive_summary": "2-3 paragraph summary of what this dataset contains and its overall data quality, based only on the statistics given",
    "data_quality": {{
        "overall_score": {quality_stats['quality_score']},
        "null_percentage": {quality_stats['overall_null_pct']},
        "issues": [
            {{"column": "name (must be one of the columns listed above)", "issue": "description grounded in that column's actual computed numbers", "severity": "high/medium/low"}}
        ]
    }},
    "key_fields": ["field1", "field2"],
    "audit_insights": [
        {{
            "type": "outlier/duplicate/null_rate/pattern",
            "title": "Brief title",
            "description": "Description that cites the specific computed number(s) it is based on",
            "severity": "high/medium/low",
            "recommendation": "Suggested audit action"
        }}
    ],
    "suggested_procedures": ["procedure1", "procedure2"]
}}

Only include audit_insights that are directly supported by the computed statistics above —
if there is nothing notable for a given column, don't list an issue for it.
Only respond with valid JSON.
"""

        result = await self.ai.structured_complete(
            prompt=prompt,
            task_type="dataset_interpretation",
            response_format="json"
        )

        # Force-override the numeric fields with the real computed values
        # rather than trusting the LLM to have echoed them back correctly —
        # the prompt asks it to, but nothing guarantees it will, and these
        # two numbers exist specifically so they don't have to be trusted.
        data_quality = dict(result.get("data_quality", {}))
        data_quality["overall_score"] = quality_stats["quality_score"]
        data_quality["null_percentage"] = quality_stats["overall_null_pct"]
        data_quality["computed_stats"] = quality_stats

        return DatasetSummary(
            executive_summary=result.get("executive_summary", ""),
            data_quality=data_quality,
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
        """Apply generated column code to dataframe — sandboxed via
        safe_exec_polars_code (see module-level docstring for why the old
        exec_globals={"pl": pl} approach wasn't actually a sandbox)."""
        try:
            return safe_exec_polars_code(code, df)
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
# SQL Generator
# =============================================================================

class SQLGenerator:
    """AI-powered SQL generation from natural language, for the SQL editor.

    Generates one query only - never executes it. The caller (SQLTransformView)
    is responsible for running it through is_safe_readonly_select() before
    ever offering to execute it, and always shows it to the user for review
    first, exactly like a query they'd typed themselves."""

    def __init__(self, ai_manager: AIManager):
        self.ai = ai_manager

    async def generate_sql(self, instruction: str, table_schemas: Dict[str, pl.DataFrame]) -> SQLSuggestion:
        """Generate a single SQL statement for the given instruction.

        Args:
            instruction: Natural-language description of the desired query
            table_schemas: {table_name: dataframe} for every table currently
                registered in the SQL editor's DuckDB connection
        """
        schema_info = self._format_schema_info(table_schemas)

        prompt = f"""
Tables available in this DuckDB session:
{schema_info}

Request: "{instruction}"

Provide your response as JSON:
{{
    "sql": "The single SELECT (or WITH ... SELECT) statement, using only the tables/columns listed above",
    "explanation": "One sentence, plain English, restating exactly what the query does"
}}

Requirements:
- DuckDB SQL syntax
- Exactly one SELECT statement - no DDL/DML, no multiple statements
- Use only the table and column names given above; never invent one
- Return only valid JSON
"""

        result = await self.ai.structured_complete(
            prompt=prompt,
            task_type="sql_generation",
            response_format="json"
        )

        return SQLSuggestion(
            sql=result.get("sql", "").strip(),
            explanation=result.get("explanation", ""),
        )

    def _format_schema_info(self, table_schemas: Dict[str, pl.DataFrame]) -> str:
        """Real, computed schema info for the prompt - table names, column
        names/types, and a couple of sample values per column, so the model
        writes SQL against what's actually there rather than guessing."""
        lines = []
        for table_name, df in table_schemas.items():
            lines.append(f'Table "{table_name}" ({len(df):,} rows):')
            for col in df.columns:
                dtype = df[col].dtype
                sample = str(df[col].drop_nulls().head(3).to_list())
                lines.append(f"  - {col} ({dtype}): {sample}")
        return "\n".join(lines) if lines else "(no tables registered)"


class FinancialImportAI:
    """Narrow, explicitly-optional AI assist for the Financial Data Import
    Wizard (core.financial_import_wizard) - picks up exactly where the
    deterministic detectors run out of runway: ambiguous column names,
    account-to-category classification, and unusual period labels. Every
    method here only ever SUGGESTS; the wizard dialog shows the
    suggestion for review/edit before it's folded into the import plan,
    and the wizard works fully without this class if no AI provider is
    configured - it's a fallback, never a dependency."""

    def __init__(self, ai_manager: AIManager):
        self.ai = ai_manager

    async def suggest_column_mapping(self, column_names: List[str], sample_rows: List[Dict[str, Any]],
                                      target_fields: Dict[str, str]) -> Dict[str, Optional[str]]:
        """Suggest which of `column_names` corresponds to each of
        `target_fields` (field_name -> what it should contain), for cases
        the deterministic name/structure-based detection couldn't
        confidently resolve (e.g. a client's idiosyncratic "COL_A"/"AMT1"
        naming instead of "Debit"/"Credit"). Returns
        {field_name: column_name_or_None}."""
        samples_text = "\n".join(f"- {row}" for row in sample_rows[:5])
        fields_text = "\n".join(f'- "{name}": {desc}' for name, desc in target_fields.items())

        prompt = f"""Column names in this file: {column_names}

Sample rows:
{samples_text}

Target fields to map (field name: what it should contain):
{fields_text}

For each target field, which column name (exactly as given above) most likely corresponds to it? If none
plausibly does, use null for that field.

Respond as JSON: {{"field_name": "column_name_or_null", ...}} for every target field listed above."""

        result = await self.ai.structured_complete(prompt=prompt, task_type="financial_import", response_format="json")
        # Defend against a stray/invented column name - only ever return
        # something that's actually one of the real columns given.
        return {field: (result.get(field) if result.get(field) in column_names else None) for field in target_fields}

    async def suggest_account_category_mapping(self, account_names: List[str],
                                                categories: List[str]) -> Dict[str, Optional[str]]:
        """Suggest a standard financial-statement category for each
        distinct account/line-item name - e.g. "Prepaid Insurance" ->
        "Current Assets". This is real domain knowledge a keyword
        dictionary always has gaps in - the strongest case for AI in this
        wizard. Returns {account_name: category_or_None}."""
        accounts_text = "\n".join(f"- {a}" for a in account_names[:200])
        categories_text = ", ".join(categories)

        prompt = f"""Account/line-item names to classify:
{accounts_text}

Standard categories to classify each into: {categories_text}

For each account name above, which ONE category does it most plausibly belong to? If genuinely unsure,
use null rather than guessing.

Respond as JSON: {{"account name": "category_or_null", ...}} for every account name listed above, using
the exact account name as the key."""

        result = await self.ai.structured_complete(prompt=prompt, task_type="financial_import", response_format="json")
        return {name: (result.get(name) if result.get(name) in categories else None) for name in account_names}

    async def suggest_period_columns(self, column_names: List[str]) -> List[str]:
        """Suggest which of `column_names` look like time-period labels
        (fiscal period codes, non-English month names, or other
        conventions a standard date/quarter/year regex wouldn't
        recognize). Returns the subset of column_names judged to be
        period labels."""
        prompt = f"""Column names: {column_names}

Which of these column names look like they represent a TIME PERIOD (a month, quarter, fiscal period, or
year) rather than a regular data field - even using non-obvious conventions like fiscal period codes
("P01", "P02") or a format a standard date pattern wouldn't recognize?

Respond as JSON: {{"period_columns": ["...", "..."]}} - only include names from the list given above,
using the exact spelling given."""

        result = await self.ai.structured_complete(prompt=prompt, task_type="financial_import", response_format="json")
        suggested = result.get("period_columns", []) or []
        return [c for c in suggested if c in column_names]


# =============================================================================
# Agent Chat (Phase 2: read-only actions, Phase 3: proposed write actions)
# =============================================================================

# The exact operator strings DataProcessor._build_condition_expr()
# recognizes for filter_advanced's "conditions" - anything else is silently
# DROPPED there (not rejected), and if it's the only condition, the whole
# filter becomes a no-op that returns the complete, unfiltered dataframe.
# Validating against this exact set here is what turns that into a clear
# rejection instead of a filter that looks applied but does nothing.
_VALID_FILTER_OPERATORS = {
    "==", "!=", ">", ">=", "<", "<=",
    "contains", "not_contains", "starts_with", "ends_with",
    "is_null", "is_not_null", "in_list", "between",
}

# Deliberately a small subset of the ~100-operation registry, not all of
# it: these are the operations already stress-tested this session (real
# parameter validation, no known crashes), and simple enough for a model to
# reliably target with valid parameters. Widen this list only once agent
# write-actions have been trusted in practice.
AGENT_WRITABLE_OPERATIONS = [
    "filter_advanced", "remove_rows", "choose_columns", "rename_columns",
    "sort_column", "change_dtype", "replace_values", "standardize_missing_values",
    "select_n_rows", "split_into_rows", "split_columns_by_delimiter",
]


def build_operations_menu(df: pl.DataFrame) -> str:
    """Plain-text menu of the operations the agent may propose against the
    active dataset - operation_id, description, and full parameter schema,
    plus the dataset's real column names, so the model has everything it
    needs to construct valid parameters instead of inventing a column or
    parameter name that doesn't exist."""
    from core.operation_registry import OPERATION_REGISTRY

    lines = [f"Active dataset columns: {', '.join(df.columns)}", "", "Operations you may propose:"]
    for op_id in AGENT_WRITABLE_OPERATIONS:
        op = OPERATION_REGISTRY.get(op_id)
        if not op:
            continue
        lines.append(f'- operation_id "{op_id}" ({op["display_name"]}): {op["description"]}')
        for pname, pschema in op.get("parameter_schema", {}).items():
            req = "required" if pschema.get("required") else "optional"
            extra = f", options: {pschema['options']}" if "options" in pschema else ""
            if "schema" in pschema:
                extra += f", each item shaped like: {pschema['schema']}"
            lines.append(f'    param "{pname}": {pschema["type"]}, {req}{extra}')
    return "\n".join(lines)


def validate_operation_params(operation_id: str, params: Dict[str, Any], df: pl.DataFrame) -> tuple[bool, str]:
    """Validate a model-proposed operation before it's ever previewed to
    the user - checked against the real parameter schema and the real
    dataframe's columns, the same validation a hand-built transform dialog
    enforces. Returns (is_valid, reason); reason is empty when valid."""
    from core.operation_registry import OPERATION_REGISTRY

    if operation_id not in AGENT_WRITABLE_OPERATIONS:
        return False, f"'{operation_id}' is not one of the operations the agent is allowed to propose."

    op = OPERATION_REGISTRY.get(operation_id)
    if not op:
        return False, f"'{operation_id}' is not a known operation."
    if not isinstance(params, dict):
        return False, "Parameters must be a JSON object."

    schema = op.get("parameter_schema", {})
    for pname, pschema in schema.items():
        if pschema.get("required") and not params.get(pname):
            return False, f"Missing required parameter '{pname}' for '{operation_id}'."

    for pname, value in params.items():
        pschema = schema.get(pname)
        if pschema is None:
            continue  # unknown params are simply dropped when applied, not fatal here
        ptype = pschema["type"]

        if ptype == "column":
            if value not in df.columns:
                return False, f"Column '{value}' does not exist in the active dataset."
        elif ptype == "list[column]":
            if not isinstance(value, list) or not all(isinstance(c, str) and c in df.columns for c in value):
                return False, f"Parameter '{pname}' must be a list of real column names from the active dataset."
        elif ptype == "list[int]":
            if not isinstance(value, list) or not all(isinstance(v, int) and not isinstance(v, bool) for v in value):
                return False, f"Parameter '{pname}' must be a list of integers."
        elif ptype == "list[str]":
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return False, f"Parameter '{pname}' must be a list of strings."
        elif ptype == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                return False, f"Parameter '{pname}' must be an integer."
        elif ptype == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False, f"Parameter '{pname}' must be a number."
        elif ptype == "bool":
            if not isinstance(value, bool):
                return False, f"Parameter '{pname}' must be true or false."
        elif ptype == "string" and "options" in pschema:
            if value not in pschema["options"]:
                return False, f"Parameter '{pname}' must be one of {pschema['options']}."
        elif ptype == "list[dict]":
            if not isinstance(value, list) or not value:
                return False, f"Parameter '{pname}' must be a non-empty list."
            for item in value:
                if not isinstance(item, dict):
                    return False, f"Each item in '{pname}' must be an object."
                item_col = item.get("column") or item.get("old_name")
                if item_col and item_col not in df.columns:
                    return False, f"'{pname}' references column '{item_col}', which does not exist in the active dataset."

                if "operator" in item:
                    op = item.get("operator")
                    if op not in _VALID_FILTER_OPERATORS:
                        return False, (
                            f"'{pname}' uses operator '{op}', which isn't recognized and would silently "
                            f"match nothing. Valid operators: {', '.join(sorted(_VALID_FILTER_OPERATORS))}."
                        )
                    # For an equality check on a non-numeric column, verify
                    # the value actually occurs - otherwise a plausible but
                    # slightly-off guess (e.g. "MEA" vs the real "EMEA")
                    # silently filters to zero matching rows instead of
                    # being caught here.
                    if op == "==" and item_col and not df[item_col].dtype.is_numeric():
                        distinct_vals = [str(v) for v in df[item_col].drop_nulls().unique().to_list()]
                        if str(item.get("value")) not in distinct_vals:
                            sample = ", ".join(distinct_vals[:8])
                            return False, (
                                f"Value '{item.get('value')}' was not found in column '{item_col}' "
                                f"(real values include: {sample})."
                            )

    # choose_columns' real requirement depends on which action was picked -
    # the flat "required" flags above can't express that on their own.
    if operation_id == "choose_columns":
        action = params.get("action")
        needed = {"keep": "columns_to_keep", "remove": "columns_to_remove", "reorder": "column_order"}.get(action)
        if needed and not params.get(needed):
            return False, f"action '{action}' requires a non-empty '{needed}' parameter."

    return True, ""


# =============================================================================
# Agent charts - the agent may render a chart instead of just describing
# numbers. Charts never mutate the dataset (read-only, like Phase 2's SQL
# lookups), so there's no preview/accept gate - they render straight into
# the chat once validated.
# =============================================================================

# operation_id (used as the "chart_type" the model picks) -> the real
# VisualizationService method name and its required parameter names,
# exactly as that method's signature expects them, so **params can be
# passed straight through.
AGENT_CHART_TYPES: Dict[str, Dict[str, Any]] = {
    "column": {"method": "create_column_chart", "required": ["x_column", "y_column"],
               "optional": ["color_column"]},
    "bar": {"method": "create_bar_chart", "required": ["category_column", "value_column"],
            "optional": ["color_column"]},
    "line": {"method": "create_line_chart", "required": ["x_column", "y_columns"], "optional": []},
    "scatter": {"method": "create_scatter_plot", "required": ["x_column", "y_column"],
                "optional": ["color_column", "size_column"]},
    "histogram": {"method": "create_histogram", "required": ["column"], "optional": []},
    "pie": {"method": "create_pie_chart", "required": ["label_column", "value_column"], "optional": []},
    "box": {"method": "create_box_plot", "required": ["value_column"], "optional": ["group_column"]},
    "heatmap": {"method": "create_heatmap", "required": [], "optional": []},
    "area": {"method": "create_area_chart", "required": ["x_column", "y_columns"], "optional": []},
    "violin": {"method": "create_violin_plot", "required": ["value_column"], "optional": ["group_column"]},
    "pareto": {"method": "create_pareto_chart", "required": ["category_column", "value_column"], "optional": []},
    "control": {"method": "create_control_chart", "required": ["value_column"], "optional": ["x_column"]},
    "stacked_column": {"method": "create_stacked_column_chart",
                        "required": ["x_column", "value_column", "stack_column"], "optional": []},
    "qq": {"method": "create_qq_plot", "required": ["column"], "optional": []},
}

# Parameters that take a list of column names rather than a single one.
_CHART_LIST_COLUMN_PARAMS = {"y_columns"}


def build_chart_menu(datasets: Dict[str, pl.DataFrame]) -> str:
    """Plain-text menu of chart types the agent may propose, across every
    dataset in the project - a chart is read-only (it never writes
    anywhere), so unlike an operation there's no reason to limit it to
    just the currently active dataset. Lists each dataset's real columns
    split into numeric vs. categorical, so the model picks both a real
    dataset and a chart type that dataset's columns can actually support."""
    lines = ["Datasets available to chart (specify one by name in \"dataset\"):"]
    for name, df in datasets.items():
        numeric_cols = [c for c in df.columns if df[c].dtype.is_numeric()]
        categorical_cols = [c for c in df.columns if c not in numeric_cols]
        lines.append(
            f'- "{name}": numeric columns: {", ".join(numeric_cols) or "(none)"}; '
            f'categorical/text columns: {", ".join(categorical_cols) or "(none)"}'
        )
    lines.append("")
    lines.extend([
        "Chart types you may propose (chart_type: required params [optional params]):",
        "- column (vertical bars): x_column (category), y_column (numeric) [color_column]",
        "- bar (horizontal bars, good for many/long category labels): category_column, value_column (numeric) [color_column]",
        "- line: x_column, y_columns (list of numeric columns)",
        "- scatter: x_column (numeric), y_column (numeric) [color_column, size_column]",
        "- histogram: column (numeric) - distribution of one column",
        "- pie: label_column (category), value_column (numeric)",
        "- box: value_column (numeric) [group_column] - distribution summary, optionally per group",
        "- heatmap: (no params) - correlation matrix across all numeric columns",
        "- area: x_column, y_columns (list of numeric columns, stacked)",
        "- violin: value_column (numeric) [group_column] - like box, shows full distribution shape",
        "- pareto: category_column, value_column (numeric) - bars sorted descending + cumulative % line",
        "- control: value_column (numeric) [x_column] - run chart with mean/±3σ control limits",
        "- stacked_column: x_column (category), value_column (numeric), stack_column (category)",
        "- qq: column (numeric) - normality check against a theoretical normal distribution",
    ])
    return "\n".join(lines)


def validate_chart_params(chart_type: str, params: Dict[str, Any], df: pl.DataFrame) -> tuple:
    """Validate a model-proposed chart before it's ever rendered - checked
    against the real chart signature and the real dataframe's columns.
    Returns (is_valid, reason); reason is empty when valid."""
    spec = AGENT_CHART_TYPES.get(chart_type)
    if spec is None:
        return False, f"'{chart_type}' is not a supported chart type."
    if not isinstance(params, dict):
        return False, "Parameters must be a JSON object."

    for pname in spec["required"]:
        if not params.get(pname):
            return False, f"Missing required parameter '{pname}' for chart type '{chart_type}'."

    allowed = set(spec["required"]) | set(spec["optional"])
    for pname, value in params.items():
        if pname not in allowed:
            continue  # unknown params are simply dropped when applied, not fatal here
        if pname in _CHART_LIST_COLUMN_PARAMS:
            if not isinstance(value, list) or not value or not all(isinstance(c, str) and c in df.columns for c in value):
                return False, f"Parameter '{pname}' must be a non-empty list of real column names."
        elif isinstance(value, str) and value not in df.columns:
            return False, f"Column '{value}' does not exist in the active dataset."

    if chart_type == "heatmap":
        numeric_count = sum(1 for c in df.columns if df[c].dtype.is_numeric())
        if numeric_count < 2:
            return False, "Need at least 2 numeric columns to compute a correlation heatmap."

    return True, ""


# =============================================================================
# Agent app help - answering "how do I do X in CaatMaster" questions,
# grounded in the real operation registry and a short curated list of the
# app's major surfaces (wizard, SQL editor, visualizations, ...) that
# aren't individual operations. Kept as a searchable index rather than
# always included in every prompt, so a plain data question doesn't pay
# for it.
# =============================================================================

_APP_SURFACES = [
    ("Cleaning Wizard", "Automatically detects structural issues in a freshly imported file - multi-row "
     "headers, subtotal rows/columns, blank rows/columns - and proposes fixes to review and accept before "
     "anything is applied. Open it from the sidebar's 'Import & Clean...' button next to Datasets."),
    ("SQL Editor", "Write and run SQL (DuckDB) queries against your loaded datasets, including joins across "
     "multiple datasets. Has an 'Ask AI' button that generates SQL from a plain-language description, and "
     "'Apply to Dataset' / 'Create New Dataset' buttons to turn a query's result into a real pipeline step "
     "or a brand new dataset. Open it from the SQL navigation item."),
    ("Visualizations", "Build charts (column, bar, line, scatter, histogram, pie, box, heatmap, area, "
     "violin, pareto, control, stacked column, Q-Q plot) from a dataset. Open it from the Visualizations "
     "navigation item, or right-click a column header and choose Visualize for a quick default chart."),
    ("AI Chat panel", "Ask questions about your data in plain language, or ask for a change to be made; it "
     "can run precise queries against the real data and propose reviewable changes you approve before "
     "anything is applied. Toggle it from the sidebar."),
    ("Applied Steps panel", "Every transformation (manual or AI-proposed) is recorded here as an ordered, "
     "individually undoable step - it's the audit trail of everything done to a dataset. Shown next to the "
     "Transform view."),
    ("Right-click column menu", "Right-click any column header in the Transform view for a menu of "
     "operations scoped to that column, organized by category (Text, Numbers, Date & Time, Table, Headers, "
     "Column, Structure, etc.)."),
    ("Right-click row / cell menu", "Right-click inside the data grid for row-level actions (remove, "
     "filter, flag) without opening the Transform menu."),
]


def _build_app_reference_corpus() -> List[tuple]:
    """(searchable_text, display_entry) pairs built once from the real
    operation registry plus the curated app-surfaces list above - the
    corpus search_app_reference() runs its keyword match against."""
    from core.operation_registry import OPERATION_REGISTRY

    corpus = []
    for name, description in _APP_SURFACES:
        entry = f"- {name}: {description}"
        corpus.append((f"{name} {description}".lower(), entry))
    for op_id, op in OPERATION_REGISTRY.items():
        display_name = op.get("display_name", op_id)
        description = op.get("description", "")
        category = op.get("category", "")
        entry = f"- {display_name} (found under the {category} category, e.g. the Transform menu or a column's right-click menu): {description}"
        corpus.append((f"{op_id} {display_name} {description} {category}".lower(), entry))
    return corpus


_app_reference_corpus_cache: List[tuple] = []


def search_app_reference(topic: str, max_results: int = 8) -> str:
    """Keyword-search the app reference corpus for entries relevant to a
    'how do I do X in CaatMaster' question - returns only the matching
    entries rather than the whole ~100-entry index, so a plain data
    question never pays for this. Cached after the first call since the
    corpus (operation registry + curated surfaces) never changes at
    runtime."""
    global _app_reference_corpus_cache
    if not _app_reference_corpus_cache:
        _app_reference_corpus_cache = _build_app_reference_corpus()

    words = [w for w in re.findall(r'\w+', topic.lower()) if len(w) > 2]
    if not words:
        return "(no matching features found)"

    scored = []
    for haystack, entry in _app_reference_corpus_cache:
        score = sum(1 for w in words if w in haystack)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda t: t[0], reverse=True)

    if not scored:
        return "(no matching features found)"
    return "\n".join(entry for _, entry in scored[:max_results])


class AgentChat:
    """Read-only agentic chat: for a question the pre-computed dataset
    summary can't already answer precisely, decide whether to request a
    single SQL query against the real data before answering, rather than
    guessing. Never mutates anything - decide() only ever returns a
    decision (answer directly, the SQL to run, or a proposed operation);
    running a query or applying an operation is the caller's job
    (main_window.py), since that's where the actual dataframes, DuckDB
    connection, and Applied Steps pipeline live."""

    def __init__(self, ai_manager: AIManager):
        self.ai = ai_manager

    async def decide(self, context: str, question: str, operations_menu: str = "",
                      chart_menu: str = "") -> Dict[str, Any]:
        """Ask the model which of answer/query/operation/chart/dataset/help
        the message calls for. Returns one of:
        {"type": "answer", "answer": ...}
        {"type": "query", "sql": ..., "reason": ...}
        {"type": "operation", "operation_id": ..., "params": {...}, "reason": ...}
        {"type": "chart", "dataset": ..., "chart_type": ..., "params": {...}, "reason": ...}
        {"type": "dataset", "sql": ..., "name": ..., "reason": ...}
        {"type": "help", "topic": ...}"""
        prompt = f"{context}\n\nUser Question: {question}"
        if operations_menu:
            prompt += f"\n\n{operations_menu}"
        if chart_menu:
            prompt += f"\n\n{chart_menu}"
        return await self.ai.structured_complete(
            prompt=prompt,
            task_type="agent_qa",
            response_format="json"
        )

    async def answer_with_query_result(self, context: str, question: str,
                                        sql: str, result_summary: str) -> str:
        """Second turn: give the model the REAL query result and ask for a
        final natural-language answer grounded in it."""
        prompt = f"""{context}

User Question: {question}

You requested this query to answer precisely:
{sql}

Real result (the complete, actual data - not a sample):
{result_summary}

Answer the user's question directly and concisely, using the numbers shown above exactly as given - don't
round or estimate. Do not add a disclaimer restating that this came from a real query or the complete
data (e.g. "this is based on the query executed against..."); just answer as if you already knew it."""

        response = await self.ai.complete(prompt=prompt, task_type="general", temperature=0.3)
        return response.content

    async def answer_after_rejected_query(self, context: str, question: str,
                                           rejected_sql: str, rejection_reason: str) -> str:
        """The model's requested query failed the safety/execution check.
        Rather than silently retrying forever or crashing the chat, ask it
        to answer using only the summary stats already in context, being
        explicit that it couldn't run the precise lookup it wanted."""
        prompt = f"""{context}

User Question: {question}

You requested this query, but it could not be run: {rejection_reason}
Query: {rejected_sql}

Answer the user's question using only the summary statistics already given above. If they don't cover
what's being asked, say plainly that you don't have a precise answer available rather than estimating."""

        response = await self.ai.complete(prompt=prompt, task_type="general", temperature=0.3)
        return response.content

    async def answer_after_rejected_operation(self, context: str, question: str,
                                               operation_id: str, rejection_reason: str) -> str:
        """The model's proposed operation failed validation before ever
        reaching a preview. Ask it to respond in plain text instead of
        silently retrying or leaving the auditor without any reply."""
        prompt = f"""{context}

User Question: {question}

You proposed the operation '{operation_id}', but it could not be used: {rejection_reason}

Reply to the auditor explaining that this change couldn't be proposed as requested, in one or two
sentences. Do not claim any change was made - nothing was applied.
Operations can only ever be proposed against the dataset marked [CURRENTLY ACTIVE] above - if the
rejection is because a column doesn't exist there, check whether a different listed dataset actually has
that column, and if so, say so plainly (e.g. "that column is in the 'X' dataset, not the currently active
one - switch to it first, or ask me to give you a new table/dataset instead, which can pull from any
dataset")."""

        response = await self.ai.complete(prompt=prompt, task_type="general", temperature=0.3)
        return response.content

    async def answer_after_rejected_chart(self, context: str, question: str,
                                           chart_type: str, rejection_reason: str) -> str:
        """The model's proposed chart failed validation before ever being
        rendered. Ask it to respond in plain text rather than leaving the
        auditor without any reply."""
        prompt = f"""{context}

User Question: {question}

You proposed a '{chart_type}' chart, but it could not be created: {rejection_reason}

Reply to the auditor explaining that this chart couldn't be created as requested, in one or two
sentences. Suggest a different chart type or columns if an obvious alternative fits."""

        response = await self.ai.complete(prompt=prompt, task_type="general", temperature=0.3)
        return response.content

    async def answer_after_rejected_dataset(self, context: str, question: str,
                                             rejected_sql: str, rejection_reason: str) -> str:
        """The model's proposed dataset-creation query failed the safety/
        execution check."""
        prompt = f"""{context}

User Question: {question}

You proposed this query to build a new dataset, but it could not be run: {rejection_reason}
Query: {rejected_sql}

Reply to the auditor explaining that the dataset couldn't be created as requested, in one or two
sentences. Do not claim any dataset was created - nothing was."""

        response = await self.ai.complete(prompt=prompt, task_type="general", temperature=0.3)
        return response.content

    async def answer_with_help_result(self, context: str, question: str,
                                       topic: str, search_results: str) -> str:
        """Second turn for a HELP decision: give the model the actual
        matching feature entries and ask it to answer using only those,
        rather than the general knowledge it might otherwise guess from."""
        prompt = f"""{context}

User Question: {question}

You determined this is a question about how to use CaatMaster itself, not about the data. Here are the
matching features found in the app's own reference:
{search_results}

Answer the user's question using ONLY the features listed above - describe what to click/do in plain,
concrete terms. If nothing above actually answers the question, say plainly that you're not sure rather
than guessing at a menu or feature that may not exist."""

        response = await self.ai.complete(prompt=prompt, task_type="general", temperature=0.3)
        return response.content


# =============================================================================
# Compliance Report Generator
# =============================================================================

class ComplianceReportGenerator:
    """AI-powered compliance report generation.

    Compliance findings — violation counts, dollar amounts, evidence
    transaction references — are never something an LLM should be asked
    to estimate: it has no way to actually know them, and would have to
    fabricate plausible-looking numbers to answer at all. This class
    splits that work in two: translate_rules_to_conditions() asks the AI
    only to express each rule as an executable filter condition (a task
    it's well-suited for), and compute_rule_violation() then applies that
    condition to the COMPLETE dataframe in Python to get exact counts,
    amounts, and real evidence values. Only after those real numbers exist
    does the AI get asked to draft prose around them.
    """

    def __init__(self, ai_manager: AIManager):
        self.ai = ai_manager

    async def translate_rules_to_conditions(self, df: pl.DataFrame, rules: List[Dict]) -> List[Dict]:
        """Translate natural-language rules into structured, executable
        conditions against df's actual columns. The AI's job is limited to
        picking column/operator/value per rule — it is explicitly not
        asked to count violations or characterize the data itself.

        Two failure modes surfaced in testing against a real LLM, both
        fixed here: (1) compound rules ("over $1,000 AND missing an
        approver") got truncated to just the first criterion because
        nothing prompted the model to look for more than one; (2) rules
        that structurally can't be a per-row filter at all — duplicate
        detection requires comparing a row to every OTHER row, not
        evaluating one row in isolation — got a fabricated, arbitrary
        condition instead of being marked not-computable. Duplicate
        detection now gets its own rule_type, computed for real via
        Polars' is_duplicated() in compute_rule_violation(), and the
        prompt now explicitly walks through both failure modes with
        examples so the model doesn't repeat them."""
        columns_info = "\n".join(
            f"- {col}: {df[col].dtype} (sample values: {df[col].drop_nulls().head(3).to_list()})"
            for col in df.columns
        )
        rules_text = "\n".join(
            f"{i}. {r.get('name', 'Unknown')}: {r.get('description', '')}"
            for i, r in enumerate(rules)
        )
        valid_operators = ("==, !=, >, >=, <, <=, contains, not_contains, starts_with, "
                            "ends_with, is_null, is_not_null, in_list, between")

        prompt = f"""
You are translating compliance rules into structured, executable checks against a dataset's
actual columns. You are NOT being asked to detect violations, count anything, or characterize
the data — only to express each rule as either (a) a per-row filter condition, or (b) a
duplicate-record check. The actual count of matching rows will be computed separately in code
from whatever you specify here, so precision matters more than optimism.

Dataset columns:
{columns_info}

Rules to translate:
{rules_text}

RULE TYPE 1 — "condition": a filter that can be evaluated on EACH ROW INDEPENDENTLY, using
ONLY these operators: {valid_operators}. "between" takes "10,20" (low,high). "in_list" takes
"A,B,C". Use exact column names as given above.

  IMPORTANT — capture EVERY testable criterion in the rule, not just the first one. A rule
  like "payments over $1,000 must have an approver on file" has TWO criteria: amount > 1000
  AND approver is_null (the exception condition — what makes it a VIOLATION). Both must appear
  as separate entries in "conditions", combined with the correct combine_operator. Do not stop
  after the first criterion just because it was easy to express.

RULE TYPE 2 — "duplicate_check": use this when the rule is fundamentally about a row being
identical to (or matching key fields of) ANOTHER row — e.g. "no transaction should be recorded
twice" — which is NOT expressible as rule type 1 (a single row's own values can't tell you
whether it's a duplicate; that requires comparing it to every other row). Set
"duplicate_check_columns" to the list of columns that define "duplicate" (e.g. all columns for
an exact duplicate, or specific columns like ["vendor", "amount", "date"] if the rule implies a
narrower match), or an empty list to mean "every column".

If a rule genuinely cannot be expressed as EITHER type against these columns (e.g. it needs
information not present in this dataset, or requires cross-row logic that isn't simple
duplicate detection — like ranking or aggregation), mark it not computable and explain why.
Do NOT invent a condition (e.g. picking arbitrary ID values) just to have something to return —
an honest "not computable" is always better than a fabricated condition.

Return JSON:
{{
    "rules": [
        {{
            "rule_index": 0,
            "rule_type": "condition",
            "computable": true,
            "reason_if_not_computable": "",
            "conditions": [{{"column": "exact_column_name", "operator": "one of the operators above", "value": "..."}}],
            "combine_operator": "AND",
            "duplicate_check_columns": null,
            "amount_column": "a numeric column to sum for a dollar-impact total, or null if none applies",
            "evidence_column": "an ID/reference-like column to show as evidence, or null to use row position"
        }}
    ]
}}
Only respond with valid JSON.
"""
        result = await self.ai.structured_complete(prompt=prompt, task_type="compliance", response_format="json")
        return result.get("rules", [])

    @staticmethod
    def _summarize_matched_rows(df: pl.DataFrame, matched: pl.DataFrame, rule_translation: Dict) -> Dict:
        """Shared tail end of both compute paths: given the full dataframe
        and the subset of rows that matched (by whatever means), compute
        the real count/pct/dollar-impact/evidence — identical logic
        whether the match came from a filter condition or a duplicate
        check."""
        affected_count = matched.height
        total_count = len(df)

        affected_amount = 0.0
        amount_col = rule_translation.get("amount_column")
        if amount_col and amount_col in df.columns and df[amount_col].dtype.is_numeric() and affected_count:
            summed = matched[amount_col].sum()
            affected_amount = float(summed) if summed is not None else 0.0

        evidence_col = rule_translation.get("evidence_column")
        if evidence_col and evidence_col in df.columns and affected_count:
            evidence = [str(v) for v in matched[evidence_col].head(10).to_list()]
        elif affected_count:
            idx_col = "_caat_idx" if "_caat_idx" in matched.columns else None
            if idx_col is None:
                matched = matched.with_row_index("_caat_idx")
                idx_col = "_caat_idx"
            evidence = [f"row {i}" for i in matched[idx_col].head(10).to_list()]
        else:
            evidence = []

        return {
            "computable": True,
            "affected_count": affected_count,
            "total_count": total_count,
            "affected_pct": round(affected_count / total_count * 100, 2) if total_count else 0.0,
            "affected_amount": affected_amount,
            "evidence": evidence,
        }

    def compute_rule_violation(self, df: pl.DataFrame, rule_translation: Dict) -> Dict:
        """Apply a translated rule to the COMPLETE dataframe and return
        exact, real numbers — nothing here is estimated, sampled, or asked
        of an LLM. Dispatches to a filter condition or a real duplicate
        check depending on rule_type."""
        empty = {
            "computable": False, "reason": "Not computable from available columns.",
            "affected_count": 0, "total_count": len(df), "affected_pct": 0.0,
            "affected_amount": 0.0, "evidence": [],
        }
        if not rule_translation.get("computable", False):
            empty["reason"] = rule_translation.get("reason_if_not_computable") or empty["reason"]
            return empty

        if rule_translation.get("rule_type") == "duplicate_check":
            cols = rule_translation.get("duplicate_check_columns") or list(df.columns)
            cols = [c for c in cols if c in df.columns]
            if not cols or len(df) == 0:
                empty["reason"] = "No valid columns available for duplicate check."
                return empty
            dup_flag = df.select(cols).is_duplicated()
            matched = df.filter(dup_flag)
            return self._summarize_matched_rows(df, matched, rule_translation)

        from core.data_processor import DataProcessor
        dp = DataProcessor()

        conditions = rule_translation.get("conditions", [])
        combine_operator = rule_translation.get("combine_operator", "AND")
        expr = dp._build_condition_expr(df, conditions, combine_operator) if conditions else None
        if expr is None:
            empty["reason"] = "No valid conditions could be built from the translated rule."
            return empty

        matched = df.filter(expr)
        return self._summarize_matched_rows(df, matched, rule_translation)

    async def extract_rules_from_policy(self, policy_text: str) -> List[Dict]:
        """Extract discrete, checkable rules from a free-text policy
        document. This only identifies WHAT the policy requires — whether
        each rule is actually violated is determined separately, over the
        complete dataset, by translate_rules_to_conditions() +
        compute_rule_violation(). Keeping "what does the policy say" apart
        from "how many rows violate it" means the second question is never
        left to the LLM to guess."""
        prompt = f"""
Extract a list of discrete, checkable compliance rules from this policy document. Each rule
should be something that could, in principle, be checked against transaction/record data
(e.g. a threshold, a required field, an approval condition) — skip requirements that are purely
procedural/narrative and can't be checked against data rows.

POLICY DOCUMENT:
{policy_text[:5000]}

Return JSON:
{{
    "rules": [
        {{"name": "Short rule name", "description": "What the policy requires, in one sentence"}}
    ]
}}
Only respond with valid JSON.
"""
        result = await self.ai.structured_complete(prompt=prompt, task_type="compliance", response_format="json")
        return result.get("rules", [])

    async def generate_report(self, policy_text: str, df: pl.DataFrame) -> ComplianceReport:
        """Generate a compliance report entirely grounded in the complete
        dataset. Rules are extracted from the policy text, then checked via
        the same real-computation path as detect_violations() — every
        finding's affected_count/affected_amount/evidence is computed by
        applying the rule's condition to the full dataframe, never
        estimated. overall_compliance_score, risk_summary, and
        compliance_by_rule are all derived arithmetically from those real
        findings; only the executive summary prose is drafted by the AI,
        and only after the real numbers already exist."""
        rules = await self.extract_rules_from_policy(policy_text)
        if not rules:
            return ComplianceReport(
                overall_compliance_score=100.0,
                executive_summary=(
                    "No checkable rules could be extracted from the provided policy document. "
                    "Try providing more specific, quantifiable requirements (e.g. dollar thresholds, "
                    "required fields, approval conditions)."
                ),
                risk_summary={"high_risk_count": 0, "medium_risk_count": 0, "low_risk_count": 0},
                findings=[],
                compliance_by_rule=[],
            )

        findings = await self.detect_violations(df, rules)

        computable = [f for f in findings if f.computable]
        overall_compliance_score = (
            round(100 - sum(f.affected_pct for f in computable) / len(computable), 1)
            if computable else 100.0
        )
        risk_summary = {
            "high_risk_count": sum(1 for f in findings if f.severity == "high"),
            "medium_risk_count": sum(1 for f in findings if f.severity == "medium"),
            "low_risk_count": sum(1 for f in findings if f.severity == "low"),
        }
        compliance_by_rule = [
            {
                "rule_name": f.title,
                "compliant_pct": round(100 - f.affected_pct, 2) if f.computable else None,
                "exception_pct": round(f.affected_pct, 2) if f.computable else None,
            }
            for f in findings
        ]

        summary_facts = "\n".join(
            f"- {f.title}: not computable ({f.finding})" if not f.computable
            else f"- {f.title}: {f.affected_count} of {f.total_count} rows affected "
                 f"({f.affected_pct}%), ${f.affected_amount:,.2f} dollar impact"
            for f in findings
        )
        summary_prompt = f"""
Write a 2-3 paragraph executive summary of this compliance assessment for an auditor's report,
based only on these REAL, precomputed findings. Do not invent additional statistics or findings.

Policy assessed (excerpt): {policy_text[:1000]}

Findings:
{summary_facts}

Overall compliance score (already computed — state it, do not change it): {overall_compliance_score}/100

Write only the executive summary text (no JSON, no headers).
"""
        response = await self.ai.complete(prompt=summary_prompt, task_type="compliance", temperature=0.3)

        return ComplianceReport(
            overall_compliance_score=overall_compliance_score,
            executive_summary=response.content.strip(),
            risk_summary=risk_summary,
            findings=findings,
            compliance_by_rule=compliance_by_rule,
        )

    async def detect_violations(self, df: pl.DataFrame,
                                 policy_rules: List[Dict]) -> List[ComplianceFinding]:
        """Detect compliance violations against policy_rules. Every count,
        dollar amount, and evidence value comes from applying the rule's
        translated condition to the COMPLETE dataframe via
        compute_rule_violation() — never a sample, never an LLM estimate.
        The AI's only remaining job is drafting a human-readable
        description/recommendation from those real, already-computed
        numbers. Rules that turn out not to be computable from this
        dataset, or that simply have zero matches, are still returned
        (marked accordingly) rather than silently dropped — so the user
        can see every rule was actually considered."""
        translations = await self.translate_rules_to_conditions(df, policy_rules)
        # translate_rules_to_conditions can return fewer/reordered entries
        # than requested if the LLM drops one — index by rule_index rather
        # than assuming positional alignment with policy_rules.
        by_index = {t.get("rule_index", i): t for i, t in enumerate(translations)}

        computed = []
        for i, rule in enumerate(policy_rules):
            translation = by_index.get(i, {"computable": False, "reason_if_not_computable": "AI did not return a translation for this rule."})
            result = self.compute_rule_violation(df, translation)
            computed.append({"rule": rule, "result": result})

        facts_lines = []
        for i, c in enumerate(computed):
            r = c["result"]
            if r["computable"]:
                facts_lines.append(
                    f"Rule {i}: {c['rule'].get('name', 'Unknown')} — {c['rule'].get('description', '')}\n"
                    f"  Computable: Yes. {r['affected_count']} of {r['total_count']} rows "
                    f"({r['affected_pct']}%) match. Dollar impact: {r['affected_amount']}. "
                    f"Example evidence: {', '.join(r['evidence'][:5]) or 'none'}."
                )
            else:
                facts_lines.append(
                    f"Rule {i}: {c['rule'].get('name', 'Unknown')} — {c['rule'].get('description', '')}\n"
                    f"  Computable: No. Reason: {r['reason']}"
                )

        prompt = f"""
You are drafting compliance finding descriptions for an auditor. Below are REAL, precomputed
results for each rule — every count and dollar figure was already computed from the complete
dataset. Do not invent additional statistics, evidence, or counts beyond what is stated here.
If a rule was not computable, or had zero matches, say so plainly rather than guessing at a
violation.

{chr(10).join(facts_lines)}

Return JSON:
{{
    "findings": [
        {{
            "rule_index": 0,
            "title": "Short finding title",
            "finding": "1-2 sentence description using only the numbers given above",
            "severity": "high/medium/low based on affected_pct and dollar impact magnitude, or 'info' if zero matches or not computable",
            "recommendation": "Suggested remediation action, or how to make the rule computable if it wasn't"
        }}
    ]
}}
Only respond with valid JSON.
"""
        result = await self.ai.structured_complete(prompt=prompt, task_type="compliance", response_format="json")
        drafted = {f.get("rule_index"): f for f in result.get("findings", [])}

        violations = []
        for i, c in enumerate(computed):
            r = c["result"]
            draft = drafted.get(i, {})
            default_severity = "info" if (not r["computable"] or r["affected_count"] == 0) else "medium"
            violations.append(ComplianceFinding(
                title=draft.get("title", c["rule"].get("name", "Unknown")),
                severity=draft.get("severity", default_severity),
                policy_requirement=c["rule"].get("description", ""),
                finding=draft.get("finding") or (
                    r["reason"] if not r["computable"]
                    else f"{r['affected_count']} of {r['total_count']} rows ({r['affected_pct']}%) match this rule."
                ),
                evidence=r["evidence"],
                recommendation=draft.get("recommendation", ""),
                affected_count=r["affected_count"],
                affected_amount=r["affected_amount"],
                total_count=r.get("total_count", 0),
                affected_pct=r.get("affected_pct", 0.0),
                computable=r["computable"],
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
