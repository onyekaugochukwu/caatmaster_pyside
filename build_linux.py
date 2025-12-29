#!/usr/bin/env python3
"""
Build script for CAATmaster on Linux
Creates a portable directory using PyInstaller
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

    # Clean spec file artifacts
    for f in Path('.').glob('*.pyc'):
        f.unlink()
    print("  Cleaned .pyc files")


def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])


def build_portable():
    """Build portable directory using PyInstaller"""
    print("Building portable directory with PyInstaller...")

    # Build command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        'caatmaster.spec',
    ]

    subprocess.check_call(cmd)


def create_launcher():
    """Create Linux launcher scripts"""
    print("Creating Linux launcher scripts...")

    dist_path = Path('dist/CAATmaster')
    if not dist_path.exists():
        print(f"  Warning: {dist_path} not found")
        return

    # Shell script launcher
    sh_content = """#!/bin/bash
# CAATmaster Launcher
# Creates data directory and launches app

mkdir -p data
./CAATmaster
"""
    sh_path = dist_path / 'start.sh'
    with open(sh_path, 'w') as f:
        f.write(sh_content)

    # Make executable
    os.chmod(sh_path, 0o755)
    print(f"  Created {sh_path}")

    # Create README in distribution
    readme_content = """# CAATmaster

Professional Continuous Audit Analytics Tool - Desktop Version

## Quick Start

1. Open terminal and run `./start.sh` to launch
2. Or double-click `CAATmaster` executable
3. Or run `./CAATmaster` directly

## First Run

The application will create a `data/` directory on first run containing:
- `caatmaster.db` - SQLite database with all your projects and data

## System Requirements

- Linux with glibc 2.17+ (or compatible)
- No additional dependencies required (all bundled)
- Approximately 500MB free disk space

## Tested On

- Ubuntu 20.04+
- Debian 11+
- Fedora 35+
- Arch Linux

Should work on most modern Linux distributions.

## File Locations

- Application files: Current directory
- User data: `data/` subdirectory
- Database: `data/caatmaster.db`

## Support

For issues or questions, please refer to the documentation.
"""
    readme_path = dist_path / 'README.txt'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"  Created {readme_path}")


def create_archive():
    """Create a tar.gz archive of the portable directory"""
    print("Creating portable archive...")

    dist_path = Path('dist/CAATmaster')
    if not dist_path.exists():
        print(f"  Warning: {dist_path} not found")
        return

    import tarfile
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d")
    archive_name = f"CAATmaster_Linux_Portable_{timestamp}.tar.gz"

    with tarfile.open(archive_name, "w:gz") as tar:
        tar.add(dist_path, arcname="CAATmaster")

    print(f"  Created {archive_name}")


def create_appimage():
    """
    Optional: Create an AppImage (requires appimage-builder)
    This is more advanced and optional
    """
    print("\nNote: AppImage creation requires appimage-builder (optional)")
    print("To install: pip install appimage-builder")
    print("This feature is not enabled by default")


def main():
    """Main build process"""
    print("=" * 60)
    print("CAATmaster Linux Build Script")
    print("=" * 60)
    print()

    # Step 1: Clean
    clean_build()
    print()

    # Step 2: Install dependencies (optional - comment out if already installed)
    # install_dependencies()
    # print()

    # Step 3: Build
    build_portable()
    print()

    # Step 4: Create launchers
    create_launcher()
    print()

    # Step 5: Create archive (optional - comment out if not needed)
    create_archive()
    print()

    print("=" * 60)
    print("Build complete!")
    print(f"Portable directory: dist/CAATmaster/")
    print()
    print("To run:")
    print("  cd dist/CAATmaster")
    print("  ./start.sh")
    print("=" * 60)


if __name__ == '__main__':
    main()
