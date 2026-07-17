"""
Tests for strict user-parameter validation, honest budget-to-pathway
derivation, and the pathway capability snapshot.
"""

from __future__ import annotations

import pandas as pd
import pytest
from conftest import STANDARD_EMISSION_CATEGORY

from fair_shares.library.allocations.budgets import (
    per_capita_adjusted_budget,
    per_capita_adjusted_gini_budget,
)
from fair_shares.library.allocations.manager import (
    convert_budget_config_to_pathway,
    derive_pathway_allocations,
    get_allocation_functions,
    run_allocation,
)
from fair_shares.library.allocations.pathways import (
    per_capita_adjusted,
    per_capita_adjusted_gini,
)
from fair_shares.library.exceptions import AllocationError


class TestStrictUserParameters:
    """run_allocation rejects config parameters the approach lacks."""

    def test_unknown_parameter_raises_and_names_it(self, test_data):
        with pytest.raises(AllocationError, match="bogus_param"):
            run_allocation(
                "equal-per-capita",
                population_ts=test_data["population"],
                first_allocation_year=2020,
                emission_category=STANDARD_EMISSION_CATEGORY,
                bogus_param=1,
            )

    def test_budget_only_parameter_rejected_on_pathway(self, test_data):
        with pytest.raises(AllocationError, match="cumulative_end_year"):
            run_allocation(
                "equal-per-capita",
                population_ts=test_data["population"],
                first_allocation_year=2020,
                emission_category=STANDARD_EMISSION_CATEGORY,
                cumulative_end_year=2050,
            )

    def test_error_lists_accepted_parameters(self, test_data):
        with pytest.raises(AllocationError, match="Accepted parameters"):
            run_allocation(
                "per-capita-adjusted",
                population_ts=test_data["population"],
                first_allocation_year=2020,
                emission_category=STANDARD_EMISSION_CATEGORY,
                nonsense=True,
            )

    def test_data_arguments_still_filtered(self, test_data):
        # equal-per-capita takes no GDP; supplying it stays valid because
        # data frames are plumbing, filtered by signature.
        result = run_allocation(
            "equal-per-capita",
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )
        assert result.approach == "equal-per-capita"

    def test_valid_parameters_accepted_for_every_approach(self, test_data):
        # preserve/first-year style parameters exist on every registered
        # approach's own signature, so a minimal valid call succeeds.
        for approach in get_allocation_functions():
            kwargs = {}
            if approach.endswith("-budget"):
                kwargs["allocation_year"] = 2020
            else:
                kwargs["first_allocation_year"] = 2020
            if "convergence" in approach:
                kwargs["convergence_year"] = 2040
            result = run_allocation(
                approach,
                population_ts=test_data["population"],
                gdp_ts=test_data["gdp"],
                gini_s=test_data["gini"],
                country_actual_emissions_ts=test_data["emissions"],
                world_scenario_emissions_ts=test_data["world-emissions"],
                emission_category=STANDARD_EMISSION_CATEGORY,
                **kwargs,
            )
            assert result is not None


class TestHonestDerivation:
    """Auto-derived pathway configs name only parameters that will run."""

    def test_cumulative_end_year_stripped(self):
        derived = convert_budget_config_to_pathway(
            {
                "allocation_year": 2015,
                "cumulative_end_year": 2050,
                "preserve_allocation_year_shares": False,
            }
        )
        assert derived == {
            "first_allocation_year": 2015,
            "preserve_first_allocation_year_shares": False,
        }

    def test_capability_reference_year_passes_through(self):
        derived = convert_budget_config_to_pathway(
            {
                "allocation_year": 2015,
                "capability_weight": 1.0,
                "capability_reference_year": 2014,
            }
        )
        assert derived["capability_reference_year"] == 2014

    def test_derived_configs_run_clean_under_strict_check(self, test_data):
        budget_allocs = {
            "per-capita-adjusted-budget": [
                {
                    "allocation_year": 2020,
                    "cumulative_end_year": 2050,
                    "preserve_allocation_year_shares": False,
                    "capability_weight": 1.0,
                    "capability_functional_form": "power",
                    "capability_exponent": 1.0,
                    "capability_reference_year": 2020,
                }
            ]
        }
        derived = derive_pathway_allocations(budget_allocs)
        (config,) = derived["per-capita-adjusted"]
        result = run_allocation(
            "per-capita-adjusted",
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            emission_category=STANDARD_EMISSION_CATEGORY,
            first_allocation_year=config.pop("first_allocation_year"),
            **config,
        )
        assert result.parameters["capability_reference_year"] == 2020


class TestPathwayCapabilitySnapshot:
    """capability_reference_year freezes pathway capability at one year."""

    @staticmethod
    def _shares(result):
        return result.relative_shares_pathway_emissions

    def test_snapshot_recorded_in_parameters(self, test_data):
        result = per_capita_adjusted(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_functional_form="power",
            capability_reference_year=2020,
        )
        assert result.parameters["capability_reference_year"] == 2020

    def test_gini_preserved_mode_matches_budget_snapshot_shares(self, test_data):
        """A Gini pathway snapshot in preserved mode equals the Gini budget
        snapshot for the same inputs. An in-window reference year applies the
        Gini adjustment on both sides."""
        common = dict(
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_functional_form="power",
            capability_exponent=1.0,
            capability_per_capita=True,
            capability_reference_year=2020,
            income_floor=7500.0,
            max_gini_adjustment=0.8,
        )
        pathway = per_capita_adjusted_gini(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            gini_s=test_data["gini"],
            first_allocation_year=2020,
            preserve_first_allocation_year_shares=True,
            **common,
        )
        budget = per_capita_adjusted_gini_budget(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            gini_s=test_data["gini"],
            allocation_year=2020,
            preserve_allocation_year_shares=True,
            **common,
        )
        pathway_shares = (
            self._shares(pathway)["2020"].droplevel(["unit", "emission-category"])
        )
        budget_shares = (
            budget.relative_shares_cumulative_emission["2020"]
            .droplevel(["unit", "emission-category"])
        )
        pd.testing.assert_series_equal(
            pathway_shares.sort_index(),
            budget_shares.sort_index(),
            check_names=False,
        )

    def test_preserved_mode_matches_budget_snapshot_shares(self, test_data):
        """With preserved shares, a pathway snapshot at the allocation year
        equals the budget-side snapshot allocation for the same inputs."""
        common = dict(
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_functional_form="power",
            capability_exponent=1.0,
            capability_per_capita=True,
            capability_reference_year=2020,
        )
        pathway = per_capita_adjusted(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            preserve_first_allocation_year_shares=True,
            **common,
        )
        budget = per_capita_adjusted_budget(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            allocation_year=2020,
            preserve_allocation_year_shares=True,
            **common,
        )
        pathway_shares = (
            self._shares(pathway)["2020"].droplevel(["unit", "emission-category"])
        )
        budget_shares = (
            budget.relative_shares_cumulative_emission["2020"]
            .droplevel(["unit", "emission-category"])
        )
        pd.testing.assert_series_equal(
            pathway_shares.sort_index(),
            budget_shares.sort_index(),
            check_names=False,
        )

    def test_dynamic_mode_snapshot_is_constant_relative_adjustment(self, test_data):
        """A snapshot freezes cross-country capability ratios: the ratio of a
        snapshot run's shares to an equal-per-capita run's shares is constant
        over time for every country."""
        snap = per_capita_adjusted(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_functional_form="power",
            capability_reference_year=2020,
        )
        epc = per_capita_adjusted(
            population_ts=test_data["population"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
        )
        year_cols = [c for c in self._shares(snap).columns if str(c).isdigit()]
        ratio = self._shares(snap)[year_cols].to_numpy() / self._shares(epc)[
            year_cols
        ].to_numpy()
        # Shares renormalise each year, so compare each year's ratio pattern
        # to the first year's after scaling out the yearly normaliser.
        first = ratio[:, [0]]
        rescaled = ratio / first
        row_spread = rescaled.max(axis=0) / rescaled.min(axis=0)
        assert (abs(row_spread - 1.0) < 1e-9).all()

    def test_snapshot_beyond_last_gdp_year_warns(self, test_data):
        gdp_short = test_data["gdp"][["2015", "2019", "2020"]]
        with pytest.warns(UserWarning, match="beyond the last observed GDP year"):
            per_capita_adjusted(
                population_ts=test_data["population"],
                gdp_ts=gdp_short,
                first_allocation_year=2020,
                emission_category=STANDARD_EMISSION_CATEGORY,
                capability_weight=1.0,
                capability_reference_year=2040,
            )

    def test_snapshot_before_window_sources_unfiltered_data(self, test_data):
        result = per_capita_adjusted(
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
            capability_weight=1.0,
            capability_functional_form="power",
            capability_reference_year=2015,
        )
        assert result.parameters["capability_reference_year"] == 2015

    def test_snapshot_outside_data_range_raises(self, test_data):
        with pytest.raises(AllocationError, match="outside the GDP data range"):
            per_capita_adjusted(
                population_ts=test_data["population"],
                gdp_ts=test_data["gdp"],
                first_allocation_year=2020,
                emission_category=STANDARD_EMISSION_CATEGORY,
                capability_weight=1.0,
                capability_reference_year=1900,
            )


class TestConvergenceStrictCheck:
    """Convergence approaches have no capability_reference_year. The strict
    check turns a forwarded snapshot year into a clear error, while the bare
    convergence key still accepts adjustment kwargs via its adjusted routing."""

    def test_per_capita_convergence_rejects_capability_reference_year(self, test_data):
        with pytest.raises(AllocationError, match="capability_reference_year"):
            run_allocation(
                "per-capita-convergence",
                population_ts=test_data["population"],
                country_actual_emissions_ts=test_data["emissions"],
                world_scenario_emissions_ts=test_data["world-emissions"],
                first_allocation_year=2020,
                emission_category=STANDARD_EMISSION_CATEGORY,
                convergence_year=2040,
                capability_reference_year=2020,
            )

    def test_cumulative_convergence_rejects_capability_reference_year(self, test_data):
        with pytest.raises(AllocationError, match="capability_reference_year"):
            run_allocation(
                "cumulative-per-capita-convergence",
                population_ts=test_data["population"],
                country_actual_emissions_ts=test_data["emissions"],
                world_scenario_emissions_ts=test_data["world-emissions"],
                first_allocation_year=2020,
                emission_category=STANDARD_EMISSION_CATEGORY,
                convergence_year=2040,
                capability_reference_year=2020,
            )

    def test_bare_cumulative_convergence_accepts_capability_weight(self, test_data):
        # The bare key routes to the adjusted function, so capability_weight
        # stays valid under the strict check rather than being rejected.
        result = run_allocation(
            "cumulative-per-capita-convergence",
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            country_actual_emissions_ts=test_data["emissions"],
            world_scenario_emissions_ts=test_data["world-emissions"],
            first_allocation_year=2020,
            emission_category=STANDARD_EMISSION_CATEGORY,
            convergence_year=2040,
            capability_weight=0.5,
        )
        assert result is not None

class TestGiniDefaultParity:
    """Gini parameter defaults match across budget and pathway approaches,
    so an auto-derived pathway config runs the same floor as its budget
    source when the config omits the parameter."""

    def test_income_floor_and_max_gini_defaults_match(self):
        import inspect

        from fair_shares.library.allocations.pathways.cumulative_per_capita_convergence import (  # noqa: E501
            cumulative_per_capita_convergence_adjusted_gini,
        )

        funcs = [
            per_capita_adjusted_gini_budget,
            per_capita_adjusted_gini,
            cumulative_per_capita_convergence_adjusted_gini,
        ]
        for param in ("income_floor", "max_gini_adjustment"):
            defaults = {
                f.__name__: inspect.signature(f).parameters[param].default
                for f in funcs
            }
            assert len(set(defaults.values())) == 1, (
                f"{param} defaults diverge across gini approaches: {defaults}"
            )
