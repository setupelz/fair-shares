---
title: Updating data each year
description: Move fair-shares to a new release of an input dataset
---

# Updating data each year

Most inputs have a new release every year: PRIMAP-hist, the Global Carbon Budget, the LULUCF Data Hub, World Bank WDI, UN population and the indicators behind the remaining carbon budgets.
This guide moves a run to a new release.
[Adding data sources](../dev-guide/adding-data-sources.md) covers a source the library has never used.

## 1. See what you have

```bash
uv run fair-shares fetch-data --list     # source, version, size, licence
uv run fair-shares fetch-data --verify   # re-hash the files you have
```

## 2. Register the new release

Each release is its own source with its own key, such as `primap-202609` for PRIMAP-hist v2.8.
Keep the old key, so earlier results stay reproducible.

1. Add a registry entry to `src/fair_shares/conf/data_registry.yaml`: URL, checksum, licence, citation and tier. Check the licence again. PRIMAP-hist moved from CC BY to CC BY-NC-SA between releases.
2. Record each DOI you verified in `tests/fixtures/verified_dois.yaml`, and place a `CITATION.md` in the data folder.
3. Add the source to `src/fair_shares/conf/data_sources/data_sources_unified.yaml`. A new PRIMAP-hist release reuses `101_data_preprocess_emiss_primap` through the `notebook` key, so it needs no new notebook.
4. Run `uv run fair-shares fetch-data --source <key>`, then `--verify`.

[Registering the source](../dev-guide/adding-data-sources.md#registering-the-source) gives the details and the tests that check each step.

## 3. Sources without a version number

The World Bank and Our World in Data overwrite their exports in place.
`--verify` reports a changed file as drift, not as damage.
Re-download with `uv run fair-shares fetch-data --source <key> --force`, then update its `reference_sha256` in the registry.
`PROVENANCE.md` records the hash of the file you used.

## 4. Update the budget inputs

Budgets are rebased to 2020 with observed global CO2 from the Global Carbon Budget global workbook.
A new workbook is a manual download ([Files you place yourself](../quickstart.md#files-you-place-yourself)).
Point `observed_co2_path` in `data/rcbs/rcbs.yaml` at it.
New published budgets, such as a new year of the Indicators of Global Climate Change, are entries under `rcb_data` in the same file ([Remaining carbon budgets](../science/remaining-carbon-budgets.md#published-budgets)).

## 5. Run with the new release

Name the new key in the `active_sources` of your notebook or Python call.
The library defaults sit in the notebooks and in `src/fair_shares/library/preprocessing/config.py`.

Each processed folder carries a provenance stamp: hashes of the package version, the run configuration, the preprocessing code, `rcbs.yaml` and the input files.
A changed stamp rebuilds the folder on the next run, and the log names what changed.
`FAIR_SHARES_TRUST_CACHE=1` reuses a folder without the check.

## 6. Check the result

- `country_data_coverage_summary.csv` in the processed folder lists the analysis countries and rest of world. A new release can move a country between them.
- The last observed year sets the year from which budgets remain ([Remaining budgets and annual pathways](pipeline-map.md#4-remaining-budgets-and-annual-pathways-notebook-601-and-the-python-api)).
- `uv run fair-shares cite` lists the citations and licences of the new run.
