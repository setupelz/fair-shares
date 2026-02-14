# Contributing

## Core Rule

**Documentation must match the code.** When they conflict, the code is correct and the docs are wrong.

If you can't explain something accurately in simple terms, link to the authoritative source instead of inventing a simplified version.

---

## Documentation Hierarchy

| Layer            | Location                   | Source of truth for                                             |
| ---------------- | -------------------------- | --------------------------------------------------------------- |
| **Docstrings**   | `src/fair_shares/library/` | What the code does (LaTeX math, parameters, return types)       |
| **Science docs** | `docs/science/`            | Why it works this way (principles, citations, design rationale) |
| **User guides**  | `docs/user-guide/`         | How to use it (workflows, examples, quick reference)            |
| **API docs**     | `docs/api/`                | Auto-generated from docstrings via mkdocstrings                 |

User guides may simplify, but only when the simplification remains accurate. If API docs are wrong, fix the docstring, not the docs.

---

## Before Merging Documentation Changes

### Ground technical claims

Every claim about function behavior, formulas, or parameter effects must be traceable to a docstring, science doc, or test case. Add HTML comment cross-references:

```markdown
<!-- REFERENCE: per_capita_adjusted_budget() in src/fair_shares/library/allocations/budgets/per_capita.py
     Mathematical details: docs/science/allocations.md -->
```

### Test code examples

Run every code example before documenting it. Verify output matches claims. Check that comments are accurate -- especially parameter explanations.

### Build locally

```bash
uv run mkdocs serve
```

Check for broken links, missing front matter, and syntax warnings.

---

## When to Update What

| Change        | Update                                                                                               |
| ------------- | ---------------------------------------------------------------------------------------------------- |
| New parameter | Docstring, `docs/science/allocations.md` if math changes, user guide if user-facing                  |
| Bug fix       | Code first, then docstring if behavior changed, then check user guides for affected examples         |
| Clearer docs  | Read the docstring and science docs first, verify your version matches, add cross-reference comments |

---

## Getting Help

1. Read the code -- docstrings in `src/` are authoritative
2. Check `docs/science/allocations.md` for theoretical grounding
3. Run a test to verify behavior
4. Tag maintainers for review
