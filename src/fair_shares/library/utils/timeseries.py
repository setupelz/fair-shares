"""Time-series data processing functions for fair-shares library.

This module handles time-series operations including interpolation,
harmonization, and year-based data transformations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd
import pint

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils.units import (
    get_default_unit_registry,
    set_single_unit,
)
from fair_shares.library.validation.pipeline_validation import (
    validate_has_year_columns,
    validate_index_structure,
    validate_year_in_data,
)

if TYPE_CHECKING:
    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def interpolate_scenarios_data(
    df: pd.DataFrame,  # Long format, so not a TimeseriesDataFrame
    interpolation_method: Literal["linear", "stepwise"],
    index_cols: list[str],
    add_missing_years: bool = True,
) -> pd.DataFrame:
    """
    Apply interpolation to long-form scenarios data and reorder columns.

    This function takes a pandas DataFrame in long format (with 'year' column)
    and applies interpolation to fill missing values in emission columns, by
    group columns.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame in long format with 'year' column and emission columns
    interpolation_method : str
        Interpolation method: "linear" or "stepwise"
    index_cols : List[str]
        List of index/metadata columns (not emission data columns)
    add_missing_years : bool, optional
        Whether to add missing years before interpolation. Defaults to True.

    Returns
    -------
    pd.DataFrame
        DataFrame with interpolated emission columns and reordered columns
    """
    # Add missing years if requested
    if add_missing_years:
        # Get the min and max years from existing data
        min_year = df["year"].min()
        max_year = df["year"].max()
        all_years = pd.DataFrame({"year": range(min_year, max_year + 1)})

        # Get unique combinations of grouping columns (excluding year)
        grouping_cols = [col for col in index_cols if col != "year"]
        unique_combinations = df[grouping_cols].drop_duplicates()

        # Create complete dataset with all combinations and all years
        complete_combinations = unique_combinations.merge(all_years, how="cross")

        # Merge with original data to preserve existing values, fill missing with NA
        df = complete_combinations.merge(df, on=grouping_cols + ["year"], how="left")  # noqa: RUF005

        print(f"Added missing years from {min_year} to {max_year}")

    # Get emission columns (exclude metadata columns)
    emission_cols = [col for col in df.columns if col not in index_cols]

    if interpolation_method == "linear":
        # For each pathway group, interpolate missing values
        grouping_cols = [col for col in index_cols if col != "year"]
        pathway_groups = df.groupby(grouping_cols)
        interpolated_pathways = []

        for name, group in pathway_groups:
            # Sort by year for interpolation
            group_sorted = group.sort_values("year")

            # Interpolate each emission column
            for col in emission_cols:
                group_sorted[col] = group_sorted[col].interpolate(method="linear")

            interpolated_pathways.append(group_sorted)

        # Combine interpolated pathways
        df = pd.concat(interpolated_pathways, ignore_index=True)
        print("Applied linear interpolation to pathways data")

    elif interpolation_method == "stepwise":
        # For stepwise interpolation, backward fill then forward fill
        # Backward fill first because each observation typically represents the
        # END of an interval (e.g., 2020 value represents 2016-2020 period)
        grouping_cols = [col for col in index_cols if col != "year"]
        pathway_groups = df.groupby(grouping_cols)
        interpolated_pathways = []

        for name, group in pathway_groups:
            # Sort by year for interpolation
            group_sorted = group.sort_values("year")

            # Apply stepwise interpolation (backward fill then forward fill)
            for col in emission_cols:
                group_sorted[col] = group_sorted[col].bfill().ffill()

            interpolated_pathways.append(group_sorted)

        # Combine interpolated pathways
        df = pd.concat(interpolated_pathways, ignore_index=True)
        print("Applied stepwise interpolation to pathways data")

    # Reorder columns to ensure emissions are in the correct order
    emission_cols = [col for col in df.columns if col not in index_cols]

    # Create the new column order
    new_column_order = index_cols + emission_cols
    df = df[new_column_order]

    print(f"Final column order: {list(df.columns)}")

    return df


def _apply_cumulative_preservation_scaling(
    values: np.ndarray[tuple[int], np.dtype[np.floating]],
    years: np.ndarray[tuple[int], np.dtype[np.integer]],
    first_adjustment_year: int,
    target_cumulative: float,
    easing_power: float = 1.0,
    tol: float = 1e-9,
) -> np.ndarray[tuple[int], np.dtype[np.floating]]:
    """
    Core math preserving cumulative totals by applying time-varying scale adjustments.

    This function applies time-varying multiplicative scaling to preserve a specified or
    original cumulative total while maintaining non-negative values over the adjustment
    period. It is used within the harmonize_to_historical_with_convergence() function.

    The algorithm uses an "ease-in" approach where:
    - Earlier years receive smaller adjustments
    - Later years receive larger adjustments
    - The scaling is weighted by both time and value magnitude

    Parameters
    ----------
    values : np.ndarray
        Array of values to adjust (can include negative values)
    years : np.ndarray
        Array of years corresponding to values
    first_adjustment_year : int
        First year (inclusive) from which adjustments apply. Values before this
        year are preserved unchanged.
    target_cumulative : float
        Target cumulative total to preserve across all years
    easing_power : float, default 1.0
        Controls the ease-in curve: 1.0 = linear, 2.0 = quadratic, 3.0 = cubic.
        Higher values concentrate more adjustment in later years.
    tol : float, default 1e-9
        Numeric tolerance for convergence and edge case detection

    Returns
    -------
    np.ndarray
        Adjusted values that:
        - Preserve the target cumulative total
        - Are non-negative in the adjustment period
        - Maintain original values before first_adjustment_year

    Raises
    ------
    DataProcessingError
        If the target cumulative cannot be preserved without reintroducing
        negative values, or if the adjustment window has no positive emissions
        to scale.
    """
    if easing_power < 1:
        raise DataProcessingError("easing_power must be >= 1")

    # Work with float64 for numerical precision
    adjusted_values = values.copy().astype("float64")

    # Edge case: single value or empty array
    if len(adjusted_values) <= 1:
        raise DataProcessingError("Single value or empty array")

    # Identify adjustment window (years >= first_adjustment_year)
    adjustment_mask = years >= first_adjustment_year

    if not np.any(adjustment_mask):
        # No years fall within adjustment window
        raise DataProcessingError("No years fall within adjustment window")

    # Remove negative values from adjustment window
    # We can only preserve cumulative totals by scaling positive values
    # Negatives are set to zero and positive values will be scaled to compensate
    values_with_negatives_removed = adjusted_values.copy()
    negative_mask = adjustment_mask & (values_with_negatives_removed < 0)
    values_with_negatives_removed[negative_mask] = 0.0

    # Calculate target for adjustment window
    # (target cumulative) = (sum before adjustment window) +
    # (target for adjustment window)
    # so ->
    # (target for adjustment window) = (target cumulative) -
    # (sum before adjustment window
    pre_adjustment_window_sum = np.nansum(adjusted_values[~adjustment_mask])
    target_for_adjustment_window = target_cumulative - pre_adjustment_window_sum

    # Calculate current sum in adjustment window after removing negatives
    positive_mask = adjustment_mask & ~np.isnan(values_with_negatives_removed)
    current_sum_after_clamping = np.nansum(values_with_negatives_removed[positive_mask])

    # Validate that target is achievable with non-negative values
    if target_for_adjustment_window < -tol:
        raise DataProcessingError(
            f"Target remainder after start year is negative "
            f"({target_for_adjustment_window}); "
            f"cannot preserve cumulative without reintroducing negatives."
        )

    # Edge case: no positive values to scale in adjustment window
    if current_sum_after_clamping <= tol:
        if abs(target_for_adjustment_window) > tol:
            raise DataProcessingError(
                f"No positive values after start year to scale but non-zero "
                f"target remainder ({target_for_adjustment_window}); "
                f"cannot preserve cumulative exactly."
            )
        return values_with_negatives_removed

    # Create time-based weights for ease-in scaling
    # Weights grow from 0 (at first adjustment year) to 1 (at last year)
    # This creates an ease-in curve controlled by easing_power
    adjustment_years = years[adjustment_mask]
    if len(adjustment_years) == 1:
        normalized_time = np.array([1.0])
    else:
        normalized_time = (adjustment_years - adjustment_years.min()) / (
            adjustment_years.max() - adjustment_years.min()
        )
    time_weights = np.power(normalized_time, easing_power)

    # Extract values in adjustment window
    adjustment_window_values = values_with_negatives_removed[adjustment_mask].copy()
    valid_values_mask = ~np.isnan(adjustment_window_values)

    # Calculate weighted sum (weights by both time and magnitude)
    # Larger values in later years will shoulder more of the adjustment
    weighted_sum = np.nansum(
        adjustment_window_values[valid_values_mask] * time_weights[valid_values_mask]
    )

    # Edge case: all values are zero, use uniform scaling
    if weighted_sum <= tol:
        uniform_scale = target_for_adjustment_window / current_sum_after_clamping
        adjustment_window_values[valid_values_mask] *= uniform_scale
        values_with_negatives_removed[adjustment_mask] = adjustment_window_values
        return values_with_negatives_removed

    # Calculate time-varying scaling factors using formula:
    # scale_t = 1 ± alpha * weight_t
    # where alpha (scaling_coefficient) determines the intensity of adjustment
    # If current sum > target: reduce using scale_t = 1 - alpha * weight_t
    # If current sum < target: increase using scale_t = 1 + alpha * weight_t
    if target_for_adjustment_window <= current_sum_after_clamping + tol:
        # Reduce: need to remove (current_sum - target) mass
        mass_to_remove = max(
            current_sum_after_clamping - target_for_adjustment_window, 0.0
        )
        alpha = mass_to_remove / weighted_sum
        time_varying_scales = 1.0 - alpha * time_weights
    else:
        # Increase: need to add (target - current_sum) mass
        mass_to_add = target_for_adjustment_window - current_sum_after_clamping
        alpha = mass_to_add / weighted_sum
        time_varying_scales = 1.0 + alpha * time_weights

    # Ensure scaling factors are non-negative
    time_varying_scales = np.maximum(time_varying_scales, 0.0)

    # Apply time-varying scaling to adjustment window
    scaled_adjustment_values = adjustment_window_values.copy()
    scaled_adjustment_values[valid_values_mask] = (
        adjustment_window_values[valid_values_mask]
        * time_varying_scales[valid_values_mask]
    )

    # Final renormalization for exact target (corrects numerical errors)
    scaled_sum = np.nansum(scaled_adjustment_values[valid_values_mask])
    if scaled_sum > tol:
        exact_correction = target_for_adjustment_window / scaled_sum
        scaled_adjustment_values[valid_values_mask] *= exact_correction
    else:
        if target_for_adjustment_window > tol:
            raise DataProcessingError(
                f"Degenerate case after scaling; unable to match target remainder "
                f"exactly ({target_for_adjustment_window})."
            )

    # Replace adjustment window with scaled values
    values_with_negatives_removed[adjustment_mask] = scaled_adjustment_values
    return values_with_negatives_removed


def harmonize_to_historical_with_convergence(
    scenario_ts: TimeseriesDataFrame,
    historical_ts: TimeseriesDataFrame,
    anchor_year: int,
    convergence_year: int,
    *,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
    preserve_cumulative_peak: bool = False,
    easing_power: float = 1.0,
    max_peak_diff_percent: float = 1.0,
) -> TimeseriesDataFrame:
    """
    Harmonize scenario pathways to historical data with linear convergence.

    Adjusts scenario pathways to match historical emissions at the anchor year,
    then linearly converges back to the original scenario trajectory by the
    convergence year. Optionally preserves the peak cumulative emissions of the
    original scenario through time-varying corrections applied after anchor year.

    Parameters
    ----------
    scenario_ts
        Scenario pathways to harmonize (wide format with year columns).
    historical_ts
        Historical emissions data. Must include anchor_year.
    anchor_year
        Year at which all scenarios match historical exactly.
    convergence_year
        Year by which scenarios return to original trajectory.
    group_level
        Index level identifying groups (e.g. 'iso3c'). Default 'iso3c'.
    unit_level
        Index level identifying units. Default 'unit'.
    ur
        Pint unit registry for conversions. Uses default if not provided.
    preserve_cumulative_peak
        If True, adjust years after anchor_year to preserve original scenario's
        peak cumulative emissions. Default False.
    easing_power
        Controls ease-in curve for cumulative corrections (1=linear, 2=quadratic).
        Higher values concentrate adjustments in later years. Default 1.0.
    max_peak_diff_percent
        Unused parameter kept for API compatibility. Default 1.0.

    Returns
    -------
    TimeseriesDataFrame
        Harmonized pathways with identical values at anchor_year.

    Raises
    ------
    DataProcessingError
        If anchor_year >= convergence_year or validation fails.
    """
    # Validation
    if int(anchor_year) >= int(convergence_year):
        raise DataProcessingError(
            "anchor_year must be strictly less than convergence_year"
        )

    if isinstance(scenario_ts.index, pd.MultiIndex):
        expected_idx = list(scenario_ts.index.names)
    else:
        expected_idx = [scenario_ts.index.name] if scenario_ts.index.name else ["iso3c"]

    validate_index_structure(
        scenario_ts, "scenario_ts", expected_index_names=expected_idx
    )
    validate_has_year_columns(scenario_ts, "scenario_ts")
    validate_index_structure(
        historical_ts, "historical_ts", expected_index_names=expected_idx
    )
    validate_has_year_columns(historical_ts, "historical_ts")
    validate_year_in_data(int(anchor_year), scenario_ts, "scenario_ts")
    validate_year_in_data(int(anchor_year), historical_ts, "historical_ts")

    # Setup: convert to single unit and extract year columns
    scenario = set_single_unit(scenario_ts, unit_level, ur=ur)
    historical = set_single_unit(historical_ts, unit_level, ur=ur)

    years = [int(c) for c in scenario.columns if str(c).isdigit()]
    years.sort()
    year_to_col = {int(c): c for c in scenario.columns}
    hist_year_to_col = {int(c): c for c in historical.columns}

    result = scenario.copy()
    anchor_idx = years.index(int(anchor_year))

    # Step 1: Replace years ≤ anchor_year with historical values
    for year in years:
        if year <= int(anchor_year):
            hist_col = hist_year_to_col.get(year)
            if hist_col is not None:
                col = year_to_col[year]
                result[col] = (
                    historical[hist_col].reindex(result.index).fillna(result[col])
                )

    # Step 2: Linear convergence from anchor_year to convergence_year
    hist_at_anchor = historical[hist_year_to_col[int(anchor_year)]].reindex(
        result.index
    )
    for year in years:
        if int(anchor_year) < year < int(convergence_year):
            w = (int(convergence_year) - year) / (
                int(convergence_year) - int(anchor_year)
            )
            col = year_to_col[year]
            original = scenario[col]
            result[col] = w * hist_at_anchor + (1 - w) * original

    # Step 3: Optional cumulative preservation
    if preserve_cumulative_peak:
        year_cols = [year_to_col[y] for y in years]

        for row_idx in result.index:
            original_values = scenario.loc[row_idx, year_cols].values.astype(float)
            harmonized_values = result.loc[row_idx, year_cols].values.astype(float)

            # Find peak cumulative year in original scenario
            original_cumsum = np.cumsum(original_values)
            peak_idx = int(np.argmax(original_cumsum))

            if peak_idx <= anchor_idx:
                continue

            # Calculate cumulative gap from harmonization
            original_peak_cumulative = original_cumsum[peak_idx]
            harmonized_peak_cumulative = np.cumsum(harmonized_values)[peak_idx]
            cumulative_gap = harmonized_peak_cumulative - original_peak_cumulative

            if abs(cumulative_gap) < 1e-9:
                continue

            # Distribute correction across years (anchor_year, peak_year]
            adj_start = anchor_idx + 1
            adj_end = peak_idx + 1
            adj_years = np.array(years[adj_start:adj_end])
            adj_values = harmonized_values[adj_start:adj_end].copy()

            if len(adj_years) == 0:
                continue

            # Create time weights for ease-in (0 at start, 1 at end)
            if len(adj_years) == 1:
                time_weights = np.array([1.0])
            else:
                t_norm = (adj_years - adj_years.min()) / (
                    adj_years.max() - adj_years.min()
                )
                time_weights = np.power(t_norm, easing_power)

            # Distribute gap proportionally by value magnitude and time
            weights = np.abs(adj_values) * time_weights
            total_weight = np.sum(weights)

            if total_weight > 1e-9:
                adj_values -= (weights / total_weight) * cumulative_gap
            else:
                # Fallback: uniform distribution
                adj_values -= cumulative_gap / len(adj_values)

            # Apply correction
            corrected = harmonized_values.copy()
            corrected[adj_start:adj_end] = adj_values
            result.loc[row_idx, year_cols] = corrected

    return result
