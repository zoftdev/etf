# Momentum Test — Instructions

Fine-grain momentum grid: per-ticker backtest of momentum variants vs buy-hold.

## Reference

- **QuantPedia: Refining ETF Asset Momentum Strategy**  
  https://quantpedia.com/refining-etf-asset-momentum-strategy/  
  — Correlation filter + selective shorting for asset allocation (13 ETFs)

- **Related:** `momentum-lab/` implements the QuantPedia strategy (asset-level). This folder tests single-ticker momentum variants.

## Instructions

### Run

```bash
cd ~/clawd/workspace/etf
uv run python momentum-test/run_fine_grid.py
```

### Outputs

- `momentum-test/out/momentum_fine_results.csv` — per (ticker, variant) metrics
- `momentum-test/out/equity_curves.csv` — equity for top5 variants + buy_hold
- `momentum-test/out/top5_variants.json` — top 5 variant keys by avg CAGR
- `momentum-test/out/momentum_vs_buyhold.html` — interactive Plotly chart

### Variants

Fine-grain around winners: lookback 55–75, skip 3–7, threshold 0–1.0.
