# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags,-all
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Global Carbon Budget 2025 Emissions Data Preprocessing
#
# Territorial fossil CO2 (`co2-ffi`) by country, 1850 to 2024, in MtCO2 per year.
#
# **Source:** Andrew and Peters (2025), Global Carbon Project fossil CO2
# emissions dataset, version 2025v15, doi:10.5281/zenodo.17417124. Paper:
# Friedlingstein et al. (2026), doi:10.5194/essd-18-3211-2026.
#
# The transformation is `fair_shares.library.utils.data.gcb.gcb_fossil_co2`.
# It applies four rules.
#
# 1. **Years.** 1850 to 2024. The file starts in 1750; earlier years are dropped.
# 2. **Blank years count as zero.** The file leaves a year blank where it
#    reports those emissions under another entity or reports none. Most blanks
#    precede a country's first record. Some sit inside a series (Ireland 1851
#    to 1923, reported under the United Kingdom). The GCB global total treats
#    every blank as zero, and so does this notebook.
# 3. **World row.** GCB global total minus international shipping (`XIS`),
#    international aviation (`XIA`) and the Kuwaiti oil fires (478 MtCO2, 1991
#    only). These three belong to no country. They are saved to
#    `emiss_co2-ffi_excluded_timeseries.csv`, so that for every year
#    world row + excluded rows = GCB global total.
# 4. **Country rows.** A country row is an ISO3 code in the region mapping.
#    Every other row stays in the world row and so lands in rest-of-world:
#    - Kosovo (`KSV`) and Antarctica (`ATA`), which the region mapping lacks.
#    - "Pacific Islands (Palau)" (1955 to 1991, 4.43 MtCO2 in total, at most
#      0.23 per year) and "Ryukyu Islands" (1965 to 1972, 0.82 MtCO2 in total,
#      at most 0.13 per year). These rows have no ISO code. The official GCB
#      workbook (National_Fossil_Carbon_Emissions_2025) keeps both in its World
#      column and in no country column: its Palau column is blank before 1992
#      and its Japan column equals the flat-file Japan row without Ryukyu.
#
# The notebook also saves each country's first recorded year to
# `emiss_co2-ffi_first_recorded_year.csv`. After the zero-fill a blank and a
# reported zero look the same, so the coverage rule of this source reads that
# table: a country with no record before 1990, or without population from
# 1850, joins rest-of-world (`coverage` in `data_sources_unified.yaml`).
#
# **Output:** `intermediate/emissions/emiss_co2-ffi_timeseries.csv`

# %%
import pandas as pd
import yaml
from pyprojroot import here

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.preprocessing import FIRST_RECORDED_YEAR_FILENAME
from fair_shares.library.utils import build_source_id
from fair_shares.library.utils.data.gcb import gcb_first_recorded_year, gcb_fossil_co2

# %% tags=["parameters"]
emission_category = None
active_target_source = None
active_emissions_source = None
active_gdp_source = None
active_population_source = None
active_gini_source = None
active_lulucf_source = None
source_id = None

# %%
if emission_category is not None:
    # Running via Papermill
    if source_id is None:
        source_id = build_source_id(
            emissions=active_emissions_source,
            gdp=active_gdp_source,
            population=active_population_source,
            gini=active_gini_source,
            lulucf=active_lulucf_source,
            target=active_target_source,
            emission_category=emission_category,
        )
    with open(here() / f"output/{source_id}/config.yaml") as f:
        config = yaml.safe_load(f)
else:
    # Running interactively
    from fair_shares.library.utils.data.config import build_data_config

    emission_category = "co2-ffi"
    active_emissions_source = "gcb-2025"
    config, source_id = build_data_config(
        emission_category,
        {
            "emissions": active_emissions_source,
            "gdp": "wdi-2025",
            "population": "un-owid-2025",
            "gini": "wdi-2025",
            "target": "rcbs",
        },
    )
    config = config.model_dump()

# %%
project_root = here()
emissions_config = config["emissions"][active_emissions_source]
world_key = emissions_config["data_parameters"]["world_key"]

if emission_category != "co2-ffi":
    raise ConfigurationError(
        f"{active_emissions_source} provides co2-ffi only, got '{emission_category}'"
    )

intermediate_dir = project_root / f"output/{source_id}/intermediate/emissions"
intermediate_dir.mkdir(parents=True, exist_ok=True)

# %% [markdown]
# ## Load and process data

# %%
raw = pd.read_csv(project_root / emissions_config["path"])
region_mapping = pd.read_csv(project_root / config["general"]["region_mapping"]["path"])

countries = set(region_mapping["iso3c"])
emissions, excluded = gcb_fossil_co2(raw, countries, world_key)
first_recorded_year = gcb_first_recorded_year(raw, countries)

# %%
emissions.reset_index().to_csv(
    intermediate_dir / "emiss_co2-ffi_timeseries.csv", index=False
)
excluded.reset_index().to_csv(
    intermediate_dir / "emiss_co2-ffi_excluded_timeseries.csv", index=False
)
first_recorded_year.reset_index().to_csv(
    intermediate_dir / FIRST_RECORDED_YEAR_FILENAME.format(category="co2-ffi"),
    index=False,
)

# %% [markdown]
# ## Summary

# %%
world = emissions.xs(world_key, level="iso3c").iloc[0]
print(f"Country rows: {len(emissions) - 1}")
late = first_recorded_year[first_recorded_year >= 1990]
print(f"First record in 1990 or later: {late.to_dict()}")
print(f"Years: {emissions.columns[0]} to {emissions.columns[-1]}")
print(f"World row ({world_key}) in 2024: {world['2024']:.1f} MtCO2")
print("Excluded from the world row in 2024 (MtCO2):")
print(excluded["2024"].round(1).to_string())
