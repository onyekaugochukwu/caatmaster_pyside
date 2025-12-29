"""
AI Service for CAATmaster
Implements AI operations that create enrichment columns
Note: AI features require API keys from providers (OpenAI, Anthropic, etc.)
"""
import polars as pl
import numpy as np
from typing import Dict, Any, List, Optional
import json
from pathlib import Path


class AIService:
    """Service for AI operations that create enrichment columns"""

    def __init__(self, api_key: str = None, provider: str = "openai"):
        self.api_key = api_key
        self.provider = provider
        self.client = None

        if api_key and provider == "openai":
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
            except ImportError:
                print("Warning: openai package not installed. Install with: pip install openai")

    def classify_text(
        self,
        df: pl.DataFrame,
        column: str,
        categories: List[str],
        output_column: str = None,
        confidence_column: str = None,
        batch_size: int = 10
    ) -> pl.DataFrame:
        """
        Classify text using AI - creates category and confidence columns
        """
        if output_column is None:
            output_column = f"{column}_category"
        if confidence_column is None:
            confidence_column = f"{column}_confidence"

        categories_list = categories
        categories_str = ", ".join(categories)

        predictions = []
        confidences = []

        # Process in batches
        texts = df[column].to_list()

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]

            if self.client:
                # Use OpenAI API
                batch_results = self._classify_with_openai(batch, categories_str)
            else:
                # Use simple keyword matching as fallback
                batch_results = self._classify_with_keywords(batch, categories_list)

            predictions.extend([r['category'] for r in batch_results])
            confidences.extend([r['confidence'] for r in batch_results])

        result_df = df.with_columns([
            pl.Series(output_column, predictions),
            pl.Series(confidence_column, confidences, dtype=pl.Float64)
        ])

        return result_df

    def _classify_with_openai(self, texts: List[str], categories: str) -> List[Dict]:
        """Classify using OpenAI API"""
        results = []

        for text in texts:
            if not text or pd.isna(text):
                results.append({'category': None, 'confidence': 0.0})
                continue

            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": f"Classify the following text into one of these categories: {categories}. "
                                    f"Respond with the category name only, followed by a confidence score (0-1). "
                                    f"Format: 'category|confidence'"
                        },
                        {
                            "role": "user",
                            "content": str(text)
                        }
                    ],
                    max_tokens=50,
                    temperature=0
                )

                response_text = response.choices[0].message.content.strip()

                if '|' in response_text:
                    category, confidence = response_text.split('|')
                    category = category.strip()
                    confidence = float(confidence.strip())
                else:
                    category = response_text.strip()
                    confidence = 0.8  # Default confidence

                results.append({'category': category, 'confidence': confidence})

            except Exception as e:
                print(f"Error classifying text: {e}")
                results.append({'category': 'Unknown', 'confidence': 0.0})

        return results

    def _classify_with_keywords(self, texts: List[str], categories: List[str]) -> List[Dict]:
        """Fallback classification using simple keyword matching"""
        results = []

        for text in texts:
            if not text or pd.isna(text):
                results.append({'category': None, 'confidence': 0.0})
                continue

            text_lower = str(text).lower()
            best_category = None
            best_score = 0

            for category in categories:
                category_lower = category.lower()
                # Check for exact word match
                if category_lower in text_lower:
                    score = text_lower.count(category_lower) / max(len(text_lower.split()), 1)
                    if score > best_score:
                        best_score = score
                        best_category = category

            if best_category:
                results.append({'category': best_category, 'confidence': min(best_score + 0.5, 1.0)})
            else:
                results.append({'category': 'Other', 'confidence': 0.3})

        return results

    def extract_entity(
        self,
        df: pl.DataFrame,
        column: str,
        entity_type: str,
        output_column: str = None,
        custom_prompt: str = None
    ) -> pl.DataFrame:
        """
        Extract entities from text using AI - creates extracted column
        """
        if output_column is None:
            output_column = f"{column}_extracted_{entity_type}"

        texts = df[column].to_list()
        extracted = []

        for text in texts:
            if not text or pd.isna(text):
                extracted.append(None)
                continue

            if self.client:
                result = self._extract_with_openai(text, entity_type, custom_prompt)
            else:
                result = self._extract_with_regex(text, entity_type)

            extracted.append(result)

        result_df = df.with_columns([
            pl.Series(output_column, extracted)
        ])

        return result_df

    def _extract_with_openai(self, text: str, entity_type: str, custom_prompt: str = None) -> str:
        """Extract using OpenAI API"""
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompts = {
                "invoice_number": "Extract the invoice number from this text. Return only the invoice number.",
                "email": "Extract the email address from this text. Return only the email.",
                "phone": "Extract the phone number from this text. Return only the phone number.",
                "date": "Extract the date from this text. Return only the date.",
                "amount": "Extract the monetary amount from this text. Return only the amount.",
                "company_name": "Extract the company name from this text. Return only the company name.",
                "address": "Extract the street address from this text. Return only the address.",
            }
            prompt = prompts.get(entity_type, f"Extract the {entity_type} from this text.")

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a data extraction assistant."},
                    {"role": "user", "content": f"{prompt}\n\nText: {text}"}
                ],
                max_tokens=100,
                temperature=0
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error extracting entity: {e}")
            return None

    def _extract_with_regex(self, text: str, entity_type: str) -> Optional[str]:
        """Fallback extraction using regex patterns"""
        import re

        patterns = {
            "email": r'[\w\.-]+@[\w\.-]+\.\w+',
            "phone": r'[\d\(\)\-\+\s]{10,}',
            "invoice_number": r'(?i)invoice\s*#?\s*[:#]?\s*([A-Z0-9\-]+)',
            "date": r'\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}',
            "amount": r'[\$€£]?\s*[\d,]+\.?\d*\s*(?:USD|EUR|GBP)?',
        }

        pattern = patterns.get(entity_type)
        if pattern:
            match = re.search(pattern, str(text))
            if match:
                return match.group(0)

        return None

    def analyze_sentiment(
        self,
        df: pl.DataFrame,
        column: str,
        score_column: str = None,
        label_column: str = None
    ) -> pl.DataFrame:
        """
        Analyze sentiment of text - creates sentiment score and label columns
        """
        if score_column is None:
            score_column = f"{column}_sentiment_score"
        if label_column is None:
            label_column = f"{column}_sentiment"

        texts = df[column].to_list()
        scores = []
        labels = []

        for text in texts:
            if not text or pd.isna(text):
                scores.append(0.0)
                labels.append("Neutral")
                continue

            if self.client:
                score, label = self._sentiment_with_openai(text)
            else:
                score, label = self._sentiment_with_keywords(text)

            scores.append(score)
            labels.append(label)

        result_df = df.with_columns([
            pl.Series(score_column, scores, dtype=pl.Float64),
            pl.Series(label_column, labels)
        ])

        return result_df

    def _sentiment_with_openai(self, text: str) -> tuple:
        """Analyze sentiment using OpenAI"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze the sentiment of the text. "
                                "Respond with a score from -1 (very negative) to +1 (very positive), "
                                "followed by a pipe and the label (Positive/Negative/Neutral). "
                                "Format: 'score|label'"
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_tokens=20,
                temperature=0
            )

            response_text = response.choices[0].message.content.strip()

            if '|' in response_text:
                score_str, label = response_text.split('|')
                score = float(score_str.strip())
            else:
                score = 0.0
                label = "Neutral"

            return score, label

        except Exception as e:
            print(f"Error analyzing sentiment: {e}")
            return 0.0, "Neutral"

    def _sentiment_with_keywords(self, text: str) -> tuple:
        """Fallback sentiment analysis using keywords"""
        positive_words = ['good', 'great', 'excellent', 'happy', 'love', 'best', 'amazing', 'wonderful']
        negative_words = ['bad', 'terrible', 'hate', 'worst', 'awful', 'poor', 'sad', 'angry']

        text_lower = str(text).lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            return 0.5, "Positive"
        elif negative_count > positive_count:
            return -0.5, "Negative"
        else:
            return 0.0, "Neutral"

    def learn_pattern(
        self,
        df: pl.DataFrame,
        source_column: str,
        examples: Dict[str, str],
        output_columns: List[str]
    ) -> pl.DataFrame:
        """
        AI learns pattern from examples (Flash Fill style) - creates extracted columns
        """
        # This is a simplified implementation
        # In production, you'd use a more sophisticated pattern learning algorithm

        source_texts = df[source_column].to_list()
        results = {col: [] for col in output_columns}

        for text in source_texts:
            if not text or pd.isna(text):
                for col in output_columns:
                    results[col].append(None)
                continue

            # Try to find matching example
            text_str = str(text)
            matched = False

            for example_input, example_output in examples.items():
                if example_input.lower() in text_str.lower():
                    # Extract similar pattern from text
                    # This is simplified - real implementation would use ML
                    for i, col in enumerate(output_columns):
                        if i < len(example_output):
                            results[col].append(example_output)
                    matched = True
                    break

            if not matched:
                for col in output_columns:
                    results[col].append(None)

        # Add columns to dataframe
        result_columns = [pl.Series(col, results[col]) for col in output_columns]
        result_df = df.with_columns(result_columns)

        return result_df


# Import pandas for null checking
import pandas as pd
