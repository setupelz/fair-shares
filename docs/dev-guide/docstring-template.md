# Docstring Template for Allocation Approaches

This template ensures consistent documentation for allocation approaches. See existing implementations in `allocations/budgets/per_capita.py` for examples.

## Required Sections

1. **Summary** - One-line description
2. **Mathematical Foundation** - LaTeX equations showing the allocation formula
3. **Parameters** - All parameters with types and descriptions
4. **Returns** - Description of result object

## Template

```python
def my_new_allocation(
    population_ts: TimeseriesDataFrame,
    allocation_year: int,
    emission_category: str,
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> BudgetAllocationResult:
    r"""
    Short one-line summary of what this approach does.

    Longer description providing context on when to use this approach.

    Mathematical Foundation
    -----------------------

    The allocation is calculated as:

    $$
    A(g) = \frac{P(g, t_a)}{\sum_{g'} P(g', t_a)}
    $$

    Where:

    - $A(g)$: Budget share allocated to country $g$
    - $P(g, t_a)$: Population of country $g$ at allocation year $t_a$

    Parameters
    ----------
    population_ts
        Timeseries of population for each group
    allocation_year
        Year from which to start calculating allocations
    emission_category
        Emission category to include in the output
    group_level
        Level in the index which specifies group information
    unit_level
        Level in the index which specifies the unit of each timeseries
    ur
        The unit registry to use for calculations

    Returns
    -------
    BudgetAllocationResult
        Container with relative shares for cumulative emissions budget allocation.
    """
    pass
```

## Best Practices

### Mathematical Foundation

- Use raw string (`r"""`) for LaTeX equations
- Define all variables used in equations
- For complex approaches, break down the calculation into steps

### Parameters

- Include cross-reference to `parameter-effects.md` for key parameters where relevant
- For adjustment weights, note the direction of effect
- Include valid ranges and defaults

## Validation

Before committing:

1. LaTeX equations render correctly: `uv run mkdocs serve`
2. Parameter types match function signature
3. Look at existing docstrings in `per_capita.py` for reference
