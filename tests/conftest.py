"""
Pytest configuration and fixtures for CAATmaster test suite
"""
import pytest
import sys
from pathlib import Path
import tempfile
import os

# Default to a headless Qt platform so PySide6 widgets (dialogs, etc.) can
# be constructed in tests without a real display - setdefault() so a
# developer who deliberately wants a visible Qt window for debugging can
# still override it by setting QT_QPA_PLATFORM themselves before running
# pytest. Must happen before anything imports PySide6.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Add src directory to path
_src_path = Path(__file__).parent.parent / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory"""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def src_path(project_root):
    """Return the src directory path"""
    return project_root / "src"


@pytest.fixture(scope="session")
def data_path(project_root):
    """Return the data directory path"""
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for test artifacts"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_dataframe():
    """Create a sample Polars DataFrame for testing"""
    import polars as pl
    from datetime import date, datetime

    df = pl.DataFrame({
        "id": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "name": ["Alice", "Bob", "Charlie", "Diana", "Eve",
                 "Frank", "Grace", "Henry", "Ivy", "Jack"],
        "amount": [100.50, 250.75, 175.00, 320.25, 89.99,
                   450.00, 125.50, 200.00, 95.75, 180.25],
        "category": ["A", "B", "A", "C", "B",
                     "A", "C", "B", "A", "C"],
        "text_col": ["Hello World", "Test String", "Data Processing",
                     "PySide6 App", "Unit Tests",
                     "CI/CD Pipeline", "Machine Learning",
                     "Data Analysis", "Audit Work", "Quality Assurance"],
        "date_col": [
            date(2024, 1, 15), date(2024, 2, 20), date(2024, 3, 10),
            date(2024, 4, 5), date(2024, 5, 25), date(2024, 6, 30),
            date(2024, 7, 12), date(2024, 8, 8), date(2024, 9, 18), date(2024, 10, 22)
        ],
        "datetime_col": [
            datetime(2024, 1, 15, 10, 30, 0), datetime(2024, 2, 20, 14, 45, 0),
            datetime(2024, 3, 10, 9, 15, 0), datetime(2024, 4, 5, 16, 20, 0),
            datetime(2024, 5, 25, 11, 0, 0), datetime(2024, 6, 30, 13, 30, 0),
            datetime(2024, 7, 12, 8, 45, 0), datetime(2024, 8, 8, 15, 0, 0),
            datetime(2024, 9, 18, 10, 30, 0), datetime(2024, 10, 22, 12, 0, 0)
        ],
        "flag": [True, False, True, False, True, False, True, False, True, False],
        "nullable_col": [1.0, 2.0, None, 4.0, 5.0, None, 7.0, 8.0, None, 10.0],
    })
    return df


@pytest.fixture
def small_dataframe():
    """Create a small Polars DataFrame for quick tests"""
    import polars as pl

    df = pl.DataFrame({
        "a": [1, 2, 3, 4, 5],
        "b": [10, 20, 30, 40, 50],
        "text": ["foo", "bar", "baz", "qux", "quux"],
    })
    return df


@pytest.fixture
def text_dataframe():
    """Create a DataFrame with text data for text transformation tests"""
    import polars as pl

    df = pl.DataFrame({
        "text": [
            "  Hello World  ",
            "test STRING",
            "Mixed Case Text",
            "  spaced out  ",
            "Numbers123456",
        ],
        "email": [
            "test@example.com",
            "user@domain.org",
            "admin@company.net",
            "invalid-email",
            "another@test.io",
        ],
    })
    return df


@pytest.fixture
def numeric_dataframe():
    """Create a DataFrame with numeric data for math transformation tests"""
    import polars as pl
    import numpy as np

    # Create data with some outliers for anomaly detection tests
    data = {
        "value": [10, 12, 11, 13, 12, 100, 11, 12, 14, 11],
        "positive": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "negative": [-5, -10, -15, -20, -25, -30, -35, -40, -45, -50],
    }
    df = pl.DataFrame(data)
    return df


@pytest.fixture
def datetime_dataframe():
    """Create a DataFrame with datetime data for datetime transformation tests"""
    import polars as pl
    from datetime import date, datetime

    df = pl.DataFrame({
        "date": [
            date(2024, 1, 15),  # Monday
            date(2024, 2, 20),  # Tuesday
            date(2024, 3, 10),  # Sunday
            date(2024, 4, 5),   # Friday
            date(2024, 5, 25),  # Saturday
        ],
        "datetime": [
            datetime(2024, 1, 15, 10, 30, 0),
            datetime(2024, 2, 20, 14, 45, 0),
            datetime(2024, 3, 10, 9, 15, 0),
            datetime(2024, 4, 5, 16, 20, 0),
            datetime(2024, 5, 25, 11, 0, 0),
        ],
    })
    return df


@pytest.fixture
def transaction_dataframe():
    """Create a DataFrame simulating financial transactions for audit tests"""
    import polars as pl

    # First digit distribution that follows Benford's Law
    amounts = [
        1250.00, 2340.50, 3150.75, 4120.00, 5100.25,
        1890.00, 2750.00, 3980.00, 4600.00, 5200.00,
        1100.00, 2200.00, 3300.00, 4400.00, 5500.00,
        1500.00, 2600.00, 3700.00, 4800.00, 5900.00,
    ]
    df = pl.DataFrame({
        "transaction_id": list(range(1, 21)),
        "amount": amounts,
        "description": [
            "Invoice #1001", "Payment #2002", "Transfer #3003", "Refund #4004", "Fee #5005",
            "Credit #6006", "Debit #7007", "Wire #8008", "Check #9009", "Deposit #10010",
            "Withdrawal #11011", "Purchase #12012", "Sale #13013", "Service #14014", "Product #15015",
            "Consulting #16016", "License #17017", "Support #18018", "Maintenance #19019", "Training #20020",
        ],
    })
    return df


@pytest.fixture
def empty_dataframe():
    """Create an empty DataFrame with column schema"""
    import polars as pl

    df = pl.DataFrame({
        "col1": pl.Series([], dtype=pl.Int64),
        "col2": pl.Series([], dtype=pl.Utf8),
        "col3": pl.Series([], dtype=pl.Float64),
    })
    return df


@pytest.fixture
def test_csv_file(temp_dir):
    """Create a test CSV file"""
    import polars as pl

    csv_path = temp_dir / "test_data.csv"
    df = pl.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "value": [100, 200, 300],
    })
    df.write_csv(csv_path)
    return csv_path


@pytest.fixture
def test_parquet_file(temp_dir):
    """Create a test Parquet file"""
    import polars as pl

    parquet_path = temp_dir / "test_data.parquet"
    df = pl.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "value": [100, 200, 300],
    })
    df.write_parquet(parquet_path)
    return parquet_path


@pytest.fixture
def test_json_file(temp_dir):
    """Create a test JSON file"""
    import polars as pl

    json_path = temp_dir / "test_data.json"
    df = pl.DataFrame({
        "id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "value": [100, 200, 300],
    })
    df.write_json(json_path)
    return json_path
