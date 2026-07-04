"""
Report builders — one small function per reportable operation, each turning
a result dataframe (+ the step's params, + metrics_sink for ML operations)
into an AnalysisReport. Kept deliberately separate from data_processor.py:
the audit-tier builders below need nothing but the columns the operation
already added, so they carry zero risk of changing how any operation itself
behaves.
"""
from typing import Optional

import polars as pl

from core.analysis_report import AnalysisReport


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{n / total * 100:.1f}%"


# ---------------------------------------------------------------------------
# Audit tier — derived purely from result columns + step params
# ---------------------------------------------------------------------------

def build_duplicate_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    columns = params.get('columns', [])
    group_col = params.get('output_column') or params.get('output_col') or 'duplicate_group_id'
    flag_col = params.get('flag_column') or params.get('flag_col') or 'is_duplicate'

    report = AnalysisReport(title="Find Duplicates — Analysis Report", operation_id="audit_duplicate_detection")
    total_rows = result_df.height
    flagged = int(result_df[flag_col].sum()) if flag_col in result_df.columns else 0

    mode = "Single column" if len(columns) == 1 else "Combination of columns"
    report.add_summary("Mode", f"{mode} ({', '.join(columns)})")
    report.add_summary("Total Rows", total_rows)
    report.add_summary("Rows Flagged as Duplicate", f"{flagged} ({_pct(flagged, total_rows)})")

    if group_col in result_df.columns:
        groups = (
            result_df.group_by(group_col)
            .agg([pl.len().alias("row_count"), *[pl.col(c).first() for c in columns]])
            .filter(pl.col("row_count") > 1)
            .sort("row_count", descending=True)
        )
        report.add_summary("Distinct Duplicate Groups", groups.height)
        report.add_table("Duplicate Groups", groups)

    report.notes.append(
        "A duplicate group is a set of rows sharing identical values in the checked column(s)."
    )
    return report


def build_benford_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    column = params.get('column')
    digit_col = params.get('digit_col', 'leading_digit')
    expected_col = params.get('expected_col', 'benford_expected')
    deviation_col = params.get('deviation_col', 'benford_deviation')
    digits = params.get('digits', 1)

    report = AnalysisReport(title="Benford's Law — Analysis Report", operation_id="audit_benford_law")
    valid = result_df.filter(pl.col(digit_col).is_not_null())
    total = valid.height

    freq_table = (
        valid.group_by(digit_col)
        .agg([pl.len().alias("actual_count"), pl.col(expected_col).first().alias("expected_pct")])
        .with_columns((pl.col("actual_count") / total * 100).alias("actual_pct"))
        .with_columns((pl.col("actual_pct") - pl.col("expected_pct")).abs().alias("abs_deviation"))
        .sort(digit_col)
    )

    mad = float(freq_table["abs_deviation"].mean()) if freq_table.height else 0.0
    # Standard Nigrini MAD conformity bands for first-digit tests.
    if digits == 1:
        if mad < 0.6:
            verdict = "Close conformity"
        elif mad < 1.2:
            verdict = "Acceptable conformity"
        elif mad < 1.8:
            verdict = "Marginally acceptable conformity"
        else:
            verdict = "Nonconformity — investigate further"
    else:
        verdict = "See deviation column (no standard MAD band for 2-digit test)"

    report.add_summary("Column Analyzed", column)
    report.add_summary("Digits Tested", digits)
    report.add_summary("Valid (Non-zero) Values", total)
    report.add_summary("Mean Absolute Deviation (MAD)", f"{mad:.4f}")
    report.add_summary("Conformity Verdict", verdict)

    worst = freq_table.sort("abs_deviation", descending=True).head(3)
    if worst.height:
        worst_digits = ", ".join(str(v) for v in worst[digit_col].to_list())
        report.add_summary("Most Deviating Digit(s)", worst_digits)

    report.add_table("Digit Frequencies (Actual vs Expected)", freq_table)
    report.notes.append(
        "MAD bands (1-digit test, Nigrini): <0.6 close, <1.2 acceptable, <1.8 marginal, >=1.8 investigate."
    )
    return report


def build_gap_analysis_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    id_column = params.get('id_column')
    output_col = params.get('output_column') or params.get('output_col') or 'is_missing_sequence'
    count_col = params.get('missing_count_column') or params.get('missing_count_col') or 'gaps_after_this'

    report = AnalysisReport(title="Gap Analysis — Analysis Report", operation_id="audit_gap_analysis")
    total_rows = result_df.height
    gap_rows = result_df.filter(pl.col(output_col)) if output_col in result_df.columns else result_df.head(0)
    total_missing = int(gap_rows[count_col].sum()) if count_col in gap_rows.columns and gap_rows.height else 0

    report.add_summary("ID Column", id_column)
    report.add_summary("Total Rows", total_rows)
    report.add_summary("Locations With a Gap After Them", gap_rows.height)
    report.add_summary("Total Missing IDs (Sum of Gaps)", total_missing)
    if gap_rows.height:
        largest = int(gap_rows[count_col].max())
        report.add_summary("Largest Single Gap", largest)

    if gap_rows.height:
        cols = [id_column, count_col] if id_column in gap_rows.columns else [count_col]
        report.add_table("Gap Locations", gap_rows.select(cols).sort(count_col, descending=True))

    report.notes.append(
        f"'{count_col}' counts how many sequence values are missing immediately after that row's ID."
    )
    return report


def build_outlier_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    column = params.get('column')
    method = params.get('method', 'iqr')
    output_col = params.get('output_column') or params.get('output_col') or 'is_outlier'
    deviation_col = params.get('deviation_column') or params.get('deviation_col') or 'outlier_deviation'

    report = AnalysisReport(title="Outlier Detection — Analysis Report", operation_id="audit_outlier_detection")
    total_rows = result_df.height
    flagged = int(result_df[output_col].sum()) if output_col in result_df.columns else 0
    col_stats = result_df[column]

    report.add_summary("Column Analyzed", column)
    report.add_summary("Method", method)
    report.add_summary("Total Rows", total_rows)
    report.add_summary("Outliers Flagged", f"{flagged} ({_pct(flagged, total_rows)})")
    report.add_summary("Column Mean", f"{col_stats.mean():.4f}")
    report.add_summary("Column Std Dev", f"{col_stats.std():.4f}")
    report.add_summary("Column Min / Max", f"{col_stats.min()} / {col_stats.max()}")

    if flagged and output_col in result_df.columns:
        cols = [c for c in [column, deviation_col] if c in result_df.columns]
        outliers = result_df.filter(pl.col(output_col)).select(cols)
        if deviation_col in outliers.columns:
            outliers = outliers.sort(deviation_col, descending=True)
        report.add_table("Outlier Rows", outliers)

    return report


def build_round_numbers_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    column = params.get('column')
    threshold = params.get('threshold', 0.9)
    output_col = params.get('output_column') or params.get('output_col') or 'is_round_number'
    score_col = params.get('score_column') or params.get('score_col') or 'roundness_score'

    report = AnalysisReport(title="Round Number Detection — Analysis Report", operation_id="audit_round_numbers")
    total_rows = result_df.height
    flagged = int(result_df[output_col].sum()) if output_col in result_df.columns else 0

    report.add_summary("Column Analyzed", column)
    report.add_summary("Roundness Threshold", threshold)
    report.add_summary("Total Rows", total_rows)
    report.add_summary("Round Numbers Flagged", f"{flagged} ({_pct(flagged, total_rows)})")

    if flagged:
        cols = [c for c in [column, score_col] if c in result_df.columns]
        rows = result_df.filter(pl.col(output_col)).select(cols).sort(score_col, descending=True)
        report.add_table("Round Number Rows", rows)

    report.notes.append(
        "A higher roundness score means the value is closer to a clean round number "
        "(e.g. 1000, 500) — often worth a closer look for possible manual entry or manipulation."
    )
    return report


def build_zscore_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    column = params.get('column')
    zcol = f"{column}_zscore"

    report = AnalysisReport(title="Z-Score — Analysis Report", operation_id="stat_zscore")
    total_rows = result_df.height
    if zcol not in result_df.columns:
        report.notes.append(f"Expected column '{zcol}' not found.")
        return report

    abs_z = result_df[zcol].abs()
    over2 = int((abs_z > 2).sum())
    over3 = int((abs_z > 3).sum())

    report.add_summary("Column Analyzed", column)
    report.add_summary("Mean", f"{result_df[column].mean():.4f}")
    report.add_summary("Std Dev", f"{result_df[column].std():.4f}")
    report.add_summary("Rows with |z| > 2", f"{over2} ({_pct(over2, total_rows)})")
    report.add_summary("Rows with |z| > 3", f"{over3} ({_pct(over3, total_rows)})")

    top = result_df.select([column, zcol]).sort(zcol, descending=True).head(20)
    bottom = result_df.select([column, zcol]).sort(zcol).head(20)
    report.add_table("Highest Z-Scores", top)
    report.add_table("Lowest Z-Scores", bottom)
    return report


def build_percent_rank_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    column = params.get('column')
    pcol = f"{column}_pct_rank"

    report = AnalysisReport(title="Percentile Rank — Analysis Report", operation_id="stat_percent_rank")
    if pcol not in result_df.columns:
        report.notes.append(f"Expected column '{pcol}' not found.")
        return report

    report.add_summary("Column Analyzed", column)
    report.add_summary("Total Rows", result_df.height)

    top = result_df.select([column, pcol]).sort(pcol, descending=True).head(20)
    bottom = result_df.select([column, pcol]).sort(pcol).head(20)
    report.add_table("Highest Percentile Rank (Top 20)", top)
    report.add_table("Lowest Percentile Rank (Bottom 20)", bottom)
    report.notes.append(
        f"'{pcol}' is each row's percentile position (0.0-1.0) within '{column}', "
        "e.g. 0.95 means it's higher than 95% of the other values."
    )
    return report


def build_rank_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    column = params.get('column')
    rcol = f"{column}_rank"

    report = AnalysisReport(title="Rank — Analysis Report", operation_id="stat_rank")
    if rcol not in result_df.columns:
        report.notes.append(f"Expected column '{rcol}' not found.")
        return report

    report.add_summary("Column Analyzed", column)
    report.add_summary("Total Rows", result_df.height)
    report.add_summary("Distinct Ranks", result_df[rcol].n_unique())

    top = result_df.select([column, rcol]).sort(rcol).head(20)
    report.add_table("Top-Ranked Rows", top)
    report.notes.append(
        f"'{rcol}' uses average (fractional) ranking — tied values share the mean of the "
        "ranks they'd otherwise occupy, so ranks need not be whole numbers."
    )
    return report


def build_group_stats_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    group_column = params.get('group_column')
    target_column = params.get('target_column')
    # Per-group aggregates (same value repeated across every row in a
    # group) — one row per group in the report.
    group_stat_cols = [f"{target_column}_{s}" for s in ('mean', 'std', 'min', 'max', 'sum', 'count')]
    present = [c for c in group_stat_cols if c in result_df.columns]
    # zscore is a per-ROW value derived from the group's mean/std, not a
    # per-group constant — reported separately, sorted by magnitude.
    zscore_col = f"{target_column}_zscore"

    report = AnalysisReport(title="Group Statistics — Analysis Report", operation_id="stat_add_group_stats")
    report.add_summary("Grouped By", group_column)
    report.add_summary("Target Column", target_column)
    report.add_summary("Number of Groups", result_df[group_column].n_unique())

    if present:
        summary_table = result_df.select([group_column, *present]).unique(subset=[group_column]).sort(group_column)
        report.add_table("Per-Group Statistics", summary_table)

    if zscore_col in result_df.columns:
        top_z = result_df.select([group_column, target_column, zscore_col]) \
            .sort(zscore_col, descending=True, nulls_last=True).head(20)
        report.add_table("Highest Within-Group Z-Scores", top_z)

    return report


def build_flag_rows_report(result_df: pl.DataFrame, params: dict) -> AnalysisReport:
    conditions = params.get('conditions', [])
    combine_operator = params.get('combine_operator', 'AND')
    flag_col = params.get('flag_column') or params.get('flag_col') or 'flagged'

    report = AnalysisReport(title="Flag Rows — Analysis Report", operation_id="audit_flag_rows")
    total_rows = result_df.height
    flagged = int(result_df[flag_col].sum()) if flag_col in result_df.columns else 0

    cond_desc = f" {combine_operator} ".join(
        f"{c.get('column')} {c.get('operator')} {c.get('value', '')}".strip() for c in conditions
    )
    report.add_summary("Condition(s)", cond_desc or "(none)")
    report.add_summary("Total Rows", total_rows)
    report.add_summary("Rows Flagged", f"{flagged} ({_pct(flagged, total_rows)})")

    if flagged:
        report.add_table("Flagged Rows", result_df.filter(pl.col(flag_col)).head(500))
    return report


AUDIT_REPORT_BUILDERS = {
    "audit_duplicate_detection": build_duplicate_report,
    "audit_benford_law": build_benford_report,
    "audit_gap_analysis": build_gap_analysis_report,
    "audit_outlier_detection": build_outlier_report,
    "audit_round_numbers": build_round_numbers_report,
    "stat_zscore": build_zscore_report,
    "stat_percent_rank": build_percent_rank_report,
    "stat_rank": build_rank_report,
    "stat_add_group_stats": build_group_stats_report,
    "audit_flag_rows": build_flag_rows_report,
}


# ---------------------------------------------------------------------------
# ML tier — derived from metrics_sink (real metrics computed during fit,
# which don't survive in the result dataframe's columns alone)
# ---------------------------------------------------------------------------

def build_supervised_model_report(result_df: pl.DataFrame, params: dict, metrics: dict) -> AnalysisReport:
    """Shared report for every regression/tree-based model (Linear
    Regression, GLM, Decision Tree, Random Forest, Gradient Boosting,
    XGBoost, LightGBM) and ML Classify — they all share the same
    is-classification-or-regression shape."""
    model_type = metrics.get('model_type', 'Model')
    report = AnalysisReport(title=f"{model_type} — Analysis Report", operation_id=params.get('_operation_id', ''))

    report.add_summary("Model Type", model_type)
    report.add_summary("Task", metrics.get('task', 'unknown').title())
    report.add_summary("Features", ", ".join(params.get('features', [])))
    if params.get('target'):
        report.add_summary("Target", params.get('target'))

    if metrics.get('task') == 'classification':
        report.add_summary("Accuracy", f"{metrics.get('accuracy', 0.0):.4f}")
        if 'auc' in metrics:
            report.add_summary("AUC", f"{metrics['auc']:.4f}")
        elif 'auc_macro_ovr' in metrics:
            report.add_summary("AUC (macro, one-vs-rest)", f"{metrics['auc_macro_ovr']:.4f}")
        if 'mean_confidence' in metrics:
            report.add_summary("Mean Prediction Confidence", f"{metrics['mean_confidence']:.4f}")

        eval_rows = [
            {"Metric": "F1", "Macro": metrics.get('f1_macro'), "Weighted": metrics.get('f1_weighted')},
            {"Metric": "Precision", "Macro": metrics.get('precision_macro'), "Weighted": metrics.get('precision_weighted')},
            {"Metric": "Recall", "Macro": metrics.get('recall_macro'), "Weighted": metrics.get('recall_weighted')},
        ]
        if all(row["Macro"] is not None for row in eval_rows):
            report.add_table("Evaluation Metrics", pl.DataFrame(eval_rows))

        classes = metrics.get('classes', [])
        cm = metrics.get('confusion_matrix', [])
        if classes and cm:
            cm_df = pl.DataFrame(
                {"Actual \\ Predicted": classes, **{str(c): [row[i] for row in cm] for i, c in enumerate(classes)}}
            )
            report.add_table("Confusion Matrix", cm_df)
    else:
        report.add_summary("R-squared", f"{metrics.get('r_squared', 0.0):.4f}")
        report.add_summary("MSE", f"{metrics.get('mse', 0.0):.4f}")
        report.add_summary("RMSE", f"{metrics.get('rmse', 0.0):.4f}")
        report.add_summary("MAE", f"{metrics.get('mae', 0.0):.4f}")
        if 'mape' in metrics:
            report.add_summary("MAPE", f"{metrics['mape']:.2f}%")
        if 'pseudo_r_squared' in metrics and metrics['pseudo_r_squared'] is not None:
            report.add_summary("Pseudo R-squared", f"{metrics['pseudo_r_squared']:.4f}")

    if 'coefficients' in metrics:
        rows = [{"Feature": f, "Coefficient": c} for f, c in metrics['coefficients'].items()]
        if 'p_values' in metrics:
            for row in rows:
                row["P-Value"] = metrics['p_values'].get(row["Feature"])
        if metrics.get('intercept') is not None:
            rows.append({"Feature": "(Intercept)", "Coefficient": metrics['intercept']})
        report.add_table("Coefficients", pl.DataFrame(rows))

    if 'feature_importances' in metrics:
        rows = sorted(
            ({"Feature": f, "Importance": v} for f, v in metrics['feature_importances'].items()),
            key=lambda r: r["Importance"], reverse=True
        )
        report.add_table("Feature Importances", pl.DataFrame(rows))

    return report


def build_clustering_report(result_df: pl.DataFrame, params: dict, metrics: dict) -> AnalysisReport:
    model_type = metrics.get('model_type', 'Clustering')
    report = AnalysisReport(title=f"{model_type} — Analysis Report", operation_id=params.get('_operation_id', ''))

    report.add_summary("Model Type", model_type)
    report.add_summary("Number of Clusters Found", metrics.get('n_clusters', 0))
    if 'n_noise' in metrics:
        report.add_summary("Noise Points (unclustered)", metrics['n_noise'])
    if 'inertia' in metrics:
        report.add_summary("Inertia (within-cluster sum of squares)", f"{metrics['inertia']:.4f}")
    if 'silhouette_score' in metrics:
        report.add_summary("Silhouette Score (higher is better)", f"{metrics['silhouette_score']:.4f}")
    if 'davies_bouldin_score' in metrics:
        report.add_summary("Davies-Bouldin Score (lower is better)", f"{metrics['davies_bouldin_score']:.4f}")

    sizes = metrics.get('cluster_sizes', {})
    centers = metrics.get('cluster_centers', {})
    if sizes:
        feature_names = sorted({f for c in centers.values() for f in c}) if centers else []
        rows = []
        for cluster_id, size in sizes.items():
            row = {"Cluster": cluster_id, "Size": size}
            if cluster_id in centers:
                row.update(centers[cluster_id])
            rows.append(row)
        report.add_table("Cluster Profile", pl.DataFrame(rows))

    report.notes.append("Cluster centers are the mean of each feature in the ORIGINAL (unscaled) units.")
    if 'n_noise' in metrics:
        report.notes.append("Cluster '-1' represents noise points that didn't fit any cluster.")
    return report


def build_train_model_report(result_df: pl.DataFrame, params: dict, metrics: dict) -> AnalysisReport:
    report = AnalysisReport(title="Train Model — Analysis Report", operation_id="ml_train")
    report.add_summary("Model Name", metrics.get('model_name', ''))
    report.add_summary("Algorithm", metrics.get('model_type', ''))
    report.add_summary("Saved To", metrics.get('model_path', ''))
    report.add_summary("Train / Test Rows", f"{metrics.get('train_rows', 0)} / {metrics.get('test_rows', 0)}")
    report.add_summary("Test Accuracy", f"{metrics.get('accuracy', 0.0):.4f}")
    if 'auc' in metrics:
        report.add_summary("Test AUC", f"{metrics['auc']:.4f}")
    elif 'auc_macro_ovr' in metrics:
        report.add_summary("Test AUC (macro, one-vs-rest)", f"{metrics['auc_macro_ovr']:.4f}")

    eval_rows = [
        {"Metric": "F1", "Macro": metrics.get('f1_macro'), "Weighted": metrics.get('f1_weighted')},
        {"Metric": "Precision", "Macro": metrics.get('precision_macro'), "Weighted": metrics.get('precision_weighted')},
        {"Metric": "Recall", "Macro": metrics.get('recall_macro'), "Weighted": metrics.get('recall_weighted')},
    ]
    if all(row["Macro"] is not None for row in eval_rows):
        report.add_table("Evaluation Metrics (Test Set)", pl.DataFrame(eval_rows))

    classes = metrics.get('classes', [])
    cm = metrics.get('confusion_matrix', [])
    if classes and cm:
        cm_df = pl.DataFrame(
            {"Actual \\ Predicted": classes, **{str(c): [row[i] for row in cm] for i, c in enumerate(classes)}}
        )
        report.add_table("Confusion Matrix (Test Set)", cm_df)

    if 'feature_importances' in metrics:
        rows = sorted(
            ({"Feature": f, "Importance": v} for f, v in metrics['feature_importances'].items()),
            key=lambda r: r["Importance"], reverse=True
        )
        report.add_table("Feature Importances", pl.DataFrame(rows))
    return report


def build_risk_score_report(result_df: pl.DataFrame, params: dict, metrics: dict) -> AnalysisReport:
    report = AnalysisReport(title="Risk Score — Analysis Report", operation_id="ml_risk_score")
    report.add_summary("Features Used", ", ".join(metrics.get('feature_weights', {}).keys()))
    report.add_summary("Score Range", f"{metrics.get('min_score', 0):.4f} - {metrics.get('max_score', 0):.4f}")
    report.add_summary("Mean Score", f"{metrics.get('mean_score', 0):.4f}")

    weights = metrics.get('feature_weights', {})
    if weights:
        report.add_table("Feature Weights", pl.DataFrame(
            [{"Feature": f, "Weight": w} for f, w in weights.items()]
        ))

    indices = metrics.get('top_risk_row_indices', [])
    scores = metrics.get('top_risk_scores', [])
    if indices:
        output_col = params.get('output_column') or params.get('output_col') or 'risk_score'
        top_rows = result_df[indices] if hasattr(result_df, '__getitem__') else None
        if top_rows is not None:
            report.add_table("Top Risk Rows", top_rows)
    return report


def build_predict_report(result_df: pl.DataFrame, params: dict, metrics: dict) -> AnalysisReport:
    report = AnalysisReport(title="Predict — Analysis Report", operation_id="ml_predict")
    report.add_summary("Model ID", metrics.get('model_id', ''))
    report.add_summary("Model Found", metrics.get('model_found', False))
    if metrics.get('model_found'):
        report.add_summary("Rows Predicted", metrics.get('rows_predicted', 0))
        if 'prediction_mean' in metrics:
            report.add_summary("Prediction Mean", f"{metrics['prediction_mean']:.4f}")
            report.add_summary("Prediction Range", f"{metrics.get('prediction_min', 0):.4f} - {metrics.get('prediction_max', 0):.4f}")
        if 'prediction_value_counts' in metrics:
            counts = metrics['prediction_value_counts']
            report.add_table("Prediction Value Counts", pl.DataFrame(
                [{"Value": k, "Count": v} for k, v in counts.items()]
            ))
    else:
        report.notes.append(f"No saved model found for id '{metrics.get('model_id', '')}' — used a passthrough fallback.")
    return report


def build_forecast_report(result_df: pl.DataFrame, params: dict, metrics: dict) -> AnalysisReport:
    model_type = metrics.get('model_type', 'Forecast')
    report = AnalysisReport(title=f"{model_type} — Analysis Report", operation_id=params.get('_operation_id', ''))

    report.add_summary("Model Type", model_type)
    _param_labels = {'aic': 'AIC', 'order': 'Order'}
    for key, val in (metrics.get('model_params') or {}).items():
        report.add_summary(_param_labels.get(key, key.replace('_', ' ').title()), val)

    if 'in_sample_rmse' in metrics:
        report.add_summary("In-Sample RMSE", f"{metrics['in_sample_rmse']:.4f}")
        report.add_summary("In-Sample MAE", f"{metrics['in_sample_mae']:.4f}")
        if 'in_sample_mape' in metrics:
            report.add_summary("In-Sample MAPE", f"{metrics['in_sample_mape']:.2f}%")
        report.add_summary("Historical Points Used", metrics.get('in_sample_points', 0))

    if 'forecast_periods' in metrics:
        report.add_summary("Forecast Periods", metrics['forecast_periods'])
        report.add_summary("Forecast Range", f"{metrics['forecast_min']:.4f} to {metrics['forecast_max']:.4f}")
        report.add_summary("Forecast Mean", f"{metrics['forecast_mean']:.4f}")

    report.notes.append(
        "In-sample metrics compare the model's fitted values against known history — there's no "
        "ground truth for the forecast period itself (it's the future), so this is the standard proxy "
        "for how well the model captured the historical pattern."
    )
    return report


ML_REPORT_BUILDERS_WITH_METRICS = {
    "ml_linear_regression": build_supervised_model_report,
    "ml_glm": build_supervised_model_report,
    "ml_decision_tree": build_supervised_model_report,
    "ml_random_forest": build_supervised_model_report,
    "ml_gradient_boosting": build_supervised_model_report,
    "ml_xgboost": build_supervised_model_report,
    "ml_lightgbm": build_supervised_model_report,
    "ml_classify": build_supervised_model_report,
    "ml_cluster": build_clustering_report,
    "ml_dbscan": build_clustering_report,
    "ml_gmm": build_clustering_report,
    "ml_train": build_train_model_report,
    "ml_risk_score": build_risk_score_report,
    "ml_predict": build_predict_report,
    "ml_forecast": build_forecast_report,
    "ml_arima": build_forecast_report,
    "ml_ets": build_forecast_report,
}
