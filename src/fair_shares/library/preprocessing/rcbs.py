"""Remaining Carbon Budget (RCB) processing logic.

Processes IPCC RCBs to 2020 baseline with NGHGI-consistent adjustments,
following the methodology of Weber et al. (2026).

Supports both co2-ffi and co2 emission categories:
- **co2-ffi**: deducts the bookkeeping (BM) land-use CO2 from the baseline
  year to net zero, the median over the scenarios of the budget's
  volume-matched set (``bm_lulucf_median_from``, one value per baseline year).
- **co2**: the rebase adds observed NGHGI LULUCF for 2020 to the year before
  the baseline, and the convention gap (BM -> NGHGI) from notebook 104 runs
  from the baseline year to net zero (``convention_gap_median_from``).

Notebook 104 writes, per budget (key ``source:label``):
``rcb_scenario_adjustments.yaml`` (the scalars and the provenance of the
scenario sets), ``scenario_set_{source}_{label}.csv`` (the members of the
volume-matched set or AR6 category with their net-zero crossings and net CO2
from each possible start year), and once ``bunker_share_reporters.csv`` (the
bunker reporters behind the bunker share). See
``fair_shares.library.utils.data.scenario_sets``.
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
from fair_shares.library.preprocessing.paths import LULUCF_CATEGORIES
from fair_shares.library.utils import (
    ensure_string_year_columns,
    parse_rcb_scenario,
    process_rcb_to_2020_baseline,
)
from fair_shares.library.utils.data.nghgi import (
    bunker_deduction_from_share,
    load_bunker_timeseries,
)
from fair_shares.library.utils.data.rcb import (
    DEFAULT_REBASE_FILL_MAX_YEARS,
    canonical_scenarios,
    fill_rebase_years,
    missing_rebase_years,
    validate_rebase_fill_max_years,
)
from fair_shares.library.utils.data.scenario_sets import (
    bunker_share,
    scenario_set_settings,
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
        Mapping of budget key (e.g., "forster_2026:1.5p50") to adjustment dict
        with keys ``bm_lulucf_median_from`` and ``convention_gap_median_from``
        (one median per RCB baseline year), the set provenance and the bunker
        pool

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
        for key, vals in sorted(adjustments.items()):
            terms = vals.get("terms_set") or {}
            print(
                f"    {key}: n={terms.get('n')}, "
                f"NZ_med={terms.get('net_zero_year_median')}, "
                f"BM LULUCF from baseline (Mt)={vals.get('bm_lulucf_median_from')}, "
                f"gap from baseline (Mt)={vals.get('convention_gap_median_from')}"
            )

    return adjustments


def _set_co2_after(scenarios_dir: Path, file_key: str, first_year: int) -> float:
    """Median net CO2 of a budget's set from ``first_year`` to net zero (Mt).

    Raises
    ------
    DataLoadingError
        If notebook 104 has not written the set file or the column
    """
    members_csv = scenarios_dir / f"scenario_set_{file_key}.csv"
    column = f"co2_from_{first_year}"
    if not members_csv.exists():
        raise DataLoadingError(
            f"Scenario set file not found: {members_csv}. "
            "Re-run notebook 104 (AR6 scenario preprocessing)."
        )
    members = pd.read_csv(members_csv)
    if column not in members:
        raise DataLoadingError(
            f"{members_csv} lacks '{column}' (the year after the last observed "
            "bunker year). Re-run notebook 104 (AR6 scenario preprocessing)."
        )
    return float(members[column].median())


def _provenance_columns(adjustment: dict, emission_category: str) -> dict:
    """Columns that record how the scenario sets of a budget were chosen.

    ``lulucf_basis`` is empty for a category without land-use CO₂: its budget
    takes BM LULUCF from the scenarios on either basis, so no basis applies,
    and runs on either basis share its output folder.
    """
    terms = adjustment.get("terms_set") or {}
    non_co2 = adjustment.get("non_co2_set") or {}
    return {
        "published_label": adjustment.get("published_label"),
        "likelihood_scope": adjustment.get("likelihood_scope"),
        "budget_metric": adjustment.get("budget_metric"),
        "scenario_selection": adjustment.get("scenario_selection"),
        "budget_2020_gt": adjustment.get("budget_2020_gt"),
        "lulucf_basis": (
            adjustment.get("lulucf_basis")
            if emission_category in LULUCF_CATEGORIES
            else None
        ),
        "terms_set_rule": terms.get("rule"),
        "terms_set_n": terms.get("n"),
        "nz_year_median": terms.get("net_zero_year_median"),
        "non_co2_set_rule": non_co2.get("rule"),
        "non_co2_set_n": non_co2.get("n"),
    }


def _resolve_adjustment_scalars(
    budget_key: str,
    baseline_year: int,
    rcb_adjustments: dict[str, dict],
    emission_category: str = "co2-ffi",
    precautionary_lulucf: bool = True,
    verbose: bool = True,
) -> tuple[float, float]:
    """Return the sign-ready LULUCF scalars of one budget.

    For co2-ffi: the median BM LULUCF from ``baseline_year`` to net zero over
    the budget's set (``bm_lulucf_median_from[baseline_year]``), with the
    precautionary cap. For co2: the convention gap from ``baseline_year`` to
    net zero (``convention_gap_median_from[baseline_year]``).

    Returns
    -------
    tuple[float, float]
        (lulucf_future_mt, lulucf_convention_correction_mt). Exactly one is
        non-zero per category (future_mt for co2-ffi, nghgi_correction_mt for co2).

    Raises
    ------
    DataLoadingError
        If ``rcb_adjustments`` has no entry for the budget, or no LULUCF term
        from ``baseline_year``
    """
    if budget_key not in rcb_adjustments:
        raise DataLoadingError(
            f"No RCB scenario adjustments for '{budget_key}' "
            f"(available: {list(rcb_adjustments)}). "
            "Re-run notebook 104 (AR6 scenario preprocessing)."
        )
    adj = rcb_adjustments[budget_key]
    field = (
        "convention_gap_median_from"
        if emission_category == "co2"
        else "bm_lulucf_median_from"
    )
    values_from = adj.get(field) or {}
    if baseline_year not in values_from:
        what = "convention gap" if emission_category == "co2" else "BM LULUCF term"
        raise DataLoadingError(
            f"No {what} from baseline year {baseline_year} for '{budget_key}' "
            f"(available baseline years: {sorted(values_from)}). "
            "Re-run notebook 104 (AR6 scenario preprocessing)."
        )

    lulucf_future_mt = 0.0
    lulucf_convention_correction_mt = 0.0
    if emission_category == "co2":
        # NGHGI-minus-BM convention gap from the baseline year to NZ (Weber
        # 2026); zero on the bookkeeping basis. The rebase adds the active
        # source's observed world LULUCF for the years before the baseline.
        lulucf_convention_correction_mt = values_from[baseline_year]
        bookkeeping = adj.get("lulucf_basis") == "bookkeeping"
        if lulucf_convention_correction_mt == 0.0 and not bookkeeping:
            warnings.warn(
                f"The convention gap is 0.0 for '{budget_key}': notebook 104 "
                f"likely ran before the NGHGI data were preprocessed. Re-run "
                f"notebooks 105/107 first, then 104.",
                stacklevel=2,
            )
    else:
        # co2-ffi: subtract BM LULUCF from the baseline year to NZ.
        bm_lulucf_mt = values_from[baseline_year]
        lulucf_future_mt = (
            -max(0.0, bm_lulucf_mt) if precautionary_lulucf else -bm_lulucf_mt
        )

    if verbose:
        print(
            f"    Budget {budget_key}: lulucf_future={lulucf_future_mt:.0f} Mt, "
            f"lulucf_convention_correction={lulucf_convention_correction_mt:.0f} Mt"
        )
    return lulucf_future_mt, lulucf_convention_correction_mt


def load_and_process_rcbs(
    rcb_yaml_path: Path,
    world_fossil_emissions: pd.DataFrame,
    emission_category: str,
    adjustments_config: AdjustmentsConfig,
    data_dir: Path | str | None = None,
    source_id: str | None = None,
    world_lulucf_emissions: pd.DataFrame | None = None,
    verbose: bool = True,
    output_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Load and process RCB data from YAML configuration.

    Processes RCBs to 2020 baseline with NGHGI-consistent bunkers and LULUCF
    adjustments, following Weber et al. (2026).

    The bunker deduction is observed bunkers from 2020 to the last observed
    year, plus the bunker share of the reporters times the median net CO2 of
    the budget's scenario set from the next year to net zero
    (``bunker_deduction_from_share``). The LULUCF terms are the medians over
    the same set, read from ``rcb_scenario_adjustments.yaml``.

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
    world_lulucf_emissions : pd.DataFrame or None, optional
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
        One row per budget with the processed RCB, each deduction, the
        scenario-set provenance and the bunker share

    Raises
    ------
    ConfigurationError
        If the category is not co2-ffi or co2, or ``source_id`` is missing
    DataLoadingError
        If the YAML or a notebook 104 output (adjustments, scenario sets,
        bunker reporters) is missing
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
        print(
            "  Bunkers: observed, then the reporters' bunker share of the set's "
            "net CO2 to net zero"
        )

    # Bunkers after the last observed year: a share of the set's net CO2.
    share_csv = scenarios_dir / "bunker_share_reporters.csv"
    if not share_csv.exists():
        raise DataLoadingError(
            f"Bunker share reporters not found: {share_csv}. "
            "Re-run notebook 104 (AR6 scenario preprocessing)."
        )
    observed_bunkers = bunker_ts.iloc[0].dropna()
    share_first_year = max(int(c) for c in observed_bunkers.index) + 1
    share_settings = scenario_set_settings(rcb_data)["bunkers"]
    share = bunker_share(
        pd.read_csv(share_csv),
        share_first_year,
        share_settings["min_reporters"],
        share_settings["min_families"],
        share_settings["min_runs_per_family"],
    )
    if verbose:
        print(
            f"  Bunker share from {share_first_year}: {share['share']:.4f} "
            f"(family-balanced; pooled {share['pooled']:.4f}) "
            f"(IQR {share['q25']:.4f}-{share['q75']:.4f}, n={share['n']} "
            f"{share['n_by_source']})"
        )

    rebase_fill_max_years = validate_rebase_fill_max_years(
        rcb_data.get("rebase_fill_max_years", DEFAULT_REBASE_FILL_MAX_YEARS)
    )

    # Create a list to store all RCB records
    rcb_records = []
    skipped_sources = []

    # Process each source
    for source_key, source_data in rcb_data["rcb_data"].items():
        if verbose:
            print(f"\n  Processing source: {source_key}")

        baseline_year = source_data.get("baseline_year")
        unit = source_data.get("unit", "Gt CO2")
        scenarios = canonical_scenarios(source_key, source_data.get("scenarios", {}))
        selection = source_data.get("scenario_selection")

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
            print(f"    Scenario selection: {selection or 'default'}")

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
        rebase_lulucf = world_lulucf_emissions
        if emission_category == "co2" and world_lulucf_emissions is not None:
            rebase_lulucf = fill_rebase_years(
                world_lulucf_emissions,
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
            budget_key = f"{source_key}:{scenario}"
            if budget_key not in rcb_adjustments:
                raise DataLoadingError(
                    f"RCB source '{source_key}', label '{scenario}': no scenario "
                    f"adjustments for '{budget_key}' in {adj_path}. "
                    "Re-run notebook 104 (AR6 scenario preprocessing)."
                )
            set_co2_after_mt = _set_co2_after(
                scenarios_dir, f"{source_key}_{scenario}", share_first_year
            )
            bunkers_mt, _ = bunker_deduction_from_share(
                bunker_ts, share["share"], set_co2_after_mt
            )
            lulucf_future_mt, lulucf_convention_mt = _resolve_adjustment_scalars(
                budget_key=budget_key,
                baseline_year=baseline_year,
                rcb_adjustments=rcb_adjustments,
                emission_category=emission_category,
                precautionary_lulucf=adjustments_config.precautionary_lulucf,
                verbose=verbose,
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
                lulucf_convention_correction_mt=lulucf_convention_mt,
                world_lulucf_emissions=rebase_lulucf,
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
                "rcb_2020_mt": result["rcb_2020_mt"],
                "net_adjustment_mt": result["net_adjustment_mt"],
                "rebase_total_mt": result["rebase_total_mt"],
                "rebase_fossil_mt": result["rebase_fossil_mt"],
                "rebase_bunkers_mt": result["rebase_bunkers_mt"],
                "rebase_lulucf_mt": result["rebase_lulucf_mt"],
                "deduction_bunkers_mt": result["deduction_bunkers_mt"],
                "deduction_lulucf_future_mt": result["deduction_lulucf_future_mt"],
                "correction_lulucf_convention_mt": result[
                    "correction_lulucf_convention_mt"
                ],
                **_provenance_columns(rcb_adjustments[budget_key], emission_category),
                "bunker_share": round(share["share"], 5),
                "bunker_share_q25": round(share["q25"], 5),
                "bunker_share_q75": round(share["q75"], 5),
                "bunker_share_from": share_first_year,
                "bunker_share_n": share["n"],
                "bunker_share_by_source": ";".join(
                    f"{k}:{v}" for k, v in share["n_by_source"].items()
                ),
                "bunker_share_pooled": round(share["pooled"], 5),
                "bunker_share_families": ";".join(
                    f"{f}:{v['median']:.4f}(n={v['n']})"
                    for f, v in share["families"].items()
                ),
                "bunker_share_excluded_families": ";".join(
                    f"{f}:{v['median']:.4f}(n={v['n']})"
                    for f, v in share["excluded_families"].items()
                ),
                "bunker_set_co2_after_mt": round(set_co2_after_mt),
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
