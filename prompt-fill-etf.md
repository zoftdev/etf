# Prompt: Fill missing ETF mappings

When `makro-etf-colreated/compare_forecast_vs_etf.py` reports unmappable symbols, it writes `makro-etf-colreated/forecast-missing.json` (same format as `etf-mapping.json`) and exits. Use this flow to add the missing ETFs.

## 1. See what’s missing

- Open `makro-etf-colreated/forecast-missing.json`, or run the compare script and read stderr.
- Each entry is a forecast name with an empty list `[]`; you must choose one or more **tickers** that exist in `data/etf_price.csv`.

## 2. Check Yahoo before adding

A ticker is only valid if we can get history from Yahoo Finance **and** it’s present in `data/etf_price.csv`.

- **Check if a ticker has data on Yahoo:**
  ```bash
  uv run python tools/check_yahoo_ticker.py TICKER
  ```
- If the ticker is **not** in `data/etf_price.csv`, add it first (step 4), then update the mapping (step 3).

## 3. Add mapping in etf-mapping.json

- Open `makro-etf-colreated/etf-mapping.json`.
- For each missing name, add the **exact** forecast name as key and a list of tickers as value.
- Names are case-sensitive and must match `macro-forecast-cursor-auto/forecast.json` (e.g. `"Consumer Discretionary"` vs `"Consumer discretionary"`).
- Example: `"Russia": ["ERUS"]`, `"Industrials": ["XLI"]`.
- Remove or fill that name from `forecast-missing.json` (or re-run the compare script; it will overwrite the missing file only if something is still unmappable).

## 4. If the ticker is not in etf_price.csv

Valid tickers for the compare script are the **columns** of `data/etf_price.csv`. If you chose a ticker that isn’t there yet:

1. **Add to config (so the project knows the ETF):**
   - `config/etf.yaml` — add under the right group (e.g. `world.europe.etfs` for a country).
   - `data/etf-v3.yaml` — add under the matching segment (e.g. `world_europe.items`).

2. **Append the ticker’s history to the CSV (incremental):**
   ```bash
   uv run python tools/append_etf_price_column.py TICKER
   ```
   This fetches from Yahoo and adds one column to `data/etf_price.csv` aligned by date.

3. Re-run the compare script; the new ticker will be accepted.

## 5. Re-run the compare

```bash
uv run python makro-etf-colreated/compare_forecast_vs_etf.py
```

- If everything is mappable: it prints “All forecast symbols mappable” and exits 0.
- If not: it writes `forecast-missing.json` again and exits 1; repeat from step 1.

## Reference

| Source of truth for “valid tickers” | `data/etf_price.csv` (column names, excluding Date) |
| Check Yahoo | `uv run python tools/check_yahoo_ticker.py TICKER` |
| Mapping file | `makro-etf-colreated/etf-mapping.json` |
| Missing output | `makro-etf-colreated/forecast-missing.json` |
| Incremental add to CSV | `uv run python tools/append_etf_price_column.py TICKER` |
