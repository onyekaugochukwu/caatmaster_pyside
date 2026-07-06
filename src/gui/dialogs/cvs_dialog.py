"""Classical Variables Sampling Dialog - sample size planning and sample
result evaluation/projection, mirroring ACL's SIZE/EVALUATE/CVSEVALUATE
commands. Two tabs: plan a sample size before drawing one, and evaluate
a drawn sample's audited-vs-book results by projecting them to the full
population with a confidence interval."""
import polars as pl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFormLayout, QDoubleSpinBox, QSpinBox, QGroupBox, QTabWidget, QWidget,
    QMessageBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt

from services.sampling_evaluation import calculate_sample_size, evaluate_sample, ESTIMATION_METHODS


class ClassicalVariablesSamplingDialog(QDialog):
    """Two-tab dialog: Sample Size (planning) and Evaluate Sample
    (projection). The Evaluate tab needs a dataframe with a book value
    and audited value column per sampled item - pass the active dataset
    (or a dataset built from just the drawn sample) as `df`."""

    def __init__(self, df: pl.DataFrame = None, parent=None):
        super().__init__(parent)
        self.df = df
        self.setWindowTitle("Classical Variables Sampling")
        self.resize(650, 560)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_size_tab(), "Calculate Sample Size")
        tabs.addTab(self._build_evaluate_tab(), "Evaluate Sample Results")
        layout.addWidget(tabs)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ---------------------------------------------------------------- Size tab

    def _build_size_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        info = QLabel(
            "How large a sample is needed to estimate the population value within a target "
            "precision, at a given confidence level - mirrors ACL's SIZE command. Requires an "
            "estimate of the population's standard deviation (from a pilot sample, prior period "
            "data, or a reasonable judgment estimate)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #4b5563;")
        layout.addWidget(info)

        form_group = QGroupBox("Inputs")
        form = QFormLayout(form_group)

        self.size_population = QSpinBox()
        self.size_population.setRange(1, 100_000_000)
        self.size_population.setValue(10000)
        form.addRow("Population Size:", self.size_population)

        self.size_std_dev = QDoubleSpinBox()
        self.size_std_dev.setRange(0.01, 1e12)
        self.size_std_dev.setValue(100.0)
        self.size_std_dev.setDecimals(2)
        form.addRow("Estimated Population Std Dev:", self.size_std_dev)

        self.size_confidence = QComboBox()
        self.size_confidence.addItems(["90", "95", "97.5", "99"])
        self.size_confidence.setCurrentText("95")
        form.addRow("Confidence Level (%):", self.size_confidence)

        self.size_precision = QDoubleSpinBox()
        self.size_precision.setRange(0.01, 1e12)
        self.size_precision.setValue(10000.0)
        self.size_precision.setDecimals(2)
        self.size_precision.setToolTip("Tolerable precision - the maximum acceptable difference between the sample estimate and the true population value.")
        form.addRow("Tolerable Precision:", self.size_precision)

        layout.addWidget(form_group)

        calc_btn = QPushButton("Calculate Sample Size")
        calc_btn.setStyleSheet("""
            QPushButton { padding: 10px 20px; background-color: #0078d4; color: white;
                          border: none; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background-color: #106ebe; }
        """)
        calc_btn.clicked.connect(self._on_calculate_size)
        layout.addWidget(calc_btn)

        self.size_result_label = QLabel("")
        self.size_result_label.setWordWrap(True)
        self.size_result_label.setStyleSheet(
            "padding: 12px; background-color: #f0fdf4; border: 1px solid #22c55e; border-radius: 6px; font-size: 13px;"
        )
        self.size_result_label.setVisible(False)
        layout.addWidget(self.size_result_label)

        layout.addStretch()
        return widget

    def _on_calculate_size(self):
        try:
            result = calculate_sample_size(
                population_size=self.size_population.value(),
                population_std_dev=self.size_std_dev.value(),
                confidence_level=float(self.size_confidence.currentText()),
                tolerable_precision=self.size_precision.value(),
            )
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return

        self.size_result_label.setText(
            f"<b>Recommended sample size: {result['recommended_sample_size']:,}</b><br>"
            f"(unadjusted: {result['unadjusted_sample_size']:,}, before finite population correction)<br>"
            f"z-score used: {result['z_score']}"
        )
        self.size_result_label.setVisible(True)

    # ------------------------------------------------------------ Evaluate tab

    def _build_evaluate_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        info = QLabel(
            "Given a drawn sample with both a recorded (book) value and a verified (audited) "
            "value per item, project the sample's results to the full population - mirrors ACL's "
            "EVALUATE/CVSEVALUATE commands."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #4b5563;")
        layout.addWidget(info)

        if self.df is None or self.df.is_empty():
            layout.addWidget(QLabel("No active dataset available to evaluate."))
            layout.addStretch()
            return widget

        form_group = QGroupBox("Sample & Population")
        form = QFormLayout(form_group)

        self.eval_book_combo = QComboBox()
        self.eval_book_combo.addItems(self.df.columns)
        form.addRow("Book Value Column:", self.eval_book_combo)

        self.eval_audited_combo = QComboBox()
        self.eval_audited_combo.addItems(self.df.columns)
        form.addRow("Audited Value Column:", self.eval_audited_combo)

        self.eval_population_size = QSpinBox()
        self.eval_population_size.setRange(1, 100_000_000)
        self.eval_population_size.setValue(max(self.df.height, 1))
        form.addRow("Population Size:", self.eval_population_size)

        self.eval_population_total = QDoubleSpinBox()
        self.eval_population_total.setRange(0, 1e15)
        self.eval_population_total.setDecimals(2)
        form.addRow("Population Book Total:", self.eval_population_total)

        self.eval_confidence = QComboBox()
        self.eval_confidence.addItems(["90", "95", "97.5", "99"])
        self.eval_confidence.setCurrentText("95")
        form.addRow("Confidence Level (%):", self.eval_confidence)

        layout.addWidget(form_group)

        method_group = QGroupBox("Estimation Method")
        method_layout = QVBoxLayout(method_group)
        self.method_group = QButtonGroup()
        method_descriptions = {
            "mean_per_unit": "Mean-Per-Unit - projects from the sample's mean audited value alone",
            "difference": "Difference - projects from the mean per-item difference (audited − book); "
                          "more precise when errors are roughly constant in size",
            "ratio": "Ratio - projects from the ratio of audited to book totals; more precise when "
                    "errors are roughly proportional to item size",
        }
        self.method_radios = {}
        for method in ESTIMATION_METHODS:
            radio = QRadioButton(method_descriptions[method])
            if method == "mean_per_unit":
                radio.setChecked(True)
            self.method_group.addButton(radio)
            self.method_radios[method] = radio
            method_layout.addWidget(radio)
        layout.addWidget(method_group)

        eval_btn = QPushButton("Evaluate Sample")
        eval_btn.setStyleSheet("""
            QPushButton { padding: 10px 20px; background-color: #0078d4; color: white;
                          border: none; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background-color: #106ebe; }
        """)
        eval_btn.clicked.connect(self._on_evaluate_sample)
        layout.addWidget(eval_btn)

        self.eval_result_label = QLabel("")
        self.eval_result_label.setWordWrap(True)
        self.eval_result_label.setStyleSheet(
            "padding: 12px; background-color: #f0fdf4; border: 1px solid #22c55e; border-radius: 6px; font-size: 13px;"
        )
        self.eval_result_label.setVisible(False)
        layout.addWidget(self.eval_result_label)

        layout.addStretch()
        return widget

    def _on_evaluate_sample(self):
        method = next(m for m, r in self.method_radios.items() if r.isChecked())
        try:
            result = evaluate_sample(
                self.df,
                self.eval_book_combo.currentText(),
                self.eval_audited_combo.currentText(),
                population_size=self.eval_population_size.value(),
                population_book_total=self.eval_population_total.value(),
                confidence_level=float(self.eval_confidence.currentText()),
                method=method,
            )
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
            return

        self.eval_result_label.setText(
            f"<b>Projected population value: {result['point_estimate']:,.2f}</b><br>"
            f"Projected misstatement: {result['projected_misstatement']:,.2f}<br>"
            f"Precision (± at {result['confidence_level']}% confidence): {result['precision']:,.2f}<br>"
            f"Confidence interval: [{result['lower_bound']:,.2f}, {result['upper_bound']:,.2f}]<br>"
            f"Standard error: {result['standard_error']:,.2f}  |  Sample size: {result['sample_size']:,} "
            f"of {result['population_size']:,}"
        )
        self.eval_result_label.setVisible(True)
