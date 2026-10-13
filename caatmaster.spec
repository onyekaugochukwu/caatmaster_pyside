"""
PyInstaller spec file for CAATmaster.
Builds a portable onedir distribution (Windows/Linux/macOS), or a
single-file executable if the CAATMASTER_ONEFILE environment variable
is set to "1" before invoking PyInstaller on this spec.
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

ONEFILE = os.environ.get('CAATMASTER_ONEFILE') == '1'

project_root = Path(SPECPATH)
src_path = project_root / "src"
resources_path = project_root / "resources"

block_cipher = None

hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.orm',
    'polars',
    'openpyxl',
    'xlsxwriter',
    'xlrd',
    'docx',
    'pypdf',
    'fastexcel',
    'duckdb',
    'pyarrow',
    'pandas',
    'numpy',
    'keyring',
    'keyring.backends',
    'keyring.backends.Windows',
    'keyring.backends.macOS',
    'keyring.backends.SecretService',
    'jwt',
    'qtawesome',
    'qtpy',
]

datas = [
    (str(src_path), 'src'),
]
if resources_path.exists():
    datas.append((str(resources_path), 'resources'))

binaries = []

# arelle does its own plugin/module discovery at runtime (XBRL/iXBRL
# validation plugins), which PyInstaller's static import analysis
# cannot follow - it needs its submodules and data files collected
# explicitly.
hiddenimports += collect_submodules('arelle')

# passlib's argon2 handler and CryptContext are reached through
# lazy/dynamic lookups that PyInstaller's static analysis misses.
hiddenimports += collect_submodules('passlib')

# The AI provider SDKs (openai, anthropic, google-generativeai,
# huggingface_hub) are only ever imported lazily from inside
# src/services/ai_service.py - and src/ ships as plain data (see `datas`
# below), loaded at runtime via sys.path.insert() in main.py, not through
# PyInstaller's static Analysis of main.py's own import graph. So none of
# these packages were ever discovered automatically and were silently
# left out of the frozen build entirely, which surfaced as every AI
# provider failing with "Failed to initialize provider client" (the
# generic message ai_service.py's `except ImportError` handlers produce)
# even with a correct, working API key.
for pkg in ['openai', 'anthropic', 'google.generativeai', 'huggingface_hub']:
    hiddenimports += collect_submodules(pkg)

datas += collect_data_files('arelle')
# qtawesome's font/charmap data files are collected by PyInstaller's
# own built-in hook-qtawesome.py - collecting them again here (even to
# the same destination) previously produced a duplicate 'qtawesome'
# entry that shadowed the real package with an empty namespace
# package, silently losing every qta.icon() call.

# cryptography ships compiled Rust extension modules
# (cryptography.hazmat.bindings._rust) that plain hiddenimports does
# not pull in - collect_all grabs its binaries and datas too.
for pkg in ['cryptography']:
    pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hiddenimports

a = Analysis(
    ['main.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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

pyz = PYZ(a.pure)

exe_kwargs = dict(
    name='CAATmaster',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

if ONEFILE:
    # Everything (binaries + datas) goes into the single EXE; there is
    # no separate COLLECT step and no _internal/ directory - PyInstaller
    # extracts to a temp dir (sys._MEIPASS) at each launch instead.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        exclude_binaries=False,
        **exe_kwargs,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        **exe_kwargs,
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

    if sys.platform == 'darwin':
        app = BUNDLE(
            coll,
            name='CAATmaster.app',
            icon=None,
            bundle_identifier='com.caatmaster.app',
            info_plist={
                'NSHighResolutionCapable': True,
                'CFBundleShortVersionString': '0.1.0',
            },
        )
