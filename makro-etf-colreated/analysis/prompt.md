# Prompt: Macro Forecast ETF Strategy Analysis

## Original Task

> Analyze possible ways to beat the buy-and-hold strategy using macro forecast recommendations from:
> - `macro-forecast-cursor-auto/forecast.json` -- per-year macro recommendations (countries, commodity, us_sector) with conviction scores
> - `makro-etf-colreated/etf-mapping.json` -- maps forecast names to ETF tickers
> - `data/etf_price.csv` -- daily close prices; columns = valid tickers

## Approach Taken

### Step 1: Understand the data
- Read forecast.json: 13 years (2010-2022) of ranked recommendations across 3 categories, each with scores 0-1
- Read etf-mapping.json: maps 17 unique ETF tickers from recommendation names
- Read etf_price.csv: 60 ETFs, daily prices from Dec 2005 to Feb 2026

### Step 2: Identify the baseline problem
- Initial benchmark used ALL 60 ETFs for buy-hold vs only 17 mapped ETFs for recommendations
- This is an unfair comparison (different universes)
- Fixed: buy-hold baseline now uses the same 17 recommendation-mapped ETFs

### Step 3: Design strategy matrix
Tested 16 strategies across 5 dimensions:
- **Weighting**: equal, score-proportional, score-squared
- **Concentration**: all picks, top-3, top-5, threshold filters
- **Category**: all, countries-only, commodity-only, us-sector-only, combinations
- **Timing**: October, January, December rebalance
- **Combination**: sector+commodity (excluding countries)

### Step 4: Run across multiple time windows
- `--end 2022`: Pure recommendation period
- `--end 2023`: 1-year post-recommendation hold
- `--end 2025`: 3-year post-recommendation hold

### Step 5: Key corrections during analysis
1. Fair baseline: B&H of 17 mapped ETFs, not all 60
2. Daily series: for accurate max drawdown (not just at rebalance points)
3. Category isolation: tested each category independently to find the signal source

## How to Reproduce

```bash
# Pure recommendation period (2010-2022)
uv run python3 3_strategy_analysis.py --end 2022

# With 1-year post-recommendation hold
uv run python3 3_strategy_analysis.py --end 2023

# Extended hold
uv run python3 3_strategy_analysis.py --end 2025

# Custom period
uv run python3 3_strategy_analysis.py --start 2012 --stop-order 2020 --end 2023
```
