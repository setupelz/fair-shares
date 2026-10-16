---
title: Adding data sources
description: How to add a new data source to the fair-shares pipeline
---

# Adding data sources

A data source is an entry in `src/fair_shares/conf/data_sources/data_sources_unified.yaml`, a registry entry, and a preprocessing notebook in the `notebooks/1xx_*.py` series.
A new release of a source the library already uses is simpler: see [Updating data each year](../user-guide/update-data.md).

| Type | Purpose | Current sources |
| --- | --- | --- |
| `emissions` | Historical emissions without land use | PRIMAP-hist v2.8 `primap-202609` (default), v2.6.1 `primap-202503`, Global Carbon Budget 2025 `gcb-2025` |
| `gdp` | Capability | World Bank WDI |
| `population` | Per capita calculations | UN/OWID |
| `gini` | Inequality within countries | World Bank WDI (default), UNU-WIDER WIID |
| `lulucf` | National-inventory land-use CO₂ | Melo et al. (2026): `melo-2026-v4` (default), `melo-2026` |
| `targets` | Global limits | AR6 scenarios, remaining carbon budgets |
| scenario sources | Scenario-derived budget terms | `ar6`, `sci` in `src/fair_shares/conf/scenario_sources.yaml` |

## 1. Place the raw data

Put the files in `data/<type>/<source>-<year>/`, for example `data/emissions/my-source-2026/`. The `{source}-{year}` name versions the source.

## 2. Configure the source

Add an entry to `src/fair_shares/conf/data_sources/data_sources_unified.yaml`:

```yaml
# Example: Adding a new emissions source
emissions:
  primap-202609:
    # ... existing source ...

  my-source-2026: # New source
    path: "data/emissions/my-source-2026/emissions_data.csv"
    data_parameters:
      available_categories:
        - co2-ffi
        - all-ghg
      world_key: "WORLD" # How the source identifies global totals
      scenario: "HISTCR" # Optional: historical scenario identifier
      bunkers_source: "gcb-2025" # Optional: registry name of the bunker data
      # Optional: coverage rule for analysis countries
      coverage: { emissions_recorded_before: 1990, population_from: 1850 }
```

### Common Configuration Parameters

| Parameter              | Purpose                                           |
| ---------------------- | ------------------------------------------------- |
| `path`                 | Relative path to data file                        |
| `available_categories` | Which emission categories this source provides    |
| `world_key`            | String used to identify global totals in the data |
| `scenario`             | Optional. Historical scenario, for sources that have one |
| `bunkers_source`       | Optional. Bunker data paired with an emissions source (default `gcb-2025`) |
| `coverage`             | Optional. Coverage rule for analysis countries (default: none) |

The pipeline asks an emissions source only for the categories in `available_categories`. A source that declares `co2-ffi` alone, such as `gcb-2025`, runs one pass of its notebook 101 and supports `co2-ffi` runs.

By default, an analysis country has complete emissions, GDP and population from 1990 through the last year of each dataset. A `coverage` block adds two tests, and a country that fails either one joins rest-of-world. `emissions_recorded_before` requires a value in the raw emissions file in a year before the threshold. `population_from` requires population for every year from the threshold. A source that zero-fills blank years needs the first test, because a blank and a reported zero look the same after the fill. Its notebook 101 writes `emiss_<category>_first_recorded_year.csv` (columns `iso3c`, `first_recorded_year`) for each category it provides. The rule is `coverage_exclusions` in `src/fair_shares/library/preprocessing/coverage.py`. `country_data_coverage_summary.csv` names the failed test for each country in the column `coverage_rule_failed`. A source without the block keeps the default check alone, and its coverage summary has no such column. `gcb-2025` sets both tests.

### Registering the source {#registering-the-source}

Every new source needs three things:

1. **Registry entry.** Add it to `src/fair_shares/conf/data_registry.yaml` with its URL, checksum, licence, citation and `tier`. `default` sources download with a plain `fetch-data`, `optional` ones with `--all`, and `manual` ones print instructions for a file the user places. State in a comment what the licence means for outputs, as the `primap-202609` entry does. `tests/unit/test_data_registry.py` fails if a source lacks a licence or citation, or if a `data/` path in the config has no registry entry. A registered source downloads on first use.
2. **Verified DOI.** Look up each DOI the entry claims at DataCite, Crossref or doi.org. Record it in `tests/fixtures/verified_dois.yaml` with the evidence and the date. `test_data_registry.py` and `test_citations.py` fail on any DOI missing from that file. `uv run pytest -m network` re-resolves the recorded DOIs (`test_dois_resolve.py`).
3. **`CITATION.md`.** Place one in the source's data folder with the full citation, DOI and licence, as the existing sources do.

Assert only a DOI or licence you have verified upstream. A source with no DOI gets name-only credit.

## 3. Write the preprocessing notebook

The Snakefile builds the notebook name from the source key: `101_data_preprocess_emiss_{source}.py` for emissions and `108_data_preprocess_bunkers_{bunkers_source}.py` for bunkers.
An emissions entry with a `notebook` key names the notebook instead. Both PRIMAP-hist entries set `notebook: "101_data_preprocess_emiss_primap"`, so a new PRIMAP release needs a config entry and a registry entry and no new notebook.

The notebook reads the path in the config and writes to the run's intermediate directory, which the Snakefile sets through `source_id`:

```python
import pandas as pd
from pyprojroot import here
from fair_shares.library.utils import ensure_string_year_columns

df = pd.read_csv(here() / "data/emissions/my-source-2026/emissions_data.csv")
df["iso3c"] = convert_to_iso3c(df["country_column"])          # your country-code mapping
df = df.set_index(["iso3c", "unit", "emission-category"])
df = ensure_string_year_columns(df)

if "World" not in df.index.get_level_values("iso3c"):        # add a World row if missing
    world = df.groupby(["unit", "emission-category"]).sum()
    world["iso3c"] = "World"
    df = pd.concat([df, world.set_index("iso3c", append=True)])

out = here() / f"output/{source_id}/intermediate/emissions/emiss_co2-ffi_timeseries.csv"
out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out)
```

Every output follows one index structure, with year columns as strings (`"1990"`):

| Data | Index levels | Columns |
| --- | --- | --- |
| Emissions | `iso3c`, `unit`, `emission-category` | Years |
| GDP, population | `iso3c`, `unit` | Years |
| Gini | `iso3c`, `unit` | `gini` (one value, not time-varying) |

A new source should cover at least the major emitters, include a World total, use standard units (Mt CO₂e for emissions, `million` for population) and document its gaps.

## 4. Test

Run the preprocessing notebook, then an allocation that names the new source in `active_sources` of notebook 301. Check the country coverage and year ranges in `country_data_coverage_summary.csv`.

These notebooks are good models:

| Notebook | Type | Example of |
| --- | --- | --- |
| `101_data_preprocess_emiss_primap.py` | Emissions | NetCDF processing, category mapping, one notebook for every release |
| `101_data_preprocess_emiss_gcb-2025.py` | Emissions | Long CSV, single category, logic in one library function |
| `102_data_preprocess_gdp_wdi-2025.py` | GDP | CSV processing, country code mapping |
| `103_data_preprocess_population_un-owid-2025.py` | Population | Combining historical and projected data |
| `105_data_preprocess_gini_wdi-2025.py` | Gini | Latest value in a window, filtering aggregates |
| `105_data_preprocess_gini_unu-wider-2025.py` | Gini | Quality filtering, stationary output |
| `107_derive_nghgi_categories.py` | Land use | National-inventory corrections, metadata, world totals |

---

## Land-use sources

National-inventory land-use CO₂ replaces the bookkeeping estimates in PRIMAP. Total CO₂ (`co2`) and `all-ghg` need it ([Convention gap](../science/remaining-carbon-budgets.md#convention-gap)).

Notebook 107 serves every land-use source and receives `active_lulucf_source` as a papermill parameter. It writes:

- `emiss_co2-lulucf_nghgi_timeseries.csv`: country land-use CO₂ (the PRIMAP bookkeeping version from notebook 101 keeps its base filename);
- `world_co2-lulucf_timeseries.csv`: the world total for the budget corrections;
- `lulucf_metadata.yaml`: the year bounds and the files written.

To add a source, place it in `data/lulucf/{source-name}/` and add an entry under `lulucf:` with `data_parameters`: `format`, `iso3_column`, `year_column`, `value_column`, `category_filter`, `gas_filter` and `exclude_regions`.
The notebook reads the release label from the file name (`..._v3.1.csv`, `..._4.0.0.csv`), so the name must end in a version number.

Allocations in `co2` and `all-ghg` start no earlier than the first year of the land-use data. Both Melo releases start in 2000.

| Category | Uses land-use data | Why |
| --- | --- | --- |
| `co2-ffi` | No | Fossil fuels only |
| `co2` | Yes | Country `co2` = `co2-ffi` + national-inventory `co2-lulucf` on shared years. Bunkers enter only at world and budget level |
| `all-ghg` | Yes | Splits into `co2` and `non-co2` |
| `all-ghg-ex-co2-lulucf` | No | Its CO₂ part is `co2-ffi` |
| `co2-lulucf` | Indirectly | It is the land-use data |
| `non-co2` | No | Derived by subtraction |

Notebook 108 (rule `preprocess_bunkers`) writes `bunker_timeseries.csv`, the international bunker emissions.

## Scenario sources and budgets

Scenario pathways must already be internally consistent with the emissions convention. The pipeline corrects the budgets, not the pathways.
The Gidden et al. AR6 reanalysis is consistent with PRIMAP history. A custom scenario source in another convention needs its corrections in its preprocessing notebook before the data enter the pipeline.

Every scenario source maps its categories to the normalised `climate-assessment` and `quantile` fields; AR6 maps C1 to `1.5C` and `0.5`. A new source **must** write these columns. Notebook 104 is the reference.
A new scenario source is an entry in `src/fair_shares/conf/scenario_sources.yaml` that declares the world variables, metadata columns and bunker variables notebook 104 reads, and the budget terms it supplies.

An all-GHG budget run splits into a CO₂ budget and a non-CO₂ pathway. Notebook 104 builds the non-CO₂ pathway of each budget from its own scenario set (the temperature-matched set, or the AR6 category under `scenario_selection: ar6-category`), and non-CO₂ rows carry the budget's source key.
A new budget label needs at least `min_scenarios` scenarios in each of its sets, or notebook 104 raises a `ConfigurationError` that names it. `data/rcbs/rcbs.yaml` lists the labels left out of the defaults and why ([Decomposition](../science/greenhouse-gases.md#decomposition-rules); [Architecture](architecture-walkthrough.md#composite-category-decomposition)).

## Normative implications

Some data source choices carry normative weight. Contributors should document the rationale for their data source choices. For example, some decision points include:

- **GDP:** PPP vs. MER measurement can significantly affect allocation results. PPP tends to raise developing-country capacity shares [Pelz 2025b](https://doi.org/10.1088/1748-9326/ada45f).
- **Emissions:** Production vs. consumption accounting embeds different theories of responsibility. Production accounting (territorial) excludes embedded imports; consumption accounting includes them.
- **Population:** Projection method choices (UN median, SSP scenarios) affect per capita allocations, particularly for countries with high projected growth.
