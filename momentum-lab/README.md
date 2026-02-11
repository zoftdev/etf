# QuantPedia ETF Asset Momentum Strategy Lab

Simulation of the [QuantPedia Refining ETF Asset Momentum Strategy](https://quantpedia.com/refining-etf-asset-momentum-strategy/).

## Strategy

- **Long:** Top 4 ETFs by average momentum (3, 6, 9, 12 months)
- **Short:** Bottom 1 ETF at 30% weight, **only when** 20-day correlation > 250-day correlation
- **Rebalance:** Monthly (last trading day)

## 13 ETFs (same as research)

| Type     | ETFs                |
|----------|----------------------|
| Stock    | SPY, IWM, EFA, EEM, IYR, QQQ |
| Bond     | LQD, IEF, TIP        |
| Commodity| GLD, USO, DBC        |
| Currency | FXE                  |

## Benchmark

Equal-weight buy-hold all 13 ETFs (no rebalancing).

## Usage

```bash
cd ~/clawd/workspace/etf
uv run python momentum-lab/run_simulation.py [--spread 0.15] [--show-trades] [--no-graph]
```

- `--spread`: Transaction cost % per rebalance (default 0.15). Set to 0 for no cost.
- `--show-trades`: Output merged buy/sell summary per date with win/loss % on exits.
- `--no-graph`: Skip chart generation (simulate only).

**Chart only** (re-runs simulation then builds chart):
```bash
uv run python momentum-lab/gen_graph.py
```

## Structure

- `simulate.py` — Strategy logic (fetch, momentum, rebalance)
- `gen_graph.py` — Plotly chart generation
- `run_simulation.py` — Main orchestrator

## Outputs

Saved under `result/momentum-lab/{ETF_GROUP_NAME}/`. Adjust `ETF_GROUP_NAME` in `simulate.py`.

- `result/momentum-lab/from-research/equity_curves.csv`
- `result/momentum-lab/from-research/metrics.csv`
- `result/momentum-lab/from-research/buysell_log.csv`
- `result/momentum-lab/from-research/trade_log.csv`
- `result/momentum-lab/from-research/trades_summary.csv` (with `--show-trades`)
- `result/momentum-lab/from-research/momentum_vs_buyhold.html`
