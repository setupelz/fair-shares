# User Data Directory

Place your IAMC-format data files here. Both CSV and Excel formats are supported.

## Required Format

Standard IAMC format with columns:

- `model`: Model name (e.g., "MESSAGEix")
- `scenario`: Scenario name (e.g., "SSP2-Baseline")
- `region`: Region identifier (e.g., "USA", "R12_CHN")
- `variable`: Variable name (e.g., "Population", "Emissions|CO2")
- `unit`: Unit string (e.g., "million", "Mt CO2/yr")
- Year columns: 1990, 2000, 2010, ..., 2100 (wide format)

Alternatively, use long format with `year` and `value` columns instead.

## Example (Wide Format)

```csv
model,scenario,region,variable,unit,1990,2000,2010,2020,2030,...
MyModel,SSP2,USA,Population,million,250,280,310,330,350,...
MyModel,SSP2,USA,Emissions|CO2,Mt CO2/yr,5000,5500,5200,4800,4000,...
MyModel,SSP2,USA,GDP|PPP,billion USD_2010/yr,8000,10500,14000,17000,20000,...
MyModel,SSP2,CHN,Population,million,1150,1270,1340,1400,1380,...
...
```

## Exploring Your Data

Use pyam to explore your data before running the notebook:

```python
import pyam

df = pyam.IamDataFrame("your_file.csv")
print(df)              # Overview
print(df.variable)     # List variables
print(df.region)       # List regions
print(df.model)        # List models
print(df.scenario)     # List scenarios
```

## Notes

- Emissions should be in CO2-equivalent (GWP conversions already applied)
- Population should be in millions
- GDP should be in billions USD (constant prices)
- The adapter auto-excludes "World" and "Global" regions by default
- Use `model_filter` and `scenario_filter` if your file contains multiple
  models/scenarios (wildcards supported, e.g., "MESSAGEix\*")
