# Citation

## World Bank GDP Data

World Bank. (2024). GDP (constant 2015 US$) and GDP, PPP (constant 2017 international $). World Bank Open Data. https://data.worldbank.org/

Files:
- `API_NY.GDP.MKTP.KD_DS2_en_csv_v2_213435.csv` — GDP (constant 2015 US$), WDI indicator `NY.GDP.MKTP.KD`
- `API_NY.GDP.MKTP.PP.KD_DS2_en_csv_v2_1004.csv` — GDP, PPP (constant 2017 international $), WDI indicator `NY.GDP.MKTP.PP.KD`

**Why constant-dollar (`.KD`) and not current-dollar (`.CD`):** Constant-dollar series fix prices to a reference year (2015 for MER, 2017 for PPP), so values across years are directly comparable in real terms. Current-dollar series use each year's own prices, which makes long-horizon comparisons silently distorted by price changes. For historical cross-year capability calculations (e.g., allocating a remaining carbon budget from 1990), using current-dollar series understates early-period real GDP by the cumulative inflation between the observation year and the base year — for 1990 values in a 2017-base comparison, this is roughly a factor of two for developed economies.
