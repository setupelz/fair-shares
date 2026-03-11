"""Remaining Carbon Budget (RCB) processing logic."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from fair_shares.library.config.models import AdjustmentsConfig
from fair_shares.library.exceptions import ConfigurationError, DataLoadingError
from fair_shares.library.utils import (
    ensure_string_year_columns,
    parse_rcb_scenario,
    process_rcb_to_2020_baseline,
)
from fair_shares.library.utils.data.nghgi import (
    compute_bunker_deduction,
    compute_gidden_medians,
    compute_lulucf_convention_gap,
    compute_scenario_median_cumulative,
    load_ar6_category_constants,
    load_bunker_timeseries,
    load_gidden_lulucf_components,
    load_gidden_per_scenario_nz_years,
    load_nghgi_lulucf_historical,
    map_scenario_to_ar6_category,
)

# Last year of Grassi historical NGHGI LULUCF data
_GRASSI_SPLICE_YEAR = 2022


def _load_shared_timeseries(
    adjustments: AdjustmentsConfig,
    project_root: Path,
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load scenario-invariant timeseries data (NGHGI LULUCF and bunkers).

    Called once before the scenario loop to avoid repeated Excel reads.

    Returns
    -------
    tuple[pd.DataFrame, pd.DataFrame]
        (nghgi_ts, bunker_ts)
    """
    nghgi_path = project_root / adjustments.lulucf_nghgi.path
    if verbose:
        print(f"    Loading NGHGI LULUCF from: {nghgi_path}")
    nghgi_ts = load_nghgi_lulucf_historical(nghgi_path)

    bunker_path = project_root / adjustments.bunkers.path
    if verbose:
        print(f"    Loading bunker timeseries from: {bunker_path}")
    bunker_ts = load_bunker_timeseries(bunker_path)

    return nghgi_ts, bunker_ts


def _get_gidden_components(
    ar6_category: str,
    project_root: Path,
    cache: dict[str, tuple[pd.DataFrame, pd.DataFrame]],
    verbose: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load Gidden LULUCF components (per-scenario), cached by AR6 category.

    Multiple scenarios map to the same AR6 category (e.g. "1.5p50" and
    "1.5p66" both map to C1), so caching avoids redundant Excel reads.

    Returns per-scenario DataFrames with (model, scenario) MultiIndex.
    """
    if ar6_category in cache:
        return cache[ar6_category]

    gidden_path = project_root / "data/scenarios/ipcc_ar6_gidden/ar6_gidden.xlsx"
    if verbose:
        print(
            f"    Loading Gidden LULUCF components ({ar6_category}) from: {gidden_path}"
        )
    result = load_gidden_lulucf_components(gidden_path, ar6_category)
    cache[ar6_category] = result
    return result


def _get_gidden_nz_years(
    ar6_category: str,
    project_root: Path,
    cache: dict[str, pd.Series],
    verbose: bool = True,
) -> pd.Series:
    """Load per-scenario total CO₂ net-zero years, cached by AR6 category."""
    if ar6_category in cache:
        return cache[ar6_category]

    gidden_path = project_root / "data/scenarios/ipcc_ar6_gidden/ar6_gidden.xlsx"
    if verbose:
        print(
            f"    Loading per-scenario NZ years ({ar6_category}) from: {gidden_path}"
        )
    result = load_gidden_per_scenario_nz_years(gidden_path, ar6_category)
    if verbose:
        print(
            f"      {len(result)} scenarios with NZ years "
            f"(range: {result.min()}-{result.max()})"
        )
    cache[ar6_category] = result
    return result


def _resolve_adjustment_scalars(
    scenario: str,
    net_zero_year: int,
    nghgi_ts: pd.DataFrame,
    bunker_ts: pd.DataFrame,
    gidden_direct_scenarios: pd.DataFrame,
    gidden_indirect_scenarios: pd.DataFrame,
    per_scenario_nz_years: pd.Series,
    emission_category: str = "co2-ffi",
    precautionary_lulucf: bool = True,
    verbose: bool = True,
) -> tuple[float, float]:
    """Compute sign-ready adjustment scalars for a given scenario.

    Follows the "integrate first, median second" aggregation order of
    Weber et al. (2026): cumulative emissions are computed per scenario,
    then the median is taken across scenarios.

    LULUCF corrections use **per-scenario** net-zero years as the integration
    endpoint, so each scenario is integrated exactly to the year its
    total CO₂ (Emissions|CO2 = fossil + BM LULUCF) reaches zero. Bunker
    deductions still use the **category-level** median net-zero year.

    Returns values that can be added directly to the budget in
    ``process_rcb_to_2020_baseline``:

    - **bunkers**: always positive (cumulative emissions); the caller negates
      it before adding.
    - **lulucf**: sign-ready (added directly to budget):
        - co2: convention gap (NGHGI − BM), negative → reduces budget
        - co2-ffi: negated BM LULUCF, positive → increases fossil budget
          (capped at 0 when ``precautionary_lulucf=True``)

    Parameters
    ----------
    scenario : str
        Fair-shares scenario string (e.g. "1.5p50")
    net_zero_year : int
        Category-level upper integration bound for **bunker** deductions
        (from AR6 constants YAML)
    nghgi_ts : pd.DataFrame
        Pre-loaded NGHGI LULUCF historical timeseries
    bunker_ts : pd.DataFrame
        Pre-loaded bunker fuel timeseries
    gidden_direct_scenarios : pd.DataFrame
        Per-scenario Gidden AFOLU|Direct timeseries for this scenario's
        AR6 category. Multi-row with (model, scenario) index.
    gidden_indirect_scenarios : pd.DataFrame
        Per-scenario Gidden AFOLU|Indirect timeseries for this scenario's
        AR6 category. Multi-row with (model, scenario) index.
    per_scenario_nz_years : pd.Series
        Per-scenario total CO₂ net-zero years for LULUCF integration endpoints,
        indexed by (model, scenario). From ``load_gidden_per_scenario_nz_years``.
    emission_category : str, optional
        Emission category (default: "co2-ffi")
    precautionary_lulucf : bool, optional
        If True (default), BM LULUCF sinks cannot increase the fossil budget
        for co2-ffi. Sources still reduce it. Only affects co2-ffi.
    verbose : bool, optional
        Whether to print progress

    Returns
    -------
    tuple[float, float]
        (bunkers_mt, lulucf_mt) — bunkers positive, lulucf sign-ready
    """
    ar6_category = map_scenario_to_ar6_category(scenario)

    # --- LULUCF deduction (sign-ready: added directly to budget) ---
    # Uses per-scenario net-zero years so each scenario is integrated
    # exactly to its own net-zero year (no post-NZ negative emissions).
    if emission_category == "co2":
        # Total CO2: convention gap (NGHGI − BM).
        lulucf_mt = compute_lulucf_convention_gap(
            nghgi_ts=nghgi_ts,
            gidden_direct_scenarios=gidden_direct_scenarios,
            gidden_indirect_scenarios=gidden_indirect_scenarios,
            start_year=2020,
            per_scenario_nz_years=per_scenario_nz_years,
            splice_year=_GRASSI_SPLICE_YEAR,
        )
    else:
        # CO2-FFI: subtract BM LULUCF (Gidden Direct) to convert total → fossil.
        # Per-scenario cumulative to each scenario's own NZ year, then median.
        common_idx = (
            gidden_direct_scenarios.index
            .intersection(gidden_indirect_scenarios.index)
            .intersection(per_scenario_nz_years.index)
        )

        per_scenario_bm = []
        for scenario_key in common_idx:
            nz = int(per_scenario_nz_years[scenario_key])
            year_cols = [
                str(y) for y in range(2020, nz + 1)
                if str(y) in gidden_direct_scenarios.columns
            ]
            if year_cols:
                per_scenario_bm.append(
                    float(gidden_direct_scenarios.loc[scenario_key, year_cols].sum())
                )

        bm_lulucf_mt = float(pd.Series(per_scenario_bm).median())

        if precautionary_lulucf:
            lulucf_mt = -max(0.0, bm_lulucf_mt)
        else:
            lulucf_mt = -bm_lulucf_mt

    # --- Bunkers deduction (always positive; caller negates) ---
    # Bunkers are observational, not scenario-dependent.
    # Uses category-level net-zero year (unchanged).
    bunkers_mt = compute_bunker_deduction(
        bunker_ts=bunker_ts,
        start_year=2020,
        net_zero_year=net_zero_year,
    )

    if verbose:
        print(
            f"    Scenario {scenario} ({ar6_category}): "
            f"bunkers={bunkers_mt:.0f} Mt, lulucf={lulucf_mt:.0f} Mt"
        )

    return bunkers_mt, lulucf_mt


def load_and_process_rcbs(
    rcb_yaml_path: Path,
    world_emissions_df: pd.DataFrame,
    emission_category: str,
    adjustments_config: AdjustmentsConfig,
    project_root: Path | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """Load and process RCB data from YAML configuration.

    Processes RCBs to 2020 baseline with NGHGI-consistent bunkers and LULUCF
    adjustments, following Weber et al. (2026).

    Aggregation order: cumulative emissions are computed per scenario first,
    then the median is taken across scenarios. Each scenario is integrated
    to its own total CO₂ net-zero year (LULUCF corrections) or to the
    category-level median NZ year (bunker deductions).

    Net-zero years: For LULUCF, each scenario is integrated to its own
    total CO₂ NZ year (from ``load_gidden_per_scenario_nz_years``). For bunkers,
    the category-level median NZ year is used (from the AR6 constants YAML).

    Parameters
    ----------
    rcb_yaml_path : Path
        Path to RCB YAML configuration file
    world_emissions_df : pd.DataFrame
        World emissions timeseries DataFrame
    emission_category : str
        Emission category (must be "co2-ffi" or "co2")
    adjustments_config : AdjustmentsConfig
        Structured adjustment configuration with timeseries source paths.
    project_root : Path or None, optional
        Root directory for resolving relative data paths in adjustments_config.
    verbose : bool, optional
        Print processing details

    Returns
    -------
    pd.DataFrame
        DataFrame with processed RCB data including provenance fields
    """
    # Validate emission category
    if emission_category not in ("co2-ffi", "co2"):
        raise ConfigurationError(
            f"RCB-based budget allocations only support 'co2-ffi' and 'co2' emission "
            f"categories. Got: {emission_category}. Please use target: 'ar6' "
            f"in your configuration for other emission categories."
        )

    # Load RCB YAML
    if not rcb_yaml_path.exists():
        raise DataLoadingError(f"RCB YAML file not found: {rcb_yaml_path}")

    with open(rcb_yaml_path) as file:
        rcb_data = yaml.safe_load(file)

    if verbose:
        print("Loaded RCB data structure:")
        print(f"  Sources: {list(rcb_data['rcb_data'].keys())}")
        if rcb_data["rcb_data"]:
            first_source = next(iter(rcb_data["rcb_data"].keys()))
            first_data = rcb_data["rcb_data"][first_source]
            print(f"  Example source ({first_source}):")
            print(f"    Baseline year: {first_data.get('baseline_year')}")
            print(f"    Unit: {first_data.get('unit')}")
            print(f"    Scenarios: {list(first_data.get('scenarios', {}).keys())}")

    # Ensure world emissions has string year columns
    world_emissions_df = ensure_string_year_columns(world_emissions_df)

    # Pre-load scenario-invariant timeseries (NGHGI LULUCF and bunkers)
    resolved_root = project_root or Path(".")
    nghgi_ts, bunker_ts = _load_shared_timeseries(
        adjustments_config, resolved_root, verbose=verbose
    )

    # Load AR6 category constants for per-category net-zero years
    constants_path = resolved_root / adjustments_config.ar6_constants_path
    ar6_constants = load_ar6_category_constants(constants_path)

    if verbose:
        print("\n  AR6 category constants loaded:")
        for cat, vals in sorted(ar6_constants.items()):
            print(
                f"    {cat}: median NZ={vals['nz_year_median']}, "
                f"range=[{vals.get('nz_year_min', '?')}-{vals.get('nz_year_max', '?')}], "
                f"n={vals['n_scenarios']}"
            )
        print("\nProcessing RCBs with adjustments:")
        print("  Target baseline year: 2020")
        print("  Adjustment mode: timeseries (NGHGI-consistent, Weber et al. 2026)")
        print("  Aggregation: integrate per scenario to its own NZ year, then median")
        print("  LULUCF NZ years: per-scenario (from Gidden Emissions|CO2)")
        print("  Bunker NZ years: category-level median (from AR6 constants YAML)")

    # Cache for Gidden components keyed by AR6 category
    # Now stores per-scenario DataFrames
    gidden_cache: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}

    # Cache for per-scenario total CO₂ net-zero years keyed by AR6 category
    nz_years_cache: dict[str, pd.Series] = {}

    # Cache for Gidden medians (for process_rcb_to_2020_baseline baseline shift)
    gidden_median_cache: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}

    # Create a list to store all RCB records
    rcb_records = []

    # Process each source
    for source_key, source_data in rcb_data["rcb_data"].items():
        if verbose:
            print(f"\n  Processing source: {source_key}")

        # Extract metadata from source
        baseline_year = source_data.get("baseline_year")
        unit = source_data.get("unit", "Gt CO2")
        scenarios = source_data.get("scenarios", {})

        # Validate required fields
        if baseline_year is None:
            raise ConfigurationError(
                f"RCB source '{source_key}' missing required field 'baseline_year'"
            )
        if not scenarios:
            raise ConfigurationError(
                f"RCB source '{source_key}' has no scenarios defined"
            )

        if verbose:
            print(f"    Baseline year: {baseline_year}")
            print(f"    Unit: {unit}")
            print(f"    Scenarios: {len(scenarios)}")

        # Process each scenario for this source
        for scenario, rcb_value in scenarios.items():
            climate_assessment, quantile = parse_rcb_scenario(scenario)

            # Get per-scenario Gidden components for this scenario's AR6 category
            ar6_category = map_scenario_to_ar6_category(scenario)
            gidden_direct_scenarios, gidden_indirect_scenarios = (
                _get_gidden_components(
                    ar6_category, resolved_root, gidden_cache, verbose=verbose
                )
            )

            # Get per-scenario total CO₂ net-zero years for LULUCF integration
            per_scenario_nz_years = _get_gidden_nz_years(
                ar6_category, resolved_root, nz_years_cache, verbose=verbose
            )

            # Get median timeseries for baseline shift (backward compat)
            if ar6_category not in gidden_median_cache:
                gidden_median_cache[ar6_category] = compute_gidden_medians(
                    gidden_direct_scenarios,
                    gidden_indirect_scenarios,
                    ar6_category,
                )
            gidden_direct_median, _ = gidden_median_cache[ar6_category]

            # Look up category-level net-zero year (for bunker integration only)
            nz_year = ar6_constants[ar6_category]["nz_year_median"]

            # Resolve adjustment scalars using per-scenario integration
            bunkers_mt, lulucf_mt = _resolve_adjustment_scalars(
                scenario=scenario,
                net_zero_year=nz_year,
                nghgi_ts=nghgi_ts,
                bunker_ts=bunker_ts,
                gidden_direct_scenarios=gidden_direct_scenarios,
                gidden_indirect_scenarios=gidden_indirect_scenarios,
                per_scenario_nz_years=per_scenario_nz_years,
                emission_category=emission_category,
                precautionary_lulucf=adjustments_config.precautionary_lulucf,
                verbose=verbose,
            )

            # Process RCB to 2020 baseline
            # NOTE: process_rcb_to_2020_baseline receives the median timeseries
            # for the baseline shift (rebasing from original baseline_year to
            # 2020). The shift period is typically short; the per-scenario
            # aggregation order matters primarily for the longer 2020-to-NZ
            # integration window handled by _resolve_adjustment_scalars above.
            result = process_rcb_to_2020_baseline(
                rcb_value=rcb_value,
                rcb_unit=unit,
                rcb_baseline_year=baseline_year,
                world_co2_ffi_emissions=world_emissions_df,
                bunkers_2020_2100=bunkers_mt,
                lulucf_2020_2100=lulucf_mt,
                world_lulucf_shift_emissions=gidden_direct_median,
                target_baseline_year=2020,
                source_name=source_key,
                scenario=scenario,
                verbose=verbose,
            )

            # Create record with parsed climate assessment and quantile
            record = {
                "source": source_key,
                "scenario": scenario,
                "climate-assessment": climate_assessment,
                "quantile": quantile,
                "emission-category": emission_category,
                "baseline_year": baseline_year,
                "rcb_original_value": result["rcb_original_value"],
                "rcb_original_unit": result["rcb_original_unit"],
                "rcb_2020_mt": result["rcb_2020_mt"],
                "rebase_total_mt": result["rebase_total_mt"],
                "rebase_fossil_mt": result["rebase_fossil_mt"],
                "rebase_lulucf_mt": result["rebase_lulucf_mt"],
                "net_deduction_mt": result["net_deduction_mt"],
                "deduction_bunkers_mt": result["deduction_bunkers_mt"],
                "deduction_lulucf_mt": result["deduction_lulucf_mt"],
                "lulucf_convention": result["lulucf_convention"],
            }

            rcb_records.append(record)

    # Convert to DataFrame
    rcb_df = pd.DataFrame(rcb_records)

    if verbose:
        print("\nProcessed RCB data:")
        print(rcb_df.to_string(index=False))

    return rcb_df
