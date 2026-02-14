"""Scenario data harmonization and processing logic."""

import numpy as np
import pandas as pd

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils import (
    ensure_string_year_columns,
    set_post_net_zero_emissions_to_nan,
)


def process_complete_scenarios(
    scenarios_data: dict[str, pd.DataFrame],
    emiss_complete: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    """Process complete scenarios by harmonizing with historical data.

    Combines historical emissions with scenario projections, handles net-negative
    emissions, and creates complete timeseries for all climate assessments and quantiles.

    Args:
        scenarios_data: Dictionary of scenario DataFrames by emission category
        emiss_complete: Dictionary of complete historical emissions by category

    Returns
    -------
        Tuple of (complete_scenarios_dict, net_negative_metadata_dict)
    """
    all_complete_scenarios = {}
    net_negative_metadata_dict = {}

    for emission_category, category_scenarios in scenarios_data.items():
        if emission_category not in emiss_complete:
            raise DataProcessingError(
                f"Historical emissions for category '{emission_category}' not found "
                f"in complete emissions data. Available categories: {list(emiss_complete.keys())}"
            )

        # Get world historical emissions for this category
        category_emiss_complete_with_row = emiss_complete[emission_category]
        world_historical_emissions = category_emiss_complete_with_row.sum(axis=0)
        world_historical_df = pd.DataFrame(
            [world_historical_emissions], index=["World"]
        )
        world_historical_df.index.name = "iso3c"

        # Get scenario metadata
        scenario_groups = category_scenarios.index.get_level_values(
            "climate-assessment"
        ).unique()

        # Prepare world scenario time series
        world_mask_all = (
            category_scenarios.index.get_level_values("iso3c") == "World"
        ) & (category_scenarios.index.get_level_values("unit") == "Mt * CO2e")
        world_scenarios_only = category_scenarios[world_mask_all]

        # Get year columns
        year_cols = [col for col in world_scenarios_only.columns if str(col).isdigit()]

        # Convert to long format for net-negative handling
        df_reset = world_scenarios_only.reset_index()

        # Determine id_cols based on actual columns (excluding year columns)
        year_cols_in_df = [col for col in df_reset.columns if str(col).isdigit()]
        id_cols = [col for col in df_reset.columns if col not in year_cols_in_df]

        harmonized_long = df_reset.melt(
            id_vars=id_cols, var_name="year", value_name=emission_category
        )
        harmonized_long["year"] = harmonized_long["year"].astype(int)

        # Apply net-negative emissions handling to each climate assessment
        adjusted_groups = []
        all_metadata = []

        for climate_assessment in scenario_groups:
            median_df = harmonized_long[
                harmonized_long["climate-assessment"] == climate_assessment
            ].copy()

            adjusted_df, metadata = set_post_net_zero_emissions_to_nan(
                median_df, emission_category
            )
            adjusted_groups.append(adjusted_df)
            all_metadata.append({"climate-assessment": climate_assessment, **metadata})

        harmonized_adjusted = pd.concat(adjusted_groups, ignore_index=True)
        net_negative_metadata = {"pathways": all_metadata}

        # Store metadata
        net_negative_metadata_dict[emission_category] = net_negative_metadata

        # Convert back to wide format
        harmonized_world = harmonized_adjusted.pivot_table(
            index=[
                "climate-assessment",
                "quantile",
                "source",
                "iso3c",
                "unit",
                "emission-category",
            ],
            columns="year",
            values=emission_category,
            fill_value=np.nan,
        )
        harmonized_world.columns = harmonized_world.columns.astype(str)

        # Create complete scenarios by combining historical and harmonized data
        complete_scenarios = []

        # Filter to World scenarios only
        world_mask = (category_scenarios.index.get_level_values("iso3c") == "World") & (
            category_scenarios.index.get_level_values("unit") == "Mt * CO2e"
        )
        world_scenarios = category_scenarios[world_mask]

        # Iterate over all scenario rows
        for idx, row in world_scenarios.iterrows():
            climate_assessment = idx[0]
            quantile = idx[1]
            source = idx[2]
            scenario_series = row

            # Get all years from both datasets
            historical_years = [
                col for col in world_historical_df.columns if str(col).isdigit()
            ]
            scenario_years_available = [
                col
                for col in scenario_series.index
                if str(col).isdigit() and not pd.isna(scenario_series[col])
            ]

            # Create complete year range from historical start to scenario end
            all_years = sorted(set(historical_years + scenario_years_available))
            complete_years = [str(year) for year in all_years]

            # Create a new series with the complete year range
            complete_series = pd.Series(index=complete_years, dtype=float)

            # Fill with historical data where available
            for year in historical_years:
                if year in world_historical_df.iloc[0].index:
                    complete_series[year] = world_historical_df.iloc[0][year]

            # Override with harmonized scenario data where available
            key = (
                climate_assessment,
                quantile,
                source,
                "World",
                "Mt * CO2e",
                emission_category,
            )

            for year in scenario_years_available:
                if year in harmonized_world.columns and key in harmonized_world.index:
                    complete_series[year] = harmonized_world.loc[key, year]

            # Create DataFrame with standard index structure
            complete_df = pd.DataFrame(
                [complete_series],
                index=pd.MultiIndex.from_tuples(
                    [key],
                    names=[
                        "climate-assessment",
                        "quantile",
                        "source",
                        "iso3c",
                        "unit",
                        "emission-category",
                    ],
                ),
            )
            complete_scenarios.append(complete_df)

        # Combine all complete scenarios for this emission category
        if complete_scenarios:
            complete_scenarios_df = pd.concat(complete_scenarios)
            complete_scenarios_df = ensure_string_year_columns(complete_scenarios_df)
            all_complete_scenarios[emission_category] = complete_scenarios_df
        else:
            raise DataProcessingError(
                f"No complete scenarios created for {emission_category}"
            )

    return all_complete_scenarios, net_negative_metadata_dict
