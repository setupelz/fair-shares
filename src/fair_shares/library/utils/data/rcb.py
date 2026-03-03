"""
Remaining Carbon Budget (RCB) processing utilities.

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
    world_lulucf_shift_emissions: pd.DataFrame | None = None,
    bunkers_2020_2100: float = 0.0,
    lulucf_2020_2100: float = 0.0,
    target_baseline_year: int = 2020,
    source_name: str = "",
    scenario: str = "",
    verbose: bool = True,
) -> dict[str, float | str | int]:
    """
    Process RCB from its original baseline year to 2020 baseline with adjustments.

    This function converts RCB values from any baseline year (>= 2020) to a
    standardized 2020 baseline by adding historical CO2-FFI plus Gidden Direct
    LULUCF emissions. It also applies adjustments for international bunkers and
    LULUCF following Weber et al. (2026).

    The calculation follows these steps:
    1. Convert RCB from source unit to Mt * CO2e
    2. If baseline_year > 2020: Add world CO2-FFI + Gidden Direct LULUCF
       from 2020 to (baseline_year - 1)
    3. Subtract bunkers deduction (always reduces budget)
    4. Subtract LULUCF deduction (reduces budget for co2; increases for co2-ffi)

    Sign convention for deduction parameters:
    - bunkers_2020_2100: always positive (cumulative emissions), subtracted
    - lulucf_2020_2100: sign-ready from caller (added directly to budget):
        - For co2: convention gap, negative → reduces budget (per Weber)
        - For co2-ffi: negated BM LULUCF, positive → increases fossil budget

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
    world_lulucf_shift_emissions : pd.DataFrame or None, optional
        World-level Gidden Direct LULUCF CO2 timeseries with year columns
        (in Mt * CO2e). Included in the baseline shift alongside fossil CO2.
        If None, LULUCF shift is zero (default: None).
    bunkers_2020_2100 : float, optional
        Total bunker CO2 emissions from 2020-2100 in Mt * CO2e (default: 0.0).
        Always positive.
    lulucf_2020_2100 : float, optional
        LULUCF adjustment in Mt * CO2e, sign-ready (default: 0.0).
        Added directly to the budget — caller is responsible for correct sign.
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
        - 'rebase_total_mt': Emissions added to rebase from source year to 2020
          (positive, Mt * CO2e); includes fossil CO2 + Gidden Direct LULUCF
        - 'rebase_fossil_mt': Fossil-only component of rebase (Mt * CO2e)
        - 'rebase_lulucf_mt': Gidden Direct LULUCF component of rebase (Mt * CO2e)
        - 'deduction_bunkers_mt': Bunker fuel deduction (negative, Mt * CO2e)
        - 'deduction_lulucf_mt': LULUCF deduction (Mt * CO2e; sign depends on
          emission category)
        - 'net_deduction_mt': Net adjustment (rebase + deductions, Mt * CO2e)
        - 'lulucf_convention': Always "nghgi"
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

    # Initialize rebase (baseline year shift) values
    rebase_total_mt = 0.0
    rebase_fossil_mt = 0.0
    rebase_lulucf_mt = 0.0

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

        rebase_fossil_mt = world_co2_ffi_emissions[year_cols].sum(axis=1).iloc[0]
        if world_lulucf_shift_emissions is not None:
            rebase_lulucf_mt = (
                world_lulucf_shift_emissions[year_cols].sum(axis=1).iloc[0]
            )
        rebase_total_mt = rebase_fossil_mt + rebase_lulucf_mt

        if verbose:
            print(
                f"    {source_name} {scenario}: "
                f"Baseline {rcb_baseline_year} > {target_baseline_year}"
            )
            print(
                f"      Adding CO2-FFI emissions "
                f"({target_baseline_year}-{rcb_baseline_year - 1}): "
                f"+{rebase_fossil_mt:.1f} Mt * CO2e"
            )
            print(
                f"      Adding Gidden Direct LULUCF emissions "
                f"({target_baseline_year}-{rcb_baseline_year - 1}): "
                f"+{rebase_lulucf_mt:.1f} Mt * CO2e"
            )

    else:
        # Already at target baseline (rcb_baseline_year == 2020)
        if verbose:
            print(
                f"    {source_name} {scenario}: "
                f"Baseline {rcb_baseline_year} = {target_baseline_year}"
            )
            print("      No emissions adjustment needed")

    # Apply baseline rebase
    rcb_adjusted_mt = rcb_original_mt + rebase_total_mt

    # Apply bunkers deduction (always reduces budget)
    deduction_bunkers_mt = -bunkers_2020_2100

    # Apply LULUCF deduction (sign-ready from caller)
    deduction_lulucf_mt = lulucf_2020_2100

    rcb_2020_mt = rcb_adjusted_mt + deduction_bunkers_mt + deduction_lulucf_mt

    # Calculate net adjustment
    net_deduction_mt = rebase_total_mt + deduction_bunkers_mt + deduction_lulucf_mt

    if verbose:
        if bunkers_2020_2100 > 0:
            print(
                f"      Bunkers deduction (2020-2100): "
                f"{deduction_bunkers_mt:.1f} Mt * CO2e"
            )
        if lulucf_2020_2100 != 0:
            print(
                f"      LULUCF deduction (2020-2100): "
                f"{deduction_lulucf_mt:.1f} Mt * CO2e"
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
        "rebase_total_mt": round(rebase_total_mt),
        "rebase_fossil_mt": round(rebase_fossil_mt),
        "rebase_lulucf_mt": round(rebase_lulucf_mt),
        "deduction_bunkers_mt": round(deduction_bunkers_mt),
        "deduction_lulucf_mt": round(deduction_lulucf_mt),
        "net_deduction_mt": round(net_deduction_mt),
        "lulucf_convention": "nghgi",
    }
