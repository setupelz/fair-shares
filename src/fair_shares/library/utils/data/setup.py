"""
Data pipeline utilities for running Snakemake workflows.

This module contains functions for executing and verifying the data processing pipeline
that prepares input data for fair share allocations.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from fair_shares.library.exceptions import (
    ConfigurationError,
    DataLoadingError,
    DataProcessingError,
    MissingPipelineDependency,
)
from fair_shares.library.paths import DATA_DIR_ENV, OUTPUT_DIR_ENV


def _enumerate_required_files(
    target: str | None, emission_category: str
) -> dict[str, str]:
    """Enumerate required file names keyed by logical role.

    Shared by ``build_data_paths`` and ``verify_data_setup`` to avoid
    duplicating the category-branching logic.
    """
    from fair_shares.library.utils.data.config import (
        get_final_categories,
        is_budget_target,
        is_composite_category,
    )

    files: dict[str, str] = {
        "country_gdp": "country_gdp_timeseries.csv",
        "country_population": "country_population_timeseries.csv",
        "country_gini": "country_gini_stationary.csv",
    }

    final_cats = get_final_categories(target, emission_category)

    if is_composite_category(emission_category) and len(final_cats) > 1:
        for cat in final_cats:
            files[f"country_emissions_{cat}"] = (
                f"country_emissions_{cat}_timeseries.csv"
            )
            if is_budget_target(target, cat):
                files[f"rcbs_{cat}"] = f"rcbs_{cat}.csv"
                files[f"world_emissions_{cat}"] = (
                    f"world_emissions_{cat}_timeseries.csv"
                )
            else:
                files[f"world_scenarios_{cat}"] = f"world_scenarios_{cat}_complete.csv"
    else:
        cat = final_cats[0]
        files["country_emissions"] = f"country_emissions_{cat}_timeseries.csv"
        if is_budget_target(target, cat):
            files["rcbs"] = f"rcbs_{cat}.csv"
        else:
            files["world_scenarios"] = f"world_scenarios_{cat}_complete.csv"

    return files


def build_data_paths(
    output_dir: Path,
    source_id: str,
    emission_category: str,
    target: str | None = None,
) -> dict[str, Path]:
    """
    Build all necessary paths for data processing pipeline.

    Used in the custom fair share allocation notebook.

    For composite categories that need decomposition (RCBs + all-ghg or
    all-ghg-ex-co2-lulucf), returns per-category path keys:
    ``country_emissions_co2``, ``country_emissions_non-co2``,
    ``rcbs_co2``, ``world_emissions_co2``, ``world_scenarios_non-co2``.

    For pathway targets + composite or any non-composite category, returns
    single-category keys: ``country_emissions``, ``world_scenarios``
    (or ``rcbs``).

    Parameters
    ----------
    output_dir : Path
        Directory holding pipeline products (``output/`` in a checkout)
    source_id : str
        Source identifier combining all data sources
    emission_category : str
        Emission category (e.g., "all-ghg", "co2-ffi")
    target : str | None, optional
        Target source type. Determines whether composite categories are
        decomposed (RCBs) or kept as single categories (pathway).

    Returns
    -------
    dict[str, Path]
        Dictionary containing all relevant paths
    """
    base_dir = Path(output_dir) / source_id
    processed_dir = base_dir / "intermediate" / "processed"

    paths: dict[str, Path] = {
        "base_dir": base_dir,
        "processed_dir": processed_dir,
        "target_file": "master_preprocess",
    }
    for key, filename in _enumerate_required_files(target, emission_category).items():
        paths[key] = processed_dir / filename

    return paths


def generate_snakemake_command(
    emission_category: str,
    target: str,
    active_sources: dict[str, str],
    target_file: Path,
    harmonisation_year: int | None = None,
) -> list[str]:
    """
    Generate Snakemake command for data setup.

    Used in the custom fair share allocation notebook.

    Parameters
    ----------
    emission_category : str
        Emission category (e.g., "all-ghg", "co2-ffi")
    target : str
        Target source (e.g., "pathway", "rcbs")
    active_sources : dict[str, str]
        Dictionary of active data sources
    target_file : Path
        Target file to build

    Returns
    -------
    list[str]
        Snakemake command as list of strings
    """
    command = [
        "snakemake",
        "--cores",
        "1",
        "--config",
        f"emission_category={emission_category}",
        f"active_emissions_source={active_sources['emissions']}",
        f"active_gdp_source={active_sources['gdp']}",
        f"active_population_source={active_sources['population']}",
        f"active_gini_source={active_sources['gini']}",
        f"active_target_source={target}",
    ]

    # Pass lulucf source (required for NGHGI corrections)
    lulucf_source = active_sources.get("lulucf")
    if lulucf_source:
        command.append(f"active_lulucf_source={lulucf_source}")

    # Pass rcb_generator if specified (for rcb-pathways target)
    rcb_generator = active_sources.get("rcb_generator")
    if rcb_generator:
        command.append(f"rcb_generator={rcb_generator}")

    # Pass harmonisation_year so pathway generation starts at the right year
    if harmonisation_year is not None:
        command.append(f"harmonisation_year={harmonisation_year}")

    command.extend(["--", str(target_file)])  # Separate config from targets

    return command


def _extract_notebook_error(stderr: str) -> str | None:
    """Extract the actual notebook error from Snakemake output."""
    lines = stderr.split("\n")

    # Find the notebook error section
    in_error_section = False
    error_lines = []

    for line in lines:
        if "NOTEBOOK EXECUTION FAILED" in line:
            in_error_section = True
            continue
        if in_error_section:
            if line.startswith("RuleException:") or line.startswith("["):
                break
            error_lines.append(line)

    if error_lines:
        return "\n".join(error_lines).strip()
    return None


def execute_snakemake_setup(
    command: list[str], project_root: Path, timeout: int = 600
) -> tuple[str, str]:
    """
    Execute Snakemake command for data setup.

    Used in the custom fair share allocation notebook.

    Parameters
    ----------
    command : list[str]
        Snakemake command as list of strings
    project_root : Path
        Root directory of the project
    timeout : int, default 600
        Timeout in seconds (10 minutes default)

    Returns
    -------
    tuple[str, str]
        (stdout, stderr)
    """
    try:
        # First, sync Python files to Jupyter notebooks using jupytext
        sync_cmd = ["uv", "run", "jupytext", "--sync", "notebooks/*.py"]
        try:
            sync_result = subprocess.run(
                sync_cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,  # 1 minute for sync
            )
        except subprocess.TimeoutExpired:
            raise DataProcessingError("Jupytext sync timed out after 1 minute")

        if sync_result.returncode != 0:
            raise DataProcessingError(f"Jupytext sync failed: {sync_result.stderr}")

        result = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if result.returncode != 0:
            # Try to extract the notebook error first
            notebook_error = _extract_notebook_error(result.stderr)

            if notebook_error:
                # Show just the notebook error - it's clear and concise
                raise DataProcessingError(
                    f"Notebook execution failed:\n\n{notebook_error}"
                )
            else:
                # Fallback to full Snakemake output
                raise DataProcessingError(
                    f"Snakemake execution failed:\n\n{result.stderr}"
                )
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        raise DataProcessingError(
            f"Snakemake command timed out after {timeout} seconds"
        )
    except FileNotFoundError:
        raise DataProcessingError("Snakemake not found - please ensure it's installed")
    except DataProcessingError:
        # Re-raise DataProcessingError without modification to preserve original error
        raise
    except Exception as e:
        raise DataProcessingError(f"Unexpected error during Snakemake execution: {e!s}")


def verify_data_setup(
    processed_dir: Path, emission_category: str, target: str
) -> tuple[bool, dict[str, dict[str, Any]]]:
    """
    Verify that all required data files exist and get their information.

    Used in the custom fair share allocation notebook.

    Parameters
    ----------
    processed_dir : Path
        Directory containing processed data files
    emission_category : str
        Emission category for file naming
    target : str
        Target source ("rcbs" or "pathway")

    Returns
    -------
    tuple[bool, dict[str, dict[str, Any]]]
        (all_files_exist, file_info_dict)
    """
    required_files = _enumerate_required_files(target, emission_category)

    all_files_exist = True
    file_info = {}

    for file_type, filename in required_files.items():
        file_path = processed_dir / filename
        exists = file_path.exists()

        if exists:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            file_info[file_type] = {
                "path": file_path,
                "exists": True,
                "size_mb": size_mb,
            }
        else:
            file_info[file_type] = {"path": file_path, "exists": False, "size_mb": 0.0}
            all_files_exist = False

    return all_files_exist, file_info


def resolve_data_setup(
    emission_category: str,
    active_sources: dict[str, str],
    verbose: bool = True,
    harmonisation_year: int | None = None,
    output_dir: Path | str | None = None,
    data_dir: Path | str | None = None,
) -> dict[str, Any]:
    """
    Resolve configuration, paths and file state for a fair share allocation.

    Validates the target, builds the Pydantic config, constructs the output
    paths and reports which required files already exist. Runs no subprocess and
    needs no Snakemake, so it works from an installed wheel pointed at a
    prebuilt data tree.

    It is not, however, guaranteed to be cheap or offline. Building the config
    validates the configured data paths, and a path that is missing but names a
    registered source is downloaded at that point — which for PRIMAP is 72 MB.
    Set ``FAIR_SHARES_AUTO_FETCH=0`` to turn that off and get a missing-file
    error instead. See :mod:`fair_shares.library.data_fetch`.

    Parameters
    ----------
    emission_category : str
        Emission category ("all-ghg", "all-ghg-ex-co2-lulucf", "co2-ffi")
    active_sources : dict[str, str]
        Dictionary of active data sources. Must include keys:
        - "emissions": emissions source (e.g., "primap-202503")
        - "gdp": GDP source (e.g., "wdi-2025")
        - "population": population source (e.g., "un-owid-2025")
        - "gini": Gini source (e.g., "unu-wider-2025")
        - "lulucf": LULUCF source (e.g., "melo-2026") — required for NGHGI corrections
        - "target": target source (e.g., "pathway", "rcbs")
    verbose : bool, default True
        Whether to print progress messages
    harmonisation_year : int | None, optional
        Year for global harmonisation. If None, will use value from config YAML
        if available, otherwise default to 2023 with a warning.
    output_dir, data_dir : Path | str | None, optional
        Product and input directories. Default to the resolved directories
        (see :mod:`fair_shares.library.paths`). When given, they seed
        process-wide resolution so the config's own relative ``path:`` values
        resolve against them too.

    Returns
    -------
    dict[str, Any]
        setup_info containing "paths", "command", "config", "source_id",
        "emission_category", "final_categories", "target" and "verification".
        Unlike :func:`setup_data` it never contains "execution".
    """
    # Import here to avoid circular imports
    from fair_shares.library.paths import configure
    from fair_shares.library.paths import output_dir as resolve_output_dir
    from fair_shares.library.utils.data.config import (
        ALL_TARGETS,
        build_data_config,
        get_final_categories,
    )

    # Seed the resolver before build_data_config, whose validation resolves the
    # config's relative data paths through the same machinery.
    configure(data_dir=data_dir, output_dir=output_dir)

    target = active_sources.get("target")
    if not target:
        raise ConfigurationError("active_sources must include 'target' key")

    if target not in ALL_TARGETS:
        raise ConfigurationError(
            f"Invalid target: {target}. Must be one of: {sorted(ALL_TARGETS)}"
        )

    # Build and validate configuration
    data_config, source_id = build_data_config(
        emission_category, active_sources, harmonisation_year=harmonisation_year
    )

    resolved_output = resolve_output_dir(output_dir)

    # Build paths (target-aware: per-category keys for allghg)
    paths = build_data_paths(
        resolved_output, source_id, emission_category, target=target
    )

    # Generate Snakemake command
    command = generate_snakemake_command(
        emission_category,
        target,
        active_sources,
        paths["target_file"],
        harmonisation_year=harmonisation_year,
    )

    final_categories = get_final_categories(target, emission_category)

    all_files_exist, file_info = verify_data_setup(
        paths["processed_dir"], emission_category, target
    )

    setup_info: dict[str, Any] = {
        "paths": paths,
        "command": command,
        "config": data_config,
        "source_id": source_id,
        "emission_category": emission_category,
        "final_categories": final_categories,
        "target": target,
        "output_dir": resolved_output,
        "verification": {
            "all_files_exist": all_files_exist,
            "file_info": file_info,
        },
    }

    if verbose:
        print("CUSTOM DATA PIPELINE SETUP")
        print(f"Target: {target}")
        print(f"Emission category: {emission_category}")
        print(f"Source ID: {source_id}")
        print(f"Target file: {paths['target_file']}")
        print()

    return setup_info


def build_data_setup(
    setup_info: dict[str, Any],
    timeout: int = 600,
    verbose: bool = True,
    repo_root: Path | str | None = None,
) -> dict[str, Any]:
    """
    Run the Snakemake build for a resolved setup, in place.

    Clone-only. Snakemake reads the ``Snakefile`` and the ``notebooks/``
    sources from a checkout, so this cannot run from an installed wheel no
    matter how the data directories resolve.

    Parameters
    ----------
    setup_info : dict[str, Any]
        The dict returned by :func:`resolve_data_setup`. Mutated in place with
        an "execution" key and a refreshed "verification".
    timeout : int, default 600
        Timeout for Snakemake execution in seconds
    verbose : bool, default True
        Whether to print progress messages
    repo_root : Path | str | None, optional
        The checkout to run Snakemake in. Autodetected when omitted.

    Raises
    ------
    MissingPipelineDependency
        If the pipeline extra is not installed, or no checkout can be found.
    """
    from fair_shares.library.paths import find_repo_root

    _require_pipeline_dependencies()

    resolved_root = Path(repo_root) if repo_root is not None else find_repo_root()
    if resolved_root is None:
        raise MissingPipelineDependency(
            "Building the data tree requires a fair-shares checkout — Snakemake "
            "reads the Snakefile and notebooks/ from the repository, which are "
            "not shipped in the wheel. Either run from inside a checkout, or "
            f"point {DATA_DIR_ENV} and {OUTPUT_DIR_ENV} at a prebuilt data tree."
        )

    command = setup_info["command"]

    if verbose:
        print("Running Snakemake...")
        print("Command:", " ".join(command))
        print()

    stdout, stderr = execute_snakemake_setup(command, resolved_root, timeout)
    setup_info["execution"] = {"success": True, "stdout": stdout, "stderr": stderr}

    if verbose:
        print("Data setup completed successfully!")

    all_files_exist, file_info = verify_data_setup(
        setup_info["paths"]["processed_dir"],
        setup_info["emission_category"],
        setup_info["target"],
    )
    setup_info["verification"] = {
        "all_files_exist": all_files_exist,
        "file_info": file_info,
    }
    return setup_info


def _require_pipeline_dependencies() -> None:
    """Raise a MissingPipelineDependency naming the extra, if it is absent."""
    import importlib.util

    missing = [
        name
        for name in ("snakemake", "jupytext", "papermill")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise MissingPipelineDependency(
            "Building the data tree needs the pipeline toolchain, but "
            f"{', '.join(sorted(missing))} "
            f"{'is' if len(missing) == 1 else 'are'} not installed. Either run "
            'pip install "fair-shares[pipeline]", or point '
            f"{DATA_DIR_ENV} and {OUTPUT_DIR_ENV} at a prebuilt data tree."
        )


def setup_data(
    project_root: Path | None = None,
    emission_category: str = "",
    active_sources: dict[str, str] | None = None,
    timeout: int = 600,
    verbose: bool = True,
    harmonisation_year: int | None = None,
    data_dir: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """
    Set up the complete data pipeline for custom fair share allocations.

    Resolves configuration and paths, then builds the data tree with Snakemake
    **only when required files are missing**. A prebuilt tree therefore costs
    no Snakemake startup, and an installed wheel pointed at one never needs the
    pipeline extra at all.

    Used in the custom fair share allocation notebook.

    Parameters
    ----------
    project_root : Path | None, optional
        Deprecated. When given, ``project_root/"output"`` is used as the output
        directory. Pass ``output_dir`` instead.
    emission_category : str
        Emission category ("all-ghg", "all-ghg-ex-co2-lulucf", "co2-ffi")
    active_sources : dict[str, str]
        Dictionary of active data sources — see :func:`resolve_data_setup`.
    timeout : int, default 600
        Timeout for Snakemake execution in seconds
    verbose : bool, default True
        Whether to print progress messages
    harmonisation_year : int | None, optional
        Year for global harmonisation. If None, will use value from config YAML
        if available, otherwise default to 2023 with a warning.
    data_dir, output_dir : Path | str | None, optional
        Explicit input and product directories. Default to the resolved
        directories (see :mod:`fair_shares.library.paths`).

    Returns
    -------
    dict[str, Any]
        setup_info. Contains "paths", "command", "config", "source_id",
        "emission_category", "final_categories" and "verification"; "execution"
        is present only when a Snakemake build actually ran.
    """
    if active_sources is None:
        raise ConfigurationError("active_sources is required")

    repo_root: Path | None = None
    if project_root is not None:
        data_dir, output_dir = _deprecate_project_root(
            project_root, data_dir, output_dir, "setup_data"
        )
        repo_root = Path(project_root)

    setup_info = resolve_data_setup(
        emission_category=emission_category,
        active_sources=active_sources,
        verbose=verbose,
        harmonisation_year=harmonisation_year,
        output_dir=output_dir,
        data_dir=data_dir,
    )

    if not setup_info["verification"]["all_files_exist"]:
        build_data_setup(
            setup_info, timeout=timeout, verbose=verbose, repo_root=repo_root
        )

    file_info = setup_info["verification"]["file_info"]
    all_files_exist = setup_info["verification"]["all_files_exist"]

    if verbose:
        print("\nDATA VERIFICATION")
        for file_type, info in file_info.items():
            status = "OK" if info["exists"] else "MISSING"
            size_info = f" ({info['size_mb']:.1f} MB)" if info["exists"] else ""
            print(f"  {file_type}: {status}{size_info}")

        if all_files_exist:
            print("\nAll required data files found!")
        else:
            print("\nSome data files are missing.")

    if not all_files_exist:
        missing = sorted(k for k, v in file_info.items() if not v["exists"])
        raise DataLoadingError(
            f"Some required data files are missing after setup: {missing}"
        )

    return setup_info


def _deprecate_project_root(
    project_root: Path | str,
    data_dir: Path | str | None,
    output_dir: Path | str | None,
    caller: str,
) -> tuple[Path | str, Path | str]:
    """Map a deprecated ``project_root`` onto the data and output directories.

    ``project_root/"data"`` and ``project_root/"output"`` reproduce the layout
    the argument used to imply, so existing callers keep resolving to exactly
    the same files. Explicit ``data_dir`` / ``output_dir`` win.
    """
    import warnings

    warnings.warn(
        f"{caller}(project_root=...) is deprecated; pass data_dir= and "
        "output_dir= instead, or set FAIR_SHARES_DATA_DIR / "
        "FAIR_SHARES_OUTPUT_DIR.",
        DeprecationWarning,
        stacklevel=3,
    )
    root = Path(project_root)
    return (
        data_dir if data_dir is not None else root / "data",
        output_dir if output_dir is not None else root / "output",
    )


def lookup_net_negative_emissions(
    net_negative_metadata: dict,
    emission_category: str,
    climate_assessment: str,
) -> float | None:
    """Look up cumulative net-negative emissions for a category and climate assessment.

    Parameters
    ----------
    net_negative_metadata : dict
        Metadata dict keyed by emission category, each containing a "pathways" list.
    emission_category : str
        The emission category to look up (e.g., "co2-ffi", "co2").
    climate_assessment : str
        The climate assessment identifier to match.

    Returns
    -------
    float | None
        The cumulative net-negative emissions value, or None if not found.
    """
    if emission_category not in net_negative_metadata:
        return None
    for pathway in net_negative_metadata[emission_category].get("pathways", []):
        if pathway.get("climate-assessment") == climate_assessment:
            return pathway.get("cumulative_net_negative_emissions", 0.0)
    return None
