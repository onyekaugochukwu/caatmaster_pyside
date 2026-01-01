"""
Tests for Export Service
"""
import pytest
import json
import tempfile
from pathlib import Path
import polars as pl
from datetime import date, datetime


class TestExportService:
    """Test cases for the ExportService class"""

    @pytest.fixture
    def sample_dataframe(self):
        """Create a sample dataframe for export tests"""
        df = pl.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "Diana", "Eve"],
            "amount": [100.50, 250.75, 175.00, 320.25, 89.99],
            "category": ["A", "B", "A", "C", "B"],
            "date_col": [
                date(2024, 1, 15), date(2024, 2, 20), date(2024, 3, 10),
                date(2024, 4, 5), date(2024, 5, 25)
            ],
            "flag": [True, False, True, False, True],
        })
        return df

    @pytest.fixture
    def export_service(self):
        """Create an ExportService instance"""
        from services.export_service import ExportService
        return ExportService()

    def test_service_initialization(self):
        """Test ExportService initialization"""
        from services.export_service import ExportService
        service = ExportService()
        assert service is not None

    def test_export_csv(self, export_service, sample_dataframe, temp_dir):
        """Test exporting to CSV format"""
        file_path = temp_dir / "test_export.csv"

        result = export_service.export_dataframe(
            df=sample_dataframe,
            file_path=str(file_path),
            format="csv"
        )

        assert result is not None
        assert Path(result).exists()
        assert Path(result).suffix == ".csv"

        # Verify content
        df_read = pl.read_csv(result)
        assert len(df_read) == 5
        assert "name" in df_read.columns

    def test_export_parquet(self, export_service, sample_dataframe, temp_dir):
        """Test exporting to Parquet format"""
        file_path = temp_dir / "test_parquet.parquet"

        result = export_service.export_dataframe(
            df=sample_dataframe,
            file_path=str(file_path),
            format="parquet"
        )

        assert result is not None
        assert Path(result).exists()
        assert Path(result).suffix == ".parquet"

        # Verify content
        df_read = pl.read_parquet(result)
        assert len(df_read) == 5

    def test_export_json(self, export_service, sample_dataframe, temp_dir):
        """Test exporting to JSON format"""
        file_path = temp_dir / "test_json.json"

        result = export_service.export_dataframe(
            df=sample_dataframe,
            file_path=str(file_path),
            format="json"
        )

        assert result is not None
        assert Path(result).exists()
        assert Path(result).suffix == ".json"

        # Verify content
        with open(result, 'r') as f:
            data = json.load(f)
        assert len(data) == 5

    def test_export_excel(self, export_service, sample_dataframe, temp_dir):
        """Test exporting to Excel format"""
        file_path = temp_dir / "test_excel.xlsx"

        result = export_service.export_dataframe(
            df=sample_dataframe,
            file_path=str(file_path),
            format="xlsx"
        )

        assert result is not None
        assert Path(result).exists()
        assert Path(result).suffix == ".xlsx"

    def test_export_invalid_format(self, export_service, sample_dataframe, temp_dir):
        """Test that invalid format raises error"""
        file_path = temp_dir / "test_invalid.fake"

        with pytest.raises(ValueError, match="Unsupported export format"):
            export_service.export_dataframe(
                df=sample_dataframe,
                file_path=str(file_path),
                format="invalid_format"
            )

    def test_export_dataframe_csv(self, export_service, temp_dir):
        """Test exporting a dataframe to CSV"""
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"]
        })
        file_path = temp_dir / "test_data.csv"

        result = export_service.export_dataframe(df, str(file_path), format="csv")

        assert Path(result).exists()
        assert Path(result).suffix == ".csv"

        # Verify content
        df_read = pl.read_csv(result)
        assert len(df_read) == 3

    def test_export_dataframe_parquet(self, export_service, temp_dir):
        """Test exporting a dataframe to Parquet"""
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "value": [100.5, 200.75, 300.0]
        })
        file_path = temp_dir / "test_parquet.parquet"

        result = export_service.export_dataframe(df, str(file_path), format="parquet")

        assert Path(result).exists()
        assert Path(result).suffix == ".parquet"

        # Verify content
        df_read = pl.read_parquet(result)
        assert len(df_read) == 3

    def test_export_dataframe_json(self, export_service, temp_dir):
        """Test exporting a dataframe to JSON"""
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "name": ["A", "B", "C"]
        })
        file_path = temp_dir / "test_json.json"

        result = export_service.export_dataframe(df, str(file_path), format="json")

        assert Path(result).exists()
        assert Path(result).suffix == ".json"

        # Verify content
        with open(result, 'r') as f:
            data = json.load(f)
        assert len(data) == 3

    def test_export_empty_dataframe(self, export_service, temp_dir):
        """Test exporting empty dataframe"""
        df = pl.DataFrame({
            "col1": pl.Series([], dtype=pl.Int64),
            "col2": pl.Series([], dtype=pl.Utf8),
        })
        file_path = temp_dir / "empty_export.csv"

        result = export_service.export_dataframe(df, str(file_path), format="csv")

        assert result is not None
        assert Path(result).exists()

        df_read = pl.read_csv(result)
        assert len(df_read) == 0

    def test_export_data_types_preservation(self, export_service, temp_dir):
        """Test that data types are preserved in export"""
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "amount": [100.5, 200.75, 300.0],
            "name": ["A", "B", "C"]
        })
        file_path = temp_dir / "types_test.parquet"

        result = export_service.export_dataframe(df, str(file_path), format="parquet")

        df_read = pl.read_parquet(result)

        # Check that numeric types are preserved
        assert df_read["amount"].dtype == pl.Float64
        assert df_read["id"].dtype == pl.Int64

    def test_export_unicode_content(self, export_service, temp_dir):
        """Test exporting data with unicode characters"""
        df = pl.DataFrame({
            "id": [1, 2, 3],
            "name": ["café", "naïve", "日本語"],
        })
        file_path = temp_dir / "unicode_export.csv"

        result = export_service.export_dataframe(df, str(file_path), format="csv")

        assert result is not None

        # Verify unicode is preserved
        df_read = pl.read_csv(result)
        assert df_read["name"][0] == "café"

    def test_overwrite_existing_file(self, export_service, sample_dataframe, temp_dir):
        """Test that export overwrites existing file"""
        file_path = temp_dir / "overwrite.csv"

        # First export
        export_service.export_dataframe(sample_dataframe, str(file_path), format="csv")

        # Modify file
        file_path.write_text("modified")

        # Export again
        result = export_service.export_dataframe(sample_dataframe, str(file_path), format="csv")

        # Verify it's been overwritten
        df_read = pl.read_csv(result)
        assert len(df_read) == 5


class TestHTMLReportGeneration:
    """Test cases for HTML report generation"""

    @pytest.fixture
    def export_service(self):
        """Create an ExportService instance"""
        from services.export_service import ExportService
        return ExportService()

    def test_export_summary(self, export_service, temp_dir):
        """Test generating HTML summary report"""
        df = pl.DataFrame({
            "numeric_col": [1.0, 2.0, 3.0],
            "text_col": ["a", "b", "c"],
        })
        file_path = temp_dir / "test_summary"

        result = export_service.export_summary(
            df=df,
            file_path=str(file_path),
            title="Test Summary Report"
        )

        assert result is not None
        assert Path(result).exists()
        assert Path(result).suffix == ".html"

        # Verify it's valid HTML
        with open(result, 'r') as f:
            content = f.read()
        assert "<html" in content.lower() or "<!DOCTYPE" in content.upper()
        assert "Test Summary Report" in content

    def test_report_contains_column_info(self, export_service, temp_dir):
        """Test that HTML report contains column information"""
        df = pl.DataFrame({
            "numeric_col": [1.0, 2.0, 3.0],
            "text_col": ["a", "b", "c"],
        })
        file_path = temp_dir / "test_report"

        export_service.export_summary(df, str(file_path), "Test Report")

        with open(str(file_path) + ".html", 'r') as f:
            content = f.read()

        assert "numeric_col" in content
        assert "text_col" in content

    def test_report_contains_statistics(self, export_service, temp_dir):
        """Test that HTML report contains statistics"""
        df = pl.DataFrame({
            "values": [10, 20, 30, 40, 50],
        })
        file_path = temp_dir / "stats_report"

        export_service.export_summary(df, str(file_path), "Stats Report")

        with open(str(file_path) + ".html", 'r') as f:
            content = f.read()

        # Should contain some statistics or data info
        assert "values" in content.lower() or "5" in content
