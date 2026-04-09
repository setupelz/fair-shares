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

# Import shared logic from Python modules (single source of truth)
from fair_shares.library.utils.data.config import (
    build_source_id,
    get_emission_preprocessing_categories,
    get_final_categories,
    get_co2_component,
    is_composite_category,
    needs_decomposition,
    ALL_GHG_CO2_CATEGORIES,
)
from fair_shares.library.utils.dataframes import determine_processing_categories

# ---------------------------------------------------------------------------
# Configuration from command line
# ---------------------------------------------------------------------------

emission_category = config.get("emission_category", None)
active_emissions_source = config.get("active_emissions_source", None)
active_gdp_source = config.get("active_gdp_source", None)
active_population_source = config.get("active_population_source", None)
active_gini_source = config.get("active_gini_source", None)
active_lulucf_source = config.get("active_lulucf_source", None)
active_target_source = config.get("active_target_source", None)
rcb_generator = config.get("rcb_generator", None)
harmonisation_year = config.get("harmonisation_year", None)
# Coerce to int if passed as string from Snakemake --config
if harmonisation_year is not None:
    harmonisation_year = int(harmonisation_year)

# Minimal checks — all other validation delegated to Pydantic via compose_config rule
if emission_category is None:
    raise ValueError(
        "Required parameter: emission_category\n"
        "Example: snakemake --config emission_category=co2-ffi "
        "active_emissions_source=primap-202503 active_gdp_source=wdi-2025 "
        "active_population_source=un-owid-2025 active_gini_source=unu-wider-2025 "
        "active_target_source=pathway active_lulucf_source=melo-2026\n\n"
        "For custom allocations, use: notebooks/301_custom_fair_share_allocation.py"
    )

# Active sources dict for Pydantic validation
active_sources_dict = {
    "emissions": active_emissions_source,
    "gdp": active_gdp_source,
    "population": active_population_source,
    "gini": active_gini_source,
    "target": active_target_source,
}
if active_lulucf_source is not None:
    active_sources_dict["lulucf"] = active_lulucf_source
if rcb_generator is not None:
    active_sources_dict["rcb_generator"] = rcb_generator

# ---------------------------------------------------------------------------
# Derived constants (imported logic, not reimplemented)
# ---------------------------------------------------------------------------

# Source ID for output paths — delegates to config.py (single source of truth)
SOURCE_ID = build_source_id(
    emissions=active_emissions_source or "unknown",
    gdp=active_gdp_source or "unknown",
    population=active_population_source or "unknown",
    gini=active_gini_source or "unknown",
    lulucf=active_lulucf_source,
    target=active_target_source or "unknown",
    emission_category=emission_category,
    rcb_generator=rcb_generator,
)

OUTPUT_DIR = f"output/{SOURCE_ID}"
NOTEBOOK_DIR = "notebooks"

# Two category lists drive the pipeline:
#  EMISSION_CATEGORIES — what PRIMAP extraction (notebook 101) produces
#  FINAL_CATEGORIES    — what the allocation loop iterates over
_target = active_target_source or ""
EMISSION_CATEGORIES = get_emission_preprocessing_categories(_target, emission_category)
FINAL_CATEGORIES = get_final_categories(_target, emission_category)
is_multi_category = needs_decomposition(_target, emission_category)

# ---------------------------------------------------------------------------
# Notebook selection — config-driven via allocation_mode and scenario_source
# ---------------------------------------------------------------------------
# Read scenario notebook stem from the scenarios config (not hard-coded).
# Read allocation_mode from the target config to select master notebook.

import yaml as _yaml
with open("conf/data_sources/data_sources_unified.yaml") as _f:
    _full_yaml = _yaml.safe_load(_f)

_target_yaml = _full_yaml["targets"].get(active_target_source, {})

# Infer allocation_mode from target structure (no explicit field needed in YAML)
if _target_yaml.get("allocation_mode"):
    _allocation_mode = _target_yaml["allocation_mode"]
elif not _target_yaml.get("path"):
    _allocation_mode = "pathway"
elif _target_yaml.get("generator"):
    _allocation_mode = "rcb-pathway"
else:
    _allocation_mode = "budget"

# Notebook 107 (LULUCF) is needed only for NGHGI corrections: co2 and all-ghg.
# Bunker data (previously bundled in 107) is now a separate rule below.
_needs_lulucf = emission_category in ("co2", "all-ghg")

# Bunker data is needed for all non-pathway targets (RCBs must subtract
# international bunker emissions before country allocation).
_needs_bunkers = _allocation_mode != "pathway"


if _needs_lulucf and active_lulucf_source is None:
    raise ValueError(
        f"Required parameter: active_lulucf_source\n"
        f"emission_category='{emission_category}' with target='{active_target_source}' "
        f"needs LULUCF preprocessing (NGHGI corrections and/or bunker data).\n"
        f"Example: --config ... active_lulucf_source=melo-2026"
    )

# Resolve scenario source: per-target override → global default
_scenario_source_key = (
    _target_yaml.get("scenario_source")
    or _full_yaml.get("active_scenario_source")
)
_scenario_yaml = _full_yaml.get("scenarios", {}).get(_scenario_source_key, {}) if _scenario_source_key else {}

# Scenario notebook: read from scenarios config (e.g. "104_data_preprocess_scenarios_ar6")
_scenario_nb_stem = _scenario_yaml.get("notebook", "104_data_preprocess_scenarios_ar6")

# Master notebook: budget mode uses 100_rcbs, everything else uses 100_pathways.
MASTER_NOTEBOOKS = {
    "budget": "100_data_preprocess_rcbs",
    "pathway": "100_data_preprocess_pathways",
    "rcb-pathway": "100_data_preprocess_pathways",
}

master_stem = MASTER_NOTEBOOKS.get(_allocation_mode, "100_data_preprocess_pathways")
master_notebook = f"{NOTEBOOK_DIR}/{master_stem}.ipynb"
master_nb_out = f"{OUTPUT_DIR}/notebooks/{master_stem}.ipynb"

# For rcb-pathways: the final scenario output comes from 106 (pathway generation),
# but 104 (scenario preprocessing) must run first to produce adjustment scalars.
# For all other targets: the scenario notebook is 104 directly.
if _allocation_mode == "rcb-pathway":
    scenario_stem = "106_generate_pathways_from_rcbs"
else:
    scenario_stem = _scenario_nb_stem

uses_scenarios = _scenario_source_key is not None
scenario_notebook = f"{NOTEBOOK_DIR}/{scenario_stem}.ipynb" if uses_scenarios else None
scenario_nb_out = f"{OUTPUT_DIR}/notebooks/{scenario_stem}.ipynb" if uses_scenarios else None

# For decomposition runs, non-CO2 always uses scenario data regardless of CO2 target
if is_multi_category and not uses_scenarios:
    uses_scenarios = True
    scenario_notebook = f"{NOTEBOOK_DIR}/{_scenario_nb_stem}.ipynb"
    scenario_nb_out = f"{OUTPUT_DIR}/notebooks/{_scenario_nb_stem}.ipynb"

# Categories for which the scenario notebook must run.
# Decomposition runs need scenarios for derivation source categories;
# rcb-pathways additionally needs a CO2 pathway from notebook 106.
if is_multi_category:
    SCENARIO_CATEGORIES = ("co2-ffi", "all-ghg-ex-co2-lulucf")
    if _allocation_mode == "rcb-pathway":
        co2_comp = get_co2_component(emission_category)
        if co2_comp not in SCENARIO_CATEGORIES:
            SCENARIO_CATEGORIES = (co2_comp,) + SCENARIO_CATEGORIES
else:
    SCENARIO_CATEGORIES = FINAL_CATEGORIES

# For rcb-pathway decomposition, the scenario notebook runs for each
# SCENARIO_CATEGORIES entry.  Each run may produce multiple CSVs (e.g.
# co2 → co2, co2-ffi, co2-lulucf).  Compute the full set from the scenario
# source's available_categories so the Snakefile declares exactly what will
# be created — works for AR6, SCI, or any future scenario source.
_SCENARIO_SUPPORTED = _scenario_yaml.get("data_parameters", {}).get(
    "available_categories", []
)
_SCENARIO_NB_ALL_OUTPUTS = set()
if is_multi_category and _allocation_mode == "rcb-pathway":
    for _cat in SCENARIO_CATEGORIES:
        _info = determine_processing_categories(_cat, _SCENARIO_SUPPORTED)
        _SCENARIO_NB_ALL_OUTPUTS.update(_info["final"])
    # The CO2 component CSV is owned by rule 2 (notebook 106) — exclude it here.
    _SCENARIO_NB_ALL_OUTPUTS.discard(get_co2_component(emission_category))

# ---------------------------------------------------------------------------
# Helper: build notebook execution command
# ---------------------------------------------------------------------------

def notebook_cmd_list(input_nb, output_nb, emission_category_override=None,
                      alignment_categories=None):
    """Build notebook execution command as list (for subprocess.run in run: blocks).

    Uses emission_category_override if given, otherwise the global emission_category.
    alignment_categories: comma-separated string of ALL categories for country alignment
    (used in decomposition to ensure consistent analysis_countries across passes).
    """
    cat = emission_category_override or emission_category
    cmd = [
        "uv", "run", "run-notebook",
        "--notebook", input_nb,
        "--output", output_nb,
        "--param", f"emission_category={cat}",
        "--param", f"active_target_source={active_target_source}",
        "--param", f"active_emissions_source={active_emissions_source}",
        "--param", f"active_gdp_source={active_gdp_source}",
        "--param", f"active_population_source={active_population_source}",
        "--param", f"active_gini_source={active_gini_source}",
        "--param", f"source_id={SOURCE_ID}",
    ]
    if active_lulucf_source is not None:
        cmd += ["--param", f"active_lulucf_source={active_lulucf_source}"]
    if alignment_categories is not None:
        cmd += ["--param", f"alignment_categories={alignment_categories}"]
    if _scenario_source_key is not None:
        cmd += ["--param", f"active_scenario_source={_scenario_source_key}"]
    return cmd

def notebook_cmd(input_nb, output_nb):
    """Build notebook execution command with standard parameters (shell string)."""
    return " ".join(notebook_cmd_list(input_nb, output_nb))


# ===========================================================================
# Rules
# ===========================================================================

rule all:
    input:
        master_notebook=master_nb_out,


rule compose_config:
    """Validate configuration using Pydantic models and save to YAML file.

    This is the SINGLE SOURCE OF TRUTH for configuration validation.
    All validation logic is in config/models.py (Pydantic).
    The Snakefile only does minimal checks — Pydantic does comprehensive validation.
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

        try:
            validated_config, source_id = build_data_config(
                emission_category=params.emission_category,
                active_sources=params.active_sources,
                harmonisation_year=harmonisation_year,
            )
        except (ConfigurationError, DataLoadingError, ValueError) as e:
            raise WorkflowError(
                f"Configuration validation failed:\n\n{e}\n\n"
                "Please check your --config parameters and ensure all data sources exist."
            ) from e

        config_dict = validated_config.model_dump()
        Path(output.config).parent.mkdir(parents=True, exist_ok=True)

        with open(output.config, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

        print(f"  [OK] Configuration validated by Pydantic")
        print(f"  [OK] Config saved to: {output.config}")
        print(f"  [OK] Source ID: {source_id}")
        print(f"  [OK] Emission category: {params.emission_category}")
        print(f"  [OK] Active sources: {params.active_sources}")


# ---------------------------------------------------------------------------
# Preprocessing rules — one per data source type
# ---------------------------------------------------------------------------

# Emissions: single-category runs produce one file; decomposition runs produce
# one file per PRIMAP source category by running the same notebook multiple times.
rule preprocess_emiss:
    """Preprocess historical emissions data.

    For decomposition runs, executes once per PRIMAP source category
    (e.g. co2-ffi, co2, co2-lulucf, all-ghg-ex-co2-lulucf) to produce
    separate timeseries files needed for non-CO2 derivation.
    """
    input:
        notebook=f"{NOTEBOOK_DIR}/101_data_preprocess_emiss_{active_emissions_source}.ipynb",
        config=f"{OUTPUT_DIR}/config.yaml",
    output:
        notebook=f"{OUTPUT_DIR}/notebooks/101_data_preprocess_emiss_{active_emissions_source}.ipynb",
        emissions_data=expand(
            f"{OUTPUT_DIR}/intermediate/emissions/emiss_{{cat}}_timeseries.csv",
            cat=EMISSION_CATEGORIES,
        ),
    run:
        import subprocess
        for cat in EMISSION_CATEGORIES:
            print(f"[preprocessing] Running emissions notebook for emission_category={cat}")
            subprocess.run(
                notebook_cmd_list(input.notebook, output.notebook, cat),
                check=True,
            )


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


if _needs_lulucf:

    rule preprocess_lulucf:
        """Preprocess LULUCF data (NGHGI-consistent categories).

        Runs notebook 107 after notebook 101 to produce NGHGI-consistent
        co2-lulucf, co2, non-co2, all-ghg, and all-ghg-ex-co2-lulucf.
        Overwrites the PRIMAP BM co2-lulucf with Melo NGHGI data.
        """
        input:
            notebook=f"{NOTEBOOK_DIR}/107_data_preprocess_lulucf_{active_lulucf_source}.ipynb",
            config=f"{OUTPUT_DIR}/config.yaml",
            emiss_notebook=f"{OUTPUT_DIR}/notebooks/101_data_preprocess_emiss_{active_emissions_source}.ipynb",
        output:
            notebook=f"{OUTPUT_DIR}/notebooks/107_data_preprocess_lulucf_{active_lulucf_source}.ipynb",
            nghgi_world=f"{OUTPUT_DIR}/intermediate/emissions/world_co2-lulucf_timeseries.csv",
            nghgi_metadata=f"{OUTPUT_DIR}/intermediate/emissions/lulucf_metadata.yaml",
        shell:
            notebook_cmd("{input.notebook}", "{output.notebook}")


if _needs_bunkers:

    rule preprocess_bunkers:
        """Extract international bunker fuel CO2 from GCB data.

        Bunker emissions are subtracted from global RCBs before country
        allocation.  Independent of LULUCF — uses GCB fossil emissions data.
        """
        input:
            notebook=f"{NOTEBOOK_DIR}/108_data_preprocess_bunkers_gcb-2024.ipynb",
            config=f"{OUTPUT_DIR}/config.yaml",
        output:
            notebook=f"{OUTPUT_DIR}/notebooks/108_data_preprocess_bunkers_gcb-2024.ipynb",
            bunker_csv=f"{OUTPUT_DIR}/intermediate/emissions/bunker_timeseries.csv",
        shell:
            notebook_cmd("{input.notebook}", "{output.notebook}")


# ---------------------------------------------------------------------------
# Scenario / pathway preprocessing
# ---------------------------------------------------------------------------
# For rcbs (non-composite): no scenario rule needed — budgets only.
# For rcb-pathways / pathway (non-composite): one scenario notebook run.
# For decomposition: per-category scenario runs over SCENARIO_CATEGORIES with
#   target-aware notebook selection (CO2 component from target, rest from AR6).

if uses_scenarios:

    if not is_multi_category:
        # Single-category scenario preprocessing
        if _allocation_mode == "rcb-pathway":

            rule preprocess_scenarios_for_rcb_pathways:
                """Run scenario notebook to produce adjustment scalars needed by 106."""
                input:
                    notebook=f"{NOTEBOOK_DIR}/{_scenario_nb_stem}.ipynb",
                    config=f"{OUTPUT_DIR}/config.yaml",
                    emissions_data=f"{OUTPUT_DIR}/intermediate/emissions/emiss_{emission_category}_timeseries.csv",
                    lulucf_notebook=(f"{OUTPUT_DIR}/notebooks/107_data_preprocess_lulucf_{active_lulucf_source}.ipynb" if _needs_lulucf else []),
                output:
                    notebook=f"{OUTPUT_DIR}/notebooks/{_scenario_nb_stem}.ipynb",
                    adjustments=f"{OUTPUT_DIR}/intermediate/scenarios/rcb_scenario_adjustments.yaml",
                shell:
                    notebook_cmd("{input.notebook}", "{output.notebook}")

            rule generate_rcb_pathways:
                """Generate emission pathways from RCB data using exponential decay."""
                input:
                    notebook=scenario_notebook,
                    config=f"{OUTPUT_DIR}/config.yaml",
                    emissions_data=f"{OUTPUT_DIR}/intermediate/emissions/emiss_{emission_category}_timeseries.csv",
                    lulucf_notebook=(f"{OUTPUT_DIR}/notebooks/107_data_preprocess_lulucf_{active_lulucf_source}.ipynb" if _needs_lulucf else []),
                    bunker_csv=(f"{OUTPUT_DIR}/intermediate/emissions/bunker_timeseries.csv" if _needs_bunkers else []),
                    scenario_adjustments=f"{OUTPUT_DIR}/intermediate/scenarios/rcb_scenario_adjustments.yaml",
                output:
                    notebook=scenario_nb_out,
                    scenarios=f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_{emission_category}_timeseries.csv",
                shell:
                    notebook_cmd("{input.notebook}", "{output.notebook}")

        else:
            # pathway or budget mode — run scenario notebook directly
            rule preprocess_scenarios:
                """Preprocess scenario data from configured source."""
                input:
                    notebook=scenario_notebook,
                    config=f"{OUTPUT_DIR}/config.yaml",
                    emissions_data=f"{OUTPUT_DIR}/intermediate/emissions/emiss_{emission_category}_timeseries.csv",
                output:
                    notebook=scenario_nb_out,
                    scenarios=f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_{emission_category}_timeseries.csv",
                shell:
                    notebook_cmd("{input.notebook}", "{output.notebook}")

    else:
        # Decomposition: per-category scenario runs over SCENARIO_CATEGORIES.
        # CO2 component uses target-appropriate notebook; derivation sources use scenario notebook.
        _co2_comp = get_co2_component(emission_category)

        # For rcb-pathway mode, the scenario notebook must run first (produces adjustment
        # scalars that 106 needs). Declare it as a separate rule so the DAG tracks it.
        if _allocation_mode == "rcb-pathway":

            rule preprocess_scenarios_for_decomposition:
                """Run scenario notebook to produce adjustment scalars needed by 106 in decomposition."""
                input:
                    notebook=f"{NOTEBOOK_DIR}/{_scenario_nb_stem}.ipynb",
                    config=f"{OUTPUT_DIR}/config.yaml",
                    emissions_data=expand(
                        f"{OUTPUT_DIR}/intermediate/emissions/emiss_{{cat}}_timeseries.csv",
                        cat=SCENARIO_CATEGORIES,
                    ),
                    lulucf_notebook=(f"{OUTPUT_DIR}/notebooks/107_data_preprocess_lulucf_{active_lulucf_source}.ipynb" if _needs_lulucf else []),
                output:
                    notebook=f"{OUTPUT_DIR}/notebooks/{_scenario_nb_stem}.ipynb",
                    adjustments=f"{OUTPUT_DIR}/intermediate/scenarios/rcb_scenario_adjustments.yaml",
                    # Declare all scenario CSVs that notebook 104 produces
                    # (computed via determine_processing_categories, excluding
                    # the CO2 component which rule 2 owns via notebook 106).
                    derivation_scenarios=expand(
                        f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_{{cat}}_timeseries.csv",
                        cat=sorted(_SCENARIO_NB_ALL_OUTPUTS),
                    ),
                    # non-co2 derived here (before rule 2 overwrites co2-ffi with RCB sources)
                    non_co2_scenarios=f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_non-co2_timeseries.csv",
                run:
                    import subprocess
                    from pathlib import Path

                    scenario_nb = f"{NOTEBOOK_DIR}/{_scenario_nb_stem}.ipynb"

                    # Run 104 for all SCENARIO_CATEGORIES.  The CO2 component run
                    # produces NGHGI sub-components (co2-lulucf) that the master
                    # notebook needs.  Its scenarios_{co2_comp}_timeseries.csv is an
                    # undeclared side-effect — harmless, overwritten by 106 in rule 2.
                    for cat in SCENARIO_CATEGORIES:
                        print(f"[decomposition/scenarios] Running {Path(scenario_nb).stem} for emission_category={cat}")
                        subprocess.run(
                            notebook_cmd_list(scenario_nb, output.notebook, cat),
                            check=True,
                        )

                    # Derive non-co2 scenarios NOW, while co2-ffi still has AR6 source
                    # labels (from 104).  Rule 2 overwrites co2-ffi with RCB sources
                    # (e.g. lamboll_2023) which would cause a source-index mismatch.
                    from fair_shares.library.utils import ensure_string_year_columns
                    from fair_shares.library.utils.data.non_co2 import derive_non_co2_world_scenarios
                    import pandas as _pd

                    _scen_dir = Path(f"{OUTPUT_DIR}/intermediate/scenarios")
                    _idx = ["climate-assessment", "quantile", "source", "iso3c", "unit", "emission-category"]
                    _ffi = _pd.read_csv(_scen_dir / "scenarios_co2-ffi_timeseries.csv").set_index(_idx)
                    _ffi = ensure_string_year_columns(_ffi)
                    _ghg = _pd.read_csv(_scen_dir / "scenarios_all-ghg-ex-co2-lulucf_timeseries.csv").set_index(_idx)
                    _ghg = ensure_string_year_columns(_ghg)
                    _nc = derive_non_co2_world_scenarios(_ghg, _ffi)
                    _nc.reset_index().to_csv(output.non_co2_scenarios, index=False)
                    print(f"[decomposition/scenarios] Derived non-co2 scenarios: {len(_nc)} rows")

        rule preprocess_decomposition_scenarios:
            """Preprocess scenario data for decomposition runs.

            Per-category notebook selection:
              - CO2 component: target-appropriate notebook (rcb-pathway -> 106, others -> scenario nb)
              - Derivation sources: always scenario notebook

            For rcb-pathway, scenario notebook runs first via preprocess_scenarios_for_decomposition.
            This rule then only runs 106 for the CO2 component.
            """
            input:
                notebook=scenario_notebook,
                config=f"{OUTPUT_DIR}/config.yaml",
                emissions_data=expand(
                    f"{OUTPUT_DIR}/intermediate/emissions/emiss_{{cat}}_timeseries.csv",
                    cat=SCENARIO_CATEGORIES,
                ),
                lulucf_notebook=(f"{OUTPUT_DIR}/notebooks/107_data_preprocess_lulucf_{active_lulucf_source}.ipynb" if _needs_lulucf else []),
                bunker_csv=(f"{OUTPUT_DIR}/intermediate/emissions/bunker_timeseries.csv" if _needs_bunkers else []),
                scenario_adjustments=(
                    f"{OUTPUT_DIR}/intermediate/scenarios/rcb_scenario_adjustments.yaml"
                    if _allocation_mode == "rcb-pathway" else []
                ),
            output:
                notebook=scenario_nb_out,
                # In rcb-pathway mode, notebook 104 already produced the derivation-
                # source CSVs (declared by preprocess_scenarios_for_decomposition).
                # This rule only runs notebook 106 for the CO2 component.
                scenarios=(
                    [f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_{_co2_comp}_timeseries.csv"]
                    if _allocation_mode == "rcb-pathway"
                    else expand(
                        f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_{{cat}}_timeseries.csv",
                        cat=SCENARIO_CATEGORIES,
                    )
                ),
            run:
                import subprocess
                from pathlib import Path

                scenario_nb = f"{NOTEBOOK_DIR}/{_scenario_nb_stem}.ipynb"

                if _allocation_mode == "rcb-pathway":
                    # Scenario notebook already ran via preprocess_scenarios_for_decomposition.
                    # Only run 106 for the CO2 component.
                    co2_nb = f"{NOTEBOOK_DIR}/106_generate_pathways_from_rcbs.ipynb"
                    print(f"[decomposition/rcb-pathway] Running {Path(co2_nb).stem} for emission_category={_co2_comp}")
                    subprocess.run(
                        notebook_cmd_list(co2_nb, output.notebook, _co2_comp),
                        check=True,
                    )
                else:
                    # pathway or budget mode: run scenario notebook for all categories
                    for cat in SCENARIO_CATEGORIES:
                        print(f"[decomposition/scenarios] Running {Path(scenario_nb).stem} for emission_category={cat}")
                        subprocess.run(
                            notebook_cmd_list(scenario_nb, output.notebook, cat),
                            check=True,
                        )


# ---------------------------------------------------------------------------
# Non-CO2 derivation (decomposition runs only)
# ---------------------------------------------------------------------------
# non-co2 = all-ghg-ex-co2-lulucf − co2-ffi
# Simple subtraction, runs after emissions and scenarios are preprocessed.
# Creates the intermediate files that the pathways master notebook expects.

if is_multi_category:

    rule derive_non_co2_emissions:
        """Derive non-CO2 historical emissions by subtraction."""
        input:
            co2_ffi=f"{OUTPUT_DIR}/intermediate/emissions/emiss_co2-ffi_timeseries.csv",
            allghg_ex=f"{OUTPUT_DIR}/intermediate/emissions/emiss_all-ghg-ex-co2-lulucf_timeseries.csv",
        output:
            non_co2=f"{OUTPUT_DIR}/intermediate/emissions/emiss_non-co2_timeseries.csv",
        run:
            import pandas as pd
            from fair_shares.library.utils import ensure_string_year_columns
            from fair_shares.library.utils.data.non_co2 import derive_non_co2_country_timeseries

            co2_ffi = pd.read_csv(input.co2_ffi).set_index(["iso3c", "unit", "emission-category"])
            co2_ffi = ensure_string_year_columns(co2_ffi)
            allghg_ex = pd.read_csv(input.allghg_ex).set_index(["iso3c", "unit", "emission-category"])
            allghg_ex = ensure_string_year_columns(allghg_ex)

            non_co2 = derive_non_co2_country_timeseries(allghg_ex, co2_ffi)
            non_co2.reset_index().to_csv(output.non_co2, index=False)
            print(f"[derive] non-co2 emissions: {len(non_co2)} rows")


    # For rcb-pathway, non-co2 scenarios are derived inside
    # preprocess_scenarios_for_decomposition (before 106 overwrites co2-ffi).
    if _allocation_mode != "rcb-pathway":

        rule derive_non_co2_scenarios:
            """Derive non-CO2 scenarios by subtraction."""
            input:
                co2_ffi=f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_co2-ffi_timeseries.csv",
                allghg_ex=f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_all-ghg-ex-co2-lulucf_timeseries.csv",
            output:
                non_co2=f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_non-co2_timeseries.csv",
            run:
                import pandas as pd
                from fair_shares.library.utils import ensure_string_year_columns
                from fair_shares.library.utils.data.non_co2 import derive_non_co2_world_scenarios

                idx_cols = ["climate-assessment", "quantile", "source", "iso3c", "unit", "emission-category"]

                co2_ffi = pd.read_csv(input.co2_ffi).set_index(idx_cols)
                co2_ffi = ensure_string_year_columns(co2_ffi)
                allghg_ex = pd.read_csv(input.allghg_ex).set_index(idx_cols)
                allghg_ex = ensure_string_year_columns(allghg_ex)

                non_co2 = derive_non_co2_world_scenarios(allghg_ex, co2_ffi)
                non_co2.reset_index().to_csv(output.non_co2, index=False)
                print(f"[derive] non-co2 scenarios: {len(non_co2)} rows")


# ---------------------------------------------------------------------------
# Master preprocessing (combines all data sources)
# ---------------------------------------------------------------------------
# Non-decomposition: single notebook run (includes AR6 + composite).
# Decomposition (RCB targets + composite): per-category runs over FINAL_CATEGORIES;
# CO2 uses target-appropriate master, non-CO2 uses 100_pathways with derived data.

rule master_preprocess:
    """Master preprocessing notebook that combines all data sources.

    For decomposition runs, executes per sub-category:
      - CO2 component: target-appropriate master (100_rcbs or 100_pathways)
      - non-co2: 100_pathways using derived non-co2 emissions and scenarios
    """
    input:
        notebook=master_notebook,
        config=f"{OUTPUT_DIR}/config.yaml",
        emiss_notebook=f"{OUTPUT_DIR}/notebooks/101_data_preprocess_emiss_{active_emissions_source}.ipynb",
        lulucf_notebook=(f"{OUTPUT_DIR}/notebooks/107_data_preprocess_lulucf_{active_lulucf_source}.ipynb" if _needs_lulucf else []),
        bunker_csv=(f"{OUTPUT_DIR}/intermediate/emissions/bunker_timeseries.csv" if _needs_bunkers else []),
        gdp_notebook=f"{OUTPUT_DIR}/notebooks/102_data_preprocess_gdp_{active_gdp_source}.ipynb",
        population_notebook=f"{OUTPUT_DIR}/notebooks/103_data_preprocess_population_{active_population_source}.ipynb",
        gini_notebook=f"{OUTPUT_DIR}/notebooks/105_data_preprocess_gini_{active_gini_source}.ipynb",
        future_data_notebook=scenario_nb_out if uses_scenarios else [],
        non_co2_data=[
            f"{OUTPUT_DIR}/intermediate/emissions/emiss_non-co2_timeseries.csv",
            f"{OUTPUT_DIR}/intermediate/scenarios/scenarios_non-co2_timeseries.csv",
        ] if is_multi_category else [],
    output:
        notebook=master_nb_out,
    run:
        import subprocess

        if not is_multi_category:
            # Single category or pathway composite: one run
            subprocess.run(
                notebook_cmd_list(input.notebook, output.notebook),
                check=True,
            )
        else:
            # Decomposition: iterate over FINAL_CATEGORIES (co2-component + non-co2).
            # All passes share the same alignment_categories so that
            # analysis_countries is the intersection across ALL categories —
            # prevents the second pass from overwriting GDP/pop/gini with a
            # different country set than the first pass.
            pathways_nb = f"{NOTEBOOK_DIR}/100_data_preprocess_pathways.ipynb"

            # Compute ALL emission categories across all passes
            _all_align_cats = set()
            for _c in FINAL_CATEGORIES:
                _info = determine_processing_categories(
                    _c, _SCENARIO_SUPPORTED or list(EMISSION_CATEGORIES)
                )
                _all_align_cats.update(_info["final"])
            _align_str = ",".join(sorted(_all_align_cats))

            for cat in FINAL_CATEGORIES:
                # CO2 component uses the target-appropriate master notebook;
                # non-co2 uses pathways master (derived data already exists)
                if cat in ALL_GHG_CO2_CATEGORIES:
                    nb_in = input.notebook
                    nb_out = output.notebook
                else:
                    nb_in = pathways_nb
                    nb_out = f"{OUTPUT_DIR}/notebooks/100_data_preprocess_pathways_nonco2.ipynb"

                print(f"[decomposition] Running master notebook for emission_category={cat}")
                subprocess.run(
                    notebook_cmd_list(nb_in, nb_out, cat,
                                     alignment_categories=_align_str),
                    check=True,
                )
