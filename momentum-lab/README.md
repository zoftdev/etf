# QuantPedia ETF Momentum Strategy Lab

Simulation of the [QuantPedia Refining ETF Asset Momentum Strategy](https://quantpedia.com/refining-etf-asset-momentum-strategy/) with configurable parameters for optimization and variant runs.

---

## Strategy

| Rule | Description |
|------|--------------|
| **Long** | Top N ETFs by average momentum (3, 6, 9, 12 months), equal weight |
| **Short** | Bottom 1 ETF at 30% weight, **only when** 20d correlation > 250d correlation |
| **Rebalance** | Monthly (last trading day) |

**Benchmark:** Equal-weight buy-hold all ETFs (no rebalancing).

---

## Default 13 ETFs (QuantPedia research)

| Type | ETFs |
|------|------|
| Stock | SPY, IWM, EFA, EEM, IYR, QQQ |
| Bond | LQD, IEF, TIP |
| Commodity | GLD, USO, DBC |
| Currency | FXE |

---

## Usage

### Basic run

```bash
cd ~/clawd/workspace/etf
uv run python momentum-lab/run_simulation.py
```

### With options

```bash
uv run python momentum-lab/run_simulation.py [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--etfs` | QuantPedia 13 | Comma-separated ETF tickers (e.g. `SPY,GLD,QQQ`) |
| `--group-name` | `from-research` | Output subfolder under `result/momentum-lab/` |
| `--n-long` | 4 | Number of top ETFs to long |
| `--n-short` | 1 | Number of bottom ETFs to short |
| `--corr-threshold` | 1.0 | Activate short when 20d_corr/250d_corr > this |
| `--mom-periods` | 63,126,189,252 | Momentum lookback days (3,6,9,12 months) |
| `--spread` | 0.15 | Transaction cost % per rebalance |
| `--lookback-years` | 20 | Years of historical data |
| `--show-trades` | false | Output merged buy/sell summary per date |
| `--no-graph` | false | Skip chart generation |
| `--output-json` | - | Save JSON summary to file (`-` = stdout) |

### Examples

```bash
# Custom ETF list + output folder
uv run python momentum-lab/run_simulation.py \
  --etfs "SPY,GLD,QQQ,IWM,EEM" \
  --group-name my-5etf

# Optimize: top 2 longs, longer lookback
uv run python momentum-lab/run_simulation.py \
  --n-long 2 \
  --mom-periods "84,126,189,252" \
  --group-name opt-n2

# Simulate only (no chart)
uv run python momentum-lab/run_simulation.py --no-graph

# Output JSON summary
uv run python momentum-lab/run_simulation.py --output-json summary.json
uv run python momentum-lab/run_simulation.py --output-json -  # print to stdout
```

### Batch research

Run hundreds/thousands of config variants in parallel:

```bash
uv run python momentum-lab/run_batch.py batch.json [--name my-batch] [--workers 4]
```

**Batch file format** (JSON):
```json
{
  "configs": [
    {"group_name": "v1", "n_long": 2},
    {"group_name": "v2", "etfs": ["SPY","GLD","QQQ"], "n_long": 2}
  ]
}
```

Or plain array: `[{...}, {...}]` — each object overrides Config fields.

**Output:** `result/momentum-lab/_batch/{batch_name}/`
- `results.csv` — flattened table
- `results.json` — full summaries
- `report.md`, `report.html` — readable reports (sorted by Sharpe)
- `configs.json` — input configs

### Chart only

Re-runs simulation (default config) then generates chart:

```bash
uv run python momentum-lab/gen_graph.py
```

---

## Config (Python API)

For parameter sweeps and optimization, use `Config` and `run_simulation`:

```python
from simulate import Config, run_simulation

config = Config(
    etfs=["SPY", "GLD", "QQQ", "IWM"],
    group_name="my-variant",
    n_long=2,
    n_short=0,  # disable short
    corr_threshold=1.2,
    mom_periods_days=(84, 126, 189, 252),
    spread_pct=0.2,
    lookback_years=15,
)

result = run_simulation(config=config)
print(result.metrics["mom_0"]["cagr_pct"])

# JSON summary (includes momentum + benchmark)
summary = result.to_summary_dict()  # or result.to_summary_json()
```

---

## Outputs

All files saved under `result/momentum-lab/{group_name}/`:

| File | Description |
|------|-------------|
| `equity_curves.csv` | Daily equity (momentum 0%, momentum spread%, buy-hold) |
| `metrics.csv` | CAGR, Sharpe, Max DD for all 3 strategies |
| `buysell_log.csv` | Holdings snapshot per rebalance |
| `trade_log.csv` | Trade log (BUY/SELL, PnL on close) |
| `trades_summary.csv` | Merged by date (with `--show-trades`) |
| `momentum_vs_buyhold.html` | Equity curves + holdings heatmap + exit P&L |
| `summary.json` | JSON summary (with `--output-json summary.json`) |

### JSON summary structure

```json
{
  "config": {"group_name", "etfs", "n_long", "n_short", "spread_pct"},
  "momentum_spread0": {"cagr_pct", "sharpe", "max_drawdown_pct", ...},
  "momentum_spread": {"cagr_pct", "sharpe", "max_drawdown_pct", ...},
  "benchmark": {"cagr_pct", "sharpe", "max_drawdown_pct", ...},
  "data_range": {"start", "end", "days"}
}
```

---

## Structure

| File | Role |
|------|------|
| `simulate.py` | `Config`, strategy logic, `run_simulation()` |
| `gen_graph.py` | Plotly chart generation |
| `run_simulation.py` | CLI orchestrator |
| `run_batch.py` | Batch runner (ProcessPoolExecutor) |
| `batch_example.json` | Sample batch config |
