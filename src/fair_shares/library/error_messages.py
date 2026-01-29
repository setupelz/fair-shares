"""
Error message templates for fair shares analysis.

Messages follow WHAT/CAUSE/FIX structure. See docs/science/ for conceptual foundations.
"""

from __future__ import annotations

from difflib import get_close_matches

ERROR_MESSAGES = {
    "empty_dataframe": """
Empty DataFrame provided for {dataset_name}.

WHAT HAPPENED:
  The DataFrame contains no data (zero rows).

LIKELY CAUSE:
  - Data source file is empty or missing
  - Filtering removed all rows
  - Data preprocessing failed silently

HOW TO FIX:
  Check your data source:
  >>> print(f"Rows: {{len(df)}}, Columns: {{len(df.columns)}}")
  >>> print(df.head())

  For data pipeline issues, review preprocessing notebooks to ensure
  data is being loaded and filtered correctly.
""",
    "index_structure_mismatch": """
Data structure error in {dataset_name}.

WHAT HAPPENED:
  The data has the wrong index structure.
  Expected: {expected} (country code and unit columns as index)
  Got: {actual} (current structure)

LIKELY CAUSE:
  The CSV was loaded without setting the index columns.

HOW TO FIX:
  After loading your data, set the index:
  >>> df = df.set_index({expected})
""",
    "year_columns_missing": """
Year columns not detected in {dataset_name}.

WHAT HAPPENED:
  No columns recognized as year columns.
  Year columns must be strings like '2020', not integers like 2020.
  Found columns: {found_columns}

LIKELY CAUSE:
  Your DataFrame has integer year columns (e.g., 2020, 2030)
  but fair-shares requires string year columns ('2020', '2030').

HOW TO FIX:
  Convert year columns to strings:
  >>> from fair_shares.library.utils import ensure_string_year_columns
  >>> df = ensure_string_year_columns(df)
""",
    "weights_exceed_limit": """
Invalid allocation weights.

WHAT HAPPENED:
  responsibility_weight ({resp}) + capability_weight ({cap}) = {total}
  The sum must be <= 1.0

WHY:
  The remaining weight (1.0 - sum) applies to the per-capita component.
  See docs/science/allocations.md#combining-principles for how weights work.

VALID EXAMPLES:
  - responsibility_weight=0.5, capability_weight=0.5 (equal weight to both)
  - responsibility_weight=0.3, capability_weight=0.3 (40% per-capita basis)
  - responsibility_weight=0.5, capability_weight=0.0 (responsibility only)
""",
    "missing_required_data": """
Missing required data for {adjustment_type} adjustment.

WHAT HAPPENED:
  You set {weight_name}={weight_value} but didn't provide {data_name}.

WHY:
  {explanation}
  See docs/science/allocations.md for data requirements.

HOW TO FIX:
  Either:
  1. Provide the required data:
     >>> result = {function_name}(
     ...     {data_param}=your_data_df,  # Add this
     ...     ...
     ... )
  2. Or set {weight_name}=0.0 to exclude this principle from the allocation
""",
    "invalid_target": """
Target '{target}' not recognized.

WHAT HAPPENED:
  The specified target source is not valid.

LIKELY CAUSE:
  Possible typo in the target name.

HOW TO FIX:
  {suggestion}

  Valid target options:
  - 'rcbs': Remaining Carbon Budget Shares (temperature-aligned budget)
  - 'rcb-pathways': RCB-based pathways over time
  - 'ar6': IPCC AR6 scenario pathways
  - 'cr': Climate Resource scenarios

  See docs/science/allocations.md for target options.
""",
    "invalid_emission_category": """
Emission category '{category}' not recognized.

WHAT HAPPENED:
  The specified emission category is not valid for this data source.

LIKELY CAUSE:
  Possible typo or category not available in the selected emissions dataset.

HOW TO FIX:
  {suggestion}

  Common emission categories:
  - 'co2-ffi': CO2 from fossil fuels and industry
  - 'all-ghg-ex-co2-lulucf': All GHGs excluding CO2 from land use
  - 'all-ghg': All greenhouse gases including land use
""",
    "missing_year_range": """
Required years not found in {dataset_name}.

WHAT HAPPENED:
  The dataset doesn't contain all required years.
  Required: {required_years}
  Available: {available_years}
  Missing: {missing_years}

LIKELY CAUSE:
  The data source doesn't cover the full time period needed for this allocation.

  For historical responsibility approaches, start date choice affects
  allocations. See docs/science/allocations.md#historical-responsibility.

HOW TO FIX:
  1. Use a different data source that covers {required_years}
  2. Or adjust your allocation parameters to be within {available_years}
""",
    "negative_values": """
Negative or zero values found in {dataset_name}.

WHAT HAPPENED:
  {value_type} must be positive values.
  Found {count} countries/years with values <= 0.

LIKELY CAUSE:
  Data quality issue or incorrect filtering.

  Note: Negative values may represent carbon sinks (land use change).
  Such entities require special handling in fair share calculations.

HOW TO FIX:
  Check your data for:
  - Missing values (NaN) that should be filtered
  - Countries with zero population (should be excluded)
  - Incorrect unit conversions
  - Carbon sinks that need separate treatment

  Example check:
  >>> print(df[df <= 0])
""",
    "allocation_year_future": """
Allocation year {year} is beyond data coverage.

WHAT HAPPENED:
  You specified allocation_year={year}
  but the data only covers up to {max_year}.

LIKELY CAUSE:
  Typo in the year, or data source doesn't extend far enough.

HOW TO FIX:
  1. Use an allocation year between {min_year} and {max_year}
  2. Or use a different data source with longer coverage
""",
    "infeasible_convergence": """
Cannot achieve convergence targets with current parameters.

WHAT HAPPENED:
  The cumulative per-capita convergence allocation cannot find a feasible solution.

CONTEXT:
  Convergence approaches transition from current emissions toward per capita targets.
  See docs/science/allocations.md#convergence for mechanism details.

LIKELY CAUSE:
  - max_convergence_speed={speed} may be insufficient given the gap between
    current shares and per-capita targets
  - Time horizon ({first_year} to {last_year}) may be too short for gradual
    convergence at the specified rate
  - Initial emissions distributions may be far from population-proportional

HOW TO FIX:
  1. Accept approximate solutions (some parties may not fully converge):
     >>> result = manager.run_allocation(..., strict=False)

  2. Or increase max_convergence_speed (default 0.9, max 1.0):
     >>> result = manager.run_allocation(..., max_convergence_speed=0.95)

  3. Or extend the time horizon (allow more years for gradual transition):
     >>> result = manager.run_allocation(..., first_allocation_year=2020)
""",
    "shares_not_sum_to_one": """
Allocation shares do not sum to 1.0.

WHAT HAPPENED:
  The calculated allocation shares sum to {actual_sum:.6f}, not 1.0.
  Difference: {difference:.6e}

CONTEXT:
  Allocation shares must sum to 1.0 to ensure complete distribution.
  See docs/science/allocations.md#share-normalization for details.

LIKELY CAUSE:
  Numerical precision issue or implementation bug.

HOW TO FIX:
  This is likely a bug. Please report this with:
  - The allocation approach used
  - Parameter values
  - Data shapes and sample values

  As a workaround, you can normalize shares:
  >>> shares_normalized = shares / shares.sum()
""",
}


def format_error(key: str, **kwargs) -> str:
    """
    Format an error message with the given parameters.

    Parameters
    ----------
    key
        The error message key from ERROR_MESSAGES
    **kwargs
        Parameters to format into the message template

    Returns
    -------
    str
        The formatted error message
    """
    template = ERROR_MESSAGES.get(key)
    if template is None:
        return f"Unknown error: {key}"
    return template.format(**kwargs).strip()


def suggest_similar(
    value: str, valid_options: list[str], max_suggestions: int = 3
) -> str:
    """
    Suggest similar valid options for typos.

    Parameters
    ----------
    value
        The invalid value that was provided
    valid_options
        List of valid options to match against
    max_suggestions
        Maximum number of suggestions to return (default: 3)

    Returns
    -------
    str
        A formatted suggestion message
    """
    matches = get_close_matches(value, valid_options, n=max_suggestions, cutoff=0.6)
    if matches:
        return f"Did you mean: {', '.join(matches)}?"
    return f"Valid options: {', '.join(valid_options)}"
