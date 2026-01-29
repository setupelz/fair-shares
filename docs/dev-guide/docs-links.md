---
title: Documentation Links
description: Managing documentation URLs across the codebase
---

# Documentation Links

This project uses a centralized system for managing documentation links, making it easy to update URLs when documentation moves or is reorganized.

## System Overview

**Central configuration**: `src/fair_shares/library/config/urls.py`
**Update script**: `scripts/update_docs_links.py`
**Placeholder pattern**: `{DOCS_ROOT}/path/to/page/`

## Usage Patterns

### In Python Code and Docstrings

Use the `docs_url()` function for dynamic link generation:

```python
from fair_shares.library.config.urls import docs_url, DOCS_URLS

# Generate a docs URL
url = docs_url("science/allocations")
# Returns: "https://setupelz.github.io/fair-shares/science/allocations/"

# Use pre-defined URLs
science_url = DOCS_URLS["science"]["allocations"]
```

### In Notebooks and Markdown

Use the `{DOCS_ROOT}` placeholder pattern:

```markdown
See [Allocation Approaches]({DOCS_ROOT}/science/allocations/) for details.
[IAMC guide]({DOCS_ROOT}/user-guide/iamc-regional-fair-shares/#format)
```

**Important**: Use trailing slashes and no `.md` extension (MkDocs convention).

## Managing Links

### When Documentation URL Changes

1. Update `DOCS_BASE_URL` in `src/fair_shares/library/config/urls.py`
2. All Python code automatically uses the new URL
3. For notebooks/markdown, no changes needed (placeholders remain)

### Converting Links

The `scripts/update_docs_links.py` script handles bulk link conversions:

```bash
# Convert relative links to placeholders (one-time setup)
python scripts/update_docs_links.py --to-placeholder

# Expand placeholders to URLs (for distribution)
python scripts/update_docs_links.py --expand

# Collapse URLs back to placeholders (for development)
python scripts/update_docs_links.py --collapse

# Preview changes without modifying files
python scripts/update_docs_links.py --collapse --dry-run
```

### Workflow

**During development**: Keep links as `{DOCS_ROOT}` placeholders in notebooks and markdown.

**Before distribution**: Optionally expand placeholders to full URLs if needed for platforms that don't support custom processing.

## Environment Variable Override

Override the documentation URL at runtime:

```bash
export FAIR_SHARES_DOCS_URL="https://custom-domain.com/docs"
python scripts/update_docs_links.py --expand
```

This is useful for:

- Testing documentation on staging servers
- Custom documentation deployments
- Local documentation preview

## Link Format Guidelines

### Correct

```markdown
[Page]({DOCS_ROOT}/science/allocations/)
[With anchor]({DOCS_ROOT}/user-guide/quickstart/#installation)
```

### Incorrect

```markdown
[Missing slash]({DOCS_ROOT}/science/allocations)
[Has .md]({DOCS_ROOT}/science/allocations.md/)
[Relative](../docs/science/allocations/)
```

## Implementation Details

### Why Placeholders?

1. **Maintainability**: Change URL once, affects all links
2. **Portability**: Move docs to new domain without updating every file
3. **Clarity**: Clear that links reference project documentation
4. **Flexibility**: Support multiple deployment targets

### Pattern Recognition

The update script recognizes:

- **Placeholders**: `{DOCS_ROOT}/path/`
- **Full URLs**: `https://setupelz.github.io/fair-shares/path/`
- **Relative**: `../docs/path/` or `docs/path/`

### File Coverage

The script updates:

- `notebooks/*.py` - All Jupytext notebook sources
- `src/**/*.py` - Python source code and docstrings
- `README.md` - Project documentation

Excluded:

- `.ipynb` files (generated from `.py` via `make sync-ipynb`)
- Binary files
- The update script itself
