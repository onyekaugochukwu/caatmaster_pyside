"""
Rule Library dialogs — field-mapping form for a canned SOX/COSO/IFRS
compliance_rule_library, and a read-only view of the COSO heatmap built
from whatever findings have been run so far in this session.

Kept separate from compliance_report_dialog.py (which wires these in)
following this codebase's one-dialog-per-file convention.
"""
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QFormLayout, QGroupBox, QScrollArea, QWidget, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox
)
from PySide6.QtCore import Qt

from gui.theme import Colors
from gui.components.common_modals import create_primary_button, create_secondary_button


class RuleLibraryMappingDialog(QDialog):
    """Lets the user confirm/override the auto-suggested column mapping and
    any threshold parameters for one rule library before it runs. Every
    field here maps a LOGICAL name the library's rules were written against
    (e.g. "amount") to an ACTUAL column in the dataset currently being
    checked — the same idea as the SOX SoD dialog's user/action columns,
    generalized to a whole library of rules at once."""

    def __init__(self, df_columns: List[str], library: Dict[str, Any],
                 field_specs: Dict[str, Any], suggested_mapping: Dict[str, str], parent=None):
        super().__init__(parent)
        self.df_columns = df_columns
        self.library = library
        self.field_specs = field_specs
        self.suggested_mapping = suggested_mapping
        self.field_combos: Dict[str, QComboBox] = {}
        self.param_inputs: Dict[str, Any] = {}
        self.setWindowTitle(f"Map Fields — {library['display_name']}")
        self.setMinimumSize(520, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(self.library["display_name"])
        title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)

        desc = QLabel(self.library["description"])
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        form_layout = QVBoxLayout(inner)

        required = self.field_specs["required_fields"]
        optional = self.field_specs["optional_fields"]
        params = self.field_specs["params"]

        if required or optional:
            fields_group = QGroupBox("Map Dataset Columns")
            fields_form = QFormLayout(fields_group)
            fields_form.setVerticalSpacing(8)

            for field_name, hint in required.items():
                combo = self._build_column_combo(field_name)
                fields_form.addRow(f"{field_name}* — {hint}", combo)
                self.field_combos[field_name] = combo

            for field_name, hint in optional.items():
                if field_name in self.field_combos:
                    continue
                combo = self._build_column_combo(field_name)
                fields_form.addRow(f"{field_name} (optional) — {hint}", combo)
                self.field_combos[field_name] = combo

            form_layout.addWidget(fields_group)

        if params:
            params_group = QGroupBox("Thresholds & Parameters")
            params_form = QFormLayout(params_group)
            params_form.setVerticalSpacing(8)

            for name, spec in params.items():
                if spec.get("type") == "number":
                    field = QDoubleSpinBox()
                    field.setRange(-1_000_000_000, 1_000_000_000)
                    field.setDecimals(2)
                    field.setValue(float(spec.get("default", 0)))
                else:
                    field = QLineEdit(str(spec.get("default", "")))
                params_form.addRow(spec.get("label", name), field)
                self.param_inputs[name] = field

            form_layout.addWidget(params_group)

        note = QLabel(
            "* required — a rule with an unmapped required field is skipped and reported "
            "as \"not computable\" rather than guessed at."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        form_layout.addWidget(note)
        form_layout.addStretch()

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = create_secondary_button("Cancel")
        cancel_btn.clicked.connect(self.reject)
        run_btn = create_primary_button("Run Rules")
        run_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(run_btn)
        layout.addLayout(btn_row)

    def _build_column_combo(self, field_name: str) -> QComboBox:
        combo = QComboBox()
        combo.addItem("— Not mapped —", None)
        for col in self.df_columns:
            combo.addItem(col, col)
        suggested = self.suggested_mapping.get(field_name)
        if suggested:
            idx = combo.findData(suggested)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        return combo

    def get_mapping(self) -> Dict[str, str]:
        mapping = {}
        for field_name, combo in self.field_combos.items():
            value = combo.currentData()
            if value:
                mapping[field_name] = value
        return mapping

    def get_params(self) -> Dict[str, Any]:
        params = {}
        for name, field in self.param_inputs.items():
            if isinstance(field, QDoubleSpinBox):
                params[name] = field.value()
            else:
                params[name] = field.text()
        return params


class CosoHeatmapDialog(QDialog):
    """Read-only table view of CosoService.build_heatmap_from_findings()'s
    output, built from whatever rule-library findings have been run so far
    in this Compliance Report session (not a persisted/reloadable report —
    closing this dialog just closes the view)."""

    def __init__(self, heatmap_df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("COSO Component Risk Heatmap")
        self.setMinimumSize(640, 320)
        self._setup_ui(heatmap_df)

    def _setup_ui(self, heatmap_df):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("COSO Component Risk Heatmap")
        title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)

        note = QLabel(
            "Built from every rule-library finding run in this session, grouped by the COSO "
            "component each rule maps to. avg_risk_weight is severity-based (high=3, medium=2, "
            "low=1) — a transparent count, not a derived probability of anything."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(note)

        columns = heatmap_df.columns
        table = QTableWidget(heatmap_df.height, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row_idx, row in enumerate(heatmap_df.to_dicts()):
            for col_idx, col_name in enumerate(columns):
                value = row.get(col_name)
                text = f"{value:.2f}" if isinstance(value, float) else str(value)
                table.setItem(row_idx, col_idx, QTableWidgetItem(text))
        layout.addWidget(table)

        close_btn = create_secondary_button("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
