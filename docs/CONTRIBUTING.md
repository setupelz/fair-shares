# Contributing to Fair Shares Documentation

This guide ensures documentation accuracy and maintains consistency between code, science foundations, and user-facing documentation.

---

## Documentation Verification Checklist

**Before merging any documentation changes, verify:**

### 1. Technical Claims Are Grounded

Every technical claim must reference an authoritative source:

- **Function behavior** → Reference the function docstring in `src/`
- **Mathematical formulation** → Reference `docs/science/allocations.md` or function docstring with LaTeX math
- **Conceptual foundation** → Reference `docs/science/climate-equity-concepts.md` or published literature
- **Parameter behavior** → Reference function docstring where parameter is defined

**Add HTML comment cross-references** to link claims to their sources:

```markdown
<!-- REFERENCE: Parameter behaviors are defined in function docstrings:
     - per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py
     For theoretical foundations, see docs/science/allocations.md
-->
```

### 2. No Invented Simplifications

**Do NOT:**

- Invent simplified formulas that don't match the code
- Describe mental models that misrepresent the actual system
- Use analogies that contradict the mathematical reality
- Create tables or examples based on how you think it "should" work

**Instead:**

- Link to science docs for detailed explanations
- Show code examples demonstrating actual behavior
- State "See [section] for mathematical details" rather than inventing a simplified version
- If you can't explain it accurately in simple terms, don't simplify — link to the authoritative source

### 3. Cross-Reference with Authoritative Sources

For every technical section, verify against **at least one** of:

1. **Function docstrings** in `src/fair_shares/library/` (have LaTeX math, parameter descriptions)
2. **Science docs** in `docs/science/` (have theoretical grounding, citations)
3. **Test cases** in `tests/` (show expected behavior with specific inputs)

**Verification workflow:**

```bash
# 1. Find the relevant function
grep -r "def function_name" src/

# 2. Read the docstring
# 3. Compare doc claim against docstring
# 4. If claim contradicts docstring, fix the doc (NOT the docstring)
```

### 4. Test Claims with Code

If documenting parameter behavior, **run a test** to verify:

```python
# Example: Verify claim about weight ratio
from fair_shares.library.allocations.budgets.per_capita import per_capita_adjusted_budget

# Test claim: "Only the ratio between weights matters"
result1 = per_capita_adjusted_budget(
    budget_gtco2=500,
    responsibility_weight=0.3,
    capability_weight=0.7,
    # ... other params
)

result2 = per_capita_adjusted_budget(
    budget_gtco2=500,
    responsibility_weight=0.15,
    capability_weight=0.35,
    # ... other params
)

# Should be identical (verify before documenting)
assert result1.equals(result2)
```

### 5. Avoid Common Pitfalls

**Pitfall: Describing additive allocation when it's multiplicative**

❌ Wrong:

> "With weights (0.5, 0.3, 0.2), the allocation is 50% population, 30% responsibility, 20% capability"

✅ Correct:

> "Population share is the foundation. Responsibility and capability adjustments multiply against it. Weights control the strength of these inverse adjustments. See `docs/science/allocations.md` for mathematical details."

**Pitfall: Implying parameters have linear effects when they're exponential**

❌ Wrong:

> "max_convergence_speed=1.0 means instant convergence to target"

✅ Correct:

> "max_convergence_speed controls the exponential rate of convergence. Higher values approach the target faster. See `per_capita_convergence()` docstring for the exponential formula."

**Pitfall: Using vague language for precise mathematical operations**

❌ Wrong:

> "Adjustments are applied based on historical emissions"

✅ Correct:

> "Responsibility adjustment multiplies allocation by `responsibility_metric^(-weight × exponent)`, creating an inverse relationship where higher historical emissions lead to lower allocations."

**Pitfall: Documenting edge cases without verification**

❌ Wrong:

> "When weight is 0, the allocation falls back to equal per-capita"

✅ Correct:

> "When weight is 0, the adjustment factor equals 1.0 (no adjustment). See test case `test_zero_weight_no_adjustment` in `tests/test_per_capita.py`."

### 6. Recipe and Example Verification

For all code examples:

1. **Run the code** to verify it executes without errors
2. **Check the output** matches what the documentation claims
3. **Verify comments** are accurate (especially parameter explanations)

**Bad comment example:**

```python
"responsibility_weight": 0.5,
"capability_weight": 0.5,
# Remaining 0.0 goes to pure per capita  ❌ WRONG (no "remaining")
```

**Good comment example:**

```python
"responsibility_weight": 0.5,
"capability_weight": 0.5,
# Equal weight to both adjustments ✅ CORRECT
```

---

## Documentation Hierarchy

Understand which documentation is authoritative for different types of information:

### 1. Function Docstrings (Authoritative for Implementation)

**Location:** `src/fair_shares/library/`

**Content:**

- LaTeX mathematical formulations
- Parameter descriptions with types and constraints
- Implementation details
- Return value schemas

**Status:** Source of truth for "what does the code do"

### 2. Science Documentation (Authoritative for Theory)

**Location:** `docs/science/`

**Content:**

- Theoretical foundations
- Climate equity concepts
- Literature citations
- Mathematical derivations
- Design rationale

**Status:** Source of truth for "why does it work this way"

### 3. User Guides (Simplified but Accurate)

**Location:** `docs/user-guide/`

**Content:**

- Step-by-step workflows
- Parameter selection guidance
- Practical examples
- Quick reference tables

**Status:** Must match (1) and (2), with simplification allowed ONLY when it remains accurate

**Guideline:** If you can't simplify without misrepresenting, link to authoritative source instead

### 4. API Documentation (Generated)

**Location:** `docs/api/`

**Content:**

- Auto-generated from docstrings using mkdocstrings

**Status:** Reflects function docstrings; if API docs are wrong, fix the docstring

---

## When to Update Different Documentation

### Scenario: Adding a New Parameter

1. ✅ Add parameter to function signature with docstring
2. ✅ Update `docs/science/allocations.md` if it changes the mathematical model
3. ✅ Update `docs/user-guide/parameter-guide.md` with usage guidance
4. ✅ Add test case demonstrating parameter behavior
5. ✅ Verify API docs regenerate correctly from docstring

### Scenario: Fixing a Bug in Calculation

1. ✅ Fix the code
2. ✅ Update function docstring if the bug fix changes documented behavior
3. ✅ Check if `docs/science/allocations.md` needs correction
4. ✅ Check if `docs/user-guide/` has examples affected by the bug
5. ⚠️ DO NOT update docs to match buggy behavior — fix code first, then verify docs

### Scenario: Improving Documentation Clarity

1. ✅ Read the function docstring (source of truth)
2. ✅ Read `docs/science/allocations.md` (theoretical grounding)
3. ✅ Verify your "clearer" explanation matches both
4. ✅ Add cross-reference HTML comments linking to authoritative sources
5. ⚠️ If you can't make it clearer without misrepresenting, add a link instead

---

## Pre-Commit Review Questions

Before submitting documentation changes, answer:

1. **Source verification**
   - [ ] Have I read the relevant function docstring(s)?
   - [ ] Have I checked the science docs for theoretical grounding?
   - [ ] Does my documentation match what the code actually does?

2. **Accuracy**
   - [ ] Are all formulas/equations copied from authoritative sources (not invented)?
   - [ ] Are parameter descriptions consistent with function docstrings?
   - [ ] Have I avoided simplified explanations that misrepresent the system?

3. **Cross-references**
   - [ ] Have I added HTML comment cross-references to ground technical claims?
   - [ ] Do I link to science docs or docstrings for mathematical details?

4. **Testing**
   - [ ] If documenting examples, have I run them to verify they work?
   - [ ] If documenting parameter behavior, have I tested with real inputs?
   - [ ] If documenting edge cases, have I verified with test cases?

5. **Consistency**
   - [ ] Does this documentation contradict any other documentation?
   - [ ] If I changed a description, did I check if it appears elsewhere?
   - [ ] Are my terms consistent with science docs (e.g., "adjustment" not "component")?

---

## Red Flags — Stop and Verify

If you write any of these phrases, **stop and verify against code:**

- "The allocation is X% based on..."
- "The remaining portion goes to..."
- "This parameter controls what percentage..."
- "When weight is X, Y% of the allocation..."
- "The formula is..." (unless copied from docstring/science docs)
- "This causes the value to instantly..."
- "The system falls back to..."
- "In simple terms, this means..." (unless you've verified the simple terms are accurate)

---

## How to Add Cross-Reference Comments

Place HTML comments **before** technical sections to link claims to their sources:

### For Parameter Descriptions

```markdown
<!-- REFERENCE: Parameter behaviors are defined in function docstrings:
     - per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py
     - per_capita_adjusted() in src/fair_shares/library/allocations/pathways/per_capita.py
     For theoretical foundations, see docs/science/allocations.md
-->

## Parameters

(parameter documentation here)
```

### For Approach Descriptions

```markdown
<!-- REFERENCE: Approach implementations in src/fair_shares/library/allocations/
     Budget approaches: budgets/per_capita.py
     Pathway approaches: pathways/per_capita.py, pathways/cumulative_per_capita_convergence.py
     Mathematical details and design rationale: docs/science/allocations.md
-->

## Allocation Approaches

(approach documentation here)
```

### For Workflow Steps

```markdown
<!-- REFERENCE: Function implementations in src/fair_shares/library/utils/data/iamc.py
     See load_iamc_data() docstring for complete parameter documentation
-->

### Loading Data

(workflow documentation here)
```

### For Conceptual Explanations

```markdown
<!-- REFERENCE: Theoretical grounding in docs/science/climate-equity-concepts.md
     CBDR-RC principle and equity frameworks
     Published literature cited in references.md
-->

## Climate Equity Principles

(conceptual documentation here)
```

---

## Documentation Testing

### Manual Testing Checklist

Before merging docs:

1. **Build the docs locally**

   ```bash
   uv run mkdocs serve
   ```

2. **Check for warnings**
   - No broken internal links
   - No missing front matter
   - No deprecated syntax warnings

3. **Verify cross-references**
   - Open referenced source files
   - Confirm claims match docstrings/code

4. **Test code examples**
   - Copy examples into Python REPL
   - Verify they execute without errors
   - Check output matches documentation

### Automated Checks (Future)

Potential automation:

- Link checker (internal references)
- Docstring-to-docs consistency checker
- Example code runner (verify all examples execute)

---

## Getting Help

If you're unsure about documentation accuracy:

1. **Read the code first** — Docstrings in `src/` are authoritative
2. **Check science docs** — `docs/science/allocations.md` has theoretical grounding
3. **Run a test** — Verify behavior with actual code execution
4. **Ask for review** — Tag maintainers for technical verification

**When in doubt, link instead of paraphrasing.** It's better to say "See [authoritative source] for details" than to risk documenting incorrect behavior.

---

## Examples of Good vs. Bad Documentation

### Example 1: Weight System

❌ **Bad (Invented Formula):**

```markdown
## Weight System

The allocation formula is:

ALLOCATION = (population × per_capita_weight) + (responsibility × responsibility_weight) + (capability × capability_weight)

Where: per_capita_weight = 1.0 - responsibility_weight - capability_weight
```

✅ **Good (References Authoritative Source):**

```markdown
<!-- REFERENCE: Mathematical formulation in docs/science/allocations.md
     Implementation: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py
-->

## Weight System

Weights control the strength of inverse adjustments to population-based allocation. Higher weights create steeper inverse relationships (higher metric → lower allocation).

Only the **ratio** between weights matters: `(0.3, 0.7)` and `(0.15, 0.35)` produce identical allocations.

**Mathematical details:** See [Weight Normalization](https://setupelz.github.io/fair-shares/science/allocations/#weight-normalization).
```

### Example 2: Parameter Behavior

❌ **Bad (Untested Claim):**

```markdown
When `max_convergence_speed=1.0`, the pathway instantly jumps to the target value.
```

✅ **Good (Verified Against Code):**

```markdown
<!-- REFERENCE: per_capita_convergence() docstring in src/fair_shares/library/allocations/pathways/per_capita.py
     Exponential convergence formula: E(t) = E_hist(t) × exp(-speed × t)
-->

`max_convergence_speed` controls the exponential rate of convergence. Higher values approach the target faster. With `speed=1.0` and `convergence_year=2050`, the pathway reaches ~63% of the remaining distance to the target by mid-century.
```

### Example 3: Code Recipe

❌ **Bad (Wrong Comment):**

```python
{
    "responsibility_weight": 0.4,
    "capability_weight": 0.6,
    # 40% responsibility, 60% capability, 0% pure per capita
}
```

✅ **Good (Accurate Comment):**

```python
<!-- REFERENCE: Weight normalization behavior in per_capita_adjusted_budget()
     See docs/science/allocations.md for mathematical derivation
-->

{
    "responsibility_weight": 0.4,
    "capability_weight": 0.6,
    # 2:3 ratio between adjustments (normalized before use)
}
```

---

## Summary

**Documentation must match implementation.** When in conflict, the code is correct and the documentation is wrong.

**Three-tier verification:**

1. **Docstrings** (in `src/`) — What does it do?
2. **Science docs** (in `docs/science/`) — Why does it work this way?
3. **User guides** (in `docs/user-guide/`) — How do I use it?

**Cross-reference everything.** Link technical claims to their authoritative sources using HTML comments.

**When uncertain, link instead of paraphrasing.** Better to say "See [source]" than to document incorrect behavior.
