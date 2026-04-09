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
# # 601 — Reproducing ESABCC 2023 / Pelz, Rogelj, Riahi 2023: EU Equity Pathways
#
# **Papers:**
# - European Scientific Advisory Board on Climate Change (ESABCC), 2023.
#   *Scientific advice for the determination of an EU-wide 2040 climate target
#   and a greenhouse gas budget for 2030–2050.* DOI: 10.2800/609405
# - Pelz, S., Rogelj, J., Riahi, K., 2023. *Evaluating equity in European
#   climate change mitigation pathways for the EU Scientific Advisory Board
#   on Climate Change.* IIASA, Laxenburg. https://pure.iiasa.ac.at/18830
#
# The ESABCC report draws directly on the Pelz/Rogelj/Riahi (hereafter PRR2023)
# technical report for its equity methodology. PRR2023 is the primary
# methodological source; the ESABCC report presents the conclusions.
#
# All equation and indicator references in the Method Extraction section below
# are to PRR2023 (the canonical methodological source).
#
# **Approach(es) reproduced:**
# - Equal Per Capita (EPC) budget allocation from two starting years (1990, 2015)
# - Equal Cumulative Per Capita (ECPC) budget allocation from two starting years
# - Responsibility-adjusted EPC with two penalty functions: F(x)=1/x and F(x)=1/sqrt(x)
# - Capability-adjusted EPC with the same two penalty functions

# %% [markdown]
# ---
# ## 1. Method Extraction
#
# PRR2023 defines a systematic equity evaluation framework building from
# European Climate Law and international environmental law (Rajamani et al.,
# 2021). The report considers five allocation approaches: Equal Per Capita,
# Equal Cumulative Per Capita, Responsibility, Capability, and
# Responsibility-Capability-Need. Only the first four are quantified;
# the fifth is excluded due to the large weighting solution space.
#
# ### 1.1 Equal Per Capita (EPC) Budget
#
# The global equal per capita remaining carbon budget is (PRR2023, Eq. 1):
#
# $$
# \text{RCB}_{\text{EPC}} = \frac{\text{RCB}_{1990,2015}}{\sum_{r} P_{\text{PC},r}}
# $$
#
# where $P_{\text{PC},r}$ is the population of region $r$ in the starting year
# of allocation (1990 or 2015). Regional budgets are then (PRR2023, Eq. 2):
#
# $$
# \text{RCB}_{r} = \text{RCB}_{\text{EPC}} \times P_{\text{PC},r}
# $$
#
# **fair-shares equivalent:** `equal-per-capita-budget` with
# `preserve_allocation_year_shares=True` (single-year population shares).
#
# ### 1.2 Equal Cumulative Per Capita (ECPC) Budget
#
# Same as EPC but using cumulative population from the starting year to 2050
# (PRR2023, Eq. 1-2 with $P_{\text{CPC},r}$ = cumulative population):
#
# $$
# \text{RCB}_{\text{ECPC}} = \frac{\text{RCB}_{1990,2015}}{\sum_{r} P_{\text{CPC},r}}
# $$
#
# **fair-shares equivalent:** `equal-per-capita-budget` with
# `preserve_allocation_year_shares=False` (cumulative population shares, the default)
# and `cumulative_end_year=2050` to match PRR2023's explicit 2050 upper bound.
#
# ### 1.3 Responsibility-Adjusted Budget
#
# The responsibility-adjusted allocation modifies the EPC/ECPC base by a
# penalty function applied to cumulative historical CO2-FFI emissions
# (PRR2023, Eq. 3):
#
# $$
# \text{RCB}_{\text{adj},r} = \frac{F(x_{i,r}) \times \text{RCB}_{1990,2015}}
# {\sum_{r} F(x_{i,r}) \times P_{\text{PC/CPC},r}}
# $$
#
# where $x_{i,r}$ is the regional indicator value (e.g., cumulative CO2-FFI
# per capita from 1850 to the year before allocation). Two penalty functions
# are applied (PRR2023, Section "Penalty functions"):
#
# - **F(x) = 1/x** — the second most severe of four functions PRR2023 tested;
#   penalizes high emitters strongly
# - **F(x) = 1/sqrt(x)** — less severe than 1/x, more lenient on high emitters
#
# PRR2023 also tested F(x)=1/x^2 (too harsh) and F(x)=asinh(x)^(-1) (too
# lenient), but uses only 1/x and 1/sqrt(x) in final results.
#
# **Indicators used for Responsibility:**
# - Cumulative CO2-FFI 1850-1989 (for 1990 allocation)
# - Cumulative CO2-FFI 1850-2014 and 1990-2014 (for 2015 allocation)
# - Per capita variants of the above
#
# **fair-shares equivalent:** `per-capita-adjusted-budget` with
# `pre_allocation_responsibility_weight=1.0`, `capability_weight=0.0`,
# `functional_form="power"`, `exponent=1.0` (for 1/x) or `exponent=0.5`
# (for 1/sqrt(x)).
#
# ### 1.4 Capability-Adjusted Budget
#
# Same structure as responsibility but using GDP per capita or capital stock
# per capita as the indicator (PRR2023, Table 18):
#
# - GDP per capita in 1990 or 2014
# - Capital stock per capita in 1990 or 2014
#
# **fair-shares equivalent:** `per-capita-adjusted-budget` with
# `capability_weight=1.0`, `pre_allocation_responsibility_weight=0.0`,
# `functional_form="power"`, `exponent=1.0` or `0.5`.
#
# ### 1.5 Responsibility-Capability-Need (Not Quantified)
#
# PRR2023 explicitly states: "We do not provide calculations using this
# allocation approach given the large solution space when weighting the
# composite allocation approaches." The combined approach would weight
# responsibility, capability, and needs indicators. fair-shares supports
# this via `pre_allocation_responsibility_weight` + `capability_weight` summing to <= 1.0.
#
# ### 1.6 Scope and Data Choices
#
# - **Emission category:** CO2-FFI only (excluding LULUCF and non-CO2)
# - **Global RCB:** 500 GtCO2 from 2020 for 1.5C at 50% likelihood (IPCC AR6 WG1)
# - **RCB from 1990:** ~1530 GtCO2 (500 + 1030 GtCO2 historical 1990-2019)
# - **RCB from 2015:** ~704 GtCO2 (500 + 204 GtCO2 historical 2015-2019)
# - **Regional grouping:** 11 regions (EU27, REU, CPA, FSU, LAM, MEA, NAM, PAS, PAO, SAS, AFR)
# - **Bunkers excluded** from historical emission attribution

# %% [markdown]
# ---
# ## 2. Mapping to fair-shares
#
# | Paper approach | fair-shares function | Key parameters | Notes |
# |---|---|---|---|
# | EPC budget (single-year pop) | `equal-per-capita-budget` | `allocation_year=1990\|2015`, `preserve_allocation_year_shares=True` | PRR2023 allocates at R11 region level; fair-shares at country level. For linear operations the two are algebraically identical when summed back to the same grouping. |
# | ECPC budget (cumul. pop) | `equal-per-capita-budget` | `allocation_year=1990\|2015`, `preserve_allocation_year_shares=False`, `cumulative_end_year=2050` | `cumulative_end_year=2050` matches PRR2023's explicit 2050 upper bound; without it, fair-shares sums to the end of the population series (~2100). |
# | Responsibility 1/x | `per-capita-adjusted-budget` | `pre_allocation_responsibility_weight=1.0`, `pre_allocation_responsibility_year=1850`, `pre_allocation_responsibility_functional_form="power"`, `pre_allocation_responsibility_exponent=1.0` | Penalty F(x)=1/x maps to `functional_form="power"` with `exponent=1.0` and default `inverse=True`; fair-shares computes `values^(-1*exponent)`. |
# | Responsibility 1/sqrt(x) | `per-capita-adjusted-budget` | same but `pre_allocation_responsibility_exponent=0.5` | Penalty F(x)=1/sqrt(x) maps to `exponent=0.5`. |
# | Capability 1/x | `per-capita-adjusted-budget` | `capability_weight=1.0`, `capability_functional_form="power"`, `capability_exponent=1.0` | PRR2023 uses GDP per capita or capital stock per capita; fair-shares uses GDP per capita via `wdi-2025`. |
# | Capability 1/sqrt(x) | `per-capita-adjusted-budget` | same but `capability_exponent=0.5` | |
# | R-C-N combined | `per-capita-adjusted-budget` | `pre_allocation_responsibility_weight=w_r`, `capability_weight=w_c` | Not quantified in PRR2023 due to large weighting solution space. |

# %% [markdown]
# ---
# ## 3. Configuration

# %%
# =============================================================================
# CONFIGURATION
# =============================================================================

allocation_folder = "601_esabcc_2023"

emission_category = "co2-ffi"

active_sources = {
    "target": "rcbs",              # Remaining carbon budgets (IPCC AR6 WG1)
    "emissions": "primap-202503",
    "gdp": "wdi-2025",
    "population": "un-owid-2025",
    "gini": "unu-wider-2025",
    "lulucf": "melo-2026",
}

# Data source note: PRR2023 used Global Carbon Budget 2021 (Friedlingstein et al. 2022)
# for historical CO2-FFI. This notebook uses PRIMAP-202503. The PRIMAP backcast is
# systematically lower than GCB 2021 for cumulative CO2-FFI: at the global aggregate
# this drives the implied RCB-from-1990 down by ~14% and RCB-from-2015 down by ~9%
# vs PRR2023's anchors (§5). Country-level differences may be larger
# for sparsely-reporting regions. LULUCF excluded in both cases.

desired_harmonisation_year = 2020

# ---------------------------------------------------------------------------
# ALLOCATION APPROACH CONFIGURATIONS
# ---------------------------------------------------------------------------

allocations = {
    "equal-per-capita-budget": [
        # APPROACH 1: EPC budget — PRR2023 Eq. 1-2, single-year population shares
        {
            "allocation_year": [1990, 2015],
            "preserve_allocation_year_shares": [True],
        },
        # APPROACH 2: ECPC budget — PRR2023 Eq. 1-2, cumulative population to 2050
        {
            "allocation_year": [1990, 2015],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
        },
    ],
    "per-capita-adjusted-budget": [
        # APPROACH 3: Responsibility 1/x — PRR2023 Eq. 3, F(x)=1/x (severe)
        {
            "allocation_year": [2015],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [1850],
            "pre_allocation_responsibility_functional_form": ["power"],
            "pre_allocation_responsibility_exponent": [1.0],
            "pre_allocation_responsibility_per_capita": [True],
            "preserve_allocation_year_shares": [True],
        },
        # APPROACH 3: Responsibility 1/√x — PRR2023 Eq. 3, F(x)=1/√x (lenient)
        {
            "allocation_year": [2015],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [1850],
            "pre_allocation_responsibility_functional_form": ["power"],
            "pre_allocation_responsibility_exponent": [0.5],
            "pre_allocation_responsibility_per_capita": [True],
            "preserve_allocation_year_shares": [True],
        },
        # APPROACH 4: Capability 1/x — PRR2023 §1.4, GDP per capita (severe)
        {
            "allocation_year": [2015],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [1.0],
            "capability_per_capita": [True],
            "capability_reference_year": [2014],
            "preserve_allocation_year_shares": [True],
        },
        # APPROACH 4: Capability 1/√x — PRR2023 §1.4, GDP per capita (lenient)
        {
            "allocation_year": [2015],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [0.5],
            "capability_per_capita": [True],
            "capability_reference_year": [2014],
            "preserve_allocation_year_shares": [True],
        },
        # APPROACH 5: CPCadjCAP ay=1990 GDP=1990 1/x — PRR2023 Table 18
        {
            "allocation_year": [1990],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [1.0],
            "capability_per_capita": [True],
            "capability_reference_year": [1990],
        },
        # APPROACH 5: CPCadjCAP ay=1990 GDP=1990 1/√x — PRR2023 Table 18
        {
            "allocation_year": [1990],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [0.5],
            "capability_per_capita": [True],
            "capability_reference_year": [1990],
        },
        # APPROACH 5: CPCadjCAP ay=2015 GDP=2014 1/x — PRR2023 Table 18
        {
            "allocation_year": [2015],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [1.0],
            "capability_per_capita": [True],
            "capability_reference_year": [2014],
        },
        # APPROACH 5: CPCadjCAP ay=2015 GDP=2014 1/√x — PRR2023 Table 18
        {
            "allocation_year": [2015],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [0.5],
            "capability_per_capita": [True],
            "capability_reference_year": [2014],
        },
    ],
}

EXAMPLE_COUNTRIES = ["DEU", "FRA", "POL", "USA", "CHN", "IND", "BRA"]
PLOT_START_YEAR = 2015

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
# ---
# ## 5. Implementation Notes
#
# This notebook implements PRR2023's allocation methodology using fair-shares'
# canonical data stack. The equations in § 1 are realised with the configurations
# in § 3; this section documents the implementation choices where fair-shares
# differs from PRR2023's own R code at the Zenodo archive
# (Pelz, Rogelj, Riahi 2023, https://doi.org/10.5281/zenodo.8035839,
# `iiasa/EUEquityReport_Replication` v1.1).
#
# ### 5.1 Data stack
#
# - **Population**: `un-owid-2025` — UN historical + WPP 2024 projections to 2100
# - **GDP**: `wdi-2025` — WDI `NY.GDP.MKTP.PP.KD` (constant 2017 international $ PPP)
# - **Emissions**: `primap-202503` — PRIMAP-hist v2.6.1, territorial, CO2-FFI scope
# - **RCB anchor**: `ar6_2020` — IPCC AR6 WG1 500 GtCO2 from 2020 for 1.5°C @ 50%
#
# ### 5.2 Key architectural choices
#
# **Country-level allocation.** fair-shares computes allocation shares at ISO3c
# level (~173 countries) and aggregates to larger groupings (EU27, R11 regions)
# post-hoc. PRR2023 aggregates country data to 11 R11 regions first, then computes
# shares at the regional level. For linear operations (EPC, ECPC) the two are
# algebraically identical when summed back to the same grouping. For non-linear
# operations (capability-adjusted with `1/x` or `1/sqrt(x)` penalty), Jensen's
# inequality applies: country-level and R11-level allocations give different
# answers whenever within-region GDP variance is material. See
# `docs/science/allocations.md` for the capability-adjustment discussion.
#
# **Capability snapshot.** PRR2023 uses a single-year GDP-per-capita snapshot
# (1990 for `ay=1990`, 2014 for `ay=2015`) loaded from a pre-computed indicator
# CSV. fair-shares supports this via the `capability_reference_year` kwarg on
# `per_capita_adjusted_budget`; the CPCadjCAP entries in § 3 use this kwarg to
# match PRR2023's snapshot construction. Without the kwarg, fair-shares computes
# capability year-by-year across the allocation window — a different but
# well-defined semantic documented in `docs/science/allocations.md`.
#
# **Scope and approach coverage.** This notebook runs fair-shares' equivalents
# of PRR2023's EPC/ECPC baselines and the capability-adjusted variants under
# `1/x` and `1/sqrt(x)` penalty functions. The responsibility-adjusted variants
# and the responsibility+capability+need composite are not configured here —
# users who want them can add entries to the allocations dict following the
# same pattern.
#
# ### 5.3 Where fair-shares and PRR2023 differ on inputs
#
# | Aspect | fair-shares | PRR2023 |
# |---|---|---|
# | GDP convention | constant 2017 PPP (`NY.GDP.MKTP.PP.KD`) | same |
# | Population historical | un-owid-2025 | OWID historical CSV |
# | Population projection | un-owid-2025 (UN WPP 2024) | IIASA WiC SSP2 v9_130115 (2013 vintage) |
# | Emissions | PRIMAP-hist v2.6.1 (CO2-FFI) | GCB 2022 |
# | RCB anchor | `ar6_2020` (Canadell et al. 2021) | same (Canadell et al. 2021) |
# | Allocation granularity | country (ISO3c) | R11 regions |
# | Capability indicator year | configurable via `capability_reference_year` | 1990 for ay=1990, 2014 for ay=2015 |
# | Penalty functions used | `power` with configurable exponent | `1/x` and `1/sqrt(x)` |
#
# Downstream users who want to compare fair-shares' allocations against PRR2023's
# published figure values should aggregate fair-shares' country-level output to
# PRR2023's R11 regions before comparing — otherwise the country-vs-R11 Jensen
# gap will appear in the residuals. The R11 aggregation maps are in the
# PRR2023 archive at `Data/countrygrouping/isorgn.csv`.

# %%
