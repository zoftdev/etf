# Indicator Simulator Plan

## Goal
Simulate RSI & SMA trading strategies on all ETFs from `etf.yaml` using 20 years of historical data.
Grid-search over RSI and SMA parameters to find the best combinations.
Show results **per ticker**, **per group** (etf.yaml groups), and **overall**.

---

## Data Source
- Reuse `ETFDataFetcher` from `../etf_data_fetcher.py` (yfinance + cache)
- Fetch 20 years of daily OHLCV data (~7360 calendar days + cushion)
- All tickers extracted from `../etf.yaml` (commodity, momentum, world, us_sectors)

---

## Strategy Definitions

### 1. SMA Crossover Strategy
- **Signal**: Buy when price crosses above SMA(N), sell when price crosses below SMA(N)
- **Parameter grid** (SMA period):
  - `sma_period`: [20, 50, 100, 150, 200]

### 2. RSI Mean-Reversion Strategy
- **Signal**: Buy when RSI(N) drops below `rsi_buy_threshold`, sell when RSI(N) rises above `rsi_sell_threshold`
- **Parameter grid**:
  - `rsi_period`: [7, 14, 21, 30]
  - `rsi_buy_threshold`: [25, 30, 35]
  - `rsi_sell_threshold`: [65, 70, 75]

### 3. Combined RSI + SMA Strategy
- **Signal**: Buy when RSI < buy_threshold AND price > SMA(N) (trend confirmation), sell when RSI > sell_threshold OR price < SMA(N)
- **Parameter grid**: subset of above (top-performing RSI params x top SMA params)

---

## Files to Create

```
indicator-simulator/
├── plan.md                  # This file
├── sim_config.yaml          # Parameter grids (editable)
├── indicator_backtest.py    # Core: RSI/SMA calculation, signal generation, backtesting engine
├── run_simulation.py        # CLI entry point: fetch data, run grid search, output results
└── results/                 # Output folder (gitignored)
    └── (generated YAML + HTML)
```

### File Details

#### 1. `sim_config.yaml`
```yaml
strategies:
  sma_crossover:
    sma_period: [20, 50, 100, 150, 200]
  rsi_mean_reversion:
    rsi_period: [7, 14, 21, 30]
    rsi_buy_threshold: [25, 30, 35]
    rsi_sell_threshold: [65, 70, 75]
  combined_rsi_sma:
    rsi_period: [14, 21]
    rsi_buy_threshold: [30, 35]
    rsi_sell_threshold: [70, 75]
    sma_period: [50, 100, 200]

# Backtest settings
backtest:
  initial_capital: 10000
  years: 20
```

#### 2. `indicator_backtest.py` — Core Engine
- `compute_sma(close: pd.Series, period: int) -> pd.Series`
- `compute_rsi(close: pd.Series, period: int) -> pd.Series`
- `generate_sma_signals(df, sma_period) -> pd.Series` (1=buy, -1=sell, 0=hold)
- `generate_rsi_signals(df, rsi_period, buy_thresh, sell_thresh) -> pd.Series`
- `generate_combined_signals(df, rsi_period, buy_thresh, sell_thresh, sma_period) -> pd.Series`
- `run_backtest(df, signals) -> dict` — walk-forward, no look-ahead
  - Returns: `{total_return_pct, n_trades, win_rate, max_drawdown_pct, sharpe_ratio, trades_list}`
- `backtest_metrics(trades) -> dict` — same metric format as existing `dip_buy_backtest.py`

#### 3. `run_simulation.py` — CLI Runner
- Uses `ETFDataFetcher` to load tickers and fetch 20yr history
- Loads `sim_config.yaml` for parameter grids
- Runs grid search in parallel (`ProcessPoolExecutor`)
- Outputs:
  - **Per-ticker results**: best params for each ticker
  - **Per-group results**: best params for each etf.yaml group (commodity, momentum, world.asia_pacific, etc.)
  - **Overall best**: single best param set across all tickers
  - **Group-level heatmap data**: mean return per param set per group

CLI:
```bash
python run_simulation.py                          # full run
python run_simulation.py --strategy sma           # only SMA
python run_simulation.py --strategy rsi           # only RSI
python run_simulation.py --strategy combined      # only combined
python run_simulation.py --limit 5                # first 5 tickers (for testing)
python run_simulation.py --workers 8              # parallel workers
```

---

## Output Format

### Console Output
```
--- SMA Crossover: Best per group ---
group              | best_sma | mean_return% | win_rate | max_dd% | n_tickers
Commodity          | 200      | 12.3         | 58.2     | -15.4   | 9
Momentum           | 100      | 28.7         | 62.1     | -22.1   | 5
World - Asia Pacific| 50      | 18.5         | 55.3     | -18.2   | 10
...

--- RSI Mean-Reversion: Best per group ---
group              | rsi_p | buy_th | sell_th | mean_return% | win_rate | n_tickers
...

--- Combined: Best per group ---
...

--- Per-ticker detail (top 20) ---
ticker | strategy  | params          | return% | trades | win_rate | max_dd%
GLD    | rsi       | 14/30/70        | 45.2    | 89     | 61.2     | -8.3
XLK    | combined  | 14/30/70/sma200 | 112.5   | 42     | 71.4     | -25.1
...
```

### YAML Output (`results/indicator_sim_result.yaml`)
```yaml
run:
  timestamp: ...
  years: 20
  n_tickers: 75
strategies:
  sma_crossover:
    best_overall: {sma_period: 200, mean_return_pct: ...}
    by_group: [...]
    by_ticker: [...]
  rsi_mean_reversion:
    best_overall: {rsi_period: 14, buy: 30, sell: 70, mean_return_pct: ...}
    by_group: [...]
    by_ticker: [...]
  combined_rsi_sma:
    best_overall: {...}
    by_group: [...]
    by_ticker: [...]
```

### HTML Chart (`results/indicator_sim_charts.html`)
- Plotly charts showing:
  1. Heatmap: SMA period vs group (color = mean return)
  2. Heatmap: RSI buy_threshold vs sell_threshold per group
  3. Bar chart: best strategy comparison per group
  4. Equity curves for top 5 tickers per strategy

---

## Implementation Steps

### Step 1: Create `sim_config.yaml`
- Define parameter grids for all 3 strategies
- Backtest settings (years, capital)

### Step 2: Create `indicator_backtest.py`
- Implement RSI and SMA computation (pure pandas, no TA-lib dependency)
- Signal generators for each strategy
- Walk-forward backtester (same no-look-ahead pattern as `dip_buy_backtest.py`)
- Metrics calculation (return, trades, win rate, drawdown, Sharpe)

### Step 3: Create `run_simulation.py`
- Data fetching via `ETFDataFetcher` (20yr, all tickers)
- Grid search with `ProcessPoolExecutor` for parallelism
- Result aggregation: per-ticker, per-group (using `group_key` from fetcher), overall
- Console summary tables
- YAML output for downstream use
- Plotly HTML charts (heatmaps, bar charts, equity curves)

### Step 4: Test with small subset
- `python run_simulation.py --limit 3 --strategy sma` to verify correctness
- Validate no look-ahead bias

---

## Key Design Decisions
1. **Reuse `ETFDataFetcher`**: no duplicate data-fetching logic; leverages existing cache
2. **Same metric format** as `dip_buy_backtest.py` for consistency
3. **YAML-driven config**: all parameter grids in `sim_config.yaml`, easy to tweak
4. **Parallel execution**: `ProcessPoolExecutor` per ticker x param combination
5. **Group hierarchy from etf.yaml**: uses `group_key` (e.g., `world.asia_pacific`, `commodity.specific`) for grouping
6. **No TA-lib dependency**: RSI and SMA computed with pandas (EWM for RSI, rolling for SMA)
