"""
Remaining Carbon Budget (RCB) processing utilities.

Functions for parsing RCB scenario strings and converting RCB values between
different baseline years with adjustments for bunkers and LULUCF.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import pandas as pd

from fair_shares.library.exceptions import ConfigurationError, DataProcessingError
from fair_shares.library.utils.units import get_default_unit_registry

if TYPE_CHECKING:
    from fair_shares.library.utils.dataframes import TimeseriesDataFrame

# AR6 category behind each budget label under the "ar6-category" rule.
AR6_CATEGORY_BY_RCB_LABEL = {"1.5p50": "C1", "2p83": "C2", "2p66": "C3"}

# AR6 metadata column that the "peak-warming-band" rule reads.
PEAK_WARMING_COLUMN = "Median peak warming (MAGICCv7.5.3)"

# Scenario metadata column that holds ``net_zero_year`` of each scenario.
NET_ZERO_YEAR_COLUMN = "net_zero_year"

# A source in rcbs.yaml without a ``scenario_selection`` field uses this rule.
DEFAULT_SCENARIO_SELECTION = "ar6-category"
DEFAULT_PEAK_WARMING_BAND_HALF_WIDTH = 0.05

# Largest number of trailing rebase years that take the last observed value.
DEFAULT_REBASE_FILL_MAX_YEARS = 1


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


def _ar6_category(source: str, label: str) -> str:
    """Return the AR6 category mapped to a budget label, or raise."""
    if label not in AR6_CATEGORY_BY_RCB_LABEL:
        raise ConfigurationError(
            f"RCB source '{source}', label '{label}': no AR6 category is mapped "
            f"to this label (mapped labels: {list(AR6_CATEGORY_BY_RCB_LABEL)}) "
            f"and the source does not use the peak-warming band rule. Set "
            f"'scenario_selection: peak-warming-band' for this source in "
            f"rcbs.yaml, or use a mapped label."
        )
    return AR6_CATEGORY_BY_RCB_LABEL[label]


def net_zero_year(co2_emissions: pd.Series) -> int | None:
    """
    Return the first year in which total CO2 emissions are at or below zero.

    The deductions of a budget end in this year, and the peak-warming band
    keeps only scenarios that have one.

    Parameters
    ----------
    co2_emissions : pd.Series
        Total CO2 emissions of one scenario, indexed by year in ascending order

    Returns
    -------
    int or None
        The net-zero year, or None when emissions stay above zero
    """
    for year, value in co2_emissions.items():
        if value <= 0:
            return int(year)
    return None


def rcb_scenario_set_key(source: str, label: str, selection: str) -> str:
    """
    Name the scenario set behind the deductions of one budget.

    The key identifies the entry in ``rcb_scenario_adjustments.yaml`` and the
    ``lulucf_shift_median_{key}.csv`` file that notebook 104 writes.

    Parameters
    ----------
    source : str
        RCB source key in rcbs.yaml (e.g., "forster_2026")
    label : str
        Budget label (e.g., "1.7p50")
    selection : str
        Scenario selection rule of the source: "ar6-category" or
        "peak-warming-band"

    Returns
    -------
    str
        - "ar6-category": the label itself (e.g., "1.5p50")
        - "peak-warming-band": the temperature only (e.g., "peak-warming-1.7C"),
          because one band serves every likelihood of its temperature

    Raises
    ------
    ConfigurationError
        If the rule is unknown, or the label has no AR6 category under the
        "ar6-category" rule
    """
    climate_assessment, _ = parse_rcb_scenario(label)
    if selection == "ar6-category":
        _ar6_category(source, label)
        return label
    if selection == "peak-warming-band":
        return f"peak-warming-{climate_assessment}"
    raise ConfigurationError(
        f"RCB source '{source}': unknown scenario_selection '{selection}'. "
        f"Expected 'ar6-category' or 'peak-warming-band'."
    )


def select_rcb_scenario_set(
    metadata: pd.DataFrame,
    source: str,
    label: str,
    selection: str,
    band_half_width: float = DEFAULT_PEAK_WARMING_BAND_HALF_WIDTH,
) -> pd.DataFrame:
    """
    Select the AR6 scenarios behind the deductions of one budget.

    Parameters
    ----------
    metadata : pd.DataFrame
        AR6 scenario metadata, one row per scenario, with the columns
        "Category" and "Median peak warming (MAGICCv7.5.3)". The
        "peak-warming-band" rule also needs "net_zero_year" (see
        ``net_zero_year``), empty for a scenario that never reaches net zero.
    source : str
        RCB source key in rcbs.yaml (e.g., "forster_2026")
    label : str
        Budget label (e.g., "1.7p50")
    selection : str
        Scenario selection rule of the source:

        - "ar6-category": every scenario in the AR6 category mapped to the
          label (1.5p50 -> C1, 2p83 -> C2, 2p66 -> C3)
        - "peak-warming-band": every scenario whose median peak warming lies
          in [T - band_half_width, T + band_half_width), where T is the
          budget temperature, and that reaches net-zero CO2. A remaining
          carbon budget runs to net-zero CO2, so a scenario that never reaches
          it is excluded. The likelihood in the label plays no role.
    band_half_width : float, optional
        Half-width of the peak-warming band in degrees C (default: 0.05)

    Returns
    -------
    pd.DataFrame
        The selected rows of ``metadata``

    Raises
    ------
    ConfigurationError
        If the rule is unknown, the label has no AR6 category under the
        "ar6-category" rule, or the metadata lack "net_zero_year" under the
        "peak-warming-band" rule
    DataProcessingError
        If the rule selects no scenario
    """
    climate_assessment, _ = parse_rcb_scenario(label)
    if selection == "ar6-category":
        category = _ar6_category(source, label)
        selected = metadata[metadata["Category"] == category]
        criterion = f"AR6 category {category}"
    elif selection == "peak-warming-band":
        temperature = float(climate_assessment.removesuffix("C"))
        # Rounding keeps the bounds exact decimals (1.7 - 0.05 gives 1.65).
        lower = round(temperature - band_half_width, 6)
        upper = round(temperature + band_half_width, 6)
        if NET_ZERO_YEAR_COLUMN not in metadata.columns:
            raise ConfigurationError(
                f"RCB source '{source}': the peak-warming band rule needs the "
                f"scenario metadata column '{NET_ZERO_YEAR_COLUMN}'."
            )
        peak_warming = metadata[PEAK_WARMING_COLUMN]
        # A budget runs to net-zero CO2, so the band keeps scenarios that reach it.
        selected = metadata[
            (peak_warming >= lower)
            & (peak_warming < upper)
            & metadata[NET_ZERO_YEAR_COLUMN].notna()
        ]
        criterion = (
            f"median peak warming in the {climate_assessment} band "
            f"[{lower}, {upper}) and a net-zero CO2 year"
        )
    else:
        raise ConfigurationError(
            f"RCB source '{source}': unknown scenario_selection '{selection}'. "
            f"Expected 'ar6-category' or 'peak-warming-band'."
        )

    if selected.empty:
        raise DataProcessingError(
            f"RCB source '{source}', label '{label}': no scenario has {criterion}."
        )
    return selected


def build_rcb_scenario_sets(
    rcb_yaml: dict, metadata: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """
    Select the scenario set for every budget in a loaded rcbs.yaml.

    Parameters
    ----------
    rcb_yaml : dict
        Content of rcbs.yaml. Each source under ``rcb_data`` may carry a
        ``scenario_selection`` field (default: "ar6-category"). The top-level
        ``peak_warming_band_half_width`` sets the band half-width (default: 0.05).
    metadata : pd.DataFrame
        AR6 scenario metadata (see ``select_rcb_scenario_set``)

    Returns
    -------
    dict[str, pd.DataFrame]
        Selected metadata rows, keyed by ``rcb_scenario_set_key``
    """
    band_half_width = rcb_yaml.get(
        "peak_warming_band_half_width", DEFAULT_PEAK_WARMING_BAND_HALF_WIDTH
    )
    scenario_sets = {}
    for source, source_data in rcb_yaml["rcb_data"].items():
        selection = source_data.get("scenario_selection", DEFAULT_SCENARIO_SELECTION)
        for label in source_data["scenarios"]:
            key = rcb_scenario_set_key(source, label, selection)
            if key not in scenario_sets:
                scenario_sets[key] = select_rcb_scenario_set(
                    metadata, source, label, selection, band_half_width
                )
    return scenario_sets


def missing_rebase_years(
    rcb_baseline_year: int,
    emissions: pd.DataFrame,
    target_baseline_year: int = 2020,
) -> list[int]:
    """
    List the rebase years that an emissions timeseries lacks.

    Rebasing a budget from ``rcb_baseline_year`` to ``target_baseline_year``
    adds the emissions of every year from the target baseline to the year
    before the RCB baseline.
    """
    return [
        year
        for year in range(target_baseline_year, rcb_baseline_year)
        if str(year) not in emissions.columns
    ]


def fill_rebase_years(
    emissions: pd.DataFrame,
    rcb_baseline_year: int,
    max_fill_years: int = DEFAULT_REBASE_FILL_MAX_YEARS,
    series_name: str = "emissions",
    source_name: str = "",
) -> pd.DataFrame:
    """
    Hold the last observed value of a world series over the rebase years after it.

    The rebase of a budget to 2020 needs every year up to the year before the
    RCB baseline. When the series ends earlier, each year after its last
    observed year takes the last observed value. The fill is a placeholder
    until observed data are published, and every use raises a warning.

    Parameters
    ----------
    emissions : pd.DataFrame
        Single-row world timeseries with string year columns
    rcb_baseline_year : int
        The year from which the RCB is calculated
    max_fill_years : int, optional
        Largest number of years to fill (default: 1). 0 turns the fill off.
    series_name : str, optional
        Name of the series for the warning (e.g., "world fossil CO2 emissions")
    source_name : str, optional
        Name of the RCB source for the warning

    Returns
    -------
    pd.DataFrame
        The series with the filled years, or the series unchanged when no
        year is missing or more than ``max_fill_years`` years are missing.
        Years before the last observed year are never filled.
    """
    observed = emissions.iloc[0].dropna()
    observed_years = [int(c) for c in observed.index if str(c).isdigit()]
    if not observed_years:
        return emissions
    last_observed_year = max(observed_years)

    fill_years = list(range(last_observed_year + 1, rcb_baseline_year))
    if not fill_years or len(fill_years) > max_fill_years:
        return emissions

    last_value = float(observed[str(last_observed_year)])
    filled = emissions.copy()
    for year in fill_years:
        filled[str(year)] = last_value
    warnings.warn(
        f"RCB source '{source_name}' (baseline year {rcb_baseline_year}): "
        f"{series_name} end in {last_observed_year}. The rebase to 2020 uses the "
        f"{last_observed_year} value ({last_value:,.1f} Mt CO2) for {fill_years}. "
        f"This is a placeholder until observed data are published.",
        stacklevel=2,
    )
    return filled


def _year_ranges(years: list[int]) -> str:
    """Format sorted years as ranges, e.g. [1990, 1991, 1995] -> '1990-1991, 1995'."""
    ranges: list[list[int]] = []
    for year in years:
        if ranges and year == ranges[-1][1] + 1:
            ranges[-1][1] = year
        else:
            ranges.append([year, year])
    return ", ".join(
        str(first) if first == last else f"{first}-{last}" for first, last in ranges
    )


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

    Raises
    ------
    DataProcessingError
        If allocation_year is before 2020 and the world emissions lack any year
        from allocation_year to 2019
    """
    if allocation_year < 2020:
        # Add historical emissions before RCB period
        year_cols = [str(y) for y in range(allocation_year, 2020)]

        # A partial sum understates the budget, so every year must hold a value.
        world_row = world_scenario_emissions_ts.iloc[0]
        years_with_data = sorted(
            int(c) for c in world_row.dropna().index if str(c).isdigit()
        )
        missing_years = [y for y in map(int, year_cols) if y not in years_with_data]
        if missing_years:
            first_year = years_with_data[0] if years_with_data else None
            raise DataProcessingError(
                f"Allocation year {allocation_year} needs world emissions for "
                f"{allocation_year}-2019, but the world emissions data lack "
                f"{_year_ranges(missing_years)}. The first available year is "
                f"{first_year}."
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
    world_bunker_emissions: pd.DataFrame | None = None,
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

    The published RCB covers total anthropogenic CO2 from its baseline year and
    includes international bunkers. The world CO2-FFI series excludes them, and
    the bunker deduction covers 2020 to net zero. The rebase therefore adds
    fossil emissions and bunker emissions for 2020 to (baseline_year - 1), so
    each bunker year from 2020 is deducted exactly once.

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
       (baseline_year - 1) — fossil + bunkers for co2-ffi, fossil + bunkers
       + BM LULUCF for co2
    3. Subtract bunkers deduction from 2020 to net zero (always reduces budget)
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
        World-level CO2-FFI emissions timeseries with year columns (in Mt * CO2e).
        Excludes international bunkers.
    actual_bm_lulucf_emissions : pd.DataFrame or None, optional
        Actual bookkeeping-model LULUCF CO2 emissions (e.g. PRIMAP), with year
        columns (in Mt * CO2e). Used ONLY for the co2 rebase (default: None).
    world_bunker_emissions : pd.DataFrame or None, optional
        International bunker CO2 emissions timeseries with year columns
        (in Mt * CO2e). Required when baseline_year > 2020 and
        bunkers_deduction_mt is non-zero (default: None).
    bunkers_deduction_mt : float, optional
        Total bunker CO2 emissions from 2020 to net zero in Mt * CO2e
        (default: 0.0). Always positive; subtracted from budget.
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
          (positive, Mt * CO2e); fossil + bunkers for co2-ffi, fossil + bunkers
          + actual BM LULUCF for co2
        - 'rebase_fossil_mt': Fossil-only component of rebase (Mt * CO2e)
        - 'rebase_bunkers_mt': International bunker component of rebase
          (Mt * CO2e)
        - 'rebase_lulucf_mt': Actual BM LULUCF component of rebase (Mt * CO2e);
          only non-zero for co2
        - 'deduction_bunkers_mt': Bunker fuel deduction (negative, Mt * CO2e)
        - 'deduction_lulucf_future_mt': projected-LULUCF deduction applied
          to convert total-CO2 → FFI-only. Non-zero for co2-ffi, zero for co2.
        - 'correction_lulucf_nghgi_mt': NGHGI-vs-BM convention correction.
          Non-zero for co2, zero for co2-ffi.
        - 'net_adjustment_mt': Total change from original to 2020 baseline
          (rebase + deductions + correction, Mt * CO2e)

    Raises
    ------
    DataProcessingError
        If a timeseries lacks a year of the rebase, or if baseline_year > 2020
        and bunkers are deducted without ``world_bunker_emissions``
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
    rebase_bunkers_mt = 0.0
    rebase_lulucf_mt = 0.0

    # Calculate emissions adjustment based on baseline year
    if rcb_baseline_year > target_baseline_year:
        # Need to add emissions from 2020 to (baseline_year - 1)
        year_cols = [str(y) for y in range(target_baseline_year, rcb_baseline_year)]

        # A partial rebase understates the budget, so every year must be present.
        missing_years = missing_rebase_years(
            rcb_baseline_year, world_co2_ffi_emissions, target_baseline_year
        )
        if missing_years:
            raise DataProcessingError(
                f"RCB source '{source_name}' has baseline year {rcb_baseline_year}. "
                f"Rebasing to {target_baseline_year} needs CO2-FFI emissions for "
                f"{target_baseline_year}-{rcb_baseline_year - 1}, but the "
                f"emissions data lack {missing_years}."
            )

        # Fossil rebase — always from actual PRIMAP data
        rebase_fossil_mt = world_co2_ffi_emissions[year_cols].sum(axis=1).iloc[0]

        # Bunker rebase. The fossil series excludes bunkers and the deduction
        # starts in 2020, so the rebase adds the bunkers of these years.
        if world_bunker_emissions is not None:
            missing_years = missing_rebase_years(
                rcb_baseline_year, world_bunker_emissions, target_baseline_year
            )
            if missing_years:
                raise DataProcessingError(
                    f"RCB source '{source_name}' has baseline year "
                    f"{rcb_baseline_year}. Rebasing to {target_baseline_year} "
                    f"needs bunker emissions for "
                    f"{target_baseline_year}-{rcb_baseline_year - 1}, but the "
                    f"bunker data lack {missing_years}."
                )
            rebase_bunkers_mt = world_bunker_emissions[year_cols].sum(axis=1).iloc[0]
        elif bunkers_deduction_mt != 0:
            raise DataProcessingError(
                f"RCB source '{source_name}' has baseline year {rcb_baseline_year} "
                f"and a bunker deduction from {target_baseline_year}. Rebasing "
                f"needs the bunker emissions for "
                f"{target_baseline_year}-{rcb_baseline_year - 1}: pass "
                f"world_bunker_emissions."
            )

        # BM LULUCF rebase — only for co2 (total CO2 needs LULUCF in rebase)
        # For co2-ffi, LULUCF is omitted because it cancels with the LULUCF
        # decomposition
        rebase_lulucf_mt = 0.0
        if emission_category == "co2" and actual_bm_lulucf_emissions is not None:
            missing_years = missing_rebase_years(
                rcb_baseline_year, actual_bm_lulucf_emissions, target_baseline_year
            )
            if missing_years:
                raise DataProcessingError(
                    f"RCB source '{source_name}' has baseline year "
                    f"{rcb_baseline_year}. Rebasing to {target_baseline_year} "
                    f"needs LULUCF emissions for "
                    f"{target_baseline_year}-{rcb_baseline_year - 1}, but the "
                    f"emissions data lack {missing_years}."
                )
            rebase_lulucf_mt = actual_bm_lulucf_emissions[year_cols].sum(axis=1).iloc[0]

        rebase_total_mt = rebase_fossil_mt + rebase_bunkers_mt + rebase_lulucf_mt

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
                f"      Adding bunker emissions "
                f"({target_baseline_year}-{rcb_baseline_year - 1}): "
                f"+{rebase_bunkers_mt:.1f} Mt * CO2e"
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
                f"      Bunkers deduction ({target_baseline_year}-NZ): "
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
        "rebase_bunkers_mt": round(rebase_bunkers_mt),
        "rebase_lulucf_mt": round(rebase_lulucf_mt),
        "deduction_bunkers_mt": round(deduction_bunkers_mt),
        "deduction_lulucf_future_mt": round(deduction_lulucf_future_mt),
        "correction_lulucf_nghgi_mt": round(correction_lulucf_nghgi_mt),
        "net_adjustment_mt": round(net_adjustment_mt),
    }
