"""
Tests for AI-backed data_processor operations - Sentiment Analysis,
Entity Extraction, Classification, Summarization, Enrichment, Explain,
and Pattern Learning.

Each of these makes a real LLM call rather than a deterministic
heuristic, so what is tested here (via FakeAIManager) is: the prompt
actually gets built and sent, the LLM's JSON response actually gets
parsed back into the right columns in the right row order, batching/
null-handling doesn't crash, and a missing AI provider fails with a
clear error rather than silently returning nothing.
"""
import json
import pytest
import polars as pl


class FakeAIManager:
    """Minimal test double satisfying exactly the AIManager surface these
    ai_*() methods actually use (get_provider() + complete()) - no real
    network call or API key, while still exercising the real prompt-
    building/response-parsing/column-assignment logic.

    default_response is a JSON string returned for any prompt that
    doesn't match a key in response_map (a dict of {substring-to-look-for
    in the prompt: JSON string to return}), letting a single fake serve
    tests that need different canned answers depending on what was asked.
    """

    def __init__(self, default_response: str = '{"results": []}', response_map: dict = None):
        self.default_response = default_response
        self.response_map = response_map or {}
        self.prompts_seen = []

    def get_provider(self, name=None):
        return "fake-provider"  # only needs to be truthy

    async def complete(self, prompt, provider=None, task_type="general", temperature=0.1, force_json=False):
        from services.ai_service import AIResponse
        self.prompts_seen.append(prompt)
        content = self.default_response
        for key, resp in self.response_map.items():
            if key in prompt:
                content = resp
                break
        return AIResponse(content=content, model="fake-model", provider="fake")


def fake_manager_for(values: list) -> FakeAIManager:
    """A fake whose default_response is exactly {"results": values} -
    the common case where a test doesn't need per-prompt branching."""
    return FakeAIManager(default_response=json.dumps({"results": values}))


class TestNoAIProviderConfigured:
    """Every ai_*() method must fail clearly, not silently, when no AI
    provider is available - the actual guard this whole module's other
    tests work around by supplying FakeAIManager."""

    def test_sentiment_requires_ai_provider(self):
        from core.data_processor import DataProcessor
        df = pl.DataFrame({"text": ["hello"]})
        with pytest.raises(ValueError, match="No AI provider configured"):
            DataProcessor().ai_sentiment_analysis(df, column="text", output_col="s")

    def test_entity_extraction_requires_ai_provider(self):
        from core.data_processor import DataProcessor
        df = pl.DataFrame({"text": ["hello"]})
        with pytest.raises(ValueError, match="No AI provider configured"):
            DataProcessor().ai_entity_extraction(df, column="text", output_col="e", entity_type="email")

    def test_classify_requires_ai_provider(self):
        from core.data_processor import DataProcessor
        df = pl.DataFrame({"text": ["hello"]})
        with pytest.raises(ValueError, match="No AI provider configured"):
            DataProcessor().ai_classify(df, column="text", categories=["A"], output_col="c", confidence_col="conf")


class TestSentimentAnalysis:
    """Test cases for sentiment analysis"""

    @pytest.fixture
    def sentiment_data(self):
        return pl.DataFrame({
            "text": [
                "This is a great product! I love it.",
                "Terrible service, very disappointed.",
                "The weather is okay, nothing special.",
                "Amazing quality and excellent support!",
                "Worst purchase I have ever made."
            ]
        })

    def test_sentiment_analysis_basic(self, sentiment_data):
        """The LLM's per-row scores land in the right columns, in order."""
        from core.data_processor import DataProcessor

        fake = fake_manager_for([0.8, -0.7, 0.0, 0.9, -0.9])
        result = DataProcessor().ai_sentiment_analysis(
            sentiment_data, column="text", output_col="sentiment", ai_manager=fake
        )

        assert result["sentiment"].to_list() == [0.8, -0.7, 0.0, 0.9, -0.9]
        assert (result["sentiment"] >= -1).all() and (result["sentiment"] <= 1).all()
        # A prompt naming the actual row count was actually sent
        assert any("5 texts" in p for p in fake.prompts_seen)

    def test_sentiment_derives_label_from_score(self, sentiment_data):
        """The Positive/Negative/Neutral label is derived FROM the LLM's
        numeric score (>0.15 / <-0.15 / between), not asked of the LLM
        separately - confirms that derivation logic still works."""
        from core.data_processor import DataProcessor

        fake = fake_manager_for([0.8, -0.7, 0.0, 0.9, -0.9])
        result = DataProcessor().ai_sentiment_analysis(
            sentiment_data, column="text", output_cols=["score", "label"], ai_manager=fake
        )
        assert result["label"].to_list() == ["Positive", "Negative", "Neutral", "Positive", "Negative"]

    def test_sentiment_output_cols_takes_priority_over_output_col(self, sentiment_data):
        """The registry's auto-naming passes output_cols=[score, label];
        output_col alone is only a fallback for direct/manual calls."""
        from core.data_processor import DataProcessor

        fake = fake_manager_for([0.5] * 5)
        result = DataProcessor().ai_sentiment_analysis(
            sentiment_data, column="text", output_col="ignored",
            output_cols=["real_score", "real_label"], ai_manager=fake
        )
        assert "real_score" in result.columns
        assert "ignored" not in result.columns

    def test_sentiment_null_handling(self):
        """Nulls in the input column don't crash the batch call."""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"text": ["Positive text", None, "Another text", None]})
        fake = fake_manager_for([0.5, 0.0, 0.3, 0.0])
        result = DataProcessor().ai_sentiment_analysis(df, column="text", output_col="sentiment", ai_manager=fake)
        assert "sentiment" in result.columns
        assert len(result) == 4

    def test_malformed_ai_response_falls_back_without_crashing(self, sentiment_data):
        """A response that isn't valid JSON must not crash the whole
        column - batched_ai_map catches the parse failure per-batch and
        fills the fallback value instead."""
        from core.data_processor import DataProcessor

        fake = FakeAIManager(default_response="not valid json at all")
        result = DataProcessor().ai_sentiment_analysis(
            sentiment_data, column="text", output_col="sentiment", ai_manager=fake
        )
        assert result["sentiment"].to_list() == [0.0] * 5  # the declared fallback


class TestEntityExtraction:
    """Test cases for entity extraction"""

    def test_extract_email_entities(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": [
                "Contact us at support@example.com for help",
                "Email me at john.doe@company.org",
                "No email here",
            ]
        })
        fake = fake_manager_for(["support@example.com", "john.doe@company.org", ""])
        result = DataProcessor().ai_entity_extraction(
            df, column="text", output_col="emails", entity_type="email", ai_manager=fake
        )
        assert result["emails"].to_list() == ["support@example.com", "john.doe@company.org", ""]
        assert any("email addresses" in p for p in fake.prompts_seen)

    def test_extract_phone_entities_prompt_names_phone_numbers(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"text": ["Call 555-123-4567 for assistance"]})
        fake = fake_manager_for(["555-123-4567"])
        result = DataProcessor().ai_entity_extraction(
            df, column="text", output_col="phones", entity_type="phone", ai_manager=fake
        )
        assert result["phones"].to_list() == ["555-123-4567"]
        assert any("phone numbers" in p for p in fake.prompts_seen)

    def test_extract_date_entities(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"text": ["Meeting on 2024-01-15", "No date here"]})
        fake = fake_manager_for(["2024-01-15", ""])
        result = DataProcessor().ai_entity_extraction(
            df, column="text", output_col="dates", entity_type="date", ai_manager=fake
        )
        assert result["dates"].to_list() == ["2024-01-15", ""]

    def test_extract_money_entities(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"text": ["Price is $1,500.00", "No money here"]})
        fake = fake_manager_for(["$1,500.00", ""])
        result = DataProcessor().ai_entity_extraction(
            df, column="text", output_col="money", entity_type="money", ai_manager=fake
        )
        assert result["money"].to_list() == ["$1,500.00", ""]

    def test_no_ai_provider_returns_empty_string_fallback_not_crash(self):
        """batched_ai_map's own no-provider short-circuit (distinct from
        _require_ai_manager's upfront raise for this specific method's
        entrypoint - this covers the shared helper's own fallback path)."""
        from services.ai_service import batched_ai_map

        results = batched_ai_map(
            None, ["a", "b"], build_prompt=lambda b: "", parse_response=lambda r, b: r, fallback=""
        )
        assert results == ["", ""]


class TestAIClassification:
    """Test cases for AI text classification"""

    def test_classify_basic(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": [
                "Financial report for Q4 2024",
                "HR policy update on benefits",
                "Server maintenance scheduled",
            ]
        })
        canned = json.dumps({"results": [
            {"category": "Finance", "confidence": 0.95},
            {"category": "HR", "confidence": 0.9},
            {"category": "IT", "confidence": 0.85},
        ]})
        fake = FakeAIManager(default_response=canned)
        result = DataProcessor().ai_classify(
            df, column="text", categories=["Finance", "HR", "IT", "Legal"],
            output_col="category", confidence_col="confidence", ai_manager=fake
        )

        assert result["category"].to_list() == ["Finance", "HR", "IT"]
        assert result["confidence"].to_list() == [0.95, 0.9, 0.85]
        assert (result["confidence"] >= 0).all() and (result["confidence"] <= 1).all()

    def test_classify_falls_back_to_first_category_and_zero_confidence_on_ai_failure(self):
        """The declared fallback for a failed/malformed batch is
        (categories[0], 0.0), not a crash or an invented category."""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"text": ["xyzabc123 random text"]})
        fake = FakeAIManager(default_response="not json")
        result = DataProcessor().ai_classify(
            df, column="text", categories=["Finance", "HR", "IT"],
            output_col="category", confidence_col="confidence", ai_manager=fake
        )
        assert result["category"][0] == "Finance"
        assert result["confidence"][0] == 0.0

    def test_classify_prompt_lists_every_category(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"text": ["some text"]})
        fake = FakeAIManager(default_response=json.dumps({"results": [{"category": "IT", "confidence": 0.7}]}))
        DataProcessor().ai_classify(
            df, column="text", categories=["Finance", "HR", "IT"],
            output_col="category", confidence_col="confidence", ai_manager=fake
        )
        prompt = fake.prompts_seen[0]
        assert "Finance" in prompt and "HR" in prompt and "IT" in prompt


class TestAISummarization:
    """Test cases for AI summarization"""

    def test_summarize_basic(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"text": ["A very long piece of text that needs summarizing." * 5]})
        fake = fake_manager_for(["A short summary."])
        result = DataProcessor().ai_summarize(df, column="text", max_length=50, output_col="summary", ai_manager=fake)
        assert result["summary"][0] == "A short summary."

    def test_summarize_result_truncated_to_max_length_as_a_safety_net(self):
        """Even though the prompt asks the LLM to respect max_length,
        parse_response() still hard-truncates - a defense against an LLM
        that ignores the instruction."""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"text": ["text"]})
        fake = fake_manager_for(["x" * 200])  # LLM "ignored" the 50-char limit
        result = DataProcessor().ai_summarize(df, column="text", max_length=50, output_col="summary", ai_manager=fake)
        assert len(result["summary"][0]) == 50

    def test_summarize_null_handling(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"text": ["Normal text", None, "Another text"]})
        fake = fake_manager_for(["summary 1", "", "summary 3"])
        result = DataProcessor().ai_summarize(df, column="text", max_length=50, output_col="summary", ai_manager=fake)
        assert "summary" in result.columns
        assert len(result) == 3


class TestAIEnrichment:
    """Test cases for AI data enrichment"""

    def test_enrich_industry(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"company": ["Microsoft Tech Solutions", "HealthCare Plus Inc", "Global Finance Bank"]})
        fake = fake_manager_for(["Technology", "Healthcare", "Financial"])
        result = DataProcessor().ai_enrich(
            df, column="company", enrichment_type="industry", output_col="industry", ai_manager=fake
        )
        assert result["industry"].to_list() == ["Technology", "Healthcare", "Financial"]
        assert any("industry" in p.lower() for p in fake.prompts_seen)

    def test_enrich_category(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"item": ["Apple iPhone 15 Pro"]})
        fake = fake_manager_for(["Smartphone"])
        result = DataProcessor().ai_enrich(
            df, column="item", enrichment_type="category", output_col="category", ai_manager=fake
        )
        assert result["category"][0] == "Smartphone"

    def test_enrich_sentiment_uses_positive_negative_neutral_instruction(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"review": ["Great product!", "Terrible service.", "Okay product."]})
        fake = fake_manager_for(["Positive", "Negative", "Neutral"])
        result = DataProcessor().ai_enrich(
            df, column="review", enrichment_type="sentiment", output_col="sentiment", ai_manager=fake
        )
        assert result["sentiment"].to_list() == ["Positive", "Negative", "Neutral"]
        assert any("Positive, Negative, Neutral" in p for p in fake.prompts_seen)

    def test_enrich_unknown_type_still_sends_a_reasonable_instruction(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"value": ["something"]})
        fake = fake_manager_for(["result"])
        DataProcessor().ai_enrich(df, column="value", enrichment_type="custom_thing", output_col="out", ai_manager=fake)
        assert any("custom_thing" in p for p in fake.prompts_seen)


class TestAIExplain:
    """Test cases for AI column explanation"""

    def test_explain_column(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"amount": [100, 200, 300]})
        fake = fake_manager_for(["A payment amount in dollars.", "x", "y"])
        result = DataProcessor().ai_explain_column(df, column="amount", output_col="explanation", ai_manager=fake)
        assert result["explanation"][0] == "A payment amount in dollars."
        assert any("'amount'" in p for p in fake.prompts_seen)

    def test_explain_column_style_affects_prompt_detail(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"amount": [100]})
        fake = fake_manager_for(["explanation"])
        DataProcessor().ai_explain_column(df, column="amount", output_col="e", style="detailed", ai_manager=fake)
        assert any("two to three sentences" in p for p in fake.prompts_seen)


class TestAIPatternLearning:
    """Test cases for AI pattern learning (flash fill)"""

    def test_pattern_learning_with_explicit_pattern(self):
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"input": ["ABC-123", "DEF-456", "GHI-789"]})
        fake = fake_manager_for(["123", "456", "789"])
        result = DataProcessor().ai_pattern_learning(
            df, column="input", output_col="output", pattern="extract just the numeric part", ai_manager=fake
        )
        assert result["output"].to_list() == ["123", "456", "789"]
        assert any("extract just the numeric part" in p for p in fake.prompts_seen)

    def test_pattern_learning_no_pattern_uses_infer_instruction(self):
        """pattern=None falls back to an "infer the most useful derived
        version" instruction, rather than a no-op copy - the old
        implementation's actual behavior (a 100% no-op) is exactly what
        this method's docstring says it was rewritten to stop doing."""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({"input": ["ABC-123"]})
        fake = fake_manager_for(["ABC-123"])
        result = DataProcessor().ai_pattern_learning(
            df, column="input", output_col="output", pattern=None, ai_manager=fake
        )
        assert result["output"][0] == "ABC-123"
        assert any("Infer the most likely useful" in p for p in fake.prompts_seen)


class TestKeyringAvailabilityProbe:
    """_use_keyring must reflect whether a working keyring backend
    actually exists, not just whether `import keyring` succeeded: on a
    headless Linux environment with no D-Bus Secret Service running,
    the keyring package installs and imports fine, but every actual
    get_password()/set_password() call raises NoKeyringError at the
    point of use."""

    def test_falls_back_when_keyring_has_no_backend(self, monkeypatch):
        import importlib
        import sys
        import types

        class FakeKeyringErrors(types.ModuleType):
            class KeyringError(Exception):
                pass

        class FakeNoKeyringError(FakeKeyringErrors.KeyringError):
            pass

        fake_keyring = types.ModuleType("keyring")
        fake_keyring.errors = FakeKeyringErrors("keyring.errors")

        def _raise_no_backend(*args, **kwargs):
            raise FakeNoKeyringError("No recommended backend was available.")

        fake_keyring.get_password = _raise_no_backend

        monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
        monkeypatch.setitem(sys.modules, "keyring.errors", fake_keyring.errors)

        import services.ai_service as ai_service
        importlib.reload(ai_service)
        try:
            assert ai_service._use_keyring is False
        finally:
            importlib.reload(ai_service)  # restore real keyring detection for later tests

    def test_uses_keyring_when_a_real_backend_responds(self, monkeypatch):
        import importlib
        import sys
        import types

        class FakeKeyringErrors(types.ModuleType):
            class KeyringError(Exception):
                pass

        fake_keyring = types.ModuleType("keyring")
        fake_keyring.errors = FakeKeyringErrors("keyring.errors")
        fake_keyring.get_password = lambda service, key: None  # a working backend with no stored value yet

        monkeypatch.setitem(sys.modules, "keyring", fake_keyring)
        monkeypatch.setitem(sys.modules, "keyring.errors", fake_keyring.errors)

        import services.ai_service as ai_service
        importlib.reload(ai_service)
        try:
            assert ai_service._use_keyring is True
        finally:
            importlib.reload(ai_service)  # restore real keyring detection for later tests
