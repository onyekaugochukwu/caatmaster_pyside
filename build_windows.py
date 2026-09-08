#!/usr/bin/env python3
"""
Build script for CAATmaster on Windows
Creates either a portable directory or single .exe file
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path


# =============================================================================
# CONFIGURATION
# =============================================================================
BUILD_TYPE = "portable"  # Options: "portable" or "onefile"

# =============================================================================
# BUILD FUNCTIONS
# =============================================================================

def clean_build():
    """Clean previous build artifacts"""
    print("Cleaning previous build...")

    folders_to_clean = ['build', 'dist']
    for folder in folders_to_clean:
        folder_path = Path(folder)
        if folder_path.exists():
            shutil.rmtree(folder_path)
            print(f"  Removed {folder}/")

    # Clean spec file artifacts
    for pyc_file in Path('.').glob('*.pyc'):
        pyc_file.unlink()
    print("  Cleaned .pyc files")


def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])


def build_portable():
    """Build portable directory using PyInstaller (default)"""
    print("Building portable directory with PyInstaller...")

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        'caatmaster.spec',
    ]

    subprocess.check_call(cmd)


def build_onefile():
    """Build single .exe file using PyInstaller"""
    print("Building single .exe file with PyInstaller...")
    print("Note: First launch may be slower (extracting to temp)...")

    # Reuses caatmaster.spec (the same dependency list as the portable
    # build) rather than a separate, hand-maintained set of PyInstaller
    # CLI flags - the latter previously drifted out of date and was
    # missing most of the app's actual hidden imports (arelle, keyring,
    # passlib, cryptography, qtawesome) and the resources/ directory.
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        'caatmaster.spec',
    ]

    env = os.environ.copy()
    env['CAATMASTER_ONEFILE'] = '1'
    subprocess.check_call(cmd, env=env)


def create_launcher_portable():
    """Create launcher scripts for portable directory build"""
    print("Creating launcher scripts...")

    dist_path = Path('dist/CAATmaster')
    if not dist_path.exists():
        print(f"  Warning: {dist_path} not found")
        return

    # Windows batch file
    bat_content = """@echo off
REM CAATmaster Launcher
REM Creates data directory and launches app

setlocal

REM Create data directory
if not exist "data" mkdir data

REM Set data directory environment variable
set CAATMASTER_DATA_DIR=%~dp0data

REM Launch application
start "" "CAATmaster.exe"

endlocal
"""
    bat_path = dist_path / 'start.bat'
    with open(bat_path, 'w') as f:
        f.write(bat_content)
    print(f"  Created {bat_path}")

    # PowerShell launcher (alternative)
    ps1_content = """# CAATmaster PowerShell Launcher
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path

# Create data directory
$DataDir = Join-Path $ScriptPath "data"
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
}

# Set environment and launch
$env:CAATMASTER_DATA_DIR = $DataDir
Start-Process (Join-Path $ScriptPath "CAATmaster.exe")
"""
    ps1_path = dist_path / 'start.ps1'
    with open(ps1_path, 'w') as f:
        f.write(ps1_content)
    print(f"  Created {ps1_path}")

    # Create README
    readme_content = """# CAATmaster

Professional Continuous Audit Analytics Tool - Desktop Version

## Quick Start

**Option 1:** Double-click `start.bat`
**Option 2:** Right-click `start.ps1` → Run with PowerShell
**Option 3:** Double-click `CAATmaster.exe` directly

## First Run

The application will create a `data/` directory containing:
- `caatmaster.db` - SQLite database with all your projects and data

## System Requirements

- Windows 10 or later (64-bit)
- No additional dependencies required (all bundled)
- Approximately 300MB free disk space

## File Locations

- Application: Current directory
- User data: `data/` subdirectory
- Database: `data/caatmaster.db`

## Notes

- All settings and data are stored in the `data/` folder
- To move to another computer, copy the entire folder
- To uninstall, simply delete the folder

## Support

For issues or questions, please refer to the documentation.
"""
    readme_path = dist_path / 'README.txt'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"  Created {readme_path}")


def create_launcher_onefile():
    """Create launcher scripts for single-file build"""
    print("Creating launcher for single .exe...")

    dist_path = Path('dist')
    exe_path = dist_path / 'CAATmaster.exe'

    if not exe_path.exists():
        print(f"  Warning: {exe_path} not found")
        return

    # For onefile, data is stored in AppData
    bat_content = """@echo off
REM CAATmaster Launcher (Single File Version)
REM Data is stored in %APPDATA%\\CAATmaster

setlocal
set CAATMASTER_DATA_DIR=%APPDATA%\\CAATmaster
start "" "CAATmaster.exe"
endlocal
"""
    bat_path = dist_path / 'start.bat'
    with open(bat_path, 'w') as f:
        f.write(bat_content)
    print(f"  Created {bat_path}")

    readme_content = """# CAATmaster (Single File Version)

Professional Continuous Audit Analytics Tool

## Quick Start

Double-click `CAATmaster.exe` to launch

## Data Storage

Your data is stored in:
```
%APPDATA%\\CAATmaster\\
```

To find this folder:
1. Press Win+R
2. Type: %APPDATA%\\CAATmaster
3. Press Enter

## System Requirements

- Windows 10 or later (64-bit)
- No additional dependencies required

## Notes

- First launch may take a few seconds (extracting bundled files)
- All data persists in AppData even if you move the .exe
- Portable: you can run from USB drive, downloads folder, etc.

## Support

For issues or questions, please refer to the documentation.
"""
    readme_path = dist_path / 'README.txt'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"  Created {readme_path}")


def create_archive():
    """Create a ZIP archive"""
    print("Creating portable archive...")

    if BUILD_TYPE == "portable":
        dist_path = Path('dist/CAATmaster')
        archive_name = "CAATmaster_Win_Portable.zip"
    else:
        dist_path = Path('dist')
        # Only archive the .exe and readme for onefile
        archive_name = "CAATmaster_Win_SingleFile.zip"

    if not dist_path.exists():
        print(f"  Warning: {dist_path} not found")
        return

    import zipfile
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d")
    archive_name = archive_name.replace('.zip', f'_{timestamp}.zip')

    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        if BUILD_TYPE == "portable":
            for file in dist_path.rglob('*'):
                if file.is_file():
                    arcname = f"CAATmaster/{file.relative_to(dist_path)}"
                    zipf.write(file, arcname)
        else:
            # For onefile, just zip exe and readme
            exe_file = dist_path / 'CAATmaster.exe'
            readme_file = dist_path / 'README.txt'
            if exe_file.exists():
                zipf.write(exe_file, 'CAATmaster.exe')
            if readme_file.exists():
                zipf.write(readme_file, 'README.txt')

    print(f"  Created {archive_name}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main build process"""
    print("=" * 70)
    print("CAATmaster Windows Build Script")
    print("=" * 70)
    print(f"\nBuild Type: {BUILD_TYPE}")
    print()

    if BUILD_TYPE == "portable":
        print("Creating portable directory (multiple files, faster startup)")
    else:
        print("Creating single .exe file (slower startup, easier distribution)")
    print()

    # Step 1: Clean
    clean_build()
    print()

    # Step 2: Install dependencies (optional - comment out if already installed)
    # install_dependencies()
    # print()

    # Step 3: Build
    if BUILD_TYPE == "portable":
        build_portable()
    else:
        build_onefile()
    print()

    # Step 4: Create launchers
    if BUILD_TYPE == "portable":
        create_launcher_portable()
    else:
        create_launcher_onefile()
    print()

    # Step 5: Create archive
    create_archive()
    print()

    # Summary
    print("=" * 70)
    print("Build complete!")
    print()
    if BUILD_TYPE == "portable":
        print(f"Output: dist/CAATmaster/")
        print()
        print("Distribution: Share the entire 'CAATmaster' folder or the ZIP file")
    else:
        print(f"Output: dist/CAATmaster.exe")
        print()
        print("Distribution: Share just the .exe file (or the ZIP)")
    print("=" * 70)


if __name__ == '__main__':
    main()
