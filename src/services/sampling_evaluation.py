"""Classical Variables Sampling (CVS) - sample size planning and sample
result evaluation/projection, mirroring ACL's SIZE/EVALUATE/CVSEVALUATE
commands. This is the piece that comes before and after sample SELECTION
(already covered by DataProcessor.sampling(), including monetary unit
sampling): given a target precision and confidence level, how large
should the sample be; and given a drawn sample's audited-vs-book results,
what does that project to for the whole population, with what precision.

All formulas are the standard mean-per-unit / difference / ratio
estimation methods taught in AICPA audit sampling guidance - nothing
here is invented or approximated beyond the well-established finite
population correction and normal-approximation confidence interval.
"""
import math
from typing import Any, Dict

import numpy as np
import polars as pl

ESTIMATION_METHODS = ["mean_per_unit", "difference", "ratio"]

_COMMON_Z_SCORES = {90.0: 1.645, 95.0: 1.960, 97.5: 2.240, 99.0: 2.576}


def z_score_for_confidence(confidence_level: float) -> float:
    """Two-tailed z-score for a given confidence level (e.g. 95 -> 1.96).
    Falls back to scipy's normal quantile function for anything not in
    the common table."""
    if confidence_level in _COMMON_Z_SCORES:
        return _COMMON_Z_SCORES[confidence_level]
    from scipy import stats as scipy_stats
    return float(scipy_stats.norm.ppf(1 - (1 - confidence_level / 100) / 2))


def calculate_sample_size(population_size: int, population_std_dev: float,
                           confidence_level: float, tolerable_precision: float,
                           apply_fpc: bool = True) -> Dict[str, Any]:
    """Classical variables (mean-per-unit) sample size calculation -
    mirrors ACL's SIZE command. Returns the sample size needed to
    estimate the population value within `tolerable_precision` (the
    auditor's allowance for sampling risk, in the same units as the
    population) at the given confidence level, given an estimate of the
    population's standard deviation (from a pilot sample or prior
    period)."""
    if population_size <= 0:
        raise ValueError("Population size must be positive.")
    if population_std_dev <= 0:
        raise ValueError("Population standard deviation must be positive.")
    if tolerable_precision <= 0:
        raise ValueError("Tolerable precision must be positive.")

    z = z_score_for_confidence(confidence_level)
    n_unadjusted = (population_size * z * population_std_dev / tolerable_precision) ** 2
    n_unadjusted = math.ceil(n_unadjusted)

    if apply_fpc:
        n_adjusted = math.ceil(n_unadjusted / (1 + n_unadjusted / population_size))
    else:
        n_adjusted = n_unadjusted

    recommended = max(1, min(n_adjusted, population_size))

    return {
        "recommended_sample_size": recommended,
        "unadjusted_sample_size": n_unadjusted,
        "z_score": z,
        "population_size": population_size,
        "population_std_dev": population_std_dev,
        "tolerable_precision": tolerable_precision,
        "confidence_level": confidence_level,
    }


def evaluate_sample(df: pl.DataFrame, book_value_column: str, audited_value_column: str,
                     population_size: int, population_book_total: float,
                     confidence_level: float = 95.0, method: str = "mean_per_unit") -> Dict[str, Any]:
    """Project a sample's audited-vs-book results to the full population -
    mirrors ACL's EVALUATE/CVSEVALUATE commands. `df` is the drawn sample
    with both a recorded (book) value and a verified (audited) value per
    item. Returns the projected population value, projected total
    misstatement, and a confidence interval around it (precision) at the
    given confidence level.

    method:
      - "mean_per_unit": projects from the sample's mean audited value alone.
      - "difference": projects from the mean per-item difference (audited - book);
        more precise when book values are known and errors are roughly constant in size.
      - "ratio": projects from the ratio of audited to book totals; more precise when
        errors are roughly proportional to item size.
    """
    if method not in ESTIMATION_METHODS:
        raise ValueError(f"Unknown evaluation method '{method}' - use one of {ESTIMATION_METHODS}.")

    n = df.height
    if n < 2:
        raise ValueError("Need at least 2 sampled items to evaluate a sample.")
    if population_size < n:
        raise ValueError("Population size can't be smaller than the sample size.")

    book = df[book_value_column].cast(pl.Float64).to_numpy()
    audited = df[audited_value_column].cast(pl.Float64).to_numpy()
    z = z_score_for_confidence(confidence_level)
    N = population_size

    # Finite population correction - shrinks the standard error when the
    # sample covers a non-trivial share of the population.
    fpc = math.sqrt((N - n) / (N - 1)) if N > n else 0.0

    if method == "mean_per_unit":
        mean_audited = float(np.mean(audited))
        std_audited = float(np.std(audited, ddof=1))
        point_estimate = N * mean_audited
        se_total = N * (std_audited / math.sqrt(n)) * fpc

    elif method == "difference":
        diffs = audited - book
        mean_diff = float(np.mean(diffs))
        std_diff = float(np.std(diffs, ddof=1))
        point_estimate = population_book_total + N * mean_diff
        se_total = N * (std_diff / math.sqrt(n)) * fpc

    else:  # ratio
        sum_audited = float(np.sum(audited))
        sum_book = float(np.sum(book))
        if sum_book == 0:
            raise ValueError("Sum of sampled book values is zero - ratio estimation isn't valid here.")
        ratio = sum_audited / sum_book
        point_estimate = ratio * population_book_total
        residuals = audited - ratio * book
        std_resid = float(np.std(residuals, ddof=1))
        se_total = N * (std_resid / math.sqrt(n)) * fpc

    precision = z * se_total
    projected_misstatement = point_estimate - population_book_total

    return {
        "method": method,
        "sample_size": n,
        "population_size": N,
        "population_book_total": population_book_total,
        "point_estimate": point_estimate,
        "projected_misstatement": projected_misstatement,
        "standard_error": se_total,
        "precision": precision,
        "confidence_level": confidence_level,
        "lower_bound": point_estimate - precision,
        "upper_bound": point_estimate + precision,
    }
