#!/usr/bin/env python3
"""
Universal build script for CAATmaster
Automatically detects platform and builds appropriately

Usage:
    python build.py              # Auto-detect platform
    python build.py --type=portable  # Force portable
    python build.py --type=onefile   # Force single file (Windows)
    python build.py --type=appimage  # Force AppImage (Linux)
"""
import os
import sys
import platform
import subprocess
from pathlib import Path


def detect_platform():
    """Detect the current platform"""
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Linux":
        return "linux"
    elif system == "Darwin":
        return "macos"
    else:
        return "unknown"


def parse_args():
    """Parse command line arguments"""
    args = {
        'type': None,  # portable, onefile, appimage
        'clean': True,
    }

    for arg in sys.argv[1:]:
        if arg.startswith('--type='):
            args['type'] = arg.split('=')[1]
        elif arg == '--no-clean':
            args['clean'] = False
        elif arg in ['--help', '-h']:
            print(__doc__)
            sys.exit(0)

    return args


def main():
    """Main build process"""
    print("=" * 70)
    print("CAATmaster Universal Build Script")
    print("=" * 70)
    print()

    # Parse arguments
    args = parse_args()

    # Detect platform
    system = detect_platform()
    print(f"Detected Platform: {platform.system()} ({platform.machine()})")
    print()

    # Clean if requested
    if args['clean']:
        print("Cleaning previous build...")
        folders = ['build', 'dist', 'AppDir']
        for folder in folders:
            if Path(folder).exists():
                import shutil
                shutil.rmtree(folder)
                print(f"  Removed {folder}/")
        print()

    # Determine build type
    build_type = args['type']

    if build_type is None:
        # Auto-select based on platform
        if system == "windows":
            build_type = "portable"  # Default for Windows
        elif system == "linux":
            build_type = "appimage"  # Best for Linux
        elif system == "macos":
            build_type = "portable"  # macOS
        else:
            build_type = "portable"

    print(f"Build Type: {build_type}")
    print()

    # Execute appropriate build
    if system == "windows":
        if build_type == "onefile":
            print("Building single .exe for Windows...")
            env = os.environ.copy()
            env['CAATMASTER_ONEFILE'] = '1'
            subprocess.check_call(
                [sys.executable, '-m', 'PyInstaller', '--clean', 'caatmaster.spec'],
                env=env,
            )
        else:
            # Use build_windows.py for portable
            subprocess.check_call([sys.executable, 'build_windows.py'])

    elif system == "linux":
        if build_type == "appimage":
            print("Building AppImage for Linux...")
            subprocess.check_call([sys.executable, 'build_appimage.py'])
        else:
            print("Building portable directory for Linux...")
            subprocess.check_call([sys.executable, 'build_linux.py'])

    elif system == "macos":
        print("Building for macOS...")
        print("Note: macOS builds require a Mac. Using portable directory approach.")
        subprocess.check_call([sys.executable, 'build_linux.py'])  # Reuse Linux script

    else:
        print(f"Error: Unknown platform {system}")
        print("Please use platform-specific build script:")
        print("  Windows: build_windows.py")
        print("  Linux:   build_linux.py or build_appimage.py")
        sys.exit(1)

    print()
    print("=" * 70)
    print("Build complete!")
    print()
    print("Output location: dist/")
    print("=" * 70)


if __name__ == '__main__':
    main()
