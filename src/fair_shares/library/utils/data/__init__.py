"""
Data processing utilities for the fair-shares library.

"""

# Import from consolidated dataframes module
from fair_shares.library.utils.dataframes import (
    derive_probability_based_categories,
    determine_processing_categories,
    normalize_metadata_column,
    normalize_metadata_columns,
    process_iamc_zip,
    set_post_net_zero_emissions_to_nan,
)

# IO module moved to utils.io
from fair_shares.library.utils.io import generate_parquet_readme

# Scenarios module moved to timeseries
from fair_shares.library.utils.timeseries import (
    _apply_cumulative_preservation_scaling,
    harmonize_to_historical_with_convergence,
    interpolate_scenarios_data,
)

from .completeness import (
    add_row_timeseries,
    get_complete_iso3c_timeseries,
    get_cumulative_budget_from_timeseries,
    get_world_totals_timeseries,
)

# New config module - preferred import location
from .config import (
    build_data_config,
    build_source_id,
    build_source_id_from_config,
    get_compatible_approaches,
    validate_data_source_config,
)

# Convergence data processing module
from .convergence import (
    build_result_dataframe,
    calculate_initial_shares,
    process_emissions_data,
    process_population_data,
    process_world_scenario_data,
)

# New IAMC module - IAMC data format adapter
from .iamc import (
    get_available_regions,
    get_available_variables,
    get_year_coverage,
    load_iamc_data,
)

# New pipeline module - preferred import location
from .pipeline import (
    build_data_paths,
    execute_snakemake_setup,
    generate_snakemake_command,
    setup_custom_data_pipeline,
    verify_data_setup,
)

# New RCB module - preferred import location
from .rcb import (
    calculate_budget_from_rcb,
    parse_rcb_scenario,
    process_rcb_to_2020_baseline,
)

# New transform module - preferred import location
from .transform import (
    broadcast_shares_to_periods,
    expand_to_annual,
    filter_time_columns,
)

__all__ = [
    "_apply_cumulative_preservation_scaling",
    "add_row_timeseries",
    "broadcast_shares_to_periods",
    "build_data_config",
    "build_data_paths",
    "build_result_dataframe",
    "build_source_id",
    "build_source_id_from_config",
    "calculate_budget_from_rcb",
    "calculate_initial_shares",
    "derive_probability_based_categories",
    "determine_processing_categories",
    "execute_snakemake_setup",
    "expand_to_annual",
    "filter_time_columns",
    "generate_parquet_readme",
    "generate_snakemake_command",
    "get_available_regions",
    "get_available_variables",
    "get_compatible_approaches",
    "get_complete_iso3c_timeseries",
    "get_cumulative_budget_from_timeseries",
    "get_world_totals_timeseries",
    "get_year_coverage",
    "harmonize_to_historical_with_convergence",
    "interpolate_scenarios_data",
    "load_iamc_data",
    "normalize_metadata_column",
    "normalize_metadata_columns",
    "parse_rcb_scenario",
    "process_emissions_data",
    "process_iamc_zip",
    "process_population_data",
    "process_rcb_to_2020_baseline",
    "process_world_scenario_data",
    "set_post_net_zero_emissions_to_nan",
    "setup_custom_data_pipeline",
    "validate_data_source_config",
    "verify_data_setup",
]
