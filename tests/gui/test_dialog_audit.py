"""
Systematic dialog audit.

Qt swallows exceptions raised inside a slot by default - no crash, no
visible error, the dialog just does nothing - so a dialog whose primary
action button raises can appear to work while being completely
non-functional. Two checks, at two different levels of rigor, guard
against that:

1. Construction, for every dialog registered in
   TransformationDialogFactory.DIALOG_MAPPING, via the REAL factory
   entrypoint (not a hand-rolled constructor call) - catches an import
   error or a _setup_ui() crash. Asserts the factory actually returned
   the EXPECTED dialog class, not its own silent fallback to
   GenericTransformationDialog on a construction exception, which
   would otherwise let a broken dialog quietly start using the generic
   form instead of failing loudly.

2. A real button click, via qtbot.mouseClick() (not calling a method by
   a guessed name) on every plausible "primary action" button in each
   dialog, with QMessageBox/QFileDialog/nested QDialog.exec() all
   neutralized first so a validation popup or an accidentally-clicked
   nested dialog can't hang the test. pytest-qt automatically fails a
   test if an exception was raised inside a Qt slot during it, which
   exactly reproduces "the auditor clicks the button" rather than
   testing whatever method happens to be connected to it.
"""
import re
from pathlib import Path

import pytest
import polars as pl
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QMessageBox, QFileDialog, QDialog

DIALOGS_DIR = Path(__file__).parent.parent.parent / "src" / "gui" / "dialogs"

# Button text substrings that are never a plausible "run the operation"
# action - clicking these deliberately isn't exercised (some are still
# made harmless via the neutralizing fixture below in case a dialog
# doesn't use the recognizable text below for its actual primary button
# and something ambiguous gets clicked anyway).
_SKIP_BUTTON_TEXT = re.compile(
    r"cancel|close|browse|load\b|manage|remove|delete|add\s|clear|reset",
    re.IGNORECASE,
)


@pytest.fixture
def rich_dataframe():
    """A dataframe with a broad spread of column names/types, so as many
    dialogs' auto-detection as possible finds *something* plausible to
    default to - construction must succeed regardless (every dialog is
    designed to offer an empty/manual selection when nothing matches),
    this just maximizes how much of each dialog's real widget-population
    code actually runs during the audit rather than immediately falling
    back to placeholders everywhere."""
    return pl.DataFrame({
        "revenue": [100000.0, 120000.0, 95000.0],
        "total_assets": [500000.0, 520000.0, 480000.0],
        "current_assets": [200000.0, 210000.0, 190000.0],
        "current_liabilities": [100000.0, 105000.0, 95000.0],
        "total_equity": [300000.0, 310000.0, 290000.0],
        "total_liabilities": [200000.0, 210000.0, 190000.0],
        "cash": [50000.0, 55000.0, 45000.0],
        "inventory": [30000.0, 32000.0, 28000.0],
        "net_income": [10000.0, 12000.0, 8000.0],
        "amount": [1234.56, -500.0, 9999.99],
        "quantity": [10, 20, 30],
        "user": ["alice", "bob", "carol"],
        "action": ["Create Vendor", "Approve Invoice", "Process Payment"],
        "status": ["Active", "Terminated", "Active"],
        "category": ["A", "B", "A"],
        "description": ["Payment", "Refund", "Transfer"],
        "date": ["2024-01-01", "2024-02-01", "2024-03-01"],
    })


@pytest.fixture(autouse=True)
def _neutralize_blocking_dialogs(monkeypatch):
    """Applies to every test in this file: QMessageBox popups resolve
    immediately (no real user to click them), a nested QDialog.exec()
    returns Rejected immediately instead of blocking (some dialogs open
    a second modal dialog from a button - e.g. "Manage Taxonomy
    Packages..." - which would otherwise hang the click sweep forever
    waiting for a close nothing will ever send), and QFileDialog's static
    pickers return "nothing selected" instead of trying to show a native
    dialog offscreen can't render."""
    for name in ("warning", "critical", "information", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.Ok))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.Rejected)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))


def _unique_dialog_mapping():
    """{operation_id: dialog_class} for every entry in the real factory
    registry - one operation_id per class is enough to construct/click
    each dialog once; testing every operation_id that maps to the SAME
    class would just repeat the identical widget code."""
    from gui.dialogs.transformation_dialog_factory import TransformationDialogFactory

    seen_classes = set()
    result = {}
    for op_id, cls in TransformationDialogFactory.DIALOG_MAPPING.items():
        if cls not in seen_classes:
            seen_classes.add(cls)
            result[op_id] = cls
    return result


_DIALOG_CASES = sorted(_unique_dialog_mapping().items())


class TestDialogConstruction:
    """Every registered dialog builds via the real factory entrypoint,
    and the factory didn't silently fall back to the generic dialog on a
    construction exception."""

    @pytest.mark.parametrize("op_id,expected_cls", _DIALOG_CASES, ids=[c[0] for c in _DIALOG_CASES])
    def test_dialog_constructs_via_factory(self, qtbot, rich_dataframe, op_id, expected_cls):
        from gui.dialogs.transformation_dialog_factory import TransformationDialogFactory

        dialog = TransformationDialogFactory.create_dialog(op_id, rich_dataframe, parent=None)
        assert dialog is not None, f"Factory returned None for '{op_id}'"
        qtbot.addWidget(dialog)
        # Some dialogs schedule a QTimer.singleShot(0, ...) during
        # construction (a preview table's "settle empty-state after
        # layout" callback) that captures `self` - draining the event
        # queue here, while this dialog is still alive, lets that fire
        # cleanly instead of leaking into a LATER test's event-processing
        # and crashing with "C++ object already deleted" against a
        # widget THIS test already tore down.
        qtbot.wait(0)
        assert type(dialog) is expected_cls, (
            f"'{op_id}' should build a {expected_cls.__name__}, but got {type(dialog).__name__} - "
            "the factory silently falls back to the generic dialog when the specific one raises "
            "during construction, which is exactly the kind of failure this test exists to catch."
        )


class TestDialogPrimaryButtonClick:
    """A real qtbot.mouseClick() on every plausible primary-action button
    in each dialog, in its default (just-constructed) state. Exceptions
    raised inside the resulting slot call are caught and reported as a
    test failure by pytest-qt automatically (Qt itself would otherwise
    swallow them silently) - confirmed directly against a synthetic
    AttributeError before relying on it for this file's actual purpose."""

    @pytest.mark.parametrize("op_id,expected_cls", _DIALOG_CASES, ids=[c[0] for c in _DIALOG_CASES])
    def test_clicking_primary_buttons_does_not_raise(self, qtbot, rich_dataframe, op_id, expected_cls):
        from gui.dialogs.transformation_dialog_factory import TransformationDialogFactory

        dialog = TransformationDialogFactory.create_dialog(op_id, rich_dataframe, parent=None)
        qtbot.addWidget(dialog)

        buttons = [
            b for b in dialog.findChildren(QPushButton)
            if b.isEnabled() and b.isVisible() and not _SKIP_BUTTON_TEXT.search(b.text())
        ]
        for button in buttons:
            qtbot.mouseClick(button, Qt.LeftButton)


class TestNoOrphanedSignalEmit:
    """Static check across EVERY dialog file (not just ones registered in
    the factory) for the exact bug class found: a method emits
    self.<name>.emit(...) where <name> is never declared as a Signal on
    that class. A structural/source-level check rather than a runtime
    one, so it also covers dialogs that aren't reachable through the
    transformation factory at all (e.g. standalone dialogs launched
    directly from main_window.py)."""

    def test_every_emitted_signal_is_declared(self):
        undeclared = []
        for path in sorted(DIALOGS_DIR.glob("*.py")):
            text = path.read_text()
            emitted = set(re.findall(r"self\.(\w+)\.emit\(", text))
            declared = set(re.findall(r"^\s*(\w+)\s*=\s*Signal\(", text, re.MULTILINE))
            for name in emitted:
                # Not declared in THIS file doesn't necessarily mean
                # missing - it could be inherited from a base class
                # defined elsewhere (e.g. BaseModal's accepted_params).
                # Only flag names that look like the app's own
                # transformation-dialog convention and aren't declared
                # anywhere in this file, mirroring exactly how the
                # original SoxSodDialog/CosoDialog/IFRS9Dialog bug was
                # found and fixed.
                if name not in declared and name not in _KNOWN_BASE_CLASS_SIGNALS:
                    undeclared.append(f"{path.name}: self.{name}.emit(...) but '{name} = Signal(' not found")
        assert not undeclared, "\n".join(undeclared)


# Signals inherited from a base class defined outside src/gui/dialogs/
# (so a per-file source scan can't see the declaration) - anything here
# has been verified to actually exist on the base class.
_KNOWN_BASE_CLASS_SIGNALS = {
    "accepted_params",  # gui.components.common_modals.BaseModal
    "columnSelected", "columnsSelected", "valueChanged", "selectionChanged",  # common_modals.py widgets
}
