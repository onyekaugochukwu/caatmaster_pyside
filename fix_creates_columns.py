#!/usr/bin/env python3
"""Fix single-element creates_columns lists in operation_registry.py"""
import re
import sys

def fix_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Pattern to find "creates_columns": ["{col}_something"]
    # Single element only
    pattern = r'("creates_columns":\s*\["\{col\}_([^"]+)"\])'

    def replace_match(match):
        original = match.group(1)
        suffix = match.group(2)
        return f'"creates_columns": True,\n        "column_naming_pattern": "{{col}}_{suffix}"'

    new_content = re.sub(pattern, replace_match, content)

    # Write back
    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f"Fixed {len(re.findall(pattern, content))} occurrences")

    # Show what changed
    old_lines = content.split('\n')
    new_lines = new_content.split('\n')
    for i, (old_line, new_line) in enumerate(zip(old_lines, new_lines)):
        if old_line != new_line:
            print(f"Line {i+1}:")
            print(f"  Old: {old_line}")
            print(f"  New: {new_line}")

if __name__ == '__main__':
    fix_file('src/core/operation_registry.py')