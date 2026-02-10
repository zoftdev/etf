# Prompt: Macro forecast vs ETF benchmark simulation

## Purpose

Run the benchmark that compares **buy-hold (all ETFs, equal weight)** vs **following the macro report’s recommendations** (rebalance once per year to that year’s recommended list). Output is terminal summary plus an interactive chart.

## Prerequisites

1. **Mapping must be complete**  
   From repo root:
   ```bash
   uv run python makro-etf-colreated/1_create_mapping.py
   ```
   If it exits with unmappable symbols, fix `makro-etf-colreated/etf-mapping.json` (and optionally add missing tickers to `data/etf_price.csv`) using `prompt-fill-etf.md` or `makro-etf-colreated/prompt-add-etf-mapping.md`, then re-run until it reports “All forecast symbols mappable.”

2. **Data**  
   - `macro-forecast-cursor-auto/forecast.json` — per-year macro recommendations (countries, commodity, us_sector).
   - `makro-etf-colreated/etf-mapping.json` — maps forecast names to ETF tickers.
   - `data/etf_price.csv` — daily close prices; columns = valid tickers.

## Run the simulation

From repo root:

```bash
uv run python makro-etf-colreated/2_benchmark.py [options]
```

### Options

| Option | Default | Meaning |
|--------|--------|--------|
| `--start` | 2010 | First year we use a report; first rebalance = last trading day of October this year. |
| `--stop-order` | 2020 | Last year we take a new recommendation; last rebalance = end-Oct this year, then hold. |
| `--benchmark-end` | 2025 | Portfolio value is measured at the last trading day of this year. |
| `--capital` | 1_000_000 | Initial capital in USD. |

### Example

```bash
# Default: start 2010, stop rebalancing 2020, benchmark at end of 2025, $1M
uv run python makro-etf-colreated/2_benchmark.py

# Custom window
uv run python makro-etf-colreated/2_benchmark.py --start 2012 --stop-order 2018 --benchmark-end 2024
```

## Output

- **Terminal:** Config, start/end dates, final portfolio value and total return (%) for Buy-hold and for Recommend, and the difference (Recommend − Buy-hold). Path to the chart file is printed.
- **Chart:** `makro-etf-colreated/benchmark_chart.html` — interactive Plotly line chart of portfolio value over time (rebalance dates + benchmark end). Open in a browser.

## Logic (short)

- **Buy-hold:** At the last trading day of October `start`, split capital equally across all ETFs in `data/etf_price.csv` that have a valid price; no rebalancing until the last trading day of `benchmark-end`.
- **Recommend:** Same start date. At the last trading day of October for each year from `start` through `stop-order`, rebalance to equal weight in the tickers implied by that year’s forecast (via `etf-mapping.json`). After the October `stop-order` rebalance, hold until the last trading day of `benchmark-end`.

## Reference

| Item | Path |
|------|------|
| Mapping check | `makro-etf-colreated/1_create_mapping.py` |
| Benchmark + chart | `makro-etf-colreated/2_benchmark.py` |
| Chart output | `makro-etf-colreated/benchmark_chart.html` |
| Fill missing mappings | `prompt-fill-etf.md`, `makro-etf-colreated/prompt-add-etf-mapping.md` |
