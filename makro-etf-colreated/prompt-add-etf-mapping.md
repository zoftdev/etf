# Prompt: Add missing ETF mapping into mapping file

Use this when `1_create_mapping.py` has written `forecast-missing.json` and you need to add those entries to the mapping file.

---

**Task:** Add every missing forecast name from `forecast-missing.json` into `etf-mapping.json` (in this dir) so that each name maps to at least one **ticker that exists as a column** in `data/etf_price.csv` (repo root).

**Rules:**
1. **Exact names** — Use the forecast name exactly as in `forecast-missing.json` (and as in `macro-forecast-cursor-auto/forecast.json`). Names are case-sensitive (e.g. `"Consumer Discretionary"` vs `"Consumer discretionary"`).
2. **Valid tickers only** — Every ticker in the list must be a column header in `data/etf_price.csv`. If a ticker is not there yet, add it first (see repo root `prompt-fill-etf.md` step 4), then add the mapping.
3. **Same structure** — `etf-mapping.json` has three top-level keys: `"countries"`, `"commodity"`, `"us_sector"`. Put each missing name under the same key it has in `forecast-missing.json`.
4. **Value format** — Each name must map to a JSON array of one or more ticker strings, e.g. `["ERUS"]` or `["XLK"]`.

**Example:** If `forecast-missing.json` contains:
```json
{
  "countries": { "Russia": [] },
  "us_sector": { "Industrials": [] }
}
```
then in `etf-mapping.json` add (or update):
- Under `countries`: `"Russia": ["ERUS"]` (only if `ERUS` is a column in `data/etf_price.csv`).
- Under `us_sector`: `"Industrials": ["XLI"]` (only if `XLI` is a column in `data/etf_price.csv`).

**Check before editing:** If you are unsure whether a ticker exists in the CSV, run from repo root:
```bash
uv run python tools/check_yahoo_ticker.py TICKER
```
and confirm the ticker appears in the first line of `data/etf_price.csv` (as a column name).

**After editing:** Run the compare script again (from repo root). It will accept the new mappings or write an updated `forecast-missing.json` if anything is still unmappable.
```bash
uv run python makro-etf-colreated/1_create_mapping.py
```

**Reference (this dir):**
- Mapping file: `etf-mapping.json`
- Missing list: `forecast-missing.json`
- Valid tickers: column names in `data/etf_price.csv` (excluding `Date`)
- Full flow (adding new tickers to CSV): repo root `prompt-fill-etf.md`
