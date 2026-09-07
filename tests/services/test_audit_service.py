"""
Tests for Audit Service - Benford's Law, Duplicate Detection, Gap Analysis, etc.
"""
import pytest
import polars as pl
import numpy as np


class TestBenfordLawAnalysis:
    """Test cases for Benford's Law analysis"""

    @pytest.fixture
    def benford_compliant_data(self):
        """Generate data that follows Benford's Law"""
        # Generate numbers where first digits follow Benford distribution
        np.random.seed(42)
        n = 100
        # Benford distribution for first digits
        benford_probs = {
            1: 0.301, 2: 0.176, 3: 0.125, 4: 0.097, 5: 0.079,
            6: 0.067, 7: 0.058, 8: 0.051, 9: 0.046
        }
        first_digits = np.random.choice(
            list(benford_probs.keys()),
            size=n,
            p=list(benford_probs.values())
        )
        # Create actual numbers from first digits
        numbers = [float(f"{d}{''.join(str(np.random.randint(0, 10)) for _ in range(np.random.randint(1, 6)))}")
                   for d in first_digits]
        return numbers

    def test_benford_law_basic(self, transaction_dataframe):
        """Test basic Benford's Law analysis"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        result = processor.audit_benford_law(
            transaction_dataframe,
            column="amount",
            deviation_col="benford_deviation"
        )

        assert "benford_deviation" in result.columns
        # All deviation values should be non-negative
        deviations = result["benford_deviation"]
        assert (deviations >= 0).all()

    def test_benford_law_compliant_data(self, benford_compliant_data):
        """Test with data that follows Benford's Law"""
        from core.data_processor import DataProcessor

        # benford_compliant_data is a fixture (see decorator above) -
        # accessing it via self.benford_compliant_data (the previous
        # form) returns the undecorated FixtureFunctionDefinition object
        # itself, not the generated numbers, and only failed downstream
        # at len() rather than where the real mistake was.
        numbers = benford_compliant_data
        df = pl.DataFrame({"amount": numbers})

        processor = DataProcessor()
        result = processor.audit_benford_law(
            df,
            column="amount",
            deviation_col="deviation"
        )
        assert "deviation" in result.columns
        assert len(result) == len(numbers)


class TestDuplicateDetection:
    """Test cases for duplicate detection"""

    @pytest.fixture
    def data_with_duplicates(self):
        """Create data with known duplicates"""
        df = pl.DataFrame({
            "id": [1, 2, 3, 4, 5, 1, 2, 6],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve", "Alice", "Bob", "Frank"],
            "amount": [100, 200, 300, 400, 500, 100, 200, 600]
        })
        return df

    def test_duplicate_detection_basic(self, data_with_duplicates):
        """Test basic duplicate detection"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        result = processor.audit_duplicate_detection(
            data_with_duplicates,
            columns=["id", "name"],
            output_col="group_id",
            flag_col="is_duplicate"
        )

        assert "group_id" in result.columns
        assert "is_duplicate" in result.columns

    def test_duplicate_detection_identifies_duplicates(self, data_with_duplicates):
        """Test that duplicates are correctly identified"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        result = processor.audit_duplicate_detection(
            data_with_duplicates,
            columns=["id", "name"],
            output_col="group_id",
            flag_col="is_duplicate"
        )

        # Rows 0 and 5 are duplicates (both Alice with id=1)
        # Rows 1 and 6 are duplicates (both Bob with id=2)
        duplicate_count = result["is_duplicate"].sum()
        assert duplicate_count >= 2  # At least 2 duplicate rows (original + duplicate)

    def test_duplicate_detection_unique_rows(self):
        """Test with data that has no duplicates"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"]
        })

        processor = DataProcessor()
        result = processor.audit_duplicate_detection(
            df,
            columns=["id", "name"],
            output_col="group_id",
            flag_col="is_duplicate"
        )

        # No duplicates
        assert result["is_duplicate"].sum() == 0

    def test_duplicate_detection_group_ids(self, data_with_duplicates):
        """Test that duplicate groups get unique IDs"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        result = processor.audit_duplicate_detection(
            data_with_duplicates,
            columns=["id"],
            output_col="group_id",
            flag_col="is_duplicate"
        )

        # Get unique group IDs for duplicates
        duplicate_groups = result.filter(pl.col("is_duplicate") == True)["group_id"].unique()
        # Should have multiple groups (at least 2 for id=1 and id=2)
        assert len(duplicate_groups) >= 2


class TestGapAnalysis:
    """Test cases for gap analysis in sequential data"""

    def test_gap_analysis_basic(self):
        """Test basic gap analysis"""
        from core.data_processor import DataProcessor

        # Data with gaps: 1, 2, 4, 7, 8 (gaps at 3, 5, 6)
        df = pl.DataFrame({"id": [1, 2, 4, 7, 8]})

        processor = DataProcessor()
        result = processor.audit_gap_analysis(
            df,
            id_column="id",
            output_col="has_gap",
            missing_count_col="missing_count"
        )

        assert "has_gap" in result.columns
        assert "missing_count" in result.columns

    def test_gap_analysis_detects_gaps(self):
        """Test that gaps are correctly detected"""
        from core.data_processor import DataProcessor

        # Data with known gaps
        df = pl.DataFrame({"id": [1, 2, 4, 7, 8, 15]})

        processor = DataProcessor()
        result = processor.audit_gap_analysis(
            df,
            id_column="id",
            output_col="has_gap",
            missing_count_col="missing_count"
        )

        # Row with id=2 should have a gap (3 is missing)
        # Row with id=4 should have gaps (5, 6 are missing)
        # Row with id=7 should have gaps (8, 9, 10, 11, 12, 13, 14 are missing) - but 8 exists so different
        # Row with id=8 should have gap after (9-14 missing)
        # Row with id=15 should have no gap after
        gap_rows = result.filter(pl.col("has_gap") == True)
        assert len(gap_rows) > 0

    def test_gap_analysis_sorted_data(self):
        """Test gap analysis with sorted data"""
        from core.data_processor import DataProcessor

        # Continuous sequence - no gaps
        df = pl.DataFrame({"id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]})

        processor = DataProcessor()
        result = processor.audit_gap_analysis(
            df,
            id_column="id",
            output_col="has_gap",
            missing_count_col="missing_count"
        )

        # No gaps
        assert result["has_gap"].sum() == 0

    def test_gap_analysis_missing_count(self):
        """Test that missing count is correct"""
        from core.data_processor import DataProcessor

        # Data with known gap sizes
        df = pl.DataFrame({"id": [1, 2, 5, 10]})  # Gap of 2 (3,4), Gap of 4 (6,7,8,9)

        processor = DataProcessor()
        result = processor.audit_gap_analysis(
            df,
            id_column="id",
            output_col="has_gap",
            missing_count_col="missing_count"
        )

        # Check that missing counts are reasonable
        missing = result["missing_count"]
        assert missing.sum() > 0  # Some gaps exist


class TestRoundNumberDetection:
    """Test cases for round number detection (potential manipulation)"""

    def test_round_number_detection_basic(self):
        """Test basic round number detection"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "amount": [100.0, 200.0, 150.0, 1000.0, 123.45, 5000.0]
        })

        processor = DataProcessor()
        result = processor.audit_round_numbers(
            df,
            column="amount",
            threshold=0.5,
            output_col="is_round",
            score_col="roundness"
        )

        assert "is_round" in result.columns
        assert "roundness" in result.columns

        by_amount = dict(zip(df["amount"].to_list(), result["is_round"].to_list()))
        # 100, 200, 1000, 5000 are genuinely round (>= 50% trailing-zero
        # digits at this threshold); 150 is only partially round; 123.45
        # has a fractional part and is never round.
        assert by_amount[100.0] is True
        assert by_amount[200.0] is True
        assert by_amount[1000.0] is True
        assert by_amount[5000.0] is True
        assert by_amount[150.0] is False
        assert by_amount[123.45] is False


class TestAuditOutlierDetection:
    """Test cases for audit-specific outlier detection"""

    def test_outlier_detection_zscore(self):
        """Test outlier detection with z-score method"""
        from core.data_processor import DataProcessor

        # Data with clear outliers
        df = pl.DataFrame({
            "amount": [100, 102, 98, 101, 99, 500, 103, 97, 101, 99]  # 500 is an outlier
        })

        processor = DataProcessor()
        result = processor.audit_outlier_detection(
            df,
            column="amount",
            method="zscore",
            output_col="is_outlier",
            deviation_col="deviation"
        )

        assert "is_outlier" in result.columns
        assert "deviation" in result.columns

    def test_outlier_detection_iqr(self):
        """Test outlier detection with IQR method"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "value": [10, 12, 11, 13, 12, 100, 11, 12, 14, 11]  # 100 is an outlier
        })

        processor = DataProcessor()
        result = processor.audit_outlier_detection(
            df,
            column="value",
            method="iqr",
            output_col="is_outlier",
            deviation_col="deviation"
        )

        assert "is_outlier" in result.columns
        assert "deviation" in result.columns

    def test_outlier_detection_deviation_column(self):
        """Test that deviation column contains meaningful values"""
        from core.data_processor import DataProcessor

        df = pl.DataFrame({
            "value": [10, 12, 11, 50, 12, 11]  # 50 is an outlier
        })

        processor = DataProcessor()
        result = processor.audit_outlier_detection(
            df,
            column="value",
            method="zscore",
            output_col="is_outlier",
            deviation_col="deviation"
        )

        # Outlier should have higher deviation
        outlier_dev = result.filter(pl.col("value") == 50)["deviation"][0]
        normal_dev = result.filter(pl.col("value") == 11)["deviation"][0]

        assert outlier_dev > normal_dev


class TestGroupStatistics:
    """Test cases for group statistics operations"""

    def test_add_group_stats_basic(self, sample_dataframe):
        """Test adding group statistics"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        result = processor.stat_add_group_stats(
            sample_dataframe,
            group_column="category",
            target_column="amount",
            calculations=["mean", "sum", "count"]
        )

        # Should have new columns for statistics
        assert f"{'amount'}_mean" in result.columns
        assert f"{'amount'}_sum" in result.columns
        assert f"{'amount'}_count" in result.columns

    def test_group_stats_values(self, sample_dataframe):
        """Test that group statistics are calculated correctly"""
        from core.data_processor import DataProcessor

        processor = DataProcessor()
        result = processor.stat_add_group_stats(
            sample_dataframe,
            group_column="category",
            target_column="amount",
            calculations=["mean"]
        )

        # Check that each category has the same mean for all its rows
        for category in result["category"].unique():
            category_rows = result.filter(pl.col("category") == category)
            means = category_rows[f"{'amount'}_mean"].unique()
            assert len(means) == 1  # All rows in same category have same mean
