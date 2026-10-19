"""
Remaining Carbon Budget (RCB) processing utilities.

Functions for parsing RCB labels, for the scenario accounting behind the
scenario-derived budget terms, and for converting RCB values between baseline
years with adjustments for bunkers and LULUCF.

Accounting of a scenario series: the series is linear between its reported
years, and a year's value is its flow over the whole year. The net-zero year is
the first zero crossing of that line. Every cumulative to net zero sums the full
years from its start and adds the fraction of the net-zero year (``integrate``).
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from fair_shares.library.exceptions import ConfigurationError, DataProcessingError
from fair_shares.library.utils.units import get_default_unit_registry

if TYPE_CHECKING:
    from fair_shares.library.utils.dataframes import TimeseriesDataFrame

# AR6 WGIII category paired with a budget label under the "ar6-category" rule
# (AR6 WGIII Annex III: C1 holds the 1.5 C p50 budget, C3 >67% below 2 C, C4
# >50% below 2 C).
AR6_CATEGORY_BY_RCB_LABEL = {"1.5p50": "C1", "2p67": "C3", "2p50": "C4"}

# Labels renamed in rcbs.yaml: these sources publish 67% budgets.
LABEL_ALIASES = {
    "forster_2024": {"2p66": "2p67"},
    "ar6_2020": {"2p66": "2p67"},
}

# Scenario selection rules. "role-matched" uses the volume-matched set for the
# integral terms and the temperature-matched set for the non-CO2 pathway.
DEFAULT_SCENARIO_SELECTION = "role-matched"
SCENARIO_SELECTION_RULES = ("role-matched", "ar6-category")
REMOVED_SELECTION_RULES = (
    "warming-at-net-zero",
    "peak-warming",
    "peak-warming-band",
    "end-of-century",
)

# Largest number of trailing rebase years that take the last observed value.
DEFAULT_REBASE_FILL_MAX_YEARS = 1


def parse_rcb_scenario(scenario_string: str) -> tuple[str, str]:
    """
    Parse RCB scenario string into climate assessment and quantile.

    RCB scenario strings follow the format "TEMPpPROB" where TEMP is the
    temperature target (e.g., "1.5" or "2") and PROB is the probability
    as a percentage (e.g., "50" or "67").

    Parameters
    ----------
    scenario_string : str
        RCB scenario string (e.g., "1.5p50", "2p67")

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
            f"Expected integer percentage (e.g., '50', '67')"
        )

    return climate_assessment, quantile


def canonical_label(source: str, label: str) -> str:
    """
    Return the current name of a budget label, warning on a renamed one.

    forster_2024 and ar6_2020 publish 67% budgets, once labelled "2p66". The
    old label reads as "2p67" with a DeprecationWarning.
    """
    renamed = LABEL_ALIASES.get(source, {}).get(label)
    if renamed is None:
        return label
    warnings.warn(
        f"RCB source '{source}': label '{label}' is deprecated. The source "
        f"publishes this budget at 67%; use '{renamed}'.",
        DeprecationWarning,
        stacklevel=2,
    )
    return renamed


def canonical_scenarios(source: str, scenarios: dict) -> dict:
    """Return the budgets of one rcbs.yaml source under their current labels."""
    return {canonical_label(source, label): value for label, value in scenarios.items()}


def label_temperature(source: str, label: str) -> float:
    """Return the temperature of a budget label, or raise for a non-numeric one."""
    climate_assessment, _ = parse_rcb_scenario(label)
    try:
        return float(climate_assessment.removesuffix("C"))
    except ValueError:
        raise ConfigurationError(
            f"RCB source '{source}', label '{label}': the label needs a numeric "
            f"temperature before 'p' (e.g. '1.5p50')."
        ) from None


def resolve_scenario_selection(source: str, selection: str | None) -> str:
    """
    Return the scenario selection rule of an RCB source.

    ``None`` gives "role-matched". "ar6-category" pairs the labels of
    ``AR6_CATEGORY_BY_RCB_LABEL`` with their AR6 category; its other labels
    use the role-matched sets.

    Raises
    ------
    ConfigurationError
        If the rule is unknown or removed
    """
    if selection is None:
        return DEFAULT_SCENARIO_SELECTION
    if selection in REMOVED_SELECTION_RULES:
        raise ConfigurationError(
            f"RCB source '{source}': scenario_selection '{selection}' was removed. "
            f"Every budget now uses role-matched sets: a volume-matched set for "
            f"the land-use, convention-gap and bunker terms and a "
            f"temperature-matched set for the non-CO2 pathway. Delete the field, "
            f"or set 'ar6-category' for an AR6 budget."
        )
    if selection not in SCENARIO_SELECTION_RULES:
        raise ConfigurationError(
            f"RCB source '{source}': unknown scenario_selection '{selection}'. "
            f"Expected one of {list(SCENARIO_SELECTION_RULES)}."
        )
    return selection


def _points(series: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Return the reported (year, value) points of a series, sorted by year."""
    values = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
    years = np.array([float(y) for y in values.index])
    order = np.argsort(years)
    return years[order], values.to_numpy(dtype=float)[order]


def net_zero_crossing(series: pd.Series, start: float = 2020) -> float | None:
    """
    Return the year in which a series first reaches zero, from ``start`` on.

    The series is linear between its reported years, so the crossing lies
    between the last positive point and the first point at or below zero.

    Parameters
    ----------
    series : pd.Series
        Total CO2 emissions of one scenario, indexed by year
    start : float, optional
        First year considered (default: 2020)

    Returns
    -------
    float or None
        The crossing year (e.g. 2051.4), or None when the series stays above zero
    """
    years, values = _points(series)
    keep = years >= start
    years, values = years[keep], values[keep]
    for i, value in enumerate(values):
        if value <= 0:
            if i == 0:
                return float(years[0])
            year_before, value_before = years[i - 1], values[i - 1]
            step = years[i] - year_before
            return float(year_before + value_before / (value_before - value) * step)
    return None


def integrate(series: pd.Series, start: int, end: float) -> float:
    """
    Return the cumulative of a series from the start of ``start`` to ``end``.

    The series is linear between its reported years, and the value of a year
    is the flow over that whole year. The cumulative sums the full years from
    ``start`` to the year before ``end`` and adds the fraction of the year of
    ``end``: the trapezoid of the line from that year to ``end``. A net-zero
    crossing at ``end`` thus counts every year of the budget in full. An empty
    interval (end <= start) gives 0.

    Raises
    ------
    DataProcessingError
        If the reported years do not cover [start, end]
    """
    if end <= start:
        return 0.0
    years, values = _points(series)
    if len(years) == 0 or start < years[0] or end > years[-1]:
        span = f"{years[0]:.0f}-{years[-1]:.0f}" if len(years) else "no years"
        raise DataProcessingError(
            f"The series covers {span}; the integral needs {start:g}-{end:g}."
        )
    last_full = int(np.floor(end))
    full_years = np.arange(int(start), last_full)
    total = float(np.interp(full_years, years, values).sum())
    if end > last_full:
        heights = np.interp([last_full, end], years, values)
        total += float((heights[0] + heights[1]) / 2 * (end - last_full))
    return total


def cumulative_to_net_zero(
    series: pd.Series, start: float = 2020
) -> tuple[float | None, float | None]:
    """Return (net-zero crossing, cumulative from ``start`` to it), or (None, None)."""
    crossing = net_zero_crossing(series, start)
    if crossing is None:
        return None, None
    return crossing, integrate(series, start, crossing)


def convention_gap_from_baseline(
    nghgi_lulucf: pd.Series,
    bm_direct: pd.Series,
    indirect: pd.Series,
    baseline_year: int,
    nz_year: float,
    splice_year: int,
) -> float:
    """
    Return the NGHGI-minus-BM LULUCF gap of one scenario from the budget baseline.

    The gap converts a budget in the bookkeeping-model (BM) convention to the
    national-inventory (NGHGI) convention. It covers the years that the
    published budget covers: the baseline year to the net-zero year of the
    scenario (Weber et al. 2026, Eqs. 2-3). The years before the baseline are
    not part of it; the rebase adds observed NGHGI LULUCF for those years.

    The gap series is:

    - years up to ``splice_year``: observed NGHGI LULUCF minus the scenario
      BM LULUCF (AFOLU|Direct)
    - years after ``splice_year``: the scenario indirect flux (AFOLU|Indirect),
      because the direct flux cancels in the difference

    and the gap is its cumulative from the baseline year to the net-zero
    crossing (full years plus the fraction of the net-zero year, ``integrate``).

    Parameters
    ----------
    nghgi_lulucf : pd.Series
        Observed world NGHGI LULUCF CO2, indexed by year as a string
    bm_direct : pd.Series
        AFOLU|Direct of the scenario, indexed by year as a string
    indirect : pd.Series
        AFOLU|Indirect of the scenario, indexed by year as a string
    baseline_year : int
        First year of the published budget
    nz_year : float
        Net-zero crossing of the scenario (end of the gap)
    splice_year : int
        Last observed year of ``nghgi_lulucf``

    Returns
    -------
    float
        The gap from ``baseline_year`` to ``nz_year``. Zero when the net-zero
        crossing is at or before the baseline year.
    """
    if nz_year <= baseline_year:
        return 0.0

    def _by_year(series: pd.Series) -> pd.Series:
        values = pd.to_numeric(pd.Series(series), errors="coerce")
        values.index = [int(y) for y in values.index]
        return values

    observed = _by_year(nghgi_lulucf).sub(_by_year(bm_direct)).dropna()
    observed = observed[observed.index <= splice_year]
    after = _by_year(indirect).dropna()
    gap = pd.concat([observed, after[after.index > splice_year]]).sort_index()
    return integrate(gap, baseline_year, nz_year)


def validate_rebase_fill_max_years(value: object) -> int:
    """Return ``rebase_fill_max_years`` from rcbs.yaml, or raise if it is not a count."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigurationError(
            f"rcbs.yaml: rebase_fill_max_years must be a non-negative integer, "
            f"got {value!r}."
        )
    return value


def _available_years(emissions: pd.DataFrame) -> list[int]:
    """List the years whose column exists and holds a value in every row."""
    return sorted(
        int(c)
        for c in emissions.columns
        if str(c).isdigit() and emissions[c].notna().all()
    )


def _years_lacking(emissions: pd.DataFrame, years: range | list[int]) -> list[int]:
    """List the years in ``years`` that ``emissions`` has no value for."""
    available = set(_available_years(emissions))
    return [year for year in years if year not in available]


def missing_rebase_years(
    rcb_baseline_year: int,
    emissions: pd.DataFrame,
    target_baseline_year: int = 2020,
) -> list[int]:
    """
    List the rebase years that an emissions timeseries lacks.

    Rebasing a budget from ``rcb_baseline_year`` to ``target_baseline_year``
    adds the emissions of every year from the target baseline to the year
    before the RCB baseline. A year with a missing value counts as lacking.
    """
    return _years_lacking(emissions, range(target_baseline_year, rcb_baseline_year))


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
        If the world emissions lack any year from allocation_year to 2019
        (allocation_year before 2020) or from 2020 to allocation_year - 1
        (allocation_year after 2020)
    """
    if allocation_year < 2020:
        # Add historical emissions before RCB period
        year_cols = [str(y) for y in range(allocation_year, 2020)]

        # A partial sum understates the budget, so every year must hold a value.
        missing_years = _years_lacking(
            world_scenario_emissions_ts, range(allocation_year, 2020)
        )
        if missing_years:
            years_with_data = _available_years(world_scenario_emissions_ts)
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
        year_cols = [str(y) for y in range(2020, allocation_year)]

        # A partial sum overstates the budget, so every year must hold a value.
        missing_years = _years_lacking(
            world_scenario_emissions_ts, range(2020, allocation_year)
        )
        if missing_years:
            years_with_data = _available_years(world_scenario_emissions_ts)
            last_year = years_with_data[-1] if years_with_data else None
            raise DataProcessingError(
                f"Allocation year {allocation_year} needs world emissions for "
                f"2020-{allocation_year - 1}, but the world emissions data lack "
                f"{_year_ranges(missing_years)}. The last available year is "
                f"{last_year}."
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
    world_lulucf_emissions: pd.DataFrame | None = None,
    world_bunker_emissions: pd.DataFrame | None = None,
    bunkers_deduction_mt: float = 0.0,
    lulucf_future_deduction_mt: float = 0.0,
    lulucf_convention_correction_mt: float = 0.0,
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
      ``lulucf_convention_correction_mt`` is not used for this category.
    - **co2**: Rebase uses fossil CO2 + observed LULUCF in the national-
      inventory (NGHGI) convention. ``lulucf_convention_correction_mt`` applies
      the NGHGI-vs-BM convention gap from the baseline year to net zero
      (Weber et al. 2026), which re-expresses the published budget against
      national-inventory accounting. ``lulucf_future_deduction_mt`` is not
      used for this category; the budget retains both FFI and LULUCF.

    The calculation follows these steps:
    1. Convert RCB from source unit to Mt * CO2e
    2. If baseline_year > 2020: Add actual emissions from 2020 to
       (baseline_year - 1) — fossil + bunkers for co2-ffi, fossil + bunkers
       + NGHGI LULUCF for co2
    3. Subtract bunkers deduction from 2020 to net zero (always reduces budget)
    4. Apply LULUCF deduction (sign-ready from caller)

    Sign convention for deduction parameters:
    - bunkers_deduction_mt: always positive (cumulative emissions), subtracted
    - lulucf_future_deduction_mt: sign-ready from caller (added directly).
      For co2-ffi: negated BM LULUCF → positive if LULUCF is a net source
      (increases fossil budget), capped at 0 if caller applies a
      precautionary rule. Zero for co2.
    - lulucf_convention_correction_mt: sign-ready from caller (added directly).
      For co2: the NGHGI-vs-BM convention gap from the baseline year to
      net zero (Weber et al. 2026), typically negative. Zero for co2-ffi.

    Parameters
    ----------
    rcb_value : float
        Original RCB value from the source
    rcb_unit : str
        Unit of the RCB value (e.g., "Gt * CO2", "Mt * CO2")
    rcb_baseline_year : int
        The year from which the RCB is calculated (must be >= 2020)
    emission_category : str
        Emission category: "co2-ffi" or "co2". Controls whether NGHGI
        LULUCF is included in the rebase.
    world_co2_ffi_emissions : pd.DataFrame
        World-level CO2-FFI emissions timeseries with year columns (in Mt * CO2e).
        Excludes international bunkers.
    world_lulucf_emissions : pd.DataFrame or None, optional
        Observed world LULUCF CO2 emissions in the national-inventory (NGHGI)
        convention (e.g. the Melo et al. world row), with year columns
        (in Mt * CO2e). Used ONLY for the co2 rebase (default: None).
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
    lulucf_convention_correction_mt : float, optional
        NGHGI-vs-BM convention gap from the baseline year to net zero in
        Mt * CO2e, sign-ready (default: 0.0). Non-zero for co2 only, where it
        re-expresses the budget from bookkeeping-model to NGHGI accounting.
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
          (positive, Mt * CO2e); fossil + bunkers for co2-ffi, fossil + bunkers
          + observed NGHGI LULUCF for co2
        - 'rebase_fossil_mt': Fossil-only component of rebase (Mt * CO2e)
        - 'rebase_bunkers_mt': International bunker component of rebase
          (Mt * CO2e)
        - 'rebase_lulucf_mt': Observed NGHGI LULUCF component of rebase
          (Mt * CO2e); only non-zero for co2
        - 'deduction_bunkers_mt': Bunker fuel deduction (negative, Mt * CO2e)
        - 'deduction_lulucf_future_mt': projected-LULUCF deduction applied
          to convert total-CO2 → FFI-only. Non-zero for co2-ffi, zero for co2.
        - 'correction_lulucf_convention_mt': NGHGI-vs-BM convention correction.
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

        # NGHGI LULUCF rebase — only for co2 (total CO2 needs LULUCF in rebase)
        # For co2-ffi, LULUCF is omitted because it cancels with the LULUCF
        # decomposition
        rebase_lulucf_mt = 0.0
        if emission_category == "co2" and world_lulucf_emissions is None:
            raise DataProcessingError(
                f"RCB source '{source_name}' has baseline year {rcb_baseline_year}. "
                f"Rebasing a co2 budget to {target_baseline_year} needs the "
                f"observed inventory (NGHGI) LULUCF emissions for "
                f"{target_baseline_year}-{rcb_baseline_year - 1}: pass "
                f"world_lulucf_emissions."
            )
        if emission_category == "co2":
            missing_years = missing_rebase_years(
                rcb_baseline_year, world_lulucf_emissions, target_baseline_year
            )
            if missing_years:
                raise DataProcessingError(
                    f"RCB source '{source_name}' has baseline year "
                    f"{rcb_baseline_year}. Rebasing to {target_baseline_year} "
                    f"needs LULUCF emissions for "
                    f"{target_baseline_year}-{rcb_baseline_year - 1}, but the "
                    f"emissions data lack {missing_years}."
                )
            rebase_lulucf_mt = world_lulucf_emissions[year_cols].sum(axis=1).iloc[0]

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
                    f"      Adding observed NGHGI LULUCF emissions "
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
    correction_lulucf_convention_mt = lulucf_convention_correction_mt

    rcb_2020_mt = (
        rcb_adjusted_mt
        - bunkers_deduction_mt
        + deduction_lulucf_future_mt
        + correction_lulucf_convention_mt
    )

    # Net adjustment = total change from original to 2020 baseline
    net_adjustment_mt = (
        rebase_total_mt
        + deduction_bunkers_mt
        + deduction_lulucf_future_mt
        + correction_lulucf_convention_mt
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
        if correction_lulucf_convention_mt != 0:
            print(
                f"      LULUCF NGHGI correction ({rcb_baseline_year}-NZ): "
                f"{correction_lulucf_convention_mt:.1f} Mt * CO2e"
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
        "rebase_bunkers_mt": round(rebase_bunkers_mt),
        "rebase_lulucf_mt": round(rebase_lulucf_mt),
        "deduction_bunkers_mt": round(deduction_bunkers_mt),
        "deduction_lulucf_future_mt": round(deduction_lulucf_future_mt),
        "correction_lulucf_convention_mt": round(correction_lulucf_convention_mt),
        "net_adjustment_mt": round(net_adjustment_mt),
    }
