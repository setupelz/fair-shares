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
    compute_lulucf_convention_gap,
    load_ar6_category_constants,
    load_bunker_timeseries,
    load_gidden_lulucf_components,
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
    """Load Gidden LULUCF components, cached by AR6 category.

    Multiple scenarios map to the same AR6 category (e.g. "1.5p50" and
    "1.5p66" both map to C1), so caching avoids redundant Excel reads.
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


def _resolve_adjustment_scalars(
    scenario: str,
    net_zero_year: int,
    nghgi_ts: pd.DataFrame,
    bunker_ts: pd.DataFrame,
    gidden_direct_ts: pd.DataFrame,
    gidden_indirect_ts: pd.DataFrame,
    emission_category: str = "co2-ffi",
    precautionary_lulucf: bool = True,
    verbose: bool = True,
) -> tuple[float, float]:
    """Compute sign-ready adjustment scalars for a given scenario.

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
        Upper integration bound for deductions (from AR6 constants)
    nghgi_ts : pd.DataFrame
        Pre-loaded NGHGI LULUCF historical timeseries
    bunker_ts : pd.DataFrame
        Pre-loaded bunker fuel timeseries
    gidden_direct_ts : pd.DataFrame
        Pre-loaded Gidden AFOLU|Direct timeseries for this scenario's AR6 category
    gidden_indirect_ts : pd.DataFrame
        Pre-loaded Gidden AFOLU|Indirect timeseries for this scenario's AR6 category
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
    from fair_shares.library.utils.data.nghgi import compute_cumulative_emissions

    ar6_category = map_scenario_to_ar6_category(scenario)

    # --- LULUCF deduction (sign-ready: added directly to budget) ---
    if emission_category == "co2":
        # Total CO2: convention gap (NGHGI − BM).
        # Negative when NGHGI shows more sink → reduces budget (Weber 2026).
        lulucf_mt = compute_lulucf_convention_gap(
            nghgi_ts=nghgi_ts,
            gidden_direct_ts=gidden_direct_ts,
            gidden_indirect_ts=gidden_indirect_ts,
            start_year=2020,
            net_zero_year=net_zero_year,
            splice_year=_GRASSI_SPLICE_YEAR,
        )
    else:
        # CO2-FFI: subtract BM LULUCF (Gidden Direct) to convert total → fossil.
        bm_lulucf_mt = compute_cumulative_emissions(
            gidden_direct_ts, 2020, net_zero_year
        )
        if precautionary_lulucf:
            # Precautionary: sinks (negative cumulative) don't increase fossil
            # budget, but sources (positive cumulative) still reduce it.
            # max(0, bm) keeps sources, zeros out sinks.
            lulucf_mt = -max(0.0, bm_lulucf_mt)
        else:
            # Original: negating gives positive → increases fossil budget
            # (more room for fossil when forests absorb CO2).
            lulucf_mt = -bm_lulucf_mt

    # --- Bunkers deduction (always positive; caller negates) ---
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

    Net-zero years are loaded from the AR6 category constants file (generated
    by the RCB preprocessing notebook). Each AR6 category gets its own net-zero year as the upper
    integration bound for LULUCF and bunker deductions.

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
                f"    {cat}: NZ(NGHGI)={vals['net_zero_year_nghgi']}, "
                f"NZ(scientific)={vals['net_zero_year_scientific']}"
            )
        print("\nProcessing RCBs with adjustments:")
        print("  Target baseline year: 2020")
        print("  Adjustment mode: timeseries (NGHGI-consistent, Weber et al. 2026)")
        print("  Net-zero years: per-category from AR6 constants")

    # Cache for Gidden components keyed by AR6 category
    gidden_cache: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}

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

            # Get Gidden components for this scenario's AR6 category (cached)
            ar6_category = map_scenario_to_ar6_category(scenario)
            gidden_direct_ts, gidden_indirect_ts = _get_gidden_components(
                ar6_category, resolved_root, gidden_cache, verbose=verbose
            )

            # Look up per-category net-zero year from AR6 constants
            nz_year = ar6_constants[ar6_category]["net_zero_year_nghgi"]

            # Resolve adjustment scalars for this scenario
            bunkers_mt, lulucf_mt = _resolve_adjustment_scalars(
                scenario=scenario,
                net_zero_year=nz_year,
                nghgi_ts=nghgi_ts,
                bunker_ts=bunker_ts,
                gidden_direct_ts=gidden_direct_ts,
                gidden_indirect_ts=gidden_indirect_ts,
                emission_category=emission_category,
                precautionary_lulucf=adjustments_config.precautionary_lulucf,
                verbose=verbose,
            )

            # Process RCB to 2020 baseline
            result = process_rcb_to_2020_baseline(
                rcb_value=rcb_value,
                rcb_unit=unit,
                rcb_baseline_year=baseline_year,
                world_co2_ffi_emissions=world_emissions_df,
                bunkers_2020_2100=bunkers_mt,
                lulucf_2020_2100=lulucf_mt,
                world_lulucf_shift_emissions=gidden_direct_ts,
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
