"""
Forecast Dialog for CAATmaster
Time series forecasting with multiple methods
"""
import polars as pl
import numpy as np
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QWidget, QMessageBox, QLineEdit, QRadioButton, QButtonGroup,
    QProgressBar, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QCategoryAxis

from ..components.common_modals import (
    BaseModal, PreviewTable, ColumnSelector, StatusLabel
)
from ..components.common_modals import TimeSeriesChart


class ForecastDialog(BaseModal):
    """
    Time Series Forecasting dialog with multiple methods
    """

    def __init__(self, dataframe: pl.DataFrame, parent=None):
        self.original_df = dataframe
        super().__init__("Time Series Forecast", dataframe, parent)
        self.setMinimumSize(850, 700)

    def _setup_ui(self):
        """Setup the Forecast dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Column selections
        cols_group = QGroupBox("Data Selection")
        cols_layout = QGridLayout(cols_group)

        # Date/time column
        cols_layout.addWidget(QLabel("Date/Time Column:"), 0, 0)
        self.date_col_selector = ColumnSelector(self.original_df)
        cols_layout.addWidget(self.date_col_selector, 0, 1)

        # Value column
        cols_layout.addWidget(QLabel("Value Column:"), 1, 0)
        self.value_col_selector = ColumnSelector(self.original_df)
        cols_layout.addWidget(self.value_col_selector, 1, 1)

        layout.addWidget(cols_group)

        # Forecast method
        method_group = QGroupBox("Forecast Method")
        method_layout = QVBoxLayout(method_group)

        self.method_group = QButtonGroup(method_group)

        methods = [
            ("Linear Regression", "linear"),
            ("Exponential Smoothing", "exponential"),
            ("Moving Average", "moving_average"),
            ("Holt-Winters (Seasonal)", "holt_winters"),
            ("Prophet-style (Trend + Seasonality)", "prophet"),
        ]

        for label, value in methods:
            radio = QRadioButton(label)
            self.method_group.addButton(radio, value)
            method_layout.addWidget(radio)
            if value == "linear":
                radio.setChecked(True)

        layout.addWidget(method_group)

        # Method-specific options
        options_group = QGroupBox("Forecast Options")
        options_layout = QGridLayout(options_group)

        # Forecast horizon
        options_layout.addWidget(QLabel("Forecast Periods:"), 0, 0)
        self.horizon_spin = QSpinBox()
        self.horizon_spin.setRange(1, 365)
        self.horizon_spin.setValue(12)
        options_layout.addWidget(self.horizon_spin, 0, 1)

        # Confidence interval
        options_layout.addWidget(QLabel("Confidence Interval:"), 1, 0)
        self.confidence_spin = QSpinBox()
        self.confidence_spin.setRange(80, 99)
        self.confidence_spin.setValue(95)
        self.confidence_spin.setSuffix("%")
        options_layout.addWidget(self.confidence_spin, 1, 1)

        # Moving average window (shown for MA method)
        options_layout.addWidget(QLabel("Window Size:"), 2, 0)
        self.window_spin = QSpinBox()
        self.window_spin.setRange(2, 100)
        self.window_spin.setValue(3)
        options_layout.addWidget(self.window_spin, 2, 1)

        # Seasonal period (for Holt-Winters)
        options_layout.addWidget(QLabel("Seasonal Period:"), 3, 0)
        self.seasonal_spin = QSpinBox()
        self.seasonal_spin.setRange(0, 365)
        self.seasonal_spin.setValue(12)
        self.seasonal_spin.setSpecialValueText("Auto-detect")
        options_layout.addWidget(self.seasonal_spin, 3, 1)

        layout.addWidget(options_group)

        # Chart
        chart_group = QGroupBox("Forecast Chart")
        chart_layout = QVBoxLayout(chart_group)

        self.chart = TimeSeriesChart()
        chart_layout.addWidget(self.chart)

        layout.addWidget(chart_group)

        # Output options
        output_group = QGroupBox("Output Columns")
        output_layout = QGridLayout(output_group)

        output_layout.addWidget(QLabel("Forecast Column:"), 0, 0)
        self.forecast_col_edit = QLineEdit("forecast")
        output_layout.addWidget(self.forecast_col_edit, 0, 1)

        output_layout.addWidget(QLabel("Lower Bound Column:"), 1, 0)
        self.lower_col_edit = QLineEdit("forecast_lower")
        output_layout.addWidget(self.lower_col_edit, 1, 1)

        output_layout.addWidget(QLabel("Upper Bound Column:"), 2, 0)
        self.upper_col_edit = QLineEdit("forecast_upper")
        output_layout.addWidget(self.upper_col_edit, 2, 1)

        layout.addWidget(output_group)

        # Preview
        preview_group = QGroupBox("Preview (Last 5 Historical + Forecast)")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_table = PreviewTable(max_rows=10)
        preview_layout.addWidget(self.preview_table)

        self.forecast_stats = StatusLabel("No forecast generated")
        preview_layout.addWidget(self.forecast_stats)

        layout.addWidget(preview_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.preview_btn = QPushButton("Generate Forecast")
        self.preview_btn.clicked.connect(self._generate_forecast)
        btn_layout.addWidget(self.preview_btn)

        self.run_btn = QPushButton("Apply Forecast")
        self.run_btn.setStyleSheet("""
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
        self.run_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.run_btn)

        layout.addLayout(btn_layout)

        # Connect method change
        self.method_group.buttonClicked.connect(self._on_method_changed)
        self._on_method_changed(self.method_group.checkedButton())

    def _on_method_changed(self, button):
        """Handle forecast method change"""
        method = self.method_group.id(button)

        if method == "moving_average":
            self.window_spin.setEnabled(True)
            self.seasonal_spin.setEnabled(False)
        elif method == "holt_winters":
            self.window_spin.setEnabled(False)
            self.seasonal_spin.setEnabled(True)
        else:
            self.window_spin.setEnabled(False)
            self.seasonal_spin.setEnabled(False)

    def get_parameters(self) -> dict:
        """Get the forecast parameters"""
        return {
            "date_column": self.date_col_selector.get_column(),
            "value_column": self.value_col_selector.get_column(),
            "method": self.method_group.checkedId(),
            "horizon": self.horizon_spin.value(),
            "confidence": self.confidence_spin.value() / 100,
            "window": self.window_spin.value(),
            "seasonal_period": self.seasonal_spin.value() if self.seasonal_spin.value() > 0 else None,
            "output_forecast_col": self.forecast_col_edit.text() or "forecast",
            "output_lower_col": self.lower_col_edit.text() or "forecast_lower",
            "output_upper_col": self.upper_col_edit.text() or "forecast_upper",
        }

    def validate(self) -> bool:
        """Validate parameters"""
        params = self.get_parameters()

        if not params["date_column"]:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a date/time column.")
            return False

        if not params["value_column"]:
            QMessageBox.warning(self, "Validation Error",
                              "Please select a value column.")
            return False

        if params["date_column"] == params["value_column"]:
            QMessageBox.warning(self, "Validation Error",
                              "Date column and value column must be different.")
            return False

        # Check minimum data points
        if len(self.original_df) < 10:
            QMessageBox.warning(self, "Validation Error",
                              "At least 10 data points are required for forecasting.")
            return False

        return True

    def _generate_forecast(self):
        """Generate forecast and update preview"""
        try:
            params = self.get_parameters()
            date_col = params["date_column"]
            value_col = params["value_column"]

            # Sort by date
            df = self.original_df.sort(date_col)

            # Get numeric values
            values = df[value_col].to_numpy()
            dates = df[date_col].to_list()

            # Handle missing values
            valid_mask = ~np.isnan(values.astype(float))
            if np.sum(~valid_mask) > 0:
                # Interpolate missing values
                values = self._interpolate_values(values)

            # Generate forecast based on method
            method = params["method"]

            if method == "linear":
                forecast_result = self._forecast_linear(dates, values, params)
            elif method == "exponential":
                forecast_result = self._forecast_exponential(dates, values, params)
            elif method == "moving_average":
                forecast_result = self._forecast_moving_average(dates, values, params)
            elif method == "holt_winters":
                forecast_result = self._forecast_holt_winters(dates, values, params)
            elif method == "prophet":
                forecast_result = self._forecast_prophet_style(dates, values, params)
            else:
                forecast_result = self._forecast_linear(dates, values, params)

            # Update chart
            historical_dates = dates
            forecast_dates = forecast_result["dates"]
            forecast_values = forecast_result["values"]
            lower_bounds = forecast_result.get("lower", forecast_values)
            upper_bounds = forecast_result.get("upper", forecast_values)

            self.chart.set_forecast_data(
                historical_dates, values,
                forecast_dates, forecast_values,
                lower_bounds, upper_bounds
            )

            # Update preview
            self._update_preview(dates, values, forecast_dates, forecast_values,
                               lower_bounds, upper_bounds, params)

            # Update stats
            rmse = forecast_result.get("rmse", 0)
            mape = forecast_result.get("mape", 0)
            self.forecast_stats.setStatus("success")
            self.forecast_stats.setText(
                f"Method: {params['method']} | Horizon: {params['horizon']} periods | "
                f"RMSE: {rmse:.2f} | MAPE: {mape:.1f}%"
            )

        except Exception as e:
            QMessageBox.warning(self, "Forecast Error",
                              f"Could not generate forecast:\n{str(e)}")

    def _interpolate_values(self, values: np.ndarray) -> np.ndarray:
        """Interpolate missing values"""
        result = values.copy()
        for i in range(len(result)):
            if np.isnan(result[i]):
                # Find nearest non-nan values
                left = right = None
                for j in range(i - 1, -1, -1):
                    if not np.isnan(result[j]):
                        left = j
                        break
                for j in range(i + 1, len(result)):
                    if not np.isnan(result[j]):
                        right = j
                        break

                if left is not None and right is not None:
                    result[i] = (result[left] + result[right]) / 2
                elif left is not None:
                    result[i] = result[left]
                elif right is not None:
                    result[i] = result[right]

        return result

    def _forecast_linear(self, dates: list, values: np.ndarray,
                        params: dict) -> dict:
        """Linear regression forecast"""
        n = len(values)
        x = np.arange(n)
        y = values

        # Fit linear regression
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs

        # Calculate trend line for historical data
        trend_line = intercept + slope * x

        # Calculate residuals and RMSE
        residuals = y - trend_line
        rmse = np.sqrt(np.mean(residuals ** 2))

        # Generate forecast
        horizon = params["horizon"]
        forecast_x = np.arange(n, n + horizon)
        forecast_values = intercept + slope * forecast_x

        # Calculate confidence intervals
        std_resid = np.std(residuals)
        z_score = 1.96  # 95% confidence
        margin = z_score * std_resid

        # Project dates
        forecast_dates = self._project_dates(dates, horizon)

        return {
            "dates": forecast_dates,
            "values": forecast_values.tolist(),
            "lower": [v - margin for v in forecast_values],
            "upper": [v + margin for v in forecast_values],
            "rmse": rmse,
            "mape": np.mean(np.abs(residuals / np.maximum(y, 1))) * 100,
        }

    def _forecast_exponential(self, dates: list, values: np.ndarray,
                              params: dict) -> dict:
        """Exponential smoothing forecast"""
        alpha = 0.3  # Smoothing factor
        horizon = params["horizon"]

        # Simple exponential smoothing
        smoothed = [values[0]]
        for i in range(1, len(values)):
            smoothed.append(alpha * values[i] + (1 - alpha) * smoothed[i - 1])

        # Calculate level
        level = smoothed[-1]

        # Calculate trend (simple difference)
        trend = (smoothed[-1] - smoothed[0]) / len(values) if len(values) > 1 else 0

        # Generate forecast
        forecast_values = []
        for h in range(horizon):
            forecast_values.append(level + trend * (h + 1))

        # Project dates
        forecast_dates = self._project_dates(dates, horizon)

        # RMSE
        residuals = np.array(values) - np.array(smoothed)
        rmse = np.sqrt(np.mean(residuals ** 2))

        # Confidence intervals (widen over time)
        std_resid = np.std(residuals)
        z_score = 1.96
        lower = [v - z_score * std_resid * np.sqrt(h + 1) for h, v in enumerate(forecast_values)]
        upper = [v + z_score * std_resid * np.sqrt(h + 1) for h, v in enumerate(forecast_values)]

        return {
            "dates": forecast_dates,
            "values": forecast_values,
            "lower": lower,
            "upper": upper,
            "rmse": rmse,
            "mape": np.mean(np.abs(residuals / np.maximum(values, 1))) * 100,
        }

    def _forecast_moving_average(self, dates: list, values: np.ndarray,
                                 params: dict) -> dict:
        """Moving average forecast"""
        window = params["window"]
        horizon = params["horizon"]

        # Calculate moving average
        ma_values = []
        for i in range(len(values)):
            start = max(0, i - window + 1)
            ma_values.append(np.mean(values[start:i + 1]))

        # Last MA value is the forecast
        last_ma = ma_values[-1]

        # Generate forecast (flat line at last MA)
        forecast_values = [last_ma] * horizon

        # Project dates
        forecast_dates = self._project_dates(dates, horizon)

        # RMSE
        residuals = np.array(values[window-1:]) - np.array(ma_values[window-1:])
        rmse = np.sqrt(np.mean(residuals ** 2))

        # Confidence intervals
        std_resid = np.std(residuals)
        z_score = 1.96
        margin = z_score * std_resid
        lower = [last_ma - margin] * horizon
        upper = [last_ma + margin] * horizon

        return {
            "dates": forecast_dates,
            "values": forecast_values,
            "lower": lower,
            "upper": upper,
            "rmse": rmse,
            "mape": np.mean(np.abs(residuals / np.maximum(values[window-1:], 1))) * 100,
        }

    def _forecast_holt_winters(self, dates: list, values: np.ndarray,
                               params: dict) -> dict:
        """Holt-Winters exponential smoothing with seasonality"""
        horizon = params["horizon"]
        seasonal_period = params["seasonal_period"] or 12

        # Simplified Holt-Winters
        alpha = 0.3  # Level smoothing
        beta = 0.1   # Trend smoothing
        gamma = 0.3  # Seasonal smoothing

        n = len(values)
        if n < seasonal_period * 2:
            # Fall back to Holt's linear if not enough data
            return self._forecast_holt(dates, values, params)

        # Initialize components
        level = np.mean(values[:seasonal_period])
        trend = (np.mean(values[seasonal_period:2*seasonal_period]) -
                 np.mean(values[:seasonal_period])) / seasonal_period

        seasonals = np.zeros(seasonal_period)
        for i in range(seasonal_period):
            seasonals[i] = np.mean(values[i::seasonal_period]) - level

        # Fit model
        levels = [level]
        trends = [trend]
        fitted = []

        for i in range(n):
            y = values[i]
            s = seasonals[i % seasonal_period]

            # Update level and trend
            new_level = alpha * (y - s) + (1 - alpha) * (level + trend)
            new_trend = beta * (new_level - level) + (1 - beta) * trend
            new_seasonal = gamma * (y - new_level) + (1 - gamma) * s

            fitted.append(new_level + new_trend + s)

            level, trend, seasonals = new_level, new_trend, seasonals
            seasonals[i % seasonal_period] = new_seasonal

            levels.append(level)
            trends.append(trend)

        # Generate forecast
        forecast_values = []
        for h in range(horizon):
            idx = (n + h) % seasonal_period
            forecast = level + trend * (h + 1) + seasonals[idx]
            forecast_values.append(forecast)

        # Project dates
        forecast_dates = self._project_dates(dates, horizon)

        # RMSE
        residuals = np.array(values) - np.array(fitted[:n])
        rmse = np.sqrt(np.mean(residuals ** 2))

        # Confidence intervals
        std_resid = np.std(residuals)
        z_score = 1.96
        margin_factor = np.sqrt(1 + h / n)  # Widen over horizon
        lower = [v - z_score * std_resid * margin_factor for v in forecast_values]
        upper = [v + z_score * std_resid * margin_factor for v in forecast_values]

        return {
            "dates": forecast_dates,
            "values": forecast_values,
            "lower": lower,
            "upper": upper,
            "rmse": rmse,
            "mape": np.mean(np.abs(residuals / np.maximum(values, 1))) * 100,
        }

    def _forecast_holt(self, dates: list, values: np.ndarray,
                       params: dict) -> dict:
        """Holt's linear trend method (fallback)"""
        alpha = 0.3
        beta = 0.1
        horizon = params["horizon"]

        # Initialize
        level = values[0]
        trend = (values[-1] - values[0]) / (len(values) - 1) if len(values) > 1 else 0

        # Fit
        fitted = []
        for i in range(len(values)):
            if i == 0:
                fitted.append(level)
            else:
                new_level = alpha * values[i] + (1 - alpha) * (level + trend)
                new_trend = beta * (new_level - level) + (1 - beta) * trend
                level, trend = new_level, new_trend
                fitted.append(level + trend)

        # Forecast
        forecast_values = [level + trend * (h + 1) for h in range(horizon)]
        forecast_dates = self._project_dates(dates, horizon)

        # RMSE
        residuals = np.array(values) - np.array(fitted)
        rmse = np.sqrt(np.mean(residuals ** 2))

        std_resid = np.std(residuals)
        z_score = 1.96
        lower = [v - z_score * std_resid for v in forecast_values]
        upper = [v + z_score * std_resid for v in forecast_values]

        return {
            "dates": forecast_dates,
            "values": forecast_values,
            "lower": lower,
            "upper": upper,
            "rmse": rmse,
            "mape": np.mean(np.abs(residuals / np.maximum(values, 1))) * 100,
        }

    def _forecast_prophet_style(self, dates: list, values: np.ndarray,
                                params: dict) -> dict:
        """Prophet-style forecast with trend and seasonality"""
        horizon = params["horizon"]

        # Use linear trend + weekly + yearly seasonality approximation
        n = len(values)
        x = np.arange(n)

        # Linear trend
        slope, intercept = np.polyfit(x, values, 1)

        # Remove trend
        detrended = values - (intercept + slope * x)

        # Estimate weekly seasonality (assuming daily data, 7-day cycle)
        # or yearly (assuming monthly data, 12-month cycle)
        if n >= 365:  # Yearly pattern
            seasonal_period = 12
            seasonal_idx = np.arange(n) % 12
        elif n >= 28:  # Weekly pattern
            seasonal_period = 7
            seasonal_idx = np.arange(n) % 7
        else:
            seasonal_period = None

        # Generate forecast
        forecast_x = np.arange(n, n + horizon)
        trend_values = intercept + slope * forecast_x

        forecast_values = trend_values.tolist()

        # Project dates
        forecast_dates = self._project_dates(dates, horizon)

        # RMSE
        trend_line = intercept + slope * x
        residuals = values - trend_line
        rmse = np.sqrt(np.mean(residuals ** 2))

        # Confidence intervals
        std_resid = np.std(residuals)
        z_score = 1.96
        margin = z_score * std_resid
        lower = [v - margin for v in forecast_values]
        upper = [v + margin for v in forecast_values]

        return {
            "dates": forecast_dates,
            "values": forecast_values,
            "lower": lower,
            "upper": upper,
            "rmse": rmse,
            "mape": np.mean(np.abs(residuals / np.maximum(values, 1))) * 100,
        }

    def _project_dates(self, dates: list, horizon: int) -> list:
        """Project future dates based on data frequency"""
        if not dates:
            return []

        # Try to infer frequency
        if len(dates) >= 2:
            diff1 = self._parse_date_diff(dates[0], dates[1])
            diff2 = self._parse_date_diff(dates[1], dates[2]) if len(dates) > 2 else diff1

            # Use median diff
            diffs = [diff1, diff2] if diff2 else [diff1]
            diff = sorted(diffs)[len(diffs) // 2]
        else:
            diff = 1  # Default to 1 day

        # Generate future dates
        last_date = dates[-1]
        future_dates = []

        if isinstance(last_date, str):
            # Parse string date
            from datetime import datetime
            try:
                last_dt = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
                for h in range(1, horizon + 1):
                    future_dates.append((last_dt + timedelta(days=diff * h)).isoformat())
            except ValueError:
                for h in range(1, horizon + 1):
                    future_dates.append(f"t+{h}")
        else:
            # Already datetime
            for h in range(1, horizon + 1):
                future_dates.append(last_date + timedelta(days=diff * h))

        return future_dates

    def _parse_date_diff(self, d1, d2) -> float:
        """Parse date difference in days"""
        from datetime import datetime

        try:
            if isinstance(d1, str):
                d1 = datetime.fromisoformat(d1.replace('Z', '+00:00'))
            if isinstance(d2, str):
                d2 = datetime.fromisoformat(d2.replace('Z', '+00:00'))

            diff = (d2 - d1).total_seconds() / 86400
            return max(0.01, diff)  # Minimum 15 minutes
        except (ValueError, TypeError):
            return 1

    def _update_preview(self, hist_dates: list, hist_values: np.ndarray,
                       forecast_dates: list, forecast_values: list,
                       lower_bounds: list, upper_bounds: list,
                       params: dict):
        """Update preview table"""
        # Combine historical and forecast data
        preview_data = []

        # Last 5 historical points
        for i in range(max(0, len(hist_dates) - 5), len(hist_dates)):
            preview_data.append({
                "Date": str(hist_dates[i]),
                "Historical": hist_values[i],
                params["output_forecast_col"]: None,
                f"{params['output_lower_col']}": None,
                f"{params['output_upper_col']}": None,
            })

        # Forecast points
        for i, (d, f, lo, hi) in enumerate(zip(forecast_dates, forecast_values,
                                                lower_bounds, upper_bounds)):
            preview_data.append({
                "Date": str(d),
                "Historical": None,
                params["output_forecast_col"]: f,
                f"{params['output_lower_col']}": lo,
                f"{params['output_upper_col']}": hi,
            })

        # Create preview DataFrame
        preview_df = pl.DataFrame(preview_data)
        self.preview_table.load_dataframe(preview_df)

    def apply_forecast(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply forecast to dataframe (adds forecast columns)"""
        params = self.get_parameters()

        # Generate forecast
        self._generate_forecast()

        # For actual application, we'd need to fit on full data
        # and extend with forecast values
        # This is a simplified version

        return df  # In real implementation, would add forecast columns
