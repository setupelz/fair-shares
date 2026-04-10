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
# # 605 — Reproducing Gignac & Matthews (2015) / Matthews (2016)
#
# **Papers:**
# - Matthews, H. D. (2016). Quantifying historical carbon and climate debts among nations.
#   *Nature Climate Change*, 6, 60--64. DOI: [10.1038/nclimate2774](https://doi.org/10.1038/nclimate2774)
# - Gignac, R. & Matthews, H. D. (2015). Allocating a 2 °C cumulative carbon budget to
#   countries. *Environmental Research Letters*, 10, 075004.
#   DOI: [10.1088/1748-9326/10/7/075004](https://doi.org/10.1088/1748-9326/10/7/075004)
#
# **Approach(es) reproduced:**
# - Carbon debt (cumulative overshoot of equal per capita share, Eq. 1)
# - Equal per capita budget allocation (Gignac & Matthews 2015)
#
# This notebook uses `co2-ffi`; the papers use total CO2 (fossil + LULUCF) from CDIAC.

# %% [markdown]
# ---
# ## 1. Method Extraction
#
# ### 1.1 Carbon Debt (Gignac & Matthews 2015, Equation 1; extended in Matthews 2016)
#
# The carbon debt of a country is defined as the cumulative difference between
# its actual CO2 emissions and the emissions it would have been entitled to under
# an equal per capita allocation of global emissions:
#
# $$
# \text{Carbon debt}_{\text{country}} = \sum_{t=t_{\text{start}}}^{t_{\text{end}}}
# \left[
#   E_{\text{country}}(t)
#   - E_{\text{world}}(t) \times \frac{P_{\text{country}}(t)}{P_{\text{world}}(t)}
# \right]
# $$
#
# where:
# - $E_{\text{country}}(t)$ = actual CO2 emissions of the country in year $t$
#   (paper uses fossil fuel + land use; units: MtCO2/yr)
# - $E_{\text{world}}(t)$ = total global CO2 emissions in year $t$
# - $P_{\text{country}}(t)$ = population of the country in year $t$
# - $P_{\text{world}}(t)$ = world population in year $t$
# - $t_{\text{start}}$ = 1990 (Gignac & Matthews 2015) or 1960 (Matthews 2016
#   primary baseline for fossil carbon debt)
# - $t_{\text{end}}$ = 2013 (assessment year in both papers)
#
# A positive value indicates a **carbon debt** (country has emitted more than its
# equal per capita share). A negative value indicates a **carbon credit**.
#
# ### 1.2 Equal Per Capita Share (the counterfactual benchmark)
#
# The equal per capita allocation embedded in the carbon debt equation assigns each
# country a share of global emissions proportional to its share of world population
# in each year:
#
# $$
# E_{\text{country}}^{\text{epc}}(t) = E_{\text{world}}(t) \times
# \frac{P_{\text{country}}(t)}{P_{\text{world}}(t)}
# $$
#
# This is an annual flow allocation, not a budget allocation. The carbon debt is
# the cumulative sum of the annual difference between actual and EPC emissions.
#
# ### 1.3 Climate Debt (Matthews 2016 extension)
#
# Matthews 2016 extends carbon debt to "climate debt" by converting cumulative CO2
# overshoot to a temperature contribution using the Transient Climate Response to
# cumulative CO2 Emissions (TCRE). The exact conversion method uses the
# methodology of Matthews et al. (2014) for national temperature attribution.
# This extension requires per-country temperature attribution that fair-shares
# does not provide and is not implemented here.
#
# ### 1.4 Key Parameters
#
# | Parameter | Value | Source |
# |-----------|-------|--------|
# | Start year (Gignac & Matthews 2015) | 1990 | "commonly cited as the year in which the scientific basis of anthropogenic climate change was sufficiently well established" |
# | Start year (Matthews 2016 primary) | 1960 | Matthews 2016 Fig. 1, Fig. 2 |
# | End year (historical) | 2013 | Both papers |
# | Gases for carbon debt | CO2 (fossil fuel + land use) | Gignac & Matthews 2015 Methods |
# | Emissions dataset (original) | CDIAC via Global Carbon Budget 2014 | Matthews 2016 |
# | Population data | UN World Population Prospects | Gignac & Matthews 2015 Methods |
# | Global carbon budget (for C&C) | 1000 GtCO2 from 2014 | Gignac & Matthews 2015 |

# %% [markdown]
# ---
# ## 2. Mapping to fair-shares
#
# | Paper approach | fair-shares function | Key parameters | Notes |
# |---|---|---|---|
# | EPC budget from 1990 | `equal-per-capita-budget` | `allocation_year=1990`, `preserve_allocation_year_shares=False` | Allocates the cumulative carbon budget by population shares from 1990. |
# | EPC budget from 1960 | `equal-per-capita-budget` | `allocation_year=1960`, `preserve_allocation_year_shares=False` | Same, using Matthews 2016's primary baseline. |
# | Carbon debt | Composition: `equal-per-capita-budget` + post-processing | Subtract actual cumulative emissions from the EPC budget | Same pattern as ECPC in 602/604: allocate budget, subtract actuals. Positive remainder = credit, negative = debt. See composition cell below §4. |
# | Climate debt | — | — | Requires TCRE / per-country temperature attribution. Not expressible in fair-shares. |

# %% [markdown]
# ---
# ## 3. Configuration

# %%
# =============================================================================
# CONFIGURATION
# =============================================================================

allocation_folder = "605_matthews_2016"

# DEVIATION: The paper uses total CO2 (fossil fuel + land use), citing
# CDIAC data. We use co2-ffi (fossil fuel only) because total CO2
# ("co2") requires NGHGI LULUCF preprocessing (notebooks 105/107).
# Absolute values will differ, particularly for countries with large
# LULUCF fluxes (Brazil, Indonesia).
emission_category = "co2-ffi"

active_sources = {
    "target": "rcbs",
    "emissions": "primap-202503",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "unu-wider-2025",
    "lulucf": "melo-2026",
}

# -------------------------------------------------------------------------
# ALLOCATION APPROACH CONFIGURATIONS
# -------------------------------------------------------------------------

allocations = {
    # EPC budget — allocate the cumulative carbon budget by population shares.
    # Carbon debt (Eq. 1) = this budget minus actual cumulative emissions
    # from the allocation year to the present. Same pattern as ECPC in 602/604.
    "equal-per-capita-budget": [
        {
            "allocation_year": [1960, 1990],
            "preserve_allocation_year_shares": [False],
        },
    ],
}

# Carbon debt (Gignac & Matthews 2015 Eq. 1): computed as post-processing
# in the composition cell below §4 from preprocessed emissions and population data.

# Climate debt (Matthews 2016): requires per-country TCRE-based temperature
# attribution. Not expressible in fair-shares.

EXAMPLE_COUNTRIES = ["USA", "CHN", "IND", "DEU", "BRA", "RUS", "GBR", "FRA", "CAN"]
PLOT_START_YEAR = 1990
desired_harmonisation_year = 2020

# %% [markdown]
# ---
# ## 4. Run Allocation

# %%
import matplotlib.pyplot as plt
from pyprojroot import here

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.notebook_helpers import (
    load_allocation_data,
    print_results_summary,
    run_all_allocations,
)
from fair_shares.library.utils import (
    convert_parquet_to_wide_csv,
    setup_data,
)
from fair_shares.library.utils.data.config import (
    is_composite_category,
    validate_data_source_config,
)
from fair_shares.library.visualization import plot_example_result

plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

project_root = here()

validation = validate_data_source_config(emission_category, active_sources)
if not validation["valid"]:
    raise ConfigurationError(
        "Configuration errors:\n" + "\n".join(f"  - {i}" for i in validation["issues"])
    )

target = active_sources["target"]
if target != "rcbs" or is_composite_category(emission_category):
    harmonisation_year = desired_harmonisation_year
else:
    harmonisation_year = None

# %%
setup_info = setup_data(
    project_root=project_root,
    emission_category=emission_category,
    active_sources=active_sources,
    harmonisation_year=harmonisation_year,
    verbose=True,
)

source_id = setup_info["source_id"]
processed_dir = setup_info["paths"]["processed_dir"]
original_emission_category = emission_category
emission_category = setup_info["emission_category"]
final_categories = setup_info["final_categories"]
harmonisation_year = setup_info["config"].harmonisation_year

# %%
loaded_data = load_allocation_data(
    processed_dir=processed_dir,
    target=target,
    final_categories=final_categories,
    emission_category=emission_category,
)

output_dir = project_root / "output" / source_id / "allocations" / allocation_folder

data_context = {
    "source-id": source_id,
    "allocation-folder": allocation_folder,
    "emission-category": emission_category,
    "target-source": target,
    "emissions-source": active_sources["emissions"],
    "gdp-source": active_sources["gdp"],
    "population-source": active_sources["population"],
    "gini-source": active_sources["gini"],
}

param_manifest_rows = run_all_allocations(
    allocations=allocations,
    loaded_data=loaded_data,
    output_dir=output_dir,
    data_context=data_context,
    target=target,
    final_categories=final_categories,
    harmonisation_year=harmonisation_year,
)

# %%
fig = plot_example_result(
    output_dir=output_dir,
    countries=EXAMPLE_COUNTRIES,
    plot_start_year=PLOT_START_YEAR,
    processed_dir=processed_dir,
    emission_category=original_emission_category,
    final_categories=final_categories,
)
plt.show()

# %% [markdown]
# ### Carbon debt: Budget allocation + subtract actuals
#
# Carbon debt is the same pattern as ECPC in notebooks 602 and 604:
# allocate a cumulative budget via EPC at some start year, then subtract
# actual cumulative emissions from that year to the present. Positive
# remainder = credit, negative = debt.

# %%
# The EPC budget allocation above (Step 1) gives each country's
# population-share-based entitlement. Carbon debt = entitlement - actuals.
print("Carbon debt (Gignac & Matthews 2015, Eq. 1) post-processing steps:")
print("  1. Load the EPC budget entitlements from the parquet above")
print("  2. Subtract each country's actual cumulative emissions (t_start to present)")
print("  3. Positive remainder = carbon credit, negative = carbon debt")
print()
print("Two baseline windows from the papers:")
print("  - 1990–2013 (Gignac & Matthews 2015 primary)")
print("  - 1960–2013 (Matthews 2016 primary for fossil carbon debt)")

# %% [markdown]
# ---
# ## 5. Implementation Notes
#
# This notebook implements the carbon debt methodology from Gignac & Matthews
# (2015) and Matthews (2016) using fair-shares' canonical data stack. The
# equations in § 1 are realised with the configurations in § 3; this section
# documents the implementation choices.
#
# ### 5.1 Data stack
#
# | Source role | Dataset |
# |---|---|
# | Emissions | PRIMAP-hist v2.6.1 (`primap-202503`) |
# | Population | UN WPP via Our World in Data (`un-owid-2025`) |
# | GDP | World Development Indicators (`wdi-2025`) |
# | Gini | UNU-WIDER (`unu-wider-2025`) |
# | LULUCF | Melo et al. 2026 (`melo-2026`) |
# | RCB anchor | Remaining Carbon Budgets (`rcbs`) |
#
# GDP and Gini are loaded as part of the standard pipeline initialisation even
# though the carbon debt formula itself only requires emissions and population.
#
# ### 5.2 Key architectural choices
#
# Carbon debt follows the same pattern as ECPC in notebooks 602 and 604:
# allocate a cumulative budget via EPC at a start year, then subtract actual
# cumulative emissions from that year to the present. The
# `equal-per-capita-budget` allocation in § 4 computes the per-country
# entitlement (Step 1). The carbon debt itself is Step 2: subtract each
# country's actual cumulative emissions from the entitlement. Positive
# remainder = carbon credit, negative = carbon debt.
#
# ### 5.3 Where fair-shares and Matthews differ on inputs
#
# | Aspect | fair-shares | Matthews 2016 / Gignac & Matthews 2015 |
# |---|---|---|
# | Emissions scope | `co2-ffi` (fossil only) | Total CO2 (fossil + LULUCF) |
# | Emissions dataset | PRIMAP-hist v2.6.1 | CDIAC via GCB-2014 |
# | Population | UN-OWID 2025 (WPP 2024) | UN World Population Prospects (vintage unspecified) |
# | Aggregation | Country-level (ISO3c) | Country-level |
# | Climate debt extension | Not expressible | TCRE-based temperature attribution |
#
# Downstream users comparing fair-shares output to Matthews' published figures
# should expect differences driven by the emissions dataset (PRIMAP-hist vs
# CDIAC/GCB-2014) and the exclusion of LULUCF, rather than by methodological
# divergence in the carbon debt accounting.

# %%
