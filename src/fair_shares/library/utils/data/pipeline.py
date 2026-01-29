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
)


def build_data_paths(
    project_root: Path, source_id: str, emission_category: str
) -> dict[str, Path]:
    """
    Build all necessary paths for data processing pipeline.

    Used in the custom fair share allocation notebook.

    Parameters
    ----------
    project_root : Path
        Root directory of the project
    source_id : str
        Source identifier combining all data sources
    emission_category : str
        Emission category (e.g., "all-ghg", "co2-ffi")

    Returns
    -------
    dict[str, Path]
        Dictionary containing all relevant paths
    """
    base_dir = project_root / "output" / source_id
    processed_dir = base_dir / "intermediate" / "processed"

    return {
        "base_dir": base_dir,
        "processed_dir": processed_dir,
        "target_file": "master_preprocess",
        "country_emissions": processed_dir
        / f"country_emissions_{emission_category}_timeseries.csv",
        "country_gdp": processed_dir / "country_gdp_timeseries.csv",
        "country_population": processed_dir / "country_population_timeseries.csv",
        "country_gini": processed_dir / "country_gini_stationary.csv",
        "world_scenarios": processed_dir
        / f"world_scenarios_{emission_category}_complete.csv",
    }


def generate_snakemake_command(
    emission_category: str,
    target: str,
    active_sources: dict[str, str],
    target_file: Path,
) -> list[str]:
    """
    Generate Snakemake command for data setup.

    Used in the custom fair share allocation notebook.

    Parameters
    ----------
    emission_category : str
        Emission category (e.g., "all-ghg", "co2-ffi")
    target : str
        Target source (e.g., "ar6", "rcbs")
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

    # Pass rcb_generator if specified (for rcb-pathways target)
    rcb_generator = active_sources.get("rcb_generator")
    if rcb_generator:
        command.append(f"rcb_generator={rcb_generator}")

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
        Target source ("rcbs" or "ar6")

    Returns
    -------
    tuple[bool, dict[str, dict[str, Any]]]
        (all_files_exist, file_info_dict)
    """
    # Base required files (common to all modes)
    required_files = {
        "country_emissions": f"country_emissions_{emission_category}_timeseries.csv",
        "country_gdp": "country_gdp_timeseries.csv",
        "country_population": "country_population_timeseries.csv",
        "country_gini": "country_gini_stationary.csv",
    }

    # Add mode-specific files
    if target == "rcbs":
        # For RCB mode, check for RCB data file
        required_files["rcbs"] = "rcbs.csv"
    else:
        # For scenario mode, check for world scenarios file
        required_files["world_scenarios"] = (
            f"world_scenarios_{emission_category}_complete.csv"
        )

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


def setup_custom_data_pipeline(
    project_root: Path,
    emission_category: str,
    active_sources: dict[str, str],
    timeout: int = 600,
    verbose: bool = True,
    harmonisation_year: int | None = None,
) -> dict[str, Any]:
    """
    Set up the complete data pipeline for custom fair share allocations.

    This function handles the entire data setup process including:
    1. Extracting target from active_sources and inferring data source type
    2. Building validated configuration with Pydantic
    3. Building necessary paths
    4. Generating Snakemake commands
    5. Executing data preprocessing
    6. Verifying the setup

    Used in the custom fair share allocation notebook.

    Parameters
    ----------
    project_root : Path
        Root directory of the project
    emission_category : str
        Emission category ("all-ghg", "all-ghg-ex-co2-lulucf", "co2-ffi")
    active_sources : dict[str, str]
        Dictionary of active data sources. Must include keys:
        - "emissions": emissions source (e.g., "primap-202503")
        - "gdp": GDP source (e.g., "wdi-2025")
        - "population": population source (e.g., "un-owid-2025")
        - "gini": Gini source (e.g., "unu-wider-2025")
        - "target": target source (e.g., "ar6", "rcbs")
    timeout : int, default 600
        Timeout for Snakemake execution in seconds
    verbose : bool, default True
        Whether to print progress messages
    harmonisation_year : int | None, optional
        Year for global harmonisation. If None, will use value from config YAML
        if available, otherwise default to 2023 with a warning.

    Returns
    -------
    dict[str, Any]
        setup_info

        setup_info contains:
        - "paths": dict of all relevant paths
        - "command": Snakemake command used
        - "config": validated DataSourcesConfig from Pydantic
        - "execution": execution results (if auto_run_snakemake=True)
        - "verification": file verification results
        - "source_id": constructed source identifier
        - "alloc_tag": allocation tag
        - "data_tag": data tag
    """
    # Import here to avoid circular imports
    from fair_shares.library.utils.data.config import build_data_config

    # Extract target from active_sources
    target = active_sources.get("target")
    if not target:
        raise ConfigurationError("active_sources must include 'target' key")

    # Validate target
    if target not in ["ar6", "rcbs", "rcb-pathways"]:
        raise ConfigurationError(
            f"Invalid target: {target}. Must be 'ar6', 'rcbs', or 'rcb-pathways'"
        )

    # Build and validate configuration
    data_config, source_id = build_data_config(
        emission_category, active_sources, harmonisation_year=harmonisation_year
    )

    # Build paths
    paths = build_data_paths(project_root, source_id, emission_category)

    # Generate Snakemake command
    command = generate_snakemake_command(
        emission_category,
        target,
        active_sources,
        paths["target_file"],
    )

    setup_info = {
        "paths": paths,
        "command": command,
        "config": data_config,
        "source_id": source_id,
        "emission_category": emission_category,
    }

    if verbose:
        print("CUSTOM DATA PIPELINE SETUP")
        print(f"Target: {target}")
        print(f"Emission category: {emission_category}")
        print(f"Source ID: {source_id}")
        print(f"Target file: {paths['target_file']}")
        print()

    # Execute Snakemake
    # First, delete existing config file to force regeneration
    config_file = project_root / "output" / source_id / "config.yaml"
    if config_file.exists():
        if verbose:
            print(f"Removing existing config file to force regeneration: {config_file}")
        config_file.unlink()

    if verbose:
        print("Running Snakemake to set up data...")
        print("Command:", " ".join(command))
        print()

    stdout, stderr = execute_snakemake_setup(command, project_root, timeout)
    setup_info["execution"] = {"success": True, "stdout": stdout, "stderr": stderr}

    if verbose:
        print("Data setup completed successfully!")

    # Verify setup
    all_files_exist, file_info = verify_data_setup(
        paths["processed_dir"], emission_category, target
    )
    setup_info["verification"] = {
        "all_files_exist": all_files_exist,
        "file_info": file_info,
    }

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
        raise DataLoadingError("Some required data files are missing after setup")

    return setup_info
