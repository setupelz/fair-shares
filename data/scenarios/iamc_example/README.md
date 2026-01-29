# IAMC Example Data

This directory contains example IAMC-format scenario data for documentation and testing.

## File: `iamc_reporting_example.xlsx`

IAMC (Integrated Assessment Modeling Consortium) format data from the AR6 scenario database.

### Column Structure

| Column     | Type   | Description                                      |
| ---------- | ------ | ------------------------------------------------ | ------------------- |
| `model`    | string | Model name (e.g., "SSP_SSP2_v6.3_ES")            |
| `scenario` | string | Scenario name (e.g., "ECPC-2015-800Gt")          |
| `region`   | string | Region code (e.g., "AFR", "CHN", "NAM", "World") |
| `variable` | string | Variable name (e.g., "Emissions                  | CO2", "Population") |
| `unit`     | string | Unit of measurement (e.g., "Gt CO2e", "million") |
| `1990`     | float  | Value for year 1990                              |
| `1995`     | float  | Value for year 1995                              |
| ...        | ...    | (5-year intervals)                               |
| `2100`     | float  | Value for year 2100                              |

### Example Values

- **Model**: `SSP_SSP2_v6.3_ES`
- **Scenario**: `ECPC-2015-800Gt`
- **Regions**: AFR, CHN, EEU, FSU, LAM, MEA, NAM, PAO, PAS, RCPA, SAS, WEU
- **Variables**: `Emissions|Allocation|Starting`, `Population`, `GDP|PPP`, `Emissions|CO2`

### Usage

```python
from fair_shares.library.utils.data import load_iamc_data

# Load data with model and scenario filters
data = load_iamc_data(
    "data/scenarios/iamc_example/iamc_reporting_example.xlsx",
    population_variable="Population",
    emissions_variable="Emissions|CO2",
    gdp_variable="GDP|PPP",
    regions=["AFR", "CHN", "NAM"],
    model_filter="SSP_SSP2_v6.3_ES",
    scenario_filter="ECPC-2015-800Gt",
    allocation_start_year=1990,
    budget_end_year=2100,
)
```

### Data Source

This file contains processed allocation results from the AR6 scenario database. For original data sources, see `docs/data-sources.md`.
