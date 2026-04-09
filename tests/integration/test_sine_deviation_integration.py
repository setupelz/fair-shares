"""
Integration tests for sine-deviation convergence with realistic country data.

These tests exercise the sine-deviation convergence method (Dekker Eqs. 7-8)
through the full `cumulative_per_capita_convergence` pipeline using
realistic-shaped data for ~15 countries. They complement the unit tests in
`tests/unit/test_sine_deviation_convergence.py`, which use synthetic 3-country
fixtures.

Coverage:
- Shares sum to 1.0 per year with realistic asymmetric profiles
- Shares are non-negative under real-world emission asymmetry
- Cumulative budget conservation across all countries
- Directional equity behavior: high per-capita emitters lose share, low gain
- Different convergence years produce valid but distinct trajectories
- Comparison with minimum-speed method (structural similarity, trajectory diff)
- Numerical stability with very small countries (island states)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair_shares.library.allocations.pathways.cumulative_per_capita_convergence import (
    cumulative_per_capita_convergence,
)
from fair_shares.library.utils.dataframes import ensure_string_year_columns

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
EMISSION_CATEGORY = "co2-ffi"
FIRST_ALLOCATION_YEAR = 2021
YEARS = list(range(2020, 2101))
STR_YEARS = [str(y) for y in YEARS]


# ---------------------------------------------------------------------------
# Realistic data fixtures
# ---------------------------------------------------------------------------

# Approximate 2020 values (population in millions, emissions in MtCO2)
COUNTRY_PROFILES = {
    #         pop(M)   emiss(Mt)  pop_growth  emiss_trend
    "CHN": (1412.0, 11680.0, 0.001, -0.005),
    "IND": (1408.0, 2710.0, 0.008, 0.010),
    "USA": (331.0, 5010.0, 0.004, -0.008),
    "IDN": (274.0, 620.0, 0.007, 0.005),
    "BRA": (213.0, 480.0, 0.005, 0.002),
    "NGA": (211.0, 130.0, 0.024, 0.015),
    "RUS": (146.0, 1760.0, -0.002, -0.006),
    "MEX": (129.0, 480.0, 0.006, 0.001),
    "JPN": (126.0, 1070.0, -0.003, -0.010),
    "DEU": (83.0, 640.0, 0.001, -0.012),
    "GBR": (67.0, 340.0, 0.003, -0.015),
    "FRA": (65.0, 310.0, 0.002, -0.010),
    "ZAF": (60.0, 460.0, 0.010, 0.002),
    "KOR": (52.0, 620.0, 0.000, -0.005),
    "AUS": (26.0, 400.0, 0.010, -0.008),
}

# High per-capita emitters (should lose share over time)
HIGH_PC_EMITTERS = {"USA", "AUS", "KOR", "RUS", "DEU", "JPN", "GBR"}
# Low per-capita emitters (should gain share over time)
LOW_PC_EMITTERS = {"IND", "NGA", "IDN", "BRA"}


def _build_population_df(profiles: dict, years: list[int]) -> pd.DataFrame:
    """Build a population DataFrame with realistic growth trajectories."""
    rows = []
    for iso, (pop_2020, _, growth, _) in profiles.items():
        for y in years:
            dt = y - 2020
            pop = pop_2020 * (1.0 + growth) ** dt
            rows.append([iso, "million", y, pop])

    df = pd.DataFrame(rows, columns=["iso3c", "unit", "year", "population"])
    df = df.pivot_table(index=["iso3c", "unit"], columns="year", values="population")
    return ensure_string_year_columns(df)


def _build_emissions_df(
    profiles: dict, years: list[int], category: str
) -> pd.DataFrame:
    """
    Build an emissions DataFrame with country + World rows.

    Country emissions follow an exponential trend from 2020 base values.
    World row is the sum of all countries (closed system).
    """
    rows = []
    world_totals = {y: 0.0 for y in years}

    for iso, (_, emiss_2020, _, trend) in profiles.items():
        for y in years:
            dt = y - 2020
            e = emiss_2020 * (1.0 + trend) ** dt
            e = max(e, 1.0)  # floor at 1 Mt to avoid zero-emission countries
            rows.append([iso, "Mt * CO2e", category, y, e])
            world_totals[y] += e

    for y in years:
        rows.append(["World", "Mt * CO2e", category, y, world_totals[y]])

    df = pd.DataFrame(
        rows, columns=["iso3c", "unit", "emission-category", "year", "emissions"]
    )
    df = df.pivot_table(
        index=["iso3c", "unit", "emission-category"], columns="year", values="emissions"
    )
    return ensure_string_year_columns(df)


def _compute_country_total_at_year(
    profiles: dict, year: int
) -> float:
    """Compute the sum of all country emissions at a given year."""
    total = 0.0
    for _, (_, emiss_2020, _, trend) in profiles.items():
        dt = year - 2020
        e = emiss_2020 * (1.0 + trend) ** dt
        e = max(e, 1.0)
        total += e
    return total


def _build_world_scenario_df(
    profiles: dict,
    years: list[int],
    category: str,
    first_allocation_year: int,
) -> pd.DataFrame:
    """
    Build a declining world scenario pathway anchored to country totals.

    The pathway value at `first_allocation_year` exactly equals the sum of
    country emissions at that year (required by the validation layer). From
    that anchor it declines exponentially, consistent with a 1.5C-type budget.
    """
    anchor = _compute_country_total_at_year(profiles, first_allocation_year)

    values = []
    for y in years:
        dt = y - first_allocation_year
        # Exponential decline from the anchor value
        v = anchor * np.exp(-0.04 * dt)
        values.append(max(v, 100.0))  # floor to keep positive

    df = pd.DataFrame(
        [values],
        columns=[str(y) for y in years],
        index=pd.MultiIndex.from_tuples(
            [("1.5C", 0.5, "test", "World", "Mt * CO2e", category)],
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
    return df


@pytest.fixture(scope="module")
def realistic_data():
    """
    Module-scoped fixture with realistic country data for 15 countries.

    Population and emissions approximate real 2020 magnitudes and relative
    ordering. The world scenario pathway declines exponentially consistent
    with a 1.5C budget.
    """
    pop = _build_population_df(COUNTRY_PROFILES, YEARS)
    emiss = _build_emissions_df(COUNTRY_PROFILES, YEARS, EMISSION_CATEGORY)
    world = _build_world_scenario_df(
        COUNTRY_PROFILES, YEARS, EMISSION_CATEGORY, FIRST_ALLOCATION_YEAR
    )

    return {
        "population": pop,
        "emissions": emiss,
        "world_pathway": world,
    }


def _run_sine_deviation(data, convergence_year=2050, **kwargs):
    """Helper to run ECPC with sine-deviation and common defaults."""
    return cumulative_per_capita_convergence(
        population_ts=data["population"],
        country_actual_emissions_ts=data["emissions"],
        world_scenario_emissions_ts=data["world_pathway"],
        first_allocation_year=FIRST_ALLOCATION_YEAR,
        emission_category=EMISSION_CATEGORY,
        convergence_method="sine-deviation",
        convergence_year=convergence_year,
        strict=False,
        max_deviation_sigma=None,
        **kwargs,
    )


def _run_minimum_speed(data, **kwargs):
    """Helper to run ECPC with minimum-speed (default) and common defaults."""
    return cumulative_per_capita_convergence(
        population_ts=data["population"],
        country_actual_emissions_ts=data["emissions"],
        world_scenario_emissions_ts=data["world_pathway"],
        first_allocation_year=FIRST_ALLOCATION_YEAR,
        emission_category=EMISSION_CATEGORY,
        convergence_method="minimum-speed",
        strict=False,
        max_deviation_sigma=None,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestSharesValidity:
    """Verify that sine-deviation produces mathematically valid shares
    with realistic 15-country data."""

    def test_shares_sum_to_one_per_year(self, realistic_data):
        """All yearly share columns must sum to 1.0 within tight tolerance.

        WHY: If shares don't sum to 1.0, the allocation violates the
        conservation law -- the global pathway would be over- or under-allocated.
        Realistic data with 15 asymmetric countries is a harder test than 3
        synthetic ones because the solver must balance large disparities.
        """
        result = _run_sine_deviation(realistic_data)
        shares = result.relative_shares_pathway_emissions

        year_sums = shares.sum(axis=0)
        for col in year_sums.index:
            assert abs(year_sums[col] - 1.0) < 1e-8, (
                f"Year {col}: shares sum to {year_sums[col]:.12f}, expected 1.0"
            )

    def test_shares_non_negative(self, realistic_data):
        """All shares must be non-negative.

        WHY: Negative emission shares are physically meaningless (a country
        cannot be allocated negative emissions in a pathway context). With
        realistic asymmetric profiles -- USA at 15 tCO2/cap vs IND at 2 tCO2/cap
        -- the solver faces large corrections that could go negative without
        proper clipping.
        """
        result = _run_sine_deviation(realistic_data)
        shares = result.relative_shares_pathway_emissions

        min_val = shares.min().min()
        assert min_val >= -1e-10, (
            f"Found negative share: {min_val:.10f}"
        )

    def test_all_countries_present_in_output(self, realistic_data):
        """Output must contain shares for every input country.

        WHY: A solver bug could silently drop countries with extreme profiles
        (very small or very large). We check that all 15 countries appear.
        """
        result = _run_sine_deviation(realistic_data)
        shares = result.relative_shares_pathway_emissions

        output_countries = set(
            shares.index.get_level_values("iso3c")
        )
        expected_countries = set(COUNTRY_PROFILES.keys())
        assert output_countries == expected_countries, (
            f"Missing countries: {expected_countries - output_countries}"
        )


class TestCumulativeBudgetConservation:
    """Verify that the sum of all country allocations weighted by the global
    pathway equals the total global pathway emissions."""

    def test_weighted_cumulative_shares_sum_to_one(self, realistic_data):
        """Weighted cumulative shares (share * global_weight per year) must sum
        to 1.0 across all countries.

        WHY: This is the fundamental budget conservation property. Each year's
        share is weighted by that year's fraction of total cumulative emissions.
        If this sum deviates from 1.0, the total budget is misallocated.
        """
        result = _run_sine_deviation(realistic_data)
        shares = result.relative_shares_pathway_emissions

        world_values = realistic_data["world_pathway"].iloc[0]
        # Align columns
        common_cols = shares.columns.intersection(world_values.index)
        shares_aligned = shares[common_cols]
        world_aligned = world_values[common_cols].astype(float)

        total_emissions = world_aligned.sum()
        # Weighted cumulative share per country
        weighted = (shares_aligned * world_aligned.values).sum(axis=1) / total_emissions

        assert abs(weighted.sum() - 1.0) < 1e-6, (
            f"Weighted cumulative shares sum to {weighted.sum():.10f}, expected 1.0"
        )


class TestEquityDirection:
    """Verify the core equity behavior: high per-capita emitters lose share
    over time and low per-capita emitters gain share."""

    def test_high_emitters_share_declines(self, realistic_data):
        """USA, AUS, and other high per-capita emitters should have lower
        shares in the mid-century than at the start.

        WHY: This is the entire point of ECPC -- it redistributes emissions
        from historically high per-capita emitters toward low per-capita ones.
        If high emitters don't lose share, the method is not working.
        """
        result = _run_sine_deviation(realistic_data, convergence_year=2060)
        shares = result.relative_shares_pathway_emissions

        start_col = str(FIRST_ALLOCATION_YEAR)

        for iso in ["USA", "AUS"]:
            iso_shares = shares.xs(iso, level="iso3c")
            start_share = float(iso_shares[start_col].iloc[0])
            mid_share = float(iso_shares["2050"].iloc[0])
            assert mid_share < start_share, (
                f"{iso}: mid-century share ({mid_share:.4f}) should be less "
                f"than start share ({start_share:.4f})"
            )

    def test_low_emitters_share_increases(self, realistic_data):
        """IND and NGA (low per-capita emitters) should have higher shares
        in the mid-century than at the start.

        WHY: Low per-capita emitters are under-allocated relative to their
        population. ECPC corrects this by increasing their share over time.
        """
        result = _run_sine_deviation(realistic_data, convergence_year=2060)
        shares = result.relative_shares_pathway_emissions

        start_col = str(FIRST_ALLOCATION_YEAR)

        for iso in ["IND", "NGA"]:
            iso_shares = shares.xs(iso, level="iso3c")
            start_share = float(iso_shares[start_col].iloc[0])
            mid_share = float(iso_shares["2050"].iloc[0])
            assert mid_share > start_share, (
                f"{iso}: mid-century share ({mid_share:.4f}) should be greater "
                f"than start share ({start_share:.4f})"
            )

    def test_relative_ordering_at_convergence(self, realistic_data):
        """By the convergence year, shares should more closely reflect
        population proportions than emission proportions.

        WHY: At convergence, the method should approximate equal per capita.
        India (large population, low emissions) should have a larger share
        than the USA (smaller population, high emissions).
        """
        conv_year = 2060
        result = _run_sine_deviation(realistic_data, convergence_year=conv_year)
        shares = result.relative_shares_pathway_emissions

        ind_share = float(
            shares.xs("IND", level="iso3c")[str(conv_year)].iloc[0]
        )
        usa_share = float(
            shares.xs("USA", level="iso3c")[str(conv_year)].iloc[0]
        )
        assert ind_share > usa_share, (
            f"At convergence year {conv_year}, IND share ({ind_share:.4f}) "
            f"should exceed USA share ({usa_share:.4f}) due to larger population"
        )


class TestConvergenceYearVariation:
    """Verify that different convergence years produce valid but distinct
    trajectories."""

    @pytest.mark.parametrize("conv_year", [2040, 2050, 2080])
    def test_valid_shares_at_each_convergence_year(
        self, realistic_data, conv_year
    ):
        """Each convergence year should produce shares that sum to 1.0 and
        are non-negative.

        WHY: The solver must work across different convergence horizons.
        A short horizon (2040) compresses 20 years of adjustment into a
        tight window; a long one (2080) spreads it out. Both must remain valid.
        """
        result = _run_sine_deviation(realistic_data, convergence_year=conv_year)
        shares = result.relative_shares_pathway_emissions

        # Sum to 1.0
        year_sums = shares.sum(axis=0)
        for col in year_sums.index:
            assert abs(year_sums[col] - 1.0) < 1e-8, (
                f"conv_year={conv_year}, year {col}: sum={year_sums[col]}"
            )
        # Non-negative
        assert (shares >= -1e-10).all().all(), (
            f"conv_year={conv_year}: found negative shares"
        )

    def test_earlier_convergence_means_faster_adjustment(self, realistic_data):
        """Earlier convergence year produces larger share changes in the
        near-term for high per-capita emitters.

        WHY: If conv_year=2040, the USA must shed its excess share in ~20 years.
        If conv_year=2080, it has ~60 years. The near-term adjustment should
        be steeper with earlier convergence.
        """
        result_early = _run_sine_deviation(
            realistic_data, convergence_year=2040
        )
        result_late = _run_sine_deviation(
            realistic_data, convergence_year=2080
        )

        shares_early = result_early.relative_shares_pathway_emissions
        shares_late = result_late.relative_shares_pathway_emissions

        start_col = str(FIRST_ALLOCATION_YEAR)
        check_year = "2035"

        # USA near-term change should be larger with early convergence
        usa_start = float(
            shares_early.xs("USA", level="iso3c")[start_col].iloc[0]
        )
        usa_early_2035 = float(
            shares_early.xs("USA", level="iso3c")[check_year].iloc[0]
        )
        usa_late_2035 = float(
            shares_late.xs("USA", level="iso3c")[check_year].iloc[0]
        )

        change_early = abs(usa_start - usa_early_2035)
        change_late = abs(usa_start - usa_late_2035)

        assert change_early > change_late, (
            f"USA share change by 2035 with conv=2040 ({change_early:.6f}) "
            f"should exceed conv=2080 ({change_late:.6f})"
        )


class TestComparisonWithMinimumSpeed:
    """Compare sine-deviation against the default minimum-speed method to
    verify structural similarity and expected trajectory differences."""

    def test_both_methods_produce_valid_shares(self, realistic_data):
        """Both methods should produce shares summing to 1.0 and non-negative.

        WHY: Regression check -- both code paths through the ECPC pipeline
        must produce valid output with the same realistic input data.
        """
        result_sine = _run_sine_deviation(realistic_data, convergence_year=2060)
        result_ms = _run_minimum_speed(realistic_data)

        for label, result in [("sine", result_sine), ("min-speed", result_ms)]:
            shares = result.relative_shares_pathway_emissions
            year_sums = shares.sum(axis=0)
            for col in year_sums.index:
                assert abs(year_sums[col] - 1.0) < 1e-8, (
                    f"{label}, year {col}: sum={year_sums[col]}"
                )
            assert (shares >= -1e-10).all().all(), (
                f"{label}: found negative shares"
            )

    def test_same_directional_equity(self, realistic_data):
        """Both methods should agree on the direction of share movement:
        high emitters lose, low emitters gain.

        WHY: The methods differ in trajectory shape but should agree on
        direction. If they disagree, one of them has a fundamental bug.
        """
        result_sine = _run_sine_deviation(realistic_data, convergence_year=2060)
        result_ms = _run_minimum_speed(realistic_data)

        start_col = str(FIRST_ALLOCATION_YEAR)

        for iso in ["USA", "IND"]:
            for label, result in [
                ("sine", result_sine),
                ("min-speed", result_ms),
            ]:
                shares = result.relative_shares_pathway_emissions
                iso_shares = shares.xs(iso, level="iso3c")
                start = float(iso_shares[start_col].iloc[0])
                mid = float(iso_shares["2060"].iloc[0])

                if iso == "USA":
                    assert mid < start, (
                        f"{label}: USA share should decline ({start:.4f} -> {mid:.4f})"
                    )
                else:
                    assert mid > start, (
                        f"{label}: IND share should increase ({start:.4f} -> {mid:.4f})"
                    )

    def test_trajectories_differ(self, realistic_data):
        """The two methods should produce numerically different trajectories.

        WHY: sine-deviation uses a front-loaded sine correction; minimum-speed
        uses exponential convergence. If they produce identical output, something
        is wrong -- one method is likely falling through to the other.
        """
        result_sine = _run_sine_deviation(realistic_data, convergence_year=2060)
        result_ms = _run_minimum_speed(realistic_data)

        shares_sine = result_sine.relative_shares_pathway_emissions
        shares_ms = result_ms.relative_shares_pathway_emissions

        # Align columns
        common_cols = shares_sine.columns.intersection(shares_ms.columns)
        # Align rows -- both should have the same countries at iso3c level
        sine_countries = shares_sine.index.get_level_values("iso3c")
        ms_countries = shares_ms.index.get_level_values("iso3c")
        common_countries = set(sine_countries) & set(ms_countries)

        # Compare a mid-range year where both methods are actively converging
        check_col = "2040"
        if check_col in common_cols:
            diffs = []
            for iso in common_countries:
                s_val = float(
                    shares_sine.xs(iso, level="iso3c")[check_col].iloc[0]
                )
                m_val = float(
                    shares_ms.xs(iso, level="iso3c")[check_col].iloc[0]
                )
                diffs.append(abs(s_val - m_val))

            max_diff = max(diffs)
            assert max_diff > 1e-4, (
                f"Sine and min-speed should differ at 2040 "
                f"(max country diff={max_diff:.8f})"
            )


class TestNumericalStabilitySmallCountries:
    """Verify that very small countries don't cause numerical instability."""

    @pytest.fixture
    def data_with_small_countries(self, realistic_data):
        """Add two very small island-state-like countries to the realistic data.

        Populations of ~0.1M and ~0.05M with emissions of ~2-5 Mt.
        These are tiny relative to CHN/IND at 1400M.
        """
        small_profiles = {
            **COUNTRY_PROFILES,
            "FJI": (0.9, 2.5, 0.005, 0.002),    # Fiji-like
            "MHL": (0.06, 0.2, 0.010, 0.001),    # Marshall Islands-like
        }

        pop = _build_population_df(small_profiles, YEARS)
        emiss = _build_emissions_df(small_profiles, YEARS, EMISSION_CATEGORY)
        world = _build_world_scenario_df(
            small_profiles, YEARS, EMISSION_CATEGORY, FIRST_ALLOCATION_YEAR
        )

        return {
            "population": pop,
            "emissions": emiss,
            "world_pathway": world,
        }

    def test_small_countries_do_not_cause_nan(self, data_with_small_countries):
        """Output must not contain NaN values even with very small countries.

        WHY: Division by near-zero population or emissions can produce NaN
        in poorly guarded solvers. The Marshall Islands at 0.06M people is
        ~23,000x smaller than China.
        """
        result = _run_sine_deviation(
            data_with_small_countries, convergence_year=2060
        )
        shares = result.relative_shares_pathway_emissions

        assert not shares.isna().any().any(), (
            "Found NaN values in shares output"
        )

    def test_small_countries_get_valid_shares(self, data_with_small_countries):
        """Small countries should have small but positive shares.

        WHY: Even tiny countries must receive a non-zero allocation
        proportional to their population. A zero share would mean the country
        gets no emissions budget at all.
        """
        result = _run_sine_deviation(
            data_with_small_countries, convergence_year=2060
        )
        shares = result.relative_shares_pathway_emissions

        for iso in ["FJI", "MHL"]:
            iso_shares = shares.xs(iso, level="iso3c")
            # Should be small but positive at every year
            for col in iso_shares.columns:
                val = float(iso_shares[col].iloc[0])
                assert val > 0, (
                    f"{iso} share at {col} is {val:.10f}, expected positive"
                )

    def test_shares_still_sum_to_one_with_small_countries(
        self, data_with_small_countries
    ):
        """Adding small countries should not break the sum-to-1 property.

        WHY: If tiny-share countries cause rounding drift in the normalization
        step, the overall sum could deviate. This is a precision check.
        """
        result = _run_sine_deviation(
            data_with_small_countries, convergence_year=2060
        )
        shares = result.relative_shares_pathway_emissions

        year_sums = shares.sum(axis=0)
        for col in year_sums.index:
            assert abs(year_sums[col] - 1.0) < 1e-8, (
                f"Year {col}: shares sum to {year_sums[col]:.12f} with small countries"
            )


class TestResultMetadata:
    """Verify that result metadata is correctly set for sine-deviation runs."""

    def test_approach_name(self, realistic_data):
        """Approach name should be 'cumulative-per-capita-convergence'.

        WHY: Downstream code dispatches on the approach name. Sine-deviation
        is a convergence method within ECPC, not a separate approach.
        """
        result = _run_sine_deviation(realistic_data, convergence_year=2060)
        assert result.approach == "cumulative-per-capita-convergence"

    def test_convergence_parameters_in_result(self, realistic_data):
        """Result parameters should record convergence_method and convergence_year.

        WHY: Reproducibility. When results are serialized, these parameters
        must be present to reconstruct the exact allocation call.
        """
        result = _run_sine_deviation(realistic_data, convergence_year=2060)
        assert result.parameters["convergence_method"] == "sine-deviation"
        assert result.parameters["convergence_year"] == 2060
