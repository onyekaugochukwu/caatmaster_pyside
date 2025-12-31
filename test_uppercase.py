#!/usr/bin/env python3
"""Test uppercase column naming issue"""
import sys
sys.path.insert(0, '.')

import polars as pl
from src.core.data_processor import DataProcessor

def test_uppercase_custom_output_col():
    """Test that uppercase uses custom output column name"""
    df = pl.DataFrame({
        'Customer': ['Alice', 'Bob', 'Charlie'],
        'Date': ['2023-01-01', '2023-01-02', '2023-01-03']
    })
    print("Original columns:", df.columns)

    processor = DataProcessor()

    # Simulate uppercase with custom output column name
    params = {
        'column': 'Customer',
        'output_col': 'Uppercase'  # User-provided name
    }

    result = processor.uppercase(df, **params)
    print("Result columns:", result.columns)
    print("Result dataframe:")
    print(result)

    # Check that new column exists with custom name
    assert 'Uppercase' in result.columns, f"Expected 'Uppercase' in columns, got {result.columns}"
    assert 'Customer_upper' not in result.columns, f"Unexpected 'Customer_upper' in columns"

    # Check that original column still exists
    assert 'Customer' in result.columns

    print("✓ Test passed: custom output column name used")

def test_uppercase_default_output_col():
    """Test uppercase with default naming pattern"""
    df = pl.DataFrame({
        'Customer': ['Alice', 'Bob', 'Charlie']
    })

    processor = DataProcessor()

    # Simulate uppercase without output_col (should use default)
    params = {
        'column': 'Customer'
    }

    # This should fail because uppercase expects output_col parameter
    # Actually apply_operation generates output_col if missing
    # Let's test via apply_operation
    result = processor.apply_operation(df, 'text_uppercase', params)
    print("Default result columns:", result.columns)
    assert 'Customer_upper' in result.columns
    print("✓ Default naming works")

def test_apply_operation_with_custom_output_col():
    """Test apply_operation with custom output_col"""
    df = pl.DataFrame({
        'Customer': ['Alice', 'Bob', 'Charlie']
    })

    processor = DataProcessor()

    # Provide output_col, should be used
    params = {
        'column': 'Customer',
        'output_col': 'MyUppercase'
    }

    result = processor.apply_operation(df, 'text_uppercase', params)
    print("Apply operation result columns:", result.columns)
    assert 'MyUppercase' in result.columns
    assert 'Customer_upper' not in result.columns
    print("✓ apply_operation respects custom output_col")

if __name__ == '__main__':
    print("Testing uppercase column naming...")
    test_uppercase_custom_output_col()
    print()
    test_uppercase_default_output_col()
    print()
    test_apply_operation_with_custom_output_col()
    print("\nAll tests passed!")