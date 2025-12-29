"""
Transformation Dialog Factory
Centralized factory for creating transformation dialogs based on operation requirements.
"""

from typing import Optional, Type, Dict, Any
from PySide6.QtWidgets import QWidget

from .generic_transformation_dialog import GenericTransformationDialog
from .pivot_dialog import PivotTableDialog
from .unpivot_dialog import UnpivotDialog, PowerPivotDialog
from .filter_dialog import FilterDialog
from .anomaly_dialog import AnomalyDetectionDialog
from .kmeans_dialog import KMeansDialog
from .benford_dialog import BenfordDialog
from .forecast_dialog import ForecastDialog
from .split_dialog import SplitColumnDialog
from .extract_dialog import ExtractDialog
from .standardize_dialog import StandardizeDialog
from .ml_training_dialog import MLTrainingDialog

# Import polars for type hints
import polars as pl


class TransformationDialogFactory:
    """
    Factory class for creating transformation dialogs.
    Handles both specific dialogs for complex operations and generic dialogs for simple ones.
    """

    # Mapping of operation IDs to their specific dialog classes
    DIALOG_MAPPING: Dict[str, Type] = {
        # Pivot operations
        'pivot_table': PivotTableDialog,
        'unpivot_table': UnpivotDialog,
        'pivot_single': PowerPivotDialog,

        # Filter operations
        'filter_advanced': FilterDialog,

        # ML Operations
        'ml_anomaly_iforest': AnomalyDetectionDialog,
        'ml_anomaly_zscore': AnomalyDetectionDialog,
        'ml_anomaly_iqr': AnomalyDetectionDialog,
        'ml_anomaly_lof': AnomalyDetectionDialog,
        'ml_cluster_kmeans': KMeansDialog,
        'ml_forecast': ForecastDialog,

        # Audit Operations
        'audit_benford_law': BenfordDialog,

        # Text operations
        'text_split_delimiter': SplitColumnDialog,
        'text_extract_first': ExtractDialog,
        'text_extract_last': ExtractDialog,
        'text_extract_middle': ExtractDialog,
        'date_extract_year': ExtractDialog,
        'date_extract_month': ExtractDialog,
        'date_extract_day': ExtractDialog,

        # Standardization operations
        'stat_zscore': StandardizeDialog,
        'standardize_minmax': StandardizeDialog,
        'stat_percent_rank': StandardizeDialog,
        'stat_rank': StandardizeDialog,

        # ML Training operations
        'ml_train': MLTrainingDialog,
    }

    @staticmethod
    def create_dialog(
        operation_id: str,
        dataframe: pl.DataFrame,
        parent: Optional[QWidget] = None,
        initial_params: Optional[Dict[str, Any]] = None
    ) -> Optional[QWidget]:
        """
        Create the appropriate dialog for the given operation.

        Args:
            operation_id: The operation identifier
            dataframe: The current dataframe for column selection
            parent: Parent widget for the dialog
            initial_params: Initial parameter values

        Returns:
            A dialog widget or None if creation fails
        """
        initial_params = initial_params or {}

        # Check if there's a specific dialog for this operation
        dialog_class = TransformationDialogFactory.DIALOG_MAPPING.get(operation_id)

        if dialog_class:
            try:
                # Create specific dialog
                return dialog_class(dataframe, parent)
            except Exception as e:
                print(f"Failed to create specific dialog for {operation_id}: {e}")
                # Fall back to generic dialog

        # Use generic dialog for operations without specific dialogs
        from core.operation_registry import OPERATION_REGISTRY

        op_data = OPERATION_REGISTRY.get(operation_id)
        if not op_data:
            print(f"Operation {operation_id} not found in registry")
            return None

        try:
            return GenericTransformationDialog(
                operation_id=operation_id,
                param_schema=op_data.get('parameter_schema', {}),
                dataframe=dataframe,
                parent=parent,
                initial_params=initial_params
            )
        except Exception as e:
            print(f"Failed to create generic dialog for {operation_id}: {e}")
            return None

    @staticmethod
    def get_supported_operations() -> list[str]:
        """
        Get list of operations that have specific dialog support.

        Returns:
            List of operation IDs with specific dialogs
        """
        return list(TransformationDialogFactory.DIALOG_MAPPING.keys())

    @staticmethod
    def requires_specific_dialog(operation_id: str) -> bool:
        """
        Check if an operation requires a specific dialog (not generic).

        Args:
            operation_id: The operation identifier

        Returns:
            True if operation has a specific dialog, False otherwise
        """
        return operation_id in TransformationDialogFactory.DIALOG_MAPPING