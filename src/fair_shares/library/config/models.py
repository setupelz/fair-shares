"""Pydantic models for data source configuration validation.

See docs/science/ for theoretical foundations of data requirements.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from fair_shares.library.error_messages import format_error, suggest_similar
from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.utils.dataframes import validate_path_exists


class EmissionsDataParameters(BaseModel):
    """Parameters for emissions data source."""

    available_categories: list[str] = Field(
        ..., description="Available emission categories in this dataset"
    )
    world_key: str = Field(..., description="Key identifier for world/global data")
    scenario: str = Field(..., description="Historical scenario identifier")


class EmissionsSourceConfig(BaseModel):
    """Configuration for emissions data source."""

    path: str = Field(..., description="Path to emissions data file")
    data_parameters: EmissionsDataParameters

    @field_validator("path")
    @classmethod
    def validate_path_exists(cls, v: str) -> str:
        """Validate that the path exists (relative to project root)."""
        return validate_path_exists(v, "Emissions data file")


class GDPDataParameters(BaseModel):
    """Parameters for GDP data source."""

    gdp_variant: str = Field(..., description="GDP variant (PPP or MER)")
    world_key: str = Field(..., description="Key identifier for world/global data")


class GDPSourceConfig(BaseModel):
    """Configuration for GDP data source."""

    path_ppp: str = Field(..., description="Path to GDP PPP data file")
    path_mer: str = Field(..., description="Path to GDP MER data file")
    data_parameters: GDPDataParameters

    @field_validator("path_ppp", "path_mer")
    @classmethod
    def validate_path_exists(cls, v: str) -> str:
        """Validate that the path exists (relative to project root)."""
        return validate_path_exists(v, "GDP data file")


class PopulationDataParameters(BaseModel):
    """Parameters for population data source."""

    projected_variant: str = Field(..., description="Projected population variant")
    historical_world_key: str = Field(
        ..., description="Key identifier for historical world/global data"
    )
    projected_world_key: str = Field(
        ..., description="Key identifier for projected world/global data"
    )


class PopulationSourceConfig(BaseModel):
    """Configuration for population data source."""

    path_historical: str = Field(..., description="Path to historical population data")
    path_projected: str = Field(..., description="Path to projected population data")
    data_parameters: PopulationDataParameters

    @field_validator("path_historical", "path_projected")
    @classmethod
    def validate_path_exists(cls, v: str) -> str:
        """Validate that the path exists (relative to project root)."""
        return validate_path_exists(v, "Population data file")


class GiniDataParameters(BaseModel):
    """Parameters for Gini data source."""

    world_key: str = Field(..., description="Key identifier for world/global data")
    gini_year: int = Field(..., description="Reference year for Gini coefficients")

    @field_validator("gini_year")
    @classmethod
    def validate_gini_year_bounds(cls, v: int) -> int:
        """Validate that gini_year is within reasonable historical bounds."""
        if not 1900 <= v <= 2100:
            raise ConfigurationError(
                f"gini_year must be between 1900 and 2100, got {v}. "
                "Historical inequality data is only meaningful within this range."
            )
        return v


class GiniSourceConfig(BaseModel):
    """Configuration for Gini data source."""

    path: str = Field(..., description="Path to Gini data file")
    data_parameters: GiniDataParameters

    @field_validator("path")
    @classmethod
    def validate_path_exists(cls, v: str) -> str:
        """Validate that the path exists (relative to project root)."""
        return validate_path_exists(v, "Gini data file")


class TargetDataParameters(BaseModel):
    """Parameters for target data source (AR6 scenarios or remaining carbon budgets)."""

    available_categories: list[str] | None = Field(
        None, description="Available emission categories"
    )
    interpolation_method: str | None = Field(
        None, description="Method for temporal interpolation"
    )
    quantiles: list[float] | None = Field(None, description="Available quantiles")
    world_key: str | None = Field(None, description="Key for world/global data")
    adjustments: dict[str, float] | None = Field(
        None, description="Adjustments for RCB processing (bunkers, lulucf, etc.)"
    )


class TargetSourceConfig(BaseModel):
    """Configuration for target data source (AR6 scenarios or remaining carbon budgets)."""

    path: str = Field(..., description="Path to target data file")
    data_parameters: TargetDataParameters | None = None

    @field_validator("path")
    @classmethod
    def validate_path_exists(cls, v: str) -> str:
        """Validate that the path exists (relative to project root)."""
        return validate_path_exists(v, "Target data file")


class RegionMappingConfig(BaseModel):
    """Configuration for region mapping."""

    path: str = Field(..., description="Path to region mapping file")


class GeneralConfig(BaseModel):
    """General configuration data."""

    region_mapping: RegionMappingConfig


class DataSourcesConfig(BaseModel):
    """Top-level configuration for all data sources."""

    emission_category: Literal["co2-ffi", "all-ghg", "all-ghg-ex-co2-lulucf"] = Field(
        ..., description="Emission category for this configuration"
    )
    emissions: dict[str, EmissionsSourceConfig] = Field(
        ..., description="Available emissions data sources"
    )
    gdp: dict[str, GDPSourceConfig] = Field(
        ..., description="Available GDP data sources"
    )
    population: dict[str, PopulationSourceConfig] = Field(
        ..., description="Available population data sources"
    )
    gini: dict[str, GiniSourceConfig] = Field(
        ..., description="Available Gini data sources"
    )
    targets: dict[str, TargetSourceConfig] = Field(
        ..., description="Available target sources (AR6 scenarios, RCBs)"
    )

    # General configuration
    general: GeneralConfig = Field(..., description="General configuration data")

    # Active sources (set by filtering)
    active_emissions_source: str | None = Field(
        None, description="Active emissions data source"
    )
    active_gdp_source: str | None = Field(None, description="Active GDP data source")
    active_population_source: str | None = Field(
        None, description="Active population data source"
    )
    active_gini_source: str | None = Field(None, description="Active Gini data source")
    active_target_source: str | None = Field(
        None, description="Active target source (AR6 scenarios or RCBs)"
    )

    # Additional target configuration
    harmonisation_year: int | None = Field(
        None, description="Year for global harmonisation"
    )

    rcb_generator: str | None = Field(
        None, description="RCB pathway generator (only used for RCB-pathways target)"
    )

    @model_validator(mode="after")
    def validate_active_sources(self) -> DataSourcesConfig:
        """Validate that active sources exist in available sources."""
        if (
            self.active_emissions_source
            and self.active_emissions_source not in self.emissions
        ):
            valid_options = list(self.emissions.keys())
            suggestion = suggest_similar(self.active_emissions_source, valid_options)
            raise ConfigurationError(
                f"Emissions source '{self.active_emissions_source}' not recognized.\n\n"
                f"{suggestion}\n\n"
                f"Available emissions sources: {', '.join(valid_options)}"
            )
        if self.active_gdp_source and self.active_gdp_source not in self.gdp:
            valid_options = list(self.gdp.keys())
            suggestion = suggest_similar(self.active_gdp_source, valid_options)
            raise ConfigurationError(
                f"GDP source '{self.active_gdp_source}' not recognized.\n\n"
                f"{suggestion}\n\n"
                f"Available GDP sources: {', '.join(valid_options)}"
            )
        if (
            self.active_population_source
            and self.active_population_source not in self.population
        ):
            valid_options = list(self.population.keys())
            suggestion = suggest_similar(self.active_population_source, valid_options)
            raise ConfigurationError(
                f"Population source '{self.active_population_source}' "
                f"not recognized.\n\n"
                f"{suggestion}\n\n"
                f"Available population sources: {', '.join(valid_options)}"
            )
        if self.active_gini_source and self.active_gini_source not in self.gini:
            valid_options = list(self.gini.keys())
            suggestion = suggest_similar(self.active_gini_source, valid_options)
            raise ConfigurationError(
                f"Gini source '{self.active_gini_source}' not recognized.\n\n"
                f"{suggestion}\n\n"
                f"Available Gini sources: {', '.join(valid_options)}"
            )
        if self.active_target_source and self.active_target_source not in self.targets:
            valid_options = list(self.targets.keys())
            suggestion = suggest_similar(self.active_target_source, valid_options)
            raise ConfigurationError(
                format_error(
                    "invalid_target",
                    target=self.active_target_source,
                    suggestion=suggestion,
                )
            )
        return self

    @model_validator(mode="after")
    def validate_emission_category(self) -> DataSourcesConfig:
        """Validate that emission category is available in emissions source."""
        if self.active_emissions_source:
            emissions_config = self.emissions[self.active_emissions_source]
            available = emissions_config.data_parameters.available_categories
            if self.emission_category not in available:
                suggestion = suggest_similar(self.emission_category, available)
                msg = format_error(
                    "invalid_emission_category",
                    category=self.emission_category,
                    suggestion=suggestion,
                )
                note = (
                    f"\n\nNote: The emissions source "
                    f"'{self.active_emissions_source}' "
                    f"only provides: {', '.join(available)}"
                )
                raise ConfigurationError(msg + note)
        return self
