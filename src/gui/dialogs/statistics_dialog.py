"""
Statistics dialog — descriptive statistics, hypothesis tests, correlation,
and distribution checks, reachable from the Statistics menu.

Unlike a transformation dialog, these don't modify the dataset — they
compute a result and display it, the same way a report does. That's why
this is a plain QDialog rather than a BaseModal/TransformationPipeline step.
"""
import numpy as np
import polars as pl
from scipy import stats as scipy_stats

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QPushButton,
    QTextEdit, QTableWidget, QTableWidgetItem, QSpinBox, QDoubleSpinBox,
    QLabel
)

NUMERIC_DTYPES = (
    pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32, pl.Int64,
    pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
)


def _numeric_columns(df: pl.DataFrame):
    return [c for c in df.columns if df[c].dtype in NUMERIC_DTYPES]


class StatisticsDialog(QDialog):
    """One dialog class handling every Statistics-menu operation, selected
    by `stat_type`. Each type builds its own small parameter form, then
    computes on Run and shows a readable result."""

    TITLES = {
        "stat_summary": "Summary Statistics",
        "stat_central": "Mean / Median",
        "stat_variance": "Variance",
        "stat_ttest": "T-Test",
        "stat_anova": "ANOVA",
        "stat_chisquare": "Chi-Square Test",
        "stat_pearson": "Pearson Correlation",
        "stat_spearman": "Spearman Correlation",
        "stat_heatmap": "Correlation Heatmap",
        "stat_normal": "Normal Distribution Test",
        "stat_binomial": "Binomial Distribution Test",
        "stat_poisson": "Poisson Distribution Test",
    }

    def __init__(self, stat_type: str, dataframe: pl.DataFrame, parent=None):
        super().__init__(parent)
        self.stat_type = stat_type
        self.df = dataframe
        self.setWindowTitle(self.TITLES.get(stat_type, "Statistics"))
        self.setMinimumSize(560, 480)
        self.form_widgets = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.form_layout = QFormLayout()
        self._build_form()
        layout.addLayout(self.form_layout)

        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self._run)
        layout.addWidget(run_btn)

        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area, 1)

        self.result_table = QTableWidget()
        self.result_table.setVisible(False)
        layout.addWidget(self.result_table, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        if not _numeric_columns(self.df) and self.stat_type != "stat_chisquare":
            self.result_area.setPlainText("No numeric columns available in this dataset.")

    # ------------------------------------------------------------------
    # Form construction
    # ------------------------------------------------------------------

    def _add_column_combo(self, label, columns):
        combo = QComboBox()
        combo.addItems(columns)
        self.form_layout.addRow(label, combo)
        return combo

    def _build_form(self):
        numeric = _numeric_columns(self.df)
        all_cols = list(self.df.columns)

        if self.stat_type in ("stat_summary", "stat_heatmap"):
            return  # Runs over all numeric columns, no parameters needed

        if self.stat_type in ("stat_central", "stat_variance", "stat_normal", "stat_poisson"):
            self.form_widgets["column"] = self._add_column_combo("Column", numeric)

        elif self.stat_type in ("stat_ttest", "stat_pearson", "stat_spearman"):
            self.form_widgets["col_a"] = self._add_column_combo("Column A", numeric)
            self.form_widgets["col_b"] = self._add_column_combo("Column B", numeric)

        elif self.stat_type == "stat_anova":
            self.form_widgets["value_col"] = self._add_column_combo("Value column", numeric)
            self.form_widgets["group_col"] = self._add_column_combo("Group column", all_cols)

        elif self.stat_type == "stat_chisquare":
            self.form_widgets["col_a"] = self._add_column_combo("Column A", all_cols)
            self.form_widgets["col_b"] = self._add_column_combo("Column B", all_cols)

        elif self.stat_type == "stat_binomial":
            successes = QSpinBox()
            successes.setRange(0, 10_000_000)
            self.form_layout.addRow("Observed successes", successes)
            self.form_widgets["successes"] = successes

            trials = QSpinBox()
            trials.setRange(1, 10_000_000)
            trials.setValue(max(1, len(self.df)))
            self.form_layout.addRow("Number of trials", trials)
            self.form_widgets["trials"] = trials

            p = QDoubleSpinBox()
            p.setRange(0.0, 1.0)
            p.setSingleStep(0.01)
            p.setValue(0.5)
            self.form_layout.addRow("Expected probability", p)
            self.form_widgets["p"] = p

    # ------------------------------------------------------------------
    # Result rendering
    # ------------------------------------------------------------------

    def _text(self, s: str):
        self.result_table.setVisible(False)
        self.result_area.setVisible(True)
        self.result_area.setPlainText(s)

    def _table(self, headers, rows):
        self.result_area.setVisible(False)
        self.result_table.setVisible(True)
        self.result_table.setColumnCount(len(headers))
        self.result_table.setHorizontalHeaderLabels(headers)
        self.result_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                self.result_table.setItem(r, c, QTableWidgetItem(str(val)))
        self.result_table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _run(self):
        try:
            handler = getattr(self, f"_run_{self.stat_type.split('stat_', 1)[-1]}", None)
            if handler is None:
                self._text(f"Unsupported statistics type: {self.stat_type}")
                return
            handler()
        except Exception as e:
            self._text(f"Could not compute: {e}")

    # ------------------------------------------------------------------
    # Computations
    # ------------------------------------------------------------------

    def _run_summary(self):
        numeric = _numeric_columns(self.df)
        if not numeric:
            self._text("No numeric columns to summarize.")
            return
        headers = ["Column", "Count", "Mean", "Std", "Min", "25%", "Median", "75%", "Max"]
        rows = []
        for col in numeric:
            s = self.df[col].drop_nulls()
            if s.is_empty():
                continue
            std = s.std()
            rows.append([
                col, s.len(),
                f"{s.mean():.4f}", f"{std:.4f}" if std is not None else "N/A",
                f"{s.min():.4f}", f"{s.quantile(0.25):.4f}", f"{s.median():.4f}",
                f"{s.quantile(0.75):.4f}", f"{s.max():.4f}",
            ])
        self._table(headers, rows)

    def _run_central(self):
        col = self.form_widgets["column"].currentText()
        s = self.df[col].drop_nulls()
        mode_vals = s.mode().to_list()[:3]
        mode_str = ", ".join(str(v) for v in mode_vals) if mode_vals else "N/A"
        self._text(
            f"Column: {col}\nCount: {s.len()}\n\n"
            f"Mean: {s.mean():.4f}\nMedian: {s.median():.4f}\nMode: {mode_str}"
        )

    def _run_variance(self):
        col = self.form_widgets["column"].currentText()
        s = self.df[col].drop_nulls()
        var = s.var()
        std = s.std()
        iqr = s.quantile(0.75) - s.quantile(0.25)
        rng = s.max() - s.min()
        self._text(
            f"Column: {col}\nCount: {s.len()}\n\n"
            f"Variance: {var:.4f}\nStd Dev: {std:.4f}\n"
            f"Range: {rng:.4f}\nIQR: {iqr:.4f}"
        )

    def _run_ttest(self):
        col_a = self.form_widgets["col_a"].currentText()
        col_b = self.form_widgets["col_b"].currentText()
        a = self.df[col_a].drop_nulls().to_numpy()
        b = self.df[col_b].drop_nulls().to_numpy()
        if len(a) < 2 or len(b) < 2:
            self._text("Need at least 2 values in each column to run a t-test.")
            return
        t_stat, p_value = scipy_stats.ttest_ind(a, b, equal_var=False)
        interp = ("statistically significant difference (p < 0.05)" if p_value < 0.05
                  else "no statistically significant difference (p >= 0.05)")
        self._text(
            "Independent samples t-test (Welch's, unequal variance)\n"
            f"{col_a} (n={len(a)}, mean={a.mean():.4f}) vs "
            f"{col_b} (n={len(b)}, mean={b.mean():.4f})\n\n"
            f"t-statistic: {t_stat:.4f}\np-value: {p_value:.6f}\n\n"
            f"Result: {interp}"
        )

    def _run_anova(self):
        value_col = self.form_widgets["value_col"].currentText()
        group_col = self.form_widgets["group_col"].currentText()
        groups, labels = [], []
        for g in self.df[group_col].unique().drop_nulls().to_list():
            vals = self.df.filter(pl.col(group_col) == g)[value_col].drop_nulls().to_numpy()
            if len(vals) > 0:
                groups.append(vals)
                labels.append(str(g))
        if len(groups) < 2:
            self._text("Need at least 2 groups with data to run ANOVA.")
            return
        f_stat, p_value = scipy_stats.f_oneway(*groups)
        interp = ("at least one group mean differs significantly (p < 0.05)" if p_value < 0.05
                  else "no statistically significant difference between group means (p >= 0.05)")
        group_summary = "\n".join(f"  {lbl}: n={len(g)}, mean={g.mean():.4f}" for lbl, g in zip(labels, groups))
        self._text(
            f"One-way ANOVA: {value_col} across groups in {group_col}\n\n{group_summary}\n\n"
            f"F-statistic: {f_stat:.4f}\np-value: {p_value:.6f}\n\nResult: {interp}"
        )

    def _run_chisquare(self):
        col_a = self.form_widgets["col_a"].currentText()
        col_b = self.form_widgets["col_b"].currentText()
        pdf = self.df.select([col_a, col_b]).drop_nulls().to_pandas()
        if pdf.empty:
            self._text("No complete rows available for these two columns.")
            return
        contingency = pdf.pivot_table(index=col_a, columns=col_b, aggfunc='size', fill_value=0)
        if contingency.shape[0] < 2 or contingency.shape[1] < 2:
            self._text("Need at least 2 distinct values in each column to run a chi-square test.")
            return
        chi2, p_value, dof, _ = scipy_stats.chi2_contingency(contingency.values)
        interp = ("statistically significant association (p < 0.05)" if p_value < 0.05
                  else "no statistically significant association (p >= 0.05)")
        self._text(
            f"Chi-square test of independence: {col_a} vs {col_b}\n\n"
            f"Chi-square statistic: {chi2:.4f}\nDegrees of freedom: {dof}\np-value: {p_value:.6f}\n\n"
            f"Result: {interp}"
        )

    def _run_pearson(self):
        self._run_correlation("pearson")

    def _run_spearman(self):
        self._run_correlation("spearman")

    def _run_correlation(self, method):
        col_a = self.form_widgets["col_a"].currentText()
        col_b = self.form_widgets["col_b"].currentText()
        pdf = self.df.select([col_a, col_b]).drop_nulls()
        a = pdf[col_a].to_numpy()
        b = pdf[col_b].to_numpy()
        if len(a) < 3:
            self._text("Need at least 3 paired values to compute a correlation.")
            return
        if method == "pearson":
            r, p_value = scipy_stats.pearsonr(a, b)
            name = "Pearson"
        else:
            r, p_value = scipy_stats.spearmanr(a, b)
            name = "Spearman"
        magnitude = abs(r)
        strength = (
            "very weak" if magnitude < 0.2 else
            "weak" if magnitude < 0.4 else
            "moderate" if magnitude < 0.6 else
            "strong" if magnitude < 0.8 else
            "very strong"
        )
        direction = "positive" if r > 0 else "negative"
        self._text(
            f"{name} correlation: {col_a} vs {col_b} (n={len(a)})\n\n"
            f"r = {r:.4f}\np-value: {p_value:.6f}\n\n"
            f"Interpretation: {strength} {direction} correlation"
        )

    def _run_heatmap(self):
        numeric = _numeric_columns(self.df)
        if len(numeric) < 2:
            self._text("Need at least 2 numeric columns for a correlation heatmap.")
            return
        pdf = self.df.select(numeric).to_pandas()
        corr = pdf.corr(method="pearson")

        self.result_area.setVisible(False)
        self.result_table.setVisible(True)
        self.result_table.setColumnCount(len(numeric))
        self.result_table.setRowCount(len(numeric))
        self.result_table.setHorizontalHeaderLabels(numeric)
        self.result_table.setVerticalHeaderLabels(numeric)
        for i, row_name in enumerate(numeric):
            for j, col_name in enumerate(numeric):
                val = corr.loc[row_name, col_name]
                item = QTableWidgetItem(f"{val:.2f}")
                item.setTextAlignment(Qt.AlignCenter)
                if val >= 0:
                    color = QColor(0, 120, 212, int(abs(val) * 200))
                else:
                    color = QColor(209, 52, 56, int(abs(val) * 200))
                item.setBackground(color)
                self.result_table.setItem(i, j, item)
        self.result_table.resizeColumnsToContents()

    def _run_normal(self):
        col = self.form_widgets["column"].currentText()
        s = self.df[col].drop_nulls().to_numpy()
        if len(s) < 3:
            self._text("Need at least 3 data points to test normality.")
            return
        stat, p_value = scipy_stats.shapiro(s[:5000])  # Shapiro-Wilk has a practical sample-size cap
        interp = ("data significantly deviates from a normal distribution (p < 0.05)" if p_value < 0.05
                  else "no significant deviation from normality detected (p >= 0.05)")
        self._text(
            f"Shapiro-Wilk normality test: {col} (n={len(s)})\n\n"
            f"W-statistic: {stat:.4f}\np-value: {p_value:.6f}\n\nResult: {interp}"
        )

    def _run_binomial(self):
        k = self.form_widgets["successes"].value()
        n = self.form_widgets["trials"].value()
        p = self.form_widgets["p"].value()
        if k > n:
            self._text("Observed successes cannot exceed number of trials.")
            return
        result = scipy_stats.binomtest(k, n, p)
        interp = ("observed rate significantly differs from expected (p < 0.05)" if result.pvalue < 0.05
                  else "observed rate consistent with expected probability (p >= 0.05)")
        self._text(
            f"Binomial test: {k} successes in {n} trials, expected p={p}\n\n"
            f"Observed rate: {k / n:.4f}\np-value: {result.pvalue:.6f}\n\nResult: {interp}"
        )

    def _run_poisson(self):
        col = self.form_widgets["column"].currentText()
        s = self.df[col].drop_nulls().to_numpy()
        if len(s) < 5:
            self._text("Need at least 5 data points for a Poisson goodness-of-fit test.")
            return
        lam = s.mean()
        max_val = int(max(s.max(), lam * 3))
        bins = list(range(0, max_val + 2))
        observed, _ = np.histogram(s, bins=bins)
        expected = np.array([scipy_stats.poisson.pmf(k, lam) * len(s) for k in bins[:-1]])

        # Merge out low-expected-count tail bins so chi-square assumptions hold
        mask = expected >= 1
        if mask.sum() < 2:
            self._text(f"Sample mean (lambda): {lam:.4f}\n\nNot enough spread to run a goodness-of-fit test.")
            return
        observed_m = observed[mask]
        expected_m = expected[mask] * (observed_m.sum() / expected[mask].sum())
        chi2, p_value = scipy_stats.chisquare(observed_m, expected_m)
        interp = ("data significantly deviates from a Poisson distribution (p < 0.05)" if p_value < 0.05
                  else "no significant deviation from a Poisson distribution (p >= 0.05)")
        self._text(
            f"Poisson goodness-of-fit test: {col} (n={len(s)})\n\n"
            f"Sample mean (lambda): {lam:.4f}\nChi-square statistic: {chi2:.4f}\np-value: {p_value:.6f}\n\n"
            f"Result: {interp}"
        )
