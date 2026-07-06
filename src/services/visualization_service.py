"""
Visualization Service for CAATmaster
Creates charts and visualizations from data
"""
import polars as pl
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
import numpy as np


class ChartType:
    """Supported chart types"""
    COLUMN = "column"      # vertical bars, one per category (formerly "bar")
    BAR = "bar"            # horizontal bars (barh)
    LINE = "line"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    PIE = "pie"
    BOX = "box"
    HEATMAP = "heatmap"
    AREA = "area"
    VIOLIN = "violin"
    PARETO = "pareto"
    CONTROL = "control"
    STACKED_COLUMN = "stacked_column"
    QQ = "qq"


class VisualizationService:
    """Service for creating data visualizations"""

    def __init__(self):
        """Initialize the visualization service"""
        # Set up matplotlib style
        plt.style.use('seaborn-v0_8-darkgrid')

    @staticmethod
    def _cast_numeric(df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Cast a value-axis column to Float64, returning a new DataFrame.

        Straight after import, a numeric-looking column is often still
        string-typed (e.g. "100", "200"). Polars raises outright if you try
        to sum/plot a string column as a value axis instead of silently
        doing something nonsensical with it (pandas' groupby().sum(), by
        contrast, would concatenate the strings instead of adding them, and
        matplotlib would then plot the resulting strings as categorical
        positions rather than their magnitude) - casting explicitly here,
        with a clear error if the column truly isn't numeric, catches the
        problem at the point it actually occurs rather than downstream as
        a baffling chart.
        """
        if df[column].dtype.is_numeric():
            return df
        casted = df[column].cast(pl.Float64, strict=False)
        if casted.null_count() == len(casted) and df[column].null_count() != len(casted):
            raise ValueError(
                f"Column '{column}' does not contain numeric data and can't be used as a value axis."
            )
        return df.with_columns(casted)

    @staticmethod
    def _fill_null_category(df: pl.DataFrame, column: str, placeholder: str = "(blank)") -> pl.DataFrame:
        """Replace nulls in a column that will be used as a category/label
        axis with a visible placeholder string, returning a new DataFrame.

        A null in a grouping column becomes its own group with key None -
        matplotlib's categorical axis converter outright rejects a None
        label ("'value' must be an instance of str or bytes, not a None"),
        which crashed every chart type below the moment a real dataset had
        even one blank value in whatever column was chosen as the category
        axis (a very ordinary thing to have - a few transactions missing a
        category, a customer missing a region). Labeling it "(blank)"
        surfaces the gap instead of either crashing or silently dropping
        those rows.
        """
        if df[column].null_count() == 0:
            return df
        if df[column].dtype != pl.Utf8:
            df = df.with_columns(pl.col(column).cast(pl.Utf8))
        return df.with_columns(pl.col(column).fill_null(placeholder))

    @staticmethod
    def _plain_number(value, _pos=None) -> str:
        """Comma-separated plain number (e.g. "830,000") instead of
        matplotlib's default axis formatting, which switches to scientific/
        offset notation for larger values (e.g. showing "8.3" on the axis
        with a tiny separate "1e5" offset label easy to miss entirely) -
        that reads as an unfamiliar, unexplained scale change rather than
        the actual number, which matters for financial/audit figures where
        the exact magnitude is the point."""
        if value == int(value):
            return f'{int(value):,}'
        return f'{value:,.2f}'

    @classmethod
    def _use_plain_numbers(cls, ax, axis: str = 'y'):
        """Apply the plain-number formatter to the given axis ('x', 'y', or
        'both'). Only call this on an axis that's genuinely numeric/
        continuous - never on a categorical or datetime axis, which format
        differently."""
        formatter = FuncFormatter(cls._plain_number)
        if axis in ('y', 'both'):
            ax.yaxis.set_major_formatter(formatter)
        if axis in ('x', 'both'):
            ax.xaxis.set_major_formatter(formatter)

    @staticmethod
    def _tag_bars(bars, labels, values):
        """Stash the category label and value on each Rectangle so the
        interactive canvas' hover/click handlers can show the exact
        category + value without having to reverse-engineer it from bar
        geometry."""
        for bar, label, value in zip(bars, labels, values):
            bar._caat_label = str(label)
            bar._caat_value = value

    def create_column_chart(
        self,
        df: pl.DataFrame,
        x_column: str,
        y_column: str,
        title: str = "Column Chart",
        color_column: str = None,
        figsize: Tuple[int, int] = (10, 6),
        max_bars: int = 50
    ) -> Figure:
        """
        Create a column chart (vertical bars). A column chart's x-axis is
        categorical, so rows sharing the same category are summed into one
        bar each (matching create_pie_chart's existing aggregation and
        standard bar-chart semantics) — plotting one bar per raw row instead
        both misrepresents categories with duplicate rows (overlapping
        un-summed bars) and is genuinely slow: hundreds of individual bars
        and rotated tick labels can take several seconds for matplotlib to
        lay out and render. If there are still more than max_bars distinct
        categories after aggregating (e.g. a near-unique column like a
        transaction ID), only the top max_bars by total value are kept, and
        the title notes the truncation.

        Args:
            df: Source DataFrame
            x_column: Column for x-axis (categories)
            y_column: Column for y-axis (values)
            title: Chart title
            color_column: Optional column to color by
            figsize: Figure size (width, height)
            max_bars: Cap on distinct categories rendered, for readability
                and performance

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, y_column)
        df = self._fill_null_category(df, x_column)
        has_color = bool(color_column and color_column in df.columns)
        if has_color:
            df = self._fill_null_category(df, color_column)

        totals = df.group_by(x_column, maintain_order=True).agg(pl.col(y_column).sum())
        total_categories = totals.height
        truncated = total_categories > max_bars
        if truncated:
            top_categories = (
                totals.with_columns(pl.col(y_column).abs().alias("_abs"))
                .sort("_abs", descending=True)
                .head(max_bars)[x_column]
            )
            df = df.filter(pl.col(x_column).is_in(top_categories))

        group_cols = [x_column, color_column] if has_color else [x_column]
        agg_df = df.group_by(group_cols, maintain_order=True).agg(pl.col(y_column).sum())

        if has_color:
            for (name,), group in agg_df.group_by(color_column, maintain_order=True):
                labels = group[x_column].to_list()
                values = group[y_column].to_numpy()
                bars = ax.bar(labels, values, label=name)
                self._tag_bars(bars, labels, values)
            ax.legend()
        else:
            labels = agg_df[x_column].to_list()
            values = agg_df[y_column].to_numpy()
            bars = ax.bar(labels, values)
            self._tag_bars(bars, labels, values)

        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
        self._use_plain_numbers(ax, 'y')
        ax.set_title(f"{title}  (top {max_bars} of {total_categories} categories by value)" if truncated else title)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        return fig

    def create_bar_chart(
        self,
        df: pl.DataFrame,
        category_column: str,
        value_column: str,
        title: str = "Bar Chart",
        color_column: str = None,
        figsize: Tuple[int, int] = (10, 6),
        max_bars: int = 50
    ) -> Figure:
        """
        Create a proper horizontal bar chart (barh) — categories run down
        the y-axis and values extend along the x-axis, the standard layout
        for ranking many long category labels (they read left-to-right
        instead of being rotated/truncated as they would on a vertical
        column chart). Rows sharing a category are summed into one bar,
        same rationale as create_column_chart.

        Args:
            df: Source DataFrame
            category_column: Column for the category axis (bar labels)
            value_column: Column for the value axis (bar length)
            title: Chart title
            color_column: Optional column to color by
            figsize: Figure size (width, height)
            max_bars: Cap on distinct categories rendered, for readability
                and performance

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, value_column)
        df = self._fill_null_category(df, category_column)
        has_color = bool(color_column and color_column in df.columns)
        if has_color:
            df = self._fill_null_category(df, color_column)

        totals = df.group_by(category_column, maintain_order=True).agg(pl.col(value_column).sum())
        total_categories = totals.height
        truncated = total_categories > max_bars
        if truncated:
            totals = (
                totals.with_columns(pl.col(value_column).abs().alias("_abs"))
                .sort("_abs", descending=True)
                .head(max_bars)
                .drop("_abs")
            )
            df = df.filter(pl.col(category_column).is_in(totals[category_column]))

        # Largest value at the top of the chart, matching how a ranked
        # list is normally read, rather than matplotlib's default of
        # plotting categories bottom-to-top in insertion order.
        order = totals.sort(value_column, descending=False)[category_column].to_list()

        group_cols = [category_column, color_column] if has_color else [category_column]
        agg_df = df.group_by(group_cols, maintain_order=True).agg(pl.col(value_column).sum())
        order_index = {cat: i for i, cat in enumerate(order)}
        agg_df = agg_df.with_columns(
            pl.col(category_column).replace_strict(order_index, return_dtype=pl.Int64).alias("_order")
        ).sort("_order")

        if has_color:
            for (name,), group in agg_df.group_by(color_column, maintain_order=True):
                labels = group[category_column].to_list()
                values = group[value_column].to_numpy()
                bars = ax.barh(labels, values, label=name)
                self._tag_bars(bars, labels, values)
            ax.legend()
        else:
            labels = agg_df[category_column].to_list()
            values = agg_df[value_column].to_numpy()
            bars = ax.barh(labels, values)
            self._tag_bars(bars, labels, values)

        ax.set_xlabel(value_column)
        ax.set_ylabel(category_column)
        self._use_plain_numbers(ax, 'x')
        ax.set_title(f"{title}  (top {max_bars} of {total_categories} categories by value)" if truncated else title)
        plt.tight_layout()

        return fig

    def create_line_chart(
        self,
        df: pl.DataFrame,
        x_column: str,
        y_columns: List[str],
        title: str = "Line Chart",
        figsize: Tuple[int, int] = (10, 6),
        marker: str = 'o'
    ) -> Figure:
        """
        Create a line chart

        Args:
            df: Source DataFrame
            x_column: Column for x-axis
            y_columns: List of columns for y-axis (multiple lines)
            title: Chart title
            figsize: Figure size
            marker: Marker style for data points

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        for y_col in y_columns:
            df = self._cast_numeric(df, y_col)
        if df[x_column].dtype == pl.Utf8:
            df = self._fill_null_category(df, x_column)

        x_vals = df[x_column].to_list()
        for y_col in y_columns:
            ax.plot(x_vals, df[y_col].to_numpy(), marker=marker, label=y_col)

        ax.set_xlabel(x_column)
        ax.set_ylabel("Value")
        self._use_plain_numbers(ax, 'y')
        if df[x_column].dtype.is_numeric():
            self._use_plain_numbers(ax, 'x')
        ax.set_title(title)
        ax.legend()
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        return fig

    def create_scatter_plot(
        self,
        df: pl.DataFrame,
        x_column: str,
        y_column: str,
        title: str = "Scatter Plot",
        color_column: str = None,
        size_column: str = None,
        figsize: Tuple[int, int] = (10, 6)
    ) -> Figure:
        """
        Create a scatter plot

        Args:
            df: Source DataFrame
            x_column: Column for x-axis
            y_column: Column for y-axis
            title: Chart title
            color_column: Optional column for color mapping
            size_column: Optional column for size mapping
            figsize: Figure size

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, x_column)
        df = self._cast_numeric(df, y_column)

        # Prepare arguments
        c = df[color_column].to_numpy() if color_column else None
        s = df[size_column].to_numpy() if size_column else 50

        scatter = ax.scatter(df[x_column].to_numpy(), df[y_column].to_numpy(), c=c, s=s, alpha=0.6)

        # Add colorbar if color_column used
        if color_column:
            plt.colorbar(scatter, ax=ax, label=color_column)

        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
        self._use_plain_numbers(ax, 'both')
        ax.set_title(title)
        plt.tight_layout()

        return fig

    def create_histogram(
        self,
        df: pl.DataFrame,
        column: str,
        title: str = "Histogram",
        bins: int = 30,
        figsize: Tuple[int, int] = (10, 6)
    ) -> Figure:
        """
        Create a histogram

        Args:
            df: Source DataFrame
            column: Column to plot
            title: Chart title
            bins: Number of bins
            figsize: Figure size

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, column)
        data = df[column].drop_nulls().to_numpy()

        counts, bin_edges, patches = ax.hist(data, bins=bins, edgecolor='black', alpha=0.7)
        for count, lo, hi, patch in zip(counts, bin_edges[:-1], bin_edges[1:], patches):
            patch._caat_label = f"{lo:,.4g} - {hi:,.4g}"
            patch._caat_value = int(count)
        ax.set_xlabel(column)
        ax.set_ylabel("Frequency")
        self._use_plain_numbers(ax, 'both')
        ax.set_title(title)
        plt.tight_layout()

        return fig

    def create_pie_chart(
        self,
        df: pl.DataFrame,
        label_column: str,
        value_column: str,
        title: str = "Pie Chart",
        figsize: Tuple[int, int] = (8, 8)
    ) -> Figure:
        """
        Create a pie chart

        Args:
            df: Source DataFrame
            label_column: Column for labels
            value_column: Column for values
            title: Chart title
            figsize: Figure size

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, value_column)
        df = self._fill_null_category(df, label_column)

        # Group by label column and sum values
        grouped = df.group_by(label_column, maintain_order=True).agg(pl.col(value_column).sum())
        labels = grouped[label_column].to_list()
        values = grouped[value_column].to_numpy()

        wedges, _texts, _autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
        for wedge, label, value in zip(wedges, labels, values):
            wedge._caat_label = str(label)
            wedge._caat_value = value
        ax.set_title(title)
        ax.axis('equal')
        plt.tight_layout()

        return fig

    def create_box_plot(
        self,
        df: pl.DataFrame,
        value_column: str,
        group_column: str = None,
        title: str = "Box Plot",
        figsize: Tuple[int, int] = (10, 6)
    ) -> Figure:
        """
        Create a box plot

        Args:
            df: Source DataFrame
            value_column: Column with values to plot
            group_column: Optional column to group by
            title: Chart title
            figsize: Figure size

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, value_column)

        if group_column:
            df = self._fill_null_category(df, group_column)
            grouped = df.drop_nulls(value_column).group_by(group_column, maintain_order=True).agg(pl.col(value_column))
            labels = [str(v) for v in grouped[group_column].to_list()]
            data = [np.array(v) for v in grouped[value_column].to_list()]
            ax.boxplot(data, tick_labels=labels)
        else:
            ax.boxplot(df[value_column].drop_nulls().to_numpy())

        ax.set_ylabel(value_column)
        self._use_plain_numbers(ax, 'y')
        ax.set_title(title)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        return fig

    def create_heatmap(
        self,
        df: pl.DataFrame,
        title: str = "Heatmap",
        figsize: Tuple[int, int] = (10, 8),
        cmap: str = "coolwarm"
    ) -> Figure:
        """
        Create a correlation heatmap

        Args:
            df: Source DataFrame (numeric columns only)
            title: Chart title
            figsize: Figure size
            cmap: Colormap name

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        # Numeric-typed columns, plus numeric-looking string columns (e.g.
        # straight after import) - cast the latter so they're not silently
        # dropped from the correlation matrix just for being string-typed.
        numeric_cols = self.get_plottable_value_columns(df)
        if len(numeric_cols) < 2:
            raise ValueError("Need at least 2 numeric columns to compute a correlation heatmap.")
        casted = df.select(numeric_cols)
        for col in numeric_cols:
            casted = self._cast_numeric(casted, col)
        corr = casted.corr()
        corr_np = corr.to_numpy()

        # Create heatmap
        im = ax.imshow(corr_np, cmap=cmap, aspect='auto', vmin=-1, vmax=1)

        # Add colorbar
        plt.colorbar(im, ax=ax)

        # Set labels
        ax.set_xticks(range(len(numeric_cols)))
        ax.set_yticks(range(len(numeric_cols)))
        ax.set_xticklabels(numeric_cols, rotation=45, ha='right')
        ax.set_yticklabels(numeric_cols)

        # Add correlation values
        for i in range(len(numeric_cols)):
            for j in range(len(numeric_cols)):
                ax.text(j, i, f'{corr_np[i, j]:.2f}', ha="center", va="center", color="black", fontsize=8)

        ax.set_title(title)
        plt.tight_layout()

        return fig

    def create_area_chart(
        self,
        df: pl.DataFrame,
        x_column: str,
        y_columns: List[str],
        title: str = "Area Chart",
        figsize: Tuple[int, int] = (10, 6)
    ) -> Figure:
        """
        Create an area chart

        Args:
            df: Source DataFrame
            x_column: Column for x-axis
            y_columns: List of columns for y-axis (stacked areas)
            title: Chart title
            figsize: Figure size

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        for y_col in y_columns:
            df = self._cast_numeric(df, y_col)
        if df[x_column].dtype == pl.Utf8:
            df = self._fill_null_category(df, x_column)

        x_vals = df[x_column].to_list()
        running_total = np.zeros(df.height)

        for y_col in y_columns:
            values = df[y_col].to_numpy()
            new_total = running_total + values
            ax.fill_between(x_vals, running_total, new_total, alpha=0.5, label=y_col)
            running_total = new_total

        ax.set_xlabel(x_column)
        ax.set_ylabel("Value")
        self._use_plain_numbers(ax, 'y')
        if df[x_column].dtype.is_numeric():
            self._use_plain_numbers(ax, 'x')
        ax.set_title(title)
        ax.legend()
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        return fig

    def create_violin_plot(
        self,
        df: pl.DataFrame,
        value_column: str,
        group_column: str = None,
        title: str = "Violin Plot",
        figsize: Tuple[int, int] = (10, 6)
    ) -> Figure:
        """
        Create a violin plot — shows the full estimated distribution shape
        per group (via a kernel density estimate on each side), a more
        informative complement to a box plot's five-number summary when
        distributions are multimodal or skewed.

        Args:
            df: Source DataFrame
            value_column: Column with values to plot
            group_column: Optional column to group by
            title: Chart title
            figsize: Figure size

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, value_column)
        df = df.drop_nulls(value_column)

        if group_column:
            df = self._fill_null_category(df, group_column)
            grouped = df.group_by(group_column, maintain_order=True).agg(pl.col(value_column))
            labels = [str(v) for v in grouped[group_column].to_list()]
            data = [np.array(v) for v in grouped[value_column].to_list() if len(v) > 0]
        else:
            labels = [value_column]
            data = [df[value_column].to_numpy()]

        if not data or all(len(d) == 0 for d in data):
            raise ValueError(f"Column '{value_column}' has no numeric values to plot.")

        ax.violinplot(data, showmeans=True, showmedians=True)
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_ylabel(value_column)
        self._use_plain_numbers(ax, 'y')
        ax.set_title(title)
        plt.tight_layout()

        return fig

    def create_pareto_chart(
        self,
        df: pl.DataFrame,
        category_column: str,
        value_column: str,
        title: str = "Pareto Chart",
        figsize: Tuple[int, int] = (10, 6),
        max_bars: int = 20
    ) -> Figure:
        """
        Create a Pareto chart — bars sorted descending by value, with a
        cumulative-percentage line on a secondary axis and a reference line
        at 80%. Standard audit tool for the "vital few" (80/20 rule): which
        small set of categories (vendors, error types, accounts) accounts
        for the bulk of total value.

        Args:
            df: Source DataFrame
            category_column: Column for categories
            value_column: Column for values (summed per category)
            title: Chart title
            figsize: Figure size
            max_bars: Cap on distinct categories rendered

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, value_column)
        df = self._fill_null_category(df, category_column)

        all_totals = (
            df.group_by(category_column, maintain_order=True)
            .agg(pl.col(value_column).sum())
            .sort(value_column, descending=True)
        )
        total_categories = all_totals.height
        truncated = total_categories > max_bars
        totals = all_totals.head(max_bars) if truncated else all_totals

        labels = [str(v) for v in totals[category_column].to_list()]
        values = totals[value_column].to_numpy()
        grand_total = float(np.sum(all_totals[value_column].to_numpy()))
        cumulative_pct = np.cumsum(values) / grand_total * 100 if grand_total else np.zeros_like(values)

        bars = ax.bar(range(len(labels)), values, color='#4C72B0')
        self._tag_bars(bars, labels, values)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_xlabel(category_column)
        ax.set_ylabel(value_column)
        self._use_plain_numbers(ax, 'y')

        ax2 = ax.twinx()
        ax2.plot(range(len(labels)), cumulative_pct, color='#C44E52', marker='o', linewidth=2)
        ax2.set_ylabel('Cumulative %')
        ax2.set_ylim(0, 110)
        ax2.axhline(80, color='gray', linestyle='--', linewidth=1)
        ax2.grid(False)

        ax.set_title(f"{title}  (top {max_bars} of {total_categories} categories by value)" if truncated else title)
        plt.tight_layout()

        return fig

    def create_control_chart(
        self,
        df: pl.DataFrame,
        value_column: str,
        x_column: str = None,
        title: str = "Control Chart",
        figsize: Tuple[int, int] = (10, 6)
    ) -> Figure:
        """
        Create a statistical process control (run) chart: the value plotted
        in sequence (or against x_column if given), with the mean and
        +/-3 sigma control limits drawn as reference lines and any point
        outside those limits flagged in red. Standard audit tool for
        spotting when a metric (transaction volume, processing time,
        variance) has drifted out of its normal operating range.

        Args:
            df: Source DataFrame
            value_column: Column with values to plot
            x_column: Optional column for the x-axis (defaults to row order)
            title: Chart title
            figsize: Figure size

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, value_column)
        df = df.drop_nulls(value_column)
        if x_column and df[x_column].dtype == pl.Utf8:
            df = self._fill_null_category(df, x_column)

        values = df[value_column].to_numpy()
        if len(values) < 2:
            raise ValueError(f"Column '{value_column}' needs at least 2 numeric values for a control chart.")
        x_vals = df[x_column].to_list() if x_column else list(range(1, len(values) + 1))

        mean = float(np.mean(values))
        std = float(np.std(values, ddof=1))
        ucl = mean + 3 * std
        lcl = mean - 3 * std

        ax.plot(x_vals, values, marker='o', linewidth=1, color='#4C72B0', label=value_column)
        ax.axhline(mean, color='green', linestyle='-', linewidth=1.5, label=f'Mean ({mean:,.4g})')
        ax.axhline(ucl, color='red', linestyle='--', linewidth=1, label=f'UCL ({ucl:,.4g})')
        ax.axhline(lcl, color='red', linestyle='--', linewidth=1, label=f'LCL ({lcl:,.4g})')

        out_of_control = (values > ucl) | (values < lcl)
        if out_of_control.any():
            oc_x = [x_vals[i] for i in range(len(values)) if out_of_control[i]]
            oc_y = values[out_of_control]
            ax.scatter(oc_x, oc_y, color='red', s=80, zorder=5, label='Out of control')

        ax.set_xlabel(x_column or "Sequence")
        ax.set_ylabel(value_column)
        self._use_plain_numbers(ax, 'y')
        if not x_column or df[x_column].dtype.is_numeric():
            self._use_plain_numbers(ax, 'x')
        ax.set_title(title)
        ax.legend()
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        return fig

    def create_stacked_column_chart(
        self,
        df: pl.DataFrame,
        x_column: str,
        value_column: str,
        stack_column: str,
        title: str = "Stacked Column Chart",
        figsize: Tuple[int, int] = (10, 6),
        max_bars: int = 50
    ) -> Figure:
        """
        Create a stacked column chart — one bar per x_column category,
        split into segments by stack_column, each segment sized by the
        summed value_column. Useful for showing both a category's total
        and its composition (e.g. total spend per vendor, broken down by
        expense type) in one chart.

        Args:
            df: Source DataFrame
            x_column: Column for x-axis (categories)
            value_column: Column for segment size (values)
            stack_column: Column whose distinct values become the stacked
                segments within each bar
            title: Chart title
            figsize: Figure size
            max_bars: Cap on distinct x_column categories rendered

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, value_column)
        df = self._fill_null_category(df, x_column)
        df = self._fill_null_category(df, stack_column)

        totals = df.group_by(x_column, maintain_order=True).agg(pl.col(value_column).sum())
        total_categories = totals.height
        truncated = total_categories > max_bars
        if truncated:
            top_categories = (
                totals.with_columns(pl.col(value_column).abs().alias("_abs"))
                .sort("_abs", descending=True)
                .head(max_bars)[x_column]
            )
            df = df.filter(pl.col(x_column).is_in(top_categories))

        agg = df.group_by([x_column, stack_column], maintain_order=True).agg(pl.col(value_column).sum())
        pivoted = agg.pivot(values=value_column, index=x_column, on=stack_column).fill_null(0)

        categories = pivoted[x_column].to_list()
        stack_values = [c for c in pivoted.columns if c != x_column]

        bottom = np.zeros(len(categories))
        for stack_val in stack_values:
            heights = pivoted[stack_val].to_numpy().astype(float)
            bars = ax.bar(categories, heights, bottom=bottom, label=str(stack_val))
            self._tag_bars(bars, categories, heights)
            bottom += heights

        ax.set_xlabel(x_column)
        ax.set_ylabel(value_column)
        self._use_plain_numbers(ax, 'y')
        ax.set_title(f"{title}  (top {max_bars} of {total_categories} categories by value)" if truncated else title)
        ax.legend(title=stack_column)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()

        return fig

    def create_qq_plot(
        self,
        df: pl.DataFrame,
        column: str,
        title: str = "Q-Q Plot",
        figsize: Tuple[int, int] = (8, 8)
    ) -> Figure:
        """
        Create a normal Q-Q (quantile-quantile) plot — plots the column's
        sorted values against the quantiles a normal distribution would
        produce. Points following the diagonal reference line indicate the
        data is approximately normally distributed; systematic curves or
        tails indicate skew or heavy tails. Useful alongside Benford's Law
        analysis for assessing whether a "normal distribution" assumption
        behind another statistical test actually holds for this data.

        Args:
            df: Source DataFrame
            column: Column to test for normality
            title: Chart title
            figsize: Figure size

        Returns:
            Matplotlib Figure
        """
        from scipy import stats

        fig, ax = plt.subplots(figsize=figsize)

        df = self._cast_numeric(df, column)
        data = df[column].drop_nulls().to_numpy()
        if len(data) < 3:
            raise ValueError(f"Column '{column}' needs at least 3 numeric values for a Q-Q plot.")

        stats.probplot(data, dist="norm", plot=ax)
        ax.set_title(title)
        ax.get_lines()[0].set_markerfacecolor('#4C72B0')
        ax.get_lines()[0].set_markeredgecolor('#4C72B0')
        ax.get_lines()[1].set_color('#C44E52')
        self._use_plain_numbers(ax, 'y')
        plt.tight_layout()

        return fig

    def get_numeric_columns(self, df: pl.DataFrame) -> List[str]:
        """Get list of numeric columns in DataFrame"""
        numeric_types = [pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                       pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                       pl.Float32, pl.Float64]
        return [col for col in df.columns if df[col].dtype in numeric_types]

    def get_categorical_columns(self, df: pl.DataFrame) -> List[str]:
        """Get list of categorical/columns in DataFrame"""
        numeric_types = [pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                       pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                       pl.Float32, pl.Float64, pl.Boolean]
        return [col for col in df.columns if df[col].dtype not in numeric_types]

    def get_plottable_value_columns(self, df: pl.DataFrame) -> List[str]:
        """Columns usable as a chart value axis: numeric-typed columns,
        plus string columns that are numeric-looking (e.g. straight after
        import, before an explicit Change Data Type step has been run).
        Without this, a numeric-looking string column never appears as a
        selectable Y-axis/value option at all - the chart-builder silently
        hides exactly the columns a fresh import is most likely to have."""
        result = list(self.get_numeric_columns(df))
        for col in df.columns:
            if col in result or df[col].dtype != pl.Utf8:
                continue
            non_null = df[col].drop_nulls()
            if non_null.len() == 0:
                continue
            if non_null.cast(pl.Float64, strict=False).null_count() == 0:
                result.append(col)
        return result

    def save_figure(self, fig: Figure, file_path: str, dpi: int = 300) -> str:
        """
        Save figure to file

        Args:
            fig: Matplotlib Figure
            file_path: Output file path
            dpi: Resolution in dots per inch

        Returns:
            Path to saved file
        """
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(file_path, dpi=dpi, bbox_inches='tight')
        return file_path

    def get_figure_as_image(self, fig: Figure) -> bytes:
        """
        Convert figure to image bytes

        Args:
            fig: Matplotlib Figure

        Returns:
            PNG image data as bytes
        """
        from io import BytesIO
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        return buf.read()
