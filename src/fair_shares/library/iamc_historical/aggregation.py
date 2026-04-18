"""Aggregate CEDS+GFED sectoral historical into top-level IAMC variables."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import pandas as pd

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.iamc_historical.constants import (
    GLOBAL_ONLY_VARIABLES,
    LUC_SECTORS,
    SECTOR_AGGREGATION_RULES,
)
from fair_shares.library.utils.dataframes import get_year_columns

logger = logging.getLogger(__name__)

_ALLOWED_SECTOR_FILTERS = {"all", "ex_luc", "ex_aircraft", "ex_luc_and_aircraft"}


def supported_top_level_variables() -> list[str]:
    """Return IAMC variables the adapter can build from sectoral country history."""
    return sorted(SECTOR_AGGREGATION_RULES)


def aggregate_sectoral_to_top_level(
    history: pd.DataFrame,
    variables: Iterable[str],
    *,
    region_col: str = "region",
    variable_col: str = "variable",
    unit_col: str = "unit",
) -> pd.DataFrame:
    """Sum sectoral child variables into top-level IAMC variables.

    Parameters
    ----------
    history
        Long DataFrame with at least columns ``[region, variable, unit, <years>]``.
        Variable values must be in IAMC ``Emissions|<gas>|<sector>`` form.
    variables
        Top-level variables to produce (e.g. ``"Emissions|CO2|Energy and Industrial Processes"``).
        Only variables listed in :data:`SECTOR_AGGREGATION_RULES` are producible.
    region_col, variable_col, unit_col
        Column names in ``history``.

    Returns
    -------
    pd.DataFrame
        Long DataFrame restricted to the requested ``variables``, with each row
        holding the summed sectoral values. Grouping preserves all non-year,
        non-variable, non-unit columns present in ``history`` (e.g. ``model``,
        ``scenario``, ``region``), so dimensions other than the variable itself
        pass through unchanged.

        When none of the requested variables match any sectoral children in
        ``history``, the return is an empty DataFrame with columns
        ``[region_col, variable_col, unit_col, <year cols>]`` and zero rows.
    """
    year_cols = get_year_columns(history, return_type="original")
    if not year_cols:
        raise DataProcessingError(
            "No year columns found in history (expected integer or digit-string column names in 1700–2200)."
        )
    requested = list(variables)
    unknown = [v for v in requested if v not in SECTOR_AGGREGATION_RULES]
    if unknown:
        raise DataProcessingError(
            f"Unsupported top-level variables: {unknown}. "
            f"Supported: {supported_top_level_variables()}"
        )
    # Group over all non-year, non-variable, non-unit columns so model/scenario
    # and any other dimension pass through unchanged.
    group_cols = [
        c
        for c in history.columns
        if c not in year_cols and c not in {variable_col, unit_col}
    ]
    frames: list[pd.DataFrame] = []
    for top in requested:
        rule = SECTOR_AGGREGATION_RULES[top]
        gas = rule["gas"]
        sector_filter = rule["sector_filter"]
        if sector_filter not in _ALLOWED_SECTOR_FILTERS:
            raise DataProcessingError(
                f"Invalid sector_filter '{sector_filter}' for variable {top}"
            )
        children = history[
            history[variable_col].apply(
                lambda v, g=gas, f=sector_filter: _matches(v, g, f)
            )
        ]
        if children.empty:
            logger.warning(
                "No sectoral children found for %s (gas=%s, filter=%s). "
                "Skipping this variable.",
                top,
                gas,
                sector_filter,
            )
            continue
        units = children[unit_col].unique()
        if len(units) != 1:
            raise DataProcessingError(
                f"Inconsistent units across sectoral children of {top}: {units.tolist()}"
            )
        unit = units[0]
        grouped = (
            children.groupby(group_cols, as_index=False, dropna=False)[year_cols]
            .sum()
            .assign(**{variable_col: top, unit_col: unit})
        )
        frames.append(grouped[[*group_cols, variable_col, unit_col, *year_cols]])
    if not frames:
        return pd.DataFrame(columns=[region_col, variable_col, unit_col, *year_cols])
    return pd.concat(frames, ignore_index=True)


def classify_scenario_variables(
    scenario_variables: Iterable[str],
) -> dict[str, list[str]]:
    """Split scenario variables by which source can produce them at region level.

    Returns a dict with keys:

    * ``producible_ceds`` — built by CEDS+GFED sectoral aggregation (see
      :data:`SECTOR_AGGREGATION_RULES`).
    * ``global_only`` — present only at World level in the pinned sources.
    * ``unknown`` — no regional source in this adapter.
    """
    producible_ceds: list[str] = []
    global_only: list[str] = []
    unknown: list[str] = []
    for v in scenario_variables:
        if v in SECTOR_AGGREGATION_RULES:
            producible_ceds.append(v)
        elif v in GLOBAL_ONLY_VARIABLES:
            global_only.append(v)
        else:
            unknown.append(v)
    return {
        "producible_ceds": sorted(producible_ceds),
        "global_only": sorted(global_only),
        "unknown": sorted(unknown),
    }


# ----------------------------------------------------------------------
# helpers


def _matches(variable: str, gas: str, sector_filter: str) -> bool:
    parts = variable.split("|")
    if len(parts) != 3 or parts[0] != "Emissions" or parts[1] != gas:
        return False
    sector = parts[2]
    if sector_filter == "all":
        return True
    if sector_filter == "ex_luc":
        return sector not in LUC_SECTORS
    if sector_filter == "ex_aircraft":
        return sector != "Aircraft"
    if sector_filter == "ex_luc_and_aircraft":
        return sector not in LUC_SECTORS and sector != "Aircraft"
    return False
