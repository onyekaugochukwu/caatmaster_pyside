"""
Transformation Dialog Factory
Centralized factory for creating transformation dialogs based on operation requirements.
"""

from typing import Optional, Type, Dict, Any
from PySide6.QtWidgets import QWidget

from .generic_transformation_dialog import GenericTransformationDialog
from .pivot_dialog import PivotTableDialog
from .unpivot_dialog import UnpivotDialog, PivotColumnDialog
from .filter_dialog import FilterDialog, AuditFlagDialog
from .anomaly_dialog import AnomalyDetectionDialog
from .kmeans_dialog import KMeansDialog
from .benford_dialog import BenfordDialog
from .forecast_dialog import ForecastDialog
from .split_dialog import SplitColumnDialog
from .extract_dialog import ExtractDialog
from .standardize_dialog import StandardizeDialog
from .ml_training_dialog import MLTrainingDialog
from .number_transform_dialog import NumberTransformDialog
from .prefix_suffix_dialog import PrefixSuffixDialog
from .replace_values_dialog import ReplaceValuesDialog
from .group_stats_dialog import GroupStatsDialog
from .ai_dialogs import AIExplainDialog, AISentimentDialog, AIEntityExtractionDialog
from .column_dialogs import RenameColumnsDialog, ChooseColumnsDialog, ChangeDataTypeDialog
from .table_dialogs import (
    SplitSheetDialog, TransposeDialog, CombineSheetsDialog,
    QuerySheetDialog, SelectNRowsDialog, JoinDatasetsDialog,
    AppendDatasetsDialog
)
from .summary_dialogs import (
    GroupSummaryDialog, TopBottomDialog, StratificationDialog,
    SamplingDialog, CrossTabulationDialog, TrendAnalysisDialog
)
from .split_columns_dialog import SplitColumnsDialog
from .financial_ratios_dialog import FinancialRatiosDialog
from .ifrs9_dialog import IFRS9Dialog
from .sox_dialog import SoxSodDialog
from .coso_dialog import CosoDialog
from .promote_row_header_dialog import PromoteRowHeaderDialog

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
        'pivot_single': PivotColumnDialog,

        # Filter operations
        'filter_advanced': FilterDialog,
        'audit_flag_rows': AuditFlagDialog,

        # Financial Operations
        'financial_ratios': FinancialRatiosDialog,
        'ifrs9_staging': IFRS9Dialog,
        
        # SOX/COSO Operations
        'sox_sod_analysis': SoxSodDialog,
        'coso_risk_heatmap': CosoDialog,

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

        # Number transformations
        'math_modulo': NumberTransformDialog,
        'math_power': NumberTransformDialog,

        # Prefix/Suffix
        'text_add_prefix': PrefixSuffixDialog,
        'text_add_suffix': PrefixSuffixDialog,

        # Replace
        'replace_values': ReplaceValuesDialog,

        # Note: GroupStatsDialog was mapped to the now-removed "stat_group_stats"
        # operation_id, but its own get_parameters() output (value_column,
        # statistics, prefix, as_new_rows) never actually matched what any
        # real operation expected — it would have crashed on apply either
        # way. stat_add_group_stats (the working group-stats operation)
        # uses the generic dialog, which does match its real schema.

        # AI Operations
        'ai_explain': AIExplainDialog,
        'ai_sentiment': AISentimentDialog,
        'ai_extract': AIEntityExtractionDialog,

        # Standardization operations
        'stat_zscore': StandardizeDialog,
        'standardize_minmax': StandardizeDialog,
        'stat_percent_rank': StandardizeDialog,
        'stat_rank': StandardizeDialog,

        # ML Training operations
        'ml_train': MLTrainingDialog,

        # Column operations
        'split_columns_by_delimiter': SplitColumnsDialog,
        'rename_columns': RenameColumnsDialog,
        'choose_columns': ChooseColumnsDialog,
        'change_dtype': ChangeDataTypeDialog,

        # Table operations
        # Note: split_sheet is NOT here - it creates multiple datasets and is triggered from sidebar
        # Note: combine_sheets was removed from OPERATION_REGISTRY - see the
        # comment there; "Append Datasets" from the sidebar is the working
        # equivalent for cross-dataset combination.
        'transpose': TransposeDialog,
        'promote_row_header': PromoteRowHeaderDialog,
        'query_sheet': QuerySheetDialog,
        'select_n_rows': SelectNRowsDialog,
        'join_datasets': JoinDatasetsDialog,
        'append_datasets': AppendDatasetsDialog,

        # Summary report operations
        'group_summary': GroupSummaryDialog,
        'top_bottom': TopBottomDialog,
        'stratification': StratificationDialog,
        'sampling': SamplingDialog,
        'cross_tabulation': CrossTabulationDialog,
        'trend_analysis': TrendAnalysisDialog,
    }

    @staticmethod
    def create_dialog(
        operation_id: str,
        dataframe: pl.DataFrame,
        parent: Optional[QWidget] = None,
        initial_params: Optional[Dict[str, Any]] = None,
        selected_column: Optional[str] = None
    ) -> Optional[QWidget]:
        """
        Create the appropriate dialog for the given operation.

        Args:
            operation_id: The operation identifier
            dataframe: The current dataframe for column selection
            parent: Parent widget for the dialog
            initial_params: Initial parameter values
            selected_column: The column that was right-clicked (for auto-selection)

        Returns:
            A dialog widget or None if creation fails
        """
        initial_params = initial_params or {}

        # Check if there's a specific dialog for this operation
        dialog_class = TransformationDialogFactory.DIALOG_MAPPING.get(operation_id)

        if dialog_class:
            try:
                # Create specific dialog with selected_column support
                import inspect
                sig = inspect.signature(dialog_class.__init__)

                # Special handling for NumberTransformDialog - needs transform_type
                if dialog_class.__name__ == 'NumberTransformDialog':
                    transform_type = 'modulo' if operation_id == 'math_modulo' else 'power'
                    if 'selected_column' in sig.parameters:
                        dialog = dialog_class(dataframe, parent, selected_column=selected_column, transform_type=transform_type)
                    else:
                        dialog = dialog_class(dataframe, parent, transform_type=transform_type)
                elif 'selected_column' in sig.parameters:
                    dialog = dialog_class(dataframe, parent, selected_column=selected_column)
                else:
                    dialog = dialog_class(dataframe, parent)
                dialog.setModal(True)
                return dialog
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
            dialog = GenericTransformationDialog(
                operation_id=operation_id,
                param_schema=op_data.get('parameter_schema', {}),
                dataframe=dataframe,
                parent=parent,
                initial_params=initial_params
            )
            dialog.setModal(True)
            return dialog
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