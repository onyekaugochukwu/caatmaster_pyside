"""
Visualizations View - Create charts and graphs from data
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox,
    QFormLayout, QCheckBox, QFileDialog, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from pathlib import Path
import io


class ChartCanvas(QWidget):
    """Widget to display matplotlib charts"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Placeholder label
        self.placeholder_label = QLabel("Create a chart to see it here")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #999; font-size: 14px; padding: 50px;")
        layout.addWidget(self.placeholder_label)

    def set_figure(self, figure):
        """Set the matplotlib figure to display"""
        self.figure = figure

        # Convert figure to pixmap
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        canvas = FigureCanvasAgg(figure)
        buf = io.BytesIO()
        canvas.print_figure(buf, format='png', dpi=150)
        buf.seek(0)

        # Create pixmap
        pixmap = QPixmap()
        pixmap.loadFromData(buf.getvalue(), 'PNG')

        # Display pixmap
        self.placeholder_label.setPixmap(pixmap)
        self.placeholder_label.setStyleSheet("")

    def clear(self):
        """Clear the canvas"""
        self.figure = None
        self.placeholder_label.clear()
        self.placeholder_label.setText("Create a chart to see it here")
        self.placeholder_label.setPixmap(None)
        self.placeholder_label.setStyleSheet("color: #999; font-size: 14px; padding: 50px;")


class VisualizationsView(QWidget):
    """Visualizations and chart builder view"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_dataframe = None
        self.viz_service = None
        self.current_figure = None
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Data Visualizations")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        main_layout.addLayout(header_layout)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Chart configuration
        config_panel = QGroupBox("Chart Configuration")
        config_layout = QVBoxLayout()

        # Chart type
        form_layout = QFormLayout()

        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems([
            "Bar Chart",
            "Line Chart",
            "Scatter Plot",
            "Histogram",
            "Pie Chart",
            "Box Plot",
            "Heatmap",
            "Area Chart"
        ])
        self.chart_type_combo.currentIndexChanged.connect(self.on_chart_type_changed)
        form_layout.addRow("Chart Type:", self.chart_type_combo)

        # X axis column
        self.x_column_combo = QComboBox()
        self.x_column_combo.currentIndexChanged.connect(self.update_column_options)
        form_layout.addRow("X Axis:", self.x_column_combo)

        # Y axis columns (for line/area charts)
        self.y_column_combo = QComboBox()
        self.y_column_combo.setMaximumWidth(200)
        form_layout.addRow("Y Axis:", self.y_column_combo)

        # Value column (for histogram/box)
        self.value_column_combo = QComboBox()
        form_layout.addRow("Value Column:", self.value_column_combo)

        # Group/Color column
        self.group_column_combo = QComboBox()
        self.group_column_combo.setMaximumWidth(200)
        form_layout.addRow("Group/Color:", self.group_column_combo)

        # Label column (for pie chart)
        self.label_column_combo = QComboBox()
        form_layout.addRow("Label Column:", self.label_column_combo)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QFormLayout()

        self.title_input = QComboBox()
        self.title_input.setEditable(True)
        self.title_input.addItems(["My Chart", "Data Distribution", "Trend Analysis"])
        options_layout.addRow("Title:", self.title_input)

        self.fig_width_spin = QSpinBox()
        self.fig_width_spin.setRange(4, 20)
        self.fig_width_spin.setValue(10)
        options_layout.addRow("Width:", self.fig_width_spin)

        self.fig_height_spin = QSpinBox()
        self.fig_height_spin.setRange(4, 20)
        self.fig_height_spin.setValue(6)
        options_layout.addRow("Height:", self.fig_height_spin)

        self.bins_spin = QSpinBox()
        self.bins_spin.setRange(5, 100)
        self.bins_spin.setValue(30)
        options_layout.addRow("Bins:", self.bins_spin)

        options_group.setLayout(options_layout)

        config_layout.addLayout(form_layout)
        config_layout.addWidget(options_group)

        # Buttons
        button_layout = QVBoxLayout()

        self.create_btn = QPushButton("Create Chart")
        self.create_btn.setStyleSheet("""
            QPushButton {
                background: #0078d4;
                color: white;
                padding: 10px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #106ebe;
            }
        """)
        self.create_btn.clicked.connect(self.create_chart)
        button_layout.addWidget(self.create_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_chart)
        button_layout.addWidget(self.clear_btn)

        self.export_btn = QPushButton("Export Chart")
        self.export_btn.clicked.connect(self.export_chart)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()

        config_layout.addLayout(button_layout)
        config_panel.setLayout(config_layout)

        splitter.addWidget(config_panel)

        # Right panel - Chart canvas
        canvas_panel = QGroupBox("Chart Preview")
        canvas_layout = QVBoxLayout()

        self.chart_canvas = ChartCanvas()
        canvas_layout.addWidget(self.chart_canvas)

        canvas_panel.setLayout(canvas_layout)
        splitter.addWidget(canvas_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        # Initialize UI state
        self.on_chart_type_changed(0)

    def set_dataframe(self, df):
        """Set the current data for visualizations"""
        self.current_dataframe = df

        # Initialize visualization service
        from services.visualization_service import VisualizationService
        if self.viz_service is None:
            self.viz_service = VisualizationService()

        # Update column dropdowns
        self.update_column_dropdowns()

    def update_column_dropdowns(self):
        """Update all column dropdowns with DataFrame columns"""
        if self.current_dataframe is None:
            return

        # Get all columns
        all_columns = list(self.current_dataframe.columns)
        numeric_columns = self.viz_service.get_numeric_columns(self.current_dataframe)
        categorical_columns = self.viz_service.get_categorical_columns(self.current_dataframe)

        # Clear all combos
        for combo in [self.x_column_combo, self.y_column_combo, self.value_column_combo,
                      self.group_column_combo, self.label_column_combo]:
            combo.clear()
            combo.addItem("")

        # X axis - all columns
        self.x_column_combo.addItems(all_columns)

        # Y axis - numeric only
        self.y_column_combo.addItems(numeric_columns)

        # Value column - numeric only
        self.value_column_combo.addItems(numeric_columns)

        # Group/Color - all columns
        self.group_column_combo.addItems(all_columns)

        # Label column - all columns
        self.label_column_combo.addItems(all_columns)

    def on_chart_type_changed(self, index: int):
        """Handle chart type selection change"""
        chart_types = {
            0: "bar",      # Bar Chart
            1: "line",     # Line Chart
            2: "scatter",  # Scatter Plot
            3: "histogram",# Histogram
            4: "pie",      # Pie Chart
            5: "box",      # Box Plot
            6: "heatmap",  # Heatmap
            7: "area"      # Area Chart
        }

        chart_type = chart_types.get(index, "bar")

        # Show/hide relevant fields
        self.x_column_combo.setVisible(True)
        self.y_column_combo.setVisible(False)
        self.value_column_combo.setVisible(False)
        self.group_column_combo.setVisible(True)
        self.label_column_combo.setVisible(False)
        self.bins_spin.setEnabled(False)

        if chart_type == "bar":
            pass  # X axis, Y axis, group
        elif chart_type == "line":
            self.y_column_combo.setVisible(True)
        elif chart_type == "scatter":
            # X axis, Y axis, group
            pass
        elif chart_type == "histogram":
            self.x_column_combo.setVisible(False)
            self.value_column_combo.setVisible(True)
            self.bins_spin.setEnabled(True)
        elif chart_type == "pie":
            self.x_column_combo.setVisible(False)
            self.label_column_combo.setVisible(True)
            self.value_column_combo.setVisible(True)
        elif chart_type == "box":
            self.x_column_combo.setVisible(False)
            self.value_column_combo.setVisible(True)
        elif chart_type == "heatmap":
            self.x_column_combo.setVisible(False)
            self.group_column_combo.setVisible(False)
        elif chart_type == "area":
            self.y_column_combo.setVisible(True)

    def update_column_options(self):
        """Update column options based on selections"""
        # Can be used to filter available columns based on x selection
        pass

    def create_chart(self):
        """Create the chart based on current configuration"""
        if self.current_dataframe is None:
            QMessageBox.warning(self, "No Data", "Please load data first")
            return

        chart_type_idx = self.chart_type_combo.currentIndex()
        chart_types = ["bar", "line", "scatter", "histogram", "pie", "box", "heatmap", "area"]
        chart_type = chart_types[chart_type_idx]

        title = self.title_input.currentText()
        figsize = (self.fig_width_spin.value(), self.fig_height_spin.value())

        try:
            if chart_type == "bar":
                x_col = self.x_column_combo.currentText()
                y_col = self.y_column_combo.currentText()
                group_col = self.group_column_combo.currentText() or None

                if not x_col or not y_col:
                    raise ValueError("Please select X and Y columns")

                self.current_figure = self.viz_service.create_bar_chart(
                    self.current_dataframe, x_col, y_col, title, group_col,
                    figsize=figsize
                )

            elif chart_type == "line":
                x_col = self.x_column_combo.currentText()
                y_col = self.y_column_combo.currentText()

                if not x_col or not y_col:
                    raise ValueError("Please select X and Y columns")

                self.current_figure = self.viz_service.create_line_chart(
                    self.current_dataframe, x_col, [y_col], title, figsize=figsize
                )

            elif chart_type == "scatter":
                x_col = self.x_column_combo.currentText()
                y_col = self.y_column_combo.currentText()
                group_col = self.group_column_combo.currentText() or None

                if not x_col or not y_col:
                    raise ValueError("Please select X and Y columns")

                self.current_figure = self.viz_service.create_scatter_plot(
                    self.current_dataframe, x_col, y_col, title, group_col,
                    figsize=figsize
                )

            elif chart_type == "histogram":
                val_col = self.value_column_combo.currentText()

                if not val_col:
                    raise ValueError("Please select a value column")

                self.current_figure = self.viz_service.create_histogram(
                    self.current_dataframe, val_col, title,
                    bins=self.bins_spin.value(),
                    figsize=figsize
                )

            elif chart_type == "pie":
                label_col = self.label_column_combo.currentText()
                val_col = self.value_column_combo.currentText()

                if not label_col or not val_col:
                    raise ValueError("Please select label and value columns")

                self.current_figure = self.viz_service.create_pie_chart(
                    self.current_dataframe, label_col, val_col, title, figsize=figsize
                )

            elif chart_type == "box":
                val_col = self.value_column_combo.currentText()
                group_col = self.x_column_combo.currentText() or None

                if not val_col:
                    raise ValueError("Please select a value column")

                self.current_figure = self.viz_service.create_box_plot(
                    self.current_dataframe, val_col, group_col, title, figsize=figsize
                )

            elif chart_type == "heatmap":
                self.current_figure = self.viz_service.create_heatmap(
                    self.current_dataframe, title, figsize=figsize
                )

            elif chart_type == "area":
                x_col = self.x_column_combo.currentText()
                y_col = self.y_column_combo.currentText()

                if not x_col or not y_col:
                    raise ValueError("Please select X and Y columns")

                self.current_figure = self.viz_service.create_area_chart(
                    self.current_dataframe, x_col, [y_col], title, figsize=figsize
                )

            # Display the chart
            self.chart_canvas.set_figure(self.current_figure)
            self.export_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Chart Error", f"Failed to create chart:\n{str(e)}")

    def clear_chart(self):
        """Clear the current chart"""
        self.chart_canvas.clear()
        self.current_figure = None
        self.export_btn.setEnabled(False)

    def export_chart(self):
        """Export the current chart"""
        if self.current_figure is None:
            QMessageBox.warning(self, "No Chart", "Please create a chart first")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Chart",
            "",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg)"
        )

        if file_path:
            try:
                self.viz_service.save_figure(self.current_figure, file_path)
                QMessageBox.information(self, "Export Successful", f"Chart saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export chart:\n{str(e)}")
