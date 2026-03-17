"""Country-level non-CO2 GHG derivation from PRIMAP timeseries data.

Non-CO2 emissions are derived by subtraction:
    non_co2 = all_ghg_ex_co2_lulucf - co2_ffi

Both inputs must be in standard timeseries format:
    MultiIndex: (iso3c, unit, emission-category)
    Columns: year strings ("2000", "2001", ...)
"""

from __future__ import annotations

import logging
import warnings

import pandas as pd

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils.dataframes import TimeseriesDataFrame, get_year_columns

logger = logging.getLogger(__name__)

NON_CO2_CATEGORY = "non-co2"


def _drop_category_level(
    df: pd.DataFrame,
    cat_level: str = "emission-category",
) -> pd.DataFrame:
    """Strip the emission-category index level, grouping by remaining levels.

    Parameters
    ----------
    df
        DataFrame whose MultiIndex may contain *cat_level*.
    cat_level
        Name of the index level to drop (default ``"emission-category"``).

    Returns
    -------
    pd.DataFrame
        DataFrame with *cat_level* removed and values summed across that level.

    Warns
    -----
    UserWarning
        If the DataFrame contains more than one unique value in *cat_level*,
        values are summed across categories (which may be unintended).
    """
    idx = df.index
    if cat_level not in idx.names:
        return df
    # Guard against multiple categories being silently summed
    n_categories = idx.get_level_values(cat_level).nunique()
    if n_categories > 1:
        cats = idx.get_level_values(cat_level).unique().tolist()
        warnings.warn(
            f"Input DataFrame contains {n_categories} emission categories "
            f"({cats}); expected exactly 1. Values will be summed across "
            f"categories, which may be incorrect.",
            UserWarning,
            stacklevel=3,
        )
    remaining = [n for n in idx.names if n != cat_level]
    return df.droplevel(cat_level).groupby(level=remaining).sum(min_count=1)


def derive_non_co2_country_timeseries(
    all_ghg_ex_co2_lulucf: TimeseriesDataFrame,
    co2_ffi: TimeseriesDataFrame,
) -> TimeseriesDataFrame:
    """Derive country-level non-CO2 GHG timeseries by subtracting CO2-FFI from
    all-GHG-ex-CO2-LULUCF.

    Non-CO2 is not a standalone PRIMAP category — it is computed as:
        non_co2 = all_ghg_ex_co2_lulucf - co2_ffi

    Parameters
    ----------
    all_ghg_ex_co2_lulucf
        PRIMAP timeseries for all-GHG-ex-CO2-LULUCF.
        MultiIndex: (iso3c, unit, emission-category), columns are year strings.
    co2_ffi
        PRIMAP timeseries for CO2-FFI.
        MultiIndex: (iso3c, unit, emission-category), columns are year strings.

    Returns
    -------
    TimeseriesDataFrame
        Non-CO2 timeseries in standard format.
        MultiIndex: (iso3c, unit, "non-co2"), columns are year strings.
        Countries present in only one input will have NaN for missing years.
        Year columns are the intersection of both inputs' year columns.

    Notes
    -----
    - Units must be consistent across both inputs (no unit conversion is performed).
    - Countries present in one DataFrame but not the other receive NaN values for
      the missing counterpart, propagating NaN into the result.
    - The result's emission-category index level is set to NON_CO2_CATEGORY.

    Raises
    ------
    DataProcessingError
        If the two inputs have different unit sets (e.g. MtCO2 vs GtCO2).
    """
    ghg_no_cat = _drop_category_level(all_ghg_ex_co2_lulucf)
    ffi_no_cat = _drop_category_level(co2_ffi)

    # Verify unit consistency between inputs before subtracting
    ghg_units = set(ghg_no_cat.index.get_level_values("unit").unique())
    ffi_units = set(ffi_no_cat.index.get_level_values("unit").unique())
    if ghg_units != ffi_units:
        raise DataProcessingError(
            f"Unit mismatch between inputs: all-GHG uses {ghg_units}, "
            f"CO2-FFI uses {ffi_units}. Cannot subtract — convert to "
            f"common units before calling derive_non_co2_country_timeseries()."
        )

    # Align on shared year columns; use union of countries (outer join on index)
    ghg_years = set(get_year_columns(ghg_no_cat))
    shared_years = [c for c in get_year_columns(ffi_no_cat) if c in ghg_years]

    ghg_aligned = ghg_no_cat[shared_years].reindex(
        ghg_no_cat.index.union(ffi_no_cat.index)
    )
    ffi_aligned = ffi_no_cat[shared_years].reindex(
        ghg_no_cat.index.union(ffi_no_cat.index)
    )

    non_co2 = ghg_aligned.subtract(ffi_aligned)

    # W2: Warn on physically implausible negative non-CO2 values
    negative_mask = (non_co2 < 0).any(axis=1)
    if negative_mask.any():
        neg_countries = [idx[0] for idx in non_co2[negative_mask].index]
        warnings.warn(
            f"Negative non-CO2 values detected for {len(neg_countries)} "
            f"country/unit combinations (first 5: {neg_countries[:5]}). "
            f"This may indicate inconsistent input data.",
            UserWarning,
            stacklevel=2,
        )

    # Re-attach emission-category level
    non_co2.index = pd.MultiIndex.from_tuples(
        [(iso3c, unit, NON_CO2_CATEGORY) for iso3c, unit in non_co2.index],
        names=["iso3c", "unit", "emission-category"],
    )

    return non_co2


def derive_non_co2_world_scenarios(
    all_ghg_ex_co2_lulucf: pd.DataFrame,
    co2_ffi: pd.DataFrame,
) -> pd.DataFrame:
    """Derive world non-CO2 scenarios by subtracting CO2-FFI from all-GHG-ex-CO2-LULUCF.

    Works with processed world scenario data that has been filtered to World region
    and has index levels including (climate-assessment, quantile, ..., emission-category).

    Parameters
    ----------
    all_ghg_ex_co2_lulucf
        World scenarios for all-GHG-ex-CO2-LULUCF.
    co2_ffi
        World scenarios for CO2-FFI.

    Returns
    -------
    pd.DataFrame
        Non-CO2 world scenarios with emission-category set to "non-co2".
    """
    cat_level = "emission-category"

    ghg_no_cat = _drop_category_level(all_ghg_ex_co2_lulucf, cat_level)
    ffi_no_cat = _drop_category_level(co2_ffi, cat_level)

    # Align on shared year columns
    ghg_years = set(get_year_columns(ghg_no_cat))
    shared_years = [c for c in get_year_columns(ffi_no_cat) if c in ghg_years]

    # Align on the union of index entries (outer join)
    union_idx = ghg_no_cat.index.union(ffi_no_cat.index)
    ghg_aligned = ghg_no_cat[shared_years].reindex(union_idx)
    ffi_aligned = ffi_no_cat[shared_years].reindex(union_idx)

    non_co2 = ghg_aligned.subtract(ffi_aligned)

    # Warn on physically implausible negative non-CO2 values
    negative_mask = (non_co2 < 0).any(axis=1)
    if negative_mask.any():
        n_neg = negative_mask.sum()
        warnings.warn(
            f"Negative non-CO2 values detected for {n_neg} "
            f"index combinations. This may indicate inconsistent input data.",
            UserWarning,
            stacklevel=2,
        )

    # Re-attach emission-category level at its original position
    original_names = list(all_ghg_ex_co2_lulucf.index.names)
    if cat_level in original_names:
        cat_pos = original_names.index(cat_level)
    else:
        cat_pos = len(non_co2.index.names)

    # Build new tuples with NON_CO2_CATEGORY inserted at the right position
    if isinstance(non_co2.index, pd.MultiIndex):
        new_tuples = []
        for tup in non_co2.index:
            tup_list = list(tup)
            tup_list.insert(cat_pos, NON_CO2_CATEGORY)
            new_tuples.append(tuple(tup_list))
        remaining_names = list(non_co2.index.names)
        remaining_names.insert(cat_pos, cat_level)
        non_co2.index = pd.MultiIndex.from_tuples(new_tuples, names=remaining_names)
    else:
        # Single-level index — just add the category level
        non_co2.index = pd.MultiIndex.from_arrays(
            [non_co2.index, [NON_CO2_CATEGORY] * len(non_co2)],
            names=[non_co2.index.name or "index", cat_level],
        )

    return non_co2
