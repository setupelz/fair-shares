"""Remaining Carbon Budget (RCB) processing logic.

Processes IPCC RCBs to 2020 baseline with NGHGI-consistent adjustments,
following the methodology of Weber et al. (2026).

Supports both co2-ffi and co2 emission categories:
- **co2-ffi**: uses the pre-computed median-of-per-scenario-cumulatives
  (``bm_lulucf_cumulative_median``) from notebook 104, based on scenario data
  (e.g. AR6) in the corresponding climate category. Scenario data is
  required because the LULUCF decomposition extends to net-zero (no
  observational data exists for the future). Adjusted for baseline year
  by subtracting the 2020-to-base prefix.
- **co2**: the rebase adds observed NGHGI LULUCF for 2020 to the year before
  the baseline, and the pre-computed convention gap (BM -> NGHGI) from
  notebook 104 runs from the baseline year to net zero.

NZ years and convention gap scalars are pre-computed by notebook 104 from
the scenario data (currently Gidden et al. AR6 reanalysis) and saved as
``rcb_scenario_adjustments.yaml``. Per-year BM LULUCF medians are stored
as ``lulucf_shift_median_{key}.csv``. Both are keyed by scenario set
(see ``rcb_scenario_set_key``): the budget label for sources under the
AR6 category rule, the temperature band for sources under the peak-warming
band rule.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
import yaml

from fair_shares.library.config.models import AdjustmentsConfig
from fair_shares.library.exceptions import (
    ConfigurationError,
    DataLoadingError,
)
from fair_shares.library.paths import resolve_source_path
from fair_shares.library.utils import (
    ensure_string_year_columns,
    parse_rcb_scenario,
    process_rcb_to_2020_baseline,
)
from fair_shares.library.utils.data.nghgi import (
    compute_bunker_deduction,
    load_bunker_timeseries,
)
from fair_shares.library.utils.data.rcb import (
    DEFAULT_REBASE_FILL_MAX_YEARS,
    DEFAULT_SCENARIO_SELECTION,
    fill_rebase_years,
    missing_rebase_years,
    rcb_scenario_set_key,
    validate_rebase_fill_max_years,
)


def _resolve_template_path(
    path_str: str,
    source_id: str | None,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> Path:
    """Resolve a config path that may contain a {source_id} template.

    The leading ``data/`` or ``output/`` segment selects which configured
    directory the remainder resolves against.
    """
    if source_id and "{source_id}" in path_str:
        path_str = path_str.replace("{source_id}", source_id)
    return resolve_source_path(path_str, data_dir=data_dir, output_dir=output_dir)


def _load_rcb_scenario_adjustments(
    intermediate_dir: Path,
    verbose: bool = True,
) -> dict[str, dict]:
    """Load pre-computed RCB adjustment scalars from notebook 104 output.

    Parameters
    ----------
    intermediate_dir : Path
        Path to the scenarios intermediate directory
        (e.g., ``output/{source_id}/intermediate/scenarios/``)
    verbose : bool
        Print progress.

    Returns
    -------
    dict[str, dict]
        Mapping of scenario set key (e.g., "1.5p50") to adjustment dict with keys:
        ``bm_lulucf_cumulative_median``, ``convention_gap_median_from``
        (one median gap per RCB baseline year), ``nz_year_median``,
        ``n_scenarios``

    Raises
    ------
    DataLoadingError
        If the adjustments file does not exist
    """
    adj_path = intermediate_dir / "rcb_scenario_adjustments.yaml"
    if not adj_path.exists():
        raise DataLoadingError(
            f"RCB scenario adjustments not found: {adj_path}. "
            "Run notebook 104 (AR6 scenario preprocessing) first."
        )

    with open(adj_path) as f:
        adjustments = yaml.safe_load(f)

    if verbose:
        print("  Pre-computed RCB scenario adjustments loaded:")
        for cat, vals in sorted(adjustments.items()):
            print(
                f"    {cat}: NZ_med={vals['nz_year_median']}, "
                f"BM_LULUCF={vals['bm_lulucf_cumulative_median']:.0f} Mt, "
                f"gap from baseline year (Mt)="
                f"{vals.get('convention_gap_median_from')}, "
                f"n={vals['n_scenarios']}"
            )

    return adjustments


def _resolve_adjustment_scalars(
    scenario: str,
    baseline_year: int,
    net_zero_year: int,
    bunker_ts: pd.DataFrame,
    lulucf_shift_ts: pd.DataFrame,
    rcb_adjustments: dict[str, dict],
    emission_category: str = "co2-ffi",
    precautionary_lulucf: bool = True,
    verbose: bool = True,
) -> tuple[float, float]:
    """Compute sign-ready adjustment scalars for a given scenario.

    For co2-ffi: uses the pre-computed ``bm_lulucf_cumulative_median``
    (median of per-scenario cumulatives from 2020 to each scenario's NZ).
    When ``baseline_year`` > 2020, the 2020-to-base prefix is subtracted
    from the median timeseries.
    For co2: uses the pre-computed convention gap from ``baseline_year`` to
    NZ (``convention_gap_median_from[baseline_year]``) from notebook 104.

    Returns values that can be added directly to the budget:
    - **bunkers**: always positive (cumulative emissions); caller negates
    - **lulucf**: sign-ready (added directly to budget)

    Parameters
    ----------
    scenario : str
        Scenario set key (e.g. "1.5p50" or "peak-warming-1.7C")
    baseline_year : int
        RCB source baseline year — the LULUCF decomposition (co2-ffi) and
        the convention gap (co2) start here
    net_zero_year : int
        Category-level NZ year for bunker and LULUCF integration
    bunker_ts : pd.DataFrame
        Pre-loaded bunker fuel timeseries
    lulucf_shift_ts : pd.DataFrame
        Per-year BM LULUCF median timeseries (from notebook 104),
        used for co2-ffi to integrate from baseline_year to NZ
    rcb_adjustments : dict[str, dict]
        Pre-computed RCB adjustment scalars from notebook 104,
        keyed by scenario set (e.g., "1.5p50")
    emission_category : str
        Emission category (default: "co2-ffi")
    precautionary_lulucf : bool
        If True, BM LULUCF sinks cannot increase the fossil budget
    verbose : bool
        Whether to print progress

    Returns
    -------
    tuple[float, float, float]
        (bunkers_mt, lulucf_future_mt, lulucf_nghgi_correction_mt).
        Bunkers is positive; the two LULUCF scalars are sign-ready.
        Exactly one of the LULUCF scalars is non-zero per category
        (future_mt for co2-ffi, nghgi_correction_mt for co2).

    Raises
    ------
    DataLoadingError
        If ``rcb_adjustments`` has no entry for ``scenario``, or, for co2,
        no convention gap from ``baseline_year``
    """
    if scenario not in rcb_adjustments:
        raise DataLoadingError(
            f"No RCB scenario adjustments for '{scenario}' "
            f"(available: {list(rcb_adjustments)}). "
            "Re-run notebook 104 (AR6 scenario preprocessing)."
        )
    adj = rcb_adjustments[scenario]

    lulucf_future_mt = 0.0
    lulucf_nghgi_correction_mt = 0.0

    if emission_category == "co2":
        # NGHGI-minus-BM convention gap from the baseline year to NZ (Weber
        # 2026). The rebase adds observed NGHGI LULUCF for the years before it.
        gaps_from = adj.get("convention_gap_median_from") or {}
        if baseline_year not in gaps_from:
            raise DataLoadingError(
                f"No convention gap from baseline year {baseline_year} for "
                f"'{scenario}' (available baseline years: {sorted(gaps_from)}). "
                "Re-run notebook 104 (AR6 scenario preprocessing)."
            )
        lulucf_nghgi_correction_mt = gaps_from[baseline_year]
        if lulucf_nghgi_correction_mt == 0.0:
            warnings.warn(
                f"The convention gap is 0.0 for scenario '{scenario}' — "
                f"this likely means notebook 104 ran before NGHGI data was "
                f"preprocessed. Re-run the preprocessing pipeline: "
                f"notebooks 105/107 first, then 104.",
                stacklevel=2,
            )
    else:
        # co2-ffi: subtract projected future (base→NZ) BM LULUCF to convert
        # a published total-CO2 RCB into an FFI-only RCB.
        bm_lulucf_mt = adj["bm_lulucf_cumulative_median"]

        # Adjust for baseline year > 2020: subtract the 2020-to-base
        # prefix using the median timeseries.  Historical BM LULUCF has
        # negligible inter-scenario spread, so median(cmltv_i - prefix_i)
        # ≈ median(cmltv_i) - median_prefix.
        if baseline_year > 2020:
            prefix_cols = [
                str(y)
                for y in range(2020, baseline_year)
                if str(y) in lulucf_shift_ts.columns
            ]
            if prefix_cols:
                bm_lulucf_mt -= float(
                    lulucf_shift_ts[prefix_cols].sum(axis=1).iloc[0]
                )

        if precautionary_lulucf:
            lulucf_future_mt = -max(0.0, bm_lulucf_mt)
        else:
            lulucf_future_mt = -bm_lulucf_mt

    # --- Bunkers deduction from 2020 to NZ (always positive; caller negates).
    # The rebase adds the bunkers of 2020 to baseline_year - 1. ---
    bunkers_mt = compute_bunker_deduction(
        bunker_ts=bunker_ts,
        start_year=2020,
        net_zero_year=net_zero_year,
    )

    if verbose:
        print(
            f"    Scenario {scenario}: "
            f"bunkers={bunkers_mt:.0f} Mt, "
            f"lulucf_future={lulucf_future_mt:.0f} Mt, "
            f"lulucf_nghgi_correction={lulucf_nghgi_correction_mt:.0f} Mt"
        )

    return bunkers_mt, lulucf_future_mt, lulucf_nghgi_correction_mt


def load_and_process_rcbs(
    rcb_yaml_path: Path,
    world_fossil_emissions: pd.DataFrame,
    emission_category: str,
    adjustments_config: AdjustmentsConfig,
    data_dir: Path | str | None = None,
    source_id: str | None = None,
    world_nghgi_lulucf_emissions: pd.DataFrame | None = None,
    verbose: bool = True,
    output_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Load and process RCB data from YAML configuration.

    Processes RCBs to 2020 baseline with NGHGI-consistent bunkers and LULUCF
    adjustments, following Weber et al. (2026).

    Parameters
    ----------
    rcb_yaml_path : Path
        Path to RCB YAML configuration file
    world_fossil_emissions : pd.DataFrame
        World fossil CO2 emissions timeseries (e.g. PRIMAP) — always fossil,
        regardless of emission_category
    emission_category : str
        Emission category (must be "co2-ffi" or "co2")
    adjustments_config : AdjustmentsConfig
        Structured adjustment configuration with timeseries source paths.
    data_dir : Path or None, optional
        Directory holding input data. Defaults to the resolved data directory.
    source_id : str or None, optional
        Source ID for resolving intermediate paths with {source_id} template.
    world_nghgi_lulucf_emissions : pd.DataFrame or None, optional
        Observed world LULUCF CO2 emissions in the national-inventory (NGHGI)
        convention, for the co2 rebase. Required when emission_category is
        "co2".
    verbose : bool, optional
        Print processing details
    output_dir : Path or None, optional
        Directory holding pipeline products. Defaults to the resolved output
        directory.

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
    world_fossil_emissions = ensure_string_year_columns(world_fossil_emissions)

    # Pre-load the scenario-invariant bunker timeseries
    bunker_path = _resolve_template_path(
        adjustments_config.bunkers.path, source_id, data_dir, output_dir
    )
    if verbose:
        print(f"    Loading bunker timeseries from: {bunker_path}")
    bunker_ts = load_bunker_timeseries(bunker_path)

    # Load pre-computed RCB adjustment scalars from notebook 104
    if not source_id:
        raise ConfigurationError(
            "source_id is required for RCB processing — the pre-computed "
            "adjustment scalars are stored per source_id in "
            "output/{source_id}/intermediate/scenarios/rcb_scenario_adjustments.yaml"
        )
    scenarios_dir = _resolve_template_path(
        "output/{source_id}/intermediate/scenarios",
        source_id,
        data_dir,
        output_dir,
    )
    adj_path = scenarios_dir / "rcb_scenario_adjustments.yaml"
    if not adj_path.exists():
        raise DataLoadingError(
            f"RCB scenario adjustments not found at {adj_path}. "
            f"Run notebook 104 (data_preprocess_scenarios_ar6) first to generate them."
        )
    rcb_adjustments = _load_rcb_scenario_adjustments(scenarios_dir, verbose=verbose)

    if verbose:
        print("\nProcessing RCBs with adjustments:")
        print("  Target baseline year: 2020")
        print("  Adjustment mode: pre-computed (NGHGI-consistent, Weber et al. 2026)")
        print("  Bunker NZ years: category-level median (from scenario adjustments)")

    rebase_fill_max_years = validate_rebase_fill_max_years(
        rcb_data.get("rebase_fill_max_years", DEFAULT_REBASE_FILL_MAX_YEARS)
    )

    # Pre-load baseline-shift LULUCF median timeseries from notebook 104 output.
    # These are year-by-year median AFOLU|Direct CSVs, one per scenario set.
    lulucf_shift_cache: dict[str, pd.DataFrame] = {}

    # Create a list to store all RCB records
    rcb_records = []
    skipped_sources = []

    # Process each source
    for source_key, source_data in rcb_data["rcb_data"].items():
        if verbose:
            print(f"\n  Processing source: {source_key}")

        baseline_year = source_data.get("baseline_year")
        unit = source_data.get("unit", "Gt CO2")
        scenarios = source_data.get("scenarios", {})
        selection = source_data.get("scenario_selection", DEFAULT_SCENARIO_SELECTION)

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
            print(f"    Scenario selection: {selection}")

        # A series that ends up to rebase_fill_max_years before the last rebase
        # year takes its last observed value for the remaining years.
        rebase_fossil = fill_rebase_years(
            world_fossil_emissions,
            baseline_year,
            rebase_fill_max_years,
            "world fossil CO2 emissions",
            source_key,
        )
        rebase_bunkers = fill_rebase_years(
            bunker_ts,
            baseline_year,
            rebase_fill_max_years,
            "international bunker emissions",
            source_key,
        )
        rebase_lulucf = world_nghgi_lulucf_emissions
        if emission_category == "co2" and world_nghgi_lulucf_emissions is not None:
            rebase_lulucf = fill_rebase_years(
                world_nghgi_lulucf_emissions,
                baseline_year,
                rebase_fill_max_years,
                "world NGHGI LULUCF CO2 emissions",
                source_key,
            )

        # The rebase to 2020 needs emissions for every year before the baseline.
        # A source that the emissions data cannot rebase is left out.
        missing_years = missing_rebase_years(baseline_year, rebase_fossil)
        missing_years += missing_rebase_years(baseline_year, rebase_bunkers)
        if emission_category == "co2" and rebase_lulucf is not None:
            missing_years += missing_rebase_years(baseline_year, rebase_lulucf)
        if missing_years:
            skipped_sources.append(
                f"'{source_key}' (baseline {baseline_year}, data lack "
                f"{sorted(set(missing_years))})"
            )
            continue

        for scenario, rcb_value in scenarios.items():
            climate_assessment, quantile = parse_rcb_scenario(scenario)
            set_key = rcb_scenario_set_key(source_key, scenario, selection)
            if set_key not in rcb_adjustments:
                raise DataLoadingError(
                    f"RCB source '{source_key}', label '{scenario}': no scenario "
                    f"adjustments for '{set_key}' in {adj_path}. "
                    "Re-run notebook 104 (AR6 scenario preprocessing)."
                )

            # Load pre-computed median LULUCF shift timeseries for baseline shift
            if set_key not in lulucf_shift_cache:
                shift_csv = scenarios_dir / f"lulucf_shift_median_{set_key}.csv"
                if not shift_csv.exists():
                    raise DataLoadingError(
                        f"LULUCF shift median not found: {shift_csv}. "
                        "Run notebook 104 (AR6 scenario preprocessing) first."
                    )
                shift_df = pd.read_csv(shift_csv).set_index("source")
                lulucf_shift_cache[set_key] = shift_df
                if verbose:
                    print(
                        f"    Loaded LULUCF shift median for {set_key} "
                        f"from {shift_csv}"
                    )
            direct_median = lulucf_shift_cache[set_key]

            # Scenario-level NZ year (for bunker integration)
            nz_year = rcb_adjustments[set_key]["nz_year_median"]

            # Resolve adjustment scalars from pre-computed values
            bunkers_mt, lulucf_future_mt, lulucf_nghgi_mt = (
                _resolve_adjustment_scalars(
                    scenario=set_key,
                    baseline_year=baseline_year,
                    net_zero_year=nz_year,
                    bunker_ts=bunker_ts,
                    lulucf_shift_ts=direct_median,
                    rcb_adjustments=rcb_adjustments,
                    emission_category=emission_category,
                    precautionary_lulucf=adjustments_config.precautionary_lulucf,
                    verbose=verbose,
                )
            )

            # Process RCB to 2020 baseline
            result = process_rcb_to_2020_baseline(
                rcb_value=rcb_value,
                rcb_unit=unit,
                rcb_baseline_year=baseline_year,
                world_co2_ffi_emissions=rebase_fossil,
                emission_category=emission_category,
                world_bunker_emissions=rebase_bunkers,
                bunkers_deduction_mt=bunkers_mt,
                lulucf_future_deduction_mt=lulucf_future_mt,
                lulucf_nghgi_correction_mt=lulucf_nghgi_mt,
                world_nghgi_lulucf_emissions=rebase_lulucf,
                target_baseline_year=2020,
                source_name=source_key,
                scenario=scenario,
                verbose=verbose,
            )

            record = {
                "source": source_key,
                "scenario": scenario,
                "climate-assessment": climate_assessment,
                "quantile": quantile,
                "emission-category": emission_category,
                "baseline_year": baseline_year,
                "rcb_original_value": result["rcb_original_value"],
                "rcb_original_unit": result["rcb_original_unit"],
                "rcb_2020_nghgi_mt": result["rcb_2020_nghgi_mt"],
                "net_adjustment_mt": result["net_adjustment_mt"],
                "rebase_total_mt": result["rebase_total_mt"],
                "rebase_fossil_mt": result["rebase_fossil_mt"],
                "rebase_bunkers_mt": result["rebase_bunkers_mt"],
                "rebase_lulucf_mt": result["rebase_lulucf_mt"],
                "deduction_bunkers_mt": result["deduction_bunkers_mt"],
                "deduction_lulucf_future_mt": result["deduction_lulucf_future_mt"],
                "correction_lulucf_nghgi_mt": result["correction_lulucf_nghgi_mt"],
            }

            rcb_records.append(record)

    rcb_df = pd.DataFrame(rcb_records)

    # This step processes every source in rcbs.yaml and does not know which
    # one an allocation requests, so it reports the skipped sources once.
    if skipped_sources:
        warnings.warn(
            f"RCB sources left out, no rebase to 2020 with at most "
            f"{rebase_fill_max_years} filled year(s) (rebase_fill_max_years): "
            f"{'; '.join(skipped_sources)}.",
            stacklevel=2,
        )

    if verbose:
        print("\nProcessed RCB data:")
        print(rcb_df.to_string(index=False))

    return rcb_df
