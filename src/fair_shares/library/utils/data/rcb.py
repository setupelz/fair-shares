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
    emission_category: str,
    world_co2_ffi_emissions: pd.DataFrame,
    actual_bm_lulucf_emissions: pd.DataFrame | None = None,
    bunkers_deduction_mt: float = 0.0,
    lulucf_future_deduction_mt: float = 0.0,
    lulucf_nghgi_correction_mt: float = 0.0,
    target_baseline_year: int = 2020,
    source_name: str = "",
    scenario: str = "",
    verbose: bool = True,
) -> dict[str, float | str | int]:
    """
    Process RCB from its original baseline year to 2020 baseline with adjustments.

    This function converts RCB values from any baseline year (>= 2020) to a
    standardized 2020 baseline. It also applies adjustments for international
    bunkers and LULUCF following Weber et al. (2026).

    The rebase always uses actual observational data (e.g. PRIMAP), never scenario
    projections. What enters the rebase depends on the emission category:

    - **co2-ffi**: Rebase uses fossil CO2 only. LULUCF is omitted because it
      cancels algebraically with the LULUCF decomposition term.
      ``lulucf_future_deduction_mt`` subtracts expected future (base→NZ) BM
      LULUCF, converting the published total-CO2 RCB to an FFI-only RCB.
      ``lulucf_nghgi_correction_mt`` is not used for this category.
    - **co2**: Rebase uses fossil CO2 + actual bookkeeping-model LULUCF.
      ``lulucf_nghgi_correction_mt`` applies the NGHGI-vs-BM convention gap
      from Weber et al. (2026) to re-express the budget against national-
      inventory accounting. ``lulucf_future_deduction_mt`` is not used for
      this category; the budget retains both FFI and LULUCF.

    The calculation follows these steps:
    1. Convert RCB from source unit to Mt * CO2e
    2. If baseline_year > 2020: Add actual emissions from 2020 to
       (baseline_year - 1) — fossil only for co2-ffi, fossil + BM LULUCF
       for co2
    3. Subtract bunkers deduction (always reduces budget)
    4. Apply LULUCF deduction (sign-ready from caller)

    Sign convention for deduction parameters:
    - bunkers_deduction_mt: always positive (cumulative emissions), subtracted
    - lulucf_future_deduction_mt: sign-ready from caller (added directly).
      For co2-ffi: negated BM LULUCF → positive if LULUCF is a net source
      (increases fossil budget), capped at 0 if caller applies a
      precautionary rule. Zero for co2.
    - lulucf_nghgi_correction_mt: sign-ready from caller (added directly).
      For co2: the NGHGI-vs-BM convention gap from Weber et al. (2026),
      typically negative. Zero for co2-ffi.

    Parameters
    ----------
    rcb_value : float
        Original RCB value from the source
    rcb_unit : str
        Unit of the RCB value (e.g., "Gt * CO2", "Mt * CO2")
    rcb_baseline_year : int
        The year from which the RCB is calculated (must be >= 2020)
    emission_category : str
        Emission category: "co2-ffi" or "co2". Controls whether BM LULUCF
        is included in the rebase.
    world_co2_ffi_emissions : pd.DataFrame
        World-level CO2-FFI emissions timeseries with year columns (in Mt * CO2e)
    actual_bm_lulucf_emissions : pd.DataFrame or None, optional
        Actual bookkeeping-model LULUCF CO2 emissions (e.g. PRIMAP), with year
        columns (in Mt * CO2e). Used ONLY for the co2 rebase (default: None).
    bunkers_deduction_mt : float, optional
        Total bunker CO2 emissions from 2020-2100 in Mt * CO2e (default: 0.0).
        Always positive; subtracted from budget.
    lulucf_future_deduction_mt : float, optional
        Projected future (2020/base → NZ) BM LULUCF adjustment in Mt * CO2e,
        sign-ready (default: 0.0). Non-zero for co2-ffi only, where it
        subtracts LULUCF to convert a total-CO2 RCB to FFI-only.
    lulucf_nghgi_correction_mt : float, optional
        NGHGI-vs-BM convention correction in Mt * CO2e, sign-ready
        (default: 0.0). Non-zero for co2 only, where it re-expresses the
        budget from bookkeeping-model to NGHGI accounting.
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
        - 'rcb_2020_nghgi_mt': RCB adjusted to 2020 baseline in Mt * CO2e
        - 'rcb_original_value': Original RCB value (in source units)
        - 'rcb_original_unit': Original RCB unit
        - 'baseline_year': Original baseline year
        - 'rebase_total_mt': Emissions added to rebase from source year to 2020
          (positive, Mt * CO2e); fossil only for co2-ffi, fossil + actual BM
          LULUCF for co2
        - 'rebase_fossil_mt': Fossil-only component of rebase (Mt * CO2e)
        - 'rebase_lulucf_mt': Actual BM LULUCF component of rebase (Mt * CO2e);
          only non-zero for co2
        - 'deduction_bunkers_mt': Bunker fuel deduction (negative, Mt * CO2e)
        - 'deduction_lulucf_future_mt': projected-LULUCF deduction applied
          to convert total-CO2 → FFI-only. Non-zero for co2-ffi, zero for co2.
        - 'correction_lulucf_nghgi_mt': NGHGI-vs-BM convention correction.
          Non-zero for co2, zero for co2-ffi.
        - 'net_adjustment_mt': Total change from original to 2020 baseline
          (rebase + deductions + correction, Mt * CO2e)
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

        # Fossil rebase — always from actual PRIMAP data
        rebase_fossil_mt = world_co2_ffi_emissions[year_cols].sum(axis=1).iloc[0]

        # BM LULUCF rebase — only for co2 (total CO2 needs LULUCF in rebase)
        # For co2-ffi, LULUCF is omitted because it cancels with the LULUCF
        # decomposition
        rebase_lulucf_mt = 0.0
        if emission_category == "co2" and actual_bm_lulucf_emissions is not None:
            lulucf_year_cols = [
                y for y in year_cols if y in actual_bm_lulucf_emissions.columns
            ]
            if lulucf_year_cols:
                rebase_lulucf_mt = (
                    actual_bm_lulucf_emissions[lulucf_year_cols].sum(axis=1).iloc[0]
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
            if emission_category == "co2":
                print(
                    f"      Adding actual BM LULUCF emissions "
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
    deduction_bunkers_mt = -bunkers_deduction_mt

    # Both LULUCF adjustments are sign-ready from caller and additive.
    # Only one is non-zero per category (co2-ffi uses future_deduction,
    # co2 uses nghgi_correction), but carry both fields always so the
    # schema is category-agnostic.
    deduction_lulucf_future_mt = lulucf_future_deduction_mt
    correction_lulucf_nghgi_mt = lulucf_nghgi_correction_mt

    rcb_2020_nghgi_mt = (
        rcb_adjusted_mt
        - bunkers_deduction_mt
        + deduction_lulucf_future_mt
        + correction_lulucf_nghgi_mt
    )

    # Net adjustment = total change from original to 2020 baseline
    net_adjustment_mt = (
        rebase_total_mt
        + deduction_bunkers_mt
        + deduction_lulucf_future_mt
        + correction_lulucf_nghgi_mt
    )

    if verbose:
        if bunkers_deduction_mt > 0:
            print(
                f"      Bunkers deduction (2020-2100): "
                f"{deduction_bunkers_mt:.1f} Mt * CO2e"
            )
        if deduction_lulucf_future_mt != 0:
            print(
                f"      LULUCF future deduction (2020-NZ): "
                f"{deduction_lulucf_future_mt:.1f} Mt * CO2e"
            )
        if correction_lulucf_nghgi_mt != 0:
            print(
                f"      LULUCF NGHGI correction: "
                f"{correction_lulucf_nghgi_mt:.1f} Mt * CO2e"
            )
        print(
            f"      Final RCB ({target_baseline_year} baseline): "
            f"{rcb_2020_nghgi_mt:.1f} Mt * CO2e"
        )

    return {
        "rcb_2020_nghgi_mt": round(rcb_2020_nghgi_mt),
        "rcb_original_value": rcb_value,
        "rcb_original_unit": rcb_unit,
        "baseline_year": rcb_baseline_year,
        "rebase_total_mt": round(rebase_total_mt),
        "rebase_fossil_mt": round(rebase_fossil_mt),
        "rebase_lulucf_mt": round(rebase_lulucf_mt),
        "deduction_bunkers_mt": round(deduction_bunkers_mt),
        "deduction_lulucf_future_mt": round(deduction_lulucf_future_mt),
        "correction_lulucf_nghgi_mt": round(correction_lulucf_nghgi_mt),
        "net_adjustment_mt": round(net_adjustment_mt),
    }
