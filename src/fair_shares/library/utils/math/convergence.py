"""
Convergence solver and speed validation for pathway allocations.

This module contains the mathematical solver logic for finding optimal convergence
parameters in cumulative per capita convergence allocations:
- Binary search for minimum convergence speed
- Fallback optimization for infeasible targets
- Convergence speed validation

These functions orchestrate the mathematical calculations to find valid
convergence solutions that satisfy cumulative target constraints.
"""

from __future__ import annotations

import pandas as pd

from fair_shares.library.error_messages import format_error
from fair_shares.library.exceptions import AllocationError


def validate_convergence_speed(
    convergence_speed: float,
    sorted_columns: list,
    start_column: str | int | float,
    year_fraction_of_cumulative_emissions: pd.Series,
    initial_shares: pd.Series,
    target_cumulative_shares: pd.Series,
) -> tuple[bool, pd.Series | None]:
    """
    Validate that a convergence_speed produces valid shares hitting cumulative targets.

    We need yearly shares to transition from initial_shares (yearly share for
    starting year) to eventually satisfy target_cumulative_shares (cumulative
    sum of yearly shares of emissions over all years for each country).

    So the constraint is that the cumulative sum of yearly shares of emissions over all
    years must equal the cumulative target shares for each country:

        sum_t [year_fraction_of_cumulative_emissions(t) * yearly_share(t)]
            = target_cumulative_shares

    where:
        - year_fraction_of_cumulative_emissions(t): fraction of total cumulative
            world emissions that occur in year t for each country (sums to 1)
        - yearly_share(t): each country's yearly allocation share in year t (sums to 1)
        - target_cumulative_shares: cumulative target (sum of yearly shares of emissions
            over all years for each country, sums to 1)

    Since we want to converge, rather than jump instantly, we model this using an
    exponential decay where each year's share moves toward a long_run_shares value:

        yearly_share(t+1) = yearly_share(t) + speed * (long_run_shares
            - yearly_share(t))

    where:
        - speed: convergence rate (0 = no change, 1 = instant jump)
        - long_run_shares: asymptotic year share that each year converges
            toward (not cumulative - this is a single asymptotic year value)
        - initial_shares: yearly share for the starting year (year 0)

    By using the exponential decay convergence function we reduce the problem from N
    unknowns to 1 unknown (long_run_shares). We know initial_shares, convergence_speed
    (which determines how fast initial_shares decay as (1-speed)^t), and
    target_cumulative_shares. So, we can calculate how much of the cumulative target
    shares comes from initial_shares (w = total_initial_contribution, accounting for
    their decaying contribution to cumulative target shares over time). The rest (1-w)
    must come from long_run_shares, so we solve:
    long_run_shares = (target_cumulative_shares - initial_shares*w) / (1-w).

    The convergence speed is valid only if long_run_shares are all in [0, 1] (each
    country's share is valid). Note: if initial_shares and target_cumulative_shares
    both sum to 1, then long_run_shares automatically sums to 1 (mathematically
    guaranteed), so we only need to check individual bounds. The intuition for the
    [0, 1] bound is that if long_run_shares are not in [0, 1], then the speed is
    invalid because it would require impossible destinations (negative or >100%) to
    compensate, which would occur over the finite time horizon we care about.

    The caller uses this function to find the minimum valid speed: the smoothest
    transition that still achieves cumulative targets.

    Parameters
    ----------
    convergence_speed : float
        The convergence speed to validate (0 to 1).
    sorted_columns : list
        Year columns in sorted order.
    start_column : str | int | float
        Column label for first allocation year.
    year_fraction_of_cumulative_emissions : pd.Series
        Fraction of cumulative emissions in each year (sums to 1).
    initial_shares : pd.Series
        Initial emission shares at start year.
    target_cumulative_shares : pd.Series
        Target cumulative shares to achieve.

    Returns
    -------
    tuple[bool, pd.Series | None]
        (is_valid, long_run_shares) where:
        - is_valid: boolean indicating whether the speed is valid
        - long_run_shares: yearly share value that satisfies the cumulative constraint
            where long_run_shares is not used anywhere but just reported.

    """
    try:
        start_idx = sorted_columns.index(start_column)
    except ValueError:
        return False, None

    if start_idx + 1 >= len(sorted_columns):
        return False, None

    start_fraction_of_cumulative_emissions = float(
        year_fraction_of_cumulative_emissions.get(start_column, float("nan"))
    )
    if pd.isna(start_fraction_of_cumulative_emissions):
        return False, None

    # Calculate weighted contribution of initial_shares from years after start.
    # Each year t contributes: fraction_of_cumulative_emissions(t) * (1-speed)^t
    lambda_factor = 1.0 - convergence_speed
    cmltv_share = 0.0
    beta_value = lambda_factor

    for column in sorted_columns[start_idx + 1 :]:
        fraction_of_cumulative_emissions = float(
            year_fraction_of_cumulative_emissions.get(column, float("nan"))
        )
        if pd.isna(fraction_of_cumulative_emissions):
            return False, None
        cmltv_share += fraction_of_cumulative_emissions * beta_value
        beta_value *= lambda_factor

    # Calculate total contribution of initial_shares (w) to cumulative target.
    # Year 0: full weight; Year t>0: decays as (1-speed)^t
    total_initial_contribution = start_fraction_of_cumulative_emissions + cmltv_share
    denominator = 1.0 - total_initial_contribution
    if denominator <= 1e-12:
        return False, None

    # Solve: target = initial*w + long_run*(1-w)
    # => long_run = (target - initial*w)/(1-w)
    long_run_shares = (
        target_cumulative_shares - initial_shares * total_initial_contribution
    ) / denominator

    # Validate: long_run_shares must be strictly in [0, 1] (no tolerance).
    # This ensures clipping on line 685 won't change the values and break
    # cumulative targets.
    if (long_run_shares < 0.0).any() or (long_run_shares > 1.0).any():
        return False, None

    return True, long_run_shares


def find_minimum_convergence_speed(
    sorted_columns: list,
    start_column: str | int | float,
    year_fraction_of_cumulative_emissions: pd.Series,
    initial_shares: pd.Series,
    target_cumulative_shares: pd.Series,
    diagnostic_params: dict | None = None,
    strict: bool = True,
    max_convergence_speed: float = 0.9,
) -> tuple[float, pd.Series, dict[str, float] | None, pd.Series | None]:
    """
    Find the minimum convergence_speed that produces valid target cumulative shares.

    Uses binary search between 0.001 and max_convergence_speed.

    Parameters
    ----------
    sorted_columns : list
        Year columns in sorted order.
    start_column : str | int | float
        Column label for first allocation year.
    year_fraction_of_cumulative_emissions : pd.Series
        Fraction of cumulative emissions in each year.
    initial_shares : pd.Series
        Initial emission shares at start year.
    target_cumulative_shares : pd.Series
        Target cumulative shares to achieve.
    diagnostic_params : dict | None, optional
        Parameters for error messages (approach name, years, weights).
    strict : bool, optional
        If True (default), raise AllocationError when exact targets cannot be achieved.
        If False, accept approximate targets and generate warnings showing deviations.
    max_convergence_speed : float, optional
        Maximum allowed convergence speed (0 to 1.0). Default 0.9.
        Lower values create smoother pathways. When targets cannot be achieved
        within this speed, strict=False will generate warnings.

    Returns
    -------
    tuple[float, pd.Series, dict[str, float] | None, pd.Series | None]
        - Convergence speed (0.001 to max_convergence_speed)
        - Long-run shares
        - Adjustment warnings dict: Maps iso3c -> (achieved/target) ratio.
          None if exact targets achieved or strict=True raised error.
        - Achieved cumulative shares (may differ from targets if speed limited).
          None if exact targets achieved or strict=True raised error.
    """
    # First check if max_convergence_speed is feasible
    is_valid, long_run_shares = validate_convergence_speed(
        max_convergence_speed,
        sorted_columns,
        start_column,
        year_fraction_of_cumulative_emissions,
        initial_shares,
        target_cumulative_shares,
    )
    if not is_valid:
        # Infeasible: even max_convergence_speed doesn't work
        if not strict:
            # Use fallback: find nearest feasible solution
            adjusted_long_run, warnings, adjusted_cumulative = (
                _find_feasible_long_run_shares(
                    initial_shares,
                    target_cumulative_shares,
                    year_fraction_of_cumulative_emissions,
                    sorted_columns,
                    start_column,
                )
            )
            # Return with max_convergence_speed, adjusted shares, warnings,
            # and adjusted cumulative. Note: we return a 4-tuple here instead
            # of 3 to include adjusted cumulative
            return (
                max_convergence_speed,
                adjusted_long_run,
                warnings,
                adjusted_cumulative,
            )

        # Strict mode: raise error with diagnostics
        # Compute what long_run_shares would be (ignoring validity) for diagnostics
        try:
            start_frac = float(
                year_fraction_of_cumulative_emissions.get(start_column, 0)
            )
            # With speed=1.0, total_initial_contribution = start_frac (cmltv_share=0)
            denom = 1.0 - start_frac
            if denom > 1e-12:
                debug_long_run = (
                    target_cumulative_shares - initial_shares * start_frac
                ) / denom
                debug_min, debug_max = debug_long_run.min(), debug_long_run.max()

                # Build detailed diagnostic message
                approach_name = (
                    diagnostic_params.get("approach", "unknown")
                    if diagnostic_params
                    else "unknown"
                )
                msg = (
                    f"Allocation approach '{approach_name}' failed:\n"
                    f"Cannot converge to target cumulative shares even with "
                    f"maximum convergence speed={max_convergence_speed}. "
                    f"Target shares would require invalid long-run shares: "
                    f"[{debug_min:.4f}, {debug_max:.4f}] "
                    f"(valid range is [0, 1]).\n\n"
                )

                # Add allocation parameters if provided
                if diagnostic_params:
                    msg += "Allocation parameters:\n"
                    for key, val in diagnostic_params.items():
                        if key != "approach":  # Already shown at top
                            msg += f"  {key}: {val}\n"
                    msg += "\n"

                # Identify problematic countries
                invalid_mask = (debug_long_run < 0.0) | (debug_long_run > 1.0)
                if invalid_mask.any():
                    problematic = debug_long_run[invalid_mask].sort_values()
                    n_show = min(10, len(problematic))
                    msg += (
                        f"Countries with invalid long-run shares "
                        f"({len(problematic)} total, showing worst {n_show}):\n"
                    )

                    for country, long_run_val in problematic.head(n_show).items():
                        initial = initial_shares.get(country, float("nan"))
                        target = target_cumulative_shares.get(country, float("nan"))
                        msg += (
                            f"  {country}: long_run={long_run_val:.6f}, "
                            f"initial_share={initial:.6f}, "
                            f"target_cumulative_share={target:.6f}\n"
                        )
                    msg += "\n"

                msg += (
                    "This means the targets are mathematically impossible "
                    "given the time horizon and max_convergence_speed. "
                    "Try: increasing max_convergence_speed, adjusting weights, "
                    "or extending the time horizon."
                )
            else:
                msg = (
                    f"Cannot find valid convergence: first year contains "
                    f"{start_frac * 100:.1f}% of total cumulative emissions, "
                    f"leaving insufficient time for convergence. "
                    f"Try starting earlier or extending the time horizon."
                )
        except Exception as e:
            msg = f"Cannot find valid convergence solution. Internal error: {e}"
        raise AllocationError(msg)

    min_speed = 0.001
    max_speed = max_convergence_speed
    tol = 1e-6
    best_speed = max_convergence_speed
    best_long_run_shares = long_run_shares

    while max_speed - min_speed > tol:
        mid_speed = (min_speed + max_speed) / 2.0
        is_valid, long_run_shares = validate_convergence_speed(
            mid_speed,
            sorted_columns,
            start_column,
            year_fraction_of_cumulative_emissions,
            initial_shares,
            target_cumulative_shares,
        )
        if is_valid:
            best_speed = mid_speed
            best_long_run_shares = long_run_shares
            max_speed = mid_speed
        else:
            min_speed = mid_speed

    # Check if we hit the max_convergence_speed limit
    # Calculate actual cumulative shares achieved with best_speed
    start_idx = sorted_columns.index(start_column)
    start_frac = year_fraction_of_cumulative_emissions[start_column]

    # Calculate total contribution of initial_shares
    lambda_factor = 1.0 - best_speed
    cmltv_share = 0.0
    beta_value = lambda_factor
    for column in sorted_columns[start_idx + 1 :]:
        fraction = year_fraction_of_cumulative_emissions.get(column, 0.0)
        cmltv_share += fraction * beta_value
        beta_value *= lambda_factor
    total_initial_contribution = start_frac + cmltv_share

    # Calculate achieved cumulative shares
    achieved_cumulative = (
        initial_shares * total_initial_contribution
        + best_long_run_shares * (1.0 - total_initial_contribution)
    )

    # Check deviation from targets
    max_deviation = (achieved_cumulative - target_cumulative_shares).abs().max()

    if max_deviation > 1e-4:  # Significant deviation (0.01%)
        if not strict:
            # Generate warnings showing adjustment factors
            adjustment_warnings = {}
            for iso3c in target_cumulative_shares.index:
                target = target_cumulative_shares[iso3c]
                achieved = achieved_cumulative[iso3c]
                if target > 1e-10:  # Avoid division by near-zero
                    adjustment_warnings[iso3c] = achieved / target
                else:
                    adjustment_warnings[iso3c] = (
                        1.0 if achieved < 1e-10 else float("inf")
                    )

            return (
                best_speed,
                best_long_run_shares,
                adjustment_warnings,
                achieved_cumulative,
            )
        else:
            # Strict mode: raise error
            approach_name = (
                diagnostic_params.get("approach", "unknown")
                if diagnostic_params
                else "unknown"
            )
            first_year = sorted_columns[0] if sorted_columns else "unknown"
            last_year = sorted_columns[-1] if sorted_columns else "unknown"
            raise AllocationError(
                format_error(
                    "infeasible_convergence",
                    speed=max_convergence_speed,
                    first_year=first_year,
                    last_year=last_year,
                )
            )

    return best_speed, best_long_run_shares, None, None


def _find_feasible_long_run_shares(
    initial_shares: pd.Series,
    target_cumulative_shares: pd.Series,
    year_fraction_of_cumulative_emissions: pd.Series,
    sorted_columns: list,
    start_column: str | int | float,
) -> tuple[pd.Series, dict[str, float], pd.Series]:
    """
    Find nearest feasible long-run shares when strict mode fails.

    Strategy:
    1. Identify countries with invalid long-run shares (< 0 or > 1)
    2. Clip invalid shares to [0, 1] bounds
    3. Recalculate cumulative targets based on clipped long-run shares
    4. Adjust remaining countries proportionally to maintain sum = 1.0
    5. Return adjusted shares and warning factors

    Parameters
    ----------
    initial_shares : pd.Series
        Initial emission shares
    target_cumulative_shares : pd.Series
        Original target cumulative shares (may be infeasible)
    year_fraction_of_cumulative_emissions : pd.Series
        Fraction of cumulative emissions in each year
    sorted_columns : list
        Year columns in order
    start_column : str | int | float
        First allocation year

    Returns
    -------
    tuple[pd.Series, dict[str, float], pd.Series]
        - Adjusted long-run shares (all valid)
        - Dict mapping iso3c -> adjustment_factor for countries with warnings
        - Adjusted cumulative targets that correspond to the adjusted long-run shares
    """
    # Calculate what long-run shares would be needed (may be invalid)
    start_idx = sorted_columns.index(start_column)
    start_frac = year_fraction_of_cumulative_emissions[start_column]
    denominator = year_fraction_of_cumulative_emissions[
        sorted_columns[start_idx + 1 :]
    ].sum()

    # Calculate unconstrained long-run shares
    total_initial_contribution = initial_shares * start_frac
    unconstrained_long_run = (
        target_cumulative_shares - total_initial_contribution
    ) / denominator

    # Identify countries needing adjustment
    needs_clip_low = unconstrained_long_run < 0.0
    needs_clip_high = unconstrained_long_run > 1.0
    needs_adjustment = needs_clip_low | needs_clip_high

    # Clip to valid range
    clipped_long_run = unconstrained_long_run.copy()
    clipped_long_run[needs_clip_low] = 0.0
    clipped_long_run[needs_clip_high] = 1.0

    # Calculate what cumulative shares these clipped values would achieve
    achieved_cumulative = total_initial_contribution + clipped_long_run * denominator

    # For countries that were clipped, lock in their achieved cumulative
    # For other countries, adjust proportionally to maintain sum = 1.0
    adjustment_warnings = {}

    if needs_adjustment.any():
        # Total cumulative that must be distributed among non-clipped countries
        locked_cumulative = achieved_cumulative[needs_adjustment].sum()
        remaining_cumulative = 1.0 - locked_cumulative

        # Original targets for non-clipped countries
        non_clipped = ~needs_adjustment
        original_remaining_targets = target_cumulative_shares[non_clipped]
        original_remaining_sum = original_remaining_targets.sum()

        # Adjust proportionally
        if original_remaining_sum > 0:
            adjustment_factor = remaining_cumulative / original_remaining_sum
            adjusted_targets = original_remaining_targets * adjustment_factor

            # Recalculate long-run shares for adjusted countries
            adjusted_long_run = (
                adjusted_targets - total_initial_contribution[non_clipped]
            ) / denominator

            clipped_long_run[non_clipped] = adjusted_long_run

            # Track adjustment factors for warnings
            # For clipped countries: show ratio of achieved vs. target
            for iso3c in target_cumulative_shares[needs_adjustment].index:
                achieved = achieved_cumulative[iso3c]
                target = target_cumulative_shares[iso3c]
                if target > 0:
                    adjustment_warnings[iso3c] = achieved / target
                else:
                    adjustment_warnings[iso3c] = 0.0

            # For adjusted countries: show ratio of adjusted vs. original target
            for iso3c in target_cumulative_shares[non_clipped].index:
                adjustment_warnings[iso3c] = adjustment_factor
        else:
            # Edge case: all non-clipped had zero target, distribute equally
            n_remaining = non_clipped.sum()
            if n_remaining > 0:
                equal_share = remaining_cumulative / n_remaining
                adjusted_long_run = (
                    equal_share - total_initial_contribution[non_clipped]
                ) / denominator
                clipped_long_run[non_clipped] = adjusted_long_run

                for iso3c in target_cumulative_shares[non_clipped].index:
                    adjustment_warnings[iso3c] = float("inf")  # Infinite adjustment

    # Renormalize to ensure exact sum = 1.0
    # (numerical precision safety)
    final_cumulative = total_initial_contribution + clipped_long_run * denominator
    clipped_long_run = clipped_long_run * (1.0 / final_cumulative.sum())

    # Recalculate final cumulative targets based on normalized long-run shares
    adjusted_cumulative = total_initial_contribution + clipped_long_run * denominator

    return clipped_long_run, adjustment_warnings, adjusted_cumulative
