#!/usr/bin/env python3
"""Test pipeline uppercase column naming issue"""
import sys
sys.path.insert(0, '.')

import polars as pl
from src.core.data_processor import TransformationPipeline

def test_pipeline_uppercase_custom_output():
    """Test that pipeline uses custom output column name"""
    df = pl.DataFrame({
        'Customer': ['Alice', 'Bob', 'Charlie'],
        'Date': ['2023-01-01', '2023-01-02', '2023-01-03']
    })
    print("Original columns:", df.columns)

    pipeline = TransformationPipeline(df)

    # Simulate adding a step with custom output column name
    params = {
        'column': 'Customer',
        'output_col': 'Uppercase'  # User-provided name
    }

    created = pipeline.add_step('text_uppercase', params)
    print("Created columns:", created)

    result = pipeline.apply()
    print("Result columns:", result.columns)
    print("Result dataframe:")
    print(result)

    # Check that new column exists with custom name
    assert 'Uppercase' in result.columns, f"Expected 'Uppercase' in columns, got {result.columns}"
    assert 'Customer_upper' not in result.columns, f"Unexpected 'Customer_upper' in columns"

    # Check that original column still exists
    assert 'Customer' in result.columns

    # Check that pipeline's column tracking knows about the custom name
    col_info = pipeline.get_column_info('Uppercase')
    assert col_info is not None, "Column info not found for 'Uppercase'"
    print("Column info:", col_info)
    assert col_info['operation'] == 'text_uppercase'
    assert col_info['params']['output_col'] == 'Uppercase'

    print("✓ Pipeline test passed: custom output column name used")

def test_pipeline_uppercase_default_output():
    """Test pipeline with default naming pattern"""
    df = pl.DataFrame({
        'Customer': ['Alice', 'Bob', 'Charlie']
    })

    pipeline = TransformationPipeline(df)

    # Add step without output_col (should be generated)
    params = {
        'column': 'Customer'
    }

    created = pipeline.add_step('text_uppercase', params)
    print("Default created columns:", created)
    result = pipeline.apply()
    print("Default result columns:", result.columns)
    assert 'Customer_upper' in result.columns
    print("✓ Default naming works in pipeline")

if __name__ == '__main__':
    print("Testing pipeline uppercase column naming...")
    test_pipeline_uppercase_custom_output()
    print()
    test_pipeline_uppercase_default_output()
    print("\nAll pipeline tests passed!")