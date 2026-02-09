# Buffett Indicator Analysis

This directory contains tools for fetching, processing, and analyzing the **Buffett Indicator** (Stock Market Capitalization to GDP ratio) and its relationship with ETF returns.

## Overview

The Buffett Indicator measures stock market valuation relative to economic output. This module:
- Fetches annual Buffett Indicator data from FRED (Federal Reserve Economic Data)
- Analyzes whether the indicator leads ETF returns (predictive power)
- Visualizes long-term ETF performance by geographic/economic groups

## Files

| File | Purpose | Output |
|------|---------|--------|
| `1_fetch_buffet_ind.py` | Fetch Buffett Indicator data from FRED API and write normalized CSV | `data/buffet-ind.csv` |
| `2_buffet_etf_lead_analysis.py` | Analyze correlation: Buffett indicator vs next-year ETF returns | `result/buffet_etf_lead_corr.csv`, `result/buffet_etf_lead_*.png` |
| `3_tool_view_performance.py` | Visualize 20-year ETF performance by group (lv2) | `result/long_term_by_section.html` |

## Quick Start

### 1. Fetch Buffett Indicator Data

**Prerequisites:**
- FRED API key (free at https://fredaccount.stlouisfed.org/apikeys)
- Set environment variable or create `.env` file in project root:
  ```bash
  FRED_API_KEY=your_key_here
  ```

**Run:**
```bash
uv run python buffet_ind/1_fetch_buffet_ind.py
```

**Output:** `data/buffet-ind.csv` with columns:
- `country_code` - 3-letter code (USA, CNA, JPA, ...)
- `country_name` - Empty by default (can be filled manually if needed)
- `country_code.source` - e.g., `USA.DDDM01USA156NWDB`
- Year columns: `2004`, `2005`, ..., `2020` (numeric values)

**Note:** Default range is 2004-2020. Edit `YEAR_COLUMNS` in the script to change.

### 2. Analyze Lead Indicator Relationship

Test whether Buffett indicator predicts next-year ETF returns:

```bash
uv run python buffet_ind/2_buffet_etf_lead_analysis.py
```

**Requirements:**
- `data/buffet-ind.csv` (from step 1)
- `data/etf_price_by_country.csv` (from `tools/build_etf_price_by_country.py`)

**Outputs:**
- **CSV:** `result/buffet_etf_lead_corr.csv` - Per-country correlations
- **Charts:**
  - `result/buffet_etf_lead_pooled_scatter.png` - Scatter plot (all countries pooled)
  - `result/buffet_etf_lead_corr_bars.png` - Bar chart of per-country correlations
  - `result/buffet_etf_lead_country_examples.png` - Time series examples (3 countries)

**Analysis includes:**
- Pooled correlation (all countries, all years)
- OLS regression: `etf_return_next = a + b * buffet`
- Per-country correlations with significance tests (p < 0.05)

### 3. Long-Term Performance Visualization

View 20-year ETF performance grouped by level-2 categories (e.g., `asia_pacific`, `europe`, `specific`):

```bash
uv run python buffet_ind/3_tool_view_performance.py
```

**Output:** `result/long_term_by_section.html` - Interactive Plotly chart

**Note:** Requires `config/etf.yaml` with `group_key` metadata (e.g., `world.asia_pacific`).

## Data Flow

```
FRED API (1_fetch_buffet_ind.py)
    ↓
data/buffet-ind.csv (normalized format: country_code, country_name, country_code.source, years...)
    ↓
2_buffet_etf_lead_analysis.py
    ↓
result/buffet_etf_lead_corr.csv
result/buffet_etf_lead_*.png
```

## Adding More Countries or Years

**Countries:** Edit `SERIES` in `1_fetch_buffet_ind.py`. FRED series ID format: `DDDM01{CODE}156NWDB`
- Example: USA → `DDDM01USA156NWDB`
- Check available series at https://fred.stlouisfed.org (search "Stock Market Capitalization to GDP")

**Years:** Change `YEAR_COLUMNS` in `1_fetch_buffet_ind.py` and update `observation_start`/`observation_end` in `fetch_series()`.

## References

- **FRED:** https://fred.stlouisfed.org
- **API Key Signup:** https://fredaccount.stlouisfed.org/apikeys
- **Example Series (USA):** https://fred.stlouisfed.org/series/DDDM01USA156NWDB
- **Documentation:** See `doc/buffet-indicator.md` for detailed data source information

## Dependencies

- `pandas` - Data manipulation
- `numpy` - Numerical operations
- `scipy` - Statistical tests (correlation, regression)
- `matplotlib` - Static charts
- `plotly` - Interactive charts (3_tool_view_performance.py)
- `core.etf_data_fetcher` - ETF data fetching (3_tool_view_performance.py)
