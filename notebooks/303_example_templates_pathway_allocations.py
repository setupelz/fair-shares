# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags,-all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Pathway Allocation Examples (Reference)
#
# **Pre-configured examples demonstrating different equity principles for pathways.**
# For custom analysis, use **notebook 301**.
#
# **What's included:**
#
# - **Equal per capita** - Operationalizes equal rights (annual)
# - **Adjusted** - Operationalizes polluter-pays + ability-to-pay
# - **Convergence** - Smooth transitions while preserving equity budgets
# - **Per capita convergence** - For comparison only (includes grandfathering)
#
# Each demonstrates how principles translate to time-varying allocations.
#
# [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/) | [Climate Equity Concepts](https://setupelz.github.io/fair-shares/science/climate-equity-concepts/)

# %%
# Imports (run this first)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from pyprojroot import here

# Import fair-shares library components
from fair_shares.library.allocations import AllocationManager
from fair_shares.library.allocations.results import (
    BudgetAllocationResult,
    PathwayAllocationResult,
)
from fair_shares.library.exceptions import (
    DataProcessingError,
)
from fair_shares.library.utils import (
    calculate_budget_from_rcb,
    convert_parquet_to_wide_csv,
    ensure_string_year_columns,
    get_cumulative_budget_from_timeseries,
    get_world_totals_timeseries,
    setup_custom_data_pipeline,
)
from fair_shares.library.validation import (
    validate_has_year_columns,
    validate_index_structure,
    validate_stationary_dataframe,
)

# Set matplotlib style
plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

project_root = here()

# %% [markdown]
# ---
# ## Step 1: Data Configuration
#
# Pre-configured for RCB-pathways with CO2-FFI emissions.
#
# **Datasets**: PRIMAP emissions (2025), WDI GDP (2025), UN population (2025), UNU-WIDER Gini (2025), exponential-decay pathway generator

# %%
# =============================================================================
# DATA SOURCE CONFIGURATION
# =============================================================================

# Name for your allocation output folder
allocation_folder = "reference_pathway_allocations_rcb_pathways"

# Choose your emission category
emission_category = "co2-ffi"

# Choose your data sources
active_sources = {
    # Target: What climate goal to allocate
    "target": "rcb-pathways",
    # Historical emissions from PRIMAP database (March 2025 version)
    "emissions": "primap-202503",
    # GDP data from World Bank World Development Indicators (2025)
    "gdp": "wdi-2025",
    # Population projections from UN (2025)
    "population": "un-owid-2025",
    # Income inequality (Gini coefficients) from UNU-WIDER (2025)
    "gini": "unu-wider-2025",
    # Pathway generator for rcb-pathways (optional, defaults to "exponential-decay")
    "rcb_generator": "exponential-decay",
}

# For pathway allocations only - choose harmonisation year to historical data
desired_harmonisation_year = 2020

# %%
# Storing configuration for later use and confirming ready for Step 2

target = active_sources.get("target")
active_target_source = active_sources["target"]
active_emissions_source = active_sources["emissions"]
active_gdp_source = active_sources["gdp"]
active_population_source = active_sources["population"]
active_gini_source = active_sources["gini"]
if target != "rcbs":
    harmonisation_year = desired_harmonisation_year
else:
    harmonisation_year = None  # Not needed for RCBs

print("Configuration set!")
print(f"  - Emission category: {emission_category}")
print(f"  - Target source: {target}")
print(f"  - Emissions: {active_emissions_source}")
if harmonisation_year is not None:
    print(f"  - Harmonisation year: {harmonisation_year}")
print("\nReady to proceed to Step 2.")

# %% [markdown]
# ---
# ## Step 2: Pathway Allocation Approaches
#
# Six principle-based approaches:
#
# 1. Equal per capita - Egalitarianism (annual shares)
# 2. Adjusted - Historical responsibility + capability
# 3. Gini-adjusted - Subsistence protection
# 4. Cumulative convergence - Smooth transitions (budget-preserving)
# 5. Cumulative convergence adjusted - Convergence + CBDR-RC
# 6. Cumulative convergence Gini - Convergence + subsistence
#
# See [From Principle to Code](https://setupelz.github.io/fair-shares/science/principle-to-code/)

# %%
# =============================================================================
# ALLOCATION APPROACH CONFIGURATIONS
# =============================================================================

allocations = {
    # -------------------------------------------------------------------------
    # APPROACH 1: Equal Per Capita Pathway
    # -------------------------------------------------------------------------
    # Principle: Egalitarianism (annual shares)
    # See: docs/science/climate-equity-concepts.md (Equal Rights to Atmosphere)
    "equal-per-capita": [
        {
            "first_allocation_year": [2015],
            "preserve_first_allocation_year_shares": [False],
        }
    ],
    # -------------------------------------------------------------------------
    # APPROACH 2: Per Capita Adjusted Pathway
    # -------------------------------------------------------------------------
    # Principle: Historical responsibility + capability (CBDR-RC)
    # See: docs/science/climate-equity-concepts.md (CBDR-RC)
    "per-capita-adjusted": [
        # Configuration A: Historical responsibility only
        {
            "first_allocation_year": [2015],
            "responsibility_weight": [1.0],
            "historical_responsibility_year": [1990],
            "preserve_first_allocation_year_shares": [False],
        },
        # Configuration B: Capability only
        {
            "first_allocation_year": [2015],
            "capability_weight": [1.0],
            "preserve_first_allocation_year_shares": [False],
        },
        # Configuration C: Combined responsibility and capability
        {
            "first_allocation_year": [2015],
            "responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "historical_responsibility_year": [1990],
            "preserve_first_allocation_year_shares": [False],
        },
    ],
    # -------------------------------------------------------------------------
    # APPROACH 3: Per Capita Adjusted with Gini
    # -------------------------------------------------------------------------
    # Adjusts for within-country inequality using income thresholds.
    "per-capita-adjusted-gini": [
        # Configuration A: Gini-adjusted capability only
        {
            "first_allocation_year": [2015],
            "capability_weight": [1.0],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "preserve_first_allocation_year_shares": [False],
        },
        # Configuration B: Responsibility plus Gini-adjusted capability
        {
            "first_allocation_year": [2015],
            "responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "historical_responsibility_year": [1990],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "preserve_first_allocation_year_shares": [False],
        },
    ],
    # -------------------------------------------------------------------------
    # APPROACH 4: Cumulative Per Capita Convergence
    # -------------------------------------------------------------------------
    # Smoothly transitions to equal per capita while matching cumulative budgets.
    "cumulative-per-capita-convergence": [
        {
            "first_allocation_year": [2015],
            "strict": [False],
        }
    ],
    # -------------------------------------------------------------------------
    # APPROACH 5: Cumulative Per Capita Convergence with Adjustments
    # -------------------------------------------------------------------------
    # Convergence with responsibility and/or capability adjustments.
    "cumulative-per-capita-convergence-adjusted": [
        {
            "first_allocation_year": [2015],
            "responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "historical_responsibility_year": [1990],
            "strict": [False],
        }
    ],
    # -------------------------------------------------------------------------
    # APPROACH 6: Cumulative Per Capita Convergence with Gini
    # -------------------------------------------------------------------------
    # Principle: Convergence + subsistence protection
    # See: docs/science/climate-equity-concepts.md
    "cumulative-per-capita-convergence-gini-adjusted": [
        # Configuration A: Gini-adjusted capability only
        {
            "first_allocation_year": [2015],
            "capability_weight": [1.0],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "strict": [False],
        },
        # Configuration B: Responsibility plus Gini-adjusted capability
        {
            "first_allocation_year": [2015],
            "responsibility_weight": [0.5],
            "capability_weight": [0.5],
            "historical_responsibility_year": [1990],
            "income_floor": [7500],
            "max_gini_adjustment": [0.8],
            "strict": [False],
        },
    ],
}

print("Allocation approaches defined!")
print(f"  - Number of approaches: {len(allocations)}")
print(f"  - Approaches: {', '.join(allocations.keys())}")
print(f"  - Output folder: {allocation_folder}")
print("\nReady to run data pipeline and allocations!")

# %% [markdown]
# ---
# ## Step 3: Data Pipeline
#
# **Automated** - Run cell below. Takes 2-5 minutes.

# %%
print("=" * 70)
print("RUNNING DATA PIPELINE")
print("=" * 70)
print("\nThis may take several minutes..., check /output/source_id/ for progress")
print(f"Processing: {emission_category} emissions")
print(f"Target: {target}")
print("")

# Run the complete data setup pipeline
setup_info = setup_custom_data_pipeline(
    project_root=project_root,
    emission_category=emission_category,
    active_sources=active_sources,
    harmonisation_year=harmonisation_year,
    verbose=True,
)

# Extract key information for later use
source_id = setup_info["source_id"]
processed_dir = setup_info["paths"]["processed_dir"]
emission_category = setup_info["emission_category"]
harmonisation_year = setup_info["config"].harmonisation_year

print("\n" + "=" * 70)
print("DATA PIPELINE COMPLETED SUCCESSFULLY!")
print("=" * 70)
print(f"Source ID: {source_id}")
print(f"Emission category: {emission_category}")
print(f"Processed data saved to: {processed_dir}")
print("\nReady to run allocations!")

# %% [markdown]
# ---
# ## Step 4: Run Allocations
#
# **Automated** - Run cell below.
#
# **Outputs**: `allocations_relative.parquet`, `allocations_absolute.parquet`, `param_manifest.csv`, `README.md`


# %%
print("=" * 70)
print("RUNNING ALLOCATIONS")
print("=" * 70)
print(f"\nAllocations to run: {', '.join(allocations.keys())}")
print(f"Output folder: {allocation_folder}")
print("\nLoading processed data...")

# Load country data
emiss_path = processed_dir / f"country_emissions_{emission_category}_timeseries.csv"
country_emissions_df = pd.read_csv(emiss_path)
country_emissions_df = country_emissions_df.set_index(
    ["iso3c", "unit", "emission-category"]
)
country_emissions_df = ensure_string_year_columns(country_emissions_df)

country_gdp_df = pd.read_csv(processed_dir / "country_gdp_timeseries.csv")
country_gdp_df = country_gdp_df.set_index(["iso3c", "unit"])
country_gdp_df = ensure_string_year_columns(country_gdp_df)
validate_index_structure(country_gdp_df, "Country GDP", ["iso3c", "unit"])
validate_has_year_columns(country_gdp_df, "Country GDP")

country_population_df = pd.read_csv(processed_dir / "country_population_timeseries.csv")
country_population_df = country_population_df.set_index(["iso3c", "unit"])
country_population_df = ensure_string_year_columns(country_population_df)
validate_index_structure(country_population_df, "Country population", ["iso3c", "unit"])
validate_has_year_columns(country_population_df, "Country population")

country_gini_df = pd.read_csv(processed_dir / "country_gini_stationary.csv")
country_gini_df = country_gini_df.set_index(["iso3c", "unit"])
validate_stationary_dataframe(country_gini_df, "Country Gini", ["gini"])

print("Country data loaded")

# Load data based on target
if target == "rcbs":  # RCBs
    rcbs_df = pd.read_csv(processed_dir / "rcbs.csv")
    world_scenarios_df = None

    # Load world emissions for RCB budget calculations
    world_emiss_path = (
        processed_dir / f"world_emissions_{emission_category}_timeseries.csv"
    )
    world_emissions_df = pd.read_csv(world_emiss_path)
    world_emissions_df = world_emissions_df.set_index(
        ["iso3c", "unit", "emission-category"]
    )
    world_emissions_df = ensure_string_year_columns(world_emissions_df)
    print("RCB data loaded")
else:  # pathways
    scenarios_path = processed_dir / f"world_scenarios_{emission_category}_complete.csv"
    world_scenarios_df = pd.read_csv(scenarios_path)
    world_scenarios_df = world_scenarios_df.set_index(
        [
            "climate-assessment",
            "quantile",
            "source",
            "iso3c",
            "unit",
            "emission-category",
        ]
    )
    world_scenarios_df = ensure_string_year_columns(world_scenarios_df)
    rcbs_df = None
    world_emissions_df = None
    print("Scenario data loaded")

    # Load net-negative emissions metadata
    net_negative_metadata_path = processed_dir / "net_negative_emissions_metadata.yaml"
    if net_negative_metadata_path.exists():
        with open(net_negative_metadata_path) as f:
            net_negative_metadata = yaml.safe_load(f) or {}
        print("Net-negative emissions metadata loaded")
    else:
        net_negative_metadata = {}
        print("Warning: No net-negative emissions metadata found")

print("\nInitializing allocation manager...")

# Initialize allocation manager
allocation_manager = AllocationManager()

# Create output directory
output_dir = project_root / "output" / source_id / "allocations" / allocation_folder
output_dir.mkdir(parents=True, exist_ok=True)

# Build data context for parquet schema
data_context = {
    "source-id": source_id,
    "allocation-folder": allocation_folder,
    "emission-category": emission_category,
    "target-source": active_target_source,
    "emissions-source": active_sources["emissions"],
    "gdp-source": active_sources["gdp"],
    "population-source": active_sources["population"],
    "gini-source": active_sources["gini"],
}

# Track all processed parameter combinations for manifest
param_manifest_rows = []

# Delete existing parquet files before starting allocations
allocation_manager._delete_existing_parquet_files(output_dir)

print("Output directories created")
print("\nRunning allocation calculations...")
print("(This may take a few minutes)")

# Run allocations
if target == "rcbs":
    for idx, rcb_row in rcbs_df.iterrows():
        rcb_source = rcb_row["source"]
        climate_assessment = rcb_row["climate-assessment"]
        quantile = rcb_row["quantile"]
        rcb_value = rcb_row["rcb_2020_mt"]

        print(f"  Processing: {climate_assessment} {quantile}")

        results = allocation_manager.run_parameter_grid(
            allocations_config=allocations,
            population_ts=country_population_df,
            gdp_ts=country_gdp_df,
            gini_s=country_gini_df,
            country_actual_emissions_ts=country_emissions_df,
            emission_category=emission_category,
            target_source=target,
            harmonisation_year=harmonisation_year,
        )

        for result in results:
            allocation_year = result.parameters.get("allocation_year")
            total_budget_allocated = calculate_budget_from_rcb(
                rcb_value=rcb_value,
                allocation_year=allocation_year,
                world_scenario_emissions_ts=world_emissions_df,
                verbose=False,
            )

            cumulative_budget = pd.DataFrame(
                {str(allocation_year): [total_budget_allocated]},
                index=world_emissions_df.index,
            )

            absolute_emissions = result.get_absolute_budgets(cumulative_budget)

            data_context_with_rcb = data_context.copy()
            data_context_with_rcb["source"] = rcb_source
            data_context_with_rcb["missing-net-negative-mtco2e"] = None

            allocation_manager.save_allocation_result(
                result=result,
                output_dir=output_dir,
                absolute_emissions=absolute_emissions,
                climate_assessment=climate_assessment,
                quantile=quantile,
                data_context=data_context_with_rcb,
                **{"total-budget": total_budget_allocated},
            )

            manifest_row = {
                "approach": result.approach,
                "climate-assessment": climate_assessment,
                "quantile": quantile,
                "emission-category": emission_category,
                "rcb-source": rcb_source,
            }
            if result.parameters:
                manifest_row.update(result.parameters)
            if data_context_with_rcb:
                manifest_row.update(data_context_with_rcb)
            param_manifest_rows.append(manifest_row)

else:
    scenario_groups = world_scenarios_df.groupby(
        ["climate-assessment", "quantile", "source"]
    )
    for scenario_idx, scenario_group in scenario_groups:
        climate_assessment, quantile, source = scenario_idx

        print(f"  Processing: {source}: {climate_assessment} {quantile}")

        expected_idx = [
            "climate-assessment",
            "quantile",
            "source",
            "iso3c",
            "unit",
            "emission-category",
        ]
        world_data = get_world_totals_timeseries(
            scenario_group, "World", expected_index_names=expected_idx
        )

        # Get net-negative emissions metadata for this climate assessment
        missing_net_negative = None
        if emission_category in net_negative_metadata:
            pathways = net_negative_metadata[emission_category].get("pathways", [])
            for pathway in pathways:
                if pathway.get("climate-assessment") == climate_assessment:
                    missing_net_negative = pathway.get(
                        "cumulative_net_negative_emissions", 0.0
                    )
                    break

        results = allocation_manager.run_parameter_grid(
            allocations_config=allocations,
            population_ts=country_population_df,
            gdp_ts=country_gdp_df,
            gini_s=country_gini_df,
            country_actual_emissions_ts=country_emissions_df,
            emission_category=emission_category,
            world_scenario_emissions_ts=world_data,
            target_source=target,
            harmonisation_year=harmonisation_year,
        )

        for result in results:
            if isinstance(result, BudgetAllocationResult):
                allocation_year = result.parameters.get("allocation_year")
                cumulative_budget = get_cumulative_budget_from_timeseries(
                    world_data, allocation_year, expected_index_names=expected_idx
                )
                absolute_emissions = result.get_absolute_budgets(cumulative_budget)
            elif isinstance(result, PathwayAllocationResult):
                absolute_emissions = result.get_absolute_emissions(world_data)
            else:
                raise DataProcessingError(f"Unknown result type: {type(result)}")

            # Update data context with net-negative metadata and source for this scenario
            data_context_with_metadata = data_context.copy()
            data_context_with_metadata["missing-net-negative-mtco2e"] = (
                missing_net_negative
            )
            data_context_with_metadata["source"] = source

            allocation_manager.save_allocation_result(
                result=result,
                output_dir=output_dir,
                absolute_emissions=absolute_emissions,
                climate_assessment=climate_assessment,
                quantile=quantile,
                data_context=data_context_with_metadata,
            )

            manifest_row = {
                "approach": result.approach,
                "climate-assessment": climate_assessment,
                "quantile": quantile,
                "source": source,
                "emission-category": emission_category,
            }
            if result.parameters:
                manifest_row.update(result.parameters)
            if data_context_with_metadata:
                manifest_row.update(data_context_with_metadata)
            param_manifest_rows.append(manifest_row)

print("\nSaving metadata and documentation...")

# Save parameter manifest
allocation_manager.create_param_manifest(param_manifest_rows, output_dir)

# Generate README files
allocation_manager.generate_readme(output_dir=output_dir, data_context=data_context)

# Summarize executed approaches (with optional display mapping)
executed_approaches = sorted({row["approach"] for row in param_manifest_rows})
print("\nExecuted allocation approaches:")
for app in executed_approaches:
    print(f"  - {app}")

print("\n" + "=" * 70)
print("ALLOCATIONS COMPLETED SUCCESSFULLY!")
print("=" * 70)
print(f"Results saved to: {output_dir}")
print(f"Total parameter combinations: {len(param_manifest_rows)}")
print(f"Approaches: {', '.join(allocations.keys())}")

# %% [markdown]
# ---
# ## Step 5: Explore Results
#
# Visualize results for a specific country. Edit `TEST_COUNTRY` (ISO alpha-3: USA, CHN, IND, etc.) and `PLOT_START_YEAR`.
#
# **Plot guide**: Black = historical | Colored = allocations | Dashed = net-zero
#
# [Pathway allocations](https://setupelz.github.io/fair-shares/science/allocations/)

# %%
# Set country and year to explore
TEST_COUNTRY = "AUS"  # EDIT THIS: country code to explore
PLOT_START_YEAR = 2015  # EDIT THIS: year to start plotting

# %%
# Load and plot results for a sample country
absolute_parquet_path = output_dir / "allocations_absolute.parquet"
if absolute_parquet_path.exists():
    absolute_df = pd.read_parquet(absolute_parquet_path)
    country_data = absolute_df[absolute_df["iso3c"] == TEST_COUNTRY]

    year_cols = [
        col
        for col in country_data.columns
        if col.isdigit() and int(col) >= PLOT_START_YEAR
    ]
    non_year_cols = [col for col in country_data.columns if not col.isdigit()]
    country_data = country_data[non_year_cols + year_cols]

    if not country_data.empty:
        # Get all unique approaches from the data for this country
        available_approaches = country_data["approach"].unique()
        configured_approaches = list(allocations.keys())

        # Debug output
        print(
            f"\nDebug: Approaches in data for {TEST_COUNTRY}: {list(available_approaches)}"
        )
        print(f"Debug: Configured approaches: {configured_approaches}")

        # Use all configured approaches that exist in the data
        approaches = [a for a in configured_approaches if a in available_approaches]

        if len(approaches) != len(configured_approaches):
            missing = set(configured_approaches) - set(approaches)
            print(f"Warning: Some configured approaches not found in data: {missing}")
            print(
                f"Available approaches in full dataset: {list(absolute_df['approach'].unique())}"
            )

        grp = country_data.groupby(["climate-assessment", "quantile", "source"]).size()
        scenario_groups = grp.reset_index()[
            ["climate-assessment", "quantile", "source"]
        ]

        n_approaches = len(approaches)
        n_scenarios = len(scenario_groups)

        fig, axes = plt.subplots(
            n_scenarios,
            n_approaches,
            figsize=(6 * n_approaches, 5 * n_scenarios),
            sharex=True,
            sharey=True,
        )
        if not isinstance(axes, np.ndarray):
            axes = np.array([[axes]])
        elif axes.ndim == 1:
            if n_scenarios == 1:
                axes = axes[np.newaxis, :]
            else:
                axes = axes[:, np.newaxis]

        for i, (_, scenario) in enumerate(scenario_groups.iterrows()):
            ca = scenario["climate-assessment"]
            q = scenario["quantile"]
            src = scenario["source"]
            scenario_data = country_data[
                (country_data["climate-assessment"] == ca)
                & (country_data["quantile"] == q)
                & (country_data["source"] == src)
            ]

            for j, approach in enumerate(approaches):
                ax = axes[i, j]
                approach_data = scenario_data[scenario_data["approach"] == approach]

                if approach_data.empty:
                    ax.text(
                        0.5,
                        0.5,
                        f"No data for {approach}",
                        ha="center",
                        va="center",
                        transform=ax.transAxes,
                    )
                    ax.set_title(
                        f"{approach}\n{src}: {ca} {q}", fontsize=12, fontweight="bold"
                    )
                    ax.set_xlabel("Year", fontsize=10)
                    ax.set_ylabel("Emissions (Mt CO2e)", fontsize=10)
                    continue

                year_cols = [col for col in approach_data.columns if col.isdigit()]
                years = [int(col) for col in year_cols]

                colors = plt.cm.Set3(np.linspace(0, 1, len(approach_data)))
                for idx, (row_idx, row) in enumerate(approach_data.iterrows()):
                    emissions = row[year_cols].values
                    ax.plot(
                        years,
                        emissions,
                        marker="o",
                        markersize=4,
                        linewidth=2,
                        color=colors[idx],
                        alpha=0.8,
                    )

                try:
                    hist_path = (
                        processed_dir
                        / f"country_emissions_{emission_category}_timeseries.csv"
                    )
                    if hist_path.exists():
                        hist_df = pd.read_csv(hist_path, index_col=[0, 1, 2])
                        country_actual = hist_df[
                            (hist_df.index.get_level_values("iso3c") == TEST_COUNTRY)
                            & (
                                hist_df.index.get_level_values("emission-category")
                                == emission_category
                            )
                        ]
                        if not country_actual.empty:
                            year_cols = [
                                col
                                for col in country_actual.columns
                                if str(col).isdigit() and int(col) >= PLOT_START_YEAR
                            ]
                            non_year_cols = [
                                col
                                for col in country_actual.columns
                                if not str(col).isdigit()
                            ]
                            country_actual = country_actual[non_year_cols + year_cols]

                            actual_years = [int(col) for col in year_cols]
                            actual_emissions = country_actual[year_cols].iloc[0].values
                            ax.plot(
                                actual_years,
                                actual_emissions,
                                color="black",
                                linewidth=3,
                                alpha=0.9,
                                label="Historical",
                            )
                except Exception:
                    pass

                # Add dashed zero line
                ax.axhline(
                    y=0, color="black", linestyle="--", linewidth=1, alpha=0.5, zorder=0
                )

                ax.set_title(
                    f"{approach}\n{src}: {ca} {q}", fontsize=12, fontweight="bold"
                )
                ax.set_xlabel("Year", fontsize=10)
                ax.set_ylabel("Emissions (Mt CO2e)", fontsize=10)
                if i == 0 and j == 0:
                    ax.legend(loc="upper right", fontsize=8)

        plt.suptitle(
            f"Emissions Allocations for {TEST_COUNTRY}", fontsize=16, fontweight="bold"
        )
        plt.tight_layout()
        plt.show()

# %% [markdown]
# ---
# ## Step 6: Export to CSV (Optional)
#
# Convert parquet results to wide-format CSV for Excel or other tools.

# %%
# =============================================================================
# CONFIGURE CSV EXPORT
# =============================================================================

allocation_param_prefixes = {
    # "first-allocation-year": "y",
    "allocation-year": "ay",
    # "preserve-first-allocation-year-shares": "pfa",
    # "preserve-allocation-year-shares": "pa",
    # "convergence-year": "cy",
    # "convergence-speed": "cs",
    "responsibility-weight": "rw",
    "capability-weight": "cw",
    "historical-responsibility-year": "hr",
    # "responsibility-per-capita": "rpc",
    # "capability-per-capita": "cpc",
    # "responsibility-exponent": "re",
    # "capability-exponent": "ce",
    # "responsibility-functional-form": "rff",
    # "capability-functional-form": "cff",
    # "max-deviation-sigma": "sigma",
    # "income-floor": "if",
    # "max-gini-adjustment": "gini",
}

# Create wide-format CSV
csv_path = convert_parquet_to_wide_csv(
    allocations_dir=output_dir,
    config_prefixes=allocation_param_prefixes,
)

print(f"\nWide-format CSV created: {csv_path}")

# %%
