"""
Utility functions for the fair-shares library.

"""

from fair_shares.library.utils.data.completeness import (
    add_row_timeseries,
    get_complete_iso3c_timeseries,
    get_cumulative_budget_from_timeseries,
    get_world_totals_timeseries,
)
from fair_shares.library.utils.data.config import (
    build_data_config,
    build_source_id,
    build_source_id_from_config,
    get_compatible_approaches,
    validate_data_source_config,
)
from fair_shares.library.utils.data.examples import create_example_data
from fair_shares.library.utils.data.iamc import (
    get_available_regions,
    get_available_variables,
    get_year_coverage,
    load_iamc_data,
)
from fair_shares.library.utils.data.parquet_to_csv import convert_parquet_to_wide_csv
from fair_shares.library.utils.data.pipeline import setup_custom_data_pipeline
from fair_shares.library.utils.data.rcb import (
    calculate_budget_from_rcb,
    parse_rcb_scenario,
    process_rcb_to_2020_baseline,
)
from fair_shares.library.utils.data.transform import (
    broadcast_shares_to_periods,
    filter_time_columns,
)
from fair_shares.library.utils.dataframes import (
    convert_country_name_to_iso3c,
    derive_probability_based_categories,
    determine_processing_categories,
    groupby_except_robust,
    normalize_metadata_column,
    normalize_metadata_columns,
    process_iamc_zip,
    set_post_net_zero_emissions_to_nan,
)
from fair_shares.library.utils.math.allocation import (
    apply_deviation_constraint,
    apply_gini_adjustment,
    calculate_gini_adjusted_gdp,
    calculate_relative_adjustment,
    create_gini_lookup_dict,
)
from fair_shares.library.utils.math.pathways import (
    calculate_exponential_decay_pathway,
    generate_rcb_pathway_scenarios,
)
from fair_shares.library.utils.timeseries import (
    harmonize_to_historical_with_convergence,
    interpolate_scenarios_data,
)

from .dataframes import (
    TimeseriesDataFrame,
    ensure_string_year_columns,
    get_year_columns,
)
from .io import generate_parquet_readme
from .units import convert_unit_robust, get_default_unit_registry, set_single_unit

__all__ = [
    "TimeseriesDataFrame",
    "add_row_timeseries",
    "apply_deviation_constraint",
    "apply_gini_adjustment",
    "broadcast_shares_to_periods",
    "build_data_config",
    "build_source_id",
    "build_source_id_from_config",
    "calculate_budget_from_rcb",
    "calculate_exponential_decay_pathway",
    "calculate_gini_adjusted_gdp",
    "calculate_relative_adjustment",
    "convert_country_name_to_iso3c",
    "convert_parquet_to_wide_csv",
    "convert_unit_robust",
    "create_example_data",
    "create_gini_lookup_dict",
    "derive_probability_based_categories",
    "determine_processing_categories",
    "ensure_string_year_columns",
    "filter_time_columns",
    "generate_parquet_readme",
    "generate_rcb_pathway_scenarios",
    "get_available_regions",
    "get_available_variables",
    "get_compatible_approaches",
    "get_complete_iso3c_timeseries",
    "get_cumulative_budget_from_timeseries",
    "get_default_unit_registry",
    "get_world_totals_timeseries",
    "get_year_columns",
    "get_year_coverage",
    "groupby_except_robust",
    "harmonize_to_historical_with_convergence",
    "interpolate_scenarios_data",
    "load_iamc_data",
    "normalize_metadata_column",
    "normalize_metadata_columns",
    "parse_rcb_scenario",
    "process_iamc_zip",
    "process_rcb_to_2020_baseline",
    "set_post_net_zero_emissions_to_nan",
    "set_single_unit",
    "setup_custom_data_pipeline",
    "validate_data_source_config",
]
