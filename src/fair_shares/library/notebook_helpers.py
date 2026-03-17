"""Notebook helper functions.

Extracts shared data-loading and allocation-execution boilerplate from the
300-series notebooks into reusable functions.  Each notebook becomes a thin
configuration wrapper that calls these.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from fair_shares.library.allocations import (
    create_param_manifest,
    delete_existing_parquet_files,
    derive_pathway_allocations,
    generate_readme,
    is_budget_approach,
    run_parameter_grid,
    save_allocation_result,
)
from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)
from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils.data.completeness import (
    get_cumulative_budget_from_timeseries,
    get_world_totals_timeseries,
)
from fair_shares.library.utils.data.config import (
    ALL_GHG_CO2_CATEGORIES,
    is_budget_target,
)
from fair_shares.library.utils.data.rcb import calculate_budget_from_rcb
from fair_shares.library.utils.data.setup import lookup_net_negative_emissions
from fair_shares.library.utils.dataframes import ensure_string_year_columns
from fair_shares.library.validation import (
    validate_has_year_columns,
    validate_index_structure,
    validate_stationary_dataframe,
)

logger = logging.getLogger(__name__)


def load_allocation_data(
    processed_dir: Path,
    target: str,
    final_categories: list[str],
    emission_category: str,
) -> dict[str, Any]:
    """Load all data needed for allocation execution.

    Replaces ~80 lines of identical data-loading boilerplate in 301/302/303.

    Parameters
    ----------
    processed_dir : Path
        Directory containing processed CSV files from the data pipeline.
    target : str
        Target source type ("rcbs", "pathway", "rcb-pathways").
    final_categories : list[str]
        Categories produced by decomposition (from ``get_final_categories``).
    emission_category : str
        Original emission category (for display/logging).

    Returns
    -------
    dict with keys:
        emissions_data, scenarios_data, rcbs_data, world_emissions_data,
        country_gdp_df, country_population_df, country_gini_df,
        net_negative_metadata
    """
    emissions_data = {}
    scenarios_data = {}
    rcbs_data = {}
    world_emissions_data = {}

    for category in final_categories:
        # Country emissions — always available
        emiss_path = processed_dir / f"country_emissions_{category}_timeseries.csv"
        emissions_data[category] = pd.read_csv(emiss_path).set_index(
            ["iso3c", "unit", "emission-category"]
        )
        emissions_data[category] = ensure_string_year_columns(emissions_data[category])

        if is_budget_target(target, category):
            # Budget mode: load RCBs + world emissions
            rcbs_data[category] = pd.read_csv(processed_dir / f"rcbs_{category}.csv")
            we_path = processed_dir / f"world_emissions_{category}_timeseries.csv"
            world_emissions_data[category] = pd.read_csv(we_path).set_index(
                ["iso3c", "unit", "emission-category"]
            )
            world_emissions_data[category] = ensure_string_year_columns(
                world_emissions_data[category]
            )
        else:
            # Pathway mode: load scenarios with conditional "source" in index
            effective_target = (
                target if category in ALL_GHG_CO2_CATEGORIES else "pathway"
            )
            index_cols = [
                "climate-assessment",
                "quantile",
                "iso3c",
                "unit",
                "emission-category",
            ]
            if effective_target == "rcb-pathways":
                index_cols.insert(2, "source")
            sc_path = processed_dir / f"world_scenarios_{category}_complete.csv"
            sc_df = pd.read_csv(sc_path)
            # Include source in index if present (e.g. non-CO2 pathways
            # in composite rcbs runs have a source column from AR6)
            if "source" in sc_df.columns and "source" not in index_cols:
                index_cols.insert(2, "source")
            scenarios_data[category] = sc_df.set_index(index_cols)
            scenarios_data[category] = ensure_string_year_columns(
                scenarios_data[category]
            )

    print(
        f"  Loaded data for {len(final_categories)} categories: "
        f"{', '.join(final_categories)}"
    )

    # Shared socioeconomic data
    country_gdp_df = pd.read_csv(processed_dir / "country_gdp_timeseries.csv")
    country_gdp_df = country_gdp_df.set_index(["iso3c", "unit"])
    country_gdp_df = ensure_string_year_columns(country_gdp_df)
    validate_index_structure(country_gdp_df, "Country GDP", ["iso3c", "unit"])
    validate_has_year_columns(country_gdp_df, "Country GDP")

    country_population_df = pd.read_csv(
        processed_dir / "country_population_timeseries.csv"
    )
    country_population_df = country_population_df.set_index(["iso3c", "unit"])
    country_population_df = ensure_string_year_columns(country_population_df)
    validate_index_structure(
        country_population_df, "Country population", ["iso3c", "unit"]
    )
    validate_has_year_columns(country_population_df, "Country population")

    country_gini_df = pd.read_csv(processed_dir / "country_gini_stationary.csv")
    country_gini_df = country_gini_df.set_index(["iso3c", "unit"])
    validate_stationary_dataframe(country_gini_df, "Country Gini", ["gini"])

    print("  Socioeconomic data loaded and validated")

    # Net-negative emissions metadata
    net_negative_metadata_path = processed_dir / "net_negative_emissions_metadata.yaml"
    if net_negative_metadata_path.exists():
        with open(net_negative_metadata_path) as f:
            net_negative_metadata = yaml.safe_load(f) or {}
    else:
        net_negative_metadata = {}

    return {
        "emissions_data": emissions_data,
        "scenarios_data": scenarios_data,
        "rcbs_data": rcbs_data,
        "world_emissions_data": world_emissions_data,
        "country_gdp_df": country_gdp_df,
        "country_population_df": country_population_df,
        "country_gini_df": country_gini_df,
        "net_negative_metadata": net_negative_metadata,
    }


def run_all_allocations(
    allocations: dict[str, Any],
    loaded_data: dict[str, Any],
    output_dir: Path,
    data_context: dict[str, str],
    target: str,
    final_categories: list[str],
    harmonisation_year: int | None,
) -> list[dict[str, Any]]:
    """Execute all allocation approaches and save results.

    Handles budget/pathway splitting, category iteration, manifest and
    README generation.  Replaces ~70 lines of identical execution code.

    Parameters
    ----------
    allocations : dict
        All allocation approach configurations.  The function splits them
        into budget vs pathway approaches internally.
    loaded_data : dict
        Output of ``load_allocation_data()``.
    output_dir : Path
        Directory for output files.
    data_context : dict
        Metadata dict for parquet schema.
    target : str
        Target source type.
    final_categories : list[str]
        Categories to iterate over.
    harmonisation_year : int | None
        Harmonisation year (None for pure RCB runs).

    Returns
    -------
    list[dict]
        Parameter-manifest rows for all allocations.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    delete_existing_parquet_files(output_dir)

    # Split approaches by type
    budget_allocs = {k: v for k, v in allocations.items() if is_budget_approach(k)}
    pathway_allocs = {k: v for k, v in allocations.items() if not is_budget_approach(k)}

    # Auto-derive pathway approaches from budget approaches when none are
    # explicitly provided.  This means users only need to define budget
    # approaches for composite RCB runs — the non-CO2 pathway equivalents
    # are generated automatically (e.g. equal-per-capita-budget →
    # equal-per-capita with allocation_year → first_allocation_year).
    if budget_allocs and not pathway_allocs:
        pathway_allocs = derive_pathway_allocations(budget_allocs)
        logger.info(
            "Derived pathway approaches for non-CO2: %s",
            list(pathway_allocs.keys()),
        )

    param_manifest_rows: list[dict[str, Any]] = []

    for category in final_categories:
        is_budget = is_budget_target(target, category)
        allocs = budget_allocs if is_budget else pathway_allocs

        # Correct target_source per category
        if is_budget:
            target_src = "rcbs"
        elif category not in ALL_GHG_CO2_CATEGORIES:
            target_src = "pathway"
        else:
            target_src = target

        if not allocs:
            print(f"  Skipping {category}: no compatible approaches")
            continue

        mode = "budget" if is_budget else "pathway"
        print(f"\n  {category} ({mode}) — {len(allocs)} approaches")

        rows = run_and_save_category_allocations(
            allocations=allocs,
            category=category,
            target_source=target_src,
            country_emissions=loaded_data["emissions_data"][category],
            world_data=loaded_data["scenarios_data"].get(category),
            rcbs_df=loaded_data["rcbs_data"].get(category),
            gdp=loaded_data["country_gdp_df"],
            population=loaded_data["country_population_df"],
            gini=loaded_data["country_gini_df"],
            output_dir=output_dir,
            harmonisation_year=harmonisation_year,
            net_negative_metadata=loaded_data["net_negative_metadata"],
            data_context=data_context,
            is_budget=is_budget,
            world_emissions=loaded_data["world_emissions_data"].get(category),
        )
        param_manifest_rows.extend(rows)
        print(f"    {len(rows)} parameter combinations processed")

    # Save manifest and README
    create_param_manifest(param_manifest_rows, output_dir)
    generate_readme(output_dir=output_dir, data_context=data_context)

    return param_manifest_rows


def print_results_summary(
    output_dir: Path,
    param_manifest_rows: list[dict[str, Any]],
    allocations: dict[str, Any],
) -> None:
    """Print a clean summary of completed allocations."""
    executed = sorted({row["approach"] for row in param_manifest_rows})

    print("\n" + "=" * 60)
    print("ALLOCATIONS COMPLETE")
    print("=" * 60)
    print(f"\nApproaches: {', '.join(executed)}")
    print(f"Parameter combinations: {len(param_manifest_rows)}")
    print(f"\nOutput: {output_dir}")

    # File listing with sizes
    for pattern, label in [
        ("*.parquet", "Parquet"),
        ("*.csv", "CSV"),
        ("*.md", "Docs"),
    ]:
        files = sorted(output_dir.glob(pattern))
        if files:
            print(f"\n  {label}:")
            for f in files:
                size_kb = f.stat().st_size / 1024
                print(f"    {f.name} ({size_kb:.1f} KB)")


# ---------------------------------------------------------------------------
# Category-level allocation runner (merged from runner.py)
# ---------------------------------------------------------------------------


def run_and_save_category_allocations(
    allocations: dict[str, Any],
    category: str,
    target_source: str,
    country_emissions: pd.DataFrame,
    world_data: pd.DataFrame,
    rcbs_df: pd.DataFrame | None,
    gdp: pd.DataFrame,
    population: pd.DataFrame,
    gini: pd.DataFrame,
    output_dir: Path,
    *,
    harmonisation_year: int,
    net_negative_metadata: dict,
    data_context: dict,
    is_budget: bool,
    world_emissions: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Run allocations for one emission *category* and save results.

    Parameters
    ----------
    allocations : dict
        Allocation approach configurations (as expected by ``run_parameter_grid``).
    category : str
        Emission category being processed (e.g. ``"co2-ffi"``).
    target_source : str
        Target type (``"rcbs"``, ``"pathway"``, ``"rcb-pathways"``).
    country_emissions, world_data, rcbs_df, gdp, population, gini : DataFrame
        Input data — see ``run_all_allocations`` for details.
    output_dir : Path
        Directory for output parquet files.
    harmonisation_year : int
        Harmonisation year for scenario-based targets.
    net_negative_metadata : dict
        Net-negative emissions metadata keyed by category.
    data_context : dict
        Base data-context dict (will be copied per result).
    is_budget : bool
        ``True`` for budget (RCB) allocation, ``False`` for pathway allocation.
    world_emissions : DataFrame | None
        World historical emissions timeseries — required for budget runs.

    Returns
    -------
    list[dict]
        Parameter-manifest rows produced during this category pass.
    """
    if is_budget:
        return _run_budget_allocations(
            allocations=allocations,
            category=category,
            target_source=target_source,
            country_emissions=country_emissions,
            rcbs_df=rcbs_df,
            gdp=gdp,
            population=population,
            gini=gini,
            output_dir=output_dir,
            harmonisation_year=harmonisation_year,
            data_context=data_context,
            world_emissions=world_emissions,
        )
    else:
        return _run_pathway_allocations(
            allocations=allocations,
            category=category,
            target_source=target_source,
            country_emissions=country_emissions,
            world_data=world_data,
            gdp=gdp,
            population=population,
            gini=gini,
            output_dir=output_dir,
            harmonisation_year=harmonisation_year,
            net_negative_metadata=net_negative_metadata,
            data_context=data_context,
        )


def _build_manifest_row(
    result,
    climate_assessment: str,
    quantile: float,
    category: str,
    cat_context: dict,
    *,
    rcb_source: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    """Build a manifest row from an allocation result and context."""
    manifest_row: dict[str, Any] = {
        "approach": result.approach,
        "climate-assessment": climate_assessment,
        "quantile": quantile,
        "emission-category": category,
    }
    if rcb_source is not None:
        manifest_row["rcb-source"] = rcb_source
    if source is not None:
        manifest_row["source"] = source
    if result.parameters:
        manifest_row.update(result.parameters)
    manifest_row.update(cat_context)
    return manifest_row


def _run_budget_allocations(
    *,
    allocations: dict[str, Any],
    category: str,
    target_source: str,
    country_emissions: pd.DataFrame,
    rcbs_df: pd.DataFrame,
    gdp: pd.DataFrame,
    population: pd.DataFrame,
    gini: pd.DataFrame,
    output_dir: Path,
    harmonisation_year: int,
    data_context: dict,
    world_emissions: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Iterate over RCB rows and run budget allocations for each."""
    manifest_rows: list[dict[str, Any]] = []

    # Compute share allocations once — they depend only on socio-economic data
    # and config, not on individual RCB values.
    results = run_parameter_grid(
        allocations_config=allocations,
        population_ts=population,
        gdp_ts=gdp,
        gini_s=gini,
        country_actual_emissions_ts=country_emissions,
        emission_category=category,
        target_source=target_source,
        harmonisation_year=harmonisation_year,
    )

    for _idx, rcb_row in rcbs_df.iterrows():
        rcb_source = rcb_row["source"]
        climate_assessment = rcb_row["climate-assessment"]
        quantile = rcb_row["quantile"]
        rcb_value = rcb_row["rcb_2020_mt"]

        for result in results:
            allocation_year = result.parameters.get("allocation_year")
            total_budget_allocated = calculate_budget_from_rcb(
                rcb_value=rcb_value,
                allocation_year=allocation_year,
                world_scenario_emissions_ts=world_emissions,
                verbose=False,
            )

            cumulative_budget = pd.DataFrame(
                {str(allocation_year): [total_budget_allocated]},
                index=world_emissions.index,
            )

            absolute_emissions = result.get_absolute_budgets(cumulative_budget)

            cat_context = data_context.copy()
            cat_context["emission-category"] = category
            cat_context["source"] = rcb_source
            cat_context["missing-net-negative-mtco2e"] = None

            save_allocation_result(
                result=result,
                output_dir=output_dir,
                absolute_emissions=absolute_emissions,
                climate_assessment=climate_assessment,
                quantile=quantile,
                data_context=cat_context,
                **{"total-budget": total_budget_allocated},
            )

            manifest_row = _build_manifest_row(
                result,
                climate_assessment,
                quantile,
                category,
                cat_context,
                rcb_source=rcb_source,
            )
            manifest_rows.append(manifest_row)

    return manifest_rows


def _run_pathway_allocations(
    *,
    allocations: dict[str, Any],
    category: str,
    target_source: str,
    country_emissions: pd.DataFrame,
    world_data: pd.DataFrame,
    gdp: pd.DataFrame,
    population: pd.DataFrame,
    gini: pd.DataFrame,
    output_dir: Path,
    harmonisation_year: int,
    net_negative_metadata: dict,
    data_context: dict,
) -> list[dict[str, Any]]:
    """Group scenarios and run pathway allocations for each group."""
    manifest_rows: list[dict[str, Any]] = []

    has_source = "source" in world_data.index.names
    groupby_cols = ["climate-assessment", "quantile"]
    if has_source:
        groupby_cols.append("source")

    expected_idx = list(world_data.index.names)

    scenario_groups = world_data.groupby(groupby_cols)
    for scenario_idx, scenario_group in scenario_groups:
        if has_source:
            climate_assessment, quantile, source = scenario_idx
        else:
            climate_assessment, quantile = scenario_idx
            source = None

        world_ts = get_world_totals_timeseries(
            scenario_group, "World", expected_index_names=expected_idx
        )

        missing_net_negative = lookup_net_negative_emissions(
            net_negative_metadata, category, climate_assessment
        )

        results = run_parameter_grid(
            allocations_config=allocations,
            population_ts=population,
            gdp_ts=gdp,
            gini_s=gini,
            country_actual_emissions_ts=country_emissions,
            emission_category=category,
            world_scenario_emissions_ts=world_ts,
            target_source=target_source,
            harmonisation_year=harmonisation_year,
        )

        for result in results:
            if isinstance(result, BudgetAllocationResult):
                allocation_year = result.parameters.get("allocation_year")
                cumulative_budget = get_cumulative_budget_from_timeseries(
                    world_ts, allocation_year, expected_index_names=expected_idx
                )
                absolute_emissions = result.get_absolute_budgets(cumulative_budget)
            elif isinstance(result, PathwayAllocationResult):
                absolute_emissions = result.get_absolute_emissions(world_ts)
            else:
                raise DataProcessingError(f"Unknown result type: {type(result)}")

            cat_context = data_context.copy()
            cat_context["emission-category"] = category
            cat_context["missing-net-negative-mtco2e"] = missing_net_negative
            if source is not None:
                cat_context["source"] = source

            save_allocation_result(
                result=result,
                output_dir=output_dir,
                absolute_emissions=absolute_emissions,
                climate_assessment=climate_assessment,
                quantile=quantile,
                data_context=cat_context,
            )

            manifest_row = _build_manifest_row(
                result,
                climate_assessment,
                quantile,
                category,
                cat_context,
                source=source,
            )
            manifest_rows.append(manifest_row)

    return manifest_rows
