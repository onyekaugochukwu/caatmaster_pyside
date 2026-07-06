"""
Visualize Dataset dialog — the full chart-builder (chart type, columns,
options, interactive preview) as a modal, for when you want to visualize a
dataset without navigating to the Visualizations page. Wraps
VisualizationsView directly rather than duplicating its logic, so any future
improvement to the chart builder (new chart types, better tooltips, etc.)
applies here for free.
"""
import polars as pl
from PySide6.QtWidgets import QDialog, QVBoxLayout

from gui.views.visualizations_view import VisualizationsView


class VisualizeDatasetDialog(QDialog):
    def __init__(self, dataframe: pl.DataFrame, dataset_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Visualize — {dataset_name}" if dataset_name else "Visualize Dataset")
        self.resize(1100, 700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.viz_view = VisualizationsView()
        layout.addWidget(self.viz_view)

        self.viz_view.set_dataframe(dataframe)
