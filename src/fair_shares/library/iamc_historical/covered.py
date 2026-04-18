"""Build ``Emissions|Covered`` from a standard IAMC scenario.

``Emissions|Covered`` is fair-shares' allocation-layer input variable. It
is constructed from a user-selected emission category by summing
IAMC-standard component variables (GWP-weighted where units differ) and
optionally subtracting others.

This module pairs with the IAMC historical back-fill adapter: call
:func:`backfill_and_build_covered` to prepend regional history for every
required component and compute ``Emissions|Covered`` across the full
timeseries in one step.

Adding a new category
---------------------
1. Add an entry to :data:`COVERED_COMPONENTS` with ``add``, ``subtract`` and
   ``output_unit`` keys.
2. Add the key to the :data:`EmissionCategory` Literal.
3. Confirm every ``add`` / ``subtract`` component is either a CEDS+GFED
   sectoral aggregate (producible by
   :mod:`fair_shares.library.iamc_historical.aggregation`) or present in
   the user's scenario natively.
"""

from __future__ import annotations

import logging
from typing import Literal

import pandas as pd
import pyam

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.iamc_historical.backfill import backfill
from fair_shares.library.iamc_historical.region_mapping import RegionMapping

logger = logging.getLogger(__name__)

# Extend the Literal and the COVERED_COMPONENTS dict in lockstep when adding
# a new category.
EmissionCategory = Literal["all-ghg-ex-co2-lulucf"]

COVERED_COMPONENTS: dict[str, dict[str, object]] = {
    "all-ghg-ex-co2-lulucf": {
        "add": [
            "Emissions|CO2|Energy and Industrial Processes",
            "Emissions|CH4",
            "Emissions|N2O",
        ],
        "subtract": [],
        "output_unit": "Mt CO2e/yr",
    },
}


def covered_components(category: EmissionCategory) -> dict[str, object]:
    """Return the ``add`` / ``subtract`` / ``output_unit`` spec for a category."""
    if category not in COVERED_COMPONENTS:
        known = sorted(COVERED_COMPONENTS)
        raise DataProcessingError(
            f"Unknown emission category {category!r}. Known: {known}"
        )
    return COVERED_COMPONENTS[category]


def _conversion_factors(
    units_by_variable: dict[str, str], output_unit: str, gwp: str
) -> dict[str, float]:
    """Per-component multiplier to convert input unit → ``output_unit``.

    Always applies the named GWP context so cross-gas conversions respect the
    user's choice. The fair-shares registry has ``AR6GWP100`` installed as the
    default, so without an explicit context a request for ``AR4GWP100`` would
    silently return AR6 numbers.
    """
    from fair_shares.library.utils.units import get_default_unit_registry

    ur = get_default_unit_registry()
    factors: dict[str, float] = {}
    with ur.context(gwp):
        for variable, input_unit in units_by_variable.items():
            quantity = 1.0 * ur(input_unit)
            factors[variable] = float(quantity.to(output_unit).magnitude)
    return factors


def build_covered(
    scenario_and_history: pyam.IamDataFrame,
    category: EmissionCategory,
    *,
    output_variable: str = "Emissions|Covered",
    gwp: str = "AR6GWP100",
) -> pyam.IamDataFrame:
    """Compute ``Emissions|Covered`` rows and return an IamDataFrame that
    contains the input data plus the computed covered variable.

    Components are converted to the category's ``output_unit`` under the
    chosen GWP context before summing, so mixed-unit inputs (CO2, CH4, N2O,
    F-gases) are handled directly without any intermediate synthetic.
    """
    spec = covered_components(category)
    add = list(spec["add"])  # type: ignore[arg-type]
    subtract = list(spec["subtract"])  # type: ignore[arg-type]
    output_unit = str(spec["output_unit"])
    required = add + subtract
    missing = [v for v in required if v not in set(scenario_and_history.variable)]
    if missing:
        raise DataProcessingError(
            f"Category {category!r} requires components {required}; the input "
            f"IamDataFrame is missing: {missing}"
        )

    df = scenario_and_history.data.copy()

    units_by_variable = (
        df[df["variable"].isin(required)]
        .drop_duplicates(subset=["variable", "unit"])
        .set_index("variable")["unit"]
        .to_dict()
    )
    factors = _conversion_factors(
        units_by_variable, output_unit=output_unit, gwp=gwp
    )

    converted = df[df["variable"].isin(required)].copy()
    converted["value"] = converted["value"] * converted["variable"].map(factors)

    wide = converted.pivot_table(
        index=["scenario", "region", "year"],
        columns="variable",
        values="value",
        aggfunc="first",
    )
    covered = wide[add].sum(axis=1)
    if subtract:
        covered = covered - wide[subtract].sum(axis=1)

    anchor = add[0]
    anchor_rows = (
        df[df["variable"] == anchor][
            ["model", "scenario", "region", "year"]
        ].drop_duplicates(subset=["scenario", "region", "year"])
    )
    covered_df = covered.reset_index(name="value").merge(
        anchor_rows, on=["scenario", "region", "year"], how="left"
    )
    covered_df["variable"] = output_variable
    covered_df["unit"] = output_unit

    out = pd.concat([df, covered_df[df.columns]], ignore_index=True)
    return pyam.IamDataFrame(out)


def backfill_and_build_covered(
    scenario: pyam.IamDataFrame,
    category: EmissionCategory,
    *,
    region_mapping: RegionMapping,
    start_year: int = 1990,
    output_variable: str = "Emissions|Covered",
    gwp: str = "AR6GWP100",
    **backfill_kwargs: object,
) -> pyam.IamDataFrame:
    """One-shot preprocessing: back-fill history for every component of the
    chosen emission category, then compute ``Emissions|Covered``.

    Parameters
    ----------
    scenario
        User's scenario IamDataFrame. Must contain every ``add`` and
        ``subtract`` component of the chosen category.
    category
        Key in :data:`COVERED_COMPONENTS`.
    region_mapping
        Model's country-to-region mapping.
    start_year
        Historical back-fill start year. Default 1990.
    output_variable
        IAMC variable name for the computed result. Default
        ``"Emissions|Covered"``.
    gwp
        GWP context for cross-gas aggregation. Defaults to ``"AR6GWP100"``.
    **backfill_kwargs
        Additional keyword arguments forwarded to
        :func:`fair_shares.library.iamc_historical.backfill`.
    """
    spec = covered_components(category)
    required = list(spec["add"]) + list(spec["subtract"])  # type: ignore[operator]
    missing = [v for v in required if v not in set(scenario.variable)]
    if missing:
        raise DataProcessingError(
            f"Category {category!r} requires components {required}; the "
            f"scenario is missing: {missing}."
        )

    filtered = scenario.filter(variable=required)
    filled = backfill(
        filtered,
        region_mapping=region_mapping,
        start_year=start_year,
        **backfill_kwargs,
    )
    return build_covered(
        filled, category=category, output_variable=output_variable, gwp=gwp
    )
