# Testing Checklist for New Allocation Approaches

This checklist ensures new allocation approaches are thoroughly validated before merging. Complete all sections before creating a pull request.

## Pre-Merge Checklist

### Unit Tests

Verify the fundamental behavior of your allocation approach:

- [ ] **Shares sum to 1.0**: All test cases verify `abs(result.relative_shares_cumulative_emission.sum() - 1.0) < 1e-10`
- [ ] **Correct approach name**: `result.approach` matches the kebab-case registry name
- [ ] **Parameters stored correctly**: `result.parameters` dict contains all input parameters
- [ ] **Zero weight produces no adjustment**: For approaches with adjustment weights (e.g., `responsibility_weight`, `capability_weight`), verify that weight=0 produces unadjusted allocations
- [ ] **Extreme parameter values handled gracefully**: Test boundary cases (e.g., `allocation_year` at dataset edges, weights at 0.0 and 1.0)
- [ ] **Edge cases**: Empty datasets, single-country scenarios, missing data handled appropriately

**Example test pattern:**

```python
def test_my_new_allocation_shares_sum_to_one():
    data = create_example_data()
    result = my_new_allocation(
        population_ts=data["population"],
        allocation_year=2020,
        emission_category="co2-ffi",
    )
    assert abs(result.relative_shares_cumulative_emission["2020"].sum() - 1.0) < 1e-10
```

### Integration Tests

Verify the approach works with the broader system:

- [ ] **Works with AllocationManager**: Approach can be loaded via `AllocationManager.create_allocation()`
- [ ] **Handles real PRIMAP data**: Runs successfully with actual historical emissions data (not just test data)
- [ ] **Handles missing countries gracefully**: Works when some countries lack population/GDP/emissions data
- [ ] **Year range validation**: Handles edge cases like `allocation_year` before/after data availability
- [ ] **Multi-category support**: Works with different emission categories (co2-ffi, kyoto-ghg, etc.)

**Example integration test pattern:**

```python
def test_my_new_allocation_with_real_data():
    from fair_shares.library.utils import load_primap_data
    primap_data = load_primap_data()
    result = my_new_allocation(
        population_ts=primap_data.population,
        country_actual_emissions_ts=primap_data.emissions,
        allocation_year=2020,
        emission_category="co2-ffi",
    )
    assert result.approach == "my-new-allocation"
```

### Documentation

Ensure comprehensive documentation following the docstring template:

- [ ] **Docstring follows template**: See [docstring-template.md]({DOCS_ROOT}/dev-guide/docstring-template/) for required sections
- [ ] **Mathematical Foundation section**: Includes LaTeX equations defining the allocation formula
- [ ] **All variables defined**: LaTeX equations define all symbols used (e.g., $A(g)$, $P(g, t)$)
- [ ] **Parameter descriptions complete**: Each parameter documented with type, description, valid range, and cross-reference to parameter-effects.md
- [ ] **Example code runs without errors**: All docstring examples execute successfully with `uv run pytest --doctest-modules src/`
- [ ] **Notes section includes normative choices**: At least one value judgment explicitly stated with implications
- [ ] **See Also section**: Cross-references to related approaches, allocations.md, principle-to-code.md

### Equity Grounding

**All allocation approaches MUST explicitly document their equity principles foundation:**

- [ ] **Equity Principles Operationalized section present**: Docstring includes dedicated section after Description
- [ ] **Specific principles identified**: Lists which equity principles are implemented (e.g., equal per capita / equal atmospheric rights, historical responsibility, capability, CBDR-RC)
- [ ] **Operationalization explained**: Describes HOW each principle is implemented in the code (not just "uses principle X")
- [ ] **Academic citations included**: References climate equity literature grounding these principles (e.g., Caney 2010, Höhne et al. 2014)
- [ ] **Key normative choice identified**: States the central value judgment the approach makes
- [ ] **Links to conceptual resources**: Cross-references to `docs/science/principle-to-code.md#[principle]` and `docs/science/climate-equity-concepts.md#[concept]`
- [ ] **Normative choices enumerated**: Notes section lists specific value judgments with implications for which countries benefit/lose
- [ ] **Anti-patterns avoided**: Does not implement or recommend grandfathering (allocating future entitlements based on current emission shares), BAU deviation framing (treating deviation from business-as-usual as a cost), or small share justifications (lacking consistency as equity argument)

**Why equity grounding matters:**

This project makes normative choices visible rather than hiding them behind technical defaults. Every allocation approach embeds value judgments about fairness, responsibility, and entitlement. Making these explicit:

- Enables users to choose approaches aligned with their principles
- Prevents "neutral-looking" defaults from masking ethical positions
- Grounds implementation in climate equity scholarship
- Maintains consistency with CBDR-RC (Common But Differentiated Responsibilities and Respective Capabilities)

**Required docstring sections:**

1. Summary (one line)
2. Description (when to use this approach)
3. Mathematical Foundation (LaTeX equations)
4. Parameters (with cross-references)
5. Returns (result object structure)
6. Notes (theoretical grounding + normative choices)
7. Examples (at least one working example)
8. See Also (cross-references)

### Registry

Ensure the approach is properly registered:

- [ ] **Added to registry.py**: Approach listed in `ALLOCATION_APPROACHES` or `PATHWAY_APPROACHES`
- [ ] **Kebab-case name follows convention**: Name uses lowercase with hyphens (e.g., `my-new-allocation`)
- [ ] **Type detection works**: `is_budget_approach()` or `is_pathway_approach()` returns correct boolean
- [ ] **Docstring summary matches**: First line of docstring matches registry description
- [ ] **Import statement correct**: Function imported from correct module path

**Example registry entry:**

```python
ALLOCATION_APPROACHES = {
    "my-new-allocation": {
        "function": my_new_allocation,
        "type": "budget",  # or "pathway"
        "description": "One-line summary matching docstring",
    },
}
```

### Code Quality

Follow project conventions and best practices:

- [ ] **Type hints on all parameters**: Function signature includes type annotations
- [ ] **Follows existing patterns**: Code structure matches similar approaches in codebase
- [ ] **No hardcoded values**: Magic numbers replaced with named constants or parameters
- [ ] **Error messages are clear**: Validation errors explain what's wrong and how to fix it
- [ ] **Performance considerations**: No unnecessary loops or redundant calculations

### Cross-References

Verify documentation links are correct:

- [ ] **Parameter effects cross-references work**: Links to `docs/science/parameter-effects.md#parameter_name` resolve correctly
- [ ] **Allocations.md anchor exists**: Reference to `docs/science/allocations.md#section` points to valid section
- [ ] **Principle-to-code reference valid**: Link to `docs/science/principle-to-code.md#principle` exists
- [ ] **API docs will generate correctly**: Docstring format compatible with mkdocs/mkdocstrings

## Quick Validation Commands

Run these commands before creating a pull request:

```bash
# Run unit and integration tests
uv run pytest tests/ -v

# Run docstring examples
uv run pytest --doctest-modules src/fair_shares/library/allocations/

# Check type hints
uv run mypy src/fair_shares/library/allocations/

# Lint code
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Build documentation to verify no broken links
uv run mkdocs build --strict

# Optional: Run documentation sync check (if available)
uv run python tools/docs-sync-check.py
```

## Common Issues

### Shares Don't Sum to 1.0

**Symptom:** Test fails with `AssertionError: shares sum to X, not 1.0`

**Solutions:**

- Check for division by zero when metric sum is zero
- Ensure all countries are included in normalization step
- Verify no NaN values in intermediate calculations
- Use `ensure_string_year_columns()` on input dataframes

### Docstring Examples Fail

**Symptom:** `pytest --doctest-modules` reports failures

**Solutions:**

- Add `# doctest: +ELLIPSIS` for non-deterministic output (e.g., unit conversion messages)
- Use `create_example_data()` instead of hardcoded data
- Verify example code matches current API signatures
- Check that imports in examples are correct

### Missing Parameter Cross-References

**Symptom:** Documentation build warnings about broken links

**Solutions:**

- Ensure `parameter-effects.md` has anchor for each parameter (e.g., `## allocation_year`)
- Use exact anchor names in cross-references
- Verify `allocations.md` section exists before linking
- Check `principle-to-code.md` has the referenced principle section

## See Also

- [Docstring Template]({DOCS_ROOT}/dev-guide/docstring-template/) — Required docstring structure
- [Adding New Approaches]({DOCS_ROOT}/dev-guide/adding-approaches/) — Complete workflow for new allocations
- [Parameter Effects Reference]({DOCS_ROOT}/science/parameter-effects/) — Parameter documentation
- [Principle-to-Code Guide]({DOCS_ROOT}/science/principle-to-code/) — Implementation patterns
- [Allocations Overview]({DOCS_ROOT}/science/allocations/) — Theoretical grounding
