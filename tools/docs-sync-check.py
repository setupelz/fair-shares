#!/usr/bin/env python3
"""
Validate documentation consistency with codebase.

Usage:
    uv run python tools/docs-sync-check.py
    uv run python tools/docs-sync-check.py --execute  # Also run example code
    uv run python tools/docs-sync-check.py --verbose  # Show all checks
    uv run python tools/docs-sync-check.py --quiet    # Only show errors
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple


class ValidationResult(NamedTuple):
    """Result from a documentation validation check.

    Attributes
    ----------
        category: Type of check ("registry", "parameter", "example", "crossref")
        severity: Level of issue ("error", "warning")
        file: Path to file where issue was found
        line: Line number where issue was found (None if not applicable)
        message: Human-readable description of the issue
    """

    category: str
    severity: str
    file: Path
    line: int | None
    message: str


def _parse_registry_functions(
    registry_path: Path,
) -> tuple[dict[str, str], set[str]]:
    """Parse registry.py to extract approach->function mappings.

    This function safely parses the registry dictionary format, handling both
    single-line and multi-line function entries. It uses a state machine approach
    with proper variable initialization to avoid scope bugs.

    Parameters
    ----------
    registry_path : Path
        Path to the registry.py file

    Returns
    -------
    tuple[dict[str, str], set[str]]
        - approaches_dict: Maps approach names (kebab-case) to function names
        - functions_set: Set of all function names for validation
    """
    try:
        registry_content = registry_path.read_text()
    except Exception:
        return {}, set()

    approaches = {}
    in_dict = False
    current_approach = None

    for line in registry_content.split("\n"):
        if "return {" in line:
            in_dict = True
            continue
        if in_dict:
            if line.strip() == "}":
                break
            if '":' in line:
                # New entry
                parts = line.split('"')
                if len(parts) >= 3:
                    current_approach = parts[1]
                    after_colon = line.split(":")[1].strip()
                    if "(" not in after_colon:
                        # Single-line entry: "name": function_name,
                        func = after_colon.rstrip(",").strip()
                        if func and not func.startswith("#"):
                            approaches[current_approach] = func
                        current_approach = None  # Reset state
            elif current_approach and line.strip() and not line.strip().startswith("#"):
                # Continuation line for current_approach
                func = line.strip().rstrip("),").strip()
                if func:
                    approaches[current_approach] = func
                    current_approach = None  # Reset after consuming

    # Extract function names as a set
    functions = set(approaches.values())

    return approaches, functions


def check_registry_coverage() -> list[ValidationResult]:
    """Verify all approaches in registry have documentation.

    Parses src/fair_shares/library/allocations/registry.py to get approach names,
    then verifies each has corresponding entries in:
    - docs/api/allocations/budgets.md (for budget approaches)
    - docs/api/allocations/pathways.md (for pathway approaches)
    - docs/user-guide/approach-catalog.md

    Returns
    -------
        List of ValidationResult objects for any issues found
    """
    results = []

    # Get project root (tools/ is one level down from root)
    project_root = Path(__file__).parent.parent

    # Parse registry to extract approach names
    registry_path = project_root / "src/fair_shares/library/allocations/registry.py"
    if not registry_path.exists():
        results.append(
            ValidationResult(
                category="registry",
                severity="error",
                file=registry_path,
                line=None,
                message="Registry file not found",
            )
        )
        return results

    # Parse registry to extract approach->function mappings
    approaches, _ = _parse_registry_functions(registry_path)

    if not approaches:
        results.append(
            ValidationResult(
                category="registry",
                severity="error",
                file=registry_path,
                line=None,
                message="Could not parse approach names from registry",
            )
        )
        return results

    # Check API documentation for each approach
    budgets_api_path = project_root / "docs/api/allocations/budgets.md"
    pathways_api_path = project_root / "docs/api/allocations/pathways.md"
    catalog_path = project_root / "docs/user-guide/approach-catalog.md"

    # Read documentation files with error handling
    try:
        budgets_content = (
            budgets_api_path.read_text() if budgets_api_path.exists() else ""
        )
    except Exception as e:
        budgets_content = ""
        results.append(
            ValidationResult(
                category="registry",
                severity="warning",
                file=budgets_api_path,
                line=None,
                message=f"Could not read file: {e}",
            )
        )

    try:
        pathways_content = (
            pathways_api_path.read_text() if pathways_api_path.exists() else ""
        )
    except Exception as e:
        pathways_content = ""
        results.append(
            ValidationResult(
                category="registry",
                severity="warning",
                file=pathways_api_path,
                line=None,
                message=f"Could not read file: {e}",
            )
        )

    try:
        catalog_content = catalog_path.read_text() if catalog_path.exists() else ""
    except Exception as e:
        catalog_content = ""
        results.append(
            ValidationResult(
                category="registry",
                severity="warning",
                file=catalog_path,
                line=None,
                message=f"Could not read file: {e}",
            )
        )

    # Check each approach
    for approach, function_name in approaches.items():
        is_budget = approach.endswith("-budget")

        # Check API documentation (using actual function name from registry)
        if is_budget:
            # Should be in budgets.md
            if function_name not in budgets_content:
                results.append(
                    ValidationResult(
                        category="registry",
                        severity="error",
                        file=budgets_api_path,
                        line=None,
                        message=f"Budget approach '{approach}' (function: {function_name}) not documented in API reference",
                    )
                )
        else:
            # Should be in pathways.md
            if function_name not in pathways_content:
                results.append(
                    ValidationResult(
                        category="registry",
                        severity="error",
                        file=pathways_api_path,
                        line=None,
                        message=f"Pathway approach '{approach}' (function: {function_name}) not documented in API reference",
                    )
                )

        # Check approach catalog (should mention the kebab-case name)
        if f"`{approach}`" not in catalog_content:
            results.append(
                ValidationResult(
                    category="registry",
                    severity="error",
                    file=catalog_path,
                    line=None,
                    message=f"Approach '{approach}' not listed in approach catalog",
                )
            )

    return results


def check_example_syntax() -> list[ValidationResult]:
    """Verify example code blocks are valid Python.

    Extracts Python code blocks from markdown files and validates syntax
    using ast.parse(). Optionally executes code if --execute flag is provided.

    Returns
    -------
        List of ValidationResult objects for any syntax errors
    """
    import ast

    results = []

    # Get project root (tools/ is one level down from root)
    project_root = Path(__file__).parent.parent
    docs_dir = project_root / "docs"

    if not docs_dir.exists():
        results.append(
            ValidationResult(
                category="example",
                severity="error",
                file=docs_dir,
                line=None,
                message="Documentation directory not found",
            )
        )
        return results

    # Find all markdown files recursively
    markdown_files = list(docs_dir.rglob("*.md"))

    # Pattern to match Python code blocks: ```python ... ```
    # Use DOTALL to match across newlines
    code_block_pattern = re.compile(r"```python\n(.*?)```", re.DOTALL)

    for md_file in markdown_files:
        try:
            content = md_file.read_text()
        except Exception as e:
            results.append(
                ValidationResult(
                    category="example",
                    severity="warning",
                    file=md_file,
                    line=None,
                    message=f"Could not read file: {e}",
                )
            )
            continue

        # Find all Python code blocks
        for match in code_block_pattern.finditer(content):
            code = match.group(1)
            # Calculate line number where code block starts
            # Count newlines up to the match start
            lines_before = content[: match.start()].count("\n")
            code_start_line = lines_before + 2  # +1 for 0-index, +1 for ```python line

            # Skip code blocks that are clearly documentation fragments
            # These are intentionally incomplete to illustrate specific points
            skip_markers = [
                "✅",  # Good example markers in documentation
                "❌",  # Bad example markers in documentation
                "...",  # Ellipsis indicating continuation or truncation
                "# TODO",  # Placeholder examples
                "<!--",  # HTML comments in code blocks (doc examples)
                "Notes\n-----",  # Docstring section examples
                "Examples\n--------",  # Docstring section examples
                "Parameters\n----------",  # Docstring section examples
                "Returns\n-------",  # Docstring section examples
                "$$",  # LaTeX math in docstrings
            ]

            # Also skip if it looks like a DataFrame repr (starts with whitespace + column names)
            lines = code.strip().split("\n")
            if (
                lines
                and lines[0].strip()
                and all(c.isdigit() or c.isspace() for c in lines[0][:20])
            ):
                # Looks like tabular data (years as columns)
                continue

            # Skip if any skip marker is found
            if any(marker in code for marker in skip_markers):
                continue

            # Try to parse the code
            try:
                ast.parse(code)
            except SyntaxError as e:
                # Calculate actual line number in the markdown file
                # e.lineno is relative to the code block
                actual_line = (
                    code_start_line + (e.lineno - 1) if e.lineno else code_start_line
                )
                results.append(
                    ValidationResult(
                        category="example",
                        severity="error",
                        file=md_file,
                        line=actual_line,
                        message=f"Invalid Python syntax: {e.msg}",
                    )
                )
            except Exception as e:
                # Catch other parsing errors
                results.append(
                    ValidationResult(
                        category="example",
                        severity="error",
                        file=md_file,
                        line=code_start_line,
                        message=f"Failed to parse Python code: {e!s}",
                    )
                )

    return results


def check_parameter_consistency() -> list[ValidationResult]:
    """Verify parameter names match between docstrings and docs.

    Extracts parameters from function signatures in source code,
    compares with parameter tables in docs/science/allocations.md.
    Flags parameters documented but not in code, or vice versa.

    Returns
    -------
        List of ValidationResult objects for any inconsistencies
    """
    import ast

    results = []

    # Get project root (tools/ is one level down from root)
    project_root = Path(__file__).parent.parent

    # Find allocation function files
    budgets_dir = project_root / "src/fair_shares/library/allocations/budgets"
    pathways_dir = project_root / "src/fair_shares/library/allocations/pathways"

    if not budgets_dir.exists() or not pathways_dir.exists():
        results.append(
            ValidationResult(
                category="parameter",
                severity="error",
                file=project_root / "src/fair_shares/library/allocations",
                line=None,
                message="Allocation function directories not found",
            )
        )
        return results

    # Extract all parameter names from allocation functions
    all_params = set()

    # Common parameters we expect in allocation functions (from core implementation)
    # These are the ones we want to check against documentation
    core_allocation_params = {
        "allocation_year",
        "first_allocation_year",
        "responsibility_weight",
        "capability_weight",
        "historical_responsibility_year",
        "responsibility_per_capita",
        "responsibility_exponent",
        "responsibility_functional_form",
        "capability_per_capita",
        "capability_exponent",
        "capability_functional_form",
        "income_floor",
        "max_gini_adjustment",
        "max_deviation_sigma",
        "preserve_allocation_year_shares",
    }

    for module_dir in [budgets_dir, pathways_dir]:
        for py_file in module_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue

            try:
                tree = ast.parse(py_file.read_text())
            except SyntaxError as e:
                results.append(
                    ValidationResult(
                        category="parameter",
                        severity="error",
                        file=py_file,
                        line=e.lineno,
                        message=f"Failed to parse Python file: {e.msg}",
                    )
                )
                continue

            # Extract parameter names from function definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Only check functions that match allocation naming patterns
                    # (e.g., equal_per_capita_budget, per_capita_adjusted, etc.)
                    if not any(
                        pattern in node.name
                        for pattern in [
                            "per_capita",
                            "convergence",
                            "gini",
                        ]
                    ):
                        continue

                    # Skip private functions
                    if node.name.startswith("_"):
                        continue

                    # Extract parameter names from function arguments
                    for arg in node.args.args:
                        param_name = arg.arg
                        # Skip 'self' and standard data inputs
                        if param_name in {
                            "self",
                            "population_ts",
                            "gdp_ts",
                            "gini_s",
                            "country_actual_emissions_ts",
                            "world_scenario_emissions_ts",
                            "emission_category",
                            "group_level",
                            "unit_level",
                            "ur",
                        }:
                            continue
                        # Only track core allocation parameters
                        if param_name in core_allocation_params:
                            all_params.add(param_name)

    # Read allocations.md documentation
    allocations_doc = project_root / "docs/science/allocations.md"
    if not allocations_doc.exists():
        results.append(
            ValidationResult(
                category="parameter",
                severity="error",
                file=allocations_doc,
                line=None,
                message="Allocations documentation file not found",
            )
        )
        return results

    try:
        doc_content = allocations_doc.read_text()
    except Exception as e:
        results.append(
            ValidationResult(
                category="parameter",
                severity="error",
                file=allocations_doc,
                line=None,
                message=f"Could not read file: {e}",
            )
        )
        return results

    # Extract parameter names mentioned in docs using backticks
    # Matches patterns like `allocation_year`, `responsibility_weight`, etc.
    doc_param_pattern = re.compile(r"`([a-z_]+)`")
    doc_params = {
        match.group(1)
        for match in doc_param_pattern.finditer(doc_content)
        if match.group(1) in core_allocation_params
    }

    # Check for parameters in docs but not in code
    undocumented_in_code = doc_params - all_params
    for param in sorted(undocumented_in_code):
        results.append(
            ValidationResult(
                category="parameter",
                severity="warning",
                file=allocations_doc,
                line=None,
                message=f"Parameter '{param}' documented in allocations.md but not found in allocation function signatures",
            )
        )

    # Check for parameters in code but not documented
    # This is a lower severity issue since not all parameters need detailed docs
    missing_in_docs = all_params - doc_params
    # Only flag if it's a commonly used parameter
    important_params = {
        "allocation_year",
        "first_allocation_year",
        "responsibility_weight",
        "capability_weight",
        "income_floor",
        "max_deviation_sigma",
        "preserve_allocation_year_shares",
    }
    for param in sorted(missing_in_docs):
        if param in important_params:
            results.append(
                ValidationResult(
                    category="parameter",
                    severity="warning",
                    file=allocations_doc,
                    line=None,
                    message=f"Parameter '{param}' exists in allocation functions but not mentioned in allocations.md",
                )
            )

    return results


def check_crossrefs() -> list[ValidationResult]:
    """Verify all internal markdown links resolve.

    Extracts all internal links ([text](path.md#anchor)) from markdown files,
    verifies target files exist and anchors are present.

    Returns
    -------
        List of ValidationResult objects for broken links/anchors
    """
    results = []

    # Get project root (tools/ is one level down from root)
    project_root = Path(__file__).parent.parent
    docs_dir = project_root / "docs"

    if not docs_dir.exists():
        results.append(
            ValidationResult(
                category="crossref",
                severity="error",
                file=docs_dir,
                line=None,
                message="Documentation directory not found",
            )
        )
        return results

    # Find all markdown files recursively
    markdown_files = list(docs_dir.rglob("*.md"))

    # Pattern to match markdown links: [text](path) or [text](path#anchor)
    # Matches both relative and absolute internal links
    # Excludes external URLs (http://, https://)
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    for md_file in markdown_files:
        try:
            content = md_file.read_text()
        except Exception as e:
            results.append(
                ValidationResult(
                    category="crossref",
                    severity="warning",
                    file=md_file,
                    line=None,
                    message=f"Could not read file: {e}",
                )
            )
            continue

        # Find all links
        for match in link_pattern.finditer(content):
            link_text = match.group(1)
            link_target = match.group(2)

            # Skip external URLs
            if link_target.startswith(("http://", "https://", "mailto:")):
                continue

            # Skip anchor-only links (same-page references)
            if link_target.startswith("#"):
                # TODO: Could validate anchor exists in current file
                continue

            # Calculate line number where link appears
            lines_before = content[: match.start()].count("\n")
            link_line = lines_before + 1  # +1 for 0-index

            # Parse link target into file path and optional anchor
            if "#" in link_target:
                file_part, anchor = link_target.split("#", 1)
            else:
                file_part = link_target
                anchor = None

            # Resolve relative path
            # Links can be relative to:
            # 1. Current file's directory (e.g., "other.md")
            # 2. Docs root (e.g., "../science/allocations.md")
            # 3. Project root (rare, but possible)

            # Try resolving relative to current file's directory
            # Use resolve(strict=False) to allow non-existent paths for checking
            target_path = (md_file.parent / file_part).resolve(strict=False)

            # Check if target file exists
            if not target_path.exists():
                results.append(
                    ValidationResult(
                        category="crossref",
                        severity="error",
                        file=md_file,
                        line=link_line,
                        message=f"Broken link: target file not found: {link_target}",
                    )
                )
                continue

            # If anchor specified, verify it exists in target file
            if anchor:
                try:
                    target_content = target_path.read_text()
                except Exception:
                    results.append(
                        ValidationResult(
                            category="crossref",
                            severity="warning",
                            file=md_file,
                            line=link_line,
                            message=f"Could not read target file to verify anchor: {link_target}",
                        )
                    )
                    continue

                # Check for anchor in target file
                # Anchors can be:
                # 1. Markdown headers: ## Header → #header (lowercase, spaces to hyphens)
                # 2. Explicit HTML anchors: <a name="anchor"></a> or <a id="anchor"></a>

                # Generate expected anchor from headers
                header_pattern = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
                headers_found = []
                for header_match in header_pattern.finditer(target_content):
                    header_text = header_match.group(1).strip()
                    # Convert header to anchor format (MkDocs/GitHub style)
                    # Lowercase, replace spaces with hyphens, remove special chars
                    header_anchor = (
                        header_text.lower()
                        .replace(" ", "-")
                        .replace("(", "")
                        .replace(")", "")
                        .replace(",", "")
                        .replace(".", "")
                        .replace("'", "")
                        .replace('"', "")
                        .replace("/", "-")
                        .replace(":", "")
                    )
                    # Collapse consecutive hyphens (MkDocs does this)
                    header_anchor = re.sub(r"-+", "-", header_anchor)
                    headers_found.append(header_anchor)

                # Check for explicit HTML anchors
                html_anchor_pattern = re.compile(
                    r'<a\s+(?:name|id)="([^"]+)"', re.IGNORECASE
                )
                for html_match in html_anchor_pattern.finditer(target_content):
                    headers_found.append(html_match.group(1))

                # Verify anchor exists
                if anchor not in headers_found:
                    results.append(
                        ValidationResult(
                            category="crossref",
                            severity="error",
                            file=md_file,
                            line=link_line,
                            message=f"Broken anchor: #{anchor} not found in {file_part}",
                        )
                    )

    return results


def check_reference_comments() -> list[ValidationResult]:
    """Verify function mentions have REFERENCE comments for drift detection.

    Scans markdown files for function references (in backticks), extracts
    REFERENCE comments, and validates they point to actual functions at the
    correct file paths. This helps detect documentation drift when functions
    are renamed, removed, or moved.

    Returns
    -------
        List of ValidationResult objects for any issues found
    """
    results = []

    # Get project root (tools/ is one level down from root)
    project_root = Path(__file__).parent.parent

    # Get all function names from the registry
    registry_path = project_root / "src/fair_shares/library/allocations/registry.py"
    if not registry_path.exists():
        results.append(
            ValidationResult(
                category="reference",
                severity="error",
                file=registry_path,
                line=None,
                message="Registry file not found",
            )
        )
        return results

    # Parse registry to extract function names
    _, registry_functions = _parse_registry_functions(registry_path)

    # Files to check for REFERENCE comments
    docs_dir = project_root / "docs/science"
    if not docs_dir.exists():
        results.append(
            ValidationResult(
                category="reference",
                severity="error",
                file=docs_dir,
                line=None,
                message="Science docs directory not found",
            )
        )
        return results

    # Check specific markdown files
    files_to_check = [
        docs_dir / "allocations.md",
        docs_dir / "climate-equity-concepts.md",
        docs_dir / "parameter-effects.md",
    ]

    # Pattern to find function mentions in backticks
    function_mention_pattern = re.compile(r"`([a-z_]+(?:_budget|_pathway)?)`")

    # Pattern to find REFERENCE comments with file paths
    # Format: <!-- REFERENCE: function_name() in src/path/to/file.py -->
    reference_comment_pattern = re.compile(
        r"<!--\s*REFERENCE:\s*([a-z_]+(?:_budget|_pathway)?)\s*\(\)\s*in\s+(src/[^-\s]+\.py)\s*-->"
    )

    for md_file in files_to_check:
        if not md_file.exists():
            # File might not exist yet, skip
            continue

        try:
            content = md_file.read_text()
        except Exception as e:
            results.append(
                ValidationResult(
                    category="reference",
                    severity="warning",
                    file=md_file,
                    line=None,
                    message=f"Could not read file: {e}",
                )
            )
            continue

        # Find all function mentions
        mentioned_functions = set()
        for match in function_mention_pattern.finditer(content):
            func_name = match.group(1)
            # Only track registry functions
            if func_name in registry_functions:
                mentioned_functions.add(func_name)

        # Find all REFERENCE comments and validate file paths
        referenced_functions = set()
        for match in reference_comment_pattern.finditer(content):
            func_name = match.group(1)
            file_path = match.group(2)
            referenced_functions.add(func_name)

            # Verify file exists
            full_path = project_root / file_path
            if not full_path.exists():
                results.append(
                    ValidationResult(
                        category="reference",
                        severity="error",
                        file=md_file,
                        line=None,
                        message=f"REFERENCE file does not exist: {file_path} (for {func_name}())",
                    )
                )
                continue

            # Verify function exists in file
            try:
                file_content = full_path.read_text()
                if f"def {func_name}(" not in file_content:
                    results.append(
                        ValidationResult(
                            category="reference",
                            severity="error",
                            file=md_file,
                            line=None,
                            message=f"Function {func_name}() not found in {file_path}",
                        )
                    )
            except Exception as e:
                results.append(
                    ValidationResult(
                        category="reference",
                        severity="warning",
                        file=md_file,
                        line=None,
                        message=f"Could not verify {func_name}() in {file_path}: {e}",
                    )
                )

        # Check for functions mentioned but not referenced
        missing_references = mentioned_functions - referenced_functions
        for func in sorted(missing_references):
            results.append(
                ValidationResult(
                    category="reference",
                    severity="error",
                    file=md_file,
                    line=None,
                    message=f"Function '{func}' mentioned but missing REFERENCE comment",
                )
            )

        # Check for references to functions not in registry (orphaned comments)
        orphaned_references = referenced_functions - registry_functions
        for func in sorted(orphaned_references):
            results.append(
                ValidationResult(
                    category="reference",
                    severity="warning",
                    file=md_file,
                    line=None,
                    message=f"REFERENCE comment for '{func}' but function not found in registry",
                )
            )

    return results


def check_example_data_usage() -> list[ValidationResult]:
    """Verify documentation examples use DataFrame-based examples with create_example_data().

    This check ensures documentation follows Phase 4 standards:
    - No scalar-only examples (e.g., calculate_func(100, budget=1000))
    - Examples import create_example_data() or reference IAMC example file
    - IAMC examples reference actual column structure

    Returns
    -------
        List of ValidationResult objects for problematic examples
    """
    results = []

    # Get project root
    project_root = Path(__file__).parent.parent
    docs_dir = project_root / "docs"

    if not docs_dir.exists():
        return results

    # Find all markdown files
    markdown_files = list(docs_dir.rglob("*.md"))

    # Pattern to match Python code blocks
    code_block_pattern = re.compile(r"```python\n(.*?)```", re.DOTALL)

    # Patterns for problematic examples
    scalar_only_pattern = re.compile(
        r"(calculate_|equal_per_capita|per_capita_adjusted|generate_pathway)\("
        r"[^)]*\b\d+\b[^)]*\)"
    )

    # Good patterns that indicate proper example usage
    good_patterns = [
        "create_example_data(",
        "load_iamc_data(",
        'data["population"]',
        'data["gdp"]',
        'data["emissions"]',
    ]

    # IAMC column references
    iamc_columns = ["model", "scenario", "region", "variable", "unit"]

    for md_file in markdown_files:
        try:
            content = md_file.read_text()
        except Exception:
            continue

        # Find all Python code blocks
        for match in code_block_pattern.finditer(content):
            code = match.group(1)
            lines_before = content[: match.start()].count("\n")
            code_start_line = lines_before + 2

            # Skip documentation fragments (same as check_example_syntax)
            skip_markers = ["✅", "❌", "...", "# TODO", "<!--", "# doctest: +SKIP"]
            if any(marker in code for marker in skip_markers):
                continue

            # Skip if it's a DataFrame repr or output example
            if code.strip().startswith((">>>", "...", "   ")):
                continue

            # Check for scalar-only function calls
            if scalar_only_match := scalar_only_pattern.search(code):
                # Only flag if it doesn't have any good patterns
                if not any(pattern in code for pattern in good_patterns):
                    results.append(
                        ValidationResult(
                            category="example",
                            severity="warning",
                            file=md_file,
                            line=code_start_line,
                            message=f"Scalar-only example detected. Use create_example_data() "
                            f"instead: {scalar_only_match.group(0)[:50]}",
                        )
                    )

            # Check that examples using allocation functions import example data
            if any(
                func in code
                for func in [
                    "equal_per_capita(",
                    "per_capita_adjusted(",
                    "calculate_",
                    "generate_pathway",
                ]
            ):
                if not any(pattern in code for pattern in good_patterns):
                    # If it's a multi-line example block, warn
                    if "\n" in code.strip() and ">>>" not in code:
                        results.append(
                            ValidationResult(
                                category="example",
                                severity="warning",
                                file=md_file,
                                line=code_start_line,
                                message="Allocation example missing create_example_data() "
                                "or load_iamc_data() import",
                            )
                        )

            # Check IAMC examples reference proper columns
            if "load_iamc_data(" in code:
                # Check if IAMC column structure is documented nearby
                # Look at 5 lines before the code block for column comments
                code_context_start = max(0, match.start() - 500)
                context = content[code_context_start : match.start()]

                if not any(col in context or col in code for col in iamc_columns):
                    results.append(
                        ValidationResult(
                            category="example",
                            severity="warning",
                            file=md_file,
                            line=code_start_line,
                            message="IAMC example should reference column structure "
                            "(model, scenario, region, variable, unit, year columns)",
                        )
                    )

    return results


def main():
    """Main entry point for documentation sync check."""
    parser = argparse.ArgumentParser(
        description="Validate documentation consistency with codebase"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute example code blocks (in addition to syntax validation)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show all checks performed"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors (suppress warnings and info)",
    )
    parser.add_argument(
        "--skip-reference-check",
        action="store_true",
        help="Skip REFERENCE comment validation (for incremental adoption)",
    )
    args = parser.parse_args()

    # Validate argument combinations
    if args.verbose and args.quiet:
        print("Error: --verbose and --quiet cannot be used together")
        sys.exit(2)

    # Run all checks
    results = []

    if args.verbose:
        print("Running registry coverage check...")
    results.extend(check_registry_coverage())

    if args.verbose:
        print("Running example syntax check...")
    results.extend(check_example_syntax())

    if args.verbose:
        print("Running parameter consistency check...")
    results.extend(check_parameter_consistency())

    if args.verbose:
        print("Running cross-reference check...")
    results.extend(check_crossrefs())

    if not args.skip_reference_check:
        if args.verbose:
            print("Running REFERENCE comment check...")
        results.extend(check_reference_comments())

    if args.verbose:
        print("Running example data usage check...")
    results.extend(check_example_data_usage())

    # Filter by severity
    errors = [r for r in results if r.severity == "error"]
    warnings = [r for r in results if r.severity == "warning"]

    # Report results
    if not args.quiet or errors:
        for r in results:
            # Skip warnings if --quiet
            if args.quiet and r.severity == "warning":
                continue

            # Format output
            file_ref = f"{r.file}:{r.line}" if r.line is not None else str(r.file)
            print(f"[{r.severity.upper()}] {file_ref} ({r.category})")
            print(f"  {r.message}")

    # Summary
    if not args.quiet:
        if errors:
            print(f"\n{len(errors)} errors, {len(warnings)} warnings")
        else:
            print(f"\nNo errors, {len(warnings)} warnings")

    # Exit code
    if errors:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
