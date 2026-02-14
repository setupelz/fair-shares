"""Data preprocessing modules for fair-shares.

This package contains reusable preprocessing logic extracted from the
100-series data preprocessing notebooks.
"""

from fair_shares.library.preprocessing.config import load_preprocessing_config
from fair_shares.library.preprocessing.coverage import (
    compute_analysis_countries,
    create_coverage_summary,
)
from fair_shares.library.preprocessing.loaders import (
    load_emissions_data,
    load_gdp_data,
    load_gini_data,
    load_population_data,
    load_scenarios_data,
)
from fair_shares.library.preprocessing.rcbs import load_and_process_rcbs
from fair_shares.library.preprocessing.row import add_row_to_datasets
from fair_shares.library.preprocessing.scenarios import process_complete_scenarios

__all__ = [
    "add_row_to_datasets",
    "compute_analysis_countries",
    "create_coverage_summary",
    "load_and_process_rcbs",
    "load_emissions_data",
    "load_gdp_data",
    "load_gini_data",
    "load_population_data",
    "load_preprocessing_config",
    "load_scenarios_data",
    "process_complete_scenarios",
]
