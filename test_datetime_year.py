#!/usr/bin/env python3
"""Test datetime_year column naming"""
import sys
sys.path.insert(0, '.')

import polars as pl
from src.core.data_processor import DataProcessor, TransformationPipeline

def test_datetime_year_custom_output():
    df = pl.DataFrame({
        'Date': ['2023-01-01', '2023-02-15', '2024-12-31']
    }).with_columns(pl.col('Date').str.strptime(pl.Date, '%Y-%m-%d'))
    print("Original columns:", df.columns)

    processor = DataProcessor()

    # Test direct method
    params = {'column': 'Date', 'output_col': 'Year'}
    result = processor.extract_year(df, **params)
    print("Direct result columns:", result.columns)
    assert 'Year' in result.columns
    assert 'Date_year' not in result.columns

    # Test via apply_operation
    params2 = {'column': 'Date', 'output_col': 'MyYear'}
    result2 = processor.apply_operation(df, 'datetime_year', params2)
    print("Apply operation result columns:", result2.columns)
    assert 'MyYear' in result2.columns
    assert 'Date_year' not in result2.columns

    # Test pipeline
    pipeline = TransformationPipeline(df)
    created = pipeline.add_step('datetime_year', {'column': 'Date', 'output_col': 'PipelineYear'})
    print("Pipeline created columns:", created)
    result3 = pipeline.apply()
    print("Pipeline result columns:", result3.columns)
    assert 'PipelineYear' in result3.columns
    assert 'Date_year' not in result3.columns

    print("✓ All datetime_year tests passed")

if __name__ == '__main__':
    test_datetime_year_custom_output()