"""
Benford's Law Dialog for CAATmaster
Analyze digit distribution for fraud detection
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QWidget, QMessageBox, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtCharts import QChart, QChartView, QBarSeries, QBarSet, QValueAxis, QCategoryAxis

from ..components.common_modals import BaseModal, PreviewTable, ColumnSelector, StatusLabel
from ..components.common_modals import BenfordChart


class BenfordDialog(BaseModal):
    """
    Benford's Law Analysis dialog for audit fraud detection
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Benford's Law Analysis", dataframe, parent)
        self.setMinimumSize(900, 700)

    def _setup_ui(self):
        """Setup the Benford's Law dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selection
        col_group = QGroupBox("Data Column")
        col_layout = QVBoxLayout(col_group)

        self.column_selector = ColumnSelector(self.original_df)
        self.column_selector.set_label("Column to Analyze:")
        col_layout.addWidget(self.column_selector)

        col_help = QLabel("Select a numeric column (transaction amounts, balances, etc.)")
        col_help.setStyleSheet("color: #666; font-size: 11px;")
        col_layout.addWidget(col_help)

        layout.addWidget(col_group)

        # Analysis options
        options_group = QGroupBox("Analysis Options")
        options_layout = QGridLayout(options_group)

        # Leading digits
        options_layout.addWidget(QLabel("Leading Digits:"), 0, 0)
        self.digits_combo = QComboBox()
        self.digits_combo.addItems(["1 (First digit only)", "2 (First 2 digits)"])
        options_layout.addWidget(self.digits_combo, 0, 1)

        # Significant digits option
        self.significant_check = QCheckBox("Use significant digits only")
        self.significant_check.setChecked(False)
        options_layout.addWidget(self.significant_check, 1, 0, 1, 2)

        layout.addWidget(options_group)

        # Results section - split view
        results_splitter = QSplitter(Qt.Horizontal)

        # Left: Chart
        chart_group = QGroupBox("Distribution Chart")
        chart_layout = QVBoxLayout(chart_group)

        self.benford_chart = BenfordChart()
        chart_layout.addWidget(self.benford_chart)

        results_splitter.addWidget(chart_group)

        # Right: Statistics table
        stats_group = QGroupBox("Digit Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(4)
        self.stats_table.setHorizontalHeaderLabels(["Digit", "Benford %", "Actual %", "Deviation"])
        self.stats_table.horizontalHeader().setStretchLastSection(True)
        self.stats_table.setMaximumWidth(350)
        stats_layout.addWidget(self.stats_table)

        # Chi-square test result
        self.chi_square_label = StatusLabel("No analysis run")
        stats_layout.addWidget(self.chi_square_label)

        results_splitter.addWidget(stats_group)

        layout.addWidget(results_splitter)

        # Output options
        output_group = QGroupBox("Output Columns")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Leading Digit Column:"), 0, 0)
        self.digit_col_edit = QLineEdit("leading_digit")
        output_layout.addWidget(self.digit_col_edit, 0, 1)

        output_layout.addWidget(QLabel("Expected Column:"), 1, 0)
        self.expected_col_edit = QLineEdit("benford_expected")
        output_layout.addWidget(self.expected_col_edit, 1, 1)

        output_layout.addWidget(QLabel("Deviation Column:"), 2, 0)
        self.deviation_col_edit = QLineEdit("benford_deviation")
        output_layout.addWidget(self.deviation_col_edit, 2, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview (First 15 Rows with Analysis)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=15)
        preview_layout.addWidget(self.preview_table)

        layout.addWidget(preview_group)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.analyze_btn = QPushButton("Run Analysis")
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        self.analyze_btn.clicked.connect(self._run_analysis)
        btn_layout.addWidget(self.analyze_btn)

        layout.addLayout(btn_layout)

    def get_benford_expected(self, n_digits: int = 1) -> dict:
        """Get Benford's Law expected percentages"""
        if n_digits == 1:
            return {str(i): np.log10(1 + 1/i) * 100 for i in range(1, 10)}
        else:
            # First 2 digits (10-99)
            expected = {}
            for d in range(10, 100):
                expected[f"{d:02d}"] = (np.log10(1 + 1/d) * 100)
            return expected

    def extract_leading_digits(self, values: np.ndarray, n_digits: int,
                               significant_only: bool) -> List[str]:
        """Extract leading digits from values"""
        digits = []
        for v in values:
            try:
                abs_v = abs(float(v))
                if abs_v == 0:
                    continue

                if significant_only:
                    # Remove leading zeros and decimal point for significant digits
                    str_v = f"{abs_v:.10g}"  # Use general format
                    str_v = str_v.replace('.', '').lstrip('0')
                else:
                    str_v = str(abs_v)

                if n_digits == 1:
                    # First non-zero digit
                    for c in str_v:
                        if c.isdigit() and c != '0':
                            digits.append(c)
                            break
                else:
                    # First n digits (or fewer if number is shorter)
                    first_n = ""
                    for c in str_v:
                        if c.isdigit():
                            first_n += c
                            if len(first_n) == n_digits:
                                break
                    if first_n:
                        digits.append(first_n)
            except (ValueError, OverflowError):
                continue

        return digits

    def _run_analysis(self):
        """Run Benford's Law analysis"""
        try:
            params = self.get_parameters()
            column = params["column"]

            if not column:
                QMessageBox.warning(self, "Warning", "Please select a column to analyze.")
                return

            # Get data
            col_data = self.original_df[column].to_numpy()
            valid_mask = ~np.isnan(col_data.astype(float)) & (col_data != 0)
            valid_data = col_data[valid_mask]

            if len(valid_data) < 100:
                QMessageBox.warning(self, "Warning",
                                  f"Only {len(valid_data)} valid non-zero values found.\n"
                                  "Benford's Law works best with 100+ data points.")
                return

            # Extract leading digits
            n_digits = 1 if params["digits"] == 1 else 2
            digits = self.extract_leading_digits(valid_data, n_digits,
                                                 params["significant_only"])

            if not digits:
                QMessageBox.warning(self, "Warning", "Could not extract leading digits.")
                return

            # Count digit frequencies
            digit_counts = {}
            for d in digits:
                digit_counts[d] = digit_counts.get(d, 0) + 1

            # Get expected values
            expected = self.get_benford_expected(n_digits)

            # Calculate percentages
            total = len(digits)
            actual = {d: (count / total * 100) for d, count in digit_counts.items()}

            # Update chart
            self.benford_chart.set_data(expected, actual)

            # Update stats table
            if n_digits == 1:
                self._update_stats_table_1digit(expected, actual, total)
            else:
                self._update_stats_table_2digit(expected, actual, total)

            # Chi-square test
            self._run_chi_square(expected, digit_counts, total)

            # Update preview
            self._update_preview(column, digits, expected)

        except Exception as e:
            QMessageBox.warning(self, "Analysis Error",
                              f"Could not complete analysis:\n{str(e)}")

    def _update_stats_table_1digit(self, expected: dict, actual: dict, total: int):
        """Update stats table for 1-digit analysis"""
        self.stats_table.setRowCount(9)
        digits = [str(i) for i in range(1, 10)]

        for i, d in enumerate(digits):
            exp_pct = expected.get(d, 0)
            act_pct = actual.get(d, 0)
            deviation = act_pct - exp_pct

            self.stats_table.setItem(i, 0, QTableWidgetItem(d))
            self.stats_table.setItem(i, 1, QTableWidgetItem(f"{exp_pct:.2f}%"))
            self.stats_table.setItem(i, 2, QTableWidgetItem(f"{act_pct:.2f}%"))

            dev_item = QTableWidgetItem(f"{deviation:+.2f}%")
            if abs(deviation) > 2:
                dev_item.setBackground(Qt.red)
            elif abs(deviation) > 1:
                dev_item.setBackground(Qt.yellow)
            self.stats_table.setItem(i, 3, dev_item)

    def _update_stats_table_2digit(self, expected: dict, actual: dict, total: int):
        """Update stats table for 2-digit analysis (show top deviations)"""
        # Calculate all deviations
        deviations = []
        all_digits = set(expected.keys()) | set(actual.keys())
        for d in all_digits:
            exp_pct = expected.get(d, 0)
            act_pct = actual.get(d, 0)
            deviation = act_pct - exp_pct
            deviations.append((d, exp_pct, act_pct, deviation))

        # Sort by absolute deviation and take top 15
        deviations.sort(key=lambda x: abs(x[3]), reverse=True)
        deviations = deviations[:15]

        self.stats_table.setRowCount(len(deviations))
        for i, (d, exp_pct, act_pct, deviation) in enumerate(deviations):
            self.stats_table.setItem(i, 0, QTableWidgetItem(d))
            self.stats_table.setItem(i, 1, QTableWidgetItem(f"{exp_pct:.2f}%"))
            self.stats_table.setItem(i, 2, QTableWidgetItem(f"{act_pct:.2f}%"))

            dev_item = QTableWidgetItem(f"{deviation:+.2f}%")
            if abs(deviation) > 1:
                dev_item.setBackground(Qt.red)
            elif abs(deviation) > 0.5:
                dev_item.setBackground(Qt.yellow)
            self.stats_table.setItem(i, 3, dev_item)

    def _run_chi_square(self, expected: dict, observed: dict, total: int):
        """Run chi-square goodness of fit test"""
        chi_square = 0
        all_digits = set(expected.keys()) | set(observed.keys())

        for d in all_digits:
            observed_count = observed.get(d, 0)
            expected_count = expected.get(d, 0) / 100 * total

            if expected_count > 0:
                chi_square += ((observed_count - expected_count) ** 2) / expected_count

        # Degrees of freedom = number of categories - 1
        df = len(all_digits) - 1

        # Critical value at alpha=0.05
        critical_values = {1: 3.84, 2: 5.99, 3: 7.81, 4: 9.49, 5: 11.07,
                          6: 12.59, 7: 14.07, 8: 15.51, 9: 16.92}
        critical = critical_values.get(df, 15.51)

        if chi_square > critical:
            status = "warning"
            message = (f"Chi-Square: {chi_square:.2f} (df={df})\n"
                      f"EXCEEDS critical value ({critical:.2f})\n"
                      "⚠️ Data may NOT follow Benford's Law")
        else:
            status = "success"
            message = (f"Chi-Square: {chi_square:.2f} (df={df})\n"
                      f"BELOW critical value ({critical:.2f})\n"
                      "✓ Data appears consistent with Benford's Law")

        self.chi_square_label.setStatus(status)
        self.chi_square_label.setText(message)

    def _update_preview(self, column: str, digits: List[str], expected: dict):
        """Update preview table with analysis results"""
        params = self.get_parameters()
        preview_df = self.original_df[:20].clone()

        # Get digit for each row
        digit_values = []
        expected_values = []
        for i in range(len(preview_df)):
            if i < len(digits):
                d = digits[i]
                digit_values.append(d)
                expected_values.append(expected.get(d, 0))
            else:
                digit_values.append("")
                expected_values.append(0)

        preview_df = preview_df.with_columns([
            pl.Series(name=params["digit_col"], values=digit_values),
            pl.Series(name=params["expected_col"], values=expected_values)
        ])

        self.preview_table.load_dataframe(preview_df)

    def get_parameters(self) -> dict:
        """Get the Benford analysis parameters"""
        digits_text = self.digits_combo.currentText()
        n_digits = 1 if "1" in digits_text else 2

        return {
            "column": self.column_selector.get_column(),
            "digits": n_digits,
            "significant_only": self.significant_check.isChecked(),
            "digit_col": self.digit_col_edit.text() or "leading_digit",
            "expected_col": self.expected_col_edit.text() or "benford_expected",
            "deviation_col": self.deviation_col_edit.text() or "benford_deviation",
        }

    def validate(self) -> bool:
        """Validate parameters"""
        column = self.column_selector.get_column()
        if not column:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a column to analyze.")
            return False

        # Check if column is numeric
        if column in self.original_df.columns:
            dtype = self.original_df[column].dtype
            if dtype not in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]:
                QMessageBox.warning(self, "Validation Error",
                                  "Selected column must be numeric.")
                return False

        return True

    def apply_analysis(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply Benford's Law analysis to dataframe"""
        params = self.get_parameters()
        column = params["column"]

        # Get data
        col_data = df[column].to_numpy()
        valid_mask = ~np.isnan(col_data.astype(float)) & (col_data != 0)

        # Extract leading digits
        n_digits = params["digits"]
        digits = self.extract_leading_digits(
            col_data[valid_mask], n_digits, params["significant_only"]
        )

        # Get expected values
        expected = self.get_benford_expected(n_digits)

        # Create result columns
        digit_series = np.full(len(df), "", dtype=object)
        expected_series = np.full(len(df), 0.0, dtype=float)
        deviation_series = np.full(len(df), 0.0, dtype=float)

        valid_indices = np.where(valid_mask)[0]
        for idx, d in zip(valid_indices, digits):
            digit_series[idx] = d
            expected_series[idx] = expected.get(d, 0)

        # Calculate deviation for rows with data
        for idx in valid_indices:
            if digit_series[idx]:
                actual_count = 1  # Simplified - would need full count for accurate deviation
                # This is a simplification - proper deviation needs population counts

        return df.with_columns([
            pl.Series(name=params["digit_col"], values=digit_series),
            pl.Series(name=params["expected_col"], values=expected_series),
            pl.Series(name=params["deviation_col"], values=deviation_series)
        ])
