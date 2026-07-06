"""
Data Cleaning Wizard dialog — reviews a deterministic CleaningPlan
(core.cleaning_wizard) with the user before anything is applied. Every
proposed step maps to a real, existing transformation operation; accepting
a step here just means it gets added to the normal Applied Steps pipeline
afterward — nothing here is a black box, and nothing is undoable-proof
different from any other step in the app.
"""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QGroupBox, QScrollArea, QWidget, QTextEdit, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame
)
from PySide6.QtCore import Qt

from core.cleaning_wizard import build_cleaning_plan, CleaningStep
from core.data_processor import DataProcessor
from core.operation_registry import OPERATION_REGISTRY


class CleaningWizardDialog(QDialog):
    def __init__(self, raw_df: pl.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Cleaning Wizard")
        self.resize(1000, 700)

        self.raw_df = raw_df
        self.plan = build_cleaning_plan(raw_df)
        self.step_checkboxes = []
        self.data_processor = DataProcessor()

        self._setup_ui()
        self._update_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Every step below was detected by an exact, checkable rule (e.g. \"this row's values equal "
            "the sum of the rows above it\") — not guessed. Steps marked \"review\" involve a judgment "
            "call (like which columns are identifiers vs. values) and start unchecked; everything else "
            "starts checked. Nothing is applied until you click Apply — accepted steps are added to the "
            "normal Applied Steps pipeline, so they stay fully visible and undoable afterward."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #555; padding: 6px;")
        layout.addWidget(intro)

        if self.plan.notes:
            notes_box = QGroupBox("Notes")
            notes_layout = QVBoxLayout(notes_box)
            for note in self.plan.notes:
                note_label = QLabel(f"⚠ {note}")
                note_label.setWordWrap(True)
                note_label.setStyleSheet("color: #8a6d3b;")
                notes_layout.addWidget(note_label)
            layout.addWidget(notes_box)

        splitter = QSplitter(Qt.Vertical)

        # Steps list
        steps_scroll = QScrollArea()
        steps_scroll.setWidgetResizable(True)
        steps_container = QWidget()
        steps_layout = QVBoxLayout(steps_container)

        if not self.plan.steps:
            steps_layout.addWidget(QLabel("No structural issues detected — nothing to clean up."))
        for step in self.plan.steps:
            steps_layout.addWidget(self._build_step_widget(step))
        steps_layout.addStretch()
        steps_scroll.setWidget(steps_container)
        splitter.addWidget(steps_scroll)

        # Before/after preview
        preview_frame = QFrame()
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.addWidget(QLabel("<b>Preview after accepted steps:</b>"))
        self.preview_summary = QLabel()
        preview_layout.addWidget(self.preview_summary)
        self.preview_table = QTableWidget()
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        preview_layout.addWidget(self.preview_table)
        splitter.addWidget(preview_frame)
        splitter.setSizes([350, 350])

        layout.addWidget(splitter)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        self.apply_btn = QPushButton()
        self.apply_btn.clicked.connect(self.accept)
        button_row.addWidget(self.apply_btn)
        layout.addLayout(button_row)

        # Must run after self.apply_btn exists — toggling a checkbox here
        # (the initial-state fixup) fires _update_preview immediately,
        # which references self.apply_btn.
        self._enforce_rename_dependency()

    def _build_step_widget(self, step: CleaningStep) -> QWidget:
        box = QGroupBox()
        box_layout = QVBoxLayout(box)

        display_name = OPERATION_REGISTRY.get(step.operation_id, {}).get("display_name", step.operation_id)
        checkbox = QCheckBox(f"{display_name}  [{step.confidence.upper()} CONFIDENCE]")
        checkbox.setChecked(step.confidence == "high")
        checkbox.stateChanged.connect(self._update_preview)
        if step.confidence == "review":
            checkbox.setStyleSheet("font-weight: bold; color: #8a6d3b;")
        box_layout.addWidget(checkbox)

        desc = QLabel(step.description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #444; margin-left: 20px;")
        box_layout.addWidget(desc)

        self.step_checkboxes.append((checkbox, step))
        return box

    def _enforce_rename_dependency(self):
        """Steps that reference a RENAMED column name (see
        cleaning_wizard.py's effective_columns) only work if the
        rename_columns step ran first — if the user unchecks the rename
        but leaves such a step checked, it fails outright, since the
        names it expects were never created. Rather than silently
        letting that broken combination through, wire it so checking a
        dependent step auto-checks the rename above it, and unchecking
        the rename auto-unchecks its dependents. remove_rows/filter_rows
        aren't included even when they come after the rename in the plan
        — they reference row positions or the fixed "value" column from
        unpivot, never a renamed name, so they're independent of it. The
        rename step's own confidence stays "review" (it's a heuristic,
        not a verified fact like the subtotal check that depends on it)
        — this only prevents the specific combination that can't work."""
        rename_idx = next(
            (i for i, (_, step) in enumerate(self.step_checkboxes) if step.operation_id == "rename_columns"),
            None
        )
        if rename_idx is None:
            return
        rename_checkbox = self.step_checkboxes[rename_idx][0]
        raw_names = {f"column_{i + 1}" for i in range(len(self.raw_df.columns))}

        def references_renamed_column(step: CleaningStep) -> bool:
            candidates = []
            candidates.extend(step.params.get("columns_to_remove", []))
            candidates.extend(step.params.get("id_vars", []))
            candidates.extend(step.params.get("value_vars", []))
            return any(c not in raw_names for c in candidates)

        dependents = [
            cb for cb, step in self.step_checkboxes[rename_idx + 1:]
            if references_renamed_column(step)
        ]

        def on_dependent_toggled(state):
            if state and not rename_checkbox.isChecked():
                rename_checkbox.setChecked(True)

        def on_rename_toggled(state):
            if not state:
                for cb in dependents:
                    cb.setChecked(False)

        for cb in dependents:
            cb.stateChanged.connect(on_dependent_toggled)
        rename_checkbox.stateChanged.connect(on_rename_toggled)

        # The default state itself can already be inconsistent (a "high
        # confidence" dependent checked by default while the "review"
        # rename it needs isn't) — fix that now rather than waiting for
        # the user to toggle something.
        if any(cb.isChecked() for cb in dependents) and not rename_checkbox.isChecked():
            rename_checkbox.setChecked(True)

    def get_accepted_steps(self):
        """Returns the list of (operation_id, params) tuples the user
        accepted, in plan order — ready to feed straight into
        TransformationPipeline.add_step()."""
        return [(step.operation_id, step.params) for checkbox, step in self.step_checkboxes if checkbox.isChecked()]

    def _update_preview(self, *_):
        accepted = self.get_accepted_steps()

        # The dialog is a valid way to finish even with nothing accepted
        # (or nothing detected in the first place) — importing the data
        # as-is is a legitimate outcome, not an error state, so the button
        # should never be stuck disabled. Label reflects what will
        # actually happen instead of always saying "Apply".
        if accepted:
            self.apply_btn.setText(f"Apply {len(accepted)} Accepted Step{'s' if len(accepted) != 1 else ''}")
        else:
            self.apply_btn.setText("Import As-Is (No Steps)")
        self.apply_btn.setEnabled(True)

        df = self.raw_df
        error = None
        for operation_id, params in accepted:
            try:
                df = self.data_processor.apply_operation(df, operation_id, dict(params))
            except Exception as e:
                error = f"Step '{operation_id}' failed to preview: {e}"
                break

        if error:
            self.preview_summary.setText(f"<span style='color:#991b1b'>{error}</span>")
            self.apply_btn.setEnabled(False)
            return

        self.preview_summary.setText(f"{df.height:,} rows × {len(df.columns)} columns")

        preview_rows = min(50, df.height)
        self.preview_table.setRowCount(preview_rows)
        self.preview_table.setColumnCount(len(df.columns))
        self.preview_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r in range(preview_rows):
            row_vals = df.row(r)
            for c, val in enumerate(row_vals):
                self.preview_table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
