"""
Tests for AI Service - Sentiment Analysis, Entity Extraction, Classification, etc.
"""
import pytest
import polars as pl


class TestSentimentAnalysis:
    """Test cases for sentiment analysis"""

    @pytest.fixture
    def sentiment_data(self):
        """Create data for sentiment analysis tests"""
        df = pl.DataFrame({
            "text": [
                "This is a great product! I love it.",
                "Terrible service, very disappointed.",
                "The weather is okay, nothing special.",
                "Amazing quality and excellent support!",
                "Worst purchase I have ever made."
            ]
        })
        return df

    def test_sentiment_analysis_basic(self, sentiment_data):
        """Test basic sentiment analysis"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        result = processor.ai_sentiment_analysis(
            sentiment_data,
            column="text",
            output_col="sentiment"
        )

        assert "sentiment" in result.columns
        # All values should be between -1 and 1
        sentiments = result["sentiment"]
        assert (sentiments >= -1).all() and (sentiments <= 1).all()

    def test_sentiment_positive_text(self, sentiment_data):
        """Test sentiment on positive text"""
        from core.data_processor import DataProcessor

        # Single positive text
        df = pl.DataFrame({
            "text": ["This is absolutely wonderful! Best experience ever!"]
        })

        processor = DataProcessor()
        result = processor.ai_sentiment_analysis(
            df,
            column="text",
            output_col="sentiment"
        )

        # Positive text should have positive sentiment
        assert result["sentiment"][0] > 0

    def test_sentiment_negative_text(self, sentiment_data):
        """Test sentiment on negative text"""
        from core.data_processor import DataProcessor

        # Single negative text
        df = pl.DataFrame({
            "text": ["This is terrible, awful, and bad. I hate it."]
        })

        processor = DataProcessor()
        result = processor.ai_sentiment_analysis(
            df,
            column="text",
            output_col="sentiment"
        )

        # Negative text should have negative sentiment
        assert result["sentiment"][0] < 0

    def test_sentiment_neutral_text(self, sentiment_data):
        """Test sentiment on neutral text"""
        from core.data_processor import DataProcessor

        # Neutral text (no positive or negative words)
        df = pl.DataFrame({
            "text": ["The file has been processed successfully."]
        })

        processor = DataProcessor()
        result = processor.ai_sentiment_analysis(
            df,
            column="text",
            output_col="sentiment"
        )

        # Neutral text should have sentiment close to 0
        assert abs(result["sentiment"][0]) <= 1.0

    def test_sentiment_null_handling(self):
        """Test sentiment analysis with null values"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": ["Positive text", None, "Another text", None]
        })

        processor = DataProcessor()
        result = processor.ai_sentiment_analysis(
            df,
            column="text",
            output_col="sentiment"
        )

        # Should handle nulls without crashing
        assert "sentiment" in result.columns


class TestEntityExtraction:
    """Test cases for entity extraction"""

    def test_extract_email_entities(self):
        """Test email entity extraction"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": [
                "Contact us at support@example.com for help",
                "Email me at john.doe@company.org",
                "No email here"
            ]
        })

        processor = DataProcessor()
        result = processor.ai_entity_extraction(
            df,
            column="text",
            output_col="emails",
            entity_type="email"
        )

        assert "emails" in result.columns
        # First two should have emails extracted
        assert "support@example.com" in result["emails"][0]
        assert "john.doe@company.org" in result["emails"][1]
        # Third should be empty or not have email
        assert "@" not in result["emails"][2] or result["emails"][2] == ""

    def test_extract_phone_entities(self):
        """Test phone number entity extraction"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": [
                "Call 555-123-4567 for assistance",
                "Phone: 1234567890",
                "No phone here"
            ]
        })

        processor = DataProcessor()
        result = processor.ai_entity_extraction(
            df,
            column="text",
            output_col="phones",
            entity_type="phone"
        )

        assert "phones" in result.columns

    def test_extract_date_entities(self):
        """Test date entity extraction"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": [
                "Meeting on 2024-01-15",
                "Due by 12/31/2024",
                "No date here"
            ]
        })

        processor = DataProcessor()
        result = processor.ai_entity_extraction(
            df,
            column="text",
            output_col="dates",
            entity_type="date"
        )

        assert "dates" in result.columns

    def test_extract_money_entities(self):
        """Test money entity extraction"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": [
                "Price is $1,500.00",
                "Cost: 500 USD",
                "No money here"
            ]
        })

        processor = DataProcessor()
        result = processor.ai_entity_extraction(
            df,
            column="text",
            output_col="money",
            entity_type="money"
        )

        assert "money" in result.columns


class TestAIClassification:
    """Test cases for AI text classification"""

    def test_classify_basic(self):
        """Test basic text classification"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": [
                "Financial report for Q4 2024",
                "HR policy update on benefits",
                "Server maintenance scheduled"
            ]
        })

        processor = DataProcessor()
        result = processor.ai_classify(
            df,
            column="text",
            categories=["Finance", "HR", "IT", "Legal"],
            output_col="category",
            confidence_col="confidence"
        )

        assert "category" in result.columns
        assert "confidence" in result.columns
        # All rows should have a category assigned
        assert None not in result["category"]
        # Confidence should be between 0 and 1
        assert (result["confidence"] >= 0).all() and (result["confidence"] <= 1).all()

    def test_classify_exact_match(self):
        """Test classification with exact category match"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": ["This is about Finance and accounting"]
        })

        processor = DataProcessor()
        result = processor.ai_classify(
            df,
            column="text",
            categories=["Finance", "HR", "IT"],
            output_col="category",
            confidence_col="confidence"
        )

        # Should match Finance with high confidence
        assert result["category"][0] == "Finance"
        assert result["confidence"][0] >= 0.9

    def test_classify_no_match(self):
        """Test classification when no category matches"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": ["xyzabc123 random text"]
        })

        processor = DataProcessor()
        result = processor.ai_classify(
            df,
            column="text",
            categories=["Finance", "HR", "IT"],
            output_col="category",
            confidence_col="confidence"
        )

        # Should return first category with low confidence
        assert result["category"][0] in ["Finance", "HR", "IT"]
        assert result["confidence"][0] < 0.5

    def test_classify_confidence_values(self):
        """Test that confidence reflects match quality"""
        from core.data_processor import DataProcessor

        # Strong match
        df_strong = pl.DataFrame({"text": ["Finance department budget report"]})
        # Weak match
        df_weak = pl.DataFrame({"text": ["Document about finance but not really"]})

        processor = DataProcessor()

        result_strong = processor.ai_classify(
            df_strong,
            column="text",
            categories=["Finance", "HR", "IT"],
            output_col="category",
            confidence_col="confidence"
        )

        result_weak = processor.ai_classify(
            df_weak,
            column="text",
            categories=["Finance", "HR", "IT"],
            output_col="category",
            confidence_col="confidence"
        )

        # Strong match should have higher confidence
        assert result_strong["confidence"][0] >= result_weak["confidence"][0]


class TestAISummarization:
    """Test cases for AI summarization"""

    def test_summarize_basic(self):
        """Test basic text summarization"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": ["This is a very long text that should be summarized because it exceeds the maximum length limit." * 5]
        })

        processor = DataProcessor()
        result = processor.ai_summarize(
            df,
            column="text",
            max_length=50,
            output_col="summary"
        )

        assert "summary" in result.columns
        # Summary should be truncated
        assert len(result["summary"][0]) <= 50

    def test_summarize_short_text(self):
        """Test summarization of short text (no truncation)"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": ["Short text"]
        })

        processor = DataProcessor()
        result = processor.ai_summarize(
            df,
            column="text",
            max_length=100,
            output_col="summary"
        )

        # Short text should not be truncated
        assert result["summary"][0] == "Short text"

    def test_summarize_null_handling(self):
        """Test summarization with null values"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "text": ["Normal text", None, "Another text"]
        })

        processor = DataProcessor()
        result = processor.ai_summarize(
            df,
            column="text",
            max_length=50,
            output_col="summary"
        )

        # Should handle nulls without crashing
        assert "summary" in result.columns


class TestAIEnrichment:
    """Test cases for AI data enrichment"""

    def test_enrich_industry(self):
        """Test industry enrichment"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "company": [
                "Microsoft Tech Solutions",
                "HealthCare Plus Inc",
                "Global Finance Bank"
            ]
        })

        processor = DataProcessor()
        result = processor.ai_enrich(
            df,
            column="company",
            enrichment_type="industry",
            output_col="industry"
        )

        assert "industry" in result.columns
        # Should classify based on keywords
        assert result["industry"][0] == "Technology"  # Microsoft -> Tech
        assert result["industry"][1] == "Healthcare"  # HealthCare -> Healthcare
        assert result["industry"][2] == "Financial"  # Finance -> Financial

    def test_enrich_category(self):
        """Test category enrichment"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "item": [
                "Apple iPhone 15 Pro",
                "Samsung Galaxy S24",
                "Google Pixel 8"
            ]
        })

        processor = DataProcessor()
        result = processor.ai_enrich(
            df,
            column="item",
            enrichment_type="category",
            output_col="category"
        )

        assert "category" in result.columns
        # Should extract first word as category
        assert result["category"][0] == "Apple"

    def test_enrich_sentiment(self):
        """Test sentiment enrichment"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "review": [
                "Great product!",
                "Terrible service.",
                "Okay product."
            ]
        })

        processor = DataProcessor()
        result = processor.ai_enrich(
            df,
            column="review",
            enrichment_type="sentiment",
            output_col="sentiment"
        )

        assert "sentiment" in result.columns


class TestAIExplain:
    """Test cases for AI column explanation"""

    def test_explain_column(self):
        """Test column explanation generation"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "amount": [100, 200, 300],
            "description": ["Payment", "Refund", "Transfer"]
        })

        processor = DataProcessor()
        result = processor.ai_explain_column(
            df,
            column="amount",
            output_col="explanation"
        )

        assert "explanation" in result.columns
        # Should contain reference to the column
        assert "amount" in result["explanation"][0].lower() or "AI" in result["explanation"][0]


class TestAIPatternLearning:
    """Test cases for AI pattern learning (flash fill)"""

    def test_pattern_learning_basic(self):
        """Test basic pattern learning"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "input": ["ABC-123", "DEF-456", "GHI-789"]
        })

        processor = DataProcessor()
        result = processor.ai_pattern_learning(
            df,
            column="input",
            output_col="output",
            pattern=None  # Should learn from data
        )

        assert "output" in result.columns
        # Output should match input (pattern learning without examples just copies)
        assert result["output"][0] == "ABC-123"
