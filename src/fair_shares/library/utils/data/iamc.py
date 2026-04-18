"""
IAMC Data Format Adapter for fair-shares Allocations.

Load IAMC-format data via pyam and reshape it for fair-shares allocation
functions. Typical upstream producer is notebook 400, which back-fills
CEDS-based regional history, builds `Emissions|Covered`, and writes an
annual-resolution file that 401/402/403 consume.

IAMC Format Requirements
------------------------
Standard IAMC columns: model, scenario, region, variable, unit, and year
columns (numeric or string).

Required Variables by Approach
------------------------------
- equal-per-capita-budget: Population
- per-capita-adjusted-budget: Population; Emissions (when
  ``pre_allocation_responsibility_weight > 0``); GDP|PPP (when
  ``capability_weight > 0``)
- cumulative-per-capita-convergence: Population, Emissions (regional and
  world-total)

Data Coverage
-------------
Data should span ``allocation_start_year`` (typically 1990 for approaches
using pre-allocation responsibility) through ``budget_end_year`` (your
model's final timestep).

Example Usage
-------------
>>> from fair_shares.library.utils.data.iamc import load_iamc_data
>>> data = load_iamc_data(
...     data_file="output/iamc/iamc_covered.xlsx",
...     population_variable="Population",
...     emissions_variable="Emissions|Covered",
...     gdp_variable="GDP|PPP",
...     allocation_start_year=1990,
...     budget_end_year=2100,
... )  # doctest: +SKIP
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

try:
    import pyam

    PYAM_AVAILABLE = True
except ImportError:
    PYAM_AVAILABLE = False

from fair_shares.library.exceptions import IAMCDataError

if TYPE_CHECKING:
    pass


def _ensure_pyam() -> None:
    """Raise informative error if pyam is not installed."""
    if not PYAM_AVAILABLE:
        raise ImportError(
            "pyam is required for IAMC data loading. "
            "Install with: pip install pyam-iamc"
        )


def load_iamc_data(
    data_file: str | Path | pd.DataFrame,
    *,
    population_variable: str = "Population",
    emissions_variable: str | None = None,
    gdp_variable: str | None = None,
    regions: list[str] | None = None,
    allocation_start_year: int = 1990,
    budget_end_year: int = 2100,
    model_filter: str | None = None,
    scenario_filter: str | None = None,
    group_level: str = "region",
    unit_level: str = "unit",
    expand_to_annual: bool = False,
    interpolation_method: str = "bfill",
) -> dict[str, pd.DataFrame]:
    """
    Load IAMC-format data for fair shares allocation calculations.

    Uses pyam.IamDataFrame for robust loading and validation.

    Parameters
    ----------
    data_file
        Path to IAMC CSV/Excel file, DataFrame, or pyam.IamDataFrame.
    population_variable
        IAMC variable name for population data.
        Default: "Population"
    emissions_variable
        IAMC variable name for emissions data.
        Required for pre-allocation-responsibility-adjusted approaches.
        Examples: "Emissions|CO2", "Emissions|Kyoto Gases"
    gdp_variable
        IAMC variable name for GDP data.
        Required for capability-adjusted approaches.
        Examples: "GDP|PPP", "GDP|MER"
    regions
        List of region identifiers to include.
        Regions not in this list (e.g., "World") are excluded.
        If None, includes all regions except "World".
    allocation_start_year
        First year of data required (for pre-allocation responsibility).
        Default: 1990
    budget_end_year
        Last year of data required (model final timestep).
        Default: 2100
    model_filter
        Filter to specific model name. Supports wildcards (e.g., "MESSAGE*").
    scenario_filter
        Filter to specific scenario name. Supports wildcards (e.g., "*SSP2*").
    group_level
        Name for the group index level in output.
        Default: "region"
    unit_level
        Name for the unit index level in output.
        Default: "unit"
    expand_to_annual
        If True, expand non-annual data to annual values.
        This is required for correct cumulative calculations when data has
        multi-year intervals (e.g., 5-year or 10-year timesteps).
        Default: False
    interpolation_method
        Method for filling annual values when expand_to_annual=True.
        - "bfill": Backward fill (each value fills the preceding interval).
          For 5-year data at 2015, 2020, 2025: the 2020 value fills years
          2016-2020, the 2025 value fills 2021-2025, etc. This is the
          standard approach for period-weighted cumulative calculations
          where each observation represents an interval ending at that year.
        - "linear": Linear interpolation between data points. Use when
          smooth transitions between observations are more appropriate.
        Default: "bfill"

    Returns
    -------
    dict
        Dictionary containing:
        - "population": Population timeseries (always present)
        - "emissions": Emissions timeseries (if emissions_variable provided)
        - "gdp": GDP timeseries (if gdp_variable provided)
        - "metadata": Dict with source info, year coverage, etc.

    Raises
    ------
    IAMCDataError
        If required data is missing or validation fails.
        Error messages include specific guidance.
    ImportError
        If pyam is not installed.

    Examples
    --------
    Load data for equal per capita allocation (population only):

    >>> # IAMC data columns: model, scenario, region, variable, unit, 1990, 1995, ..., 2100
    >>> # Reference: data/scenarios/iamc_example/iamc_reporting_example.xlsx
    >>> data = load_iamc_data(
    ...     "data/scenarios/iamc_example/iamc_reporting_example.xlsx",
    ...     population_variable="Population",
    ...     regions=["AFR", "CHN", "NAM"],
    ...     model_filter="SSP_SSP2_v6.3_ES",
    ...     scenario_filter="ECPC-2015-800Gt",
    ...     budget_end_year=2100,
    ... )  # doctest: +SKIP

    Load data for adjusted allocation (with emissions and GDP):

    >>> # Load IAMC scenario data with emissions and GDP for capability adjustments
    >>> # model="SSP_SSP2_v6.3_ES", scenario="ECPC-2015-800Gt" from example file
    >>> data = load_iamc_data(
    ...     "data/scenarios/iamc_example/iamc_reporting_example.xlsx",
    ...     population_variable="Population",
    ...     emissions_variable="Emissions|CO2",
    ...     gdp_variable="GDP|PPP",
    ...     regions=["AFR", "CHN", "NAM"],
    ...     model_filter="SSP_SSP2_v6.3_ES",
    ...     scenario_filter="ECPC-2015-800Gt",
    ...     allocation_start_year=1990,
    ...     budget_end_year=2100,
    ... )  # doctest: +SKIP
    """
    _ensure_pyam()

    # Load data into pyam.IamDataFrame
    if isinstance(data_file, pyam.IamDataFrame):
        df = data_file
    else:
        df = pyam.IamDataFrame(data_file)

    # Apply model/scenario filters using pyam's wildcard support
    if model_filter:
        df = df.filter(model=model_filter)
    if scenario_filter:
        df = df.filter(scenario=scenario_filter)

    # Guard: require exactly one model/scenario combination
    if len(df.model) > 1 or len(df.scenario) > 1:
        lines = [
            f"Data contains {len(df.model)} model(s) × "
            f"{len(df.scenario)} scenario(s):",
        ]
        for m in df.model:
            for s in df.scenario:
                lines.append(f"  • {m} | {s}")
        lines.append("")
        lines.append("This function requires exactly one model/scenario combination.")
        lines.append("Filter when calling load_iamc_data():")
        lines.append(f'    model_filter="{df.model[0]}",')
        lines.append(f'    scenario_filter="{df.scenario[0]}"')
        lines.append("")
        lines.append("Or use pyam directly:")
        lines.append('    df = pyam.IamDataFrame("your_file.xlsx")')
        lines.append(
            f'    df = df.filter(model="{df.model[0]}", '
            f'scenario="{df.scenario[0]}")'
        )
        raise IAMCDataError("\n".join(lines))

    # Determine regions to include
    if regions is None:
        # Auto-detect: exclude "World" and similar global aggregates
        all_regions = df.region
        regions = [r for r in all_regions if r.lower() not in ("world", "global")]

    df = df.filter(region=regions)

    # Filter to year range
    years = range(allocation_start_year, budget_end_year + 1)
    df = df.filter(year=years)

    # Validate required variables using pyam's require_data
    required_vars = [population_variable]
    if emissions_variable:
        required_vars.append(emissions_variable)
    if gdp_variable:
        required_vars.append(gdp_variable)

    _validate_iamc_data(
        df, required_vars, regions, allocation_start_year, budget_end_year
    )

    # Extract each variable as fair-shares timeseries format
    result = {}
    result["population"] = _iamc_to_timeseries(
        df, population_variable, group_level, unit_level
    )

    if emissions_variable:
        result["emissions"] = _iamc_to_timeseries(
            df, emissions_variable, group_level, unit_level
        )

    if gdp_variable:
        result["gdp"] = _iamc_to_timeseries(df, gdp_variable, group_level, unit_level)
        # Normalize GDP units from billion to million (common IAMC unit conversion)
        result["gdp"] = _normalize_gdp_units(result["gdp"], unit_level)

    # Expand to annual data if requested
    # Import here to avoid circular import at module level
    if expand_to_annual:
        from fair_shares.library.utils.data.transform import (
            expand_to_annual as expand_annual_fn,
        )

        for key in ["population", "emissions", "gdp"]:
            if key in result:
                result[key] = expand_annual_fn(
                    result[key],
                    allocation_start_year,
                    budget_end_year,
                    method=interpolation_method,
                )

    # Metadata for reproducibility
    result["metadata"] = {
        "regions": list(regions),
        "year_range": (allocation_start_year, budget_end_year),
        "model": list(df.model),
        "scenario": list(df.scenario),
        "variables_loaded": required_vars,
        "expanded_to_annual": expand_to_annual,
        "interpolation_method": interpolation_method if expand_to_annual else None,
    }

    return result


def _validate_iamc_data(
    df: pyam.IamDataFrame,
    required_variables: list[str],
    required_regions: list[str],
    start_year: int,
    end_year: int,
) -> None:
    """
    Validate IAMC data meets requirements using pyam's built-in validation.

    Raises IAMCDataError with specific guidance for any issues.
    """
    # Check for required variables
    available_vars = set(df.variable)
    missing_vars = [v for v in required_variables if v not in available_vars]
    if missing_vars:
        suggestion = _suggest_similar_variables(missing_vars, available_vars)
        raise IAMCDataError(
            f"Required variable(s) not found: {missing_vars}\n"
            f"Available variables: {sorted(available_vars)}\n"
            f"{suggestion}"
        )

    # Check for required regions
    available_regions = set(df.region)
    missing_regions = [r for r in required_regions if r not in available_regions]
    if missing_regions:
        raise IAMCDataError(
            f"Required region(s) not found: {missing_regions}\n"
            f"Available regions: {sorted(available_regions)}"
        )

    # Use pyam's require_data for completeness check
    for var in required_variables:
        missing = df.require_data(variable=var, year=[start_year, end_year])
        if missing is not None and not missing.empty:
            raise IAMCDataError(
                f"Missing data for variable '{var}' at required years.\n"
                f"Required: {start_year} to {end_year}\n"
                f"Missing entries:\n{missing}"
            )


def _suggest_similar_variables(missing: list[str], available: set[str]) -> str:
    """Suggest similar variable names for common mistakes."""
    suggestions = []
    for var in missing:
        # Check for common hierarchical patterns
        if "|" in var:
            prefix = var.split("|")[0]
            matches = [v for v in available if v.startswith(prefix)]
            if matches:
                suggestions.append(f"  '{var}' -> Did you mean one of: {matches[:5]}")
        else:
            # Check for exact matches with different case
            lower_var = var.lower()
            matches = [v for v in available if v.lower() == lower_var]
            if matches:
                suggestions.append(f"  '{var}' -> Did you mean: {matches[0]}")

    if suggestions:
        return "Suggestions:\n" + "\n".join(suggestions)
    return ""


def _iamc_to_timeseries(
    df: pyam.IamDataFrame,
    variable: str,
    group_level: str = "region",
    unit_level: str = "unit",
) -> pd.DataFrame:
    """
    Transform pyam.IamDataFrame to fair-shares timeseries format.

    Converts from pyam's IamDataFrame to fair-shares MultiIndex format:
        index: (region, unit)
        columns: "2020", "2030", ... (string year columns)

    Parameters
    ----------
    df
        pyam.IamDataFrame
    variable
        Variable name to extract
    group_level
        Name for group index level (default: "region")
    unit_level
        Name for unit index level (default: "unit")

    Returns
    -------
    DataFrame
        Timeseries in fair-shares format with MultiIndex (region, unit)
        and string year columns
    """
    # Filter to specific variable
    var_df = df.filter(variable=variable)

    # Get wide-format timeseries from pyam
    ts = var_df.timeseries()

    # pyam timeseries has MultiIndex (model, scenario, region, variable, unit)
    # We need to reduce to (region, unit) with string year columns

    # Reset index to get region and unit columns
    ts = ts.reset_index()

    # Keep only region, unit, and year columns
    year_cols = [c for c in ts.columns if isinstance(c, (int, float))]
    ts = ts[["region", "unit", *year_cols]]

    # Set MultiIndex with our level names
    ts = ts.set_index(["region", "unit"])
    ts.index.names = [group_level, unit_level]

    # Convert year columns to strings (fair-shares convention)
    ts.columns = [str(int(c)) for c in ts.columns]

    return ts


def _normalize_gdp_units(
    gdp_df: pd.DataFrame, unit_level: str = "unit"
) -> pd.DataFrame:
    """
    Normalize GDP units to the simple label ``"million"`` for allocation functions.

    IAMC GDP rows carry labels like ``"billion US$2010/yr"`` whose currency-year
    token (``US$2010``) the fair-shares pint registry cannot parse. Downstream
    allocation functions need GDP in millions so that per-capita quantities are
    dimensionally consistent with the ``"million"`` population unit. This helper
    rescales billion → million where needed and strips the currency-year token
    from the label. No change is applied to already-millions data beyond the
    label simplification.
    """
    units = gdp_df.index.get_level_values(unit_level).unique()
    if len(units) != 1:
        raise IAMCDataError(f"Expected single GDP unit, found multiple: {list(units)}")

    current_unit = units[0].lower()

    if "billion" in current_unit:
        gdp_df = gdp_df * 1000  # billion → million
    elif "million" not in current_unit:
        raise IAMCDataError(
            f"GDP unit '{units[0]}' is not recognised (expected 'billion' or "
            f"'million' substring). Allocation functions require GDP in millions; "
            f"rescale and relabel before calling load_iamc_data()."
        )

    new_index = gdp_df.index.to_frame()
    new_index[unit_level] = "million"
    gdp_df.index = pd.MultiIndex.from_frame(new_index)
    return gdp_df


def get_available_variables(data_file: str | Path | pd.DataFrame) -> list[str]:
    """
    List all unique variable names in IAMC data.

    Parameters
    ----------
    data_file
        Path to IAMC CSV/Excel file or DataFrame

    Returns
    -------
    list[str]
        Sorted list of variable names
    """
    _ensure_pyam()
    df = (
        pyam.IamDataFrame(data_file)
        if not isinstance(data_file, pyam.IamDataFrame)
        else data_file
    )
    return sorted(df.variable)


def get_available_regions(data_file: str | Path | pd.DataFrame) -> list[str]:
    """
    List all unique region names in IAMC data.

    Parameters
    ----------
    data_file
        Path to IAMC CSV/Excel file or DataFrame

    Returns
    -------
    list[str]
        Sorted list of region names
    """
    _ensure_pyam()
    df = (
        pyam.IamDataFrame(data_file)
        if not isinstance(data_file, pyam.IamDataFrame)
        else data_file
    )
    return sorted(df.region)


def get_year_coverage(data_file: str | Path | pd.DataFrame) -> tuple[int, int]:
    """
    Get (min_year, max_year) from IAMC data.

    Parameters
    ----------
    data_file
        Path to IAMC CSV/Excel file or DataFrame

    Returns
    -------
    tuple[int, int]
        (minimum_year, maximum_year)
    """
    _ensure_pyam()
    df = (
        pyam.IamDataFrame(data_file)
        if not isinstance(data_file, pyam.IamDataFrame)
        else data_file
    )
    years = df.timeseries().columns
    return (int(min(years)), int(max(years)))


def calculate_cumulative_emissions(
    emissions_ts: pd.DataFrame,
    start_year: int,
    end_year: int,
    target_unit: str = "Gt CO2/yr",
    unit_level: str = "unit",
    gwp: str = "AR6GWP100",
) -> pd.Series:
    """
    Calculate cumulative emissions over a time period from annual timeseries data.

    Expects annual data (e.g., expanded via ``expand_to_annual`` with linear
    interpolation). Each year column represents the annual rate for that year,
    and the cumulative is the sum of those annual values, converted to
    ``target_unit`` using the fair-shares pint registry.

    Parameters
    ----------
    emissions_ts
        Emissions timeseries DataFrame with annual year columns and an index
        that includes ``unit_level``. Native units are read row-wise from that
        level; the returned series drops it.
    start_year
        First year to include in cumulative sum
    end_year
        Last year to include in cumulative sum
    target_unit
        Output unit; default ``"Gt CO2/yr"``. CO2-equivalent inputs are
        converted via the ``gwp`` context.
    unit_level
        Name of the index level holding each row's native unit.
    gwp
        GWP context activated for CO2e → CO2 conversions. Default AR6GWP100.

    Returns
    -------
    pd.Series
        Cumulative emissions in ``target_unit``, indexed by the non-unit index
        levels (e.g. region).

    Examples
    --------
    >>> cumulative = calculate_cumulative_emissions(
    ...     emissions_ts=emissions_df,
    ...     start_year=2015,
    ...     end_year=2100,
    ... )  # doctest: +SKIP
    """
    from fair_shares.library.utils.units import get_default_unit_registry

    year_cols = [
        str(y)
        for y in range(start_year, end_year + 1)
        if str(y) in emissions_ts.columns
    ]

    if not year_cols:
        raise IAMCDataError(
            f"No data found between {start_year} and {end_year}. "
            f"Available years: {[c for c in emissions_ts.columns if c.isdigit()]}"
        )

    index_names = list(emissions_ts.index.names or [])
    if unit_level not in index_names:
        raise IAMCDataError(
            f"emissions_ts must retain the '{unit_level}' index level for "
            f"unit-aware conversion. Available levels: {index_names}."
        )

    summed = emissions_ts[year_cols].sum(axis=1)
    units = summed.index.get_level_values(unit_level)
    ur = get_default_unit_registry()
    with ur.context(gwp):
        factors = {
            u: float((1.0 * ur(u)).to(target_unit).magnitude) for u in set(units)
        }
    factor_series = pd.Series([factors[u] for u in units], index=summed.index)
    return (summed * factor_series).droplevel(unit_level)


def calculate_world_total_timeseries(
    regional_ts: pd.DataFrame,
    unit_level: str = "unit",
    group_level: str = "iso3c",
) -> pd.DataFrame:
    """
    Calculate world total timeseries by summing across all regions.

    Creates a timeseries with iso3c="World" containing the sum of all
    regional values for each year.

    Parameters
    ----------
    regional_ts
        Regional timeseries DataFrame with MultiIndex including group level
    unit_level
        Name of unit index level (default: "unit")
    group_level
        Name of group/region index level (default: "iso3c")

    Returns
    -------
    pd.DataFrame
        World total timeseries with same structure as input

    Examples
    --------
    Calculate world emissions from regional data:

    >>> world_emissions = calculate_world_total_timeseries(
    ...     regional_ts=regional_emissions_df, unit_level="unit", group_level="iso3c"
    ... )  # doctest: +SKIP
    """
    units = regional_ts.index.get_level_values(unit_level).unique()
    if len(units) > 1:
        raise IAMCDataError(
            f"Cannot sum across regions with mixed units {list(units)}. "
            f"Normalize to a single unit before calling calculate_world_total_timeseries()."
        )

    world_totals = regional_ts.groupby(level=unit_level).sum()
    world_totals[group_level] = "World"
    world_totals = world_totals.set_index(group_level, append=True)
    world_totals = world_totals.reorder_levels([group_level, unit_level])

    return world_totals
