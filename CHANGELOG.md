# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer](https://semver.org/).

## [0.3.0] — unreleased

### Added

- `fair-shares fetch-data`: downloads every input dataset from source, verifies pinned checksums, records provenance in `data/PROVENANCE.md`. Missing files also fetch automatically on first use.
- Python API reference (`docs/api/python-api.md`) for pip-only users.
- Root `CONTRIBUTING.md`. This changelog.
- LULUCF Data Hub v4.0.0 (gap-filled NGHGI, 187 countries, 2000-2024) as the opt-in LULUCF source `melo-2026-v4`. `melo-2026` (v3.1.1) stays the default.
- Global Carbon Budget 2025 national fossil CO2 (1850-2024) as the opt-in emissions source `gcb-2025`, `co2-ffi` only. Its world row excludes international bunkers and the 1991 Kuwaiti oil fires, and its runs take bunkers from the same file. The pipeline asks an emissions source only for the categories it declares. `primap-202503` stays the default.
- RCB sources `forster_2026` (IGCC 2025, from 2026) and `ar6_wg1_2021` (AR6 WGI Table SPM.2, from 2020), each with 1.5, 1.7 and 2°C budgets. Their deductions use AR6 scenarios in a peak-warming band (`scenario_selection: peak-warming-band` in `rcbs.yaml`). The band keeps only scenarios that reach net-zero CO2 by 2100, because a remaining carbon budget runs to net-zero CO2 (14, 111 and 37 of 14, 131 and 69 scenarios at 1.5, 1.7 and 2°C). A budget label without a scenario set and an empty band raise an error. A rebase with missing emission years raises an error, and the pipeline skips that source with a warning. The band rule leaves the budgets of the existing sources unchanged; the bunker rebase under "Fixed" changes them.
- `rebase_fill_max_years` in `rcbs.yaml` (default 1). When a world series of the rebase (fossil CO2, bunkers, LULUCF) ends before the year before the budget baseline, each later year takes the last observed value, up to this number of years, with a warning that names the source, the series, the years and the value. The fill is a placeholder until observed data are published. With `gcb-2025` (observed to 2024) `forster_2026` rebases with 2025 filled. With PRIMAP (observed to 2023) it needs two years and stays skipped. 0 turns the fill off.
- World Bank WDI Gini index (`SI.POV.GINI`) as a Gini source, with `analysis/gini_source_comparison.py` reporting the coverage and value differences against WIID.

### Changed

- **Breaking:** `pip install fair-shares` installs only the allocation library. Notebook/pipeline tools moved to the `pipeline` extra, documentation tools to `docs`.
- The package works when installed outside a clone. Data/output locations resolve: explicit argument → `FAIR_SHARES_DATA_DIR`/`FAIR_SHARES_OUTPUT_DIR` → existing per-user directory → repo root.
- Config files moved into the package (`src/fair_shares/conf/`); repo-root `conf/` removed.
- **Breaking:** the default Gini source is now World Bank WDI (`wdi-2025`), which is CC-BY-4.0. WIID stays available as `active_gini_source=unu-wider-2025` but is opt-in, and outputs built on it cannot be redistributed under CC BY 4.0. Output directory names change, so existing WIID runs are not overwritten. The two sources give materially different capability-based allocations — WDI/PIP is consumption-based for most low- and middle-income countries.
- **Breaking:** analysis-country membership no longer depends on Gini availability. A country with complete emissions, GDP and population is now in the analysis even without a Gini value, and receives the analysis-country mean (`general.gini_missing_policy: fallback-mean`, or `strict` to refuse). The country set grows by 9 on the standard sources; `country_data_coverage_summary.csv` gains a `gini_imputed` column.
- Gini source config replaces the unused `world_key` and `gini_year` keys with `selection` and `year_window`, both of which the notebooks read.
- Allocation years start at 1850 (was 1900). With `capability_reference_year` set, the adjusted budget approaches need GDP at the reference year only, so `allocation_year` can precede the GDP series. For `co2` and `all-ghg`, the parameter grid checks `pre_allocation_responsibility_year` against the first year of the responsibility emissions frame it receives.

### Deprecated

- `project_root=` in `calculate_allocation_timeseries` — use `data_dir=`/`output_dir=`. Still works, warns.

### Removed

- Four unused data sources (IMF WEO, WID.world, Taiwan GDP override, Grassi 2023 LULUCF) with their notebooks and config entries.

### Fixed

- Global Carbon Budget citation pointed at a DOI that does not resolve; now the correct paper DOI (10.5194/essd-17-965-2025) plus data-product DOI (10.18160/GCP-2024).
- Licence statements corrected: WIID is CC BY-NC-SA 3.0 IGO, UN/OWID population is mixed-terms, CMIP7 is CC-BY-SA-4.0 (author-confirmed).
- The Python API's preprocessing path wrote `country_gini_stationary.csv` without a Rest-of-World row, unlike the notebook path. Both now use the same code.
- Notebook `100_data_preprocess_rcbs` passed the removed `project_root=` argument to `load_and_process_rcbs`, so the RCB pipeline could not run.
- Adjusted budgets of RCB sources with a baseline after 2020 were too low. The rebase to 2020 added world fossil emissions, which exclude international bunkers, and the bunker deduction covered 2020 to net zero, so the bunkers of 2020 to the year before the baseline were deducted and never added. The rebase now adds them (new output column `rebase_bunkers_mt`). Every adjusted budget of `lamboll_2023` (baseline 2023) rises by 2,822 Mt CO2 and every adjusted budget of `forster_2024` (baseline 2024) by 3,959 Mt CO2, for `co2-ffi` and `co2`, with PRIMAP emissions and `gcb-2024` bunkers. `ar6_2020` (baseline 2020) is unchanged. `process_rcb_to_2020_baseline` takes the bunker series as `world_bunker_emissions`.
- `build_nghgi_world_co2_timeseries` subtracted bunkers from a world fossil series that already excludes them (871 Mt CO2 in 2020; 20,770 Mt over 2000-2019). World `co2` is now fossil plus LULUCF, as in notebook `100_data_preprocess_rcbs`, and the function no longer takes `bunker_ts`. The error reached `run_rcb_preprocessing` and notebook `106_generate_pathways_from_rcbs`; budget files written by notebook 100 did not contain it.
- `compute_bunker_deduction` treated 2023 as the last observed bunker year for every source. It now reads the last year from the bunker data, so `gcb-2025` runs use the observed 2024 value and extrapolate the 2024 rate. Runs with `gcb-2024` bunkers give the same deduction as before.
- `calculate_budget_from_rcb` summed only the years present when the allocation year preceded the first year of the world emissions series (for example `co2`, which starts in 2000, with allocation year 1990). It now raises an error that names the missing years and the first available year.
- The Gini-adjusted approaches ignored Gini entirely when `capability_reference_year` named a year before `allocation_year`: the capability snapshot was read from the unfiltered inputs without the adjustment, on both the budget and pathway side. Results on that parameterisation change — on the standard sources, China's share of a `per-capita-adjusted-gini-budget` allocation moves from 10.8% to 5.3% and India's from 23.2% to 28.4%.
