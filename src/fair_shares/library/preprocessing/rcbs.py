"""Remaining Carbon Budget (RCB) processing logic."""

from pathlib import Path

import pandas as pd
import yaml

from fair_shares.library.exceptions import ConfigurationError, DataLoadingError
from fair_shares.library.utils import (
    ensure_string_year_columns,
    process_rcb_to_2020_baseline,
)


def load_and_process_rcbs(
    rcb_yaml_path: Path,
    world_emissions_df: pd.DataFrame,
    emission_category: str,
    bunkers_2020_2100: float,
    lulucf_2020_2100: float,
    verbose: bool = True,
) -> pd.DataFrame:
    """Load and process RCB data from YAML configuration.

    Processes RCBs to 2020 baseline with bunkers and LULUCF adjustments.

    Args:
        rcb_yaml_path: Path to RCB YAML configuration file
        world_emissions_df: World emissions timeseries DataFrame
        emission_category: Emission category (must be "co2-ffi")
        bunkers_2020_2100: Bunkers emissions 2020-2100 in Mt CO2
        lulucf_2020_2100: LULUCF emissions 2020-2100 in Mt CO2
        verbose: Print processing details

    Returns
    -------
        DataFrame with processed RCB data
    """
    # Validate emission category
    if emission_category != "co2-ffi":
        raise ConfigurationError(
            f"RCB-based budget allocations only support 'co2-ffi' emission category. "
            f"Got: {emission_category}. Please use target: 'ar6' or 'cr' "
            f"in your configuration for other emission categories."
        )

    # Load RCB YAML
    if not rcb_yaml_path.exists():
        raise DataLoadingError(f"RCB YAML file not found: {rcb_yaml_path}")

    with open(rcb_yaml_path) as file:
        rcb_data = yaml.safe_load(file)

    if verbose:
        print("Loaded RCB data structure:")
        print(f"  Sources: {list(rcb_data['rcb_data'].keys())}")
        if rcb_data["rcb_data"]:
            first_source = next(iter(rcb_data["rcb_data"].keys()))
            first_data = rcb_data["rcb_data"][first_source]
            print(f"  Example source ({first_source}):")
            print(f"    Baseline year: {first_data.get('baseline_year')}")
            print(f"    Unit: {first_data.get('unit')}")
            print(f"    Scenarios: {list(first_data.get('scenarios', {}).keys())}")

    # Ensure world emissions has string year columns
    world_emissions_df = ensure_string_year_columns(world_emissions_df)

    if verbose:
        print("\nProcessing RCBs with adjustments:")
        print("  Target baseline year: 2020")
        print(f"  Bunkers adjustment: {bunkers_2020_2100} Mt CO2e")
        print(f"  LULUCF adjustment: {lulucf_2020_2100} Mt CO2e")

    # Create a list to store all RCB records
    rcb_records = []

    # Process each source
    for source_key, source_data in rcb_data["rcb_data"].items():
        if verbose:
            print(f"\n  Processing source: {source_key}")

        # Extract metadata from source
        baseline_year = source_data.get("baseline_year")
        unit = source_data.get("unit", "Gt CO2")
        scenarios = source_data.get("scenarios", {})

        # Validate required fields
        if baseline_year is None:
            raise ConfigurationError(
                f"RCB source '{source_key}' missing required field 'baseline_year'"
            )
        if not scenarios:
            raise ConfigurationError(
                f"RCB source '{source_key}' has no scenarios defined"
            )

        if verbose:
            print(f"    Baseline year: {baseline_year}")
            print(f"    Unit: {unit}")
            print(f"    Scenarios: {len(scenarios)}")

        # Process each scenario for this source
        for scenario, rcb_value in scenarios.items():
            # Parse scenario string into climate assessment and quantile
            # Format: "TEMPpPROB" (e.g., "1.5p50" -> 1.5C warming, 50% probability)
            parts = scenario.split("p")
            if len(parts) == 2:
                temperature = parts[0]
                probability = parts[1]
                climate_assessment = f"{temperature}C"
                quantile = str(int(probability) / 100)
            else:
                raise ValueError(f"Invalid RCB scenario format: {scenario}")

            # Process RCB to 2020 baseline
            result = process_rcb_to_2020_baseline(
                rcb_value=rcb_value,
                rcb_unit=unit,
                rcb_baseline_year=baseline_year,
                world_co2_ffi_emissions=world_emissions_df,
                bunkers_2020_2100=bunkers_2020_2100,
                lulucf_2020_2100=lulucf_2020_2100,
                target_baseline_year=2020,
                source_name=source_key,
                scenario=scenario,
                verbose=verbose,
            )

            # Create record with parsed climate assessment and quantile
            record = {
                "source": source_key,
                "scenario": scenario,
                "climate-assessment": climate_assessment,
                "quantile": quantile,
                "emission-category": emission_category,
                "baseline_year": baseline_year,
                "rcb_original_value": result["rcb_original_value"],
                "rcb_original_unit": result["rcb_original_unit"],
                "rcb_2020_mt": result["rcb_2020_mt"],
                "emissions_adjustment_mt": result["emissions_adjustment_mt"],
                "bunkers_adjustment_mt": result["bunkers_adjustment_mt"],
                "lulucf_adjustment_mt": result["lulucf_adjustment_mt"],
                "total_adjustment_mt": result["total_adjustment_mt"],
            }

            rcb_records.append(record)

    # Convert to DataFrame
    rcb_df = pd.DataFrame(rcb_records)

    if verbose:
        print("\nProcessed RCB data:")
        print(rcb_df.to_string(index=False))

    return rcb_df
