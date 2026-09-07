"""
Transformation Dialog Factory
Centralized factory for creating transformation dialogs based on operation requirements.
"""

from typing import Optional, Type, Dict, Any
from PySide6.QtWidgets import QWidget

from .generic_transformation_dialog import GenericTransformationDialog
from .pivot_dialog import PivotTableDialog
from .unpivot_dialog import UnpivotDialog
from .filter_dialog import FilterDialog, AuditFlagDialog
from .anomaly_dialog import AnomalyDetectionDialog
from .benford_dialog import BenfordDialog
from .duplicate_detection_dialog import DuplicateDetectionDialog
from .extract_dialog import ExtractDialog
from .standardize_dialog import StandardizeDialog
from .ml_training_dialog import MLTrainingDialog
from .number_transform_dialog import NumberTransformDialog
from .prefix_suffix_dialog import PrefixSuffixDialog
from .replace_values_dialog import ReplaceValuesDialog
from .ai_dialogs import AIExplainDialog, AISentimentDialog, AIEntityExtractionDialog
from .column_dialogs import RenameColumnsDialog, ChooseColumnsDialog, ChangeDataTypeDialog
from .table_dialogs import (
    TransposeDialog,
    QuerySheetDialog, SelectNRowsDialog, JoinDatasetsDialog,
    AppendDatasetsDialog, CompareDatasetsDialog, FuzzyMatchDatasetsDialog
)
from .summary_dialogs import (
    GroupSummaryDialog, TopBottomDialog, StratificationDialog,
    SamplingDialog, CrossTabulationDialog, TrendAnalysisDialog,
    AgingAnalysisDialog, FieldStatisticsDialog
)
from .split_columns_dialog import SplitColumnsDialog
from .financial_ratios_dialog import FinancialRatiosDialog
from .statement_concept_map_dialog import StatementConceptMapDialog
from .ifrs9_dialog import IFRS9Dialog, IFRS9ScenarioECLDialog
from .ias36_dialog import IAS36ReverseDCFDialog
from .ifrs16_dialog import IFRS16LeaseLiabilityDialog
from .ifrs15_dialog import IFRS15MarginCusumDialog, IFRS15TimingGapDialog
from .ias37_dialog import IAS37ProvisionTrendDialog
from .ias2_dialog import IAS2NrvWritedownDialog
from .ias21_dialog import IAS21FxRateCheckDialog
from .ias12_dialog import IAS12DtaRecoverabilityDialog
from .sox_dialog import SoxSodDialog, SoxAccessReviewDialog
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

        # Filter operations
        'filter_advanced': FilterDialog,
        'audit_flag_rows': AuditFlagDialog,

        # Financial Operations
        'financial_ratios': FinancialRatiosDialog,
        'reshape_statement_to_concepts': StatementConceptMapDialog,
        'ifrs9_staging': IFRS9Dialog,
        'ifrs9_scenario_ecl': IFRS9ScenarioECLDialog,
        'ias36_implied_growth_rate': IAS36ReverseDCFDialog,
        'ifrs16_lease_liability': IFRS16LeaseLiabilityDialog,
        'ifrs15_margin_cusum': IFRS15MarginCusumDialog,
        'ifrs15_timing_gap': IFRS15TimingGapDialog,
        'ias37_provision_trend': IAS37ProvisionTrendDialog,
        'ias2_nrv_writedown': IAS2NrvWritedownDialog,
        'ias21_fx_rate_check': IAS21FxRateCheckDialog,
        'ias12_dta_recoverability': IAS12DtaRecoverabilityDialog,

        # SOX/COSO Operations
        'sox_sod_analysis': SoxSodDialog,
        'sox_access_review': SoxAccessReviewDialog,
        'coso_risk_heatmap': CosoDialog,

        # ML Operations
        'ml_anomaly_iforest': AnomalyDetectionDialog,
        'ml_anomaly_zscore': AnomalyDetectionDialog,
        'ml_anomaly_iqr': AnomalyDetectionDialog,
        'ml_anomaly_lof': AnomalyDetectionDialog,

        # Audit Operations
        'audit_benford_law': BenfordDialog,
        'audit_duplicate_detection': DuplicateDetectionDialog,

        # Text operations
        'text_extract_first': ExtractDialog,
        'text_extract_last': ExtractDialog,
        'text_extract_middle': ExtractDialog,

        # Number transformations
        'math_modulo': NumberTransformDialog,
        'math_power': NumberTransformDialog,

        # Prefix/Suffix
        'text_add_prefix': PrefixSuffixDialog,
        'text_add_suffix': PrefixSuffixDialog,

        # Replace
        'replace_values': ReplaceValuesDialog,

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
        # split_sheet is not mapped here: it creates multiple datasets
        # and is triggered from the sidebar instead.
        'transpose': TransposeDialog,
        'promote_row_header': PromoteRowHeaderDialog,
        'query_sheet': QuerySheetDialog,
        'select_n_rows': SelectNRowsDialog,
        'join_datasets': JoinDatasetsDialog,
        'append_datasets': AppendDatasetsDialog,
        'compare_datasets': CompareDatasetsDialog,
        'fuzzy_match_datasets': FuzzyMatchDatasetsDialog,

        # Summary report operations
        'group_summary': GroupSummaryDialog,
        'top_bottom': TopBottomDialog,
        'stratification': StratificationDialog,
        'aging_analysis': AgingAnalysisDialog,
        'field_statistics': FieldStatisticsDialog,
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

                # Dialogs shared by more than one operation_id via a
                # transform_type constructor kwarg need to know which
                # was requested, so the dialog opens on the matching
                # tab (the same reason AnomalyDetectionDialog below
                # needs operation_id).
                if dialog_class.__name__ == 'NumberTransformDialog':
                    transform_type = 'modulo' if operation_id == 'math_modulo' else 'power'
                    if 'selected_column' in sig.parameters:
                        dialog = dialog_class(dataframe, parent, selected_column=selected_column, transform_type=transform_type)
                    else:
                        dialog = dialog_class(dataframe, parent, transform_type=transform_type)
                elif dialog_class.__name__ == 'PrefixSuffixDialog':
                    transform_type = 'prefix' if operation_id == 'text_add_prefix' else 'suffix'
                    if 'selected_column' in sig.parameters:
                        dialog = dialog_class(dataframe, parent, selected_column=selected_column, transform_type=transform_type)
                    else:
                        dialog = dialog_class(dataframe, parent, transform_type=transform_type)
                elif 'selected_column' in sig.parameters and 'operation_id' in sig.parameters:
                    # AnomalyDetectionDialog: several operation_ids share this
                    # one class, so it needs to know which was actually
                    # requested to open on the matching tab (e.g.
                    # 'ml_anomaly_lof' should land on the LOF tab, not
                    # whatever tab happens to be first).
                    dialog = dialog_class(dataframe, parent, selected_column=selected_column, operation_id=operation_id)
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