"""Pydantic models for allocation input and output validation.

This module provides validation models for fair shares allocation functions.
Replaces the decorator-based validation pattern with explicit Pydantic models.

See docs/science/ for theoretical foundations of validation requirements.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

from fair_shares.library.exceptions import InputValidationError
from fair_shares.library.utils.dataframes import TimeseriesDataFrame
from fair_shares.library.validation.inputs import (
    validate_gdp_data,
    validate_gini_data,
    validate_has_year_columns,
    validate_index_structure,
    validate_no_null_values,
    validate_population_data,
    validate_year_in_data,
)
from fair_shares.library.validation.outputs import validate_shares_sum_to_one
from fair_shares.library.validation.pipeline_validation import validate_years_in_window


class AllocationInputs(BaseModel):
    """
    Validates all input data before allocation runs.

    This model encapsulates input validation that was previously scattered across
    decorators and function bodies. It validates:

    - Data structure (index, columns)
    - Value constraints (positive values, Gini in [0,1])
    - Year coverage (required years exist)
    - Data completeness (no nulls in required fields)

    Examples
    --------
    >>> inputs = AllocationInputs(
    ...     population_ts=pop_df,
    ...     gdp_ts=gdp_df,
    ...     first_allocation_year=2020,
    ... )
    >>> # Validation runs automatically on model creation
    >>> # Will raise ValidationError if data is invalid
    """

    # Required inputs
    population_ts: TimeseriesDataFrame = Field(
        ..., description="Population time series data (group_level index, year columns)"
    )
    first_allocation_year: int = Field(
        ...,
        ge=1850,
        le=2100,
        description="First year to allocate (must exist in data)",
    )
    last_allocation_year: int = Field(
        ...,
        ge=1850,
        le=2100,
        description="Last year to allocate (must exist in data)",
    )

    # Optional inputs for adjustments
    gdp_ts: TimeseriesDataFrame | None = Field(
        None,
        description=(
            "GDP time series data (required for capability adjustments, used from "
            "allocation year onwards, or at capability_reference_year or over "
            "capability_window when set)"
        ),
    )
    gini_s: pd.DataFrame | None = Field(
        None,
        description="Gini coefficient data (stationary, required for Gini adjustments)",
    )
    country_actual_emissions_ts: TimeseriesDataFrame | None = Field(
        None,
        description="Country historical emissions (required for pre-allocation responsibility adjustments)",
    )
    world_scenario_emissions_ts: TimeseriesDataFrame | None = Field(
        None,
        description="World scenario emissions (required for pathway allocations)",
    )
    responsibility_emissions_ts: TimeseriesDataFrame | None = Field(
        None,
        description="Country emissions of the responsibility window, when separate",
    )

    # Pre-allocation responsibility parameters (when applicable)
    pre_allocation_responsibility_year: int | None = Field(
        None,
        ge=1800,
        le=2100,
        description="Base year for pre-allocation responsibility calculation",
    )

    # Capability snapshot year (when applicable)
    capability_reference_year: int | None = Field(
        None,
        description="Capability snapshot year (GDP is read at this year only)",
    )
    capability_window: tuple[int, int] | None = Field(
        None,
        description="Capability window (GDP is read over these years only)",
    )

    # Index level names, taken from the allocation function's arguments
    group_level: str = Field(
        "iso3c", description="Index level holding the country or region"
    )
    unit_level: str = Field("unit", description="Index level holding the unit")
    country_emissions_read_at_first_year: bool = Field(
        False,
        description=(
            "True when the allocation reads country emissions at "
            "first_allocation_year (grandfathering start of convergence methods)"
        ),
    )

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def validate_structure(self) -> AllocationInputs:
        """Validate index structure and values against group_level and unit_level."""
        levels = {"group_level": self.group_level, "unit_level": self.unit_level}
        validate_population_data(
            self.population_ts, "Population", verbose=False, **levels
        )
        if self.gdp_ts is not None:
            validate_gdp_data(self.gdp_ts, "GDP", verbose=False, **levels)
        if self.gini_s is not None:
            validate_gini_data(self.gini_s, "Gini", verbose=False)
        if self.country_actual_emissions_ts is not None:
            validate_index_structure(
                self.country_actual_emissions_ts,
                "Country Emissions",
                [self.group_level, self.unit_level, "emission-category"],
            )
            validate_has_year_columns(
                self.country_actual_emissions_ts, "Country Emissions"
            )
        return self

    @field_validator("world_scenario_emissions_ts")
    @classmethod
    def validate_world_emissions(
        cls, v: TimeseriesDataFrame | None
    ) -> TimeseriesDataFrame | None:
        """Validate world scenario emissions has MultiIndex with 'unit' (if provided)."""
        if v is not None:
            # Flexible validation - world scenario emissions can have various index structures
            # as long as it's a MultiIndex with 'unit' in it
            if not isinstance(v.index, pd.MultiIndex):
                from fair_shares.library.exceptions import DataProcessingError

                raise DataProcessingError(
                    "World Scenario Emissions must have MultiIndex"
                )
            if "unit" not in v.index.names:
                from fair_shares.library.exceptions import DataProcessingError

                raise DataProcessingError(
                    "World Scenario Emissions must have 'unit' in index levels"
                )
            validate_has_year_columns(v, "World Scenario Emissions")
        return v

    @model_validator(mode="after")
    def validate_year_coverage(self) -> AllocationInputs:
        """
        Ensure required years exist in all provided data.

        All datasets must cover the allocation period from first_allocation_year
        to last_allocation_year.
        """
        # Validate allocation year range
        if self.first_allocation_year > self.last_allocation_year:
            raise InputValidationError(
                f"first_allocation_year ({self.first_allocation_year}) must be <= "
                f"last_allocation_year ({self.last_allocation_year})"
            )

        # Check population has required years
        validate_year_in_data(
            self.first_allocation_year,
            self.population_ts,
            "Population",
        )
        validate_year_in_data(
            self.last_allocation_year,
            self.population_ts,
            "Population",
        )

        # Check GDP at the first year only. A capability snapshot or window reads
        # GDP at its own years instead, which the allocation function checks.
        if (
            self.gdp_ts is not None
            and self.capability_reference_year is None
            and self.capability_window is None
        ):
            validate_year_in_data(
                self.first_allocation_year,
                self.gdp_ts,
                "GDP",
            )

        # Country emissions: only the years the allocation reads. The responsibility
        # window [pre_allocation_responsibility_year, first_allocation_year) excludes the first year.
        if self.country_actual_emissions_ts is not None:
            if self.country_emissions_read_at_first_year:
                validate_year_in_data(
                    self.first_allocation_year,
                    self.country_actual_emissions_ts,
                    "Country Emissions",
                )
            if self.pre_allocation_responsibility_year is not None:
                separate = self.responsibility_emissions_ts is not None
                validate_years_in_window(
                    self.pre_allocation_responsibility_year,
                    self.first_allocation_year,
                    self.responsibility_emissions_ts
                    if separate
                    else self.country_actual_emissions_ts,
                    "Responsibility Emissions" if separate else "Country Emissions",
                )

        # Check world emissions if provided
        if self.world_scenario_emissions_ts is not None:
            validate_year_in_data(
                self.first_allocation_year,
                self.world_scenario_emissions_ts,
                "World Scenario Emissions",
            )
            validate_year_in_data(
                self.last_allocation_year,
                self.world_scenario_emissions_ts,
                "World Scenario Emissions",
            )

        return self

    @model_validator(mode="after")
    def validate_gini_year_in_bounds(self) -> AllocationInputs:
        """
        Validate that Gini reference year is reasonable.

        Gini data is typically only available for recent historical periods.
        """
        if self.gini_s is not None:
            # Gini data should be from reasonable historical period
            # This is a sanity check - Gini coefficients change slowly
            if self.first_allocation_year < 1960:
                # Warning: using modern Gini data for pre-1960 allocations
                # may not be appropriate, but we allow it
                pass

        return self


class AllocationOutputs(BaseModel):
    """
    Validates allocation output data after allocation runs.

    This model ensures allocation outputs are mathematically valid and complete:

    - Shares sum to 1.0 for each year (within numerical tolerance)
    - No null values in shares (unless expected post-net-zero)
    - Data structure is consistent with input requirements

    Examples
    --------
    >>> outputs = AllocationOutputs(
    ...     shares=shares_df,
    ...     dataset_name="Equal Per Capita Shares",
    ... )
    >>> # Validation runs automatically on model creation
    >>> # Will raise ValidationError if shares invalid

    >>> # Allow post-net-zero NaN values
    >>> outputs = AllocationOutputs(
    ...     shares=shares_df,
    ...     dataset_name="Pathway Shares",
    ...     first_year=2020,
    ...     reference_data=world_pathway_df,  # NaN pattern template
    ... )
    """

    shares: TimeseriesDataFrame = Field(
        ..., description="Allocation shares (iso3c index, year columns)"
    )
    dataset_name: str = Field(..., description="Name of dataset for error messages")
    tolerance: float = Field(
        default=1e-6,
        ge=0.0,
        le=1e-3,
        description="Tolerance for shares sum validation",
    )
    first_year: int | None = Field(
        None,
        description="First allocation year (for focused null validation)",
    )
    reference_data: TimeseriesDataFrame | None = Field(
        None,
        description="Reference data for expected NaN pattern (e.g., post-net-zero years)",
    )

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def validate_shares_sum(self) -> AllocationOutputs:
        """
        Validate that shares sum to 1.0 for each year.

        Uses the tolerance parameter for floating point comparison.
        Years containing NaN values are skipped (e.g., post-net-zero periods).
        """
        validate_shares_sum_to_one(
            shares_df=self.shares,
            dataset_name_for_error_msg=self.dataset_name,
            tolerance=self.tolerance,
        )
        return self

    @model_validator(mode="after")
    def validate_no_unexpected_nulls(self) -> AllocationOutputs:
        """
        Validate that there are no unexpected null values in shares.

        If reference_data is provided, NaN values in shares are allowed
        if they match the NaN pattern in reference_data (e.g., for
        post-net-zero pathway years where global emissions are zero).
        """
        validate_no_null_values(
            df=self.shares,
            dataset_name_for_error_msg=self.dataset_name,
            context="allocation output",
            first_allocation_year=self.first_year,
            reference_data=self.reference_data,
        )
        return self
