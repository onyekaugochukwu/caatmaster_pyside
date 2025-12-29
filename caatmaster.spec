"""
PyInstaller Spec File for CAATmaster
Creates a portable directory structure for Windows
"""
import sys
from pathlib import Path

# Project paths
project_root = Path(SPECPATH)
src_path = project_root / "src"
resources_path = project_root / "resources"

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(src_path), 'src'),
        (str(resources_path), 'resources') if resources_path.exists() else None,
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.orm',
        'polars',
        'openpyxl',
        'pandas',
        'numpy',
        'sklearn',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.backends.backend_wxagg',
        'IPython',
    ],
    noarchive=False,
    optimize=0,
)

# Filter out None values from datas
a.datas = [d for d in a.datas if d is not None]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CAATmaster',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path if available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CAATmaster',
)
