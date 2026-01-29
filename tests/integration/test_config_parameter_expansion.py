"""
Integration tests for config parameter expansion pipeline for the fair-shares library.

"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest
import yaml
from conftest import STANDARD_EMISSION_CATEGORY, generate_simple_test_data

from fair_shares.library.allocations.manager import AllocationManager
from fair_shares.library.exceptions import ConfigurationError


class TestConfigParameterExpansion:
    """Test configuration parameter expansion pipeline end-to-end."""

    @pytest.fixture
    def sample_config_with_lists(self):
        """Sample allocation config with list parameters like the real config files."""
        return {
            "allocations": {
                "per-capita-adjusted": {
                    "first-allocation-year": [1990, 2015],
                    "population-projection": "un-median-to-2100",
                    "gdp-variant": "PPP",
                    "capability-exponent": [1.0, 0.5, 2.0],
                    "capability-functional-form": ["power", "asinh"],
                    "preserve-first-allocation-year-shares": [False],
                    "max-deviation-sigma": [2.0],
                },
                "per-capita-adjusted-gini": {
                    "first-allocation-year": [2015],
                    "population-projection": "un-median-to-2100",
                    "gdp-variant": "PPP",
                    "capability-exponent": [1.0, 0.5],
                    "capability-functional-form": ["power"],
                    "income-floor": [7500],
                    "max-gini-adjustment": [0.8],
                    "preserve-first-allocation-year-shares": [False],
                    "max-deviation-sigma": [2.0],
                },
            }
        }

    def _to_list(self, value):
        """Convert value to list if not already a list (mimics notebook logic)."""
        if isinstance(value, list):
            return value
        return [value]

    def _get_allowed_param_names(self, approach, allocation_manager):
        """Get allowed parameter names for an approach (mimics notebook logic)."""
        import inspect

        from fair_shares.library.allocations import get_function

        func = get_function(approach)
        func_params = set(inspect.signature(func).parameters.keys())
        # Just return all function parameters - let the function handle what it needs
        return func_params

    def test_parameter_expansion_logic(self, sample_config_with_lists):
        """Test the parameter expansion logic that converts lists to individual combinations."""
        from fair_shares.library.allocations import (
            get_allocation_functions,
            is_budget_approach,
        )

        allocation_manager = AllocationManager()
        allocations = sample_config_with_lists["allocations"]

        param_manifest_rows = []
        allocation_functions = get_allocation_functions()

        for approach, approach_config in allocations.items():
            if approach not in allocation_functions:
                continue

            approach_config = approach_config or {}
            cfg = {str(k).replace("-", "_"): v for k, v in approach_config.items()}

            # Determine year parameter based on approach type
            if is_budget_approach(approach):
                year_param = "allocation_year"
            else:
                year_param = "first_allocation_year"

            if year_param not in cfg:
                raise ConfigurationError(
                    f"Missing '{year_param}' in allocation config for {approach}"
                )

            years = self._to_list(cfg.pop(year_param))

            # Get allowed parameters for this approach
            allowed_param_names = self._get_allowed_param_names(
                approach, allocation_manager
            )
            func_param_keys = [k for k in cfg.keys() if k in allowed_param_names]
            meta_keys = [k for k in cfg.keys() if k not in func_param_keys]

            func_param_values = [self._to_list(cfg[k]) for k in func_param_keys]

            for year in years:
                if func_param_values:
                    for combo in itertools.product(*func_param_values):
                        row = {"approach": approach, year_param: year}
                        for k, v in zip(func_param_keys, combo):
                            row[k] = v
                        for mk in meta_keys:
                            row[mk] = cfg[mk]
                        param_manifest_rows.append(row)
                else:
                    row = {"approach": approach, year_param: year}
                    for mk in meta_keys:
                        row[mk] = cfg[mk]
                    param_manifest_rows.append(row)

        # Verify parameter expansion worked correctly
        assert (
            len(param_manifest_rows) > 0
        ), "Parameter expansion should create at least one row"

        # Check that all parameters are scalar, not lists
        for row in param_manifest_rows:
            for key, value in row.items():
                if key in [
                    "capability_exponent",
                    "capability_functional_form",
                    "max_deviation_sigma",
                    "income_floor",
                    "max_gini_adjustment",
                ]:
                    assert not isinstance(
                        value, list
                    ), f"Parameter {key} should be scalar, got list: {value}"

        # Test specific combinations we expect
        per_capita_adjusted_rows = [
            r for r in param_manifest_rows if r["approach"] == "per-capita-adjusted"
        ]
        # Should have 2 years * 3 capability_exponents * 2 capability_functional_forms * 1 preserve * 1 max_deviation = 12 combinations
        assert len(per_capita_adjusted_rows) == 12

        # Check sample parameter values are scalar
        sample_row = per_capita_adjusted_rows[0]
        assert isinstance(
            sample_row["capability_exponent"], (int, float)
        ), f"Capability exponent should be scalar, got: {type(sample_row['capability_exponent'])}"
        assert isinstance(
            sample_row["capability_functional_form"], str
        ), f"Capability functional form should be string, got: {type(sample_row['capability_functional_form'])}"

    def test_allocation_execution_with_expanded_parameters(
        self, sample_config_with_lists
    ):
        """Test that allocation functions work with expanded scalar parameters from config."""
        allocation_manager = AllocationManager()
        test_data = generate_simple_test_data()

        # Test one specific parameter combination from the expansion
        test_params = {
            "approach": "per-capita-adjusted",
            "first_allocation_year": 2015,
            "capability_exponent": 1.0,  # This should be scalar, not [1.0]
            "capability_functional_form": "power",  # This should be scalar, not ['power']
            "preserve_first_allocation_year_shares": False,
            "max_deviation_sigma": 2.0,
        }

        # This should work without errors - no lists should be passed to the function
        result = allocation_manager.run_allocation(
            approach=test_params["approach"],
            config=sample_config_with_lists,
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=test_params["first_allocation_year"],
            capability_weight=1.0,
            capability_exponent=test_params["capability_exponent"],
            capability_functional_form=test_params["capability_functional_form"],
            preserve_first_allocation_year_shares=test_params[
                "preserve_first_allocation_year_shares"
            ],
            max_deviation_sigma=test_params["max_deviation_sigma"],
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Verify result contains scalar parameters, not lists
        assert isinstance(result.parameters["capability_exponent"], (int, float))
        assert isinstance(result.parameters["capability_functional_form"], str)

    def test_real_config_file_parameter_expansion(self):
        """Test parameter expansion with actual config files from the project."""
        config_path = Path("conf/allocations/alloc_all-pathway.yaml")
        if not config_path.exists():
            pytest.skip("Real config file not found")

        with open(config_path) as f:
            real_config = yaml.safe_load(f)

        from fair_shares.library.allocations import (
            get_allocation_functions,
            is_budget_approach,
        )

        allocation_manager = AllocationManager()
        allocation_functions = get_allocation_functions()

        # Test expansion logic on real config
        param_manifest_rows = []

        for approach, approach_config in real_config.items():
            if approach not in allocation_functions:
                continue

            approach_config = approach_config or {}
            cfg = {str(k).replace("-", "_"): v for k, v in approach_config.items()}

            # Get the year parameter
            year_param = (
                "first_allocation_year"
                if not is_budget_approach(approach)
                else "allocation_year"
            )

            if year_param not in cfg:
                continue

            years = self._to_list(cfg.pop(year_param))

            # Get allowed parameters for this approach
            allowed_param_names = self._get_allowed_param_names(
                approach, allocation_manager
            )
            func_param_keys = [k for k in cfg.keys() if k in allowed_param_names]

            func_param_values = [self._to_list(cfg[k]) for k in func_param_keys]

            for year in years:
                if func_param_values:
                    for combo in itertools.product(*func_param_values):
                        row = {"approach": approach, year_param: year}
                        for k, v in zip(func_param_keys, combo):
                            row[k] = v
                        param_manifest_rows.append(row)

        # Verify all parameters are scalar after expansion
        for row in param_manifest_rows:
            for key, value in row.items():
                if key == "capability_exponent":
                    assert isinstance(
                        value, (int, float)
                    ), f"Capability exponent should be scalar, got {type(value)}: {value}"
                elif key == "capability_functional_form":
                    assert isinstance(
                        value, str
                    ), f"Capability functional form should be string, got {type(value)}: {value}"

    def test_config_with_manager_integration_now_works_with_lists(
        self, sample_config_with_lists
    ):
        """Test that list parameters are now correctly overridden by scalar kwargs."""
        allocation_manager = AllocationManager()
        test_data = generate_simple_test_data()

        # This should now work - scalar capability_exponent should override the list in config
        result = allocation_manager.run_allocation(
            approach="per-capita-adjusted",
            config=sample_config_with_lists,  # Contains capability-exponent: [1.0, 0.5, 2.0]
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2015,
            capability_weight=1.0,
            capability_exponent=1.5,  # This scalar should override the list from config
            capability_functional_form="power",
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # Verify the scalar value was used, not the list
        assert result.parameters["capability_exponent"] == 1.5
        assert isinstance(result.parameters["capability_exponent"], (int, float))

    def test_original_error_scenario_now_fixed(self, sample_config_with_lists):
        """Test that reproduces the original error scenario from the notebook."""
        allocation_manager = AllocationManager()
        test_data = generate_simple_test_data()

        # Simulate the exact scenario from the notebook where approach_config contains lists
        # but the individual parameter should be scalar
        approach_config = sample_config_with_lists["allocations"]["per-capita-adjusted"]

        # Verify config contains lists
        assert isinstance(approach_config["capability-exponent"], list)
        assert isinstance(approach_config["capability-functional-form"], list)

        # This simulates what the notebook does - passing a scalar capability_exponent but config contains lists
        result = allocation_manager.run_allocation(
            approach="per-capita-adjusted",
            config=sample_config_with_lists,
            population_ts=test_data["population"],
            gdp_ts=test_data["gdp"],
            first_allocation_year=2015,
            capability_weight=1.0,
            capability_exponent=1.0,  # Scalar value from parameter expansion
            capability_functional_form="power",  # Scalar value from parameter expansion
            emission_category=STANDARD_EMISSION_CATEGORY,
        )

        # This should succeed and use scalar values, not lists
        assert result.parameters["capability_exponent"] == 1.0
        assert result.parameters["capability_functional_form"] == "power"
        assert isinstance(result.parameters["capability_exponent"], (int, float))
        assert isinstance(result.parameters["capability_functional_form"], str)
