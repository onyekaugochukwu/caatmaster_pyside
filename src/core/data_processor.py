"""
Data Processor for CAATmaster
Handles data import, export, and transformations using Polars
"""
import polars as pl
from typing import Dict, Any, List, Optional
from pathlib import Path
import re
import hashlib
from datetime import datetime
import numpy as np
import inspect

# Import the operation registry
from .operation_registry import OPERATION_REGISTRY, TransformationStepType


class DataProcessor:
    """
    A stateless processor that executes individual data transformation operations.
    The methods in this class are called by the TransformationPipeline.
    """

    # Mapping from operation_id to method name (for parameter validation)
    _OPERATION_METHODS = {
        'text_uppercase': 'uppercase',
        'text_lowercase': 'lowercase',
        'text_titlecase': 'titlecase',
        'text_trim': 'trim',
        'text_extract_numbers': 'extract_numbers',
        'text_extract_text': 'extract_text',
        'text_reverse': 'reverse_text',
        'text_length': 'text_length',
        'text_hash_md5': 'hash_md5',
        'text_soundex': 'soundex',
        'math_round': 'round',
        'math_ceil': 'ceil',
        'math_floor': 'floor',
        'math_abs': 'abs',
        'math_sqrt': 'sqrt',
        'math_square': 'square',
        'math_log': 'log',
        'math_log10': 'log10',
        'math_exp': 'exp',
        'trig_sin': 'sin',
        'trig_cos': 'cos',
        'trig_tan': 'tan',
        'trig_asin': 'asin',
        'trig_acos': 'acos',
        'trig_atan': 'atan',
        'datetime_year': 'year',
        'datetime_month': 'month',
        'datetime_day': 'day',
        'datetime_hour': 'hour',
        'datetime_minute': 'minute',
        'datetime_second': 'second',
        'datetime_weekday': 'weekday',
        'datetime_quarter': 'quarter',
        'datetime_age_days': 'age_days',
        'datetime_age_years': 'age_years',
        'datetime_is_weekend': 'is_weekend',
        'datetime_is_leap_year': 'is_leap_year',
        'datetime_days_in_month': 'days_in_month',
        'stat_zscore': 'zscore',
        'stat_percent_rank': 'percent_rank',
        'stat_rank': 'rank',
        'column_rename': 'rename_column',
        'column_change_dtype': 'change_dtype',
        'split_comma': 'split_by_comma',
        'split_space': 'split_by_space',
        'split_semicolon': 'split_by_semicolon',
        'split_pipe': 'split_by_pipe',
        'split_custom': 'split_by_custom',
        'pivot_table': 'pivot_table',
        'unpivot_table': 'unpivot_table',
        'ml_anomaly_iforest': 'anomaly_iforest',
        'ml_anomaly_zscore': 'anomaly_zscore',
        'ml_anomaly_iqr': 'anomaly_iqr',
        'ml_anomaly_lof': 'anomaly_lof',
        'ml_outlier': 'outlier_detection',
        'ml_cluster': 'kmeans_cluster',
        'ml_forecast': 'forecast',
        'ml_train': 'train_model',
        'audit_benford_law': 'benford_law',
        'ai_explain': 'explain_column',
        'ai_sentiment': 'sentiment_analysis',
        'ai_extract': 'extract_entities',
        'ai_pattern_learn': 'ai_pattern_learn',
        'stat_quick_stats': 'quick_stats',
        'stat_group_stats': 'group_stats',
        'ml_classify': 'ml_classify',
        'ml_risk_score': 'ml_risk_score',
        'ml_predict': 'ml_predict',
        'ml_linear_regression': 'ml_linear_regression',
        'ml_glm': 'ml_glm',
        'ml_decision_tree': 'ml_decision_tree',
        'ml_random_forest': 'ml_random_forest',
        'ml_gradient_boosting': 'ml_gradient_boosting',
        'ml_xgboost': 'ml_xgboost',
        'ml_lightgbm': 'ml_lightgbm',
        'ml_dbscan': 'ml_dbscan',
        'ml_gmm': 'ml_gmm',
        'ml_arima': 'ml_arima',
        'ml_ets': 'ml_ets',
        'ai_classify': 'ai_classify',
        'ai_summarize': 'ai_summarize',
        'ai_enrich': 'ai_enrich',
        'ai_generate_column': 'ai_generate_column',
        'audit_duplicate_detection': 'duplicate_detection',
        'audit_gap_analysis': 'gap_analysis',
        'audit_outlier_detection': 'audit_outlier_detection',
        'audit_round_numbers': 'round_number_detection',
        'stat_add_group_stats': 'add_group_stats',

        # New operations added to registry
        'text_extract_first': 'extract_first_chars',
        'text_extract_last': 'extract_last_chars',
        'text_extract_middle': 'extract_middle_chars',
        'math_modulo': 'modulo',
        'math_power': 'power',
        'text_add_prefix': 'add_prefix',
        'text_add_suffix': 'add_suffix',
        'replace_values': 'replace_values',
        'standardize_minmax': 'minmax_normalize',
    }

    def _format_column_template(self, template: str, params: Dict[str, Any]) -> str:
        """Format a column name template with parameters.

        Missing placeholders are replaced with the placeholder name (without braces).
        """
        # Find all placeholders
        placeholders = set(re.findall(r'\{([^}]+)\}', template))
        # Build mapping
        mapping = {}
        for ph in placeholders:
            if ph in params and params[ph] is not None:
                mapping[ph] = str(params[ph])
            else:
                # Fallback to placeholder name
                mapping[ph] = ph
        # Replace placeholders
        result = template
        for ph, val in mapping.items():
            result = result.replace('{' + ph + '}', val)
        return result

    def _map_parameters_to_method(self, method, params: Dict[str, Any]) -> Dict[str, Any]:
        """Map parameter names to match method signature.

        Handles common aliases like 'output_column' -> 'output_col'.
        Removes parameters not accepted by the method.
        """
        import inspect
        sig = inspect.signature(method)
        param_names = set(sig.parameters.keys())
        # Remove 'self' and 'df' as they are provided separately
        param_names.discard('self')
        param_names.discard('df')

        # Common alias mapping (schema param -> method param)
        alias_map = {
            'output_column': 'output_col',
            'probability_column': 'probability_col',
            'confidence_column': 'confidence_col',
            'deviation_column': 'deviation_col',
            'score_column': 'score_col',
            'flag_column': 'flag_col',
            'missing_count_column': 'missing_count_col',
            'var_name': 'var_name',
            'value_name': 'value_name',
        }

        mapped_params = {}
        for key, value in params.items():
            # Try to map key via aliases
            mapped_key = alias_map.get(key, key)
            if mapped_key in param_names:
                mapped_params[mapped_key] = value
            # If key not in param_names, drop it (e.g., 'operation')

        return mapped_params

    def _call_mapped_method(self, method, df: pl.DataFrame, params: Dict[str, Any], **extra_kwargs):
        """Call a method with mapped parameters and extra keyword arguments."""
        mapped = self._map_parameters_to_method(method, params)
        mapped.update(extra_kwargs)
        return method(df, **mapped)

    def apply_operation(self, df: pl.DataFrame, operation_id: str, params: Dict[str, Any]) -> pl.DataFrame:
        """
        Main dispatcher for all transformation operations.

        Args:
            df: The input Polars DataFrame.
            operation_id: The unique ID of the operation from OPERATION_REGISTRY.
            params: A dictionary of parameters for the operation.

        Returns:
            A new Polars DataFrame with the operation applied.
        """
        # Look up the operation to find its type
        op_info = OPERATION_REGISTRY.get(operation_id)
        if not op_info:
            raise ValueError(f"Unknown operation_id: {operation_id}")

        op_type = op_info['type']

        # Generate output column name(s) from the source column
        column = params.get('column')
        creates_columns = op_info.get('creates_columns', False)
        if creates_columns and column:
            if isinstance(creates_columns, list):
                # Multiple columns created (e.g., split operations)
                # Only generate if output_cols not already provided
                if 'output_cols' not in params:
                    format_params = params.copy()
                    output_cols = [self._format_column_template(col_name, format_params) for col_name in creates_columns]
                    # If only one column, use output_col (singular) instead of output_cols (plural)
                    if len(output_cols) == 1:
                        # Only set output_col if not already provided
                        if 'output_col' not in params:
                            params['output_col'] = output_cols[0]
                    else:
                        params['output_cols'] = output_cols
            elif creates_columns is True:
                # Single column created
                # Only generate output_col if not already provided
                if 'output_col' not in params:
                    naming_pattern = op_info.get('column_naming_pattern', '{column}_{operation}')
                    format_params = params.copy()
                    format_params['operation'] = operation_id.split('_')[-1]
                    output_col = self._format_column_template(naming_pattern, format_params)
                    params['output_col'] = output_col

        # Dispatch based on operation type or specific ID
        # Text transformations
        if operation_id == 'text_uppercase':
            return self._call_mapped_method(self.uppercase, df, params)
        elif operation_id == 'text_lowercase':
            return self._call_mapped_method(self.lowercase, df, params)
        elif operation_id == 'text_titlecase':
            return self._call_mapped_method(self.titlecase, df, params)
        elif operation_id == 'text_trim':
            return self._call_mapped_method(self.trim, df, params)
        elif operation_id == 'text_extract_numbers':
            return self._call_mapped_method(self.extract_numbers, df, params)
        elif operation_id == 'text_extract_text':
            return self._call_mapped_method(self.extract_text, df, params)
        elif operation_id == 'text_reverse':
            return self._call_mapped_method(self.reverse_text, df, params)
        elif operation_id == 'text_length':
            return self._call_mapped_method(self.text_length, df, params)
        elif operation_id == 'text_hash_md5':
            return self._call_mapped_method(self.hash_md5, df, params)
        elif operation_id == 'text_soundex':
            return self._call_mapped_method(self.soundex, df, params)

        # Text extraction operations (Excel LEFT/RIGHT/MID style)
        elif operation_id == 'text_extract_first':
            return self._call_mapped_method(self.extract_first_chars, df, params)
        elif operation_id == 'text_extract_last':
            return self._call_mapped_method(self.extract_last_chars, df, params)
        elif operation_id == 'text_extract_middle':
            return self._call_mapped_method(self.extract_middle_chars, df, params)

        # Text prefix/suffix operations
        elif operation_id == 'text_add_prefix':
            return self._call_mapped_method(self.add_prefix, df, params)
        elif operation_id == 'text_add_suffix':
            return self._call_mapped_method(self.add_suffix, df, params)

        # Replace values operation
        elif operation_id == 'replace_values':
            return self._call_mapped_method(self.replace_values, df, params)

        # Math transformations
        elif operation_id == 'math_round':
            return self._call_mapped_method(self.round_val, df, params)
        elif operation_id == 'math_ceil':
            return self._call_mapped_method(self.ceil_val, df, params)
        elif operation_id == 'math_floor':
            return self._call_mapped_method(self.floor_val, df, params)
        elif operation_id == 'math_abs':
            return self._call_mapped_method(self.abs_val, df, params)
        elif operation_id == 'math_sqrt':
            return self._call_mapped_method(self.sqrt_val, df, params)
        elif operation_id == 'math_square':
            return self._call_mapped_method(self.square_val, df, params)
        elif operation_id == 'math_log':
            return self._call_mapped_method(self.log_val, df, params)
        elif operation_id == 'math_log10':
            return self._call_mapped_method(self.log10_val, df, params)
        elif operation_id == 'math_exp':
            return self._call_mapped_method(self.exp_val, df, params)
        elif operation_id == 'math_modulo':
            return self._call_mapped_method(self.modulo, df, params)
        elif operation_id == 'math_power':
            return self._call_mapped_method(self.power, df, params)

        # Trigonometric transformations
        elif operation_id == 'trig_sin':
            return self._call_mapped_method(self.sin_val, df, params)
        elif operation_id == 'trig_cos':
            return self._call_mapped_method(self.cos_val, df, params)
        elif operation_id == 'trig_tan':
            return self._call_mapped_method(self.tan_val, df, params)
        elif operation_id == 'trig_asin':
            return self._call_mapped_method(self.asin_val, df, params)
        elif operation_id == 'trig_acos':
            return self._call_mapped_method(self.acos_val, df, params)
        elif operation_id == 'trig_atan':
            return self._call_mapped_method(self.atan_val, df, params)

        # DateTime transformations
        elif operation_id == 'datetime_year':
            return self._call_mapped_method(self.extract_year, df, params)
        elif operation_id == 'datetime_month':
            return self._call_mapped_method(self.extract_month, df, params)
        elif operation_id == 'datetime_day':
            return self._call_mapped_method(self.extract_day, df, params)
        elif operation_id == 'datetime_hour':
            return self._call_mapped_method(self.extract_hour, df, params)
        elif operation_id == 'datetime_minute':
            return self._call_mapped_method(self.extract_minute, df, params)
        elif operation_id == 'datetime_second':
            return self._call_mapped_method(self.extract_second, df, params)
        elif operation_id == 'datetime_weekday':
            return self._call_mapped_method(self.extract_weekday, df, params)
        elif operation_id == 'datetime_quarter':
            return self._call_mapped_method(self.extract_quarter, df, params)
        elif operation_id == 'datetime_age_days':
            return self._call_mapped_method(self.age_days, df, params)
        elif operation_id == 'datetime_age_years':
            return self._call_mapped_method(self.age_years, df, params)
        elif operation_id == 'datetime_is_weekend':
            return self._call_mapped_method(self.is_weekend, df, params)
        elif operation_id == 'datetime_is_leap_year':
            return self._call_mapped_method(self.is_leap_year, df, params)
        elif operation_id == 'datetime_days_in_month':
            return self._call_mapped_method(self.days_in_month, df, params)

        # Statistical transformations
        elif operation_id == 'stat_zscore':
            return self._call_mapped_method(self.zscore_transform, df, params)
        elif operation_id == 'stat_percent_rank':
            return self._call_mapped_method(self.percent_rank_transform, df, params)
        elif operation_id == 'stat_rank':
            return self._call_mapped_method(self.rank_transform, df, params)
        elif operation_id == 'standardize_minmax':
            return self._call_mapped_method(self.minmax_normalize, df, params)

        # ML transformations
        elif operation_id == 'ml_anomaly_iforest':
            return self._call_mapped_method(self.ml_anomaly_iforest, df, params)
        elif operation_id == 'ml_anomaly_zscore':
            return self._call_mapped_method(self.ml_anomaly_zscore, df, params)
        elif operation_id == 'ml_anomaly_iqr':
            return self._call_mapped_method(self.ml_anomaly_iqr, df, params)
        elif operation_id == 'ml_anomaly_lof':
            return self._call_mapped_method(self.ml_anomaly_lof, df, params)
        elif operation_id == 'ml_outlier':
            return self._call_mapped_method(self.ml_outlier_detection, df, params)
        elif operation_id == 'ml_cluster':
            return self._call_mapped_method(self.ml_clustering, df, params)
        elif operation_id == 'ml_forecast':
            return self._call_mapped_method(self.ml_forecast, df, params)

        # ML Training operations
        elif operation_id == 'ml_train':
            return self._call_mapped_method(self.ml_train_model, df, params)

        # Financial operations
        elif operation_id == 'financial_ratios':
            return self.financial_ratios(
                df, 
                params.get('mapping', {}), 
                params.get('ratios', []),
                **{k: v for k, v in params.items() if k not in ['mapping', 'ratios']}
            )
        elif operation_id == 'ifrs9_staging':
            return self.ifrs9_staging(df, params.get('mapping', {}), params.get('thresholds', {}))
            
        # SOX operations
        elif operation_id == 'sox_sod_analysis':
            return self.sox_sod_analysis(
                df, 
                params.get('user_column'), 
                params.get('action_column'),
                params.get('conflicts', [])
            )
        elif operation_id == 'coso_risk_heatmap':
            return self.coso_risk_heatmap(
                df,
                params.get('category_column'),
                params.get('risk_score_column'),
                params.get('mapping', {})
            )

        # Audit transformations
        elif operation_id == 'audit_benfords_law':
            return self._call_mapped_method(self.audit_benford_law, df, params)

        # AI transformations
        elif operation_id == 'ai_explain':
            return self._call_mapped_method(self.ai_explain_column, df, params)
        elif operation_id == 'ai_sentiment':
            return self._call_mapped_method(self.ai_sentiment_analysis, df, params)
        elif operation_id == 'ai_extract':
            return self._call_mapped_method(self.ai_entity_extraction, df, params)
        elif operation_id == 'ai_pattern_learn':
            return self._call_mapped_method(self.ai_pattern_learning, df, params)
        elif operation_id == 'ai_classify':
            return self._call_mapped_method(self.ai_classify, df, params)
        elif operation_id == 'ai_summarize':
            return self._call_mapped_method(self.ai_summarize, df, params)
        elif operation_id == 'ai_enrich':
            return self._call_mapped_method(self.ai_enrich, df, params)
        elif operation_id == 'ai_generate_column':
            return self._call_mapped_method(self.ai_generate_column, df, params)

        # ML Classification & Prediction
        elif operation_id == 'ml_classify':
            return self._call_mapped_method(self.ml_classify, df, params)
        elif operation_id == 'ml_risk_score':
            return self._call_mapped_method(self.ml_risk_score, df, params)
        elif operation_id == 'ml_predict':
            return self._call_mapped_method(self.ml_predict, df, params)

        # Supervised Learning - Regression
        elif operation_id == 'ml_linear_regression':
            return self._call_mapped_method(self.ml_linear_regression, df, params)
        elif operation_id == 'ml_glm':
            return self._call_mapped_method(self.ml_glm, df, params)

        # Supervised Learning - Tree-based
        elif operation_id == 'ml_decision_tree':
            return self._call_mapped_method(self.ml_decision_tree, df, params)
        elif operation_id == 'ml_random_forest':
            return self._call_mapped_method(self.ml_random_forest, df, params)
        elif operation_id == 'ml_gradient_boosting':
            return self._call_mapped_method(self.ml_gradient_boosting, df, params)
        elif operation_id == 'ml_xgboost':
            return self._call_mapped_method(self.ml_xgboost, df, params)
        elif operation_id == 'ml_lightgbm':
            return self._call_mapped_method(self.ml_lightgbm, df, params)

        # Unsupervised Learning - Clustering
        elif operation_id == 'ml_dbscan':
            return self._call_mapped_method(self.ml_dbscan, df, params)
        elif operation_id == 'ml_gmm':
            return self._call_mapped_method(self.ml_gmm, df, params)

        # Time Series
        elif operation_id == 'ml_arima':
            return self._call_mapped_method(self.ml_arima, df, params)
        elif operation_id == 'ml_ets':
            return self._call_mapped_method(self.ml_ets, df, params)

        # Audit transformations
        elif operation_id == 'audit_duplicate_detection':
            return self._call_mapped_method(self.audit_duplicate_detection, df, params)
        elif operation_id == 'audit_gap_analysis':
            return self._call_mapped_method(self.audit_gap_analysis, df, params)
        elif operation_id == 'audit_outlier_detection':
            return self._call_mapped_method(self.audit_outlier_detection, df, params)
        elif operation_id == 'audit_round_numbers':
            return self._call_mapped_method(self.audit_round_numbers, df, params)

        # Statistics group operations
        elif operation_id == 'stat_add_group_stats':
            return self._call_mapped_method(self.stat_add_group_stats, df, params)

        # Column operations
        elif operation_id == 'column_rename':
            return self._call_mapped_method(self.rename_col, df, params)

        # Split operations
        elif operation_id == 'split_comma':
            return self._call_mapped_method(self.split_column, df, params, delimiter=',')
        elif operation_id == 'split_space':
            return self._call_mapped_method(self.split_column, df, params, delimiter=' ')
        elif operation_id == 'split_semicolon':
            return self._call_mapped_method(self.split_column, df, params, delimiter=';')
        elif operation_id == 'split_pipe':
            return self._call_mapped_method(self.split_column, df, params, delimiter='|')
        elif operation_id == 'split_custom':
            return self._call_mapped_method(self.split_column, df, params)

        # New column/table operations
        elif operation_id == 'split_columns_by_delimiter':
            return self._call_mapped_method(self.split_columns_by_delimiter, df, params)
        elif operation_id == 'custom_column_from_math':
            return self._call_mapped_method(self.custom_column_from_math, df, params)
        elif operation_id == 'calculated_columns':
            return self._call_mapped_method(self.calculated_columns, df, params)
        elif operation_id == 'choose_columns':
            return self._call_mapped_method(self.choose_columns, df, params)
        elif operation_id == 'change_dtype':
            return self._call_mapped_method(self.change_data_type_extended, df, params)
        elif operation_id == 'rename_columns':
            return self._call_mapped_method(self.rename_columns_bulk, df, params)
        elif operation_id == 'split_alphanumeric':
            return self._call_mapped_method(self.split_alphanumeric, df, params)
        elif operation_id == 'transpose':
            return self._call_mapped_method(self.transpose_table, df, params)
        elif operation_id == 'promote_row_header':
            return self.promote_row_as_header(df, params.get('row_index', 0))
        elif operation_id == 'remove_rows':
            return self.remove_rows(df, params.get('row_indices', []), params.get('remove', True))
        elif operation_id == 'filter_rows':
            return self.filter_rows_by_value(
                df,
                params.get('column'),
                params.get('operator'),
                params.get('value')
            )
        elif operation_id == 'join_datasets':
            return self._call_mapped_method(self.join_datasets, df, params)
        elif operation_id == 'append_datasets':
            return self._call_mapped_method(self.append_datasets, df, params)

        # Aggregate operations (summary reports)
        elif operation_id == 'group_summary':
            return self._call_mapped_method(self.group_summary, df, params)
        elif operation_id == 'stratification':
            return self._call_mapped_method(self.stratification, df, params)
        elif operation_id == 'cross_tabulation':
            return self._call_mapped_method(self.cross_tabulation, df, params)
        elif operation_id == 'trend_analysis':
            return self._call_mapped_method(self.trend_analysis, df, params)
        elif operation_id == 'top_bottom':
            return self._call_mapped_method(self.top_bottom_items, df, params)
        elif operation_id == 'sampling':
            return self._call_mapped_method(self.sampling, df, params)

        # Pivot operations
        elif op_type == TransformationStepType.PIVOT:
            return self._call_mapped_method(self.pivot, df, params)
        elif op_type == TransformationStepType.UNPIVOT:
            return self._call_mapped_method(self.unpivot, df, params)

        # Filter operations
        elif op_type == TransformationStepType.FILTER:
            return self._call_mapped_method(self.filter_rows, df, params)

        # Sort operations
        elif op_type == TransformationStepType.SORT:
            return self._call_mapped_method(self.sort_rows, df, params)

        else:
            raise NotImplementedError(f"Operation '{operation_id}' of type '{op_type}' is not yet implemented.")

    # ============================================================================
    # TEXT TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def uppercase(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Convert text to uppercase"""
        return df.with_columns(pl.col(column).str.to_uppercase().alias(output_col))

    def lowercase(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Convert text to lowercase"""
        return df.with_columns(pl.col(column).str.to_lowercase().alias(output_col))

    def titlecase(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Convert text to title case"""
        return df.with_columns(pl.col(column).str.to_titlecase().alias(output_col))

    def trim(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Remove leading/trailing whitespace"""
        return df.with_columns(pl.col(column).str.strip_chars().alias(output_col))

    def extract_numbers(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract numbers from text"""
        return df.with_columns(
            pl.col(column).str.extract_all(r"\d+").list.join("").alias(output_col)
        )

    def extract_text(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract alphabetic text"""
        return df.with_columns(
            pl.col(column).str.replace_all(r"\d+", "", literal=True).str.strip_chars().alias(output_col)
        )

    def reverse_text(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Reverse text string"""
        return df.with_columns(
            pl.col(column).str.reverse().alias(output_col)
        )

    def text_length(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Get text length"""
        return df.with_columns(pl.col(column).str.len_bytes().alias(output_col))

    def hash_md5(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Create MD5 hash"""
        import hashlib
        return df.with_columns(
            pl.col(column).map_elements(
                lambda x: hashlib.md5(str(x).encode()).hexdigest() if x is not None else None,
                return_dtype=pl.Utf8
            ).alias(output_col)
        )

    def soundex(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Create Soundex code"""
        def soundex_code(word):
            if not word:
                return "0000"
            word = str(word).upper()[:4]
            mapping = {"BFPV": "1", "CGJKQSXZ": "2", "DT": "3", "L": "4", "MN": "5", "R": "6"}
            result = [word[0]]
            prev = ""
            for char in word[1:]:
                for letters, code in mapping.items():
                    if char in letters and code != prev:
                        result.append(code)
                        prev = code
                        break
            return (''.join(result) + "000")[:4]

        return df.with_columns(
            pl.col(column).map_elements(soundex_code, return_dtype=pl.Utf8).alias(output_col)
        )

    # ============================================================================
    # MATH TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def round_val(self, df: pl.DataFrame, column: str, output_col: str, decimals: int = 2) -> pl.DataFrame:
        """Round numbers"""
        return df.with_columns(pl.col(column).round(decimals).alias(output_col))

    def ceil_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Ceiling (round up)"""
        return df.with_columns(pl.col(column).ceil().alias(output_col))

    def floor_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Floor (round down)"""
        return df.with_columns(pl.col(column).floor().alias(output_col))

    def abs_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Absolute value"""
        return df.with_columns(pl.col(column).abs().alias(output_col))

    def sqrt_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Square root"""
        return df.with_columns((pl.col(column) ** 0.5).alias(output_col))

    def square_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Square"""
        return df.with_columns((pl.col(column) ** 2).alias(output_col))

    def log_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Natural logarithm"""
        return df.with_columns(pl.col(column).log().alias(output_col))

    def log10_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Base-10 logarithm"""
        return df.with_columns(pl.col(column).log10().alias(output_col))

    def exp_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Exponential (e^x)"""
        return df.with_columns(pl.col(column).exp().alias(output_col))

    # ============================================================================
    # TRIGONOMETRIC TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def sin_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Sine (radians)"""
        return df.with_columns(pl.col(column).sin().alias(output_col))

    def cos_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Cosine (radians)"""
        return df.with_columns(pl.col(column).cos().alias(output_col))

    def tan_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Tangent (radians)"""
        return df.with_columns(pl.col(column).tan().alias(output_col))

    def asin_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Arc sine (radians)"""
        return df.with_columns(pl.col(column).arcsin().alias(output_col))

    def acos_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Arc cosine (radians)"""
        return df.with_columns(pl.col(column).arccos().alias(output_col))

    def atan_val(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Arc tangent (radians)"""
        return df.with_columns(pl.col(column).arctan().alias(output_col))

    # ============================================================================
    # DATETIME TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def _ensure_datetime(self, df: pl.DataFrame, column: str):
        """Ensure column is datetime type"""
        col_dtype = df[column].dtype

        # If already datetime type, return as is
        if isinstance(col_dtype, pl.Datetime) or isinstance(col_dtype, pl.Date):
            return df[column]

        # If string type, convert to datetime
        if col_dtype == pl.Utf8:
            return df[column].str.to_datetime()

        # For other types, try to convert
        return df[column].cast(pl.Datetime)

    def extract_year(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract year"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.year().alias(output_col))

    def extract_month(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract month (1-12)"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.month().alias(output_col))

    def extract_day(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract day of month"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.day().alias(output_col))

    def extract_hour(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract hour"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.hour().alias(output_col))

    def extract_minute(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract minute"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.minute().alias(output_col))

    def extract_second(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract second"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.second().alias(output_col))

    def extract_weekday(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract weekday (0=Monday, 6=Sunday)"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.weekday().alias(output_col))

    def extract_quarter(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Extract quarter (1-4)"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(dates.dt.quarter().alias(output_col))

    def age_days(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate age in days from today"""
        from datetime import datetime
        today = datetime.now()
        dates = self._ensure_datetime(df, column)
        return df.with_columns(
            (pl.lit(today).cast(pl.Datetime()) - dates.cast(pl.Datetime())).dt.total_days().abs().alias(output_col)
        )

    def age_years(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate age in years from today"""
        days_col = f"_temp_days_{column}"
        dates = self._ensure_datetime(df, column)
        today = datetime.now()
        temp_df = df.with_columns(
            (pl.lit(today).cast(pl.Datetime()) - dates.cast(pl.Datetime())).dt.total_days().abs().alias(days_col)
        )
        return temp_df.with_columns(
            (pl.col(days_col) / 365.25).cast(pl.Int64).alias(output_col)
        ).drop(days_col)

    def is_weekend(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Check if date is weekend"""
        dates = self._ensure_datetime(df, column)
        weekday = dates.dt.weekday()
        return df.with_columns(((weekday == 6) | (weekday == 7)).alias(output_col))

    def is_leap_year(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Check if year is leap year"""
        dates = self._ensure_datetime(df, column)
        year = dates.dt.year()
        return df.with_columns(((year % 4 == 0) & ((year % 100 != 0) | (year % 400 == 0))).alias(output_col))

    def days_in_month(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Get days in month using native polars method"""
        dates = self._ensure_datetime(df, column)
        return df.with_columns(
            dates.dt.days_in_month().alias(output_col)
        )

    # ============================================================================
    # STATISTICAL TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def zscore_transform(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate z-score"""
        col = pl.col(column)
        mean = df[column].mean()
        std = df[column].std()
        if std == 0:
            std = 1
        return df.with_columns(((col - mean) / std).alias(output_col))

    def percent_rank_transform(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate percent rank"""
        return df.with_columns(pl.col(column).rank("average", pct=True).alias(output_col))

    def rank_transform(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Calculate rank"""
        return df.with_columns(pl.col(column).rank("average").alias(output_col))

    # ============================================================================
    # ML TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def ml_anomaly_iforest(self, df: pl.DataFrame, column: str, contamination: float = 0.1) -> pl.DataFrame:
        """Anomaly detection using Isolation Forest - simplified"""
        import numpy as np
        col_data = df[column].to_numpy().reshape(-1, 1)
        mean_val = np.mean(col_data)
        std_val = np.std(col_data)
        if std_val == 0:
            std_val = 1

        distances = np.abs(col_data - mean_val) / std_val
        threshold = 2.5
        is_anomaly = distances > threshold
        scores = 1 - (1 / (1 + distances))

        return df.with_columns([
            pl.Series(name=f"{column}_is_anomaly", values=is_anomaly.flatten()),
            pl.Series(name=f"{column}_anomaly_score", values=scores.flatten())
        ])

    def ml_anomaly_zscore(self, df: pl.DataFrame, column: str, threshold: float = 3.0) -> pl.DataFrame:
        """Anomaly detection using Z-score"""
        import numpy as np
        col_data = df[column].to_numpy()
        mean = np.mean(col_data)
        std = np.std(col_data)
        if std == 0:
            std = 1
        zscore = (col_data - mean) / std
        is_outlier = np.abs(zscore) > threshold
        return df.with_columns([
            pl.Series(name=f"{column}_is_outlier", values=is_outlier),
            pl.Series(name=f"{column}_zscore", values=zscore)
        ])

    def ml_anomaly_iqr(self, df: pl.DataFrame, column: str, multiplier: float = 1.5) -> pl.DataFrame:
        """Anomaly detection using IQR"""
        col_data = df[column].to_numpy()
        Q1 = np.percentile(col_data, 25)
        Q3 = np.percentile(col_data, 75)
        IQR = Q3 - Q1
        lower_bound = Q1 - multiplier * IQR
        upper_bound = Q3 + multiplier * IQR
        is_outlier = (col_data < lower_bound) | (col_data > upper_bound)
        iqr_distance = np.abs(col_data - (Q3 + Q1) / 2)
        return df.with_columns([
            pl.Series(name=f"{column}_is_outlier", values=is_outlier),
            pl.Series(name=f"{column}_iqr_distance", values=iqr_distance)
        ])

    def ml_anomaly_lof(self, df: pl.DataFrame, column: str, n_neighbors: int = 20) -> pl.DataFrame:
        """Local Outlier Factor - simplified"""
        import numpy as np
        col_data = df[column].to_numpy()
        mean_val = np.mean(col_data)
        distances = np.abs(col_data - mean_val)
        max_dist = np.max(distances)
        if max_dist == 0:
            max_dist = 1
        scores = 1 - (distances / max_dist)
        is_outlier = scores < 0.3
        return df.with_columns([
            pl.Series(name=f"{column}_is_outlier", values=is_outlier),
            pl.Series(name=f"{column}_lof_score", values=scores)
        ])

    def ml_outlier_detection(self, df: pl.DataFrame, column: str, output_col: str, method: str = 'iqr') -> pl.DataFrame:
        """General outlier detection"""
        if method == 'zscore':
            return self.ml_anomaly_zscore(df, column=column, output_col=output_col, threshold=3.0)
        else:
            return self.ml_anomaly_iqr(df, column=column, output_col=output_col, multiplier=1.5)

    def ml_clustering(self, df: pl.DataFrame, column: str, output_col: str, n_clusters: int = 3) -> pl.DataFrame:
        """K-Means clustering - simplified"""
        import numpy as np
        col_data = df[column].to_numpy().reshape(-1, 1)
        means = np.mean(col_data, axis=0)
        stds = np.std(col_data, axis=0)
        if stds == 0:
            stds = 1
        normalized = (col_data - means) / stds

        np.random.seed(42)
        centers = normalized[np.random.choice(len(normalized), n_clusters, replace=False)]

        distances = np.zeros((len(normalized), n_clusters))
        for i in range(n_clusters):
            distances[:, i] = np.linalg.norm(normalized - centers[i], axis=1)
        labels = np.argmin(distances, axis=1)

        return df.with_columns(pl.Series(name=output_col, values=labels))

    def ml_forecast(self, df: pl.DataFrame, column: str, output_col: str, periods: int = 12) -> pl.DataFrame:
        """Simple time series forecast using exponential smoothing"""
        import numpy as np
        values = df[column].to_numpy()
        if len(values) == 0:
            return df.with_columns(pl.lit(None).alias(output_col))

        alpha = 0.3
        n = len(values)
        smoothed = np.zeros(n)

        smoothed[0] = values[0]
        for i in range(1, n):
            smoothed[i] = alpha * values[i] + (1 - alpha) * smoothed[i - 1]

        return df.with_columns(pl.Series(name=output_col, values=smoothed))

    def ml_train_model(self, df: pl.DataFrame, model_name: str, algorithm: str, features: List[str],
                      target: str, test_split: float = 0.2, random_seed: int = 42) -> pl.DataFrame:
        """
        Train an ML model and save it for later use.
        This operation doesn't modify the dataframe but saves a trained model.
        """
        try:
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, classification_report
            import joblib
            import os
        except ImportError:
            raise ImportError("scikit-learn and joblib are required for ML training")

        # Prepare data
        X = df.select(features).to_pandas()
        y = df[target].to_pandas()

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_split, random_state=random_seed
        )

        # Select and train model
        if algorithm == "random_forest":
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(random_state=random_seed)
        elif algorithm == "logistic_regression":
            from sklearn.linear_model import LogisticRegression
            model = LogisticRegression(random_state=random_seed)
        elif algorithm == "svm":
            from sklearn.svm import SVC
            model = SVC(random_state=random_seed)
        elif algorithm == "gradient_boosting":
            from sklearn.ensemble import GradientBoostingClassifier
            model = GradientBoostingClassifier(random_state=random_seed)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Train model
        model.fit(X_train, y_train)

        # Evaluate model
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        # Save model
        model_dir = Path(__file__).parent.parent.parent / "models"
        model_dir.mkdir(exist_ok=True)
        model_path = model_dir / f"{model_name}.joblib"
        joblib.dump(model, model_path)

        # Return original dataframe unchanged (this operation doesn't create columns)
        # But we could add metadata about the trained model
        print(f"Model '{model_name}' trained with accuracy: {accuracy:.3f}")
        print(f"Model saved to: {model_path}")

        return df  # Return unchanged dataframe

    # ============================================================================
    # FINANCIAL TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def financial_ratios(self, df: pl.DataFrame, mapping: Dict[str, str], ratios: List[str], **kwargs) -> pl.DataFrame:
        """Calculate financial ratios and advanced analysis"""
        from services.financial_service import FinancialService
        service = FinancialService()

        # Check for multi-dataset mode
        dataset_mapping = kwargs.get('dataset_mapping', {})
        all_datasets = kwargs.get('all_datasets', {})

        # 1. Standard Ratios - use multi-dataset if dataset_mapping provided
        if ratios:
            if dataset_mapping and all_datasets:
                # Multi-dataset mode
                df = service.calculate_ratios_multi_dataset(
                    df, mapping, dataset_mapping, all_datasets, ratios
                )
            else:
                # Single dataset mode
                df = service.calculate_ratios(df, mapping, ratios)

        # 2. Altman Z-Score
        if kwargs.get('do_altman_z'):
            df = service.calculate_altman_z_score(
                df, mapping, is_public=kwargs.get('is_public', False)
            )

        # 3. Vertical Analysis
        v_base = kwargs.get('vertical_base')
        v_cols = kwargs.get('vertical_cols', [])
        if v_base and v_cols:
            df = service.calculate_vertical_analysis(df, v_base, v_cols)

        # 4. Horizontal Analysis
        h_period = kwargs.get('horizontal_period')
        h_cols = kwargs.get('horizontal_cols', [])
        if h_period and h_cols:
            df = service.calculate_horizontal_analysis(df, h_period, h_cols)

        return df
        
    def ifrs9_staging(self, df: pl.DataFrame, mapping: Dict[str, str], thresholds: Dict[str, int]) -> pl.DataFrame:
        """Perform IFRS 9 Staging"""
        from services.ifrs9_service import IFRS9Service
        service = IFRS9Service()
        return service.perform_staging(df, mapping, thresholds)

    def sox_sod_analysis(self, df: pl.DataFrame, user_col: str, action_col: str, conflicts: List[Dict]) -> pl.DataFrame:
        """Perform SOX SoD Analysis"""
        from services.sox_service import SoxService
        service = SoxService()
        return service.analyze_sod_conflicts(df, user_col, action_col, conflicts)

    def coso_risk_heatmap(self, df: pl.DataFrame, category_col: str, risk_score_col: str, mapping: Dict[str, str]) -> pl.DataFrame:
        """Generate COSO Risk Heatmap"""
        from services.coso_service import CosoService
        service = CosoService()
        return service.generate_risk_heatmap(df, category_col, risk_score_col, mapping)

    # ============================================================================
    # AUDIT TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def audit_benford_law(self, df: pl.DataFrame, column: str, output_col: str, threshold: float = 0.1) -> pl.DataFrame:
        """Benford's Law analysis"""
        first_digit = df[column].cast(pl.Utf8).str.slice(0, 1)

        benford_expected = {
            '1': 0.301, '2': 0.176, '3': 0.125, '4': 0.097, '5': 0.079,
            '6': 0.067, '7': 0.058, '8': 0.051, '9': 0.046
        }

        total = len(df)
        digit_counts = first_digit.value_counts().to_dict()

        def calc_deviation(val):
            if val is None or str(val) == '0':
                return 0
            first = str(val)[0]
            expected = benford_expected.get(first, 0.05)
            actual = digit_counts.get(first, 0) / total if first in digit_counts else 0
            return abs(expected - actual)

        return df.with_columns(
            pl.col(column).map_elements(calc_deviation, return_dtype=pl.Float64).alias(output_col)
        )

    # ============================================================================
    # AI TRANSFORMATION IMPLEMENTATIONS
    # ============================================================================

    def ai_explain_column(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """AI explanation - placeholder"""
        return df.with_columns(
            pl.lit(f"AI analysis of {column}").alias(output_col)
        )

    def ai_sentiment_analysis(self, df: pl.DataFrame, column: str, output_col: str) -> pl.DataFrame:
        """Sentiment analysis - simplified"""
        positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'best', 'happy']
        negative_words = ['bad', 'poor', 'terrible', 'awful', 'hate', 'worst', 'sad']

        def simple_sentiment(text):
            if text is None:
                return 0.0
            text_lower = str(text).lower()
            pos_count = sum(1 for w in positive_words if w in text_lower)
            neg_count = sum(1 for w in negative_words if w in text_lower)
            return (pos_count - neg_count) / max(pos_count + neg_count, 1)

        return df.with_columns(
            pl.col(column).map_elements(simple_sentiment, return_dtype=pl.Float64).alias(output_col)
        )

    def ai_entity_extraction(self, df: pl.DataFrame, column: str, output_col: str, entity_type: str = 'email') -> pl.DataFrame:
        """Entity extraction - placeholder"""
        patterns = {
            'email': r'[\w\.-]+@[\w\.-]+',
            'phone': r'\d{3}-\d{3}-\d{4}|\d{10}',
            'date': r'\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}',
            'money': r'\$[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP)'
        }
        pattern = patterns.get(entity_type, r'.+')
        return df.with_columns(
            pl.col(column).str.extract_all(pattern).list.join(", ").alias(output_col)
        )

    def ai_pattern_learning(self, df: pl.DataFrame, column: str, output_col: str, pattern: str = None) -> pl.DataFrame:
        """Pattern learning (flash fill) - placeholder"""
        return df.with_columns(pl.col(column).alias(output_col))

    # ============================================================================
    # ML CLASSIFICATION & PREDICTION IMPLEMENTATIONS
    # ============================================================================

    def ml_classify(self, df: pl.DataFrame, features: List[str], target: str, output_col: str, probability_col: str,
                   model_id: str = None, **kwargs) -> pl.DataFrame:
        """ML Classification - trains model and predicts (simplified)"""
        try:
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.preprocessing import LabelEncoder
            import numpy as np
        except ImportError:
            # Fallback: return mock predictions
            return df.with_columns([
                pl.lit("unknown").alias(output_col),
                pl.lit(0.5).alias(probability_col)
            ])

        # Prepare features
        X = df.select(features).to_pandas()
        y_raw = df[target].to_pandas()

        # Encode target if string
        le = LabelEncoder()
        y = le.fit_transform(y_raw.astype(str))

        # Train simple model
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(X, y)

        # Predict
        predictions = model.predict(X)
        probabilities = model.predict_proba(X).max(axis=1)

        # Map back to original labels
        predicted_labels = le.inverse_transform(predictions)

        return df.with_columns([
            pl.Series(name=output_col, values=predicted_labels),
            pl.Series(name=probability_col, values=probabilities)
        ])

    def ml_risk_score(self, df: pl.DataFrame, group_column: str, features: List[str], output_col: str) -> pl.DataFrame:
        """Calculate risk score per group"""
        import numpy as np

        # Normalize features
        feature_data = df.select(features).to_numpy()
        means = np.mean(feature_data, axis=0)
        stds = np.std(feature_data, axis=0)
        stds[stds == 0] = 1
        normalized = (feature_data - means) / stds

        # Calculate risk as weighted sum of normalized features (simplified)
        weights = np.ones(len(features)) / len(features)
        risk_scores = np.dot(normalized, weights)
        risk_scores = (risk_scores - risk_scores.min()) / (risk_scores.max() - risk_scores.min() + 1e-8)

        return df.with_columns(pl.Series(name=output_col, values=risk_scores))

    def ml_predict(self, df: pl.DataFrame, model_id: str, features: List[str], output_col: str) -> pl.DataFrame:
        """Apply trained model to predict new values"""
        import joblib
        from pathlib import Path

        # Try to load model
        model_path = Path(__file__).parent.parent.parent / "models" / f"{model_id}.joblib"

        if not model_path.exists():
            # Fallback: return original values with mock prediction
            return df.with_columns(pl.col(features[0]).alias(output_col))

        try:
            model = joblib.load(model_path)
            X = df.select(features).to_pandas()
            predictions = model.predict(X)
            return df.with_columns(pl.Series(name=output_col, values=predictions))
        except Exception:
            return df.with_columns(pl.col(features[0]).alias(output_col))

    # ============================================================================
    # AI ENRICHMENT IMPLEMENTATIONS
    # ============================================================================

    def ai_classify(self, df: pl.DataFrame, column: str, categories: List[str], output_col: str,
                   confidence_col: str, **kwargs) -> pl.DataFrame:
        """AI Text Classification - simplified keyword-based"""
        def classify_text(text):
            if text is None:
                return "Unknown", 0.0
            text_lower = str(text).lower()
            best_category = categories[0] if categories else "Unclassified"
            best_score = 0.0

            for cat in categories:
                cat_lower = cat.lower()
                if cat_lower in text_lower:
                    return cat, 0.9
                # Partial match score
                words = cat_lower.split()
                match_count = sum(1 for w in words if w in text_lower)
                score = match_count / len(words) if words else 0
                if score > best_score:
                    best_score = score
                    best_category = cat

            return best_category, best_score

        results = [classify_text(v) for v in df[column]]
        return df.with_columns([
            pl.Series(name=output_col, values=[r[0] for r in results]),
            pl.Series(name=confidence_col, values=[r[1] for r in results])
        ])

    def ai_summarize(self, df: pl.DataFrame, column: str, max_length: int, output_col: str) -> pl.DataFrame:
        """AI Summarize - simplified extraction"""
        def summarize(text):
            if text is None:
                return ""
            text = str(text)
            # Simple truncation with ellipsis
            if len(text) > max_length:
                return text[:max_length - 3] + "..."
            return text

        return df.with_columns(
            pl.col(column).map_elements(summarize, return_dtype=pl.Utf8).alias(output_col)
        )

    def ai_enrich(self, df: pl.DataFrame, column: str, enrichment_type: str, output_col: str) -> pl.DataFrame:
        """AI Enrich - simplified enrichment based on type"""
        def enrich(value):
            if value is None:
                return ""
            value = str(value)
            if enrichment_type == "industry":
                # Simple heuristic classification
                keywords = {"tech": "Technology", "health": "Healthcare", "finance": "Financial",
                           "retail": "Retail", "manufacturing": "Manufacturing"}
                for kw, ind in keywords.items():
                    if kw in value.lower():
                        return ind
                return "Other"
            elif enrichment_type == "sentiment":
                return "Neutral"
            elif enrichment_type == "category":
                return value.split()[0] if value else "Unknown"
            else:
                return value

        return df.with_columns(
            pl.col(column).map_elements(enrich, return_dtype=pl.Utf8).alias(output_col)
        )

    def ai_generate_column(self, df: pl.DataFrame, column_name: str, instruction: str,
                           generated_code: str, **kwargs) -> pl.DataFrame:
        """Execute AI-generated column code"""
        try:
            # Create execution context with df available
            exec_globals = {"pl": pl}
            exec_locals = {"df": df}

            # Check if code reassigns df
            lines = generated_code.strip().split("\n")
            first_line = lines[0] if lines else ""
            reassigns_df = "=" in first_line and first_line.split("=")[0].strip() in ("df", "_df")

            if not reassigns_df:
                # Wrap to capture result
                wrapped = "_result = (" + generated_code.strip() + ")\n_result"
                code_to_exec = wrapped
            else:
                code_to_exec = generated_code

            exec(code_to_exec, exec_globals, exec_locals)

            # Get result
            if "_result" in exec_locals:
                result = exec_locals["_result"]
                if isinstance(result, pl.DataFrame):
                    return result
            if "df" in exec_locals:
                result_df = exec_locals["df"]
                if isinstance(result_df, pl.DataFrame):
                    return result_df

            return df
        except Exception as e:
            print(f"Error executing AI-generated column code: {e}")
            raise

    # ============================================================================
    # SUPERVISED LEARNING - REGRESSION
    # ============================================================================

    def ml_linear_regression(self, df: pl.DataFrame, features: List[str], target: str,
                             output_col: str = "y_hat", fit_intercept: bool = True,
                             **kwargs) -> pl.DataFrame:
        """Linear regression prediction"""
        try:
            from sklearn.linear_model import LinearRegression
            from sklearn.preprocessing import StandardScaler

            # Convert to pandas for sklearn
            X = df.select(features).to_pandas()
            y = df[target].to_pandas()

            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Train model
            model = LinearRegression(fit_intercept=fit_intercept)
            model.fit(X_scaled, y)

            # Predict
            y_pred = model.predict(X_scaled)

            return df.with_columns(pl.Series(name=output_col, values=y_pred))

        except Exception as e:
            print(f"Linear regression error: {e}")
            raise

    def ml_glm(self, df: pl.DataFrame, features: List[str], target: str,
               output_col: str = "y_hat", family: str = "gaussian",
               **kwargs) -> pl.DataFrame:
        """Generalized Linear Model prediction"""
        try:
            import statsmodels.api as sm
            from statsmodels.genmod.families import Gaussian, Binomial, Poisson, Gamma

            family_map = {
                "gaussian": Gaussian(),
                "binomial": Binomial(),
                "poisson": Poisson(),
                "gamma": Gamma()
            }

            # Convert to pandas for statsmodels
            X = df.select(features).to_pandas()
            y = df[target].to_pandas()

            # Add constant for intercept
            X = sm.add_constant(X)

            # Fit GLM
            model = sm.GLM(y, X, family=family_map.get(family, Gaussian()))
            result = model.fit()

            # Predict
            y_pred = result.predict(X)

            return df.with_columns(pl.Series(name=output_col, values=y_pred))

        except Exception as e:
            print(f"GLM error: {e}")
            raise

    # ============================================================================
    # SUPERVISED LEARNING - TREE-BASED
    # ============================================================================

    def ml_decision_tree(self, df: pl.DataFrame, features: List[str], target: str,
                         output_col: str = "prediction", max_depth: int = 10,
                         min_samples_split: int = 2, min_samples_leaf: int = 1,
                         **kwargs) -> pl.DataFrame:
        """Decision tree prediction"""
        try:
            from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
            from sklearn.preprocessing import LabelEncoder

            # Convert to pandas
            X = df.select(features).to_pandas()
            y = df[target].to_pandas()

            # Encode target if categorical
            le = LabelEncoder()
            y_encoded = le.fit_transform(y)

            # Determine if classification or regression
            is_classification = len(le.classes_) <= 10 and y.dtype == 'object'

            # Train model
            if is_classification:
                model = DecisionTreeClassifier(max_depth=max_depth, min_samples_split=min_samples_split, min_samples_leaf=min_samples_leaf)
            else:
                model = DecisionTreeRegressor(max_depth=max_depth, min_samples_split=min_samples_split, min_samples_leaf=min_samples_leaf)

            model.fit(X, y_encoded)

            # Predict
            y_pred = model.predict(X)

            # Decode if classification
            if is_classification:
                y_pred = le.inverse_transform(y_pred.astype(int))

            return df.with_columns(pl.Series(name=output_col, values=y_pred))

        except Exception as e:
            print(f"Decision tree error: {e}")
            raise

    def ml_random_forest(self, df: pl.DataFrame, features: List[str], target: str,
                         output_col: str = "prediction", n_estimators: int = 100,
                         max_depth: int = 10, min_samples_split: int = 2,
                         min_samples_leaf: int = 1, **kwargs) -> pl.DataFrame:
        """Random forest prediction"""
        try:
            from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
            from sklearn.preprocessing import LabelEncoder

            X = df.select(features).to_pandas()
            y = df[target].to_pandas()

            le = LabelEncoder()
            y_encoded = le.fit_transform(y)

            is_classification = len(le.classes_) <= 10 and y.dtype == 'object'

            if is_classification:
                model = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth,
                                               min_samples_split=min_samples_split, min_samples_leaf=min_samples_leaf)
            else:
                model = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth,
                                              min_samples_split=min_samples_split, min_samples_leaf=min_samples_leaf)

            model.fit(X, y_encoded)
            y_pred = model.predict(X)

            if is_classification:
                y_pred = le.inverse_transform(y_pred.astype(int))

            return df.with_columns(pl.Series(name=output_col, values=y_pred))

        except Exception as e:
            print(f"Random forest error: {e}")
            raise

    def ml_gradient_boosting(self, df: pl.DataFrame, features: List[str], target: str,
                             output_col: str = "prediction", n_estimators: int = 100,
                             learning_rate: float = 0.1, max_depth: int = 5,
                             min_samples_split: int = 2, min_samples_leaf: int = 1,
                             **kwargs) -> pl.DataFrame:
        """Gradient boosting prediction"""
        try:
            from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
            from sklearn.preprocessing import LabelEncoder

            # Validate parameters
            learning_rate = max(0.01, float(learning_rate))
            n_estimators = max(1, int(n_estimators))
            max_depth = max(1, int(max_depth))
            min_samples_split = max(2, int(min_samples_split))
            min_samples_leaf = max(1, int(min_samples_leaf))

            X = df.select(features).to_pandas()
            y = df[target].to_pandas()

            le = LabelEncoder()
            y_encoded = le.fit_transform(y)

            is_classification = len(le.classes_) <= 10 and y.dtype == 'object'

            if is_classification:
                model = GradientBoostingClassifier(n_estimators=n_estimators, learning_rate=learning_rate,
                                                   max_depth=max_depth, min_samples_split=min_samples_split,
                                                   min_samples_leaf=min_samples_leaf)
            else:
                model = GradientBoostingRegressor(n_estimators=n_estimators, learning_rate=learning_rate,
                                                  max_depth=max_depth, min_samples_split=min_samples_split,
                                                  min_samples_leaf=min_samples_leaf)

            model.fit(X, y_encoded)
            y_pred = model.predict(X)

            if is_classification:
                y_pred = le.inverse_transform(y_pred.astype(int))

            return df.with_columns(pl.Series(name=output_col, values=y_pred))

        except Exception as e:
            print(f"Gradient boosting error: {e}")
            raise

    def ml_xgboost(self, df: pl.DataFrame, features: List[str], target: str,
                   output_col: str = "prediction", n_estimators: int = 100,
                   learning_rate: float = 0.1, max_depth: int = 6,
                   subsample: float = 0.8, colsample_bytree: float = 0.8,
                   **kwargs) -> pl.DataFrame:
        """XGBoost prediction"""
        try:
            import xgboost as xgb
            from sklearn.preprocessing import LabelEncoder

            # Validate parameters
            learning_rate = max(0.01, float(learning_rate))
            n_estimators = max(1, int(n_estimators))
            max_depth = max(1, int(max_depth))
            subsample = max(0.1, min(1.0, float(subsample)))
            colsample_bytree = max(0.1, min(1.0, float(colsample_bytree)))

            X = df.select(features).to_pandas()
            y = df[target].to_pandas()

            le = LabelEncoder()
            y_encoded = le.fit_transform(y)

            is_classification = len(le.classes_) <= 10 and y.dtype == 'object'

            if is_classification:
                model = xgb.XGBClassifier(n_estimators=n_estimators, learning_rate=learning_rate,
                                          max_depth=max_depth, subsample=subsample,
                                          colsample_bytree=colsample_bytree, use_label_encoder=False,
                                          eval_metric='logloss')
            else:
                model = xgb.XGBRegressor(n_estimators=n_estimators, learning_rate=learning_rate,
                                         max_depth=max_depth, subsample=subsample,
                                         colsample_bytree=colsample_bytree)

            model.fit(X, y_encoded)
            y_pred = model.predict(X)

            if is_classification:
                y_pred = le.inverse_transform(y_pred.astype(int))

            return df.with_columns(pl.Series(name=output_col, values=y_pred))

        except ImportError:
            raise ImportError("xgboost not installed. Install with: pip install xgboost")
        except Exception as e:
            print(f"XGBoost error: {e}")
            raise

    def ml_lightgbm(self, df: pl.DataFrame, features: List[str], target: str,
                    output_col: str = "prediction", n_estimators: int = 100,
                    learning_rate: float = 0.1, num_leaves: int = 31,
                    min_child_samples: int = 20, **kwargs) -> pl.DataFrame:
        """LightGBM prediction"""
        try:
            import lightgbm as lgb
            from sklearn.preprocessing import LabelEncoder

            # Validate parameters
            learning_rate = max(0.01, float(learning_rate))
            n_estimators = max(1, int(n_estimators))
            num_leaves = max(2, min(200, int(num_leaves)))
            min_child_samples = max(1, int(min_child_samples))

            X = df.select(features).to_pandas()
            y = df[target].to_pandas()

            le = LabelEncoder()
            y_encoded = le.fit_transform(y)

            is_classification = len(le.classes_) <= 10 and y.dtype == 'object'

            if is_classification:
                model = lgb.LGBMClassifier(n_estimators=n_estimators, learning_rate=learning_rate,
                                           num_leaves=num_leaves, min_child_samples=min_child_samples,
                                           verbose=-1)
            else:
                model = lgb.LGBMRegressor(n_estimators=n_estimators, learning_rate=learning_rate,
                                          num_leaves=num_leaves, min_child_samples=min_child_samples,
                                          verbose=-1)

            model.fit(X, y_encoded)
            y_pred = model.predict(X)

            if is_classification:
                y_pred = le.inverse_transform(y_pred.astype(int))

            return df.with_columns(pl.Series(name=output_col, values=y_pred))

        except ImportError:
            raise ImportError("lightgbm not installed. Install with: pip install lightgbm")
        except Exception as e:
            print(f"LightGBM error: {e}")
            raise

    # ============================================================================
    # UNSUPERVISED LEARNING - CLUSTERING
    # ============================================================================

    def ml_dbscan(self, df: pl.DataFrame, features: List[str],
                  output_col: str = "cluster", eps: float = 0.5,
                  min_samples: int = 5, **kwargs) -> pl.DataFrame:
        """DBSCAN clustering"""
        try:
            from sklearn.cluster import DBSCAN
            from sklearn.preprocessing import StandardScaler

            X = df.select(features).to_pandas()

            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Fit DBSCAN
            model = DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(X_scaled)

            return df.with_columns(pl.Series(name=output_col, values=labels))

        except Exception as e:
            print(f"DBSCAN error: {e}")
            raise

    def ml_gmm(self, df: pl.DataFrame, features: List[str],
               output_col: str = "cluster", n_components: int = 3,
               **kwargs) -> pl.DataFrame:
        """Gaussian Mixture Model clustering"""
        try:
            from sklearn.mixture import GaussianMixture
            from sklearn.preprocessing import StandardScaler

            X = df.select(features).to_pandas()

            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Fit GMM
            model = GaussianMixture(n_components=n_components)
            labels = model.fit_predict(X_scaled)

            return df.with_columns(pl.Series(name=output_col, values=labels))

        except Exception as e:
            print(f"GMM error: {e}")
            raise

    # ============================================================================
    # TIME SERIES FORECASTING
    # ============================================================================

    def ml_arima(self, df: pl.DataFrame, column: str, output_col: str = "forecast",
                 order_p: int = 1, order_d: int = 1, order_q: int = 1,
                 steps: int = 12, **kwargs) -> pl.DataFrame:
        """ARIMA time series forecasting - extends dataset with forecast values"""
        try:
            from statsmodels.tsa.arima.model import ARIMA
            import numpy as np

            # Get the time series data - convert to float64
            series = df[column].to_pandas().astype(np.float64)
            n = len(series)

            # Fit ARIMA model
            model = ARIMA(series, order=(order_p, order_d, order_q))
            result = model.fit()

            # Forecast future values
            forecast = result.forecast(steps=steps)

            # Step 1: Add forecast column to original df with NaN values (Float64 type)
            result_df = df.with_columns(pl.lit(np.nan).cast(pl.Float64).alias(output_col))

            # Step 2: Create new rows for forecast period
            new_rows = []
            for val in forecast.values:
                row = {col: None for col in df.columns}
                row[column] = None  # Original value is null for new rows
                row[output_col] = float(val)
                new_rows.append(row)

            # Step 3: Concatenate original df with new rows
            if new_rows:
                new_df = pl.DataFrame(new_rows)
                # Ensure output_col is Float64
                if output_col in new_df.columns:
                    new_df = new_df.with_columns(pl.col(output_col).cast(pl.Float64))
                result_df = pl.concat([result_df, new_df], how="vertical")

            return result_df

        except Exception as e:
            print(f"ARIMA error: {e}")
            raise

    def ml_ets(self, df: pl.DataFrame, column: str, output_col: str = "forecast",
               trend: str = "add", seasonal: str = None, steps: int = 12,
               **kwargs) -> pl.DataFrame:
        """Exponential Smoothing - extends dataset with forecast values"""
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            import numpy as np

            # Get the time series data - convert to float64
            series = df[column].to_pandas().astype(np.float64)
            n = len(series)

            # Determine seasonal periods (if any)
            seasonal_periods = None
            if seasonal:
                seasonal_periods = 12  # Monthly data assumption

            # Fit ETS model
            model = ExponentialSmoothing(
                series,
                trend=trend if trend else None,
                seasonal=seasonal,
                seasonal_periods=seasonal_periods
            )
            result = model.fit()

            # Forecast future values
            forecast = result.forecast(steps=steps)

            # Step 1: Add forecast column to original df with NaN values (Float64 type)
            result_df = df.with_columns(pl.lit(np.nan).cast(pl.Float64).alias(output_col))

            # Step 2: Create new rows for forecast period
            new_rows = []
            for val in forecast.values:
                row = {col: None for col in df.columns}
                row[column] = None
                row[output_col] = float(val)
                new_rows.append(row)

            # Step 3: Concatenate original df with new rows
            if new_rows:
                new_df = pl.DataFrame(new_rows)
                # Ensure output_col is Float64
                if output_col in new_df.columns:
                    new_df = new_df.with_columns(pl.col(output_col).cast(pl.Float64))
                result_df = pl.concat([result_df, new_df], how="vertical")

            return result_df

        except Exception as e:
            print(f"ETS error: {e}")
            raise

    # ============================================================================
    # AUDIT IMPLEMENTATIONS
    # ============================================================================

    def audit_duplicate_detection(self, df: pl.DataFrame, columns: List[str], output_col: str,
                                  flag_col: str, **kwargs) -> pl.DataFrame:
        """Detect duplicate rows based on specified columns"""
        # Create a grouping key
        select_exprs = [pl.col(c).cast(pl.Utf8).str.replace(r"[^\w]", "_", literal=True).alias(c) for c in columns]
        temp_df = df.with_columns(select_exprs)

        # Create group IDs
        group_keys = temp_df.select(columns).with_columns(
            pl.concat_str(columns, separator="_").alias("_group_key")
        )["_group_key"].to_list()

        # Count occurrences
        from collections import Counter
        counts = Counter(group_keys)

        # Assign group IDs and flags
        group_ids = []
        is_duplicates = []
        seen = {}

        for i, key in enumerate(group_keys):
            if key not in seen:
                seen[key] = len(seen)
            group_ids.append(seen[key])
            is_duplicates.append(counts[key] > 1)

        return df.with_columns([
            pl.Series(name=output_col, values=group_ids),
            pl.Series(name=flag_col, values=is_duplicates)
        ])

    def audit_gap_analysis(self, df: pl.DataFrame, id_column: str, output_col: str,
                          missing_count_col: str, **kwargs) -> pl.DataFrame:
        """Detect gaps in sequential ID column"""
        # Sort by ID and detect gaps
        ids = df[id_column].to_numpy()
        is_sorted = np.all(ids[:-1] <= ids[1:])

        if not is_sorted:
            # Sort indices
            sorted_idx = np.argsort(ids)
            ids = ids[sorted_idx]

        # Detect gaps
        is_missing = np.zeros(len(ids), dtype=bool)
        gaps_after = np.zeros(len(ids), dtype=int)

        if len(ids) > 1:
            for i in range(len(ids) - 1):
                expected_diff = ids[i + 1] - ids[i]
                if expected_diff > 1:
                    # Mark current as having gap after
                    is_missing[i] = True
                    gaps_after[i] = expected_diff - 1

        # If not sorted, map back to original order
        if not is_sorted:
            is_missing_orig = np.zeros(len(ids), dtype=bool)
            gaps_after_orig = np.zeros(len(ids), dtype=int)
            for orig_idx, sorted_i in enumerate(sorted_idx):
                is_missing_orig[orig_idx] = is_missing[sorted_i]
                gaps_after_orig[orig_idx] = gaps_after[sorted_i]
            is_missing = is_missing_orig
            gaps_after = gaps_after_orig

        return df.with_columns([
            pl.Series(name=output_col, values=is_missing),
            pl.Series(name=missing_count_col, values=gaps_after)
        ])

    def audit_outlier_detection(self, df: pl.DataFrame, column: str, method: str, output_col: str,
                               deviation_col: str, **kwargs) -> pl.DataFrame:
        """Detect statistical outliers for audit"""
        col_data = df[column].to_numpy()
        is_outlier = np.zeros(len(col_data), dtype=bool)
        deviation = np.zeros(len(col_data))

        if method == "zscore" or method == "mad":
            mean = np.mean(col_data)
            std = np.std(col_data)
            if std == 0:
                std = 1
            zscores = np.abs((col_data - mean) / std)
            deviation = zscores
            is_outlier = zscores > 3.0
        else:  # IQR method
            Q1 = np.percentile(col_data, 25)
            Q3 = np.percentile(col_data, 75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            is_outlier = (col_data < lower) | (col_data > upper)
            deviation = np.where(col_data < lower, lower - col_data, col_data - upper)
            deviation = np.clip(deviation, 0, None)

        return df.with_columns([
            pl.Series(name=output_col, values=is_outlier),
            pl.Series(name=deviation_col, values=deviation)
        ])

    def audit_round_numbers(self, df: pl.DataFrame, column: str, threshold: float, output_col: str,
                           score_col: str, **kwargs) -> pl.DataFrame:
        """Detect unusually round numbers (potential manipulation)"""
        def calc_roundness(val):
            if val is None or val == 0:
                return 0.0
            val = abs(float(val))
            # Calculate ratio of trailing zeros for integers
            log10 = np.log10(val)
            mantissa = 10 ** (log10 - np.floor(log10))
            # Higher score = more round (mantissa close to 1, 10, 100...)
            round_scores = [1.0, 0.1, 0.01, 0.001]
            score = max(1 - min(abs(mantissa - r) for r in round_scores), 0)
            return score

        roundness = [calc_roundness(v) for v in df[column]]
        is_round = [s >= threshold for s in roundness]

        return df.with_columns([
            pl.Series(name=output_col, values=is_round),
            pl.Series(name=score_col, values=roundness)
        ])

    # ============================================================================
    # STATISTICS ADD GROUP IMPLEMENTATIONS
    # ============================================================================

    def stat_add_group_stats(self, df: pl.DataFrame, group_column: str, target_column: str,
                            calculations: List[str], **kwargs) -> pl.DataFrame:
        """Add aggregate statistics as columns per group"""
        result_df = df.clone()

        # Calculate group statistics
        group_stats = df.group_by(group_column).agg([
            pl.col(target_column).mean().alias(f"{target_column}_mean"),
            pl.col(target_column).std().alias(f"{target_column}_std"),
            pl.col(target_column).min().alias(f"{target_column}_min"),
            pl.col(target_column).max().alias(f"{target_column}_max"),
            pl.col(target_column).sum().alias(f"{target_column}_sum"),
            pl.col(target_column).count().alias(f"{target_column}_count"),
        ])

        # Join back to original dataframe
        result_df = result_df.join(group_stats, on=group_column, how="left")

        return result_df

    # ============================================================================
    # COLUMN OPERATION IMPLEMENTATIONS
    # ============================================================================

    def rename_col(self, df: pl.DataFrame, column: str, new_name: str) -> pl.DataFrame:
        """Rename column"""
        return df.rename({column: new_name})

    def change_data_type(self, df: pl.DataFrame, column: str, new_type: str) -> pl.DataFrame:
        """Change column data type"""
        type_map = {
            'Int64': pl.Int64, 'Float64': pl.Float64, 'Utf8': pl.Utf8,
            'Boolean': pl.Boolean, 'Date': pl.Date, 'Datetime': pl.Datetime
        }
        if new_type not in type_map:
            raise ValueError(f"Unsupported type: {new_type}")
        return df.with_columns(pl.col(column).cast(type_map[new_type], strict=False))

    def duplicate_column(self, df: pl.DataFrame, column: str, new_name: str = None) -> pl.DataFrame:
        """Duplicate column"""
        target = new_name or f"{column}_copy"
        return df.with_columns(pl.col(column).alias(target))

    def delete_column(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Delete column"""
        return df.drop(column)

    # ============================================================================
    # SPLIT OPERATION IMPLEMENTATIONS
    # ============================================================================

    def split_column(self, df: pl.DataFrame, column: str, output_cols: List[str], delimiter: str = ',') -> pl.DataFrame:
        """Split column by delimiter"""
        return df.with_columns(
            pl.col(column).str.split(delimiter).list.to_struct(
                fields=output_cols
            )
        ).unnest(column)

    def split_columns_by_delimiter(self, df: pl.DataFrame, column: str, delimiter: str = ' ', custom_delimiter: str = None, max_splits: int = -1, output_prefix: str = None) -> pl.DataFrame:
        """Split column by delimiter into multiple columns"""
        # Map delimiter options to actual characters
        delimiter_map = {
            'space': ' ',
            'comma': ',',
            'tab': '\t',
            'period': '.',
            'asterisk': '*'
        }
        actual_delimiter = delimiter_map.get(delimiter, delimiter)
        if delimiter == 'custom' and custom_delimiter:
            actual_delimiter = custom_delimiter

        # Use provided prefix or default to column name
        prefix = output_prefix or f"{column}_"

        # Determine number of output columns
        if max_splits > 0:
            num_cols = max_splits + 1
        else:
            # Estimate based on first few rows
            sample = df[column].head(10).to_list()
            max_parts = max((str(v).count(actual_delimiter) for v in sample if v), default=0) + 1
            num_cols = min(max(max_parts, 2), 10)  # Between 2 and 10 columns

        output_cols = [f"{prefix}{i+1}" for i in range(num_cols)]

        # Split and create columns
        if max_splits > 0:
            # Limit splits
            result = df.with_columns(
                pl.col(column).str.splitn(actual_delimiter, max_splits + 1).alias("_split_parts")
            )
        else:
            result = df.with_columns(
                pl.col(column).str.split(actual_delimiter).alias("_split_parts")
            )

        # Get actual number of parts for each row
        result = result.with_columns(
            pl.col("_split_parts").list.len().alias("_num_parts")
        )

        # Create output columns, handling varying lengths
        for i in range(num_cols):
            col_name = f"{column}_{i+1}"
            result = result.with_columns(
                pl.when(pl.col("_num_parts") > i)
                .then(pl.col("_split_parts").list.get(i))
                .otherwise(pl.lit(None))
                .alias(col_name)
            )

        # Clean up and return
        return result.drop("_split_parts", "_num_parts")

    def custom_column_from_math(self, df: pl.DataFrame, expression: str, output_column: str = "custom_result", columns: List[str] = None) -> pl.DataFrame:
        """Create custom column using mathematical expression"""
        # For safety, use polars expressions
        try:
            # Replace column names with pl.col() calls
            expr = expression
            for col in columns or []:
                expr = expr.replace(f"col('{col}')", f"pl.col('{col}')")

            # Create the expression
            result_expr = eval(expr)
            return df.with_columns(result_expr.alias(output_column))
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    def calculated_columns(self, df: pl.DataFrame, formula: str, output_column: str, formula_type: str = "arithmetic") -> pl.DataFrame:
        """Create calculated column using formula"""
        try:
            return df.with_columns(eval(formula).alias(output_column))
        except Exception as e:
            raise ValueError(f"Invalid formula: {e}")

    def choose_columns(self, df: pl.DataFrame, action: str, columns_to_keep: List[str] = None, columns_to_remove: List[str] = None, column_order: List[str] = None) -> pl.DataFrame:
        """Select, remove, or reorder columns"""
        if action == "keep":
            if columns_to_keep:
                return df.select(columns_to_keep)
        elif action == "remove":
            if columns_to_remove:
                return df.drop(columns_to_remove)
        elif action == "reorder":
            if column_order:
                return df.select(column_order)
        return df

    def change_data_type_extended(self, df: pl.DataFrame, column: str, new_dtype: str, format_string: str = None) -> pl.DataFrame:
        """Change column data type with extended type support"""
        dtype_map = {
            "Int8": pl.Int8, "Int16": pl.Int16, "Int32": pl.Int32, "Int64": pl.Int64,
            "Float32": pl.Float32, "Float64": pl.Float64,
            "Utf8": pl.Utf8, "Boolean": pl.Boolean,
            "Date": pl.Date, "Datetime": pl.Datetime, "Categorical": pl.Categorical
        }
        target_type = dtype_map.get(new_dtype)
        if not target_type:
            raise ValueError(f"Unsupported data type: {new_dtype}")

        if new_dtype in ["Date", "Datetime"] and format_string:
            return df.with_columns(
                pl.col(column).str.to_date(format_string) if new_dtype == "Date"
                else pl.col(column).str.to_datetime(format_string)
            )
        return df.with_columns(pl.col(column).cast(target_type))

    def rename_columns_bulk(self, df: pl.DataFrame, renames: List[dict] = None, prefix: str = None, suffix: str = None, lowercase: bool = False, uppercase: bool = False) -> pl.DataFrame:
        """Bulk rename columns"""
        result_df = df.clone()

        # Apply individual renames
        if renames:
            rename_map = {r["old_name"]: r["new_name"] for r in renames}
            result_df = result_df.rename(rename_map)

        # Apply prefix/suffix
        if prefix or suffix:
            new_cols = {}
            for col in result_df.columns:
                new_name = ""
                if prefix:
                    new_name += prefix
                new_name += col
                if suffix:
                    new_name += suffix
                new_cols[col] = new_name
            result_df = result_df.rename(new_cols)

        # Apply case conversion
        if lowercase:
            new_cols = {col: col.lower() for col in result_df.columns}
            result_df = result_df.rename(new_cols)
        elif uppercase:
            new_cols = {col: col.upper() for col in result_df.columns}
            result_df = result_df.rename(new_cols)

        return result_df

    def split_alphanumeric(self, df: pl.DataFrame, column: str, output_text: str = None, output_number: str = None) -> pl.DataFrame:
        """Split alphanumeric values into text and numeric parts"""
        output_text = output_text or f"{column}_text"
        output_number = output_number or f"{column}_number"

        return df.with_columns(
            pl.col(column).str.extract(r"^([a-zA-Z\s]*)", group=1).alias(output_text),
            pl.col(column).str.extract(r"(\d+\.?\d*)$", group=1).alias(output_number)
        )

    def transpose_table(self, df: pl.DataFrame, columns_to_transpose: List[str], include_index: bool = True, index_column: str = "index") -> pl.DataFrame:
        """Transpose rows to columns"""
        if include_index:
            return df.select(columns_to_transpose).transpose(
                include_header=True,
                header_name=index_column
            )
        return df.select(columns_to_transpose).transpose(include_header=False)

    def promote_row_as_header(self, df: pl.DataFrame, row_index: int = 0) -> pl.DataFrame:
        """
        Promote a specific row to become the column headers.

        Args:
            df: Input DataFrame
            row_index: The 0-based index of the row to use as headers

        Returns:
            DataFrame with the specified row as column names
        """
        if row_index >= len(df):
            raise ValueError(f"Row index {row_index} is out of range (dataframe has {len(df)} rows)")

        # Get the row to use as header
        row = df.row(row_index)
        new_headers = []
        seen = {}
        for i, h in enumerate(row):
            h_str = str(h).strip() if h is not None else f"col_{i}"
            # Handle duplicates by appending a suffix
            if h_str in seen:
                seen[h_str] += 1
                h_str = f"{h_str}_{seen[h_str]}"
            else:
                seen[h_str] = 0
            new_headers.append(h_str)

        # Remove the header row and return with new column names
        return df[row_index+1:].rename(dict(zip(df.columns, new_headers)))

    def remove_rows(self, df: pl.DataFrame, row_indices: List[int], remove: bool = True) -> pl.DataFrame:
        """
        Remove or keep specific rows by index.

        Args:
            df: Input DataFrame
            row_indices: List of row indices to remove or keep
            remove: If True, remove the specified rows. If False, keep only the specified rows.

        Returns:
            DataFrame with rows removed or filtered
        """
        if not row_indices:
            return df

        # Convert to set for fast lookup
        indices_set = set(row_indices)

        # Get all valid indices
        all_indices = set(range(len(df)))

        if remove:
            # Remove specified indices
            keep_indices = all_indices - indices_set
        else:
            # Keep only specified indices
            keep_indices = indices_set

        # Filter dataframe
        if not keep_indices:
            return df.clear()

        # Use lazy evaluation for better performance
        return df.filter(pl.int_range(0, len(df)).is_in(list(keep_indices)))

    def filter_rows_by_value(self, df: pl.DataFrame, column: str, operator: str, value: Any) -> pl.DataFrame:
        """
        Filter rows based on a column value.

        Args:
            df: Input DataFrame
            column: Column to filter on
            operator: One of '==', '!=', '>', '<', '>=', '<=', 'contains', 'starts_with', 'ends_with'
            value: Value to compare against

        Returns:
            Filtered DataFrame
        """
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in dataframe")

        col = pl.col(column)

        # Handle different operators
        if operator == "==":
            expr = col == value
        elif operator == "!=":
            expr = col != value
        elif operator == ">":
            expr = col > value
        elif operator == "<":
            expr = col < value
        elif operator == ">=":
            expr = col >= value
        elif operator == "<=":
            expr = col <= value
        elif operator == "contains":
            expr = col.str.contains(value, literal=False)
        elif operator == "starts_with":
            expr = col.str.starts_with(value)
        elif operator == "ends_with":
            expr = col.str.ends_with(value)
        elif operator == "is_null":
            expr = col.is_null()
        elif operator == "is_not_null":
            expr = col.is_not_null()
        else:
            raise ValueError(f"Unknown operator: {operator}")

        return df.filter(expr)

    def join_datasets(self, left_df: pl.DataFrame, right_df: pl.DataFrame, left_key: str, right_key: str, join_type: str = "left", suffix: str = "_right") -> pl.DataFrame:
        """Join two datasets by a key column"""
        if left_df is None:
            raise ValueError("Left dataframe is None")
        if right_df is None:
            raise ValueError("Right dataframe is None")

        # Map join type to polars join strategy
        join_map = {
            "left": "left",
            "right": "outer",
            "inner": "inner",
            "outer": "outer",
            "cross": "cross"
        }

        strategy = join_map.get(join_type, "left")

        # Perform the join
        if strategy == "left":
            return left_df.join(right_df, left_on=left_key, right_on=right_key, how=strategy, suffix=suffix)
        elif strategy == "right":
            return left_df.join(right_df, left_on=left_key, right_on=right_key, how="outer", suffix=suffix)
        elif strategy == "inner":
            return left_df.join(right_df, left_on=left_key, right_on=right_key, how=strategy, suffix=suffix)
        elif strategy == "outer":
            return left_df.join(right_df, left_on=left_key, right_on=right_key, how=strategy, suffix=suffix)
        elif strategy == "cross":
            return left_df.join(right_df, how=strategy, suffix=suffix)

        return left_df

    def append_datasets(self, dataframes: List[pl.DataFrame], align_columns: bool = True, fill_missing: bool = True) -> pl.DataFrame:
        """Append/stack multiple datasets vertically"""
        if not dataframes:
            raise ValueError("No dataframes provided")

        if len(dataframes) == 1:
            return dataframes[0].clone()

        # Clone all dataframes first to avoid modifying originals
        clones = [df.clone() for df in dataframes]

        if align_columns:
            # Get all unique columns from all dataframes
            all_cols_set = set()
            for df in clones:
                all_cols_set.update(df.columns)
            # Sort columns for consistent ordering
            all_cols = sorted(all_cols_set)

            # Determine target dtype for each column (use first dataframe's dtype)
            column_dtypes = {}
            for col in all_cols:
                for df in clones:
                    if col in df.columns:
                        column_dtypes[col] = df[col].dtype
                        break
                if col not in column_dtypes:
                    column_dtypes[col] = pl.String

            # For each dataframe, add missing columns and cast to match target dtypes
            for i, df in enumerate(clones):
                new_cols = []
                for col in all_cols:
                    if col not in df.columns:
                        # Add missing column with nulls of correct dtype
                        new_cols.append(pl.lit(None, dtype=column_dtypes[col]).alias(col))
                    else:
                        # Cast existing column to target dtype
                        target_dtype = column_dtypes[col]
                        if df[col].dtype != target_dtype:
                            try:
                                new_cols.append(pl.col(col).cast(target_dtype))
                            except:
                                # If cast fails, use null column
                                new_cols.append(pl.lit(None, dtype=target_dtype).alias(col))
                        else:
                            new_cols.append(pl.col(col))
                # Add all new columns at once
                df = df.with_columns(new_cols)
                # Select columns in the same order for all dataframes
                df = df.select(all_cols)
                clones[i] = df

        # Use polars vstack which requires matching schemas
        result = clones[0]
        for df in clones[1:]:
            result = result.vstack(df, in_place=False)

        return result

    def split_sheet(self, df: pl.DataFrame, column: str) -> List[tuple]:
        """
        Split a dataframe into multiple dataframes based on unique values in a column.

        Args:
            df: The source Polars DataFrame
            column: The column name to split by

        Returns:
            List of tuples: [(dataset_name, dataframe), ...]
        """
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in dataframe")

        # Get unique values and sort them
        unique_values = df[column].unique().to_list()
        unique_values.sort()

        result = []
        for value in unique_values:
            # Filter dataframe for this value
            filtered_df = df.filter(pl.col(column) == value)
            # Create dataset name (sanitize the value for use as name)
            safe_name = str(value).strip()
            result.append((safe_name, filtered_df))

        return result

    def group_summary(self, df: pl.DataFrame, group_columns: List[str], value_column: str, aggregations: List[str] = None) -> pl.DataFrame:
        """Create group summary with aggregations"""
        agg_map = {
            "sum": pl.sum, "mean": pl.mean, "count": pl.count,
            "min": pl.min, "max": pl.max, "std": pl.std,
            "median": pl.median, "first": pl.first, "last": pl.last
        }

        aggs = []
        for agg in aggregations or ["sum", "count"]:
            if agg in agg_map:
                aggs.append(agg_map[agg](value_column).alias(f"{value_column}_{agg}"))

        return df.group_by(group_columns).agg(*aggs)

    def stratification(self, df: pl.DataFrame, column: str, strata: List[float], value_column: str = None, include_counts: bool = True) -> pl.DataFrame:
        """Create stratified summary by value ranges"""
        # Create strata labels
        labels = []
        for i in range(len(strata) - 1):
            labels.append(f"{strata[i]}-{strata[i+1]}")

        # Create strata column
        result = df.with_columns(
            pl.cut(pl.col(column), bins=strata, labels=labels).alias("_stratum")
        )

        # Create summary
        if value_column:
            agg_map = {"sum": pl.sum, "mean": pl.mean, "count": pl.count, "min": pl.min, "max": pl.max}
            aggs = [agg_map["sum"](value_column).alias(f"{value_column}_sum") for _ in [1]] if "sum" in agg_map else []

            return result.group_by("_stratum").agg(
                pl.col(value_column).sum().alias(f"{value_column}_sum"),
                pl.col(value_column).mean().alias(f"{value_column}_mean"),
                pl.col(value_column).count().alias("count")
            )
        return result.group_by("_stratum").agg(pl.count().alias("count"))

    def cross_tabulation(self, df: pl.DataFrame, rows: str, columns: str, values: str = None, agg_function: str = "count", show_percentages: bool = False, percentages_by: str = "total") -> pl.DataFrame:
        """Create cross-tabulation (contingency table)"""
        if values:
            agg_map = {"sum": "sum", "mean": "mean", "min": "min", "max": "max", "count": "count"}
            agg = agg_map.get(agg_function, "count")
            result = df.pivot(values=values, index=rows, columns=columns, aggregate_function=agg)
        else:
            result = df.pivot(index=rows, columns=columns, aggregate_function="count")

        if show_percentages:
            # Calculate percentages based on totals
            for col in result.columns:
                if col != rows:
                    total = result[col].sum()
                    result = result.with_columns(
                        (pl.col(col) / total * 100).alias(f"{col}_pct")
                    )

        return result

    def trend_analysis(self, df: pl.DataFrame, date_column: str, value_column: str, period: str = "month", aggregations: List[str] = None, include_trendline: bool = False, trend_type: str = "linear") -> pl.DataFrame:
        """Create time-based trend analysis"""
        period_map = {"day": "day", "week": "week", "month": "month", "quarter": "quarter", "year": "year"}

        # Group by period
        grouper = getattr(pl.col(date_column).dt, period_map.get(period, "month"))

        agg_map = {"sum": pl.sum, "mean": pl.mean, "count": pl.count, "min": pl.min, "max": pl.max}
        aggs = [agg_map.get(a, pl.sum)(value_column).alias(f"{value_column}_{a}") for a in (aggregations or ["sum", "mean"])]

        result = df.group_by(grouper.alias("_period")).agg(*aggs).sort("_period")

        if include_trendline:
            # Simple linear trend calculation
            result = result.with_columns(
                (pl.col(f"{value_column}_{aggregations[0] if aggregations else 'sum'}").rank() * 0.1).alias("trend_value")
            )

        return result.rename({"_period": date_column})

    def top_bottom_items(self, df: pl.DataFrame, column: str, value_column: str, n: int, rank_type: str = "top", tie_break: str = "keep_all") -> pl.DataFrame:
        """Get top or bottom N items"""
        sorted_df = df.sort(value_column, descending=(rank_type == "top"))

        if tie_break == "keep_all":
            # Get all items that would be in top N (including ties)
            if rank_type == "top":
                threshold = sorted_df[value_column][min(n-1, len(sorted_df)-1)] if n <= len(sorted_df) else sorted_df[value_column][-1]
                return sorted_df.filter(pl.col(value_column) >= threshold)
            else:
                threshold = sorted_df[value_column][min(n-1, len(sorted_df)-1)] if n <= len(sorted_df) else sorted_df[value_column][-1]
                return sorted_df.filter(pl.col(value_column) <= threshold)
        else:
            return sorted_df.head(n)

    def sampling(self, df: pl.DataFrame, method: str = "random", sample_size: int = None, percentage: float = None, stratify_column: str = None, random_seed: int = None, output_type: str = "sample_view") -> pl.DataFrame:
        """Create sample of data"""
        import numpy as np

        n = sample_size or int(len(df) * (percentage or 10) / 100)

        if method == "random":
            if random_seed:
                np.random.seed(random_seed)
            indices = np.random.choice(len(df), size=min(n, len(df)), replace=False)
            return df[indices]

        elif method == "stratified":
            if stratify_column:
                # Sample proportionally from each stratum
                strata = df.group_by(stratify_column).agg(pl.col(0).count().alias("count"))
                total = strata["count"].sum()
                samples = []
                for _, row in strata.iterrows():
                    stratum_size = int(n * row["count"] / total) or 1
                    stratum_df = df.filter(pl.col(stratify_column) == row[stratify_column])
                    if random_seed:
                        np.random.seed(random_seed + row["count"])
                    indices = np.random.choice(len(stratum_df), size=min(stratum_size, len(stratum_df)), replace=False)
                    samples.append(stratum_df[indices])
                return pl.concat(samples) if samples else df.head(0)

        elif method == "systematic":
            step = max(1, len(df) // n)
            start = np.random.randint(0, step) if random_seed else 0
            return df[start::step]

        elif method == "cluster":
            # Simple cluster sampling - sample every kth group
            if stratify_column:
                unique_vals = df[stratify_column].unique().to_list()
                n_clusters = max(1, len(unique_vals) // 4)
                selected = np.random.choice(unique_vals, size=n_clusters, replace=False) if random_seed is None else unique_vals[:n_clusters]
                return df.filter(pl.col(stratify_column).is_in(selected))

        return df.head(n)

    # ============================================================================
    # PIVOT/UNPIVOT IMPLEMENTATIONS
    # ============================================================================

    def pivot(self, df: pl.DataFrame, index: List[str], columns: str, values: str, aggregate: str = 'first') -> pl.DataFrame:
        """Create pivot table"""
        agg_map = {
            'sum': 'sum', 'mean': 'mean', 'min': 'min', 'max': 'max',
            'count': 'count', 'first': 'first', 'last': 'last'
        }
        agg_func = agg_map.get(aggregate, 'first')
        return df.pivot(values=values, index=index, columns=columns, aggregate_function=agg_func)

    def unpivot(self, df: pl.DataFrame, id_vars: List[str], value_vars: List[str] = None, var_name: str = "variable", value_name: str = "value") -> pl.DataFrame:
        """Unpivot (melt) a DataFrame."""
        if value_vars is None:
            value_vars = [c for c in df.columns if c not in id_vars]
        return df.melt(id_vars=id_vars, value_vars=value_vars, variable_name=var_name, value_name=value_name)

    # ============================================================================
    # FILTER/SORT IMPLEMENTATIONS
    # ============================================================================

    def filter_rows(self, df: pl.DataFrame, column: str, operator: str, value: Any) -> pl.DataFrame:
        """Filter rows based on column value"""
        if operator == '==':
            return df.filter(pl.col(column) == value)
        elif operator == '!=':
            return df.filter(pl.col(column) != value)
        elif operator == '>':
            return df.filter(pl.col(column) > value)
        elif operator == '>=':
            return df.filter(pl.col(column) >= value)
        elif operator == '<':
            return df.filter(pl.col(column) < value)
        elif operator == '<=':
            return df.filter(pl.col(column) <= value)
        elif operator == 'contains':
            return df.filter(pl.col(column).str.contains(str(value)))
        elif operator == 'starts_with':
            return df.filter(pl.col(column).str.starts_with(str(value)))
        elif operator == 'ends_with':
            return df.filter(pl.col(column).str.ends_with(str(value)))
        elif operator == 'is_null':
            return df.filter(pl.col(column).is_null())
        elif operator == 'is_not_null':
            return df.filter(pl.col(column).is_not_null())
        elif operator == 'in':
            return df.filter(pl.col(column).is_in(value))
        else:
            raise ValueError(f"Unsupported operator: {operator}")

    def sort_rows(self, df: pl.DataFrame, column: str, ascending: bool = True) -> pl.DataFrame:
        """Sort rows by column"""
        return df.sort(column, descending=not ascending)



    # =========================================================================
    # TEXT EXTRACTION OPERATIONS (Excel LEFT/RIGHT/MID style)
    # =========================================================================

    def extract_first_chars(self, df: pl.DataFrame, column: str, num_chars: int = 1, output_col: str = None) -> pl.DataFrame:
        """Extract first N characters from text (Excel LEFT function)"""
        output_col = output_col or f"{column}_left"
        return df.with_columns(
            pl.col(column).str.slice(offset=0, length=num_chars).alias(output_col)
        )

    def extract_last_chars(self, df: pl.DataFrame, column: str, num_chars: int = 1, output_col: str = None) -> pl.DataFrame:
        """Extract last N characters from text (Excel RIGHT function)"""
        output_col = output_col or f"{column}_right"
        return df.with_columns(
            pl.col(column).str.slice(offset=-num_chars).alias(output_col)
        )

    def extract_middle_chars(self, df: pl.DataFrame, column: str, start_pos: int = 1, num_chars: int = 1, output_col: str = None) -> pl.DataFrame:
        """Extract characters from the middle of text (Excel MID function)"""
        output_col = output_col or f"{column}_mid"
        offset = max(0, start_pos - 1)
        return df.with_columns(
            pl.col(column).str.slice(offset=offset, length=num_chars).alias(output_col)
        )

    # =========================================================================
    # MATH OPERATIONS - MODULO & POWER
    # =========================================================================

    def modulo(self, df: pl.DataFrame, column: str, divisor: int, output_col: str = None) -> pl.DataFrame:
        """Calculate remainder after division"""
        output_col = output_col or f"{column}_mod"
        col_dtype = df[column].dtype

        # Check if column is date/datetime type - modulo not applicable
        if col_dtype in [pl.Date, pl.Datetime]:
            # Return original column with warning indicator
            return df.with_columns(
                pl.lit(None, dtype=pl.Int64).alias(output_col)
            )

        return df.with_columns(
            (pl.col(column) % divisor).alias(output_col)
        )

    def power(self, df: pl.DataFrame, column: str, exponent: int, output_col: str = None) -> pl.DataFrame:
        """Raise value to a specified power"""
        output_col = output_col or f"{column}_power"
        return df.with_columns(
            (pl.col(column) ** exponent).alias(output_col)
        )

    # =========================================================================
    # PREFIX/SUFFIX OPERATIONS
    # =========================================================================

    def add_prefix(self, df: pl.DataFrame, column: str, prefix: str, output_col: str = None) -> pl.DataFrame:
        """Add prefix to text"""
        output_col = output_col or f"{column}_prefixed"
        return df.with_columns(
            (pl.lit(prefix) + pl.col(column)).alias(output_col)
        )

    def add_suffix(self, df: pl.DataFrame, column: str, suffix: str, output_col: str = None) -> pl.DataFrame:
        """Add suffix to text"""
        output_col = output_col or f"{column}_suffixed"
        return df.with_columns(
            (pl.col(column) + pl.lit(suffix)).alias(output_col)
        )

    # =========================================================================
    # REPLACE VALUES OPERATION
    # =========================================================================

    def replace_values(self, df: pl.DataFrame, column: str, find_value: str, replace_value: str,
                       case_sensitive: bool = True, output_col: str = None) -> pl.DataFrame:
        """Find and replace values in a column"""
        output_col = output_col or f"{column}_replaced"
        if case_sensitive:
            return df.with_columns(
                pl.col(column).str.replace(find_value, replace_value).alias(output_col)
            )
        else:
            return df.with_columns(
                pl.col(column).str.replace(find_value, replace_value, literal=False).alias(output_col)
            )

    # =========================================================================
    # STANDARDIZATION OPERATIONS
    # =========================================================================

    def minmax_normalize(self, df: pl.DataFrame, column: str, output_col: str = None) -> pl.DataFrame:
        """Scale values to range 0-1 using min-max normalization"""
        output_col = output_col or f"{column}_minmax"
        col_min = df[column].min()
        col_max = df[column].max()
        col_range = col_max - col_min
        if col_range == 0:
            return df.with_columns(
                pl.lit(0.5).alias(output_col)
            )
        return df.with_columns(
            ((pl.col(column) - col_min) / col_range).alias(output_col)
        )
class TransformationStep:
    """Represents a single transformation step in the pipeline."""

    def __init__(self, operation_id: str, params: Dict[str, Any], step_number: int):
        self.operation_id = operation_id
        self.params = params
        self.step_number = step_number
        self.created_columns: List[str] = []
        self.timestamp = datetime.now()


class TransformationPipeline:
    """
    Manages a sequence of transformation steps to be applied to a DataFrame.
    This is a stateful object that holds the original data and the list of steps.
    Tracks created columns and maintains intermediate datasets for inspection.
    """

    def __init__(self, initial_df: pl.DataFrame):
        self.original_df = initial_df
        self.steps: List[TransformationStep] = []
        self._data_processor = DataProcessor()
        self._cache: Dict[int, pl.DataFrame] = {0: initial_df}
        self._column_tracking: Dict[str, Dict] = {}  # column_name -> {'created_by_step': int, 'operation': str}

    def add_step(self, operation_id: str, params: Dict[str, Any]) -> List[str]:
        """
        Adds a new transformation step to the pipeline.

        Args:
            operation_id: The ID of the operation to perform.
            params: The parameters for the operation.

        Returns:
            List of column names created by this step.
        """
        if operation_id not in OPERATION_REGISTRY:
            raise ValueError(f"Operation '{operation_id}' not found in the registry.")

        step_number = len(self.steps) + 1
        step = TransformationStep(operation_id, params, step_number)
        self.steps.append(step)

        # Apply the operation to detect created columns
        current_df = self.apply(to_step=step_number)
        created_columns = self._detect_created_columns(step_number - 1, step_number)

        # Update step with created columns
        step.created_columns = created_columns

        # Track column creation
        for col in created_columns:
            self._column_tracking[col] = {
                'created_by_step': step_number,
                'operation': operation_id,
                'params': params.copy()
            }

        # Clear cache from this point forward
        self._cache = {k: v for k, v in self._cache.items() if k <= step_number}

        return created_columns

    def _detect_created_columns(self, from_step: int, to_step: int) -> List[str]:
        """
        Detect which columns were created between two pipeline steps.

        Args:
            from_step: The step number before the operation (0-based).
            to_step: The step number after the operation (0-based).

        Returns:
            List of newly created column names.
        """
        df_before = self.apply(to_step=from_step)
        df_after = self.apply(to_step=to_step)

        columns_before = set(df_before.columns)
        columns_after = set(df_after.columns)

        return list(columns_after - columns_before)

    def apply(self, to_step: Optional[int] = None) -> pl.DataFrame:
        """
        Applies the transformations in the pipeline sequentially.

        Args:
            to_step: If specified, applies transformations up to and including
                      this step number (1-based). If None, applies all steps.

        Returns:
            The transformed Polars DataFrame.
        """
        target_step_idx = len(self.steps) if to_step is None else to_step

        if target_step_idx in self._cache:
            return self._cache[target_step_idx]

        # Find the latest cached step before the target
        start_step_idx = max([k for k in self._cache.keys() if k < target_step_idx], default=0)
        current_df = self._cache[start_step_idx]

        # Apply steps from the cached point up to the target
        for i in range(start_step_idx, target_step_idx):
            step = self.steps[i]
            current_df = self._data_processor.apply_operation(
                current_df,
                step.operation_id,
                step.params
            )
            # Cache the result of this step
            self._cache[i + 1] = current_df

        return current_df

    def get_steps(self) -> List[TransformationStep]:
        """Returns the list of applied steps."""
        return self.steps

    def get_dataframe_at_step(self, step_num: int) -> pl.DataFrame:
        """
        Returns the state of the DataFrame at a specific step in the pipeline.

        Args:
            step_num: The step number (0 for original data, 1 for after first step, etc.).

        Returns:
            The DataFrame at the specified step.
        """
        if step_num < 0 or step_num > len(self.steps):
            raise IndexError("Step number is out of range.")

        return self.apply(to_step=step_num)

    def get_column_info(self, column_name: str) -> Optional[Dict]:
        """
        Get information about when and how a column was created.

        Args:
            column_name: Name of the column to query.

        Returns:
            Dictionary with creation info or None if column is original.
        """
        return self._column_tracking.get(column_name)

    def get_created_columns_at_step(self, step_num: int) -> List[str]:
        """
        Get the list of columns created at a specific step.

        Args:
            step_num: The step number (1-based).

        Returns:
            List of column names created at that step.
        """
        if 1 <= step_num <= len(self.steps):
            return self.steps[step_num - 1].created_columns
        return []

    def get_all_created_columns(self) -> Dict[int, List[str]]:
        """
        Get all columns created in the pipeline, organized by step.

        Returns:
            Dictionary mapping step numbers to lists of created column names.
        """
        return {step.step_number: step.created_columns for step in self.steps}

    def remove_last_step(self):
        """Removes the last transformation step."""
        if self.steps:
            removed_step = self.steps.pop()
            # Remove column tracking for columns created by this step
            for col in removed_step.created_columns:
                self._column_tracking.pop(col, None)
            # Clear cache from this point forward
            self._cache = {k: v for k, v in self._cache.items() if k <= len(self.steps)}

    def clear_steps(self):
        """Removes all transformation steps."""
        self.steps.clear()
        self._column_tracking.clear()
        self._cache = {0: self.original_df}


# ============================================================================
# LEGACY DATA PROCESSOR - All transformation methods
# ============================================================================

class LegacyDataProcessor:
    """Process and transform data using Polars for high performance"""

    def __init__(self, data_dir: str = None):
        """Initialize data processor with data directory"""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    # =========================================================================
    # FILE I/O METHODS
    # =========================================================================

    def read_file(self, file_path: str, sheet_name: str = None) -> pl.DataFrame:
        """Read various file formats using Polars"""
        file_path_obj = Path(file_path)
        file_extension = file_path_obj.suffix.lower()

        if file_extension == '.csv':
            return pl.read_csv(file_path_obj)
        elif file_extension in ['.xlsx', '.xls']:
            import io
            # Read file into memory to avoid path-handling issues in lower-level engines
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            df = None
            try:
                # Try Polars with default engine first
                if sheet_name:
                    df = pl.read_excel(io.BytesIO(file_content), sheet_name=sheet_name)
                else:
                    df = pl.read_excel(io.BytesIO(file_content))
                
                if df is not None and len(df.columns) == 0:
                    df = None
            except Exception:
                df = None
            
            if df is None:
                import pandas as pd
                # Use xlrd for .xls files (xlrd 2+ doesn't support .xls)
                if file_extension == '.xls':
                    try:
                        import xlrd
                        # xlrd 1.x works directly with file path
                        wb = xlrd.open_workbook(file_path)
                        sheet_names = wb.sheet_names()

                        # Determine which sheet to read
                        if sheet_name and sheet_name in sheet_names:
                            sheet_idx = sheet_names.index(sheet_name)
                        else:
                            sheet_idx = 0

                        sheet = wb.sheet_by_index(sheet_idx)

                        # Convert xlrd sheet to pandas DataFrame
                        data = []
                        for row_idx in range(sheet.nrows):
                            row_data = []
                            for col_idx in range(sheet.ncols):
                                cell = sheet.cell(row_idx, col_idx)
                                cell_value = cell.value
                                # Convert xlrd cell types to Python types
                                if cell.ctype == xlrd.XL_CELL_EMPTY:
                                    cell_value = None
                                elif cell.ctype == xlrd.XL_CELL_NUMBER:
                                    # Convert to int if whole number, else keep as float
                                    if cell_value == int(cell_value):
                                        cell_value = int(cell_value)
                                    cell_value = str(cell_value)
                                elif cell.ctype == xlrd.XL_CELL_DATE:
                                    # Convert Excel date to Python datetime
                                    try:
                                        date_tuple = xlrd.xldate_as_tuple(cell_value, wb.datemode)
                                        cell_value = datetime.date(date_tuple[0], date_tuple[1], date_tuple[2]).isoformat()
                                    except:
                                        cell_value = str(cell_value)
                                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                                    cell_value = bool(cell_value)
                                else:
                                    cell_value = str(cell_value) if cell_value else None
                                row_data.append(cell_value)
                            data.append(row_data)

                        # Get column names from first row if available
                        # Generate unique column names if first row has duplicates/empty values
                        if sheet.nrows > 0:
                            columns = data[0].copy()
                            # Check if columns are valid (unique, non-empty strings)
                            has_issues = False
                            seen = set()
                            for col in columns:
                                if not isinstance(col, str) or not col.strip() or col in seen:
                                    has_issues = True
                                    break
                                seen.add(col)

                            if has_issues or len(data) <= 1:
                                # Generate generic column names
                                columns = [f'Column_{i+1}' for i in range(sheet.ncols)]
                                df_pandas = pd.DataFrame(data, columns=columns)
                            else:
                                df_pandas = pd.DataFrame(data[1:], columns=columns)
                        else:
                            df_pandas = pd.DataFrame()
                    except Exception as e:
                        raise ValueError(f"Failed to read .xls file: {str(e)}")
                else:
                    # openpyxl for .xlsx
                    try:
                        df_pandas = pd.read_excel(
                            io.BytesIO(file_content),
                            sheet_name=sheet_name,
                            engine='openpyxl'
                        )
                    except Exception as e:
                        raise ValueError(f"Failed to read .xlsx file with openpyxl: {str(e)}")

                return pl.from_pandas(df_pandas)
            return df
        elif file_extension == '.json':
            return pl.read_json(file_path)
        elif file_extension == '.parquet':
            return pl.read_parquet(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

    def get_excel_sheets(self, file_path: str) -> List[str]:
        """Get list of available sheets in Excel file"""
        try:
            # Use xlrd for .xls files (xlrd 2+ doesn't support .xls)
            if file_path.endswith('.xls'):
                import xlrd
                wb = xlrd.open_workbook(file_path)
                return wb.sheet_names()
            else:
                # openpyxl for .xlsx files
                import pandas as pd
                import io
                with open(file_path, 'rb') as f:
                    file_content = f.read()
                excel_file = pd.ExcelFile(io.BytesIO(file_content), engine='openpyxl')
                return excel_file.sheet_names
        except Exception as e:
            raise ValueError(f"Error reading Excel file: {str(e)}")

    def save_dataset(self, df: pl.DataFrame, filename: str, format: str = 'parquet') -> str:
        """Save dataset to file"""
        file_path = self.data_dir / f"{filename}.{format}"

        if format == 'parquet':
            df.write_parquet(str(file_path))
        elif format == 'csv':
            df.write_csv(str(file_path))
        elif format == 'xlsx':
            import pandas as pd
            df_pandas = df.to_pandas()
            df_pandas.to_excel(str(file_path), index=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        return str(file_path)

    # =========================================================================
    # DATA PROFILING
    # =========================================================================

    def profile_data(self, df: pl.DataFrame) -> List[Dict[str, Any]]:
        """Generate comprehensive data profile for each column"""
        profiles = []

        for column in df.columns:
            col_data = df[column]

            profile = {
                'column_name': column,
                'data_type': str(col_data.dtype),
                'null_count': col_data.null_count(),
                'unique_count': col_data.n_unique(),
                'min_value': None,
                'max_value': None,
                'mean_value': None,
                'std_dev': None
            }

            # Calculate numeric statistics if applicable
            if col_data.dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32, pl.Int16, pl.Int8, pl.UInt64, pl.UInt32, pl.UInt16, pl.UInt8]:
                try:
                    profile['min_value'] = col_data.min()
                    profile['max_value'] = col_data.max()
                    profile['mean_value'] = col_data.mean()
                    profile['std_dev'] = col_data.std()
                except Exception:
                    pass

            profiles.append(profile)

        return profiles

    # =========================================================================
    # TEXT TRANSFORMATIONS
    # =========================================================================

    def text_uppercase(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Convert text to uppercase"""
        return df.with_columns(pl.col(column).str.to_uppercase().alias(f"{column}_upper"))

    def text_lowercase(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Convert text to lowercase"""
        return df.with_columns(pl.col(column).str.to_lowercase().alias(f"{column}_lower"))

    def text_titlecase(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Convert text to title case"""
        return df.with_columns(pl.col(column).str.to_titlecase().alias(f"{column}_title"))

    def text_trim(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Remove leading/trailing whitespace"""
        return df.with_columns(pl.col(column).str.strip_chars().alias(f"{column}_trimmed"))

    def text_extract_numbers(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract numbers from text"""
        return df.with_columns(
            pl.col(column).str.extract_all(r"\d+").list.join("").alias(f"{column}_numbers")
        )

    def text_extract_text(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract alphabetic text"""
        return df.with_columns(
            pl.col(column).str.replace_all(r"\d+", "", literal=True).str.strip_chars().alias(f"{column}_text")
        )

    def text_reverse(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Reverse text string"""
        return df.with_columns(
            pl.col(column).str.reverse().alias(f"{column}_reversed")
        )

    def text_length(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Get text length"""
        return df.with_columns(pl.col(column).str.len_bytes().alias(f"{column}_length"))

    def text_hash_md5(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Create MD5 hash"""
        return df.with_columns(
            pl.col(column).map_elements(
                lambda x: hashlib.md5(str(x).encode()).hexdigest() if x is not None else None,
                return_dtype=pl.Utf8
            ).alias(f"{column}_md5")
        )

    def text_soundex(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Create Soundex code"""
        def soundex(word):
            if not word:
                return "0000"
            word = word.upper()[:4]
            mapping = {"BFPV": "1", "CGJKQSXZ": "2", "DT": "3", "L": "4", "MN": "5", "R": "6"}
            result = [word[0]]
            prev = ""
            for char in word[1:]:
                for letters, code in mapping.items():
                    if char in letters and code != prev:
                        result.append(code)
                        prev = code
                        break
            return (''.join(result) + "000")[:4]

        return df.with_columns(
            pl.col(column).map_elements(soundex, return_dtype=pl.Utf8).alias(f"{column}_soundex")
        )

    # =========================================================================
    # MATH TRANSFORMATIONS
    # =========================================================================

    def math_round(self, df: pl.DataFrame, column: str, decimals: int = 2) -> pl.DataFrame:
        """Round numbers"""
        return df.with_columns(pl.col(column).round(decimals).alias(f"{column}_rounded"))

    def math_ceil(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Ceiling (round up)"""
        return df.with_columns(pl.col(column).ceil().alias(f"{column}_ceil"))

    def math_floor(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Floor (round down)"""
        return df.with_columns(pl.col(column).floor().alias(f"{column}_floor"))

    def math_abs(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Absolute value"""
        return df.with_columns(pl.col(column).abs().alias(f"{column}_abs"))

    def math_sqrt(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Square root"""
        return df.with_columns((pl.col(column) ** 0.5).alias(f"{column}_sqrt"))

    def math_square(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Square"""
        return df.with_columns((pl.col(column) ** 2).alias(f"{column}_sq"))

    def math_log(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Natural logarithm"""
        return df.with_columns(pl.col(column).log().alias(f"{column}_log"))

    def math_log10(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Base-10 logarithm"""
        return df.with_columns(pl.col(column).log10().alias(f"{column}_log10"))

    def math_exp(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Exponential (e^x)"""
        return df.with_columns(pl.col(column).exp().alias(f"{column}_exp"))

    # =========================================================================
    # TRIGONOMETRIC TRANSFORMATIONS
    # =========================================================================

    def trig_sin(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Sine (radians)"""
        return df.with_columns(pl.col(column).sin().alias(f"{column}_sin"))

    def trig_cos(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Cosine (radians)"""
        return df.with_columns(pl.col(column).cos().alias(f"{column}_cos"))

    def trig_tan(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Tangent (radians)"""
        return df.with_columns(pl.col(column).tan().alias(f"{column}_tan"))

    def trig_asin(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Arc sine (radians)"""
        return df.with_columns(pl.col(column).arcsin().alias(f"{column}_asin"))

    def trig_acos(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Arc cosine (radians)"""
        return df.with_columns(pl.col(column).arccos().alias(f"{column}_acos"))

    def trig_atan(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Arc tangent (radians)"""
        return df.with_columns(pl.col(column).arctan().alias(f"{column}_atan"))

    # =========================================================================
    # DATE/TIME TRANSFORMATIONS
    # =========================================================================

    def datetime_year(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract year"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.year()
        else:
            col = col.dt.year()
        return df.with_columns(col.alias(f"{column}_year"))

    def datetime_month(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract month (1-12)"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.month()
        else:
            col = col.dt.month()
        return df.with_columns(col.alias(f"{column}_month"))

    def datetime_day(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract day of month"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.day()
        else:
            col = col.dt.day()
        return df.with_columns(col.alias(f"{column}_day"))

    def datetime_hour(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract hour"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.hour()
        else:
            col = col.dt.hour()
        return df.with_columns(col.alias(f"{column}_hour"))

    def datetime_minute(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract minute"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.minute()
        else:
            col = col.dt.minute()
        return df.with_columns(col.alias(f"{column}_minute"))

    def datetime_second(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract second"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.second()
        else:
            col = col.dt.second()
        return df.with_columns(col.alias(f"{column}_second"))

    def datetime_weekday(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract weekday (0=Monday, 6=Sunday)"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.weekday()
        else:
            col = col.dt.weekday()
        return df.with_columns(col.alias(f"{column}_weekday"))

    def datetime_quarter(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Extract quarter (1-4)"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            col = col.str.to_datetime().dt.quarter()
        else:
            col = col.dt.quarter()
        return df.with_columns(col.alias(f"{column}_quarter"))

    def datetime_age_days(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate age in days from today"""
        today = datetime.now()
        if df[column].dtype == pl.Utf8:
            dates = df[column].str.to_datetime()
        else:
            dates = df[column]
        return df.with_columns(
            (pl.lit(today).cast(pl.Datetime()) - dates.cast(pl.Datetime())).dt.total_days().abs().alias(f"{column}_age_days")
        )

    def datetime_age_years(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate age in years from today"""
        days = self.datetime_age_days(df, column)[f"{column}_age_days"]
        return df.with_columns((days / 365.25).cast(pl.Int64).alias(f"{column}_age_years"))

    def datetime_is_weekend(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Check if date is weekend"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            weekday = col.str.to_datetime().dt.weekday()
        else:
            weekday = col.dt.weekday()
        return df.with_columns(((weekday == 6) | (weekday == 7)).alias(f"{column}_is_weekend"))

    def datetime_is_leap_year(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Check if year is leap year"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            year = col.str.to_datetime().dt.year()
        else:
            year = col.dt.year()
        return df.with_columns(((year % 4 == 0) & ((year % 100 != 0) | (year % 400 == 0))).alias(f"{column}_is_leap_year"))

    def datetime_days_in_month(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Get days in month using native polars method"""
        col = pl.col(column)
        if df[column].dtype == pl.Utf8:
            dates = col.str.to_datetime()
        else:
            dates = col
        return df.with_columns(
            dates.dt.days_in_month().alias(f"{column}_days_in_month")
        )

    # =========================================================================
    # STATISTICAL TRANSFORMATIONS
    # =========================================================================

    def stat_zscore(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate z-score"""
        col = pl.col(column)
        mean = df[column].mean()
        std = df[column].std()
        if std == 0:
            std = 1
        return df.with_columns(((col - mean) / std).alias(f"{column}_zscore"))

    def stat_percent_rank(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate percent rank"""
        return df.with_columns(pl.col(column).rank("average", pct=True).alias(f"{column}_pct_rank"))

    def stat_rank(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Calculate rank"""
        return df.with_columns(pl.col(column).rank("average").alias(f"{column}_rank"))

    # =========================================================================
    # COLUMN OPERATIONS
    # =========================================================================

    def rename_column(self, df: pl.DataFrame, old_name: str, new_name: str) -> pl.DataFrame:
        """Rename column"""
        return df.rename({old_name: new_name})

    # =========================================================================
    # SPLIT OPERATIONS
    # =========================================================================

    def split_text(self, df: pl.DataFrame, column: str, delimiter: str) -> pl.DataFrame:
        """Split text by delimiter"""
        return df.with_columns(
            pl.col(column).str.split(delimiter).list.to_struct(
                fields=[f"{column}_part{i}" for i in range(2)]
            )
        ).unnest(column)

    # =========================================================================
    # PIVOT/UNPIVOT OPERATIONS
    # =========================================================================

    def pivot_table(self, df: pl.DataFrame, index: str, columns: str, values: str, aggregate: str = 'sum') -> pl.DataFrame:
        """Create pivot table"""
        agg_map = {
            'sum': 'sum', 'mean': 'mean', 'min': 'min', 'max': 'max', 'count': 'count', 'first': 'first', 'last': 'last'
        }
        agg_func = agg_map.get(aggregate, 'first')
        return df.pivot(values=values, index=index, columns=columns, aggregate_function=agg_func)

    def unpivot_table(self, df: pl.DataFrame, id_vars: List[str], value_vars: List[str] = None, var_name: str = "variable", value_name: str = "value") -> pl.DataFrame:
        """Unpivot/melt table"""
        if value_vars is None:
            value_vars = [c for c in df.columns if c not in id_vars]
        return df.melt(id_vars=id_vars, value_vars=value_vars, variable_name=var_name, value_name=value_name)

    # =========================================================================
    # ML OPERATIONS (Simplified implementations)
    # =========================================================================

    def ml_anomaly_iforest(self, df: pl.DataFrame, column: str, contamination: float = 0.1) -> pl.DataFrame:
        """Anomaly detection using Isolation Forest - simplified"""
        col_data = df[column].to_numpy().reshape(-1, 1)
        mean_val = np.mean(col_data)
        std_val = np.std(col_data)
        if std_val == 0:
            std_val = 1

        # Simplified anomaly detection based on distance from mean
        distances = np.abs(col_data - mean_val) / std_val
        threshold = 2.5  # Simplified threshold
        is_anomaly = distances > threshold
        scores = 1 - (1 / (1 + distances))  # Higher = more anomalous

        return df.with_columns([
            pl.Series(name=f"{column}_is_anomaly", values=is_anomaly),
            pl.Series(name=f"{column}_anomaly_score", values=scores.flatten())
        ])

    def ml_anomaly_zscore(self, df: pl.DataFrame, column: str, threshold: float = 3.0) -> pl.DataFrame:
        """Anomaly detection using Z-score"""
        col = pl.col(column)
        mean = df[column].mean()
        std = df[column].std()
        if std == 0:
            std = 1
        zscore = (col - mean) / std
        return df.with_columns([
            zscore.alias(f"{column}_zscore"),
            (zscore.abs() > threshold).alias(f"{column}_is_outlier")
        ])

    def ml_anomaly_iqr(self, df: pl.DataFrame, column: str, multiplier: float = 1.5) -> pl.DataFrame:
        """Anomaly detection using IQR"""
        Q1 = df[column].quantile(0.25)
        Q3 = df[column].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - multiplier * IQR
        upper_bound = Q3 + multiplier * IQR
        return df.with_columns([
            (pl.col(column) < lower_bound).alias(f"{column}_is_outlier"),
            (pl.col(column) - (Q3 + Q1) / 2).abs().alias(f"{column}_iqr_distance")
        ])

    def ml_anomaly_lof(self, df: pl.DataFrame, column: str, n_neighbors: int = 20) -> pl.DataFrame:
        """Local Outlier Factor - simplified"""
        col_data = df[column].to_numpy()
        mean_val = np.mean(col_data)
        distances = np.abs(col_data - mean_val)
        max_dist = np.max(distances)
        if max_dist == 0:
            max_dist = 1
        # Simplified LOF-like score
        scores = 1 - (distances / max_dist)
        threshold = 0.3
        is_outlier = scores < threshold
        return df.with_columns([
            pl.Series(name=f"{column}_is_outlier", values=is_outlier),
            pl.Series(name=f"{column}_lof_score", values=scores)
        ])

    def ml_outlier(self, df: pl.DataFrame, column: str, method: str = 'iqr') -> pl.DataFrame:
        """General outlier detection"""
        if method == 'zscore':
            return self.ml_anomaly_zscore(df, column)
        else:
            return self.ml_anomaly_iqr(df, column)

    def ml_cluster(self, df: pl.DataFrame, columns: List[str], n_clusters: int = 3) -> pl.DataFrame:
        """K-Means clustering - simplified"""
        data = df.select(columns).to_numpy()
        means = np.mean(data, axis=0)
        stds = np.std(data, axis=0)
        if np.any(stds == 0):
            stds[stds == 0] = 1
        normalized = (data - means) / stds

        # Simple k-means simulation using random initial centers
        np.random.seed(42)
        centers = normalized[np.random.choice(len(normalized), n_clusters, replace=False)]

        distances = np.zeros((len(normalized), n_clusters))
        for i in range(n_clusters):
            distances[:, i] = np.linalg.norm(normalized - centers[i], axis=1)
        labels = np.argmin(distances, axis=1)

        return df.with_columns(pl.Series(name="cluster", values=labels))

    def ml_forecast(self, df: pl.DataFrame, column: str, periods: int = 12) -> pl.DataFrame:
        """Simple time series forecast using exponential smoothing"""
        values = df[column].to_numpy()
        if len(values) == 0:
            return df.with_columns(pl.lit(None).alias(f"{column}_forecast"))

        alpha = 0.3
        n = len(values)
        smoothed = np.zeros(n + periods)

        # Calculate smoothed values
        smoothed[0] = values[0]
        for i in range(1, n):
            smoothed[i] = alpha * values[i] + (1 - alpha) * smoothed[i - 1]

        # Extend with last smoothed value (naive forecast)
        for i in range(n, n + periods):
            smoothed[i] = smoothed[i - 1]

        return df.with_columns(
            pl.Series(name=f"{column}_forecast", values=smoothed[:n])
        )

    # =========================================================================
    # AUDIT OPERATIONS
    # =========================================================================

    def audit_benford_law(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Benford's Law analysis"""
        # Get first digit
        first_digit = df[column].cast(pl.Utf8).str.slice(0, 1)

        # Expected Benford distribution
        benford_expected = {
            '1': 0.301, '2': 0.176, '3': 0.125, '4': 0.097, '5': 0.079,
            '6': 0.067, '7': 0.058, '8': 0.051, '9': 0.046
        }

        # Calculate actual distribution
        total = len(df)
        digit_counts = first_digit.value_counts().to_dict()

        # Calculate deviation for each row
        def calc_deviation(val):
            if val is None or str(val) == '0':
                return 0
            first = str(val)[0]
            expected = benford_expected.get(first, 0.05)
            actual = digit_counts.get(first, 0) / total if first in digit_counts else 0
            return abs(expected - actual)

        return df.with_columns([
            pl.col(column).map_elements(calc_deviation, return_dtype=pl.Float64).alias(f"{column}_benford_deviation"),
            pl.col(column).map_elements(
                lambda x: calc_deviation(x) > 0.1,
                return_dtype=pl.Boolean
            ).alias(f"{column}_is_suspicious")
        ])

    # =========================================================================
    # AI OPERATIONS (Simplified placeholders)
    # =========================================================================

    def ai_explain(self, df: pl.DataFrame, column: str, style: str = 'concise') -> pl.DataFrame:
        """AI explanation - placeholder"""
        # In production, this would call OpenAI/Anthropic API
        return df.with_columns(
            pl.lit(f"AI analysis of {column}").alias(f"{column}_ai_explanation")
        )

    def ai_sentiment(self, df: pl.DataFrame, column: str) -> pl.DataFrame:
        """Sentiment analysis - placeholder"""
        # Simplified sentiment based on keywords
        positive_words = ['good', 'great', 'excellent', 'amazing', 'love', 'best', 'happy']
        negative_words = ['bad', 'poor', 'terrible', 'awful', 'hate', 'worst', 'sad']

        def simple_sentiment(text):
            if text is None:
                return 0.0, "Neutral"
            text_lower = str(text).lower()
            pos_count = sum(1 for w in positive_words if w in text_lower)
            neg_count = sum(1 for w in negative_words if w in text_lower)
            score = (pos_count - neg_count) / max(pos_count + neg_count, 1)
            if score > 0:
                label = "Positive"
            elif score < 0:
                label = "Negative"
            else:
                label = "Neutral"
            return score, label

        scores = []
        labels = []
        for val in df[column]:
            score, label = simple_sentiment(val)
            scores.append(score)
            labels.append(label)

        return df.with_columns([
            pl.Series(name=f"{column}_sentiment_score", values=scores),
            pl.Series(name=f"{column}_sentiment_label", values=labels)
        ])

    def ai_extract(self, df: pl.DataFrame, column: str, entity_type: str) -> pl.DataFrame:
        """Entity extraction - placeholder"""
        patterns = {
            'email': r'[\w\.-]+@[\w\.-]+',
            'phone': r'\d{3}-\d{3}-\d{4}|\d{10}',
            'date': r'\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}',
            'money': r'\$[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*(?:USD|EUR|GBP)'
        }
        pattern = patterns.get(entity_type, r'.+')
        return df.with_columns(
            pl.col(column).str.extract_all(pattern).list.join(", ").alias(f"{column}_extracted")
        )

    def ai_pattern_learn(self, df: pl.DataFrame, column: str, output_column: str) -> pl.DataFrame:
        """Pattern learning (flash fill) - placeholder"""
        # In production, this would learn from examples and apply
        return df.with_columns(pl.col(column).alias(output_column))

    # =========================================================================
    # FILTER OPERATIONS
    # =========================================================================

    def filter_data(self, df: pl.DataFrame, filters: Dict[str, Any]) -> pl.DataFrame:
        """Apply filters to DataFrame"""
        filtered_df = df

        for column, condition in filters.items():
            if column in df.columns:
                if isinstance(condition, dict):
                    if 'min' in condition and 'max' in condition:
                        filtered_df = filtered_df.filter(
                            (pl.col(column) >= condition['min']) &
                            (pl.col(column) <= condition['max'])
                        )
                    elif 'equals' in condition:
                        filtered_df = filtered_df.filter(pl.col(column) == condition['equals'])
                    elif 'contains' in condition:
                        filtered_df = filtered_df.filter(pl.col(column).str.contains(condition['contains']))
                    elif 'in' in condition:
                        filtered_df = filtered_df.filter(pl.col(column).is_in(condition['in']))
                else:
                    filtered_df = filtered_df.filter(pl.col(column) == condition)

        return filtered_df

    # =========================================================================
    # SAMPLE OPERATIONS
    # =========================================================================

    def sample_data(self, df: pl.DataFrame, method: str = "random", size: int = 1000, **kwargs) -> pl.DataFrame:
        """Sample data using various methods"""
        n_rows = len(df)
        if n_rows == 0:
            return df

        if method == "random":
            return df.sample(n=min(size, n_rows))
        elif method == "systematic":
            interval = max(1, n_rows // size)
            return df[::interval].head(size)
        elif method == "top":
            return df.head(size)
        elif method == "bottom":
            return df.tail(size)
        else:
            raise ValueError(f"Unknown sampling method: {method}")

    # =========================================================================
    # LEGACY TRANSFORMATION METHODS
    # =========================================================================

    def lowercase(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Convert text to lowercase"""
        target_col = new_column or f"{column}_lower"
        return df.with_columns(pl.col(column).str.to_lowercase().alias(target_col))

    def trim(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Remove leading/trailing whitespace"""
        target_col = new_column or f"{column}_trimmed"
        return df.with_columns(pl.col(column).str.strip_chars().alias(target_col))

    def capitalize(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Convert to title case"""
        target_col = new_column or f"{column}_title"
        return df.with_columns(pl.col(column).str.to_titlecase().alias(target_col))

    def round_values(self, df: pl.DataFrame, column: str, decimals: int, new_column: str = None) -> pl.DataFrame:
        """Round numeric values"""
        target_col = new_column or f"{column}_rounded"
        return df.with_columns(pl.col(column).round(decimals).alias(target_col))

    def absolute(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Absolute value"""
        target_col = new_column or f"{column}_abs"
        return df.with_columns(pl.col(column).abs().alias(target_col))

    def log_transform(self, df: pl.DataFrame, column: str, new_column: str = None) -> pl.DataFrame:
        """Log transform"""
        target_col = new_column or f"{column}_log"
        return df.with_columns(pl.col(column).log().alias(target_col))

    def split_column(self, df: pl.DataFrame, column: str, delimiter: str, max_split: int = 0) -> pl.DataFrame:
        """Split column into multiple parts"""
        if max_split > 0:
            fields = [f"{column}_part_{i}" for i in range(max_split + 1)]
        else:
            fields = [f"{column}_part_{i}" for i in range(10)]

        return df.with_columns(
            pl.col(column).str.split(delimiter).list.to_struct(fields=fields)
        ).unnest(column)

    def replace_values(self, df: pl.DataFrame, old_value: Any, new_value: Any) -> pl.DataFrame:
        """Replace values in column"""
        return df.with_columns(
            pl.when(pl.col(column) == old_value)
            .then(new_value)
            .otherwise(pl.col(column))
            .alias(column)
        )

    def cast_column(self, df: pl.DataFrame, column: str, new_type: str) -> pl.DataFrame:
        """Change column data type"""
        type_mapping = {
            'string': pl.Utf8, 'str': pl.Utf8, 'int': pl.Int64,
            'integer': pl.Int64, 'float': pl.Float64, 'double': pl.Float64,
            'bool': pl.Boolean, 'boolean': pl.Boolean, 'date': pl.Date, 'datetime': pl.Datetime,
        }

        if new_type not in type_mapping:
            raise ValueError(f"Unsupported type: {new_type}")

        return df.with_columns(pl.col(column).cast(type_mapping[new_type], strict=False))

    def filter_column(self, df: pl.DataFrame, column: str, operator: str, value: Any) -> pl.DataFrame:
        """Filter rows based on column value"""
        if operator == '==':
            return df.filter(pl.col(column) == value)
        elif operator == '!=':
            return df.filter(pl.col(column) != value)
        elif operator == '>':
            return df.filter(pl.col(column) > value)
        elif operator == '>=':
            return df.filter(pl.col(column) >= value)
        elif operator == '<':
            return df.filter(pl.col(column) < value)
        elif operator == '<=':
            return df.filter(pl.col(column) <= value)
        elif operator == 'contains':
            return df.filter(pl.col(column).str.contains(str(value)))
        elif operator == 'starts_with':
            return df.filter(pl.col(column).str.starts_with(str(value)))
        elif operator == 'ends_with':
            return df.filter(pl.col(column).str.ends_with(str(value)))
        elif operator == 'is_null':
            return df.filter(pl.col(column).is_null())
        elif operator == 'is_not_null':
            return df.filter(pl.col(column).is_not_null())
        elif operator == 'in':
            return df.filter(pl.col(column).is_in(value))
        else:
            raise ValueError(f"Unsupported operator: {operator}")

    def aggregate(self, df: pl.DataFrame, group_by: List[str], aggregations: Dict[str, str]) -> pl.DataFrame:
        """Aggregate data"""
        agg_exprs = []
        for column, agg_func in aggregations.items():
            if agg_func == 'sum':
                agg_exprs.append(pl.col(column).sum())
            elif agg_func == 'mean':
                agg_exprs.append(pl.col(column).mean())
            elif agg_func == 'avg':
                agg_exprs.append(pl.col(column).mean())
            elif agg_func == 'count':
                agg_exprs.append(pl.col(column).count())
            elif agg_func == 'min':
                agg_exprs.append(pl.col(column).min())
            elif agg_func == 'max':
                agg_exprs.append(pl.col(column).max())
            elif agg_func == 'first':
                agg_exprs.append(pl.col(column).first())
            elif agg_func == 'last':
                agg_exprs.append(pl.col(column).last())
            elif agg_func == 'n_unique':
                agg_exprs.append(pl.col(column).n_unique())

        return df.group_by(group_by).agg(aggregations)

    def sort_data(self, df: pl.DataFrame, columns: List[str], descending: List[bool] = None) -> pl.DataFrame:
        """Sort data by columns"""
        if descending is None:
            descending = [False] * len(columns)
        return df.sort(columns, descending=descending)

    def select_columns(self, df: pl.DataFrame, columns: List[str]) -> pl.DataFrame:
        """Select specific columns"""
        return df.select(columns)

    def drop_columns(self, df: pl.DataFrame, columns: List[str]) -> pl.DataFrame:
        """Drop columns"""
        return df.drop(columns)

    def add_column(self, df: pl.DataFrame, column_name: str, expression: str) -> pl.DataFrame:
        """Add a computed column"""
        try:
            expr = eval(expression)
            return df.with_columns(expr.alias(column_name))
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    def join_dataframes(self, df1: pl.DataFrame, df2: pl.DataFrame, on: List[str], how: str = 'inner') -> pl.DataFrame:
        """Join two dataframes"""
        return df1.join(df2, on=on, how=how)

    def pivot_table_legacy(self, df: pl.DataFrame, index: List[str], columns: str, values: str, aggregate: str = 'first') -> pl.DataFrame:
        """Create pivot table"""
        return df.pivot(values=values, index=index, columns=columns, aggregate_function=aggregate)

    # =========================================================================
    # TABLE STRUCTURE OPERATIONS
    # =========================================================================

    def promote_row_as_header(self, df: pl.DataFrame, row_index: int = 0) -> pl.DataFrame:
        """
        Promote a specific row to become the column headers.

        Args:
            df: Input DataFrame
            row_index: The 0-based index of the row to use as headers

        Returns:
            DataFrame with the specified row as column names
        """
        if row_index >= len(df):
            raise ValueError(f"Row index {row_index} is out of range (dataframe has {len(df)} rows)")

        # Get the row to use as header
        row = df.row(row_index)
        new_headers = []
        seen = {}
        for i, h in enumerate(row):
            h_str = str(h).strip() if h is not None else f"col_{i}"
            # Handle duplicates by appending a suffix
            if h_str in seen:
                seen[h_str] += 1
                h_str = f"{h_str}_{seen[h_str]}"
            else:
                seen[h_str] = 0
            new_headers.append(h_str)

        # Remove the header row and return with new column names
        return df[row_index+1:].rename(dict(zip(df.columns, new_headers)))

    def remove_rows(self, df: pl.DataFrame, row_indices: List[int], remove: bool = True) -> pl.DataFrame:
        """
        Remove or keep specific rows by index.

        Args:
            df: Input DataFrame
            row_indices: List of row indices to remove or keep
            remove: If True, remove the specified rows. If False, keep only the specified rows.

        Returns:
            DataFrame with rows removed or filtered
        """
        if not row_indices:
            return df

        # Convert to set for fast lookup
        indices_set = set(row_indices)

        # Get all valid indices
        all_indices = set(range(len(df)))

        if remove:
            # Remove specified indices
            keep_indices = all_indices - indices_set
        else:
            # Keep only specified indices
            keep_indices = indices_set

        # Filter dataframe
        if not keep_indices:
            return df.clear()

        # Use lazy evaluation for better performance
        return df.filter(pl.int_range(0, len(df)).is_in(list(keep_indices)))

    def filter_rows_by_value(self, df: pl.DataFrame, column: str, operator: str, value: Any) -> pl.DataFrame:
        """
        Filter rows based on a column value.

        Args:
            df: Input DataFrame
            column: Column to filter on
            operator: One of '==', '!=', '>', '<', '>=', '<=', 'contains', 'starts_with', 'ends_with'
            value: Value to compare against

        Returns:
            Filtered DataFrame
        """
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in dataframe")

        col = pl.col(column)

        # Handle different operators
        if operator == "==":
            expr = col == value
        elif operator == "!=":
            expr = col != value
        elif operator == ">":
            expr = col > value
        elif operator == "<":
            expr = col < value
        elif operator == ">=":
            expr = col >= value
        elif operator == "<=":
            expr = col <= value
        elif operator == "contains":
            expr = col.str.contains(value, literal=False)
        elif operator == "starts_with":
            expr = col.str.starts_with(value)
        elif operator == "ends_with":
            expr = col.str.ends_with(value)
        elif operator == "is_null":
            expr = col.is_null()
        elif operator == "is_not_null":
            expr = col.is_not_null()
        else:
            raise ValueError(f"Unknown operator: {operator}")

        return df.filter(expr)
