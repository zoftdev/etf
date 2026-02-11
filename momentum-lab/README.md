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
uv run python momentum-lab/run_simulation.py [--spread 0.15]
```

- `--spread`: Transaction cost % per rebalance (default 0.15). Set to 0 for no cost.

## Outputs

- `result/equity_curves.csv` — Daily equity (momentum_spread0, momentum_spread015, buy_hold)
- `result/metrics.csv` — CAGR, Sharpe, Max DD for all 3
- `result/buysell_log.csv` — Rebalance log (date, ticker, side, weight_pct)
- `result/momentum_vs_buyhold.html` — Interactive Plotly chart (3 curves)
