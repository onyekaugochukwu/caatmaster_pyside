#!/usr/bin/env python3
"""Fix column naming patterns to use {column} instead of {col}"""
import re

def fix_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Replace {col} with {column} in column_naming_pattern values
    # Pattern: "column_naming_pattern": "{col}_something"
    pattern = r'("column_naming_pattern":\s*)"\{col\}([^"]*)"'

    def replace_match(match):
        return f'{match.group(1)}"{{column}}{match.group(2)}"'

    new_content = re.sub(pattern, replace_match, content)

    # Also replace in creates_columns lists if any remain
    pattern2 = r'("creates_columns":\s*\[)"\{col\}([^"]*)"(\])'
    def replace_match2(match):
        return f'{match.group(1)}"{{column}}{match.group(2)}"{match.group(3)}'

    new_content = re.sub(pattern2, replace_match2, new_content)

    # Write back
    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f"Fixed patterns")

    # Show changes
    import difflib
    old_lines = content.split('\n')
    new_lines = new_content.split('\n')
    diff = difflib.unified_diff(old_lines, new_lines, lineterm='')
    for line in list(diff)[:50]:  # Show first 50 lines
        print(line)

if __name__ == '__main__':
    fix_file('src/core/operation_registry.py')