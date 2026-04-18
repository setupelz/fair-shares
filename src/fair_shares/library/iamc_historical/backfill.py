"""The public ``backfill`` entry point: prepend IAMC history to a scenario."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pyam

from fair_shares.library.exceptions import (
    ConfigurationError,
    DataProcessingError,
)
from fair_shares.library.iamc_historical.aggregation import (
    aggregate_sectoral_to_top_level,
    classify_scenario_variables,
)
from fair_shares.library.iamc_historical.constants import (
    LATEST_IAMC_HISTORICAL_RELEASE,
)
from fair_shares.library.iamc_historical.region_mapping import RegionMapping
from fair_shares.library.iamc_historical.sources import fetch_historical
from fair_shares.library.utils.dataframes import get_year_columns


def _resolve_version_label(version: str) -> str:
    return LATEST_IAMC_HISTORICAL_RELEASE if version == "latest" else version


def _iamc_historical_model_label(version: str) -> str:
    """Build the ``model`` column value for the IAMC historical slice.

    Uses the release's ``title`` field from ``iamc_data_sources.yaml`` if
    present, otherwise falls back to a generic label. Truthful across IAMC
    pipeline generations (CMIP7 today, CMIP8 tomorrow) without Python edits.
    """
    from fair_shares.library.iamc_historical.constants import IAMC_HISTORICAL_RELEASES

    resolved = _resolve_version_label(version)
    rec = IAMC_HISTORICAL_RELEASES.get(resolved, {})
    title = rec.get("title")
    if title:
        return f"{title} ({resolved})"
    return f"IAMC historical ({resolved})"

logger = logging.getLogger(__name__)

RegionMappingLike = RegionMapping | str | Path


def backfill(
    scenario: pyam.IamDataFrame,
    *,
    model: str | None = None,
    region_mapping: RegionMappingLike | None = None,
    start_year: int = 1990,
    variables: list[str] | None = None,
    history_version: str = "latest",
    history_path: str | Path | None = None,
    check_continuity: bool = True,
    continuity_threshold: float = 0.10,
    missing_region_emissions_share_threshold: float = 0.05,
    return_parts: bool = False,
) -> pyam.IamDataFrame | tuple[pyam.IamDataFrame, pyam.IamDataFrame]:
    """Prepend IAMC-consistent history to a scenario IamDataFrame.

    For each (region, variable) pair in ``scenario``, build the corresponding
    historical timeseries from the packaged **IAMC historical composite**
    (CEDS + GFED + Velders + WMO). Current release: CMIP7 ScenarioMIP
    2025.12.07 (Nicholls et al. 2025, concept DOI
    https://doi.org/10.5281/zenodo.15357372) for anthropogenic non-LULUCF
    gases (``Emissions|CO2|Energy and Industrial Processes``,
    ``Emissions|CH4``, ``Emissions|N2O``, aerosols). New releases register
    in ``conf/data_sources/iamc_data_sources.yaml``.

    See ``specs/active/2026-04-17-iamc-historical-backfill-design.md`` for the
    behaviour contract and testing strategy.

    Parameters
    ----------
    scenario
        Scenario emissions, IamDataFrame.
    model
        Model name used to fetch the region mapping. Ignored if
        ``region_mapping`` is passed explicitly.
    region_mapping
        Either a :class:`RegionMapping` instance or a path to a
        nomenclature-style YAML. Required if ``model`` alone cannot resolve
        a known mapping.
    start_year
        Fill history from this year inclusive. Defaults to 1990.
    variables
        Restrict back-fill to this subset. Defaults to auto-detect from
        the scenario.
    history_version
        Zenodo record version to use; ``"latest"`` picks the newest known.
    history_path
        Local override for the historical file. Skips the Zenodo download.
    check_continuity
        If True, warn on (region, variable) pairs where history and scenario
        disagree at the join year by more than ``continuity_threshold``.
    continuity_threshold
        Fractional delta above which to warn.
    missing_region_emissions_share_threshold
        If unmapped regions hold more than this share of join-year total
        emissions, raise :class:`DataProcessingError` rather than silently
        passing through.
    return_parts
        Return ``(history_idf, scenario_idf)`` instead of a concatenated
        single IamDataFrame. If the scenario already starts at or before
        ``start_year``, no back-fill is performed and the first element of
        the tuple is an empty IamDataFrame with no rows.
    """
    if not isinstance(scenario, pyam.IamDataFrame):
        raise TypeError(
            f"scenario must be a pyam.IamDataFrame, got {type(scenario).__name__}"
        )
    mapping = _resolve_mapping(model=model, region_mapping=region_mapping)
    scen_years = sorted(scenario.year)
    first_scen_year = scen_years[0]
    if first_scen_year <= start_year:
        logger.info(
            "Scenario already starts at or before %d; nothing to back-fill.",
            start_year,
        )
        if return_parts:
            empty_hist = _empty_like(scenario)
            return empty_hist, scenario
        return scenario

    requested = list(variables) if variables else list(scenario.variable)
    classified = classify_scenario_variables(requested)
    if classified["unknown"]:
        logger.warning(
            "%d variable(s) have no IAMC historical match and will be left "
            "unchanged: %s",
            len(classified["unknown"]),
            classified["unknown"],
        )
    if classified["global_only"]:
        logger.warning(
            "%d variable(s) are only available at global level in this Zenodo "
            "record and will NOT be back-filled at regional resolution: %s",
            len(classified["global_only"]),
            classified["global_only"],
        )
    producible_ceds = classified["producible_ceds"]

    if not producible_ceds:
        logger.warning(
            "No producible variables in scenario. Returning scenario unchanged."
        )
        if return_parts:
            return _empty_like(scenario), scenario
        return scenario

    history_country = fetch_historical(
        version=history_version,
        kind="country_feather",
        history_path=Path(history_path) if history_path else None,
    )
    history_country = history_country[history_country["scenario"] == "historical"]
    hist_country_only = history_country[history_country["region"] != "global"].copy()
    history_regional = mapping.aggregate(
        hist_country_only,
        country_col="region",
    )
    history_regional = history_regional.assign(
        model=_iamc_historical_model_label(history_version),
        scenario="historical",
    )
    history_top = aggregate_sectoral_to_top_level(
        history_regional, variables=producible_ceds
    )
    history_top = history_top.assign(
        model=_iamc_historical_model_label(history_version),
        scenario="historical",
    )

    # Trim year range: [start_year, first_scen_year - 1] inclusive
    years_to_keep = [
        c
        for c in get_year_columns(history_top, return_type="original")
        if start_year <= int(c) <= first_scen_year - 1
    ]
    history_slim = history_top[
        ["model", "scenario", "region", "variable", "unit", *years_to_keep]
    ].copy()

    # Region coverage check
    _verify_region_coverage(
        scenario=scenario,
        history_slim=history_slim,
        first_scen_year=first_scen_year,
        threshold=missing_region_emissions_share_threshold,
    )

    # Continuity warnings at the join year. Use the pre-trim history_top
    # because history_slim excludes the join year by construction.
    if check_continuity:
        _emit_continuity_warnings(
            scenario=scenario,
            history_full=history_top,
            join_year=first_scen_year,
            threshold=continuity_threshold,
        )

    history_idf = pyam.IamDataFrame(history_slim)
    if return_parts:
        return history_idf, scenario
    return pyam.concat([history_idf, scenario])


# ----------------------------------------------------------------------
# helpers


def _resolve_mapping(
    *, model: str | None, region_mapping: RegionMappingLike | None
) -> RegionMapping:
    if region_mapping is None:
        if model is None:
            raise ConfigurationError(
                "Either 'model' or 'region_mapping' must be supplied"
            )
        raise ConfigurationError(
            f"No built-in mapping known for model '{model}'. Pass "
            "region_mapping=<path to nomenclature YAML> or a RegionMapping instance. "
            "WITCH 7.0 is not yet in IAMconsortium/common-definitions; use the "
            "regions_WITCH_7.0.yml file shipped by the justmip_workflow repo."
        )
    if isinstance(region_mapping, RegionMapping):
        return region_mapping
    if isinstance(region_mapping, (str, Path)):
        return RegionMapping.from_nomenclature_yaml(region_mapping)
    raise ConfigurationError(
        f"Unsupported region_mapping type: {type(region_mapping).__name__}"
    )


def _empty_like(scenario: pyam.IamDataFrame) -> pyam.IamDataFrame:
    empty_df = pd.DataFrame(
        columns=["model", "scenario", "region", "variable", "unit", "year", "value"]
    )
    return pyam.IamDataFrame(empty_df)


def _verify_region_coverage(
    *,
    scenario: pyam.IamDataFrame,
    history_slim: pd.DataFrame,
    first_scen_year: int,
    threshold: float,
) -> None:
    scen_regions = set(scenario.region)
    hist_regions = set(history_slim["region"])
    unmapped = sorted(scen_regions - hist_regions - {"World"})
    if not unmapped:
        return
    # Compute emissions share that falls outside mapping at the join year for
    # variables that are covered by history (same filter as producible).
    scen_df = scenario.data
    join = scen_df[scen_df["year"] == first_scen_year]
    covered_vars = set(history_slim["variable"])
    join_covered = join[join["variable"].isin(covered_vars)]
    total_abs = join_covered["value"].abs().sum()
    missing_abs = join_covered.loc[
        join_covered["region"].isin(unmapped), "value"
    ].abs().sum()
    share = (missing_abs / total_abs) if total_abs > 0 else 0.0
    if share > threshold:
        raise DataProcessingError(
            f"Regions {unmapped} missing from mapping carry {share:.1%} of "
            f"join-year (year={first_scen_year}) absolute emissions across "
            f"covered variables, above threshold {threshold:.1%}. "
            "Pass an extended region_mapping or raise the threshold explicitly."
        )
    logger.warning(
        "Scenario regions not in mapping (%.2f%% of join-year covered emissions): %s",
        share * 100,
        unmapped,
    )


def _emit_continuity_warnings(
    *,
    scenario: pyam.IamDataFrame,
    history_full: pd.DataFrame,
    join_year: int,
    threshold: float,
) -> None:
    scen_df = scenario.data
    join_scen = scen_df[scen_df["year"] == join_year]
    if join_scen.empty:
        return
    year_col_candidates = [
        c
        for c in get_year_columns(history_full, return_type="original")
        if int(c) == join_year
    ]
    if not year_col_candidates:
        return
    col = year_col_candidates[0]
    hist_join = history_full[["region", "variable", col]].rename(columns={col: "hist"})
    merged = join_scen.merge(hist_join, on=["region", "variable"], how="inner")

    # Partition rows by hist status to avoid inf/NaN in the relative delta.
    hist_is_nan = merged["hist"].isna()
    hist_is_zero = (~hist_is_nan) & (merged["hist"] == 0)
    hist_is_finite_pos = (~hist_is_nan) & (merged["hist"] != 0)

    # a) hist == 0 and scen != 0: distinct absolute warning (no relative pct)
    zero_hist_nonzero_scen = merged[hist_is_zero & (merged["value"] != 0)]
    for _, row in zero_hist_nonzero_scen.iterrows():
        logger.warning(
            "Continuity: history is zero, scenario is %.3g at year %d for "
            "region=%s variable=%s.",
            row["value"],
            join_year,
            row["region"],
            row["variable"],
        )

    # b) both zero: silent pass (no-op)

    # c) hist is NaN: data-gap warning
    nan_hist = merged[hist_is_nan]
    for _, row in nan_hist.iterrows():
        logger.warning(
            "Continuity: history is missing (NaN) at year %d for "
            "region=%s variable=%s (scen=%.3g).",
            join_year,
            row["region"],
            row["variable"],
            row["value"],
        )

    # d) hist is finite non-zero: standard relative-delta check
    finite = merged[hist_is_finite_pos].copy()
    finite["delta"] = (finite["value"] - finite["hist"]).abs() / finite["hist"].abs()
    bad = finite[finite["delta"] > threshold]
    for _, row in bad.iterrows():
        logger.warning(
            "Continuity: scenario and history differ by %.1f%% at year %d for "
            "region=%s variable=%s (scen=%.3g hist=%.3g).",
            row["delta"] * 100,
            join_year,
            row["region"],
            row["variable"],
            row["value"],
            row["hist"],
        )


