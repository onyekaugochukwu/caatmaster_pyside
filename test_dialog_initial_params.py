#!/usr/bin/env python3
"""Test initial_params generation in transform_view.py"""
import sys
sys.path.insert(0, '.')

from src.core.operation_registry import OPERATION_REGISTRY

def simulate_initial_params(operation_id, column_name):
    """Simulate transform_view.py logic for generating initial_params"""
    op_data = OPERATION_REGISTRY[operation_id]

    # Prepare initial parameters
    initial_params = {'column': column_name}

    # Set default output column name(s) based on operation
    creates_columns = op_data.get('creates_columns', False)
    if creates_columns:
        if isinstance(creates_columns, list):
            # Multiple columns created - generate output_cols list
            output_cols = [col_name.format(column=column_name) for col_name in creates_columns]
            initial_params['output_cols'] = output_cols
            # If only one column, also set output_col for backward compatibility
            if len(output_cols) == 1:
                initial_params['output_col'] = output_cols[0]
        else:
            # Single column created - generate output_col
            naming_pattern = op_data.get('column_naming_pattern', '{column}_{operation}')
            operation_name = operation_id.split('_')[-1]
            initial_params['output_col'] = naming_pattern.format(column=column_name, operation=operation_name)

    return initial_params

def test_datetime_year():
    """Test datetime_year initial params"""
    params = simulate_initial_params('datetime_year', 'Date')
    print(f"datetime_year params: {params}")
    assert 'output_col' in params, "Should have output_col"
    assert params['output_col'] == 'Date_year', f"Expected Date_year, got {params['output_col']}"
    assert 'output_cols' not in params, "Should not have output_cols for single column operation"
    print("✓ datetime_year passes")

def test_text_lowercase():
    """Test text_lowercase initial params (was list, now True)"""
    params = simulate_initial_params('text_lowercase', 'Customer')
    print(f"text_lowercase params: {params}")
    assert 'output_col' in params, "Should have output_col"
    assert params['output_col'] == 'Customer_lower', f"Expected Customer_lower, got {params['output_col']}"
    assert 'output_cols' not in params, "Should not have output_cols for single column operation"
    print("✓ text_lowercase passes")

def test_text_split():
    """Test a multi-column operation (if exists)"""
    # Find an operation with creates_columns as list with multiple elements
    multi_col_ops = []
    for op_id, op_data in OPERATION_REGISTRY.items():
        creates = op_data.get('creates_columns', False)
        if isinstance(creates, list) and len(creates) > 1:
            multi_col_ops.append(op_id)

    if multi_col_ops:
        op_id = multi_col_ops[0]
        params = simulate_initial_params(op_id, 'Column')
        print(f"{op_id} params: {params}")
        assert 'output_cols' in params, f"Should have output_cols for multi-column operation {op_id}"
        assert isinstance(params['output_cols'], list), "output_cols should be a list"
        print(f"✓ {op_id} passes")
    else:
        print("No multi-column operations found to test")

def test_operation_registry_consistency():
    """Check that all operations with creates_columns=True have column_naming_pattern"""
    issues = []
    for op_id, op_data in OPERATION_REGISTRY.items():
        creates = op_data.get('creates_columns', False)
        if creates is True:
            if 'column_naming_pattern' not in op_data:
                issues.append(f"{op_id}: missing column_naming_pattern")

    if issues:
        print("Registry consistency issues:")
        for issue in issues:
            print(f"  {issue}")
        raise AssertionError("Registry inconsistent")
    else:
        print("✓ All creates_columns=True operations have column_naming_pattern")

if __name__ == '__main__':
    print("Testing initial_params generation...")
    test_datetime_year()
    print()
    test_text_lowercase()
    print()
    test_text_split()
    print()
    test_operation_registry_consistency()
    print("\nAll tests passed!")