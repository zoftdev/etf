# QuantPedia ETF Momentum Strategy Lab

Lab for backtesting the [QuantPedia ETF Asset Momentum Strategy](https://quantpedia.com/refining-etf-asset-momentum-strategy/) and exploring parameter combinations. Long top ETFs by momentum, short bottom ETF when correlation condition allows; rebalance monthly.

---

## Workflow

```
1. Single run        →  uv run python momentum-lab/run_simulation.py
2. Batch sweep       →  uv run python momentum-lab/run_batch.py batch.json [--name X] [--workers N]
3. Review results    →  result/momentum-lab/_batch/{name}/report.html, graph2_parcoords.html
```

**Batch workflow:** Define config overrides in JSON → run batch → inspect report (sorted by Sharpe) and parallel-coordinates chart.

---

## Quick Start

```bash
# Single run (default from param/default or MOMENTUM_LAB_PARAM env)
uv run python momentum-lab/run_simulation.py

# Override: use another param file
uv run python momentum-lab/run_simulation.py --param optimal-13etf.json

# Batch: sweep n_long, short_weight, etc.
uv run python momentum-lab/run_batch.py momentum-lab/batch_example.json
uv run python momentum-lab/run_batch.py batch.json --param custom.json
```

---

## Strategy (overview)

- **Long:** Top N ETFs by multi-month momentum, equal weight
- **Short:** Bottom 1 ETF, conditional on correlation filter
- **Rebalance:** Monthly last trading day  
- **Benchmark:** Equal-weight buy-hold all ETFs

See `simulate.py` and `research-plan.md` for parameter details.

---

## Batch Research

Define variants in JSON (`batch.json` or `batch_example.json`):

```json
{"configs": [
  {"group_name": "v1", "n_long": 2},
  {"group_name": "v2", "short_weight": 0.2, "n_long": 4}
]}
```

**Output:** `result/momentum-lab/_batch/{name}/`
- `report.html`, `report.md` — top configs by Sharpe
- `results.csv`, `results.json` — full data
- `graph2_parcoords.html` — parallel coordinates (auto-generated)
- `configs.json` — input used

Regenerate scatter/parcoords from existing batch dir:
```bash
uv run python momentum-lab/gen_batch_graphs.py result/momentum-lab/_batch/{name}
```

---

## Outputs (single run)

`result/momentum-lab/{group_name}/`:
- **Metrics:** `metrics.csv`, `equity_curves.csv`
- **Logs:** `trade_log.csv`, `buysell_log.csv`
- **Chart:** `momentum_vs_buyhold.html` (equity + holdings heatmap)

---

## Files

| File | Purpose |
|------|---------|
| `run_simulation.py` | CLI single run |
| `run_batch.py` | CLI batch runner |
| `gen_graph.py` | Equity chart (single run) |
| `gen_batch_graphs.py` | Scatter + parcoords from batch output |
| `simulate.py` | Strategy logic, Config, `run_simulation()` |
| `param/quantpedia.json` | Default params. Use `--param X` to pick another file. |
| `param/default` | Single setting: filename of default profile (e.g. `optimal-13etf.json`). Env `MOMENTUM_LAB_PARAM` overrides. |
| `batch_example.json` | Sample batch config |
| `research-plan.md` | Parameter sweep ideas |

Options: `uv run python momentum-lab/run_simulation.py --help`
