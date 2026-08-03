# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer](https://semver.org/).

## [0.3.0] — unreleased

### Added

- `fair-shares fetch-data`: downloads every input dataset from source, verifies pinned checksums, records provenance in `data/PROVENANCE.md`. Missing files also fetch automatically on first use.
- Python API reference (`docs/api/python-api.md`) for pip-only users.
- Root `CONTRIBUTING.md`. This changelog.
- World Bank WDI Gini index (`SI.POV.GINI`) as a Gini source, with `analysis/gini_source_comparison.py` reporting the coverage and value differences against WIID.

### Changed

- **Breaking:** `pip install fair-shares` installs only the allocation library. Notebook/pipeline tools moved to the `pipeline` extra, documentation tools to `docs`.
- The package works when installed outside a clone. Data/output locations resolve: explicit argument → `FAIR_SHARES_DATA_DIR`/`FAIR_SHARES_OUTPUT_DIR` → existing per-user directory → repo root.
- Config files moved into the package (`src/fair_shares/conf/`); repo-root `conf/` removed.
- **Breaking:** the default Gini source is now World Bank WDI (`wdi-2025`), which is CC-BY-4.0. WIID stays available as `active_gini_source=unu-wider-2025` but is opt-in, and outputs built on it cannot be redistributed under CC BY 4.0. Output directory names change, so existing WIID runs are not overwritten. The two sources give materially different capability-based allocations — WDI/PIP is consumption-based for most low- and middle-income countries.
- **Breaking:** analysis-country membership no longer depends on Gini availability. A country with complete emissions, GDP and population is now in the analysis even without a Gini value, and receives the analysis-country mean (`general.gini_missing_policy: fallback-mean`, or `strict` to refuse). The country set grows by 9 on the standard sources; `country_data_coverage_summary.csv` gains a `gini_imputed` column.
- Gini source config replaces the unused `world_key` and `gini_year` keys with `selection` and `year_window`, both of which the notebooks read.

### Deprecated

- `project_root=` in `calculate_allocation_timeseries` — use `data_dir=`/`output_dir=`. Still works, warns.

### Removed

- Four unused data sources (IMF WEO, WID.world, Taiwan GDP override, Grassi 2023 LULUCF) with their notebooks and config entries.

### Fixed

- Global Carbon Budget citation pointed at a DOI that does not resolve; now the correct paper DOI (10.5194/essd-17-965-2025) plus data-product DOI (10.18160/GCP-2024).
- Licence statements corrected: WIID is CC BY-NC-SA 3.0 IGO, UN/OWID population is mixed-terms, CMIP7 is CC-BY-SA-4.0 (author-confirmed).
- The Python API's preprocessing path wrote `country_gini_stationary.csv` without a Rest-of-World row, unlike the notebook path. Both now use the same code.
- Notebook `100_data_preprocess_rcbs` passed the removed `project_root=` argument to `load_and_process_rcbs`, so the RCB pipeline could not run.
- The Gini-adjusted approaches ignored Gini entirely when `capability_reference_year` named a year before `allocation_year`: the capability snapshot was read from the unfiltered inputs without the adjustment, on both the budget and pathway side. Results on that parameterisation change — on the standard sources, China's share of a `per-capita-adjusted-gini-budget` allocation moves from 10.8% to 5.3% and India's from 23.2% to 28.4%.
