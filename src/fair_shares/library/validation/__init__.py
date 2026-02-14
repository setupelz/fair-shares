"""
Validation for the fair-shares library.

"""

from .allocation_validation import (
    validate_allocation_inputs,
    validate_emission_category_match,
    validate_emissions_data,
    validate_gdp_data,
    validate_gini_data,
    validate_gini_range,
    validate_population_data,
    validate_scenarios_data,
    validate_single_emission_category,
    validate_world_data_present,
    validate_years_match,
)
from .config import (
    validate_allocation_approach,
    validate_allocation_parameters,
    validate_allocation_years_against_harmonisation,
    validate_function_parameters,
    validate_target_source_compatibility,
)
from .convergence import (
    validate_adjustment_data_requirements,
    validate_country_data_present,
    validate_country_world_consistency,
    validate_share_calculation,
    validate_sufficient_time_horizon,
    validate_weights,
    validate_world_emissions_present,
    validate_world_weights_aligned,
)
from .convergence import (
    validate_emissions_data as validate_convergence_emissions_data,
)
from .convergence import (
    validate_year_in_data as validate_convergence_year_in_data,
)
from .inputs import (
    validate_has_year_columns,
    validate_index_structure,
    validate_no_null_values,
    validate_stationary_dataframe,
)
from .models import AllocationInputs, AllocationOutputs
from .outputs import (
    validate_exactly_one_year_column,
    validate_shares_sum_to_one,
)
from .pipeline_validation import (
    validate_all_datasets_totals,
    validate_dataset_totals,
    validate_incremental_annual_timeseries,
    validate_paths,
    validate_positive_values,
    validate_timeseries_values,
    validate_year_in_data,
)

__all__ = [
    # Pydantic models
    "AllocationInputs",
    "AllocationOutputs",
    # Pipeline validation
    "validate_all_datasets_totals",
    # Config validation
    "validate_allocation_approach",
    # Allocation validation
    "validate_allocation_inputs",
    "validate_allocation_parameters",
    "validate_allocation_years_against_harmonisation",
    "validate_dataset_totals",
    "validate_emission_category_match",
    "validate_emissions_data",
    # Output validation
    "validate_exactly_one_year_column",
    "validate_function_parameters",
    "validate_gdp_data",
    "validate_gini_data",
    "validate_gini_range",
    # Input validation
    "validate_has_year_columns",
    "validate_incremental_annual_timeseries",
    "validate_index_structure",
    "validate_no_null_values",
    "validate_paths",
    "validate_population_data",
    "validate_positive_values",
    "validate_scenarios_data",
    "validate_shares_sum_to_one",
    "validate_single_emission_category",
    "validate_stationary_dataframe",
    "validate_target_source_compatibility",
    "validate_timeseries_values",
    "validate_world_data_present",
    "validate_year_in_data",
    "validate_years_match",
    # Convergence validation
    "validate_adjustment_data_requirements",
    "validate_convergence_emissions_data",
    "validate_convergence_year_in_data",
    "validate_country_data_present",
    "validate_country_world_consistency",
    "validate_share_calculation",
    "validate_sufficient_time_horizon",
    "validate_weights",
    "validate_world_emissions_present",
    "validate_world_weights_aligned",
]
