#!/usr/bin/env python3
"""
Build CAATmaster as an AppImage for Linux
Creates a single portable .AppImage file
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_build():
    """Clean previous build artifacts"""
    print("Cleaning previous build...")

    folders_to_clean = ['build', 'dist', 'AppDir']
    for folder in folders_to_clean:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"  Removed {folder}/")


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


def create_appimage():
    """Create AppImage from portable directory"""
    print("\nCreating AppImage...")

    dist_path = Path('dist/CAATmaster')
    if not dist_path.exists():
        print(f"  Error: {dist_path} not found")
        return False

    # Create AppDir structure
    appdir_path = Path('AppDir')
    if appdir_path.exists():
        shutil.rmtree(appdir_path)

    appdir_path.mkdir()
    (appdir_path / 'usr').mkdir()
    (appdir_path / 'usr' / 'bin').mkdir()
    (appdir_path / 'usr' / 'lib').mkdir()

    # Copy application files
    print("  Copying application files...")

    # Copy the main binary
    caatmaster_bin = dist_path / 'CAATmaster'
    if caatmaster_bin.exists():
        shutil.copy2(caatmaster_bin, appdir_path / 'usr' / 'bin' / 'CAATmaster')
        os.chmod(appdir_path / 'usr' / 'bin' / 'CAATmaster', 0o755)
    else:
        print(f"  Warning: CAATmaster binary not found")

    # Copy all internal files - PyInstaller's onedir bootloader looks
    # for _internal as a sibling of the executable, not under lib/.
    internal_path = dist_path / '_internal'
    if internal_path.exists():
        shutil.copytree(internal_path, appdir_path / 'usr' / 'bin' / '_internal')

    # Copy resources if they exist
    resources_src = Path('resources')
    if resources_src.exists():
        shutil.copytree(resources_src, appdir_path / 'usr' / 'share' / 'caatmaster' / 'resources')

    # Create AppRun script (the entry point)
    apprun_content = """#!/bin/bash
# AppRun - AppImage entry point for CAATmaster

self="$(readlink -f "$0")"
here="${self%/*}"
cd "${here}/usr/bin"

# Create data directory in user's home
DATA_DIR="${HOME}/.caatmaster"
mkdir -p "${DATA_DIR}"

# Set environment to use user data directory
export CAATMASTER_DATA_DIR="${DATA_DIR}"

# Run the application
exec "${here}/usr/bin/CAATmaster" "$@"
"""
    apprun_path = appdir_path / 'AppRun'
    with open(apprun_path, 'w') as f:
        f.write(apprun_content)
    os.chmod(apprun_path, 0o755)

    # Create .desktop file
    desktop_content = """[Desktop Entry]
Name=CAATmaster
Comment=Professional Continuous Audit Analytics Tool
Exec=CAATmaster
Icon=caatmaster
Type=Application
Categories=Office;Finance;Development;
Terminal=false
"""
    desktop_path = appdir_path / 'CAATmaster.desktop'
    with open(desktop_path, 'w') as f:
        f.write(desktop_content)

    # Create a simple icon (placeholder)
    # In production, you'd copy a real .png or .svg file
    icon_path = appdir_path / 'caatmaster.png'
    # Create a minimal 48x48 PNG icon (red square as placeholder)
    # This is just a placeholder - replace with real icon
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (48, 48), color='#0078d4')
        draw = ImageDraw.Draw(img)
        draw.rectangle([8, 8, 40, 40], fill='white', outline='white')
        draw.text((12, 16), "C", fill='#0078d4')
        img.save(icon_path)
    except ImportError:
        # PIL not available, create minimal SVG
        svg_path = appdir_path / 'caatmaster.svg'
        with open(svg_path, 'w') as f:
            f.write("""<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48">
<rect fill="#0078d4" width="48" height="48"/>
<text x="24" y="32" font-size="24" fill="white" text-anchor="middle">C</text>
</svg>""")
        if icon_path.exists():
            os.remove(icon_path)

    # Download appimagetool if not present
    appimagetool = Path('appimagetool-x86_64.AppImage')
    if not appimagetool.exists():
        print("\n  Downloading appimagetool...")
        subprocess.check_call([
            'wget',
            'https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage'
        ])
        os.chmod(appimagetool, 0o755)

    # Build AppImage
    print("\n  Building AppImage (this may take a minute)...")
    from datetime import datetime
    version = datetime.now().strftime("%Y.%m.%d")

    appimage_env = os.environ.copy()
    appimage_env['ARCH'] = 'x86_64'

    appimagetool_cmd = [
        str(appimagetool.resolve()),
        str(appdir_path),
        f'CAATmaster-{version}-x86_64.AppImage'
    ]

    result = subprocess.run(appimagetool_cmd, env=appimage_env, capture_output=True, text=True)

    if result.returncode != 0 and 'libfuse.so.2' in result.stderr:
        # No FUSE (common in containers/CI) - appimagetool's own
        # bundled runtime falls back to extracting itself instead of
        # mounting, which needs no FUSE at all.
        print("  FUSE not available, retrying with --appimage-extract-and-run...")
        result = subprocess.run(
            [appimagetool_cmd[0], '--appimage-extract-and-run'] + appimagetool_cmd[1:],
            env=appimage_env,
        )
    else:
        print(result.stdout)
        print(result.stderr)

    if result.returncode == 0:
        print(f"\n  ✓ Created: CAATmaster-{version}-x86_64.AppImage")
        return True
    else:
        print(f"\n  ✗ AppImage creation failed")
        return False


def main():
    """Main build process"""
    print("=" * 60)
    print("CAATmaster AppImage Builder")
    print("=" * 60)
    print()

    # Step 1: Clean
    clean_build()
    print()

    # Step 2: Install dependencies (optional)
    # install_dependencies()
    # print()

    # Step 3: Build portable
    build_portable()
    print()

    # Step 4: Create AppImage
    success = create_appimage()
    print()

    if success:
        print("=" * 60)
        print("AppImage build complete!")
        print()
        print("To run:")
        print("  chmod +x CAATmaster-*.AppImage")
        print("  ./CAATmaster-*.AppImage")
        print()
        print("Distribute the .AppImage file - no installation needed!")
        print("=" * 60)
    else:
        print("=" * 60)
        print("AppImage build failed. Portable directory still available at:")
        print("  dist/CAATmaster/")
        print("=" * 60)


if __name__ == '__main__':
    main()
