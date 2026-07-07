"""
Visualizations View - Create charts and graphs from data
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QSpinBox, QDoubleSpinBox, QGroupBox,
    QFormLayout, QCheckBox, QFileDialog, QMessageBox, QSplitter, QDialog
)
from PySide6.QtCore import Qt, Signal
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.patches import Rectangle, Wedge
from matplotlib.collections import PathCollection

from services.visualization_service import VisualizationService
from gui.theme import Colors, Spacing
from gui.components.common_modals import create_primary_button


class ChartCanvas(QWidget):
    """Widget to display matplotlib charts as a live, interactive Qt canvas
    (zoom/pan/save via matplotlib's own navigation toolbar) rather than a
    static rasterized image — plus hover tooltips and, where the chart type
    supports it, click-to-drill into the underlying rows."""

    pointClicked = Signal(object)  # emits a polars DataFrame of matched rows

    def __init__(self, parent=None):
        super().__init__(parent)
        self.figure = None
        self.canvas = None
        self.toolbar = None
        self._click_resolver = None  # callable(event) -> Optional[pl.DataFrame]
        self._annotation = None
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.placeholder_label = QLabel("Create a chart to see it here")
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet(f"color: {Colors.TEXT_TERTIARY}; font-size: 14px; padding: 50px;")
        self.layout.addWidget(self.placeholder_label)

    def set_figure(self, figure, click_resolver=None):
        """Display a matplotlib figure as a live, interactive canvas.

        click_resolver: optional callable(kind, key) -> a polars DataFrame
        of the rows the clicked bar/wedge/point represents, or None. kind
        is 'label' (key = the clicked category's value, for tagged bars/
        wedges) or 'index' (key = the clicked scatter point's row index).
        Chart types without a natural row-mapping (line/area/histogram/box/
        heatmap) just won't invoke this — hover tooltips still work.
        """
        self._teardown_canvas()

        self.figure = figure
        self._click_resolver = click_resolver

        self.canvas = FigureCanvasQTAgg(figure)
        self.canvas.setMinimumHeight(300)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        self.placeholder_label.setVisible(False)
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas, 1)

        self.canvas.mpl_connect('motion_notify_event', self._on_hover)
        self.canvas.mpl_connect('button_press_event', self._on_click)
        self.canvas.mpl_connect('figure_leave_event', lambda e: self._hide_tooltip())

        self.canvas.draw()

    def _on_hover(self, event):
        """Show an annotation with the exact value under the cursor."""
        if event.inaxes is None:
            self._hide_tooltip()
            return

        ax = event.inaxes
        hit = self._find_artist_under_cursor(ax, event)
        if hit is None:
            self._hide_tooltip()
            return

        text = hit['text']
        if self._annotation is None or self._annotation.axes is not ax:
            self._hide_tooltip()
            self._annotation = ax.annotate(
                text, xy=(event.xdata, event.ydata), xytext=(12, 12),
                textcoords="offset points",
                bbox=dict(boxstyle="round", fc="#ffffe0", ec="#999", alpha=0.95),
                fontsize=9, zorder=100,
            )
        else:
            self._annotation.xy = (event.xdata, event.ydata)
            self._annotation.set_text(text)
        self._annotation.set_visible(True)
        self.canvas.draw_idle()

    @staticmethod
    def _format_value(value):
        """Format a value for a tooltip — plain comma-separated number
        (matching the axis tick formatting in VisualizationService, not
        '%g''s scientific notation for large magnitudes, e.g. "8.3e+05"
        instead of "830,000"); anything else (e.g. a categorical x-axis on
        a line chart, where matplotlib happily plots string positions)
        just gets str()'d rather than crashing the format."""
        try:
            return VisualizationService._plain_number(value)
        except (ValueError, TypeError):
            return str(value)

    def _find_artist_under_cursor(self, ax, event):
        """Identify whatever artist is under the cursor and return a dict
        with a human-readable tooltip ('text') plus, where the chart type
        maps cleanly to underlying rows, a resolvable key: {'kind': 'label',
        'key': <category value>} for tagged bars/wedges, or {'kind':
        'index', 'key': <row index>} for scatter points. Line/area/heatmap
        points get a tooltip but no resolvable key (no natural 1:1 row
        mapping) — hover-only for those, which is an intentional, honest
        scope limit rather than a guess."""
        fmt = self._format_value
        for patch in ax.patches:
            if patch.contains(event)[0]:
                if isinstance(patch, Wedge):
                    label = getattr(patch, '_caat_label', None)
                    value = getattr(patch, '_caat_value', None)
                    if label is not None:
                        return {'kind': 'label', 'key': label, 'text': f"{label}: {value}"}
                elif isinstance(patch, Rectangle):
                    label = getattr(patch, '_caat_label', None)
                    value = getattr(patch, '_caat_value', None)
                    if value is None:
                        height, width = patch.get_height(), patch.get_width()
                        value = width if abs(width) > abs(height) else height
                    if label is not None:
                        return {'kind': 'label', 'key': label, 'text': f"{label}: {fmt(value)}"}
                    return {'kind': None, 'key': None, 'text': fmt(value)}

        for coll in ax.collections:
            if isinstance(coll, PathCollection) and coll.contains(event)[0]:
                idx = coll.contains(event)[1].get('ind')
                if idx:
                    offsets = coll.get_offsets()
                    x, y = offsets[idx[0]]
                    return {'kind': 'index', 'key': int(idx[0]), 'text': f"({fmt(x)}, {fmt(y)})"}

        for line in ax.lines:
            contains, info = line.contains(event)
            if contains and info.get('ind') is not None and len(info['ind']):
                xdata, ydata = line.get_data()
                i = info['ind'][0]
                return {'kind': None, 'key': None, 'text': f"{line.get_label()}: ({fmt(xdata[i])}, {fmt(ydata[i])})"}

        for image in ax.images:
            if image.contains(event)[0]:
                arr = image.get_array()
                extent = image.get_extent()
                if arr is not None and event.xdata is not None:
                    ncols_, nrows_ = arr.shape[1], arr.shape[0]
                    col_i = int((event.xdata - extent[0]) / (extent[1] - extent[0]) * ncols_)
                    row_i = int((event.ydata - extent[2]) / (extent[3] - extent[2]) * nrows_)
                    if 0 <= row_i < nrows_ and 0 <= col_i < ncols_:
                        return {'kind': None, 'key': None, 'text': fmt(arr[row_i, col_i])}

        return None

    def _hide_tooltip(self):
        if self._annotation is not None:
            self._annotation.set_visible(False)
            if self.canvas is not None:
                self.canvas.draw_idle()

    def _on_click(self, event):
        if event.inaxes is None or self._click_resolver is None:
            return
        hit = self._find_artist_under_cursor(event.inaxes, event)
        if hit is None or hit['kind'] is None:
            return
        result = self._click_resolver(hit['kind'], hit['key'])
        if result is not None and result.height > 0:
            self.pointClicked.emit(result)

    def _teardown_canvas(self):
        if self.canvas is not None:
            self.layout.removeWidget(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = None
            self.layout.removeWidget(self.canvas)
            self.canvas.deleteLater()
            self.canvas = None
        if self.figure is not None:
            # Figures created via plt.subplots() stay registered with
            # matplotlib's global figure manager until explicitly closed —
            # otherwise every chart switch/rebuild leaks one more Figure for
            # the rest of the session.
            import matplotlib.pyplot as plt
            plt.close(self.figure)
        self._annotation = None

    def clear(self):
        """Clear the canvas"""
        self._teardown_canvas()
        self.figure = None
        self._click_resolver = None
        self.placeholder_label.setVisible(True)


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

        # Stretch 0 for the header row, so it stays at its natural height -
        # without an explicit split, Qt was giving the header the vast
        # majority of the view's vertical space (its QLabel stretched to
        # ~300px tall) and squeezing the splitter below into a sliver,
        # which read as a large dead gap above "Data Visualizations".
        main_layout.addLayout(header_layout, 0)

        # Create splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Chart configuration
        config_panel = QGroupBox("Chart Configuration")
        config_layout = QVBoxLayout()

        # Chart type
        form_layout = self.form_layout = QFormLayout()

        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems([
            "Column Chart",
            "Bar Chart",
            "Line Chart",
            "Scatter Plot",
            "Histogram",
            "Pie Chart",
            "Box Plot",
            "Heatmap",
            "Area Chart",
            "Violin Plot",
            "Pareto Chart",
            "Control Chart",
            "Stacked Column Chart",
            "Q-Q Plot",
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
        # Extra breathing room before the "Options" group - its own
        # top-margin/title (from theme.py's QGroupBox rule) sat close
        # enough to "Label Column:" above it to read as a rendering
        # glitch rather than two distinct sections.
        config_layout.addSpacing(Spacing.MD)
        config_layout.addWidget(options_group)

        # Buttons
        button_layout = QVBoxLayout()

        self.create_btn = create_primary_button("Create Chart")
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
        self.chart_canvas.pointClicked.connect(self._on_point_clicked)
        canvas_layout.addWidget(self.chart_canvas)

        canvas_panel.setLayout(canvas_layout)
        splitter.addWidget(canvas_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter, 1)

        # Initialize UI state
        self.on_chart_type_changed(0)

    def set_dataframe(self, df):
        """Set the current data for visualizations"""
        self.current_dataframe = df

        # Initialize visualization service
        if self.viz_service is None:
            self.viz_service = VisualizationService()

        # Update column dropdowns
        self.update_column_dropdowns()

    def quick_visualize(self, df, column_name: str):
        """Jump straight to a sensible default chart for one column — a
        histogram for numeric columns, a top-values bar chart of value
        counts for everything else — without requiring the manual
        chart-type/column setup below. Renders directly onto the canvas
        without disturbing the manual builder's own configuration, so
        switching back to it afterward still behaves as expected."""
        self.set_dataframe(df)

        try:
            numeric_cols = self.viz_service.get_plottable_value_columns(df)
            if column_name in numeric_cols:
                fig = self.viz_service.create_histogram(
                    df, column_name, title=f"Distribution of {column_name}"
                )
                self.chart_canvas.set_figure(fig)
            else:
                counts_df = (
                    df[column_name].value_counts()
                    .sort("count", descending=True)
                    .head(20)
                )
                fig = self.viz_service.create_bar_chart(
                    counts_df, column_name, "count",
                    title=f"{column_name} — Top Values"
                )
                click_resolver = self._make_label_resolver(column_name, df=df)
                self.chart_canvas.set_figure(fig, click_resolver=click_resolver)

            self.current_figure = fig
            self.export_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Chart Error", f"Failed to visualize '{column_name}':\n{str(e)}")

    def update_column_dropdowns(self):
        """Update all column dropdowns with DataFrame columns"""
        if self.current_dataframe is None:
            return

        # Get all columns
        all_columns = list(self.current_dataframe.columns)
        # Numeric-typed columns, plus numeric-looking string columns (e.g.
        # straight after import, before a Change Data Type step) - a
        # strict dtype-only filter would hide exactly the columns a fresh
        # import is most likely to have from the Y-axis/value pickers.
        plottable_columns = self.viz_service.get_plottable_value_columns(self.current_dataframe)

        # Clear all combos
        for combo in [self.x_column_combo, self.y_column_combo, self.value_column_combo,
                      self.group_column_combo, self.label_column_combo]:
            combo.clear()
            combo.addItem("")

        # X axis - all columns
        self.x_column_combo.addItems(all_columns)

        # Y axis - numeric or numeric-looking only
        self.y_column_combo.addItems(plottable_columns)

        # Value column - numeric or numeric-looking only
        self.value_column_combo.addItems(plottable_columns)

        # Group/Color - all columns
        self.group_column_combo.addItems(all_columns)

        # Label column - all columns
        self.label_column_combo.addItems(all_columns)

    CHART_TYPES = [
        "column", "bar", "line", "scatter", "histogram", "pie", "box",
        "heatmap", "area", "violin", "pareto", "control", "stacked_column", "qq",
    ]

    def on_chart_type_changed(self, index: int):
        """Handle chart type selection change"""
        chart_type = self.CHART_TYPES[index] if 0 <= index < len(self.CHART_TYPES) else "column"

        # Show/hide relevant fields
        self.x_column_combo.setVisible(True)
        self.y_column_combo.setVisible(False)
        self.value_column_combo.setVisible(False)
        self.group_column_combo.setVisible(True)
        self.label_column_combo.setVisible(False)
        self.bins_spin.setEnabled(False)

        group_label = self.form_layout.labelForField(self.group_column_combo)
        if group_label:
            group_label.setText("Stack By:" if chart_type == "stacked_column" else "Group/Color:")

        if chart_type in ("column", "bar"):
            self.y_column_combo.setVisible(True)  # X axis, Y axis, group
        elif chart_type == "line":
            self.y_column_combo.setVisible(True)
        elif chart_type == "scatter":
            self.y_column_combo.setVisible(True)  # X axis, Y axis, group
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
        elif chart_type == "violin":
            # value_column = values, x_column reused as the optional group
            self.value_column_combo.setVisible(True)
            self.group_column_combo.setVisible(False)
        elif chart_type == "pareto":
            self.y_column_combo.setVisible(True)
            self.group_column_combo.setVisible(False)
        elif chart_type == "control":
            # value_column = values, x_column reused as the optional sequence axis
            self.value_column_combo.setVisible(True)
            self.group_column_combo.setVisible(False)
        elif chart_type == "stacked_column":
            self.value_column_combo.setVisible(True)  # x_column + value_column + group(stack by)
        elif chart_type == "qq":
            self.x_column_combo.setVisible(False)
            self.value_column_combo.setVisible(True)
            self.group_column_combo.setVisible(False)

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
        chart_type = self.CHART_TYPES[chart_type_idx]

        title = self.title_input.currentText()
        figsize = (self.fig_width_spin.value(), self.fig_height_spin.value())
        click_resolver = None

        try:
            if chart_type == "column":
                x_col = self.x_column_combo.currentText()
                y_col = self.y_column_combo.currentText()
                group_col = self.group_column_combo.currentText() or None

                if not x_col or not y_col:
                    raise ValueError("Please select X and Y columns")

                self.current_figure = self.viz_service.create_column_chart(
                    self.current_dataframe, x_col, y_col, title, group_col,
                    figsize=figsize
                )
                click_resolver = self._make_label_resolver(x_col)

            elif chart_type == "bar":
                x_col = self.x_column_combo.currentText()
                y_col = self.y_column_combo.currentText()
                group_col = self.group_column_combo.currentText() or None

                if not x_col or not y_col:
                    raise ValueError("Please select category and value columns")

                self.current_figure = self.viz_service.create_bar_chart(
                    self.current_dataframe, x_col, y_col, title, group_col,
                    figsize=figsize
                )
                click_resolver = self._make_label_resolver(x_col)

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
                click_resolver = self._make_index_resolver()

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
                click_resolver = self._make_label_resolver(label_col)

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

            elif chart_type == "violin":
                val_col = self.value_column_combo.currentText()
                group_col = self.x_column_combo.currentText() or None

                if not val_col:
                    raise ValueError("Please select a value column")

                self.current_figure = self.viz_service.create_violin_plot(
                    self.current_dataframe, val_col, group_col, title, figsize=figsize
                )

            elif chart_type == "pareto":
                x_col = self.x_column_combo.currentText()
                y_col = self.y_column_combo.currentText()

                if not x_col or not y_col:
                    raise ValueError("Please select category and value columns")

                self.current_figure = self.viz_service.create_pareto_chart(
                    self.current_dataframe, x_col, y_col, title, figsize=figsize
                )
                click_resolver = self._make_label_resolver(x_col)

            elif chart_type == "control":
                val_col = self.value_column_combo.currentText()
                x_col = self.x_column_combo.currentText() or None

                if not val_col:
                    raise ValueError("Please select a value column")

                self.current_figure = self.viz_service.create_control_chart(
                    self.current_dataframe, val_col, x_col, title, figsize=figsize
                )

            elif chart_type == "stacked_column":
                x_col = self.x_column_combo.currentText()
                val_col = self.value_column_combo.currentText()
                stack_col = self.group_column_combo.currentText()

                if not x_col or not val_col or not stack_col:
                    raise ValueError("Please select category, value, and stack-by columns")

                self.current_figure = self.viz_service.create_stacked_column_chart(
                    self.current_dataframe, x_col, val_col, stack_col, title, figsize=figsize
                )

            elif chart_type == "qq":
                val_col = self.value_column_combo.currentText()

                if not val_col:
                    raise ValueError("Please select a column")

                self.current_figure = self.viz_service.create_qq_plot(
                    self.current_dataframe, val_col, title, figsize=figsize
                )

            # Display the chart
            self.chart_canvas.set_figure(self.current_figure, click_resolver=click_resolver)
            self.export_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Chart Error", f"Failed to create chart:\n{str(e)}")

    def _make_label_resolver(self, column: str, df=None):
        """Resolver for bar/pie charts: clicking a bar or wedge shows the
        rows whose value in `column` matches that category."""
        def resolver(kind, key):
            if kind != 'label':
                return None
            import polars as pl
            source = df if df is not None else self.current_dataframe
            return source.filter(pl.col(column).cast(pl.Utf8) == str(key))
        return resolver

    def _make_index_resolver(self):
        """Resolver for scatter plots: each point is exactly one row, in the
        same order the dataframe was plotted in."""
        def resolver(kind, key):
            if kind != 'index' or not (0 <= key < self.current_dataframe.height):
                return None
            return self.current_dataframe.slice(key, 1)
        return resolver

    def _on_point_clicked(self, matched_rows):
        """Show the underlying rows for a clicked bar/wedge/point — the
        audit-relevant payoff of an interactive chart: click the outlier,
        see exactly which transactions it represents."""
        from PySide6.QtWidgets import QVBoxLayout as _QVBoxLayout
        from gui.components.common_modals import PreviewTable

        dialog = QDialog(self)
        dialog.setWindowTitle(f"{matched_rows.height:,} Matching Row(s)")
        dialog.setMinimumSize(700, 400)
        layout = _QVBoxLayout(dialog)
        table = PreviewTable(max_rows=500)
        table.load_dataframe(matched_rows)
        layout.addWidget(table)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.show()
        # Keep a reference so Python doesn't GC the dialog out from under the
        # open window — shiboken6.isValid() (not .isVisible()) is required
        # to safely check a WA_DeleteOnClose dialog that may already have
        # had its C++ object destroyed by a previous close().
        import shiboken6
        self._drill_dialogs = [d for d in getattr(self, '_drill_dialogs', []) if shiboken6.isValid(d) and d.isVisible()]
        self._drill_dialogs.append(dialog)

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
