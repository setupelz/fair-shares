"""
Mathematical utilities for the fair-shares library.

"""

from fair_shares.library.utils.data.transform import (
    broadcast_shares_to_periods,
    filter_time_columns,
)
from fair_shares.library.utils.dataframes import groupby_except_robust
from fair_shares.library.utils.math.adjustments import (
    calculate_capability_adjustment_data,
    calculate_responsibility_adjustment_data,
    calculate_responsibility_adjustment_data_convergence,
)
from fair_shares.library.utils.math.allocation import (
    apply_deviation_constraint,
    apply_gini_adjustment,
    calculate_gini_adjusted_gdp,
    create_gini_lookup_dict,
)
from fair_shares.library.utils.math.convergence import (
    find_minimum_convergence_speed,
    validate_convergence_speed,
)
from fair_shares.library.utils.math.pathways import (
    calculate_exponential_decay_pathway,
    generate_rcb_pathway_scenarios,
)

__all__ = [
    "apply_deviation_constraint",
    "apply_gini_adjustment",
    "broadcast_shares_to_periods",
    "calculate_capability_adjustment_data",
    "calculate_exponential_decay_pathway",
    "calculate_gini_adjusted_gdp",
    "calculate_responsibility_adjustment_data",
    "calculate_responsibility_adjustment_data_convergence",
    "create_gini_lookup_dict",
    "filter_time_columns",
    "find_minimum_convergence_speed",
    "generate_rcb_pathway_scenarios",
    "groupby_except_robust",
    "validate_convergence_speed",
]
