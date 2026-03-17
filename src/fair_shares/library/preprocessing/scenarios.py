"""Scenario data harmonization and processing logic."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.library.utils import (
    ensure_string_year_columns,
    harmonize_to_historical_with_convergence,
    interpolate_scenarios_data,
    set_post_net_zero_emissions_to_nan,
)

# CO2 categories for which post-net-zero NaN masking applies.
# Non-CO2 gases rarely reach net-zero within the scenario timeframe;
# brief sub-zero dips are modelling artefacts (e.g. AFOLU CH4).
_CO2_CATEGORIES: frozenset[str] = frozenset({"co2-ffi", "co2", "co2-lulucf"})


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

        # Apply net-negative emissions handling to each climate assessment.
        # Skip for non-CO2 categories (see _CO2_CATEGORIES docstring).
        adjusted_groups = []
        all_metadata = []

        for climate_assessment in scenario_groups:
            median_df = harmonized_long[
                harmonized_long["climate-assessment"] == climate_assessment
            ].copy()

            if emission_category in _CO2_CATEGORIES:
                adjusted_df, metadata = set_post_net_zero_emissions_to_nan(
                    median_df, emission_category
                )
            else:
                adjusted_df = median_df
                metadata = {}
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


def harmonise_and_median_ar6_pathways(
    var_long: pd.DataFrame,
    emission_category: str,
    historical_data: pd.DataFrame | None,
    anchor_year: int,
    convergence_year: int,
    interpolation_method: str,
    pathway_index_cols: list[str],
    source_name: str,
    target_unit: str = "Mt * CO2e",
) -> pd.DataFrame:
    """Interpolate, harmonise, and median-aggregate AR6 individual pathways.

    Encapsulates the notebook-104 pipeline that converts individual AR6 pathways
    into a single median timeseries suitable for downstream budget calculations.

    Pipeline steps:
    1. Interpolate to annual timesteps via ``interpolate_scenarios_data()``.
    2. Harmonise each individual pathway to historical at ``anchor_year`` using
       ``harmonize_to_historical_with_convergence(preserve_cumulative_peak=True)``.
    3. Compute the median across harmonised pathways (groupby climate-assessment).
    4. Apply ``set_post_net_zero_emissions_to_nan()``.
    5. Pivot to wide format with a 6-level MultiIndex matching the rest of the
       pipeline:
       ``(climate-assessment, quantile, source, iso3c, unit, emission-category)``.

    Parameters
    ----------
    var_long : pd.DataFrame
        Long-format DataFrame of individual AR6 pathways.  Must contain
        columns: ``year``, ``iso3c``, ``unit``, ``climate-assessment``,
        ``model``, ``scenario``, plus ``emission_category`` as the value column.
    emission_category : str
        Name of the emission value column (e.g. ``"co2-ffi"``).
    historical_data : pd.DataFrame or None
        Wide-format historical timeseries (one row, year columns as strings) to
        harmonise against.  If ``None``, harmonisation is skipped.
    anchor_year : int
        Year at which all pathways are matched to historical.
    convergence_year : int
        Year by which pathways return to their original trajectory.
    interpolation_method : str
        ``"linear"`` or ``"stepwise"`` — passed to ``interpolate_scenarios_data()``.
    pathway_index_cols : list[str]
        Index column list for ``interpolate_scenarios_data()``, must include
        ``"year"`` and all pathway grouping columns.
    source_name : str
        Label written into the ``source`` index level (e.g. ``"ar6"``).
    target_unit : str
        Unit string written into the ``unit`` index level. Default ``"Mt * CO2e"``.

    Returns
    -------
    pd.DataFrame
        Wide-format DataFrame with a 6-level MultiIndex:
        ``(climate-assessment, quantile, source, iso3c, unit, emission-category)``.
        Columns are string year labels.

    Raises
    ------
    DataProcessingError
        If ``var_long`` is empty, or if required columns are missing.
    """
    if var_long.empty:
        raise DataProcessingError(
            f"Input pathway data for '{emission_category}' is empty."
        )

    required_cols = {"year", "iso3c", "unit", "climate-assessment", emission_category}
    missing = required_cols - set(var_long.columns)
    if missing:
        raise DataProcessingError(
            f"var_long is missing required columns for '{emission_category}': {missing}"
        )

    # Step 1: Interpolate to annual timesteps
    var_long_annual = interpolate_scenarios_data(
        var_long, interpolation_method, pathway_index_cols
    )

    groupby_cols = ["climate-assessment", "iso3c", "unit", "year"]

    # Step 2: Harmonise individual pathways (if historical data is available)
    if historical_data is not None:
        pathway_id_cols = [col for col in pathway_index_cols if col != "year"]

        var_wide = var_long_annual.pivot_table(
            index=pathway_id_cols,
            columns="year",
            values=emission_category,
            fill_value=None,
        )
        var_wide = ensure_string_year_columns(var_wide)

        # Broadcast historical row to each pathway row
        historical_broadcast = pd.DataFrame(
            np.tile(historical_data.iloc[0].values, (len(var_wide), 1)),
            index=pd.MultiIndex.from_tuples(var_wide.index, names=var_wide.index.names),
            columns=historical_data.columns,
        )
        historical_broadcast = ensure_string_year_columns(historical_broadcast)

        var_wide_harmonized = harmonize_to_historical_with_convergence(
            var_wide,
            historical_broadcast,
            anchor_year,
            convergence_year,
            preserve_cumulative_peak=True,
        )

        # Back to long format
        var_long_harmonized = var_wide_harmonized.reset_index().melt(
            id_vars=pathway_id_cols, var_name="year", value_name=emission_category
        )
        var_long_harmonized["year"] = var_long_harmonized["year"].astype(int)
    else:
        var_long_harmonized = var_long_annual

    # Step 3: Compute median across harmonised pathways
    var_grouped = (
        var_long_harmonized.groupby(groupby_cols)
        .agg({emission_category: "median"})
        .reset_index()
    )
    var_grouped["quantile"] = 0.5

    # Step 4: Apply post-net-zero NaN masking per climate assessment.
    # Skip for non-CO2 categories (see _CO2_CATEGORIES docstring).
    adjusted_groups = []
    for climate_assessment in var_grouped["climate-assessment"].unique():
        ca_df = var_grouped[
            var_grouped["climate-assessment"] == climate_assessment
        ].copy()
        if emission_category in _CO2_CATEGORIES:
            adjusted_df, _ = set_post_net_zero_emissions_to_nan(
                ca_df, emission_category
            )
        else:
            adjusted_df = ca_df
        adjusted_groups.append(adjusted_df)

    var_median = pd.concat(adjusted_groups, ignore_index=True)

    # Step 5: Pivot to wide format with 6-level MultiIndex
    timeseries_wide = var_median.pivot_table(
        index=["climate-assessment", "quantile", "iso3c"],
        columns="year",
        values=emission_category,
        fill_value=None,
    )
    timeseries_wide = ensure_string_year_columns(timeseries_wide)

    timeseries_wide.index = pd.MultiIndex.from_tuples(
        [
            (ca, q, source_name, iso3c, target_unit, emission_category)
            for ca, q, iso3c in timeseries_wide.index
        ],
        names=[
            "climate-assessment",
            "quantile",
            "source",
            "iso3c",
            "unit",
            "emission-category",
        ],
    )

    return timeseries_wide
