"""
Unit conversion and registry utilities for allocation calculations.

This module consolidates unit conversion and unit registry functionality.
It provides:
- A configured Pint registry with climate-specific units
- Robust unit conversion with automatic cleaning
- Single-unit normalization for DataFrames
"""

from __future__ import annotations

import functools
import re
from typing import TYPE_CHECKING

from pandas_openscm.unit_conversion import convert_unit
from pint import Context

from fair_shares.library.exceptions import (
    DataProcessingError,
    MissingOptionalDependencyError,
)

if TYPE_CHECKING:
    import pint.facets

    from .core.types import TimeseriesDataFrame


# ============================================================================
# Unit Registry
# ============================================================================


@functools.cache
def get_default_unit_registry() -> pint.facets.PlainRegistry:
    """
    Get the default unit registry to use throughout the codebase.

    This registry is configured with climate-specific units and contexts
    needed for fair share allocation calculations. It includes:
    - Magnitude units (thousand, million, billion)
    - Emission units (kt, Mt, CO2e, gigagram)
    - Annual conversion contexts
    - AR6GWP100 context for greenhouse gas equivalencies

    This is the standard unit registry used by default in all allocation
    functions and unit conversion utilities. Custom registries can be
    supplied directly to individual functions if needed.

    Returns
    -------
    :
        Configured unit registry with climate-specific units and contexts

    Raises
    ------
    MissingOptionalDependencyError
        `openscm_units` is not installed
    """
    try:
        import openscm_units

        ur = openscm_units.ScmUnitRegistry()
    except ImportError:
        raise MissingOptionalDependencyError(
            "get_default_unit_registry", "openscm_units"
        )

    ur.add_standards()

    # Add magnitude units used in the codebase
    ur.define("thousand = 1000")
    ur.define("million = thousand * 1000")
    ur.define("billion = million * 1000")

    # Add CO2 emission units used in the codebase
    ur.define("kt = 1000 * kg")
    ur.define("Mt = 1000000 * kg")
    ur.define("Gt = 1000000000 * kg")  # 1 Gt = 1000 Mt
    ur.define("CO2e = CO2")  # CO2e is equivalent to CO2

    # Add gigagram units for PRIMAP data processing
    ur.define("gigagram = kt")

    # Add conversion trick: set annum (a) as 1 to convert data provided in
    # annual rates to totals. This allows converting e.g. "Gigagram * CO2 / a"
    # to "Gigagram * CO2" which is the more common way to represent this here.
    # NOTE: The assumption here is that data is always interval data - so it
    # represents the total cumulative value over the year.
    ur.define("a = 1 = annum = year")

    # Add transformation to convert mass/time to mass by assuming 1 year
    # This allows converting e.g. "ktCO2 / yr" to "kt CO2" or
    # "kt CO2 / month" to "kt CO2"
    annual_context = Context("assume-annual")
    annual_context.add_transformation(
        "[mass] / [time]",
        "[mass]",
        lambda ureg, x: x.to("mass / yr").magnitude * ureg("mass"),
    )
    ur.add_context(annual_context)

    # Enable both AR6GWP100 and assume-annual contexts by default
    ur.enable_contexts("AR6GWP100", "assume-annual")

    return ur


# ============================================================================
# Unit Conversion
# ============================================================================


def _clean_unit_string(unit_str: str) -> str:
    """Clean unit strings to be compatible with Pint.

    This function handles common unit formats that are incompatible with Pint.
    """
    # Handle CO2-equiv -> CO2e (hyphens not allowed in Pint unit names)
    unit_str = unit_str.replace("CO2-equiv", "CO2e")
    # Add spaces around / and * operators when they don't already have spaces
    unit_str = re.sub(r"(\S)([/\*])(\S)", r"\1 \2 \3", unit_str)
    # You can add more cleaning rules here if needed..
    # unit_str = ....
    return unit_str


def convert_unit_robust(
    df: TimeseriesDataFrame,
    target_unit: str,
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> TimeseriesDataFrame:
    """
    Convert units with automatic cleaning of unit formats.

    This wrapper around pandas_openscm's convert_unit automatically cleans
    unit strings to handle common formats that are incompatible with Pint.

    Parameters
    ----------
    df
        TimeseriesDataFrame to convert
    target_unit
        Target unit to convert to
    unit_level
        Name of the level containing units (default: "unit")
    ur
        Unit registry to use (defaults to openscm-units registry)

    Returns
    -------
    :
        DataFrame with converted units

    Raises
    ------
    DataProcessingError
        If unit conversion fails after cleaning
    """
    # Clean both target and source units
    target_unit = _clean_unit_string(target_unit)

    # Clean source units in the index
    df_cleaned = df.copy()
    if hasattr(df_cleaned.index, "levels"):
        # MultiIndex case
        level_idx = df_cleaned.index.names.index(unit_level)
        levels = list(df_cleaned.index.levels)
        levels[level_idx] = levels[level_idx].map(_clean_unit_string)
        df_cleaned.index = df_cleaned.index.set_levels(levels)
    else:
        # Single index case - assume it contains the units
        if df_cleaned.index.name == unit_level:
            df_cleaned.index = df_cleaned.index.map(_clean_unit_string)

    # Get the unit for display
    if hasattr(df_cleaned.index, "levels"):
        source_unit = df_cleaned.index.get_level_values(unit_level)[0]
    else:
        source_unit = df_cleaned.index[0]
    print(f"Converting units from {source_unit} to {target_unit}")

    return convert_unit(df_cleaned, target_unit, unit_level=unit_level, ur=ur)


def set_single_unit(
    df: TimeseriesDataFrame,
    unit_level: str,
    ur: pint.facets.PlainRegistry = None,
) -> TimeseriesDataFrame:
    """
    Convert DataFrame to have a single unit by converting all units to the first unit.

    Parameters
    ----------
    df
        DataFrame to convert to single unit
    unit_level
        Name of the index level containing units
    ur
        Unit registry to use for conversions (defaults to openscm-units registry)

    Returns
    -------
    :
        DataFrame with all data converted to the first unit found

    Raises
    ------
    DataProcessingError
        If the DataFrame has no units
    """
    if ur is None:
        ur = get_default_unit_registry()

    if hasattr(df.index, "levels"):
        # MultiIndex case
        units = df.index.get_level_values(unit_level).unique()
    else:
        # Single index case
        if df.index.name == unit_level:
            units = df.index.unique()
        else:
            raise DataProcessingError(
                f"Index name '{df.index.name}' does not match unit_level '{unit_level}'"
            )

    if len(units) == 0:
        raise DataProcessingError("No units found in DataFrame")

    # Get the first unit to convert everything to
    target_unit = units[0]

    # If there's only one unit, return the DataFrame as-is
    if len(units) == 1:
        return df

    # Clean the target unit and convert all units to the first unit found
    target_unit = _clean_unit_string(target_unit)
    return convert_unit(df, target_unit, unit_level=unit_level, ur=ur)


__all__ = [
    "_clean_unit_string",  # Used by notebooks, keep for backwards compatibility
    "convert_unit_robust",
    "get_default_unit_registry",
    "set_single_unit",
]
