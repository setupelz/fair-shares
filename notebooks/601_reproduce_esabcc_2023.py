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

# %% [markdown] tags=[]
# # 601 — Reproducing ESABCC 2023 / Pelz, Rogelj, Riahi 2023: EU Equity Pathways
#
# **Papers:**
# - European Scientific Advisory Board on Climate Change (ESABCC), 2023.
#   *Scientific advice for the determination of an EU-wide 2040 climate target
#   and a greenhouse gas budget for 2030-2050.* DOI: 10.2800/609405
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
# **Approaches reproduced (all approaches quantified in PRR2023):**
# - Equal Per Capita (EPC) budget allocation from two starting years (1990, 2015)
# - Equal Cumulative Per Capita (ECPC) budget allocation from two starting years
# - Responsibility-adjusted allocations on both the EPC and ECPC bases, for
#   every historical-emissions window in PRR2023 Table 18 that our data supports,
#   in both total and per-capita form, with both penalty functions F(x)=1/x and
#   F(x)=1/sqrt(x)
# - Capability-adjusted allocations on both bases, using GDP per capita
#   snapshots (1990 and 2014), with both penalty functions
#
# **Extensions beyond PRR2023:** the same approaches are run for three
# emission categories — `co2-ffi` (the report's scope),
# `all-ghg-ex-co2-lulucf`, and `all-ghg` (NGHGI convention). § 5 then
# computes each country's fair-share budget left from 2024 onward, after
# subtracting observed emissions through 2023, and § 6 spreads those
# remaining budgets into annual pathways to 2100.

# %% [markdown] tags=[]
# ---
# ## 0. Decisions taken in this reproduction.
#
# 1. **Two of the report's indicators are not reproduced** because fair-shares
#    has no data source for them: consumption-based CO2 (1990-2014) and capital
#    stock per capita.
# 2. **The Responsibility-Capability-Need composite is not quantified.** The
#    report itself declines to quantify it ("given the large solution space when
#    weighting the composite allocation approaches"); we follow the report.
# 3. **Three emission categories are run:**
#    `co2-ffi` (fossil and industry CO2 — the report's own scope),
#    `all-ghg-ex-co2-lulucf` (all greenhouse gases except CO2 from land use),
#    and `all-ghg` (all greenhouse gases, with land-use CO2 counted the way
#    national greenhouse gas inventories count it — the "NGHGI convention").
#    Note the library's name for "all-ghg-ex-lulucf" is `all-ghg-ex-co2-lulucf`:
#    only the CO2 part of land use is excluded; non-CO2 land emissions (e.g.
#    methane from agriculture) remain included.
# 4. **Multi-gas budgets are split in two.** A remaining carbon budget caps CO2
#    only, so for the two all-GHG categories the library allocates the CO2 part
#    as a budget and the non-CO2 part as an annual pathway taken from AR6
#    scenarios of the same climate target. Their outputs appear as separate
#    rows (`co2` or `co2-ffi`, and `non-co2`) and are also combined in § 5.
# 5. **The all-GHG categories start in 2015 only.** The report's second
#    allocation year (1990) is not possible for them: national-inventory
#    land-use data begins in 2000, and the non-CO2 scenario pathways do not
#    extend back before 2015. For `all-ghg` the historical-responsibility
#    window also starts in 2000 (data start) instead of 1850 or 1990.
# 6. For every country and approach: remaining = allocated total minus actual
#    emissions from the allocation year through the last year with observed
#    data (2023 in PRIMAP-hist v2.6.1 / Melo NGHGI), so budgets are reported
#    as remaining from 2024.
# 7. **One budget across the whole notebook.** The RCB registry holds three
#    sources at three climate targets; this notebook filters the pipeline to
#    the report's anchor only — IPCC AR6 500 GtCO2 from 2020 for 1.5C at 50%
#    (`source="ar6_2020"`, `climate-assessment="1.5C"`, `quantile=0.5`) — and
#    the matching 1.5C-50% scenario pathways for the non-CO2 part. To use a
#    different anchor, change `RCB_ANCHOR` in § 3 and re-run.
# 8. **Non-CO2 configs are derived from the CO2 configs.** The library
#     derives the non-CO2 pathway configurations automatically from the
#     budget configurations, so both gas components run the same equity
#     parameters, including the single-year GDP snapshot
#     (`capability_reference_year`). One parameter has no pathway analogue:
#     the 2050 cumulative-population cutoff (`cumulative_end_year`) bounds
#     the budget's population window and is removed on derivation, so the
#     non-CO2 population window runs to 2100.
# 9. **Time distribution of remaining budgets (§ 6).** Each country's net
#     remaining budget (which can be negative) is spread into an annual pathway
#     to 2100 with `distribute_remaining_budgets_pathways`: a
#     per-capita-convergence baseline plus a deviation envelope solved so every
#     country's pathway integrates exactly to its remaining budget. Two
#     envelope shapes are run — `half-sine` (debtor countries dip net-negative
#     and recover to the baseline by the deviation end year) and `exponential`
#     (debtors stay net-negative through 2100) — crossed with deviation end
#     years {2050, 2075, 2100}. An earlier deviation end year front-loads debt
#     redress; 2100 back-loads it. The baseline converges to equal per capita
#     by 2050. These are normative knobs — edit `DISTRIBUTION_GRID` in § 3.
# 10. **Net-sink countries at the start year.** In the `all-ghg` CO2 part
#     (NGHGI convention), 29 countries are net CO2 sinks in 2023. The
#     distribution function requires positive base-year emissions (they define
#     starting shares only), so these are floored at 0.001 Mt. Budgets are
#     unaffected. Per-capita target shares use the population projection in
#     the convergence year (2050). Only the CO2 parts are distributed; for the
#     all-GHG categories the combined annual pathway = distributed CO2 + the
#     AR6 non-CO2 pathway (Decision 4).
# 11. **Past non-CO2 over-use: two settlement options, both computed.** The
#     hist-2023 gap between actual and allocated non-CO2 is reported per
#     country in a `historical-deviation` column, and § 6 runs every
#     configuration under two modes, selected by the `nonco2-debt-mode`
#     column:
#     - **`free-rider`** — no penalty. Past non-CO2 over- and under-use
#       nearly cancel globally (§ 6.2 quantifies this at +0.6% of 2015-2023
#       non-CO2), so the historical debts are simply named and left at that.
#     - **`co2-debit`** — each country's non-CO2 over-use is subtracted from
#       its remaining CO2 budget (AR6 GWP100 equivalence): missing a methane
#       target costs CO2 space. The collected debt is retired. It leaves the
#       allocation entirely, so the sum of country CO2 budgets falls below
#       the global remaining CO2 budget by the gross debt sum (quantified in
#       § 6.2); the retired space benefits the climate, and the global
#       envelope pathway is rebuilt to the reduced total so country pathways
#       stay mutually consistent. CO2 budgets can go negative so debts of any
#       size are payable; methane pathways stop at zero, which is why large
#       debts are settled here in CO2 space rather than inside non-CO2 space.
#     In both modes past under-use earns nothing. The `co2-debit` results
#     depend on the GWP100 metric — equating old methane excess with future
#     CO2 space is an accounting convention, and a different metric would
#     give different numbers.
# 12. **Non-CO2 forward pathways stay as allocated.** Under both modes the
#     non-CO2 parts are the scenario-based allocations, unchanged; all
#     settlement happens in CO2 space, where negative pathways are
#     meaningful.

# %% [markdown] tags=[]
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
# where $x_{i,r}$ is the regional indicator value. Two penalty functions
# are applied (PRR2023, Section "Penalty functions"):
#
# - **F(x) = 1/x** — the second most severe of four functions PRR2023 tested;
#   penalizes high emitters strongly
# - **F(x) = 1/sqrt(x)** — less severe than 1/x, more lenient on high emitters
#
# PRR2023 also tested F(x)=1/x^2 (too harsh) and F(x)=asin(x)^(-1) (too
# lenient), but uses only 1/x and 1/sqrt(x) in final results. We do the same.
#
# **Responsibility indicators in PRR2023 Table 18, and their status here:**
#
# | Indicator | Allocation year | Reproduced? |
# |---|---|---|
# | Cumulative CO2-FFI 1850-1989 (total and per capita) | 1990 | yes |
# | Cumulative CO2-FFI 1850-2014 (total and per capita) | 2015 | yes |
# | Cumulative CO2-FFI 1990-2014 (total and per capita) | 2015 | yes |
# | Consumption CO2 1990-2014 (total and per capita) | 2015 | no — no consumption-emissions source |
#
# **fair-shares equivalent:** `per-capita-adjusted-budget` with
# `pre_allocation_responsibility_weight=1.0`,
# `pre_allocation_responsibility_functional_form="power"`, and
# `pre_allocation_responsibility_exponent=1.0` (for 1/x) or `0.5` (for
# 1/sqrt(x)). The window start is `pre_allocation_responsibility_year`; the
# total-vs-per-capita choice is `pre_allocation_responsibility_per_capita`.
# The report applies the adjustment to both the EPC and ECPC bases ("per
# capita or cumulative per capita"); both are run here via
# `preserve_allocation_year_shares` True/False.
#
# ### 1.4 Capability-Adjusted Budget
#
# Same structure as responsibility but using a single-year snapshot of GDP per
# capita or capital stock per capita as the indicator (PRR2023, Table 18):
#
# | Indicator | Allocation year | Reproduced? |
# |---|---|---|
# | GDP per capita 1990 | 1990 | yes |
# | GDP per capita 2014 | 2015 | yes |
# | Capital stock per capita 1990 / 2014 | 1990 / 2015 | no — no capital-stock source |
#
# **fair-shares equivalent:** `per-capita-adjusted-budget` with
# `capability_weight=1.0`, `capability_functional_form="power"`,
# `capability_exponent=1.0` or `0.5`, and `capability_reference_year` set to
# the snapshot year. Run on both the EPC and ECPC bases.
#
# ### 1.5 Responsibility-Capability-Need (Not Quantified)
#
# PRR2023 explicitly states: "We do not provide calculations using this
# allocation approach given the large solution space when weighting the
# composite allocation approaches." We follow the report and do not quantify
# it. fair-shares supports it via `pre_allocation_responsibility_weight` +
# `capability_weight` summing to <= 1.0 if a downstream user wants it.
#
# ### 1.6 Scope and Data Choices
#
# - **Emission category (report):** CO2-FFI only (excluding LULUCF and non-CO2).
#   This notebook additionally runs `all-ghg-ex-co2-lulucf` and `all-ghg`
#   (NGHGI convention) — see Decisions 3-5.
# - **Global RCB (report):** 500 GtCO2 from 2020 for 1.5C at 50% likelihood
#   (IPCC AR6 WG1); the report derives ~1530 GtCO2 from 1990 and ~704 GtCO2
#   from 2015 by adding back historical emissions. fair-shares performs the
#   same rebasing internally from its own historical series.
# - **Bunkers excluded** from historical emission attribution (both).
# - **LULUCF CO2 excluded** from the report's history and scope; here it enters
#   only the `all-ghg` category, in NGHGI convention (Melo et al. data).

# %% [markdown] tags=[]
# ---
# ## 2. Mapping to fair-shares
#
# | Paper approach | fair-shares function | Key parameters | Notes |
# |---|---|---|---|
# | EPC budget (single-year pop) | `equal-per-capita-budget` | `allocation_year=1990\|2015`, `preserve_allocation_year_shares=True` | PRR2023 allocates at R11 region level; fair-shares at country level. For linear operations the two are algebraically identical when summed back to the same grouping. |
# | ECPC budget (cumul. pop) | `equal-per-capita-budget` | `allocation_year=1990\|2015`, `preserve_allocation_year_shares=False`, `cumulative_end_year=2050` | `cumulative_end_year=2050` matches PRR2023's explicit 2050 upper bound. |
# | Responsibility 1/x, 1/sqrt(x) | `per-capita-adjusted-budget` | `pre_allocation_responsibility_weight=1.0`, `pre_allocation_responsibility_year=1850\|1990`, `..._functional_form="power"`, `..._exponent=1.0\|0.5`, `..._per_capita=True\|False`, both bases | Penalty F(x)=1/x maps to `power` with exponent 1.0; F(x)=1/sqrt(x) to exponent 0.5. Windows: 1850-1989 (ay=1990), 1850-2014 and 1990-2014 (ay=2015). |
# | Capability 1/x, 1/sqrt(x) | `per-capita-adjusted-budget` | `capability_weight=1.0`, `capability_functional_form="power"`, `capability_exponent=1.0\|0.5`, `capability_reference_year=1990\|2014`, both bases | GDP-per-capita snapshot; capital stock not available. |
# | R-C-N combined | `per-capita-adjusted-budget` | weights summing to <= 1.0 | Not quantified — follows PRR2023's own exclusion. |
# | (extension) non-CO2 part of all-GHG categories | `equal-per-capita`, `per-capita-adjusted` (pathway) | auto-derived from the budget configs | `capability_reference_year` passes through (pathway approaches support the snapshot); `cumulative_end_year` is budget-only and removed on derivation (Decision 8). |

# %% [markdown] tags=[]
# ---
# ## 3. Configuration

# %% tags=[]
# =============================================================================
# CONFIGURATION
# =============================================================================

# --- Optional external overrides (front-end / reproducible runs) -------------
# By default this notebook runs standalone: the report's own RCB anchor and the
# in-repo output/ tree. Point the FAIR_SHARES_601_CONFIG env var at a YAML file
# to override either, without editing the notebook. Recognised keys (all
# optional; anything omitted keeps the default below):
#
#     rcb_anchor:                     # any subset of source / assessment / quantile
#       source: ar6_2020
#       climate-assessment: 1.5C
#       quantile: 0.5
#     output_root: /abs/path/output   # replaces <project_root>/output for §4-§6
#
import os
from pathlib import Path

import yaml

_config_601: dict = {}
_config_601_path = os.environ.get("FAIR_SHARES_601_CONFIG")
if _config_601_path:
    _config_601 = yaml.safe_load(Path(_config_601_path).read_text()) or {}
    print(f"601 overrides from {_config_601_path}: {sorted(_config_601)}")

# Output tree root for §4-§6. None -> resolved to <project_root>/output in §4,
# once pyprojroot.here() is available.
_output_root_override = _config_601.get("output_root")
OUTPUT_ROOT = Path(_output_root_override).expanduser() if _output_root_override else None

# Output subfolder name; results land in
# output/<source-id>/allocations/<allocation_folder>/ (§ 4).
allocation_folder = "601_esabcc_2023"

active_sources = {
    "target": "rcbs",              # Remaining carbon budgets; filtered to RCB_ANCHOR below
    "emissions": "primap-202503",  # Historical emissions (PRIMAP-hist v2.6.1) — allocation shares and § 5 netting actuals
    "gdp": "wdi-2025",             # GDP per capita — capability-adjusted approaches
    "population": "un-owid-2025",  # Population — per-capita and cumulative-per-capita shares, § 6 base-year weighting
    "gini": "unu-wider-2025",      # Gini — required by the data-source schema; no approach run here uses it
    "lulucf": "melo-2026",         # NGHGI LULUCF — used only for the all-ghg category
}

# Data source note: PRR2023 used Global Carbon Budget 2021 (Friedlingstein et al. 2022)
# for historical CO2-FFI. This notebook uses PRIMAP-202503. The PRIMAP backcast is
# systematically lower than GCB 2021 for cumulative CO2-FFI: at the global aggregate
# this drives the implied RCB-from-1990 down by ~14% and RCB-from-2015 down by ~9%
# vs PRR2023's anchors (§7). Country-level differences may be larger
# for sparsely-reporting regions. LULUCF excluded in both cases.

desired_harmonisation_year = 2020
# Year scenario-based pathways are harmonised to observed emissions. Applied
# when target != "rcbs" or the category is composite (the non-CO2 part of
# all-ghg / all-ghg-ex-co2-lulucf is scenario-based); has no effect for
# co2-ffi with target="rcbs" (see § 4's harmonisation_year logic).

# Remaining-budget accounting (§ 5, Decision 6): budgets are netted through
# the last year with observed emissions data. The netting year is read from
# the data at runtime; with the current sources it is 2023, so remaining
# budgets are reported from 2024.

# The single budget used across the whole notebook (Decision 7): the report's
# anchor, filtering the pipeline to one RCB row and its matching scenario
# pathways before any allocation runs. `source` picks the RCB generator
# (`ar6_2020`, `lamboll_2023`, or `forster_2024`); `climate-assessment` and
# `quantile` pick the temperature target and likelihood within that source.
# Change any field to explore a different anchor and re-run (or inject via the
# FAIR_SHARES_601_CONFIG YAML above, which updates the fields it names).
RCB_ANCHOR = {"source": "ar6_2020", "climate-assessment": "1.5C", "quantile": 0.5}
RCB_ANCHOR.update(_config_601.get("rcb_anchor", {}))

# Time distribution of remaining budgets (§ 6, Decision 9). The grid
# expands as a cross product; edit to explore other normative positions.
DISTRIBUTION_GRID = {
    "shape": ["half-sine", "exponential"],  # debt-redress envelope shape
    "deviation_end_year": [2050, 2075, 2100],  # earlier = front-loaded redress
    "convergence_year": [2050],  # year the per-capita baseline converges by
}
PATHWAY_END_YEAR = 2100  # last year of the § 6 distributed annual pathways
# Starting point for § 6 pathways is each country's actual 2023 emissions.
# Net CO2 sinks (negative values, possible under NGHGI land-use accounting)
# are raised to this tiny positive floor, in Mt CO2/yr, so their pathways
# start from ~zero. Budgets are unaffected (Decision 10).
BASE_SHARE_FLOOR_MT = 0.001

# How past non-CO2 over-use is treated in the § 6 distribution (Decision 11).
# Both modes are always computed; the output column `nonco2-debt-mode`
# selects one. Removing an entry drops its rows from the § 6 output.
NONCO2_DEBT_MODES = ["free-rider", "co2-debit"]

# ISO3c codes shown in the § 4 / 5.1 / 6.1 example plots and preview tables
EXAMPLE_COUNTRIES = ["DEU", "FRA", "POL", "USA", "CHN", "IND", "BRA"]
PLOT_START_YEAR = 2015  # first year on the § 4 example-result plot x-axis

# EU27 members (PRR2023 Table 17); aggregated into an EU27 row in the § 5.1
# preview table.
EU27 = [
    "AUT", "BEL", "BGR", "CYP", "CZE", "DEU", "DNK", "ESP", "EST", "FIN",
    "FRA", "GRC", "HRV", "HUN", "IRL", "ITA", "LTU", "LUX", "LVA", "MLT",
    "NLD", "POL", "PRT", "ROU", "SVK", "SVN", "SWE",
]

# ---------------------------------------------------------------------------
# ALLOCATION APPROACH CONFIGURATIONS
#
# Grid entries expand as cross-products: a dict with two-element lists in two
# fields yields four runs. Budget approaches allocate the CO2 (or CO2-FFI)
# budget; for the all-GHG categories, pathway approaches allocate the non-CO2
# annual pathway and are given explicitly (Decision 4).
# ---------------------------------------------------------------------------

# --- co2-ffi: the report's own scope. Full PRR2023 matrix. -----------------

allocations_co2_ffi = {
    "equal-per-capita-budget": [
        # EPC — PRR2023 Eq. 1-2, single-year population shares
        {
            "allocation_year": [1990, 2015],
            "preserve_allocation_year_shares": [True],
        },
        # ECPC — PRR2023 Eq. 1-2, cumulative population to 2050
        {
            "allocation_year": [1990, 2015],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
        },
    ],
    "per-capita-adjusted-budget": [
        # Responsibility, EPC base, ay=1990 — window 1850-1989 (Table 18)
        {
            "allocation_year": [1990],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [1850],
            "pre_allocation_responsibility_functional_form": ["power"],
            "pre_allocation_responsibility_exponent": [1.0, 0.5],
            "pre_allocation_responsibility_per_capita": [True, False],
            "preserve_allocation_year_shares": [True],
        },
        # Responsibility, EPC base, ay=2015 — windows 1850-2014 and 1990-2014
        {
            "allocation_year": [2015],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [1850, 1990],
            "pre_allocation_responsibility_functional_form": ["power"],
            "pre_allocation_responsibility_exponent": [1.0, 0.5],
            "pre_allocation_responsibility_per_capita": [True, False],
            "preserve_allocation_year_shares": [True],
        },
        # Responsibility, ECPC base, ay=1990
        {
            "allocation_year": [1990],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [1850],
            "pre_allocation_responsibility_functional_form": ["power"],
            "pre_allocation_responsibility_exponent": [1.0, 0.5],
            "pre_allocation_responsibility_per_capita": [True, False],
        },
        # Responsibility, ECPC base, ay=2015
        {
            "allocation_year": [2015],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
            "pre_allocation_responsibility_weight": [1.0],
            "pre_allocation_responsibility_year": [1850, 1990],
            "pre_allocation_responsibility_functional_form": ["power"],
            "pre_allocation_responsibility_exponent": [1.0, 0.5],
            "pre_allocation_responsibility_per_capita": [True, False],
        },
        # Capability, EPC base — GDP-per-capita snapshot in 1990 / 2014
        {
            "allocation_year": [1990],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [1.0, 0.5],
            "capability_per_capita": [True],
            "capability_reference_year": [1990],
            "preserve_allocation_year_shares": [True],
        },
        {
            "allocation_year": [2015],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [1.0, 0.5],
            "capability_per_capita": [True],
            "capability_reference_year": [2014],
            "preserve_allocation_year_shares": [True],
        },
        # Capability, ECPC base
        {
            "allocation_year": [1990],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [1.0, 0.5],
            "capability_per_capita": [True],
            "capability_reference_year": [1990],
        },
        {
            "allocation_year": [2015],
            "cumulative_end_year": [2050],
            "preserve_allocation_year_shares": [False],
            "capability_weight": [1.0],
            "capability_functional_form": ["power"],
            "capability_exponent": [1.0, 0.5],
            "capability_per_capita": [True],
            "capability_reference_year": [2014],
        },
    ],
}


def _composite_allocations(responsibility_years: list[int]) -> dict:
    """Budget grid for an all-GHG category, templated on the responsibility window.

    The two composite categories share one grid shape but differ from the
    co2-ffi grid in two ways: allocation starts in 2015 only (Decision 5),
    and the responsibility window start is category-specific — 1850/1990
    where the CO2 part has full fossil history, 2000 where NGHGI land-use
    data begins (Decision 5). The library derives the non-CO2 pathway
    configurations from these budget entries (Decision 8).
    """
    return {
        "equal-per-capita-budget": [
            {
                "allocation_year": [2015],
                "preserve_allocation_year_shares": [True],
            },
            {
                "allocation_year": [2015],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
            },
        ],
        "per-capita-adjusted-budget": [
            {
                "allocation_year": [2015],
                "pre_allocation_responsibility_weight": [1.0],
                "pre_allocation_responsibility_year": responsibility_years,
                "pre_allocation_responsibility_functional_form": ["power"],
                "pre_allocation_responsibility_exponent": [1.0, 0.5],
                "pre_allocation_responsibility_per_capita": [True, False],
                "preserve_allocation_year_shares": [True, False],
            },
            {
                "allocation_year": [2015],
                "capability_weight": [1.0],
                "capability_functional_form": ["power"],
                "capability_exponent": [1.0, 0.5],
                "capability_per_capita": [True],
                "capability_reference_year": [2014],
                "preserve_allocation_year_shares": [True],
            },
            {
                "allocation_year": [2015],
                "cumulative_end_year": [2050],
                "preserve_allocation_year_shares": [False],
                "capability_weight": [1.0],
                "capability_functional_form": ["power"],
                "capability_exponent": [1.0, 0.5],
                "capability_per_capita": [True],
                "capability_reference_year": [2014],
            },
        ],
    }


# Category run matrix. co2-ffi reproduces the report; the all-GHG categories
# extend it (Decisions 3-5). all-ghg responsibility windows start at the NGHGI
# LULUCF data start (2000); all-ghg-ex-co2-lulucf keeps the report's windows
# because its CO2 part is fossil-only with full history.
CATEGORY_ALLOCATIONS = {
    "co2-ffi": allocations_co2_ffi,
    "all-ghg-ex-co2-lulucf": _composite_allocations(responsibility_years=[1850, 1990]),
    "all-ghg": _composite_allocations(responsibility_years=[2000]),
}

# %% [markdown] tags=[]
# ---
# ## 4. Run Allocations
#
# One full pipeline run per emission category. Each category resolves to its
# own composite source id and writes to
# `output/<source-id>/allocations/601_esabcc_2023/`.

# %% tags=[]
import matplotlib.pyplot as plt
import pandas as pd
from pyprojroot import here

from fair_shares.library.exceptions import ConfigurationError
from fair_shares.library.notebook_helpers import (
    load_allocation_data,
    run_all_allocations,
)
from fair_shares.library.utils import setup_data
from fair_shares.library.utils.data.config import (
    is_composite_category,
    validate_data_source_config,
)
from fair_shares.library.visualization import plot_example_result

plt.style.use("default")
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3

project_root = here()
# Resolve the output root now that here() is available (§3 override or default).
output_root = OUTPUT_ROOT if OUTPUT_ROOT is not None else project_root / "output"

run_registry: dict[str, dict] = {}

for category, allocations in CATEGORY_ALLOCATIONS.items():
    print(f"\n{'=' * 70}\nCATEGORY: {category}\n{'=' * 70}")

    validation = validate_data_source_config(category, active_sources)
    if not validation["valid"]:
        raise ConfigurationError(
            "Configuration errors:\n"
            + "\n".join(f"  - {i}" for i in validation["issues"])
        )

    target = active_sources["target"]
    harmonisation_year = (
        desired_harmonisation_year
        if (target != "rcbs" or is_composite_category(category))
        else None
    )

    setup_info = setup_data(
        project_root=project_root,
        emission_category=category,
        active_sources=active_sources,
        harmonisation_year=harmonisation_year,
        verbose=True,
    )

    source_id = setup_info["source_id"]
    processed_dir = setup_info["paths"]["processed_dir"]
    final_categories = setup_info["final_categories"]

    loaded_data = load_allocation_data(
        processed_dir=processed_dir,
        target=target,
        final_categories=final_categories,
        emission_category=setup_info["emission_category"],
    )

    # Restrict the pipeline to the single anchor (Decision 7): one RCB row for
    # the budget parts, the matching climate assessment for the scenario parts.
    for cat_key, rdf in loaded_data["rcbs_data"].items():
        loaded_data["rcbs_data"][cat_key] = rdf[
            (rdf["source"] == RCB_ANCHOR["source"])
            & (rdf["climate-assessment"] == RCB_ANCHOR["climate-assessment"])
            & (rdf["quantile"] == RCB_ANCHOR["quantile"])
        ].reset_index(drop=True)
        if loaded_data["rcbs_data"][cat_key].empty:
            raise ConfigurationError(f"No RCB row matches {RCB_ANCHOR} for {cat_key}")
    for cat_key, sdf in loaded_data["scenarios_data"].items():
        mask = (
            sdf.index.get_level_values("climate-assessment")
            == RCB_ANCHOR["climate-assessment"]
        ) & (sdf.index.get_level_values("quantile") == RCB_ANCHOR["quantile"])
        loaded_data["scenarios_data"][cat_key] = sdf[mask]
        if loaded_data["scenarios_data"][cat_key].empty:
            raise ConfigurationError(
                f"No scenario rows match {RCB_ANCHOR} for {cat_key}"
            )

    output_dir = output_root / source_id / "allocations" / allocation_folder

    data_context = {
        "source-id": source_id,
        "allocation-folder": allocation_folder,
        "emission-category": setup_info["emission_category"],
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
        harmonisation_year=setup_info["config"].harmonisation_year,
    )

    run_registry[category] = {
        "source_id": source_id,
        "processed_dir": processed_dir,
        "output_dir": output_dir,
        "final_categories": final_categories,
        "n_manifest_rows": len(param_manifest_rows),
    }

    fig = plot_example_result(
        output_dir=output_dir,
        countries=EXAMPLE_COUNTRIES,
        plot_start_year=PLOT_START_YEAR,
        processed_dir=processed_dir,
        emission_category=category,
        final_categories=final_categories,
    )
    plt.show()

pd.DataFrame(
    [
        {"category": c, "source-id": r["source_id"], "configs": r["n_manifest_rows"]}
        for c, r in run_registry.items()
    ]
)

# %% [markdown] tags=[]
# ---
# ## 5. Remaining budgets after the last observed emissions year
#
# Netting uses observed data only, through the last observed year (Decision 6
# — currently 2023, so remaining from 2024). The two kinds of part carry
# different semantics (Decision 11):
#
# - **CO2 budget parts** — remaining = allocated total minus **actual**
#   emissions from the allocation year through the last observed year. CO2 is
#   a stock budget: past over-use is a real debt (remaining goes negative)
#   and § 6 redresses it in the forward pathways.
# - **Non-CO2 pathway part** — remaining = the **forward-window allocation**
#   (2024-2100). The `historical-deviation` column reports actual minus
#   allocated non-CO2 over 2015-2023: positive means the country emitted
#   more non-CO2 than its allocation, a debt that § 6 can charge against its
#   CO2 budget (`co2-debit` mode, Decision 11); negative means under-use,
#   which earns nothing (space in short-lived gases cannot be banked).
#   Combined rows inherit the non-CO2 deviation unchanged.
#
# Outputs per category: `remaining_budgets_from_<year>.csv` in the category's
# allocation folder, plus a combined tidy CSV across all three categories at
# `output/601_remaining_budgets_from_<year>.csv`. Every row carries
# `netting-end-year` and `remaining-from-year` columns stating the accounting
# window explicitly. For the all-GHG categories the CSV contains the two parts
# and a `combined` row per matching configuration (CO2 budget remaining +
# non-CO2 pathway remaining).


# %% tags=[]
def _cumulative_actuals(
    processed_dir, part: str, start_year: int
) -> tuple[pd.Series, int]:
    """Actual emissions per country from start_year through the last observed
    data year, plus that year. Observed data only — no extrapolation.
    """
    df = pd.read_csv(processed_dir / f"country_emissions_{part}_timeseries.csv")
    year_cols = sorted(c for c in df.columns if c.isdigit())
    first_year, last_observed = int(year_cols[0]), int(year_cols[-1])
    if start_year < first_year:
        raise ValueError(
            f"{part}: data start {first_year} is after allocation year {start_year}"
        )
    window = [str(y) for y in range(start_year, last_observed + 1)]
    consumed = df[window].sum(axis=1)
    return pd.Series(consumed.values, index=df["iso3c"].values), last_observed


# Columns identifying one allocation configuration (used for part pairing and
# de-duplication; year columns and value columns excluded).
_ID_COLS = [
    "iso3c",
    "source",
    "climate-assessment",
    "quantile",
    "approach",
    "emission-category",
    "unit",
    "allocation-year",
    "first-allocation-year",
    "preserve-allocation-year-shares",
    "preserve-first-allocation-year-shares",
    "pre-allocation-responsibility-weight",
    "capability-weight",
    "pre-allocation-responsibility-year",
    "pre-allocation-responsibility-per-capita",
    "capability-per-capita",
    "pre-allocation-responsibility-exponent",
    "capability-exponent",
]

# Canonical keys shared by a budget config and its pathway analogue: approach
# family (strip "-budget"), allocation year, preserve flag, equity parameters.
# "source" is excluded on purpose: budget parts carry the RCB source
# (ar6_2020 / lamboll_2023 / forster_2024) while the non-CO2 pathway part
# carries the scenario source ("ar6"); parts pair on climate assessment and
# quantile, and a combined row inherits the budget part's RCB source.
_PAIR_KEYS = [
    "iso3c",
    "climate-assessment",
    "quantile",
    "family",
    "year",
    "preserve",
    "pre-allocation-responsibility-weight",
    "pre-allocation-responsibility-year",
    "pre-allocation-responsibility-per-capita",
    "pre-allocation-responsibility-exponent",
    "capability-weight",
    "capability-exponent",
]


def _remaining_for_category(category: str, reg: dict) -> pd.DataFrame:
    ab = pd.read_parquet(reg["output_dir"] / "allocations_absolute.parquet")
    year_cols = sorted(c for c in ab.columns if c.isdigit())

    frames = []
    for part, sub in ab.groupby("emission-category"):
        sub = sub.copy()
        is_budget_part = sub["allocation-year"].notna().all()
        if is_budget_part:
            sub["year"] = sub["allocation-year"].astype(int)
            # Budget rows hold one cumulative value in the allocation-year column
            sub["allocated-total"] = [
                row[str(y)] for y, row in zip(sub["year"], sub.to_dict("records"))
            ]
            sub["preserve"] = sub["preserve-allocation-year-shares"].astype(bool)
        else:
            sub["year"] = sub["first-allocation-year"].astype(int)
            sub["allocated-total"] = sub[year_cols].sum(axis=1)
            sub["preserve"] = sub["preserve-first-allocation-year-shares"].astype(bool)

        for ay, chunk in sub.groupby("year"):
            consumed, last_observed = _cumulative_actuals(
                reg["processed_dir"], part, int(ay)
            )
            idx = chunk.index
            sub.loc[idx, "consumed-actuals"] = chunk["iso3c"].map(consumed).values
            sub.loc[idx, "netting-end-year"] = last_observed
        frames.append(sub)

    out = pd.concat(frames, ignore_index=True)
    out["netting-end-year"] = out["netting-end-year"].astype(int)
    out["remaining-from-year"] = out["netting-end-year"] + 1

    # Budget parts: remaining = allocated minus actual consumption (CO2 is a
    # stock budget; past over-use is real debt and the § 6 distribution
    # redresses it). Non-CO2 pathway parts: remaining = the forward-window
    # allocation, with the historical deviation (actual minus allocated over
    # the past window) reported in its own column; § 6 decides how that
    # deviation is treated (Decision 11).
    out["remaining-budget"] = out["allocated-total"] - out["consumed-actuals"]
    out["historical-deviation"] = float("nan")
    pathway_mask = out["allocation-year"].isna()
    if pathway_mask.any():
        for ne, chunk in out[pathway_mask].groupby("netting-end-year"):
            fwd = [y for y in year_cols if int(y) > int(ne)]
            fwd_sum = out.loc[chunk.index, fwd].sum(axis=1)
            past_alloc = out.loc[chunk.index, "allocated-total"] - fwd_sum
            out.loc[chunk.index, "remaining-budget"] = fwd_sum
            out.loc[chunk.index, "historical-deviation"] = (
                out.loc[chunk.index, "consumed-actuals"] - past_alloc
            )

    out["family"] = out["approach"].str.replace("-budget", "", regex=False)
    out["category"] = category

    keep = [
        "category",
        *[c for c in _ID_COLS if c in out.columns],
        "netting-end-year",
        "remaining-from-year",
        "allocated-total",
        "consumed-actuals",
        "remaining-budget",
        "historical-deviation",
    ]
    tidy = out[[*keep, "family", "year", "preserve"]].copy()

    # Combined rows for composite categories: CO2 budget part + non-CO2 pathway
    # part, matched on the shared equity parameters. Combining requires both
    # parts to be netted through the same observed year.
    parts = tidy["emission-category"].unique()
    if len(parts) > 1:
        if tidy["netting-end-year"].nunique() != 1:
            raise ValueError(
                f"{category}: parts have different last observed years "
                f"({sorted(tidy['netting-end-year'].unique())}) — cannot combine"
            )
        value_cols = ["allocated-total", "consumed-actuals", "remaining-budget"]
        pair_keys = [k for k in _PAIR_KEYS if k in tidy.columns]
        budget_part = tidy[tidy["emission-category"] != "non-co2"]
        pathway_part = tidy[tidy["emission-category"] == "non-co2"]
        merged = budget_part.merge(
            pathway_part[
                pair_keys + value_cols + ["historical-deviation"]
            ].drop_duplicates(pair_keys),
            on=pair_keys,
            how="inner",
            suffixes=("", "-nonco2"),
        )
        combined = merged.copy()
        for col in value_cols:
            combined[col] = combined[col] + combined[f"{col}-nonco2"]
        # The deviation concept only exists on the non-CO2 part; a combined
        # row inherits it unchanged (the CO2 part nets its debt directly).
        combined["historical-deviation"] = combined["historical-deviation-nonco2"]
        combined["emission-category"] = "combined"
        combined = combined[tidy.columns]
        n_expected = len(budget_part)
        if len(combined) != n_expected:
            print(
                f"  {category}: paired {len(combined)}/{n_expected} budget rows "
                "with a non-CO2 analogue (unpaired configs remain as parts only)"
            )
        tidy = pd.concat([tidy, combined], ignore_index=True)

    return tidy.drop(columns=["family", "year", "preserve"])


remaining_all = []
for category, reg in run_registry.items():
    tidy = _remaining_for_category(category, reg)
    from_year = int(tidy["remaining-from-year"].min())
    csv_path = reg["output_dir"] / f"remaining_budgets_from_{from_year}.csv"
    tidy.to_csv(csv_path, index=False)
    print(f"{category}: {len(tidy)} rows -> {csv_path}")
    remaining_all.append(tidy)

remaining_all = pd.concat(remaining_all, ignore_index=True)
combined_from_year = int(remaining_all["remaining-from-year"].min())
combined_path = (
    output_root / f"601_remaining_budgets_from_{combined_from_year}.csv"
)
remaining_all.to_csv(combined_path, index=False)
print(f"\ncombined: {len(remaining_all)} rows -> {combined_path}")

# %% [markdown] tags=[]
# ### 5.1 Preview — report anchor (AR6 500 GtCO2 from 2020, 1.5C at 50%)
#
# Remaining budgets (from the year after the last observed data year) for the
# EU27 aggregate and example countries, under the report's RCB anchor.
# Units: Mt CO2e. Negative = fair share exhausted.

# %% tags=[]
# The pipeline is already anchor-filtered (Decision 7); the non-CO2 part
# carries the scenario source label, so filter on assessment and quantile only.
anchor = remaining_all[
    (remaining_all["climate-assessment"] == RCB_ANCHOR["climate-assessment"])
    & (remaining_all["quantile"] == RCB_ANCHOR["quantile"])
].copy()

eu27 = (
    anchor[anchor["iso3c"].isin(EU27)]
    .groupby(
        [c for c in anchor.columns if c not in ("iso3c", "allocated-total",
         "consumed-actuals", "remaining-budget", "historical-deviation")],
        dropna=False,
    )[["allocated-total", "consumed-actuals", "remaining-budget",
       "historical-deviation"]]
    .sum(min_count=1)
    .reset_index()
)
eu27["iso3c"] = "EU27"

preview = pd.concat(
    [eu27, anchor[anchor["iso3c"].isin(EXAMPLE_COUNTRIES)]], ignore_index=True
)

pivot = (
    preview.pivot_table(
        index=["category", "emission-category", "approach", "allocation-year",
               "pre-allocation-responsibility-year",
               "pre-allocation-responsibility-exponent",
               "pre-allocation-responsibility-per-capita",
               "capability-exponent",
               "preserve-allocation-year-shares"],
        columns="iso3c",
        values="remaining-budget",
        dropna=False,
    )
    .round(0)
)
with pd.option_context("display.max_rows", 200, "display.width", 250):
    print(pivot.to_string())

# %% [markdown] tags=[]
# ---
# ## 6. Distributing remaining budgets over time to 2100
#
# Each country's net remaining budget from § 5 (negative allowed) is spread
# into an annual emissions pathway using
# `distribute_remaining_budgets_pathways` (Decision 9): a
# per-capita-convergence baseline plus a shared deviation envelope whose
# per-country amplitude is solved in closed form, so every pathway integrates
# exactly to its remaining budget. The normative grid crosses the two envelope
# shapes with three deviation end years:
#
# - **`half-sine`** — debtor countries dip net-negative mid-horizon and
#   recover to their per-capita baseline by the deviation end year.
# - **`exponential`** — debtors stay net-negative through 2100.
# - **Deviation end year** {2050, 2075, 2100} — earlier concentrates debt
#   redress early (front-loaded); 2100 spreads it to the horizon end
#   (back-loaded).
#
# **CO2 parts** are distributed under two non-CO2 debt modes (Decision 11):
# `free-rider` leaves the CO2 budgets as they are; `co2-debit` subtracts
# each country's 2015-2023 non-CO2 over-use from its remaining CO2 budget
# (AR6 GWP100) and retires the collected debt, shrinking the global envelope
# by the gross debt sum. Negative CO2 pathways are allowed (CO2 removal is
# real), so debts of any size are payable. **Non-CO2 parts** are the
# allocated scenario pathways, identical under both modes (Decision 12).
# `combined` rows sum the distributed CO2 part and the non-CO2 pathway per
# mode and shape variant; every row's `adjusted-target` column states the
# cumulative total its pathway integrates to.
# Outputs per category: `distributed_remaining_pathways.parquet` and `.csv`
# in the category's allocation folder.


# %% tags=[]
from fair_shares.library.utils.math import (
    calculate_exponential_decay_pathway,
    distribute_remaining_budgets_pathways,
)

# Parameter columns that identify one §5 configuration (values differ per run)
_CONFIG_COLS = [
    "approach",
    "allocation-year",
    "first-allocation-year",
    "preserve-allocation-year-shares",
    "preserve-first-allocation-year-shares",
    "pre-allocation-responsibility-weight",
    "capability-weight",
    "pre-allocation-responsibility-year",
    "pre-allocation-responsibility-per-capita",
    "capability-per-capita",
    "pre-allocation-responsibility-exponent",
    "capability-exponent",
]


def _distribute_category(category: str, reg: dict, remaining: pd.DataFrame) -> pd.DataFrame:
    """Distribute every budget-part configuration's remaining budgets to 2100.

    For composite categories, each CO2 configuration is distributed under two
    non-CO2 debt modes (Decision 11):

    - ``free-rider`` — the CO2 budget stays as it is; past non-CO2 over-use
      is reported and carries no penalty.
    - ``co2-debit`` — each country's 2015-2023 non-CO2 over-use is subtracted
      from its remaining CO2 budget (AR6 GWP100) and the collected debt is
      retired. CO2 budgets can go negative, so debts of any size are payable.
    """
    rem = remaining[
        (remaining["category"] == category)
        & (~remaining["emission-category"].isin(["non-co2", "combined"]))
    ].copy()
    part = rem["emission-category"].iloc[0]
    start_year = int(rem["remaining-from-year"].iloc[0])
    last_observed = str(int(rem["netting-end-year"].iloc[0]))

    emiss = pd.read_csv(
        reg["processed_dir"] / f"country_emissions_{part}_timeseries.csv"
    )
    base = pd.Series(emiss[last_observed].values, index=emiss["iso3c"].values)
    n_floored = int((base <= 0).sum())
    if n_floored:
        print(
            f"  {category}: {n_floored} net-sink countries floored to "
            f"{BASE_SHARE_FLOOR_MT} Mt for base-year shares (Decision 10)"
        )
    base = base.clip(lower=BASE_SHARE_FLOOR_MT)

    pop = pd.read_csv(reg["processed_dir"] / "country_population_timeseries.csv")

    config_cols = [c for c in _CONFIG_COLS if c in rem.columns]
    is_composite = category != "co2-ffi"

    # Non-CO2 historical deviation per CO2 configuration, read from the
    # combined rows (they inherit it through § 5's part pairing and carry the
    # same budget-style config keys as the CO2 part). Looked up by merge —
    # unlike tuple keys, a merge matches NaN config values.
    dev_lookup = None
    if is_composite:
        dev_lookup = remaining[
            (remaining["category"] == category)
            & (remaining["emission-category"] == "combined")
        ][[*config_cols, "iso3c", "historical-deviation"]]

    out_frames = []
    for key, cfg in rem.groupby(config_cols, dropna=False):
        budgets = pd.Series(
            cfg["remaining-budget"].values, index=cfg["iso3c"].values
        )
        regions = budgets.index
        base_cfg = base.reindex(regions)
        if base_cfg.isna().any():
            raise ValueError(
                f"{category}: missing base-year emissions for "
                f"{base_cfg[base_cfg.isna()].index.tolist()[:5]}"
            )
        modes = NONCO2_DEBT_MODES if is_composite else [None]
        for mode in modes:
            if mode == "co2-debit":
                matched = cfg[[*config_cols, "iso3c"]].merge(
                    dev_lookup, on=[*config_cols, "iso3c"], how="left"
                )
                deviation = pd.Series(
                    matched["historical-deviation"].values,
                    index=matched["iso3c"].values,
                ).reindex(regions)
                if deviation.isna().any():
                    raise ValueError(
                        f"{category}: no combined-row deviation match for "
                        "this configuration"
                    )
                debt = deviation.clip(lower=0.0)
            else:
                debt = pd.Series(0.0, index=regions)
            # The collected debt is retired (Decision 11): the global
            # allocated CO2 shrinks by the gross debt sum, so the envelope
            # pathway is rebuilt per mode to integrate to the reduced total,
            # keeping country pathways consistent with the smaller envelope.
            budgets_mode = budgets - debt
            global_pathway = calculate_exponential_decay_pathway(
                total_budget=float(budgets_mode.sum()),
                start_value=float(base_cfg.sum()),
                start_year=start_year,
                end_year=PATHWAY_END_YEAR,
            )
            for conv_year in DISTRIBUTION_GRID["convergence_year"]:
                pop_cfg = pd.Series(
                    pop[str(conv_year)].values, index=pop["iso3c"].values
                ).reindex(regions)
                for shape in DISTRIBUTION_GRID["shape"]:
                    for dev_year in DISTRIBUTION_GRID["deviation_end_year"]:
                        paths = distribute_remaining_budgets_pathways(
                            base_year_emissions=base_cfg,
                            population=pop_cfg,
                            global_pathway=global_pathway,
                            remaining_budgets=budgets_mode,
                            convergence_year=conv_year,
                            deviation_end_year=dev_year,
                            shape=shape,
                        )
                        paths.columns = [str(c) for c in paths.columns]
                        block = cfg.drop(
                            columns=["allocated-total", "consumed-actuals"]
                        ).set_index("iso3c")
                        block = block.join(paths)
                        block["adjusted-target"] = budgets_mode
                        if mode is not None:
                            block["nonco2-debt-mode"] = mode
                            block["nonco2-debt-paid"] = debt
                        block["shape"] = shape
                        block["deviation-end-year"] = dev_year
                        block["convergence-year"] = conv_year
                        out_frames.append(block.reset_index())

    out = pd.concat(out_frames, ignore_index=True)

    # Composite categories: the non-CO2 part is the allocated scenario pathway,
    # identical under both debt modes (the debt is settled in CO2 space or not
    # at all). Combined rows sum the distributed CO2 part and the allocated
    # non-CO2 pathway per mode and shape variant.
    if is_composite:
        ab = pd.read_parquet(reg["output_dir"] / "allocations_absolute.parquet")
        nonco2 = ab[ab["emission-category"] == "non-co2"].copy()
        pathway_years = [
            str(y) for y in range(start_year, PATHWAY_END_YEAR + 1)
        ]
        nonco2["nonco2-forward"] = nonco2[pathway_years].sum(axis=1)
        nd = nonco2.assign(
            family=nonco2["approach"],
            year=nonco2["first-allocation-year"].astype(int),
            preserve=nonco2["preserve-first-allocation-year-shares"].astype(bool),
        )
        pair_cols = [
            "iso3c", "family", "year", "preserve",
            "pre-allocation-responsibility-weight",
            "pre-allocation-responsibility-year",
            "pre-allocation-responsibility-per-capita",
            "pre-allocation-responsibility-exponent",
            "capability-weight", "capability-exponent",
        ]
        co2_part = out.assign(
            family=out["approach"].str.replace("-budget", "", regex=False),
            year=out["allocation-year"].astype(int),
            preserve=out["preserve-allocation-year-shares"].astype(bool),
        )
        merged = co2_part.merge(
            nd[pair_cols + pathway_years + ["nonco2-forward"]].drop_duplicates(
                pair_cols
            ),
            on=pair_cols,
            how="inner",
            suffixes=("", "-nonco2"),
        )
        for y in pathway_years:
            merged[y] = merged[y] + merged[f"{y}-nonco2"]
        # A combined row's target is the mode-adjusted CO2 target plus the
        # forward non-CO2 allocation, so every part verifies uniformly against
        # its own adjusted-target column.
        merged["adjusted-target"] = (
            merged["adjusted-target"] + merged["nonco2-forward"]
        )
        combined = merged[list(out.columns)].copy()
        combined["emission-category"] = "combined"
        if len(combined) != len(out):
            print(
                f"  {category}: paired {len(combined)}/{len(out)} distributed "
                "rows with a non-CO2 pathway (unpaired remain CO2-part only)"
            )

        # The allocated non-CO2 rows themselves (forward window), once per
        # configuration — no mode or shape variants apply to them. Pre-2024
        # year columns are dropped so the distributed output stays on the
        # forward window.
        nonco2_rows = nonco2.copy()
        nonco2_rows["adjusted-target"] = nonco2_rows["nonco2-forward"]
        past_cols = [
            c for c in nonco2_rows.columns
            if c.isdigit() and int(c) < start_year
        ]
        nonco2_rows = nonco2_rows.drop(columns=["nonco2-forward", *past_cols])

        out = pd.concat([out, nonco2_rows, combined], ignore_index=True)

    out["category"] = category
    return out


distributed_all = []
for category, reg in run_registry.items():
    dist = _distribute_category(category, reg, remaining_all)
    pq_path = reg["output_dir"] / "distributed_remaining_pathways.parquet"
    csv_path = reg["output_dir"] / "distributed_remaining_pathways.csv"
    dist.to_parquet(pq_path, index=False)
    dist.to_csv(csv_path, index=False)
    print(f"{category}: {len(dist)} pathway rows -> {pq_path.name} / {csv_path.name}")
    distributed_all.append(dist)

distributed_all = pd.concat(distributed_all, ignore_index=True)

# %% [markdown] tags=[]
# ### 6.1 Preview — EPC (ay=2015) under the normative grid
#
# Annual CO2-FFI allocations for example countries under the equal-per-capita
# baseline, showing how the shape and deviation-end-year choices front- or
# back-load debt redress. Debtor countries (fair share exhausted) go
# net-negative; the half-sine variants return to the per-capita baseline,
# the exponential variants do not.

# %% tags=[]
sel = distributed_all[
    (distributed_all["category"] == "co2-ffi")
    & (distributed_all["approach"] == "equal-per-capita-budget")
    & (distributed_all["allocation-year"] == 2015)
    & (distributed_all["preserve-allocation-year-shares"] == True)  # noqa: E712
]
plot_years = [c for c in sel.columns if c.isdigit()]
plot_countries = ["USA", "DEU", "CHN", "IND"]

fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True)
for ax, iso in zip(axes.flat, plot_countries):
    for _, row in sel[sel["iso3c"] == iso].iterrows():
        style = "-" if row["shape"] == "half-sine" else "--"
        ax.plot(
            [int(y) for y in plot_years],
            row[plot_years].astype(float) / 1000,
            style,
            label=f"{row['shape']}, dev {int(row['deviation-end-year'])}",
        )
    ax.axhline(0, color="black", lw=0.5)
    ax.set_title(iso)
    ax.set_ylabel("Gt CO2 / yr")
axes.flat[0].legend(fontsize=7)
fig.suptitle(
    "Distributed remaining CO2-FFI budgets, EPC ay=2015 — "
    "front- vs back-loaded debt redress"
)
fig.tight_layout()
plt.show()

# %% [markdown] tags=[]
# ### 6.2 Verification — do the pathways still add up to the remaining budgets?
#
# All emissions in this notebook are aggregated with **AR6 GWP100** (PRIMAP
# `KYOTOGHG (AR6GWP100)`; the unit registry applies the `AR6GWP100` context),
# so CO2 and non-CO2 quantities add on a consistent CO2e basis.
#
# For `all-ghg-ex-co2-lulucf`, one CO2-part creditor and one CO2-part debtor
# (the stock budget is where debt lives — Decision 6), across every
# shape/deviation variant and both non-CO2 debt modes:
#
# 1. **CO2-FFI part** — the cumulative distributed pathway (2024-2100) must
#    equal its `adjusted-target` exactly (closed-form guarantee of the
#    distribution function). Under `free-rider` that target is the § 5
#    remaining CO2 budget; under `co2-debit` it is that budget minus the
#    country's non-CO2 debt, which is retired (Decision 11). A debtor's
#    pathway integrates to its negative target either way.
# 2. **Non-CO2 part** — the allocated scenario pathway, unmodified in both
#    modes (Decision 12); its cumulative equals the § 5 forward allocation
#    and is non-negative by construction.
# 3. **Combined** — cumulative combined pathway = mode-adjusted CO2 target +
#    forward non-CO2 allocation (= the row's `adjusted-target`), exactly.
#    The difference between the two modes' combined totals for a country is
#    exactly its non-CO2 debt paid.

# %% tags=[]
VERIFY_CATEGORY = "all-ghg-ex-co2-lulucf"
VERIFY_CONFIG = {  # EPC ay=2015, single-year shares — simplest baseline
    "approach": "equal-per-capita-budget",
    "allocation-year": 2015,
    "preserve-allocation-year-shares": True,
}

rem_cat = remaining_all[remaining_all["category"] == VERIFY_CATEGORY]
rem_cfg = rem_cat[
    (rem_cat["approach"] == VERIFY_CONFIG["approach"])
    & (rem_cat["allocation-year"] == VERIFY_CONFIG["allocation-year"])
    & (rem_cat["preserve-allocation-year-shares"] == True)  # noqa: E712
]

# The non-CO2 part carries pathway-style keys (approach "equal-per-capita",
# first-allocation-year), so its deviation is read from the combined rows,
# which inherit it through § 5's part pairing.
combined_rem = rem_cfg[rem_cfg["emission-category"] == "combined"].set_index("iso3c")
co2_rem = rem_cfg[rem_cfg["emission-category"] == "co2-ffi"].set_index("iso3c")

# Debtor/creditor is a CO2 stock-budget concept: with the non-CO2 part defined
# as a forward flow (Decision 6), combined remaining can be positive even
# for a country whose CO2 fair share is deep in debt.
candidates = co2_rem.loc[
    co2_rem.index.intersection(EXAMPLE_COUNTRIES), "remaining-budget"
]
creditor = candidates.idxmax()
debtor = candidates.idxmin()
assert candidates[creditor] > 0 > candidates[debtor], (
    "Need one positive- and one negative-CO2-remaining country among "
    f"EXAMPLE_COUNTRIES; got {candidates.to_dict()}"
)
print(
    f"creditor: {creditor} (CO2 part {candidates[creditor] / 1000:+.1f} Gt, "
    f"combined {combined_rem.loc[creditor, 'remaining-budget'] / 1000:+.1f} Gt) | "
    f"debtor: {debtor} (CO2 part {candidates[debtor] / 1000:+.1f} Gt, "
    f"combined {combined_rem.loc[debtor, 'remaining-budget'] / 1000:+.1f} Gt)"
)

reg_v = run_registry[VERIFY_CATEGORY]
ab_v = pd.read_parquet(reg_v["output_dir"] / "allocations_absolute.parquet")
nonco2_alloc = ab_v[
    (ab_v["emission-category"] == "non-co2")
    & (ab_v["approach"] == "equal-per-capita")
    & (ab_v["first-allocation-year"] == 2015)
    & (ab_v["preserve-first-allocation-year-shares"] == True)  # noqa: E712
].set_index("iso3c")
nonco2_years_all = sorted(c for c in nonco2_alloc.columns if c.isdigit())

# Budget-part and combined rows carry budget-style keys; the allocated
# non-CO2 rows carry the pathway analogue keys — select both.
_cat = distributed_all[distributed_all["category"] == VERIFY_CATEGORY]
dist_cat = _cat[
    (
        (_cat["approach"] == VERIFY_CONFIG["approach"])
        & (_cat["allocation-year"] == VERIFY_CONFIG["allocation-year"])
        & (_cat["preserve-allocation-year-shares"] == True)  # noqa: E712
    )
    | (
        (_cat["approach"] == "equal-per-capita")
        & (_cat["first-allocation-year"] == VERIFY_CONFIG["allocation-year"])
        & (_cat["preserve-first-allocation-year-shares"] == True)  # noqa: E712
    )
]
dist_years = sorted(c for c in dist_cat.columns if c.isdigit())
fwd_years = dist_years  # 2024-2100
past_years = [y for y in nonco2_years_all if y not in fwd_years]  # 2015-2023

# Actual non-CO2 emissions, for the global deviation statement
nonco2_actual = pd.read_csv(
    reg_v["processed_dir"] / "country_emissions_non-co2_timeseries.csv"
).set_index("iso3c")

rows = []
for iso in (creditor, debtor):
    iso_rows = dist_cat[dist_cat["iso3c"] == iso]
    non_part = iso_rows[iso_rows["emission-category"] == "non-co2"].iloc[0]
    cmltv_non = non_part[fwd_years].astype(float).sum()
    for (mode, shape, dev), grp in iso_rows[
        iso_rows["emission-category"].isin(["co2-ffi", "combined"])
    ].groupby(["nonco2-debt-mode", "shape", "deviation-end-year"]):
        co2_part = grp[grp["emission-category"] == "co2-ffi"].iloc[0]
        comb_part = grp[grp["emission-category"] == "combined"].iloc[0]
        cmltv_co2 = co2_part[fwd_years].astype(float).sum()
        cmltv_comb = comb_part[fwd_years].astype(float).sum()
        rows.append(
            {
                "iso3c": iso,
                "mode": mode,
                "shape": shape,
                "dev-year": int(dev),
                "cmltv co2-ffi": cmltv_co2,
                "co2 target": co2_part["adjusted-target"],
                "co2 residual": cmltv_co2 - co2_part["adjusted-target"],
                "debt paid": co2_part["nonco2-debt-paid"],
                "cmltv non-co2": cmltv_non,
                "non-co2 target": non_part["adjusted-target"],
                "non-co2 residual": cmltv_non - non_part["adjusted-target"],
                "cmltv combined": cmltv_comb,
                "combined target": comb_part["adjusted-target"],
                "combined residual": cmltv_comb - comb_part["adjusted-target"],
            }
        )

recon = pd.DataFrame(rows)
with pd.option_context("display.width", 320, "display.float_format", "{:.2f}".format):
    print(recon.to_string(index=False))

assert recon["co2 residual"].abs().max() < 1.0, (
    "CO2 parts must integrate to their mode-adjusted targets"
)
assert recon["non-co2 residual"].abs().max() < 1.0, (
    "Non-CO2 pathways must integrate to the forward allocation"
)
assert recon["combined residual"].abs().max() < 1.0, (
    "Combined pathways must integrate to their adjusted targets"
)
nonneg_all = distributed_all[distributed_all["emission-category"] == "non-co2"]
nonneg_min = nonneg_all[fwd_years].astype(float).min().min()
assert nonneg_min >= -1e-6, "Allocated non-CO2 pathways must be non-negative"
print("\nAll integrals verified (residuals < 1 Mt CO2e) under both debt modes.")

# Global statement: past non-CO2 over- and under-use across countries
common = nonco2_alloc.index.intersection(nonco2_actual.index)
global_deviation = (
    nonco2_actual.loc[common, past_years].astype(float).sum().sum()
    - nonco2_alloc.loc[common, past_years].astype(float).sum().sum()
)
global_actual = nonco2_actual.loc[common, past_years].astype(float).sum().sum()
print(
    f"\nGlobal non-CO2 2015-2023: actual {global_actual / 1000:.1f} Gt CO2e; "
    f"net deviation vs allocation {global_deviation / 1000:+.1f} Gt CO2e "
    f"({100 * global_deviation / global_actual:+.1f}%) — over- and under-use "
    "nearly cancel globally, which is the case for the free-rider mode; "
    "the co2-debit mode settles the per-country transfers in CO2 space."
)
_deb = recon[(recon["iso3c"] == debtor) & (recon["mode"] == "co2-debit")].iloc[0]
d_dev = combined_rem.loc[debtor, "historical-deviation"]
c_dev = combined_rem.loc[creditor, "historical-deviation"]
gross_debt = combined_rem["historical-deviation"].clip(lower=0.0).sum()
global_co2_rem = co2_rem["remaining-budget"].sum()
print(
    f"  {debtor}: {d_dev / 1000:+.1f} Gt CO2e past non-CO2 over-use — under "
    f"co2-debit its remaining CO2 budget is reduced by "
    f"{_deb['debt paid'] / 1000:.1f} Gt, which is retired (CO2 target "
    f"{_deb['co2 target'] / 1000:+.1f} Gt vs "
    f"{co2_rem.loc[debtor, 'remaining-budget'] / 1000:+.1f} Gt under "
    "free-rider)."
)
print(
    f"  {creditor}: {c_dev / 1000:+.1f} Gt CO2e past non-CO2 under-use — "
    "earns nothing in either mode (collected debt is retired)."
)
print(
    f"  Gross non-CO2 debt retired from the global CO2 allocation under "
    f"co2-debit: {gross_debt / 1000:.1f} Gt CO2e "
    f"({100 * gross_debt / global_co2_rem:.1f}% of the global remaining CO2 "
    "budget at this configuration)."
)

# %% [markdown] tags=[]
# The verification figure: annual pathways by gas part under `co2-debit`
# (left) and the running cumulative combined pathway under both modes
# (right), for the creditor (top) and debtor (bottom). Each cumulative curve
# converges exactly to its mode's dashed target line; the gap between the
# two lines is exactly the country's non-CO2 debt paid (zero for countries
# with no debt).

# %% tags=[]
fig, axes = plt.subplots(2, 2, figsize=(13, 8), sharex=True)
yrs_int = [int(y) for y in fwd_years]

for row_i, iso in enumerate((creditor, debtor)):
    sub = dist_cat[
        (dist_cat["iso3c"] == iso) & (dist_cat["deviation-end-year"] == 2100)
    ]
    non_part = dist_cat[
        (dist_cat["iso3c"] == iso)
        & (dist_cat["emission-category"] == "non-co2")
    ].iloc[0]

    ax = axes[row_i, 0]
    for shape, ls in (("half-sine", "-"), ("exponential", "--")):
        g = sub[(sub["shape"] == shape) & (sub["nonco2-debt-mode"] == "co2-debit")]
        co2_part = g[g["emission-category"] == "co2-ffi"].iloc[0]
        comb_part = g[g["emission-category"] == "combined"].iloc[0]
        ax.plot(yrs_int, comb_part[fwd_years].astype(float) / 1000, ls,
                color="tab:blue", label=f"combined ({shape})")
        ax.plot(yrs_int, co2_part[fwd_years].astype(float) / 1000, ls,
                color="tab:orange", alpha=0.7, label=f"co2-ffi ({shape})")
    ax.plot(yrs_int, non_part[fwd_years].astype(float) / 1000, ":",
            color="tab:green", label="non-co2 (allocated, both modes)")
    ax.axhline(0, color="black", lw=0.5)
    ax.set_title(f"{iso} — annual under co2-debit, dev-year 2100")
    ax.set_ylabel("Gt CO2e / yr")
    if row_i == 0:
        ax.legend(fontsize=7)

    ax = axes[row_i, 1]
    for mode, color in (("free-rider", "tab:gray"), ("co2-debit", "tab:blue")):
        g = sub[
            (sub["shape"] == "half-sine")
            & (sub["nonco2-debt-mode"] == mode)
            & (sub["emission-category"] == "combined")
        ].iloc[0]
        ax.plot(
            yrs_int,
            g[fwd_years].astype(float).cumsum() / 1000,
            "-", color=color, label=f"cumulative combined ({mode})",
        )
        ax.axhline(g["adjusted-target"] / 1000, color=color, ls="--",
                   alpha=0.8, label=f"target ({mode})")
    dev_val = combined_rem.loc[iso, "historical-deviation"] / 1000
    dev_note = (
        "past non-CO2 over-use, charged to CO2 space under co2-debit"
        if dev_val > 0
        else "past non-CO2 under-use, earns nothing in either mode"
    )
    ax.set_title(
        f"{iso} — cumulative combined vs mode targets\n"
        f"historical non-CO2 deviation {dev_val:+.1f} Gt: {dev_note}",
        fontsize=9,
    )
    ax.set_ylabel("Gt CO2e (cumulative)")
    if row_i == 0:
        ax.legend(fontsize=7)

fig.suptitle(
    f"Verification: {VERIFY_CATEGORY} pathways integrate to remaining budgets "
    "(AR6 GWP100), under free-rider and co2-debit non-CO2 debt modes"
)
fig.tight_layout()
plt.show()

# %% [markdown] tags=[]
# ---
# ## 7. Implementation Notes
#
# This notebook implements PRR2023's allocation methodology using fair-shares'
# canonical data stack. The equations in § 1 are realised with the configurations
# in § 3; this section documents the implementation choices where fair-shares
# differs from PRR2023's own R code at the Zenodo archive
# (Pelz, Rogelj, Riahi 2023, https://doi.org/10.5281/zenodo.8035839,
# `iiasa/EUEquityReport_Replication` v1.1).
#
# ### 7.1 Data stack
#
# - **Population**: `un-owid-2025` — UN historical + WPP 2024 projections to 2100
# - **GDP**: `wdi-2025` — WDI `NY.GDP.MKTP.PP.KD` (constant 2017 international $ PPP)
# - **Emissions**: `primap-202503` — PRIMAP-hist v2.6.1 (Gütschow et al.),
#   territorial; observed country data through 2023
# - **NGHGI LULUCF**: `melo-2026` — Melo et al. LULUCF Data Hub v3.1.1,
#   2000-2023, used for the `all-ghg` category only
# - **RCB anchors**: `ar6_2020` (IPCC AR6 WG1, Canadell et al. 2021),
#   `lamboll_2023`, `forster_2024` — all computed; the report anchor is
#   `ar6_2020` at 1.5C / 50%
#
# ### 7.2 Key architectural choices
#
# **Country-level allocation.** fair-shares computes allocation shares at ISO3c
# level (~173 countries) and aggregates to larger groupings (EU27, R11 regions)
# post-hoc. PRR2023 aggregates country data to 11 R11 regions first, then computes
# shares at the regional level. For linear operations (EPC, ECPC) the two are
# algebraically identical when summed back to the same grouping. For non-linear
# operations (responsibility/capability-adjusted with `1/x` or `1/sqrt(x)`
# penalty), Jensen's inequality applies: country-level and R11-level allocations
# give different answers whenever within-region variance is material. See
# `docs/science/allocations.md`.
#
# **Capability snapshot.** PRR2023 uses a single-year GDP-per-capita snapshot
# (1990 for `ay=1990`, 2014 for `ay=2015`). The budget parts replicate this via
# `capability_reference_year`. The pathway (non-CO2) parts compute capability
# year-by-year — the snapshot kwarg does not exist for pathway approaches
# (Decision 8).
#
# **Approach coverage.** All four approaches PRR2023 quantifies are configured,
# on both the EPC and ECPC bases, for every Table 18 indicator with a data
# source: responsibility windows 1850-1989 (ay=1990), 1850-2014 and 1990-2014
# (ay=2015), in total and per-capita form; capability snapshots 1990 and 2014.
# Consumption CO2 and capital stock are omitted (no source; Decision 1). The
# responsibility-capability-need composite is not quantified (Decision 2).
#
# **Multi-gas decomposition.** For `all-ghg-ex-co2-lulucf` and `all-ghg`, RCBs
# constrain CO2 only, so the library allocates the CO2 component as a budget
# and the non-CO2 component as a pathway from AR6 scenarios of the matching
# climate category, in NGHGI convention where land use is involved. See
# `docs/science/other-operations.md` for the decomposition and the BM-to-NGHGI
# convention gap.
#
# ### 7.3 Where fair-shares and PRR2023 differ on inputs
#
# | Aspect | fair-shares | PRR2023 |
# |---|---|---|
# | GDP convention | constant 2017 PPP (`NY.GDP.MKTP.PP.KD`) | same |
# | Population historical | un-owid-2025 | OWID historical CSV |
# | Population projection | un-owid-2025 (UN WPP 2024) | IIASA WiC SSP2 v9_130115 (2013 vintage) |
# | Emissions | PRIMAP-hist v2.6.1 (CO2-FFI) | GCB 2022 |
# | RCB anchor | `ar6_2020` (+ Lamboll, Forster) | `ar6_2020` (Canadell et al. 2021) |
# | Allocation granularity | country (ISO3c) | R11 regions |
# | Capability indicator | GDP per capita (snapshot year kwarg) | GDP pc and capital stock pc |
# | Responsibility indicator | territorial CO2 (PRIMAP) | territorial (GCB) and consumption CO2 |
# | Penalty functions | `power`, exponents 1.0 / 0.5 | `1/x` and `1/sqrt(x)` |
#
# Downstream users comparing against PRR2023's published figures should
# aggregate fair-shares' country-level output to PRR2023's R11 regions before
# comparing — otherwise the country-vs-R11 Jensen gap will appear in the
# residuals. The R11 aggregation maps are in the PRR2023 archive at
# `Data/countrygrouping/isorgn.csv`.

# %% tags=[]
