#!/usr/bin/env python3
"""
CaatMaster - Professional Continuous Audit Analytics Tool
PySide 6 Desktop Application
"""
import sys
import os
import signal
import faulthandler
from pathlib import Path
from PySide6.QtWidgets import QApplication, QToolTip
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QIcon, QPalette, QColor

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from gui.main_window import MainWindow
from gui.theme import get_stylesheet, Colors, load_bundled_fonts
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

    # Load the bundled Inter font before the stylesheet references it by
    # name — must happen after QApplication exists (Qt's font database
    # isn't available before that) and before setStyleSheet() below.
    load_bundled_fonts()

    # Apply the CaatMaster light theme — single source of truth for the
    # whole app's styling, see src/gui/theme.py
    app.setStyleSheet(get_stylesheet())

    # theme.py's QSS has a "QToolTip { background: dark; color: light }"
    # rule, but QToolTip keeps its OWN static palette completely separate
    # from QApplication's — confirmed directly: QToolTip.palette() stays
    # at Qt's default (#ffffdc background, black text) even after
    # app.setPalette() changes QApplication's palette. The QSS rule's
    # "color" property still reaches individual tooltips (white text),
    # but its "background-color" doesn't reliably repaint the tooltip
    # window under Fusion, which keeps drawing QToolTip's own palette
    # background underneath — white text on top of a near-white
    # background. Setting BOTH palettes explicitly, to the same colors,
    # is what actually fixes every tooltip regardless of which of the
    # two rendering paths a given widget's tooltip takes.
    palette = app.palette()
    palette.setColor(QPalette.ToolTipBase, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ToolTipText, QColor(Colors.BG_PRIMARY))
    app.setPalette(palette)

    tooltip_palette = QToolTip.palette()
    tooltip_palette.setColor(QPalette.ToolTipBase, QColor(Colors.TEXT_PRIMARY))
    tooltip_palette.setColor(QPalette.ToolTipText, QColor(Colors.BG_PRIMARY))
    QToolTip.setPalette(tooltip_palette)

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
        # Maximized, not true fullscreen - fills the screen but keeps the
        # title bar and minimize/restore/close buttons. True fullscreen
        # (Qt.WindowFullScreen) hides all window chrome, which left no way
        # to close or minimize the app at all - available via F11
        # (toggle_fullscreen) for anyone who wants it deliberately.
        #
        # Deferred by one event-loop turn rather than called inline: on
        # some Linux window managers, showMaximized() called on a window
        # that has never been mapped/shown yet gets silently ignored (the
        # WM has no valid geometry to maximize against) - the window ends
        # up shown at its small default size, only responding to a manual
        # click on the title bar's own Maximize button afterward. Letting
        # the window get mapped first, then requesting maximized state
        # on the next iteration, is the standard workaround.
        window.show()
        QTimer.singleShot(0, window.showMaximized)

        # Ctrl+C in the terminal otherwise surfaces as a confusing
        # traceback inside whatever unrelated Qt callback happens to be
        # running when the signal arrives (Qt's C++ event loop doesn't
        # hand control back to Python's interpreter often enough for the
        # default SIGINT handler to run promptly). Route it through
        # close() instead, so it gets the same unsaved-changes prompt as
        # File > Exit or the window's own close button - not an abrupt
        # kill. QTimer.singleShot(0, ...) defers the actual close to a
        # normal event-loop turn rather than doing GUI work inside the
        # raw signal handler itself. The periodic no-op timer just keeps
        # ticking the interpreter over so Python gets a chance to notice
        # the signal in the first place.
        def _handle_sigint(*_args):
            QTimer.singleShot(0, window.close)

        signal.signal(signal.SIGINT, _handle_sigint)
        _signal_pump = QTimer()
        _signal_pump.timeout.connect(lambda: None)
        _signal_pump.start(200)

        sys.exit(app.exec())
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
