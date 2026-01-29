"""
Allocation mathematical utilities for the fair-shares library.

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy.special import erfinv
from scipy.stats import norm

from fair_shares.library.exceptions import AllocationError
from fair_shares.library.utils.dataframes import groupby_except_robust

if TYPE_CHECKING:
    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def calculate_relative_adjustment(
    values: TimeseriesDataFrame | pd.Series,
    functional_form: str = "power",
    exponent: float = 1.0,
    inverse: bool = True,
) -> TimeseriesDataFrame | pd.Series:
    """
    Calculate relative adjustment factors for allocations.

    Applies a transformation to input values (e.g., GDP per capita, cumulative
    emissions) to produce adjustment factors. See docs/science/allocations.md
    for theoretical grounding.

    Parameters
    ----------
    values
        Input values (GDP per capita, cumulative emissions, etc.)
    functional_form
        Transformation to apply: "asinh" or "power"
    exponent
        Exponent for the transformation
    inverse
        If True (default), higher values -> lower relative adjustment factor.
        If False, higher values -> higher relative adjustment factor.

    Returns
    -------
    Adjustment factors with same structure as input

    Notes
    -----
    Negative or NaN values are clamped to 1.0 before transformation to avoid
    numerical issues and ensure valid results for all inputs.
    """
    sign = -1 if inverse else 1

    # Handle negative values and NaN for both functional forms
    # Set problematic values to 1.0 before transformation
    # This treats net-sink countries and missing data as having minimal responsibility
    # Result: adjustment_factor = transform(1.0)^(sign*exponent)
    values_clamped = np.where((values <= 0) | np.isnan(values), 1.0, values)

    if functional_form == "power":
        return values_clamped ** (sign * exponent)
    elif functional_form == "asinh":
        return np.arcsinh(values_clamped) ** (sign * exponent)
    else:
        raise AllocationError(
            f"Unknown functional_form: {functional_form}. Must be 'power' or 'asinh'"
        )


def apply_deviation_constraint(
    shares: TimeseriesDataFrame,
    population: TimeseriesDataFrame,
    max_deviation_sigma: float,
    group_level: str,
) -> TimeseriesDataFrame:
    """
    Apply maximum deviation constraint from equal per capita baseline.

    Constrains allocation shares to within a specified number of standard deviations
    from equal per capita distribution. See docs/science/allocations.md for
    theoretical basis.

    Parameters
    ----------
    shares
        Current allocation shares
    population
        Population data
    max_deviation_sigma
        Maximum allowed deviation in standard deviations
    group_level
        Level name for grouping (typically "iso3c")

    Returns
    -------
    Constrained allocation shares
    """
    # Validate population data before division operations
    if population.isna().any().any():
        raise AllocationError(
            "Population data contains NaN values. "
            "Cannot apply deviation constraint with missing population data. "
            "Check data quality in population input."
        )

    # Calculate equal per capita baseline
    population_totals = groupby_except_robust(population, group_level)
    baseline_shares = population.divide(population_totals)

    # Convert to per capita space
    baseline_per_capita = baseline_shares.divide(population)
    shares_per_capita = shares.divide(population)

    # Calculate population-weighted standard deviation
    mean_numerator = groupby_except_robust(shares_per_capita * population, group_level)
    weighted_mean = mean_numerator / population_totals
    var_numerator = groupby_except_robust(
        (shares_per_capita - weighted_mean) ** 2 * population, group_level
    )
    weighted_var = var_numerator / population_totals
    std_dev = np.sqrt(weighted_var)

    # Apply constraints
    min_allowed = baseline_per_capita - (max_deviation_sigma * std_dev)
    max_allowed = baseline_per_capita + (max_deviation_sigma * std_dev)
    constrained_per_capita = np.clip(shares_per_capita, min_allowed, max_allowed)

    # Convert back to shares and normalize
    constrained_shares = constrained_per_capita * population
    constrained_totals = groupby_except_robust(constrained_shares, group_level)
    return constrained_shares.divide(constrained_totals)


def calculate_gini_adjusted_gdp(
    total_gdps: np.ndarray,
    gini_coefficients: np.ndarray,
    income_floor: float,
    total_populations: np.ndarray,
    max_adjustment: float = 0.8,
) -> np.ndarray:
    """
    Gini-adjusted GDP calculation using log-normal distribution and an income floor.

    Adjusts GDP to account for within-country income inequality by removing the
    portion of GDP below a specified income floor. See docs/science/allocations.md
    for theoretical grounding.

    Mathematical approach:
    - Models income distribution as log-normal with parameters derived from Gini
    - Calculates proportion of population below income floor using CDF
    - Estimates income share below floor using Lorenz curve properties
    - Removes this share from total GDP

    Parameters
    ----------
    total_gdps
        Array of total GDP values for each country
    gini_coefficients
        Array of Gini coefficients for each country
    income_floor
        Income floor value (absolute value in currency units per capita per year)
    total_populations
        Array of total population values for each country
    max_adjustment
        Maximum adjustment allowed as proportion of total GDP (default: 0.8)

    Returns
    -------
    Array of adjusted GDP values for each country
    """
    # Validation checks
    if income_floor < 0:
        raise AllocationError("Income floor must be non-negative.")
    if not (0 <= max_adjustment <= 1):
        raise AllocationError("Max adjustment must be between 0 and 1.")

    # Special case: if max_adjustment is 0, no adjustment is needed
    if max_adjustment == 0:
        return total_gdps

    # Special case: if income_floor is 0, no adjustment is needed
    if income_floor == 0:
        return total_gdps

    # Check for zero population before calculating per-capita income
    if np.any(total_populations == 0):
        zero_indices = np.where(total_populations == 0)[0]
        raise AllocationError(
            f"Zero population found for indices {zero_indices.tolist()} when calculating "
            f"Gini-adjusted GDP. Cannot calculate mean income per capita with zero population."
        )

    # Calculate log-normal distribution parameters for each country
    sigmas = 2 * erfinv(gini_coefficients)

    # Calculate mean income per capita for each country
    mean_incomes = total_gdps / total_populations

    # mu = ln(mean income) - sigma² / 2 for each country
    # Reshape sigmas to match the 2D structure of mean_incomes
    sigmas_2d = sigmas.reshape(-1, 1) if mean_incomes.ndim > 1 else sigmas
    mus = np.log(mean_incomes) - (sigmas_2d**2) / 2

    # Calculate floor proportions for each country
    floor_proportions = norm.cdf((np.log(income_floor) - mus) / sigmas_2d)

    # Calculate income shares below floor using Lorenz function for each country
    floor_income_shares = norm.cdf(norm.ppf(floor_proportions) - sigmas_2d)

    # Calculate adjusted GDPs for each country
    adjusted_total_gdps = total_gdps * (1 - floor_income_shares)

    # Apply maximum adjustment cap
    min_allowed_gdps = total_gdps * (1 - max_adjustment)
    adjusted_total_gdps = np.maximum(adjusted_total_gdps, min_allowed_gdps)

    return adjusted_total_gdps


def create_gini_lookup_dict(gini_data_df: TimeseriesDataFrame) -> dict[str, float]:
    """
    Create a simple lookup dict for Gini coefficients.

    Assumes the common case:
    - Index: MultiIndex with level 'iso3c' (and possibly 'unit')
    - Column: 'gini'

    Falls back to using 'iso3c' as a column if not found in the index.

    Parameters
    ----------
    gini_data_df
        DataFrame containing Gini coefficient data

    Returns
    -------
    Dictionary mapping country codes to Gini coefficients
    """
    # Prefer index level 'iso3c' if present
    if hasattr(gini_data_df, "index") and isinstance(gini_data_df.index, pd.MultiIndex):
        index_names = list(gini_data_df.index.names)
        if "iso3c" in index_names:
            iso3c_values = gini_data_df.index.get_level_values("iso3c")
            return dict(zip(iso3c_values, gini_data_df["gini"]))

    # Fallback: expect columns 'iso3c' and 'gini'
    return dict(zip(gini_data_df["iso3c"], gini_data_df["gini"]))


def apply_gini_adjustment(
    gdp_data: TimeseriesDataFrame | pd.Series,
    population_data: TimeseriesDataFrame | pd.Series,
    gini_lookup: dict[str, float],
    income_floor: float,
    max_gini_adjustment: float,
    group_level: str = "iso3c",
) -> TimeseriesDataFrame | pd.Series:
    """
    Apply Gini adjustment to GDP data for all groups.

    Parameters
    ----------
    gdp_data
        GDP data (DataFrame or Series)
    population_data
        Population data (DataFrame or Series)
    gini_lookup
        Dictionary mapping country codes to Gini coefficients
    income_floor
        Income floor value
    max_gini_adjustment
        Maximum adjustment allowed as proportion of total GDP
    group_level
        Level name for grouping (typically "iso3c")

    Returns
    -------
    Gini-adjusted GDP data with same structure as input
    """
    # Extract group identifiers
    # MultiIndex requires get_level_values(), single-level index uses index
    if isinstance(gdp_data.index, pd.MultiIndex):
        group_ids = gdp_data.index.get_level_values(group_level)
    else:
        group_ids = gdp_data.index

    # Prepare data for calculation
    gdp_values = gdp_data.values
    population_values = population_data.values
    gini_values = np.array([gini_lookup[group_id] for group_id in group_ids])

    # Apply Gini adjustment
    adjusted_gdp_values = calculate_gini_adjusted_gdp(
        total_gdps=gdp_values,
        gini_coefficients=gini_values,
        income_floor=income_floor,
        total_populations=population_values,
        max_adjustment=max_gini_adjustment,
    )

    # Return same type as input with same index
    if isinstance(gdp_data, pd.DataFrame):
        return pd.DataFrame(
            adjusted_gdp_values.reshape(gdp_data.shape),
            index=gdp_data.index,
            columns=gdp_data.columns,
        )
    else:
        return pd.Series(adjusted_gdp_values, index=gdp_data.index)
