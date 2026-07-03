#!/usr/bin/env python3
"""
CaatMaster - Professional Continuous Audit Analytics Tool
PySide 6 Desktop Application
"""
import sys
import os
import faulthandler
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from gui.main_window import MainWindow
from gui.theme import get_stylesheet
from core.database import init_db


def _enable_crash_logging():
    """Native crashes (segfaults) don't produce a Python traceback by
    default — faulthandler writes one to a log file when the process
    receives a fatal signal, which is the only way to pinpoint where a
    segfault actually happened rather than guessing from symptoms."""
    log_dir = Path.home() / ".caatmaster"
    log_dir.mkdir(parents=True, exist_ok=True)
    crash_log = open(log_dir / "crash_log.txt", "a")
    faulthandler.enable(file=crash_log)
    return crash_log  # keep a reference alive for the process lifetime


def main():
    """Main application entry point"""
    _crash_log_handle = _enable_crash_logging()

    # Set high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("CaatMaster")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("CaatMaster")

    # Set application style
    app.setStyle("Fusion")

    # Apply the CaatMaster light theme — single source of truth for the
    # whole app's styling, see src/gui/theme.py
    app.setStyleSheet(get_stylesheet())

    # Initialize database
    try:
        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")

    # Create main window (this will show login dialog)
    # If login is cancelled, the app will exit during initialization
    window = MainWindow()

    # Check if login was successful
    # If login was cancelled, _login_successful will be False
    if getattr(window, '_login_successful', False):
        window.showMaximized()
        sys.exit(app.exec())
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
