"""
Menu-to-handler wiring audit.

This exists because of a real, recurring failure mode found twice in this
codebase: an action_id gets added to a menu structure in app_menu.py, but
the corresponding entry in MainWindow.handle_ribbon_action's own
action_handlers dict is never added alongside it. Unlike a missing dialog
mapping (covered by test_dialog_audit.py), this fails completely silently
- handle_ribbon_action's fallback branch just posts a status bar message
("Action 'x' not yet implemented") and returns, with no dialog, no
exception, and no visible sign anything went wrong. A reviewer clicking
the menu item sees nothing happen and has no way to tell a real feature
is missing from a slightly slow one.

Every action_id declared anywhere in app_menu.py's menu trees is checked
here against the real handle_ribbon_action dispatch, using the app's own
menu-building code as the source of truth rather than a hand-maintained
list that would drift from it.
"""
import pytest
import polars as pl
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QFileDialog


@pytest.fixture(scope="session", autouse=True)
def _init_database():
    """This file is the only one in the suite that constructs a real
    MainWindow() directly, rather than through main.py's own entry point
    - which matters because main.py calls core.database.init_db() BEFORE
    ever constructing MainWindow (main.py line ~87), and at least one
    menu action reads from the users table that call creates. A real
    first launch always goes through main.py and never hits this; a
    fresh checkout with no prior local run of the real app - exactly
    what a CI runner is - has no users table yet, since nothing else
    in this test file (or the rest of the suite) ever calls init_db()
    itself. Confirmed by reproducing the exact CI failure locally
    against a machine with no ~/.caatmaster directory at all."""
    from core.database import init_db
    init_db()


@pytest.fixture(autouse=True)
def _neutralize_blocking_dialogs(monkeypatch):
    """Same rationale as test_dialog_audit.py's fixture of the same name:
    nothing here should block waiting for a real user."""
    for name in ("warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Rejected)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))


def _all_menu_action_ids():
    """Every action_id in app_menu.py's menu trees, via the app's own
    leaf-walking helper - the same one build_menu_bar() itself uses -
    rather than a separately maintained list that could go stale."""
    from gui.components.app_menu import _ALL_MENUS, _iter_leaves

    ids = []
    for menu in _ALL_MENUS:
        for label, icon, action_id in _iter_leaves(menu):
            ids.append(action_id)
    return sorted(set(ids))


_ACTION_IDS = _all_menu_action_ids()


@pytest.fixture
def main_window_with_data(qtbot):
    from gui.main_window import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)
    df = pl.DataFrame({
        "vendor": ["Acme Corp", "Beta LLC", "Gamma Inc"],
        "requester": ["alice", "bob", "carol"],
        "approver": ["bob", "carol", "alice"],
        "amount": [1000.0, 2500.5, 300.25],
        "revenue": [100000.0, 120000.0, 95000.0],
        "cost": [80000.0, 90000.0, 70000.0],
        "date": ["2024-01-01", "2024-02-01", "2024-03-01"],
        "text_field": ["a;b;c", "x|y|z", "p,q,r"],
        "region": ["East", "West", "East"],
    })
    win.views["transform"].set_dataframe(df)
    return win


class TestEveryMenuActionHasAHandler:
    """Every action_id declared in a top-menu-bar entry must actually be
    wired in handle_ribbon_action - not just present in the menu."""

    @pytest.mark.parametrize("action_id", _ACTION_IDS)
    def test_action_is_wired(self, main_window_with_data, action_id):
        win = main_window_with_data
        win.handle_ribbon_action(action_id)
        QApplication.processEvents()
        message = win.statusBar().currentMessage()
        assert message != f"Action '{action_id}' not yet implemented", (
            f"'{action_id}' is declared in a top menu bar entry (app_menu.py) but has no "
            "corresponding handler in MainWindow.handle_ribbon_action - clicking it in the "
            "real app does nothing, silently, with no error and no dialog."
        )
