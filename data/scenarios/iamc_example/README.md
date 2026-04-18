# IAMC Example Data

This directory contains example IAMC-format scenario data for documentation and testing.

## File: `iamc_reporting_example.xlsx`

A MESSAGEix-GLOBIOM 800fm SSP2 scenario exported from IIASA's ixmp database.
Used as the default input for the 400-series notebooks.

### Column Structure

| Column     | Type   | Description                                              |
| ---------- | ------ | -------------------------------------------------------- |
| `model`    | string | `MESSAGEix-GLOBIOM 2.1-R12`                              |
| `scenario` | string | `800fm_ecpc_1990_tce_el_limited`                         |
| `region`   | string | `MESSAGEix-GLOBIOM 2.1-R12\|<Region>` or `World`         |
| `variable` | string | IAMC variable name (e.g. `Emissions\|CO2`, `Population`) |
| `unit`     | string | Native unit (e.g. `Mt CO2/yr`, `million`)                |
| `2015`     | float  | Value for year 2015                                      |
| `2020`     | float  | Value for year 2020                                      |
| ...        | ...    | (5-year steps to 2060, then 2070–2110)                   |

### Example Values

- **Model**: `MESSAGEix-GLOBIOM 2.1-R12`
- **Scenario**: `800fm_ecpc_1990_tce_el_limited`
- **Regions**: 12 R12 regions (China, Eastern Europe, Former Soviet Union,
  Latin America and the Caribbean, Middle East and North Africa, North America,
  Other Pacific Asia, Pacific OECD, Rest of Centrally Planned Asia, South Asia,
  Sub-Saharan Africa, Western Europe) plus `World`.
- **Variables**: `Population`, `GDP|PPP`, `Emissions|CO2`, `Emissions|CO2|AFOLU`,
  `Emissions|CO2|Energy and Industrial Processes`, `Emissions|CH4`, `Emissions|N2O`.

### Usage

```python
from fair_shares.library.utils.data import load_iamc_data

data = load_iamc_data(
    "data/scenarios/iamc_example/iamc_reporting_example.xlsx",
    population_variable="Population",
    emissions_variable="Emissions|CO2",
    gdp_variable="GDP|PPP",
    model_filter="MESSAGEix-GLOBIOM 2.1-R12",
    scenario_filter="800fm_ecpc_1990_tce_el_limited",
    allocation_start_year=1990,
    budget_end_year=2100,
)
```

See `notebooks/400_data_preprocess_scenario_for_allocation.py` for the canonical
load + back-fill + `Emissions|Covered` build pattern.
