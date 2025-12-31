#!/usr/bin/env python3
"""Replace {col} with {column} in creates_columns lists"""
import re

def fix_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Replace "{col}_" with "{column}_" but only within creates_columns lists
    # We'll do a simple global replace since all {col} are in creates_columns
    # and we already fixed column_naming_pattern
    new_content = content.replace('"{col}_', '"{column}_')

    # Write back
    with open(file_path, 'w') as f:
        f.write(new_content)

    print("Fixed {col} in creates_columns lists")

    # Show diff
    old_lines = content.split('\n')
    new_lines = new_content.split('\n')
    for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
        if old_line != new_line:
            print(f"Line {i+1}: {old_line} -> {new_line}")

if __name__ == '__main__':
    fix_file('src/core/operation_registry.py')