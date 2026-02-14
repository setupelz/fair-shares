"""
RCB (Remaining Carbon Budget) processing utilities.

Functions for parsing RCB scenario strings and converting RCB values between
different baseline years with adjustments for bunkers and LULUCF.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils.units import get_default_unit_registry

if TYPE_CHECKING:
    from fair_shares.library.utils.dataframes import TimeseriesDataFrame


def parse_rcb_scenario(scenario_string: str) -> tuple[str, str]:
    """
    Parse RCB scenario string into climate assessment and quantile.

    RCB scenario strings follow the format "TEMPpPROB" where TEMP is the
    temperature target (e.g., "1.5" or "2") and PROB is the probability
    as a percentage (e.g., "50" or "66").

    Parameters
    ----------
    scenario_string : str
        RCB scenario string (e.g., "1.5p50", "2p66")

    Returns
    -------
    tuple[str, str]
        A tuple of (climate_assessment, quantile) as strings
        - climate_assessment: Temperature target with "C" suffix (e.g., "1.5C")
        - quantile: Probability as decimal string (e.g., "0.5")
    """
    parts = scenario_string.split("p")
    if len(parts) != 2:
        raise DataProcessingError(
            f"Invalid RCB scenario format: {scenario_string}. "
            f"Expected format: 'TEMPpPROB' (e.g., '1.5p50')"
        )

    temperature = parts[0]
    probability = parts[1]

    # Format temperature target with C suffix
    climate_assessment = f"{temperature}C"

    # Convert probability to decimal quantile (e.g., "50" -> "0.5")
    try:
        quantile = str(int(probability) / 100)
    except ValueError:
        raise DataProcessingError(
            f"Invalid probability value in RCB scenario: {probability}. "
            f"Expected integer percentage (e.g., '50', '66')"
        )

    return climate_assessment, quantile


def calculate_budget_from_rcb(
    rcb_value: float,
    allocation_year: int,
    world_scenario_emissions_ts: TimeseriesDataFrame,
    verbose: bool = True,
) -> float:
    """
    Calculate total budget to allocate based on RCB value and allocation year.

    RCB (Remaining Carbon Budget) values represent the remaining budget FROM 2020
    onwards. The total budget to allocate depends on the allocation year:

    - If allocation_year < 2020: Add historical emissions (allocation_year to
      2019)
    - If allocation_year == 2020: Use RCB directly
    - If allocation_year > 2020: Subtract emissions already used (2020 to
      allocation_year-1)

    This ensures that the budget allocation is consistent regardless of which year
    is chosen as the allocation starting point.

    All values are in Mt * CO2. RCB values are converted from Gt to Mt during
    preprocessing to match the units used in world_scenario_emissions_ts.

    Parameters
    ----------
    rcb_value : float
        Remaining Carbon Budget value in Mt CO2 (from 2020 onwards)
    allocation_year : int
        Year when budget allocation should start
    world_scenario_emissions_ts : TimeseriesDataFrame
        World scenario emissions timeseries data with year columns (in Mt CO2)
    verbose : bool, optional
        Whether to print detailed calculation information (default: True)

    Returns
    -------
    float
        Total budget to allocate in Mt CO2
    """
    if allocation_year < 2020:
        # Add historical emissions before RCB period
        year_cols = [
            str(y)
            for y in range(allocation_year, 2020)
            if str(y) in world_scenario_emissions_ts.columns
        ]

        if not year_cols:
            raise DataProcessingError(
                f"No emission data found for years {allocation_year}-2019. "
                f"Cannot calculate historical component of budget."
            )

        historical_emissions = (
            world_scenario_emissions_ts[year_cols].sum(axis=1).iloc[0]
        )
        total_budget = round(historical_emissions + rcb_value)

        if verbose:
            print(
                f"    Allocation year {allocation_year} < 2020: "
                f"Historical {historical_emissions:.1f} + RCB {rcb_value:.1f} "
                f"= {total_budget:.1f} Mt CO2"
            )

    elif allocation_year == 2020:
        # RCB applies directly
        total_budget = round(rcb_value)

        if verbose:
            print(
                f"    Allocation year {allocation_year} = 2020: "
                f"RCB {rcb_value:.1f} Mt CO2"
            )

    else:  # allocation_year > 2020
        # Subtract emissions already used from RCB
        year_cols = [
            str(y)
            for y in range(2020, allocation_year)
            if str(y) in world_scenario_emissions_ts.columns
        ]

        if not year_cols:
            raise DataProcessingError(
                f"No emission data found for years 2020-{allocation_year - 1}. "
                f"Cannot calculate emissions already used from RCB."
            )

        emissions_used = world_scenario_emissions_ts[year_cols].sum(axis=1).iloc[0]
        total_budget = round(rcb_value - emissions_used)

        if verbose:
            print(
                f"    Allocation year {allocation_year} > 2020: "
                f"RCB {rcb_value:.1f} - Used {emissions_used:.1f} "
                f"= {total_budget:.1f} Mt CO2"
            )

    return total_budget


def process_rcb_to_2020_baseline(
    rcb_value: float,
    rcb_unit: str,
    rcb_baseline_year: int,
    world_co2_ffi_emissions: pd.DataFrame,
    bunkers_2020_2100: float = 0.0,
    lulucf_2020_2100: float = 0.0,
    target_baseline_year: int = 2020,
    source_name: str = "",
    scenario: str = "",
    verbose: bool = True,
) -> dict[str, float | str | int]:
    """
    Process RCB from its original baseline year to 2020 baseline with adjustments.

    This function converts RCB values from any baseline year (>= 2020) to a standardized
    2020 baseline by adding historical CO2-FFI emissions. It also applies adjustments
    for international bunkers and LULUCF emissions.

    The calculation follows these steps:
    1. Convert RCB from source unit to Mt * CO2e
    2. If baseline_year > 2020: Add world emissions from 2020 to (baseline_year - 1)
    3. Add bunkers adjustment (stored as negative to reduce budget)
    4. Add lulucf adjustment (stored as negative to reduce budget)

    Note: Bunkers and LULUCF are returned as negative values to make the total
    adjustment calculation clearer as a simple sum of all adjustments.

    Parameters
    ----------
    rcb_value : float
        Original RCB value from the source
    rcb_unit : str
        Unit of the RCB value (e.g., "Gt * CO2", "Mt * CO2")
    rcb_baseline_year : int
        The year from which the RCB is calculated (must be >= 2020)
    world_co2_ffi_emissions : pd.DataFrame
        World-level CO2-FFI emissions timeseries with year columns (in Mt * CO2e)
    bunkers_2020_2100 : float, optional
        Total bunker CO2 emissions from 2020-2100 in Mt * CO2e (default: 0.0)
    lulucf_2020_2100 : float, optional
        Total LULUCF CO2 emissions from 2020-2100 in Mt * CO2e (default: 0.0)
    target_baseline_year : int, optional
        Target baseline year for standardization (default: 2020)
    source_name : str, optional
        Name of the RCB source for logging (default: "")
    scenario : str, optional
        Scenario name for logging (default: "")
    verbose : bool, optional
        Whether to print detailed calculation information (default: True)

    Returns
    -------
    dict
        Dictionary containing:
        - 'rcb_2020_mt': RCB adjusted to 2020 baseline in Mt * CO2e
        - 'rcb_original_value': Original RCB value (in source units)
        - 'rcb_original_unit': Original RCB unit
        - 'baseline_year': Original baseline year
        - 'emissions_adjustment_mt': Emissions added (positive value, Mt * CO2e)
        - 'bunkers_adjustment_mt': Bunkers adjustment (negative value, Mt * CO2e)
        - 'lulucf_adjustment_mt': LULUCF adjustment (negative value, Mt * CO2e)
        - 'total_adjustment_mt': Total adjustment (sum of above, Mt * CO2e)
    """
    # Get unit registry
    ureg = get_default_unit_registry()

    # Convert original RCB to Mt * CO2e using Pint
    try:
        rcb_quantity = rcb_value * ureg(rcb_unit)
        rcb_original_mt = rcb_quantity.to("Mt * CO2e").magnitude
    except Exception as e:
        raise DataProcessingError(
            f"Failed to convert RCB from '{rcb_unit}' to 'Mt * CO2e': {e}"
        )

    # Initialize adjustments
    emissions_adjustment_mt = 0.0

    # Calculate emissions adjustment based on baseline year
    if rcb_baseline_year > target_baseline_year:
        # Need to add emissions from 2020 to (baseline_year - 1)
        year_cols = [
            str(y)
            for y in range(target_baseline_year, rcb_baseline_year)
            if str(y) in world_co2_ffi_emissions.columns
        ]

        if not year_cols:
            raise DataProcessingError(
                f"No CO2-FFI emission data found for years "
                f"{target_baseline_year}-{rcb_baseline_year - 1}. "
                f"Cannot calculate emissions adjustment for RCB conversion."
            )

        emissions_adjustment_mt = world_co2_ffi_emissions[year_cols].sum(axis=1).iloc[0]

        if verbose:
            print(
                f"    {source_name} {scenario}: "
                f"Baseline {rcb_baseline_year} > {target_baseline_year}"
            )
            print(
                f"      Adding CO2-FFI emissions "
                f"({target_baseline_year}-{rcb_baseline_year - 1}): "
                f"+{emissions_adjustment_mt:.1f} Mt * CO2e"
            )

    else:
        # Already at target baseline (rcb_baseline_year == 2020)
        if verbose:
            print(
                f"    {source_name} {scenario}: "
                f"Baseline {rcb_baseline_year} = {target_baseline_year}"
            )
            print("      No emissions adjustment needed")

    # Apply emissions adjustment
    rcb_adjusted_mt = rcb_original_mt + emissions_adjustment_mt

    # Apply bunkers and LULUCF adjustments
    # Store as negative values to make the calculation clearer
    bunkers_adjustment_mt = -bunkers_2020_2100
    lulucf_adjustment_mt = -lulucf_2020_2100

    rcb_2020_mt = rcb_adjusted_mt + bunkers_adjustment_mt + lulucf_adjustment_mt

    # Calculate total adjustment
    total_adjustment_mt = (
        emissions_adjustment_mt + bunkers_adjustment_mt + lulucf_adjustment_mt
    )

    if verbose:
        if bunkers_2020_2100 > 0:
            print(
                f"      Bunkers adjustment (2020-2100): "
                f"{bunkers_adjustment_mt:.1f} Mt * CO2e"
            )
        if lulucf_2020_2100 > 0:
            print(
                f"      LULUCF adjustment (2020-2100): "
                f"{lulucf_adjustment_mt:.1f} Mt * CO2e"
            )
        print(
            f"      Final RCB ({target_baseline_year} baseline): "
            f"{rcb_2020_mt:.1f} Mt * CO2e"
        )

    return {
        "rcb_2020_mt": round(rcb_2020_mt),
        "rcb_original_value": rcb_value,
        "rcb_original_unit": rcb_unit,
        "baseline_year": rcb_baseline_year,
        "emissions_adjustment_mt": round(emissions_adjustment_mt),
        "bunkers_adjustment_mt": round(bunkers_adjustment_mt),
        "lulucf_adjustment_mt": round(lulucf_adjustment_mt),
        "total_adjustment_mt": round(total_adjustment_mt),
    }
