#!/usr/bin/env python3
"""
CaatMaster - Professional Continuous Audit Analytics Tool
PySide 6 Desktop Application
"""
import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from gui.main_window import MainWindow
from core.database import init_db


def main():
    """Main application entry point"""
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

    # Load and apply the dark theme stylesheet
    try:
        theme_path = Path(__file__).parent / "src" / "gui" / "themes" / "dark_theme.qss"
        with open(theme_path, "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Warning: Stylesheet 'dark_theme.qss' not found. Using default style.")

    # Initialize database
    try:
        init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Warning: Database initialization failed: {e}")

    # Create and show main window in maximized mode
    window = MainWindow()
    window.showMaximized()

    # Start event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
