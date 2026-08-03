# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions: [SemVer](https://semver.org/).

## [0.3.0] — unreleased

### Added

- `fair-shares fetch-data`: downloads every input dataset from source, verifies pinned checksums, records provenance in `data/PROVENANCE.md`. Missing files also fetch automatically on first use.
- Python API reference (`docs/api/python-api.md`) for pip-only users.
- Root `CONTRIBUTING.md`. This changelog.

### Changed

- **Breaking:** `pip install fair-shares` installs only the allocation library. Notebook/pipeline tools moved to the `pipeline` extra, documentation tools to `docs`.
- The package works when installed outside a clone. Data/output locations resolve: explicit argument → `FAIR_SHARES_DATA_DIR`/`FAIR_SHARES_OUTPUT_DIR` → existing per-user directory → repo root.
- Config files moved into the package (`src/fair_shares/conf/`); repo-root `conf/` removed.

### Deprecated

- `project_root=` in `calculate_allocation_timeseries` — use `data_dir=`/`output_dir=`. Still works, warns.

### Removed

- Four unused data sources (IMF WEO, WID.world, Taiwan GDP override, Grassi 2023 LULUCF) with their notebooks and config entries.

### Fixed

- Global Carbon Budget citation pointed at a DOI that does not resolve; now the correct paper DOI (10.5194/essd-17-965-2025) plus data-product DOI (10.18160/GCP-2024).
- Licence statements corrected: WIID is CC BY-NC-SA 3.0 IGO, UN/OWID population is mixed-terms, CMIP7 is CC-BY-SA-4.0 (author-confirmed).
