# Parameter Optimization Plan — Default 13 ETFs

## Tunable Parameters

| Parameter | Default | Range to sweep | Impact |
|---|---|---|---|
| `n_long` | 4 | 1, 2, 3, 4, 5, 6 | Concentration vs diversification |
| `n_short` | 1 | 0, 1 | Hedge on/off |
| `short_weight` | 0.30 | 0.05, 0.10, 0.20, 0.30, 0.40, 0.50 | Size of short hedge |
| `corr_threshold` | 1.0 | 0.6, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5 | When to activate short |
| `mom_periods_days` | (63,126,189,252) | 10 variants below | Signal timeframe |
| `corr_short_days` | 20 | 10, 15, 20, 30 | Short-term corr window |
| `corr_long_days` | 250 | 200, 250, 300 | Long-term corr window |

---

## Batch Structure: 6 Groups (~94 configs)

### Group A: `n_long` sweep (6 configs)
Fix everything else at defaults. Sweep n_long: 1, 2, 3, 4, 5, 6
- **Question:** Is 4 really optimal? Fewer = more concentrated bets, more = diversified.

### Group B: Short weight sweep (7 configs)
n_long=4, sweep short_weight: 0 (via n_short=0), 0.05, 0.10, 0.20, 0.30, 0.40, 0.50
- QuantPedia tested 5-50%, found 30% best. Verify with our data.

### Group C: Correlation threshold sweep (7 configs)
n_long=4, sweep corr_threshold: 0.6, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5
- Lower = short more often (more hedging), higher = short only in extreme regimes.

### Group D: Momentum period variants (10 configs)
n_long=4, sweep mom_periods_days:
- Single: (63,), (126,), (189,), (252,)
- Dual: (63, 252), (63, 126)
- Triple: (63, 126, 252)
- Default quad: (63, 126, 189, 252)
- Shorter quad: (21, 63, 126, 189)
- Extended: (21, 63, 126, 189, 252)

### Group E: Correlation window sweep (8 configs)
Sweep (corr_short_days, corr_long_days):
- (10, 200), (10, 250), (15, 250), (20, 200)
- (20, 250), (20, 300), (30, 250), (30, 300)

### Group F: Cross-factorial of key params (~57 configs)
**F1: n_long × short_weight × mom_periods** (48 configs)
- n_long: 2, 3, 4, 5
- short_weight: 0 (n_short=0), 0.20, 0.30, 0.40
- mom_periods: (63,126,252), (63,126,189,252), (21,63,126,189,252)

**F2: n_long × corr_threshold** (9 configs)
- n_long: 3, 4, 5
- corr_threshold: 0.8, 1.0, 1.2
- Fixed: n_short=1, short_weight=0.30, default mom_periods

---

## Run

```bash
cd ~/clawd/workspace/etf
uv run python momentum-lab/run_batch.py momentum-lab/batch_optimize.json \
  --name optimize-13etf --workers 4
# → result/momentum-lab/_batch/optimize-13etf/report.html
```

## What to look for

1. **Sort by Sharpe ratio** — best risk-adjusted return
2. **Compare mom0_cagr vs bh_cagr** — does momentum beat buy-hold?
3. **Check max drawdown** — acceptable risk?
4. **Look for robustness** — do nearby parameter values give similar results? (not a lucky spike)
