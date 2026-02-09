# ETF Analysis & Trading Simulation Toolkit

Tools for ETF analysis, backtesting trading strategies, and sentiment analysis.

## Installation

```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
```

## Quick Start

```bash
# Interactive dashboard
uv run etf_comparison.py                           # → web server :8050

# Backtest dip-buy strategy
uv run dip_buy_backtest.py --small-grid --years 3  # → result/dip_sim_result.yaml

# Serve results
uv run serve_result.py                             # → web server :8000
```

---

## Python Files Reference

### Core Data Layer

| File | Purpose | Output |
|------|---------|--------|
| `etf_data_fetcher.py` | Core data fetcher with caching - Fetches ETF data from yfinance, parses `etf.yaml`, handles caching (24h), parallel fetching | `cache/*.pkl` |

### Buffett Indicator Analysis

| File | Purpose | Output |
|------|---------|--------|
| `fetch_buffet_ind.py` | Fetch Buffett Indicator from FRED - Downloads Stock Market Cap/GDP ratio for ~35 countries | `data/buffet-ind.csv` |
| `parse_buffet_ind.py` | Parse/clean Buffett CSV - Splits country columns | `data/buffet-ind.csv` |
| `buffet_etf_lead_analysis.py` | Lead indicator analysis - Correlates Buffett indicator with next-year ETF returns | `result/buffet_etf_lead_*.png/.csv` |
| `build_etf_price_by_country.py` | Map ETF prices to country codes | `data/etf_price_by_country.csv` |
| `export_etf_price_csv.py` | Export 20-year ETF prices - All tickers Close prices | `data/etf_price.csv` |

### Interactive Dashboard

| File | Purpose | Output |
|------|---------|--------|
| `etf_comparison.py` | Dash web dashboard - Interactive ETF comparison with period selection, group toggles, SMA overlay | *(web :8050)* |

### Sentiment Analysis

| File | Purpose | Output |
|------|---------|--------|
| `generate_sentiment_scores.py` | Score sentiment from YAML - Generates numerical scores (-1 to +1) | `etf_sentiment_score.yaml` |
| `tool_view_sentiment.py` | Visualize sentiment vs returns - HTML report with scatter, correlation | `result/sentiment_view.html` |
| `sentiment_v2/*.py` | Sentiment analysis v2 (analyze, add ChatGPT, process) | `sentiment_v2/*.yaml` |
| `sentiment_v3/*.py` | Sentiment analysis v3 (generate, test) | `sentiment_v3/generate/*.yaml` |

### Dip-Buy Strategy / Backtest

| File | Purpose | Output |
|------|---------|--------|
| `dip_buy_backtest.py` | Dip-buy strategy backtest engine - Grid search over params, exit rules | `result/dip_sim_result.yaml` |
| `decision/dip_buy.py` | Dip-buy signal generator - Pure signal logic (entry only) | *(returns signal)* |
| `simulation_planner.py` | Multi-period backtest planner - Runs across multiple periods | `result/planner_result.yaml` |

### Bot / Trading Simulation

| File | Purpose | Output |
|------|---------|--------|
| `bot/simulation.py` | Full trading simulation - Decision + bot, manages capital | `result/simulation_charts.html` |
| `bot/smc/__init__.py` | SMC bot - Money management, position sizing | *(runtime only)* |
| `bot2/decision_rsi.py` | RSI decision module - RSI-based buy/sell signals | *(returns score)* |
| `bot2/tool_view_decision.py` | View decision output | `result/decision_view.html` |

### Technical Indicator Simulation

| File | Purpose | Output |
|------|---------|--------|
| `indicator-simulator/run_simulation.py` | RSI/SMA grid search - Backtests SMA, RSI, combined strategies | `result/indicator_sim_result.yaml`<br>`result/indicator_sim_charts.html` |
| `indicator-simulator/indicator_backtest.py` | Indicator backtest engine - Signal generation | *(returns metrics)* |

### Visualization / Long-term Analysis

| File | Purpose | Output |
|------|---------|--------|
| `long-term-check.py` | 20-year group performance - Normalized performance by group | `result/long_term_by_section.html` |

### Utilities

| File | Purpose | Output |
|------|---------|--------|
| `serve_result.py` | HTTP server for results - Serves `./result` directory | *(web :8000)* |

---

## Command Reference

```bash
# Dashboard
uv run etf_comparison.py                           # → web :8050

# Data Export  
uv run export_etf_price_csv.py                     # → data/etf_price.csv

# Backtest
uv run dip_buy_backtest.py --small-grid --years 3  # → result/dip_sim_result.yaml
uv run dip_buy_backtest.py --grid-exit             # Grid search exit rules
uv run simulation_planner.py                       # Multi-period backtest
uv run indicator-simulator/run_simulation.py       # RSI/SMA grid search

# Bot simulation
uv run bot/simulation.py --limit 5                 # → result/simulation_charts.html

# Sentiment
uv run generate_sentiment_scores.py                # → etf_sentiment_score.yaml
uv run tool_view_sentiment.py                      # → result/sentiment_view.html

# Buffett Indicator
uv run fetch_buffet_ind.py                         # → data/buffet-ind.csv (needs FRED_API_KEY)
uv run buffet_etf_lead_analysis.py                 # → result/buffet_etf_lead_*.png

# Long-term
uv run long-term-check.py                          # → result/long_term_by_section.html

# Results server
uv run serve_result.py                             # → web :8000
```

---

## Project Structure

```
etf/
├── etf.yaml                    # ETF configuration (tickers, names, groups)
├── etf_data_fetcher.py         # Core data fetching and caching
├── etf_comparison.py           # Interactive Dash dashboard
├── dip_buy_backtest.py         # Dip-buy strategy backtest
├── dip_default.yaml            # Default dip-buy parameters
├── dip-sim.yaml                # Grid search parameters
├── planner.yaml                # Multi-period simulation config
│
├── bot/                        # Trading bot modules
│   ├── simulation.py           # Full simulation orchestrator
│   ├── simulation.yaml         # Bot simulation config
│   └── smc/                    # SMC (Smart Money Concept) bot
│
├── bot2/                       # Alternative bot with RSI
│   └── decision_rsi.py         # RSI-based decision module
│
├── decision/                   # Signal generators
│   ├── dip_buy.py              # Dip-buy signal logic
│   └── dip.yaml                # Dip-buy parameters
│
├── indicator-simulator/        # Technical indicator backtests
│   ├── run_simulation.py       # RSI/SMA grid search
│   ├── indicator_backtest.py   # Backtest engine
│   └── sim_config.yaml         # Indicator parameters
│
├── sentiment_data/             # Sentiment YAML files
├── sentiment_v2/               # Sentiment analysis v2
├── sentiment_v3/               # Sentiment analysis v3
│
├── data/                       # Data files (CSV, YAML)
├── cache/                      # Cached API data (auto-generated)
├── result/                     # Output files (HTML, YAML, PNG)
└── doc/                        # Documentation
```

## Data Sources

- **ETF Prices**: Yahoo Finance via `yfinance`
- **Buffett Indicator**: FRED API (requires `FRED_API_KEY`)
- **Sentiment**: Manual YAML files in `sentiment_data/`

## Notes

- Cache files refresh every 24 hours
- First run fetches data for all ETFs (slower)
- Results are saved to `result/` directory
