#!/usr/bin/env python3
"""
Build script for CAATmaster on macOS
Creates a CAATmaster.app bundle using PyInstaller
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_build():
    """Clean previous build artifacts"""
    print("Cleaning previous build...")

    folders_to_clean = ['build', 'dist']
    for folder in folders_to_clean:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"  Removed {folder}/")

    for f in Path('.').glob('*.pyc'):
        f.unlink()
    print("  Cleaned .pyc files")


def build_app():
    """Build CAATmaster.app using PyInstaller"""
    print("Building CAATmaster.app with PyInstaller...")

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        'caatmaster.spec',
    ]

    subprocess.check_call(cmd)


def create_readme():
    """Create a README next to the .app bundle"""
    print("Creating README...")

    dist_path = Path('dist')
    app_path = dist_path / 'CAATmaster.app'
    if not app_path.exists():
        print(f"  Warning: {app_path} not found")
        return

    readme_content = """# CAATmaster

Professional Continuous Audit Analytics Tool - Desktop Version

## Quick Start

Double-click `CAATmaster.app` to launch.

This build is not code-signed or notarized, so the first launch will
be blocked by Gatekeeper ("CAATmaster.app is damaged and can't be
opened" or "cannot be opened because the developer cannot be
verified"). To run it anyway, either:

- Right-click (or Control-click) `CAATmaster.app` and choose "Open",
  then confirm in the dialog that appears - this only needs to be
  done once, or
- Run `xattr -cr CAATmaster.app` in Terminal from this directory to
  clear the quarantine attribute, then open it normally.

## First Run

The application creates a `~/.caatmaster` directory containing:
- `data/caatmaster.db` - SQLite database with all your projects and data

## System Requirements

- macOS 12 (Monterey) or later, Apple Silicon or Intel
- No additional dependencies required (all bundled)
- Approximately 500MB free disk space

## Support

For issues or questions, please refer to the documentation.
"""
    readme_path = dist_path / 'README.txt'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"  Created {readme_path}")


def create_archive():
    """Create a zip archive of the .app bundle"""
    print("Creating archive...")

    dist_path = Path('dist')
    app_path = dist_path / 'CAATmaster.app'
    if not app_path.exists():
        print(f"  Warning: {app_path} not found")
        return

    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d")
    archive_name = f"CAATmaster_macOS_{timestamp}.zip"

    # ditto preserves the .app bundle's structure (symlinks, code
    # signature placeholders, resource forks) the way macOS expects -
    # Python's zipfile module does not handle bundle metadata the same
    # way and can produce an app that Gatekeeper/Finder mishandles.
    subprocess.check_call([
        'ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
        str(app_path), archive_name,
    ])
    readme_path = dist_path / 'README.txt'
    if readme_path.exists():
        subprocess.check_call(['zip', '-j', archive_name, str(readme_path)])

    print(f"  Created {archive_name}")


def main():
    """Main build process"""
    print("=" * 60)
    print("CAATmaster macOS Build Script")
    print("=" * 60)
    print()

    clean_build()
    print()

    build_app()
    print()

    create_readme()
    print()

    create_archive()
    print()

    print("=" * 60)
    print("Build complete!")
    print(f"App bundle: dist/CAATmaster.app")
    print()
    print("To run:")
    print("  open dist/CAATmaster.app")
    print("=" * 60)


if __name__ == '__main__':
    main()
