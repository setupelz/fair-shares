"""Data coverage analysis for preprocessing."""

from pathlib import Path

import pandas as pd

from fair_shares.library.exceptions import DataLoadingError
from fair_shares.library.utils import (
    get_complete_iso3c_timeseries,
    last_year_column,
)

# Written by an emissions notebook (101) next to its timeseries file.
FIRST_RECORDED_YEAR_FILENAME = "emiss_{category}_first_recorded_year.csv"


def coverage_exclusions(
    countries: set[str],
    population: pd.DataFrame,
    coverage: dict | None,
    first_recorded_year: pd.Series | None = None,
) -> dict[str, str]:
    """Return {iso3c: reason} for the countries that fail the coverage rule.

    The rule is the ``coverage`` block of an emissions source in
    ``data_sources_unified.yaml``. A source without the block has no rule, and
    the result is empty. With the block, a country is an analysis country only
    if it passes each configured test:

    - ``emissions_recorded_before``: the raw emissions file holds a value for
      the country in a year before this one. A blank that the source fills
      with zero is not a record.
    - ``population_from``: the population series holds a value for every year
      from this one through its last year.

    A country that fails joins rest-of-world, whose rows are the world row
    minus the analysis countries. The country set is then the same for every
    allocation start year that the two thresholds cover.

    Args:
        countries: Countries to test
        population: Population DataFrame
        coverage: The ``coverage`` block, or None
        first_recorded_year: First recorded emissions year by iso3c. Required
            when ``emissions_recorded_before`` is set.

    Returns
    -------
        Reasons by iso3c, for the failing countries only
    """
    if not coverage:
        return {}
    reasons: dict[str, list[str]] = {}

    recorded_before = coverage.get("emissions_recorded_before")
    if recorded_before is not None:
        if first_recorded_year is None:
            raise DataLoadingError(
                "The coverage rule 'emissions_recorded_before' needs the first "
                "recorded year of each country, and none was given."
            )
        # A country without an entry has no record at all.
        first = first_recorded_year.reindex(sorted(countries))
        for iso3c in first.index[~(first < recorded_before)]:
            reasons.setdefault(iso3c, []).append(
                f"no emissions recorded before {recorded_before}"
            )

    population_from = coverage.get("population_from")
    if population_from is not None:
        complete = get_complete_iso3c_timeseries(
            population,
            expected_index_names=["iso3c", "unit"],
            start=population_from,
            end=last_year_column(population),
        )
        for iso3c in sorted(countries - complete):
            reasons.setdefault(iso3c, []).append(
                f"population incomplete from {population_from}"
            )

    return {iso3c: "; ".join(reasons[iso3c]) for iso3c in sorted(reasons)}


def source_coverage_exclusions(
    countries: set[str],
    population: pd.DataFrame,
    emissions_parameters: dict,
    emissions_dir: Path,
) -> dict[str, str]:
    """Apply the coverage rule of an emissions source to ``countries``.

    Reads the rule from the source's ``data_parameters`` and the first recorded
    years from the tables its notebook wrote to ``emissions_dir``. With several
    categories a country takes its latest first year.
    """
    coverage = emissions_parameters.get("coverage")
    if not coverage:
        return {}
    first_recorded_year = None
    if coverage.get("emissions_recorded_before") is not None:
        tables = []
        for category in emissions_parameters["available_categories"]:
            path = emissions_dir / FIRST_RECORDED_YEAR_FILENAME.format(
                category=category
            )
            if not path.exists():
                raise DataLoadingError(
                    f"First recorded year table not found: {path}. The coverage "
                    "rule 'emissions_recorded_before' needs it from notebook 101."
                )
            table = pd.read_csv(path).set_index("iso3c")["first_recorded_year"]
            tables.append(table)
        first_recorded_year = pd.concat(tables, axis=1).max(axis=1, skipna=False)
    return coverage_exclusions(countries, population, coverage, first_recorded_year)


def compute_analysis_countries(
    emissions_data: dict[str, pd.DataFrame],
    gdp: pd.DataFrame,
    population: pd.DataFrame,
    gini: pd.DataFrame | None = None,
    coverage: dict | None = None,
    first_recorded_year: pd.Series | None = None,
) -> set[str]:
    """Compute the set of countries with complete emissions, GDP and population.

    Gini is deliberately not part of this. A country without a Gini value used
    to be dropped from every allocation, including approaches that never look
    at inequality; it now stays in the analysis and its missing Gini is handled
    where Gini is actually used (see ``preprocessing.gini.complete_gini``).

    Args:
        emissions_data: Dictionary of emission category DataFrames
        gdp: GDP DataFrame
        population: Population DataFrame
        gini: Accepted for backwards compatibility and ignored.
        coverage: Opt-in coverage rule of the emissions source, or None
        first_recorded_year: First recorded emissions year by iso3c, for the rule

    Returns
    -------
        Set of ISO3C country codes with complete data
    """
    # Completeness is checked through each dataset's own last year so
    # countries without full coverage land in ROW via the intersection.
    emiss_analysis_countries = {}
    for category, emiss_df in emissions_data.items():
        emiss_analysis_countries[category] = get_complete_iso3c_timeseries(
            emiss_df,
            expected_index_names=["iso3c", "unit", "emission-category"],
            start=1990,
            end=last_year_column(emiss_df),
        )

    gdp_analysis_countries = get_complete_iso3c_timeseries(
        gdp,
        expected_index_names=["iso3c", "unit"],
        start=1990,
        end=last_year_column(gdp),
    )
    population_analysis_countries = get_complete_iso3c_timeseries(
        population,
        expected_index_names=["iso3c", "unit"],
        start=1990,
        end=last_year_column(population),
    )
    analysis_countries = gdp_analysis_countries & population_analysis_countries

    for category_countries in emiss_analysis_countries.values():
        analysis_countries = analysis_countries & category_countries

    excluded = coverage_exclusions(
        analysis_countries, population, coverage, first_recorded_year
    )
    return analysis_countries - set(excluded)


def create_coverage_summary(
    analysis_countries: set[str],
    emissions_data: dict[str, pd.DataFrame],
    gdp: pd.DataFrame,
    population: pd.DataFrame,
    gini: pd.DataFrame,
    region_mapping: pd.DataFrame,
    output_dir: Path,
    gdp_variant: str | None = None,
    coverage_rule_failed: dict[str, str] | None = None,
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
        coverage_rule_failed: Reasons from ``coverage_exclusions`` by iso3c.
            Adds the ``coverage_rule_failed`` column when given.

    Returns
    -------
        Coverage summary DataFrame
    """
    emiss_analysis_countries = {}
    for category, emiss_df in emissions_data.items():
        emiss_analysis_countries[category] = get_complete_iso3c_timeseries(
            emiss_df,
            expected_index_names=["iso3c", "unit", "emission-category"],
            start=1990,
            end=last_year_column(emiss_df),
        )

    gdp_analysis_countries = get_complete_iso3c_timeseries(
        gdp,
        expected_index_names=["iso3c", "unit"],
        start=1990,
        end=last_year_column(gdp),
    )
    population_analysis_countries = get_complete_iso3c_timeseries(
        population,
        expected_index_names=["iso3c", "unit"],
        start=1990,
        end=last_year_column(population),
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

    # An analysis country with no Gini value keeps its place and is given the
    # analysis-country mean. This column is the record of where that happened.
    coverage_summary["gini_imputed"] = (
        coverage_summary["in_analysis"] & ~coverage_summary["has_gini"]
    )

    # Add ROW indicator
    coverage_summary["in_row"] = coverage_summary["iso3c"].isin(
        all_region_countries
    ) & ~coverage_summary["iso3c"].isin(analysis_countries)

    # Sources with a coverage rule get one more column: the failed tests.
    if coverage_rule_failed is not None:
        coverage_summary["coverage_rule_failed"] = (
            coverage_summary["iso3c"].map(coverage_rule_failed).fillna("")
        )

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

    imputed_countries = coverage_summary[coverage_summary["gini_imputed"]][
        "iso3c"
    ].tolist()
    print(
        f"Countries in analysis with an imputed Gini: {len(imputed_countries)} "
        f"{sorted(imputed_countries)}"
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
