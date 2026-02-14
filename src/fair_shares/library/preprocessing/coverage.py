"""Data coverage analysis for preprocessing."""

from pathlib import Path

import pandas as pd

from fair_shares.library.utils import get_complete_iso3c_timeseries


def compute_analysis_countries(
    emissions_data: dict[str, pd.DataFrame],
    gdp: pd.DataFrame,
    population: pd.DataFrame,
    gini: pd.DataFrame,
) -> set[str]:
    """Compute the set of countries with complete data across all datasets.

    Args:
        emissions_data: Dictionary of emission category DataFrames
        gdp: GDP DataFrame
        population: Population DataFrame
        gini: Gini coefficient DataFrame

    Returns
    -------
        Set of ISO3C country codes with complete data
    """
    # Get countries with complete data for each dataset
    emiss_analysis_countries = {}
    for category, emiss_df in emissions_data.items():
        emiss_analysis_countries[category] = get_complete_iso3c_timeseries(
            emiss_df,
            expected_index_names=["iso3c", "unit", "emission-category"],
            start=1990,
            end=2019,
        )

    gdp_analysis_countries = get_complete_iso3c_timeseries(
        gdp, expected_index_names=["iso3c", "unit"], start=1990, end=2023
    )
    population_analysis_countries = get_complete_iso3c_timeseries(
        population, expected_index_names=["iso3c", "unit"], start=1990, end=2019
    )
    gini_analysis_countries = set(gini.index.get_level_values("iso3c").tolist())

    # Find intersection of all datasets
    analysis_countries = (
        gdp_analysis_countries & population_analysis_countries & gini_analysis_countries
    )

    for category_countries in emiss_analysis_countries.values():
        analysis_countries = analysis_countries & category_countries

    return analysis_countries


def create_coverage_summary(
    analysis_countries: set[str],
    emissions_data: dict[str, pd.DataFrame],
    gdp: pd.DataFrame,
    population: pd.DataFrame,
    gini: pd.DataFrame,
    region_mapping: pd.DataFrame,
    output_dir: Path,
    gdp_variant: str | None = None,
) -> pd.DataFrame:
    """Create and save data coverage summary.

    Args:
        analysis_countries: Set of countries in final analysis
        emissions_data: Dictionary of emission category DataFrames
        gdp: GDP DataFrame
        population: Population DataFrame
        gini: Gini coefficient DataFrame
        region_mapping: Region mapping DataFrame with iso3c column
        output_dir: Directory to save coverage summary
        gdp_variant: Optional GDP variant name for reporting

    Returns
    -------
        Coverage summary DataFrame
    """
    # Get complete data countries for each dataset
    emiss_analysis_countries = {}
    for category, emiss_df in emissions_data.items():
        emiss_analysis_countries[category] = get_complete_iso3c_timeseries(
            emiss_df,
            expected_index_names=["iso3c", "unit", "emission-category"],
            start=1990,
            end=2019,
        )

    gdp_analysis_countries = get_complete_iso3c_timeseries(
        gdp, expected_index_names=["iso3c", "unit"], start=1990, end=2023
    )
    population_analysis_countries = get_complete_iso3c_timeseries(
        population, expected_index_names=["iso3c", "unit"], start=1990, end=2019
    )
    gini_analysis_countries = set(gini.index.get_level_values("iso3c").tolist())

    # Get all region countries
    all_region_countries = set(region_mapping["iso3c"].unique())

    # Create summary dataframe
    coverage_summary = pd.DataFrame({"iso3c": sorted(all_region_countries)})

    # Add coverage indicators for each dataset
    coverage_summary["has_emissions"] = True
    for category_countries in emiss_analysis_countries.values():
        coverage_summary["has_emissions"] = coverage_summary[
            "has_emissions"
        ] & coverage_summary["iso3c"].isin(category_countries)

    coverage_summary["has_gdp"] = coverage_summary["iso3c"].isin(gdp_analysis_countries)
    coverage_summary["has_population"] = coverage_summary["iso3c"].isin(
        population_analysis_countries
    )
    coverage_summary["has_gini"] = coverage_summary["iso3c"].isin(
        gini_analysis_countries
    )

    # Add final analysis indicator
    coverage_summary["in_analysis"] = coverage_summary["iso3c"].isin(analysis_countries)

    # Add ROW indicator
    coverage_summary["in_row"] = coverage_summary["iso3c"].isin(
        all_region_countries
    ) & ~coverage_summary["iso3c"].isin(analysis_countries)

    # Calculate summary statistics
    total_countries = len(coverage_summary)
    countries_with_emissions = coverage_summary["has_emissions"].sum()
    countries_with_gdp = coverage_summary["has_gdp"].sum()
    countries_with_population = coverage_summary["has_population"].sum()
    countries_with_gini = coverage_summary["has_gini"].sum()
    countries_in_analysis = coverage_summary["in_analysis"].sum()
    countries_in_row = coverage_summary["in_row"].sum()

    # Print summary
    print("\n=== Data Coverage Summary ===")
    print(f"Total countries in region mapping: {total_countries}")
    print(
        f"Countries with emissions data: {countries_with_emissions} "
        f"({countries_with_emissions / total_countries * 100:.1f}%)"
    )
    gdp_label = f"GDP data ({gdp_variant})" if gdp_variant else "GDP data"
    print(
        f"Countries with {gdp_label}: {countries_with_gdp} "
        f"({countries_with_gdp / total_countries * 100:.1f}%)"
    )
    print(
        f"Countries with population data: {countries_with_population} "
        f"({countries_with_population / total_countries * 100:.1f}%)"
    )
    print(
        f"Countries with Gini data: {countries_with_gini} "
        f"({countries_with_gini / total_countries * 100:.1f}%)"
    )

    print("\n=== Countries composition in final dataset ===")
    print(
        f"Countries independently complete in final dataset: {countries_in_analysis} "
        f"({countries_in_analysis / total_countries * 100:.1f}%)"
    )
    print(
        f"Countries clubbed in ROW in final dataset: {countries_in_row} "
        f"({countries_in_row / total_countries * 100:.1f}%)"
    )

    # Show countries in ROW
    row_countries = coverage_summary[coverage_summary["in_row"]]["iso3c"].tolist()
    print(f"\nCountries in ROW: {sorted(row_countries)}")

    # Show missing countries
    missing_emissions = coverage_summary[~coverage_summary["has_emissions"]][
        "iso3c"
    ].tolist()
    missing_gdp = coverage_summary[~coverage_summary["has_gdp"]]["iso3c"].tolist()
    missing_population = coverage_summary[~coverage_summary["has_population"]][
        "iso3c"
    ].tolist()
    missing_gini = coverage_summary[~coverage_summary["has_gini"]]["iso3c"].tolist()

    print(f"\nCountries missing emissions data: {sorted(missing_emissions)}")
    gdp_missing_label = f"GDP data ({gdp_variant})" if gdp_variant else "GDP data"
    print(f"Countries missing {gdp_missing_label}: {sorted(missing_gdp)}")
    print(f"Countries missing population data: {sorted(missing_population)}")
    print(f"Countries missing Gini data: {sorted(missing_gini)}")

    # Save coverage summary
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = output_dir / "country_data_coverage_summary.csv"
    coverage_summary.to_csv(coverage_path, index=False)
    print(f"\nData coverage summary saved to: {coverage_path}")

    return coverage_summary
