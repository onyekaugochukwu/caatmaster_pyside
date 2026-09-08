"""
PyInstaller spec file for CAATmaster.
Builds a portable onedir distribution (Windows/Linux/macOS).
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
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
