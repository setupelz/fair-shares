# Docstring Template for Allocation Approaches

This template ensures consistent, comprehensive documentation for all allocation approaches in Fair Shares.

## Complete Template

```python
def my_new_allocation(
    population_ts: TimeseriesDataFrame,
    allocation_year: int,  # or first_allocation_year for pathways
    emission_category: str,
    # ... additional parameters
    group_level: str = "iso3c",
    unit_level: str = "unit",
    ur: pint.facets.PlainRegistry = get_default_unit_registry(),
) -> BudgetAllocationResult:  # or PathwayAllocationResult
    r"""
    Short one-line summary of what this approach does.

    Longer description providing context on when to use this approach and
    what equity principles it operationalizes. This should help users choose
    between approaches based on their normative commitments.

    Equity Principles Operationalized
    ----------------------------------

    [Describe which equity principles this approach implements and how. Consider
    principles like equal rights to atmosphere, CBDR-RC, capability, historical
    responsibility, etc. Check docs/science/climate-equity-concepts.md and
    docs/science/allocations.md for existing principles. If this approach doesn't
    align with documented principles, suggest adding new ones to the conceptual
    framework.

    Include the key normative choice - what value judgment does this approach make?
    Link to relevant sections in docs/science/principle-to-code.md.]

    Mathematical Foundation
    -----------------------

    The allocation is calculated as:

    $$
    A(g) = \frac{\text{metric}(g)}{\sum_{g'} \text{metric}(g')}
    $$

    Where:

    - $A(g)$: Budget/pathway share allocated to country $g$
    - $\text{metric}(g)$: The metric used for allocation (e.g., population,
      adjusted population, historical emissions)
    - $\sum_{g'} \text{metric}(g')$: Sum of metric across all countries

    [For complex approaches, provide additional mathematical detail showing
    how adjustments are calculated. Use LaTeX notation for equations.]

    Parameters
    ----------
    population_ts : TimeseriesDataFrame
        Timeseries of population for each country with MultiIndex (iso3c, unit).
        Required for all per capita approaches.
    allocation_year : int
        [For budget approaches] Year from which to start calculating allocations.
        Earlier years account for more historical emissions.
        See docs/science/parameter-effects.md#allocation_year for how this
        affects country shares.
    first_allocation_year : int
        [For pathway approaches] First year of the allocation period.
        See docs/science/parameter-effects.md#first_allocation_year.
    last_allocation_year : int
        [For pathway approaches] Last year of the allocation period.
    emission_category : str
        Emission category to include in the output (e.g., "co2-ffi", "kyoto-ghg").
    responsibility_weight : float, optional
        Weight for historical responsibility adjustment (0.0 to 1.0).
        Higher values reduce allocation for countries with higher historical emissions.
        See docs/science/parameter-effects.md#responsibility_weight.
    capability_weight : float, optional
        Weight for economic capability adjustment (0.0 to 1.0).
        Higher values reduce allocation for wealthier countries.
        See docs/science/parameter-effects.md#capability_weight.
    income_floor : float, optional
        Income level (USD/capita/year) below which no capability adjustment
        is applied. Protects subsistence emissions.
        See docs/science/parameter-effects.md#income_floor.
    [... other parameters with types, descriptions, and cross-references]
    group_level : str, default="iso3c"
        Level in the index which specifies country/group information.
    unit_level : str, default="unit"
        Level in the index which specifies the unit of each timeseries.
    ur : pint.facets.PlainRegistry, optional
        The unit registry to use for calculations.

    Returns
    -------
    BudgetAllocationResult or PathwayAllocationResult
        Container with allocation results. Contains:

        - `approach`: Name of approach used (kebab-case string)
        - `relative_shares_cumulative_emission`: DataFrame with country shares
          (sums to 1.0 for each year/emission category)
        - `parameters`: Dict of all parameters used in calculation
        - [Pathway only] `allocation_pathways_by_country`: Year-by-year emissions

    Notes
    -----
    **Theoretical grounding:**

    This approach operationalizes [PRINCIPLE NAME] by [MECHANISM].

    See docs/science/allocations.md#[section-anchor] for detailed theoretical
    discussion, limitations, and academic citations.

    For translating this principle into code, see
    docs/science/principle-to-code.md#[principle-section] for implementation
    patterns.

    **Normative choices embedded in this approach:**

    - **[Choice 1]**: [What is chosen and why it matters]
      - *Implication*: [How this affects allocations, which countries benefit/lose]
    - **[Choice 2]**: [Description]
      - *Implication*: [Impact on equity outcomes]

    [Include any other implementation notes, edge cases, or important behaviors]

    Examples
    --------
    Basic usage with minimal parameters:

    >>> from fair_shares.library.allocations.budgets import my_new_allocation
    >>> from fair_shares.library.utils import create_example_data
    >>> data = create_example_data()
    >>> result = my_new_allocation(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     allocation_year=2020,
    ...     emission_category="co2-ffi",
    ... )
    Converting units...
    >>> result.approach
    'my-new-allocation'
    >>> # Verify shares sum to 1.0
    >>> shares = result.relative_shares_cumulative_emission
    >>> bool(abs(shares["2020"].sum() - 1.0) < 1e-10)
    True

    [For approaches with adjustments, show examples with different parameter values:]

    With historical responsibility adjustment:

    >>> result_with_responsibility = my_new_allocation(  # doctest: +ELLIPSIS
    ...     population_ts=data["population"],
    ...     allocation_year=2020,
    ...     emission_category="co2-ffi",
    ...     country_actual_emissions_ts=data["emissions"],
    ...     responsibility_weight=0.5,
    ...     historical_responsibility_year=1990,
    ... )
    Converting units...
    >>> # Countries with high historical emissions get lower shares
    >>> result_with_responsibility.approach
    'my-new-allocation'

    See Also
    --------
    related_function : Brief description of relationship
    docs/science/allocations.md#relevant-section : Design rationale and theory
    docs/science/principle-to-code.md#principle : Implementation guidance
    docs/user-guide/approach-catalog.md : Complete approach comparison
    """
    # Implementation
    pass
```

## Required Sections

All allocation approach docstrings **must** include:

1. **Summary**: One-line description at the top
2. **Description**: Longer paragraph on when to use this approach
3. **Equity Principles Operationalized**: List of equity principles this approach implements with brief explanations and academic citations
4. **Mathematical Foundation**: LaTeX equations showing the core allocation formula
5. **Parameters**: All parameters with types, descriptions, and cross-references to parameter-effects.md
6. **Returns**: Clear description of result object structure
7. **Notes**:
   - Theoretical grounding with links to allocations.md
   - Link to principle-to-code.md for implementation patterns
   - Normative choices section listing value judgments
8. **Examples**: At least one working example using `create_example_data()`
9. **See Also**: Cross-references to related functions and documentation

## Best Practices

### Equity Principles Operationalized

This section makes the normative foundations of your approach explicit. Think about:

- Which equity principles does this approach align with? (Check docs/science/climate-equity-concepts.md)
- How does the implementation operationalize these principles?
- What is the central normative choice or value judgment?
- Does this fit within existing principles in docs/science/, or should we add new ones?

Write this section in your own words - there's no required format. The goal is understanding the equity grounding, not filling in a template.

**Good example:**

```python
r"""
Equity Principles Operationalized
----------------------------------

This approach implements the principle of equal rights to the atmosphere (grounded
in the egalitarian ethical tradition) by giving all people equal entitlements to
atmospheric space, operationalized via per capita allocation at the allocation year.
It can also account for historical responsibility (earlier allocation years include
more cumulative emissions, following the "polluter pays" principle from Caney 2010)
and capability (GDP-based adjustments when `capability_weight > 0`, following
Höhne et al. 2014).

The key normative choice is treating population at a single point in time as the
basis for equal entitlements, rather than using projected or historical population.

See docs/science/principle-to-code.md#egalitarianism and
docs/science/climate-equity-concepts.md#equal-per-capita.
"""
```

**Bad example:**

```python
r"""
Equity Principles Operationalized
----------------------------------

Uses standard allocation methodology based on population.
"""
```

(Doesn't identify principles, explain how they're operationalized, or surface normative choices.)

### Mathematical Foundation

- Use raw string (`r"""`) for LaTeX equations
- Define all variables used in equations
- For complex approaches, break down the calculation into steps
- Show both the main allocation formula and any adjustment formulas

### Parameters

- Always include cross-reference to `parameter-effects.md` for key parameters
- For adjustment weights, note the direction of effect (e.g., "higher values reduce allocation for...")
- Include valid ranges (e.g., "0.0 to 1.0")
- Specify defaults where applicable

### Normative Choices

Be explicit about value judgments embedded in the approach:

- **Good**: "Allocating based on current population treats all people as equal regardless of when they were born"
  - _Implication_: "Countries with growing populations receive larger future allocations"

- **Bad**: "Uses population" (doesn't surface the normative choice or implications)

### Examples

**CRITICAL:** All examples must demonstrate realistic usage with DataFrame-based data structures. Never use scalar-only examples.

#### Requirements

1. **Use `create_example_data()` for non-IAMC work:**

```pycon
>>> from fair_shares.library.utils import create_example_data
>>> data = create_example_data()
>>> result = calculate_equal_per_capita(data, budget=1000.0)
```

2. **Reference IAMC example file for pathway-based work:**

```pycon
# Example IAMC data columns: model, scenario, region, variable, unit, 1990, 1995, ..., 2100
# Reference: data/scenarios/iamc_example/iamc_reporting_example.xlsx
>>> iamc_data = load_example_iamc()
>>> result = generate_pathway_from_iamc(
...     iamc_data,
...     model="SSP_SSP2_v6.3_ES",
...     scenario="ECPC-2015-800Gt"
... )
```

3. **NEVER use scalar-only examples:**

```pycon
# ❌ BAD - scalar only
>>> calculate_equal_per_capita(100, budget=1000)

# ✅ GOOD - realistic DataFrame
>>> data = create_example_data()
>>> calculate_equal_per_capita(data, budget=1000.0)
```

#### Best Practices

- All examples must be executable (use `# doctest: +ELLIPSIS` for non-deterministic output)
- Use `create_example_data()` for consistent test data
- Show verification that shares sum to 1.0
- For approaches with many parameters, show multiple examples with different configurations
- Include comments explaining what the example demonstrates
- For IAMC examples, explicitly reference column structure (model, scenario, region, variable, unit, year columns)

### Cross-References

Link to:

- **Parameter effects** (`docs/science/parameter-effects.md#parameter_name`) for each key parameter
- **Theoretical grounding** (`docs/science/allocations.md#section`) for academic context
- **Principle-to-code** (`docs/science/principle-to-code.md#principle`) for implementation guidance
- **Related approaches** in See Also section
- **Approach catalog** (`docs/user-guide/approach-catalog.md`) for comparison

## Anti-Patterns to Avoid

❌ **Don't** hide normative choices behind technical jargon:

```python
Notes
-----
Uses standard convergence methodology.
```

✅ **Do** make value judgments explicit:

```python
Notes
-----
**Normative choices:**

- **Grandfathering**: Allocates future emissions based on current shares
  - *Implication*: Countries with high current emissions receive larger
    future allocations, which lacks ethical basis per CBDR-RC principles.
```

❌ **Don't** omit the mathematical foundation:

```python
"""Allocates emissions based on population and other factors."""
```

✅ **Do** show the complete formula:

```python
r"""
Mathematical Foundation
-----------------------

$$
A(g) = \frac{P(g, t_a)}{\sum_{g'} P(g', t_a)} \times (1 - R(g) \times w_R)
$$

Where $R(g)$ is the responsibility adjustment...
```

❌ **Don't** use placeholder examples:

```python
Examples
--------
>>> result = my_function(data)
>>> # TODO: Add example output
```

✅ **Do** provide working, verified examples:

```python
Examples
--------
>>> from fair_shares.library.utils import create_example_data
>>> data = create_example_data()
>>> result = my_function(  # doctest: +ELLIPSIS
...     population_ts=data["population"],
...     allocation_year=2020,
... )
Converting units...
>>> bool(abs(result.relative_shares_cumulative_emission["2020"].sum() - 1.0) < 1e-10)
True
```

## Validation

Before committing, verify:

1. ✅ All sections present (use checklist from `testing-checklist.md`)
2. ✅ "Equity Principles Operationalized" section lists specific principles with citations
3. ✅ LaTeX equations render correctly in generated docs
4. ✅ All examples execute without errors: `uv run pytest --doctest-modules src/`
5. ✅ Cross-references link to existing documentation sections
6. ✅ Parameter types match function signature
7. ✅ Normative choices section identifies at least one value judgment

## See Also

- [Testing Checklist](https://setupelz.github.io/fair-shares/dev-guide/testing-checklist/) — Pre-merge validation steps
- [Adding New Approaches](https://setupelz.github.io/fair-shares/dev-guide/adding-approaches/) — Complete workflow for new allocations
- [Parameter Effects Reference](https://setupelz.github.io/fair-shares/science/parameter-effects/) — Parameter documentation to link to
- [Principle-to-Code Guide](https://setupelz.github.io/fair-shares/science/principle-to-code/) — Implementation patterns for equity principles
