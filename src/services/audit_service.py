"""
Audit Service for CAATmaster
Implements audit procedures that create flag columns
"""
import polars as pl
import numpy as np
from typing import Dict, Any, List, Tuple
import re


class AuditService:
    """Service for audit procedures that create flag columns"""

    def benfords_law_analysis(
        self,
        df: pl.DataFrame,
        column: str,
        deviation_column: str = None,
        flag_column: str = None,
        threshold: float = 0.15
    ) -> pl.DataFrame:
        """
        Benford's Law analysis - creates deviation and flag columns
        """
        if deviation_column is None:
            deviation_column = f"{column}_benford_deviation"
        if flag_column is None:
            flag_column = f"{column}_is_suspicious"

        # Get first digits
        def get_first_digit(value):
            if value is None or value == 0:
                return None
            value = abs(float(value))
            if value < 1:
                return None
            while value >= 10:
                value /= 10
            return int(value)

        first_digits = df[column].map_elements(get_first_digit, return_dtype=pl.Int64)

        # Calculate actual distribution
        digit_counts = first_digits.filter(first_digits.is_not_null()).to_numpy()
        if len(digit_counts) == 0:
            # No valid data, return with null columns
            return df.with_columns([
                pl.lit(None, dtype=pl.Float64).alias(deviation_column),
                pl.lit(None, dtype=pl.Boolean).alias(flag_column)
            ])

        unique, actual_counts = np.unique(digit_counts, return_counts=True)
        actual_dist = {int(d): actual_counts[i] / len(digit_counts) for i, d in enumerate(unique)}

        # Benford's Law expected distribution
        benford_expected = {i: np.log10(1 + 1/i) for i in range(1, 10)}

        # Calculate deviation for each row
        deviations = []
        flags = []

        for digit in first_digits.to_list():
            if digit is None or digit not in actual_dist:
                deviations.append(None)
                flags.append(None)
            else:
                actual = actual_dist[digit]
                expected = benford_expected.get(digit, 0)
                deviation = abs(actual - expected)
                deviations.append(deviation)
                flags.append(deviation > threshold)

        result_df = df.with_columns([
            pl.Series(deviation_column, deviations, dtype=pl.Float64),
            pl.Series(flag_column, flags, dtype=pl.Boolean)
        ])

        return result_df

    def detect_duplicates(
        self,
        df: pl.DataFrame,
        columns: List[str],
        group_column: str = "duplicate_group",
        flag_column: str = "is_duplicate"
    ) -> pl.DataFrame:
        """
        Duplicate detection - creates duplicate group and flag columns
        """
        # Create a hash of the specified columns
        def create_hash(row_values):
            values = [str(v) if v is not None else "" for v in row_values]
            return hash("|".join(values))

        hashes = []
        for row in df.select(columns).iter_rows(named=False):
            hashes.append(create_hash(row))

        # Find duplicates
        unique_hashes, counts = np.unique(hashes, return_counts=True)
        duplicate_hashes = set(unique_hashes[counts > 1])

        # Assign group IDs
        hash_to_group = {}
        group_id = 0
        group_ids = []

        for h in hashes:
            if h in duplicate_hashes:
                if h not in hash_to_group:
                    hash_to_group[h] = group_id
                    group_id += 1
                group_ids.append(hash_to_group[h])
            else:
                group_ids.append(None)

        # Flag duplicates
        flags = [h in duplicate_hashes for h in hashes]

        result_df = df.with_columns([
            pl.Series(group_column, group_ids, dtype=pl.Int64),
            pl.Series(flag_column, flags, dtype=pl.Boolean)
        ])

        return result_df

    def gap_analysis(
        self,
        df: pl.DataFrame,
        id_column: str,
        gap_flag_column: str = "has_gap_after",
        gap_count_column: str = "gaps_after_this"
    ) -> pl.DataFrame:
        """
        Sequence gap analysis - creates gap flag and count columns
        """
        # Get sorted IDs
        ids = df.select(id_column).to_numpy().flatten()
        valid_mask = ~df[id_column].is_null()
        valid_ids = ids[valid_mask]
        valid_ids = np.sort(valid_ids[~np.isnan(valid_ids)])

        if len(valid_ids) < 2:
            # No gaps possible
            return df.with_columns([
                pl.lit(False).alias(gap_flag_column),
                pl.lit(0).alias(gap_count_column)
            ])

        # Find gaps
        gaps = {}
        for i in range(len(valid_ids) - 1):
            current_id = valid_ids[i]
            next_id = valid_ids[i + 1]
            gap_size = int(next_id - current_id - 1)

            if gap_size > 0:
                gaps[current_id] = gap_size

        # Create result columns
        gap_flags = []
        gap_counts = []

        for id_val in ids:
            if pd.isna(id_val):
                gap_flags.append(None)
                gap_counts.append(None)
            else:
                flag = id_val in gaps
                count = gaps.get(id_val, 0)
                gap_flags.append(flag)
                gap_counts.append(count)

        result_df = df.with_columns([
            pl.Series(gap_flag_column, gap_flags, dtype=pl.Boolean),
            pl.Series(gap_count_column, gap_counts, dtype=pl.Int32)
        ])

        return result_df

    def detect_outliers(
        self,
        df: pl.DataFrame,
        column: str,
        method: str = "iqr",
        threshold: float = 1.5,
        flag_column: str = None,
        deviation_column: str = None
    ) -> pl.DataFrame:
        """
        Statistical outlier detection - creates outlier flag and deviation columns
        """
        if flag_column is None:
            flag_column = f"{column}_is_outlier"
        if deviation_column is None:
            deviation_column = f"{column}_outlier_deviation"

        # Get column values
        values = df[column].to_numpy()
        valid_mask = ~df[column].is_null()
        valid_values = values[valid_mask]

        if len(valid_values) < 4:
            # Not enough data
            return df.with_columns([
                pl.lit(None, dtype=pl.Boolean).alias(flag_column),
                pl.lit(None, dtype=pl.Float64).alias(deviation_column)
            ])

        # Calculate outliers
        flags = np.zeros(len(df), dtype=bool)
        deviations = np.zeros(len(df), dtype=float)

        if method == "iqr":
            Q1 = np.percentile(valid_values, 25)
            Q3 = np.percentile(valid_values, 75)
            IQR = Q3 - Q1

            lower_bound = Q1 - threshold * IQR
            upper_bound = Q3 + threshold * IQR

            for i, val in enumerate(values):
                if not valid_mask[i]:
                    flags[i] = None
                    deviations[i] = None
                else:
                    is_outlier = val < lower_bound or val > upper_bound
                    flags[i] = is_outlier

                    # Calculate deviation in terms of IQR
                    if val < lower_bound:
                        deviations[i] = (lower_bound - val) / IQR
                    elif val > upper_bound:
                        deviations[i] = (val - upper_bound) / IQR
                    else:
                        deviations[i] = 0

        elif method == "zscore":
            mean = np.mean(valid_values)
            std = np.std(valid_values)

            for i, val in enumerate(values):
                if not valid_mask[i]:
                    flags[i] = None
                    deviations[i] = None
                else:
                    z_score = abs((val - mean) / std) if std > 0 else 0
                    flags[i] = z_score > threshold
                    deviations[i] = z_score

        result_df = df.with_columns([
            pl.Series(flag_column, flags, dtype=pl.Boolean),
            pl.Series(deviation_column, deviations, dtype=pl.Float64)
        ])

        return result_df

    def detect_round_numbers(
        self,
        df: pl.DataFrame,
        column: str,
        flag_column: str = None,
        tolerance: float = 0.01
    ) -> pl.DataFrame:
        """
        Round number detection - creates is_round flag column
        """
        if flag_column is None:
            flag_column = f"{column}_is_round"

        values = df[column].to_numpy()
        flags = []

        for val in values:
            if pd.isna(val):
                flags.append(None)
            else:
                val_float = float(val)
                # Check if value is close to a round number
                rounded = round(val_float)
                is_round = abs(val_float - rounded) < tolerance
                flags.append(is_round)

        result_df = df.with_columns([
            pl.Series(flag_column, flags, dtype=pl.Boolean)
        ])

        return result_df


# Import pandas for null checking
import pandas as pd
