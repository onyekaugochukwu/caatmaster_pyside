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
import numpy as np


class ChartType:
    """Supported chart types"""
    BAR = "bar"
    LINE = "line"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    PIE = "pie"
    BOX = "box"
    HEATMAP = "heatmap"
    AREA = "area"


class VisualizationService:
    """Service for creating data visualizations"""

    def __init__(self):
        """Initialize the visualization service"""
        # Set up matplotlib style
        plt.style.use('seaborn-v0_8-darkgrid')

    def create_bar_chart(
        self,
        df: pl.DataFrame,
        x_column: str,
        y_column: str,
        title: str = "Bar Chart",
        color_column: str = None,
        orientation: str = "vertical",
        figsize: Tuple[int, int] = (10, 6)
    ) -> Figure:
        """
        Create a bar chart

        Args:
            df: Source DataFrame
            x_column: Column for x-axis (categories)
            y_column: Column for y-axis (values)
            title: Chart title
            color_column: Optional column to color by
            orientation: 'vertical' or 'horizontal'
            figsize: Figure size (width, height)

        Returns:
            Matplotlib Figure
        """
        fig, ax = plt.subplots(figsize=figsize)

        # Convert to pandas for plotting
        df_pd = df.to_pandas()

        if color_column and color_column in df_pd.columns:
            # Group by color column and plot
            groups = df_pd.groupby(color_column)
            for name, group in groups:
                if orientation == "horizontal":
                    ax.barh(group[x_column], group[y_column], label=name)
                else:
                    ax.bar(group[x_column], group[y_column], label=name)
            ax.legend()
        else:
            if orientation == "horizontal":
                ax.barh(df_pd[x_column], df_pd[y_column])
            else:
                ax.bar(df_pd[x_column], df_pd[y_column])

        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
        ax.set_title(title)
        plt.xticks(rotation=45, ha='right')
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

        df_pd = df.to_pandas()

        for y_col in y_columns:
            ax.plot(df_pd[x_column], df_pd[y_col], marker=marker, label=y_col)

        ax.set_xlabel(x_column)
        ax.set_ylabel("Value")
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

        df_pd = df.to_pandas()

        # Prepare arguments
        c = df_pd[color_column] if color_column else None
        s = df_pd[size_column] if size_column else 50

        scatter = ax.scatter(df_pd[x_column], df_pd[y_column], c=c, s=s, alpha=0.6)

        # Add colorbar if color_column used
        if color_column:
            plt.colorbar(scatter, ax=ax, label=color_column)

        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
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

        df_pd = df.to_pandas()
        data = df_pd[column].dropna()

        ax.hist(data, bins=bins, edgecolor='black', alpha=0.7)
        ax.set_xlabel(column)
        ax.set_ylabel("Frequency")
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

        df_pd = df.to_pandas()

        # Group by label column and sum values
        grouped = df_pd.groupby(label_column)[value_column].sum()

        ax.pie(grouped, labels=grouped.index, autopct='%1.1f%%', startangle=90)
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

        df_pd = df.to_pandas()

        if group_column:
            # Create box plot for each group
            groups = df_pd.groupby(group_column)[value_column].apply(list)
            ax.boxplot(groups.values, labels=groups.index)
        else:
            ax.boxplot(df_pd[value_column].dropna())

        ax.set_ylabel(value_column)
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

        # Select only numeric columns
        df_pd = df.to_pandas()
        numeric_df = df_pd.select_dtypes(include=[np.number])

        # Calculate correlation
        corr = numeric_df.corr()

        # Create heatmap
        im = ax.imshow(corr, cmap=cmap, aspect='auto', vmin=-1, vmax=1)

        # Add colorbar
        plt.colorbar(im, ax=ax)

        # Set labels
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha='right')
        ax.set_yticklabels(corr.columns)

        # Add correlation values
        for i in range(len(corr.columns)):
            for j in range(len(corr.columns)):
                text = ax.text(j, i, f'{corr.iloc[i, j]:.2f}',
                             ha="center", va="center", color="black", fontsize=8)

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

        df_pd = df.to_pandas()

        # Plot areas
        ax.fill_between(df_pd[x_column], df_pd[y_columns[0]], alpha=0.5, label=y_columns[0])

        for i, y_col in enumerate(y_columns[1:], 1):
            # Stack on top of previous
            previous_sum = df_pd[y_columns[:i]].sum(axis=1)
            current_sum = df_pd[y_columns[:i+1]].sum(axis=1)
            ax.fill_between(df_pd[x_column], previous_sum, current_sum, alpha=0.5, label=y_col)

        ax.set_xlabel(x_column)
        ax.set_ylabel("Value")
        ax.set_title(title)
        ax.legend()
        plt.xticks(rotation=45, ha='right')
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
