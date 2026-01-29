# Citation

## Taiwan GDP PPP Data

This isn't used in the fair-shares codebase, but kept as legacy motivation to add IMF GDP PPP/MER data which has different coverage to the World Bank dataset.

### Data Sources

**International Monetary Fund (IMF)**

- GDP data and purchasing power parity (PPP) conversion factors
- World Economic Outlook Database

**Taiwan Directorate-General of Budget, Accounting and Statistics (DGBAS)**

- Official GDP statistics for Taiwan
- National accounts data

### Background

Taiwan's statistics are not included in the World Bank's primary databases. The World Bank database explicitly notes: "Unless otherwise noted, data for China do not include data for Hong Kong SAR, China; Macao SAR, China; or Taiwan, China."

However, Taiwan does participate in the World Bank–led International Comparison Program (ICP), which collects purchasing power parity data. The 2021 ICP bubble chart displays the GDP Price Level Index for countries worldwide, including Taiwan, confirming the availability of PPP data through this channel.

### Data Processing

The compiled dataset includes:

- **Nominal GDP in USD**: IMF data (Column B) and Taiwan government data (Column H)
- **Deflated GDP (PPP-adjusted)**: IMF data (Column C) and Taiwan government GDP divided by IMF parity (Column J)
- **Price Level Index**: Columns I and K, used to confirm consistency with World Bank ICP data

All source references are documented in the spreadsheet footer rows.

Files:

- `Taiwan_GDP_PPP.xlsx` - Taiwan GDP and PPP data compiled from IMF and DGBAS sources
