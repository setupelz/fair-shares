"""
IAMC Data Format Adapter for fair-shares Allocations.

This module provides utilities to load IAMC-format data using pyam and transform it
for use with fair-shares allocation functions.

IAMC Format Requirements
------------------------
Your data must be in standard IAMC format with columns:
- model: Model name (e.g., "MESSAGEix-GLOBIOM")
- scenario: Scenario name (e.g., "SSP2-Baseline")
- region: Region identifier (e.g., "USA", "R12_CHN")
- variable: Variable name (e.g., "Population", "Emissions|CO2")
- unit: Unit string (e.g., "million", "Mt CO2/yr")
- Year columns: 1990, 2000, 2010, ..., 2100 (numeric or string)

Required Variables by Approach
------------------------------
- equal-per-capita-budget: Population
- per-capita-adjusted-budget: Population, Emissions (for responsibility),
  GDP|PPP (for capability)

Data Coverage
-------------
Your data should span from `allocation_start_year` (typically 1990 for
historical responsibility) through `budget_end_year` (your model's final
timestep, e.g., 2100 or 2110).

Example Usage
-------------
>>> from fair_shares.library.utils.data.iamc import load_iamc_data
>>> data = load_iamc_data(
...     data_file="my_scenario.csv",
...     population_variable="Population",
...     emissions_variable="Emissions|CO2",
...     gdp_variable="GDP|PPP",
...     regions=["USA", "CHN", "EUR", "IND", "JPN", "OAS", "LAM", "AFR", "MEA", "FSU"],
...     allocation_start_year=1990,
...     budget_end_year=2100,
... )
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
        Required for responsibility-adjusted approaches.
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
        First year of data required (for historical responsibility).
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
    Normalize GDP units from billion to million for allocation functions.

    IAMC data commonly uses "billion USD/yr" but allocation functions expect
    "million USD/yr". This converts the units and scales values appropriately.

    Parameters
    ----------
    gdp_df
        GDP timeseries DataFrame with MultiIndex including unit level
    unit_level
        Name of the unit index level (default: "unit")

    Returns
    -------
    DataFrame
        GDP data with normalized units in million USD/yr
    """
    # Get current units
    units = gdp_df.index.get_level_values(unit_level).unique()

    # Check if conversion is needed
    if len(units) != 1:
        raise IAMCDataError(f"Expected single GDP unit, found multiple: {list(units)}")

    current_unit = units[0]

    # Normalize units to simple "million" for pint compatibility
    # IAMC units often have complex strings like "billion US$2010/yr" which
    # contain characters ($, numbers) that pint can't parse

    if "billion" in current_unit.lower():
        # Convert values: billion to million is *1000
        gdp_df = gdp_df * 1000
        new_unit = "million"

        # Recreate index with new unit
        new_index = gdp_df.index.to_frame()
        new_index[unit_level] = new_unit
        gdp_df.index = pd.MultiIndex.from_frame(new_index)

    elif "million" in current_unit.lower():
        # Units already in millions, just simplify the label
        new_unit = "million"

        # Recreate index with new unit
        new_index = gdp_df.index.to_frame()
        new_index[unit_level] = new_unit
        gdp_df.index = pd.MultiIndex.from_frame(new_index)

    else:
        # Unknown units - warn user
        import warnings

        warnings.warn(
            f"GDP units '{current_unit}' don't contain 'billion' or 'million'. "
            f"Allocation functions expect GDP in millions. Results may be incorrect.",
            UserWarning,
        )

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
    unit_conversion: float = 1.0 / 1000,  # Default: Mt to Gt
) -> pd.Series:
    """
    Calculate cumulative emissions over a time period from timeseries data.

    For timestep data (e.g., 5-year intervals), this function correctly accounts
    for the period each value represents using backward fill logic.

    Parameters
    ----------
    emissions_ts
        Emissions timeseries DataFrame with year columns and region index
    start_year
        First year to include in cumulative sum
    end_year
        Last year to include in cumulative sum
    unit_conversion
        Factor to convert units (default: Mt to Gt = 1/1000)

    Returns
    -------
    pd.Series
        Cumulative emissions by region in converted units

    Examples
    --------
    Calculate regional cumulative budgets from IAMC emissions data:

    >>> cumulative = calculate_cumulative_emissions(
    ...     emissions_ts=emissions_df,
    ...     start_year=2015,
    ...     end_year=2100,
    ...     unit_conversion=1.0 / 1000,  # Mt to Gt
    ... )  # doctest: +SKIP
    """
    # Get year columns in range
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

    # Calculate cumulative for each region
    cumulative = pd.Series(index=emissions_ts.index, dtype=float)

    for idx in emissions_ts.index:
        total = 0
        prev_year = None

        for year_str in year_cols:
            year = int(year_str)
            annual_rate = emissions_ts.loc[idx, year_str]

            # Calculate years in this period (backward fill logic)
            if prev_year is None:
                years_in_period = 1  # First year
            else:
                years_in_period = year - prev_year

            # Add cumulative emissions for this period
            total += annual_rate * years_in_period * unit_conversion
            prev_year = year

        cumulative[idx] = total

    return cumulative


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
    # Sum across all groups/regions
    world_totals = regional_ts.groupby(level=unit_level).sum()

    # Add group level back with "World" identifier
    world_totals[group_level] = "World"
    world_totals = world_totals.set_index(group_level, append=True)
    world_totals = world_totals.reorder_levels([group_level, unit_level])

    return world_totals
