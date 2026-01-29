# ============================================================================
# fair-shares Data Preprocessing Pipeline (Snakemake)
# ============================================================================
#
#    This Snakefile handles all data preprocessing steps.
#
#    Example use (run programmatically in the notebooks):
#     snakemake --config \
#       emission_category=co2-ffi \
#       active_emissions_source=primap-202503 \
#       active_gdp_source=wdi-2025 \
#       active_population_source=un-owid-2025 \
#       active_gini_source=unu-wider-2025 \
#       active_target_source=rcbs \
#       --cores 1
#
# It also interacts with Make targets to simplify development.
#   make dev-pipeline-rcbs (creates RCBs pipeline)
#   make dev-pipeline-scenarios (creates AR6 pipeline)
#
# ============================================================================

# Get configuration parameters from command line
emission_category = config.get("emission_category", None)
active_emissions_source = config.get("active_emissions_source", None)
active_gdp_source = config.get("active_gdp_source", None)
active_population_source = config.get("active_population_source", None)
active_gini_source = config.get("active_gini_source", None)
active_target_source = config.get("active_target_source", None)
rcb_generator = config.get("rcb_generator", None)

# Minimal check for emission_category (required for all operations)
# All other validation is delegated to Pydantic models (single source of truth)
if emission_category is None:
    raise ValueError(
        "Required parameter: emission_category\n"
        "Example: snakemake --config emission_category=co2-ffi "
        "active_emissions_source=primap-202503 active_gdp_source=wdi-2025 "
        "active_population_source=un-owid-2025 active_gini_source=unu-wider-2025 "
        "active_target_source=ar6\n\n"
        "For custom allocations, use: notebooks/301_custom_fair_share_allocation.py"
    )

# Build active sources dict for passing to Pydantic validation
# Validation happens in compose_config rule via build_data_config()
active_sources_dict = {
    "emissions": active_emissions_source,
    "gdp": active_gdp_source,
    "population": active_population_source,
    "gini": active_gini_source,
    "target": active_target_source,
}

# Add rcb_generator if specified
if rcb_generator is not None:
    active_sources_dict["rcb_generator"] = rcb_generator

# Build SOURCE_ID for output paths
# This duplicates logic from build_source_id() but avoids import issues at Snakefile load time
if active_target_source == "rcb-pathways":
    if rcb_generator is None:
        rcb_generator = "exponential-decay"
    target_with_generator = f"{active_target_source}-{rcb_generator}"
else:
    target_with_generator = active_target_source if active_target_source else "unknown"

SOURCE_ID = "_".join([
    active_emissions_source if active_emissions_source else "unknown",
    active_gdp_source if active_gdp_source else "unknown",
    active_population_source if active_population_source else "unknown",
    active_gini_source if active_gini_source else "unknown",
    target_with_generator,
    emission_category,
])
OUTPUT_DIR = f"output/{SOURCE_ID}"
NOTEBOOK_DIR = "notebooks"

# Determine which master preprocessing notebook to use
if active_target_source == "rcbs":
    # Use RCB-based preprocessing (budget allocations only)
    master_notebook = f"{NOTEBOOK_DIR}/100_data_preprocess_rcbs.ipynb"
    master_nb_out = f"{OUTPUT_DIR}/notebooks/100_data_preprocess_rcbs.ipynb"
    uses_scenarios = False
    scenario_notebook = None
    scenario_nb_out = None
elif active_target_source == "rcb-pathways":
    # Use pathway-based preprocessing with RCB-derived pathways
    master_notebook = f"{NOTEBOOK_DIR}/100_data_preprocess_pathways.ipynb"
    master_nb_out = f"{OUTPUT_DIR}/notebooks/100_data_preprocess_pathways.ipynb"
    uses_scenarios = True
    scenario_notebook = f"{NOTEBOOK_DIR}/106_generate_pathways_from_rcbs.ipynb"
    scenario_nb_out = f"{OUTPUT_DIR}/notebooks/106_generate_pathways_from_rcbs.ipynb"
else:
    # Use scenario-based preprocessing (ar6)
    master_notebook = f"{NOTEBOOK_DIR}/100_data_preprocess_pathways.ipynb"
    master_nb_out = f"{OUTPUT_DIR}/notebooks/100_data_preprocess_pathways.ipynb"
    uses_scenarios = True
    scenario_notebook = (
        f"{NOTEBOOK_DIR}/104_data_preprocess_scenarios_{active_target_source}.ipynb"
    )
    scenario_nb_out = f"{OUTPUT_DIR}/notebooks/104_data_preprocess_scenarios_{active_target_source}.ipynb"

# Helper function to build notebook execution command with common parameters
def notebook_cmd(input_nb, output_nb):
    """Build notebook execution command with standard parameters."""
    return (
        f"uv run run-notebook "
        f"--notebook {input_nb} "
        f"--output {output_nb} "
        f"--param emission_category={emission_category} "
        f"--param active_target_source={active_target_source} "
        f"--param active_emissions_source={active_emissions_source} "
        f"--param active_gdp_source={active_gdp_source} "
        f"--param active_population_source={active_population_source} "
        f"--param active_gini_source={active_gini_source}"
    )


# The default rule: what Snakemake will build if you just run 'snakemake'
rule all:
    input:
        master_notebook=master_nb_out,


# Rule to validate configuration using Pydantic and save to YAML
rule compose_config:
    """
    Validate configuration using Pydantic models and save to YAML file.

    This is the SINGLE SOURCE OF TRUTH for configuration validation.
    All validation logic is in config/models.py (Pydantic).
    The Snakefile only does minimal checks - Pydantic does comprehensive validation.
    """
    output:
        config=f"{OUTPUT_DIR}/config.yaml",
    params:
        emission_category=emission_category,
        active_sources=active_sources_dict,
    run:
        import yaml
        from pathlib import Path
        from fair_shares.library.utils.data.config import build_data_config
        from fair_shares.library.exceptions import ConfigurationError, DataLoadingError

        # Validate configuration through Pydantic (single source of truth)
        # This will raise detailed field-level error messages if validation fails
        try:
            validated_config, source_id = build_data_config(
                emission_category=params.emission_category,
                active_sources=params.active_sources,
                harmonisation_year=None,
            )
        except (ConfigurationError, DataLoadingError, ValueError) as e:
            # Re-raise with clear context that this is a configuration issue
            raise WorkflowError(
                f"Configuration validation failed:\n\n{e}\n\n"
                "Please check your --config parameters and ensure all data sources exist."
            ) from e

        # Convert Pydantic model to dict and save as YAML
        config_dict = validated_config.model_dump()
        Path(output.config).parent.mkdir(parents=True, exist_ok=True)

        with open(output.config, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

        print(f"  ✓ Configuration validated by Pydantic")
        print(f"  ✓ Config saved to: {output.config}")
        print(f"  ✓ Source ID: {source_id}")
        print(f"  ✓ Emission category: {params.emission_category}")
        print(f"  ✓ Active sources: {params.active_sources}")


# Preprocessing rules - one for each data source type
rule preprocess_emiss:
    """Preprocess historical emissions data."""
    input:
        notebook=f"{NOTEBOOK_DIR}/101_data_preprocess_emiss_{active_emissions_source}.ipynb",
        config=f"{OUTPUT_DIR}/config.yaml",
    output:
        notebook=f"{OUTPUT_DIR}/notebooks/101_data_preprocess_emiss_{active_emissions_source}.ipynb",
        emissions_data=f"{OUTPUT_DIR}/intermediate/emissions/emiss_{emission_category}_timeseries.csv",
    shell:
        notebook_cmd("{input.notebook}", "{output.notebook}")


rule preprocess_gdp:
    """Preprocess GDP data (PPP or MER)."""
    input:
        notebook=f"{NOTEBOOK_DIR}/102_data_preprocess_gdp_{active_gdp_source}.ipynb",
        config=f"{OUTPUT_DIR}/config.yaml",
    output:
        notebook=f"{OUTPUT_DIR}/notebooks/102_data_preprocess_gdp_{active_gdp_source}.ipynb",
    shell:
        notebook_cmd("{input.notebook}", "{output.notebook}")


rule preprocess_population:
    """Preprocess population data (historical + projected)."""
    input:
        notebook=f"{NOTEBOOK_DIR}/103_data_preprocess_population_{active_population_source}.ipynb",
        config=f"{OUTPUT_DIR}/config.yaml",
    output:
        notebook=f"{OUTPUT_DIR}/notebooks/103_data_preprocess_population_{active_population_source}.ipynb",
    shell:
        notebook_cmd("{input.notebook}", "{output.notebook}")


rule preprocess_gini:
    """Preprocess Gini coefficient data."""
    input:
        notebook=f"{NOTEBOOK_DIR}/105_data_preprocess_gini_{active_gini_source}.ipynb",
        config=f"{OUTPUT_DIR}/config.yaml",
    output:
        notebook=f"{OUTPUT_DIR}/notebooks/105_data_preprocess_gini_{active_gini_source}.ipynb",
    shell:
        notebook_cmd("{input.notebook}", "{output.notebook}")


# Scenario preprocessing (for ar6) or RCB pathway generation (for rcb-pathways)
if active_target_source == "ar6":

    rule preprocess_quantities:
        """Preprocess scenario data (e.g. AR6 scenarios)."""
        input:
            notebook=scenario_notebook,
            config=f"{OUTPUT_DIR}/config.yaml",
            # Add dependency on emissions data for harmonisation
            emissions_data=f"{OUTPUT_DIR}/intermediate/emissions/emiss_{emission_category}_timeseries.csv",
        output:
            notebook=scenario_nb_out,
        shell:
            notebook_cmd("{input.notebook}", "{output.notebook}")

elif active_target_source == "rcb-pathways":

    rule generate_rcb_pathways:
        """Generate emission pathways from RCB data using exponential decay."""
        input:
            notebook=scenario_notebook,
            config=f"{OUTPUT_DIR}/config.yaml",
            # Emissions data needed to extract world emissions for start value
            emissions_data=f"{OUTPUT_DIR}/intermediate/emissions/emiss_{emission_category}_timeseries.csv",
        output:
            notebook=scenario_nb_out,
            scenarios=f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_{emission_category}_timeseries.csv",
        shell:
            notebook_cmd("{input.notebook}", "{output.notebook}")


# Master preprocessing (combines all data sources)
rule master_preprocess:
    """
    Master preprocessing notebook that combines all data sources.
    Uses 100_data_preprocess_pathways for scenarios or 100_data_preprocess_rcbs for RCBs.
    """
    input:
        notebook=master_notebook,
        config=f"{OUTPUT_DIR}/config.yaml",
        # Dependencies on preprocessing notebooks
        emiss_notebook=f"{OUTPUT_DIR}/notebooks/101_data_preprocess_emiss_{active_emissions_source}.ipynb",
        gdp_notebook=f"{OUTPUT_DIR}/notebooks/102_data_preprocess_gdp_{active_gdp_source}.ipynb",
        population_notebook=f"{OUTPUT_DIR}/notebooks/103_data_preprocess_population_{active_population_source}.ipynb",
        gini_notebook=f"{OUTPUT_DIR}/notebooks/105_data_preprocess_gini_{active_gini_source}.ipynb",
        # Scenarios for pathway allocations only
        future_data_notebook=scenario_nb_out if uses_scenarios else [],
    output:
        notebook=master_nb_out,
    shell:
        notebook_cmd("{input.notebook}", "{output.notebook}")