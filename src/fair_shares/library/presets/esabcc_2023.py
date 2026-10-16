"""ESABCC 2023 / PRR2023 allocation preset.

The European Scientific Advisory Board on Climate Change (ESABCC) based its
2023 advice on the EU 2040 target on the equity analysis in Pelz, Rogelj and
Riahi (2023), referred to here as PRR2023. Notebook
``601_reproduce_esabcc_2023`` reproduces that analysis. This module holds its
approach grid so that other tools run the same settings.

Several library defaults differ from the PRR2023 settings: the functional form
(``"asinh"`` against ``"power"``), ``cumulative_end_year`` (none against 2050),
``capability_reference_year`` (none against a 1990 or 2014 snapshot) and
``pre_allocation_responsibility_year`` (1990 against the 1850 or 1990 window
start). The preset states these parameters for the approaches that use them,
so a run built from it takes no library default for them.
"""

from __future__ import annotations

from typing import Any

from fair_shares.library.allocations.manager import _expand_parameters

ESABCC_2023_RCB_ANCHOR: dict[str, Any] = {
    "source": "ar6_2020",
    "climate-assessment": "1.5C",
    "quantile": 0.5,
}
"""The PRR2023 budget anchor: AR6 remaining carbon budget from 2020, 1.5C, 50%."""

ESABCC_2023_CATEGORIES: tuple[str, ...] = (
    "co2-ffi",
    "all-ghg-ex-co2-lulucf",
    "all-ghg",
)
"""Emission categories the preset covers. ``co2-ffi`` is the report's own scope."""


def _co2_ffi_allocations() -> dict[str, list[dict[str, list[Any]]]]:
    return {
        "equal-per-capita-budget": [
            # EPC: PRR2023 Eq. 1-2, single-year population shares
            {
                "allocation_year": [1990, 2015],
                "preserve_allocation_year_shares": [True],
            },
            # ECPC: PRR2023 Eq. 1-2, cumulative population to 2050
            {
                "allocation_year": [1990, 2015],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
            },
        ],
        "per-capita-adjusted-budget": [
            # Responsibility, EPC base, ay=1990: window 1850-1989 (Table 18)
            {
                "allocation_year": [1990],
                "pre_allocation_responsibility_weight": [1.0],
                "pre_allocation_responsibility_year": [1850],
                "pre_allocation_responsibility_functional_form": ["power"],
                "pre_allocation_responsibility_exponent": [1.0, 0.5],
                "pre_allocation_responsibility_per_capita": [True, False],
                "preserve_allocation_year_shares": [True],
            },
            # Responsibility, EPC base, ay=2015: windows 1850-2014 and 1990-2014
            {
                "allocation_year": [2015],
                "pre_allocation_responsibility_weight": [1.0],
                "pre_allocation_responsibility_year": [1850, 1990],
                "pre_allocation_responsibility_functional_form": ["power"],
                "pre_allocation_responsibility_exponent": [1.0, 0.5],
                "pre_allocation_responsibility_per_capita": [True, False],
                "preserve_allocation_year_shares": [True],
            },
            # Responsibility, ECPC base, ay=1990
            {
                "allocation_year": [1990],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
                "pre_allocation_responsibility_weight": [1.0],
                "pre_allocation_responsibility_year": [1850],
                "pre_allocation_responsibility_functional_form": ["power"],
                "pre_allocation_responsibility_exponent": [1.0, 0.5],
                "pre_allocation_responsibility_per_capita": [True, False],
            },
            # Responsibility, ECPC base, ay=2015
            {
                "allocation_year": [2015],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
                "pre_allocation_responsibility_weight": [1.0],
                "pre_allocation_responsibility_year": [1850, 1990],
                "pre_allocation_responsibility_functional_form": ["power"],
                "pre_allocation_responsibility_exponent": [1.0, 0.5],
                "pre_allocation_responsibility_per_capita": [True, False],
            },
            # Capability, EPC base: GDP-per-capita snapshot in 1990 / 2014
            {
                "allocation_year": [1990],
                "capability_weight": [1.0],
                "capability_functional_form": ["power"],
                "capability_exponent": [1.0, 0.5],
                "capability_per_capita": [True],
                "capability_reference_year": [1990],
                "preserve_allocation_year_shares": [True],
            },
            {
                "allocation_year": [2015],
                "capability_weight": [1.0],
                "capability_functional_form": ["power"],
                "capability_exponent": [1.0, 0.5],
                "capability_per_capita": [True],
                "capability_reference_year": [2014],
                "preserve_allocation_year_shares": [True],
            },
            # Capability, ECPC base
            {
                "allocation_year": [1990],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
                "capability_weight": [1.0],
                "capability_functional_form": ["power"],
                "capability_exponent": [1.0, 0.5],
                "capability_per_capita": [True],
                "capability_reference_year": [1990],
            },
            {
                "allocation_year": [2015],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
                "capability_weight": [1.0],
                "capability_functional_form": ["power"],
                "capability_exponent": [1.0, 0.5],
                "capability_per_capita": [True],
                "capability_reference_year": [2014],
            },
        ],
    }


def _composite_allocations(
    responsibility_years: list[int],
) -> dict[str, list[dict[str, list[Any]]]]:
    # Allocation starts in 2015 only; the library derives the non-CO2 pathway
    # configurations from these budget entries.
    return {
        "equal-per-capita-budget": [
            {
                "allocation_year": [2015],
                "preserve_allocation_year_shares": [True],
            },
            {
                "allocation_year": [2015],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
            },
        ],
        "per-capita-adjusted-budget": [
            # Responsibility, EPC base
            {
                "allocation_year": [2015],
                "pre_allocation_responsibility_weight": [1.0],
                "pre_allocation_responsibility_year": list(responsibility_years),
                "pre_allocation_responsibility_functional_form": ["power"],
                "pre_allocation_responsibility_exponent": [1.0, 0.5],
                "pre_allocation_responsibility_per_capita": [True, False],
                "preserve_allocation_year_shares": [True],
            },
            # Responsibility, ECPC base
            {
                "allocation_year": [2015],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
                "pre_allocation_responsibility_weight": [1.0],
                "pre_allocation_responsibility_year": list(responsibility_years),
                "pre_allocation_responsibility_functional_form": ["power"],
                "pre_allocation_responsibility_exponent": [1.0, 0.5],
                "pre_allocation_responsibility_per_capita": [True, False],
            },
            {
                "allocation_year": [2015],
                "capability_weight": [1.0],
                "capability_functional_form": ["power"],
                "capability_exponent": [1.0, 0.5],
                "capability_per_capita": [True],
                "capability_reference_year": [2014],
                "preserve_allocation_year_shares": [True],
            },
            {
                "allocation_year": [2015],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
                "capability_weight": [1.0],
                "capability_functional_form": ["power"],
                "capability_exponent": [1.0, 0.5],
                "capability_per_capita": [True],
                "capability_reference_year": [2014],
            },
        ],
    }


def esabcc_2023_allocations(
    emission_category: str,
) -> dict[str, list[dict[str, list[Any]]]]:
    """Return the ESABCC 2023 / PRR2023 allocation grid for one emission category.

    The grid is the one notebook ``601_reproduce_esabcc_2023`` runs. Source:
    Pelz, Rogelj and Riahi (2023), the equity analysis behind the ESABCC 2023
    advice on the EU 2040 target.

    ``co2-ffi`` is the report's full matrix: equal per capita (EPC) and equal
    cumulative per capita (ECPC, population to 2050) budgets from 1990 and
    2015; responsibility penalties 1/x and 1/sqrt(x) over 1850-1989 (from 1990)
    and 1850-2014 or 1990-2014 (from 2015), total and per capita, on both
    bases; capability penalties 1/x and 1/sqrt(x) on a GDP-per-capita snapshot
    in 1990 or 2014, on both bases. The two all-GHG categories extend the report.
    They allocate from 2015 only. ``all-ghg-ex-co2-lulucf`` keeps the 1850 and
    1990 windows. ``all-ghg`` starts its window in 2000, where national land-use
    data begin.

    Every approach names its functional form (``"power"``), its responsibility
    window start or capability snapshot year, and, on the ECPC base,
    ``cumulative_end_year=2050``, so the library defaults for these
    parameters do not apply.

    Parameters
    ----------
    emission_category
        One of ``"co2-ffi"``, ``"all-ghg-ex-co2-lulucf"`` or ``"all-ghg"``.

    Returns
    -------
    dict
        Approach name mapped to a list of parameter grids, each value a list.
        This is the ``allocations`` argument of
        :func:`fair_shares.library.notebook_helpers.run_all_allocations`. Use
        :func:`esabcc_2023_allocation_list` for the single-allocation form that
        :func:`fair_shares.library.python_api.calculate_allocation_timeseries`
        takes. Each call returns a new object.
    """
    if emission_category == "co2-ffi":
        return _co2_ffi_allocations()
    if emission_category == "all-ghg-ex-co2-lulucf":
        return _composite_allocations(responsibility_years=[1850, 1990])
    if emission_category == "all-ghg":
        return _composite_allocations(responsibility_years=[2000])
    raise ValueError(
        f"No ESABCC 2023 preset for emission category {emission_category!r}. "
        f"Choose one of {list(ESABCC_2023_CATEGORIES)}."
    )


def esabcc_2023_allocation_list(
    emission_category: str,
) -> list[dict[str, dict[str, Any]]]:
    """Expand the preset grid into single allocations with scalar parameters.

    Each item has the form ``{approach: {parameter: value}}`` and can be passed
    as the ``allocation`` argument of
    :func:`fair_shares.library.python_api.calculate_allocation_timeseries`.
    The order follows the grid order of :func:`esabcc_2023_allocations`.
    """
    return [
        {approach: params}
        for approach, grids in esabcc_2023_allocations(emission_category).items()
        for grid in grids
        for params in _expand_parameters(grid)
    ]
