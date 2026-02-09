# Buffett Indicator – How to Get the Data

## What is the Buffett indicator?

The **Buffett indicator** (Stock Market Capitalization to GDP) is the ratio of a country’s stock market cap to its GDP. It is used as a rough valuation measure: high values can mean the market is expensive relative to the economy.

- **Source:** [FRED](https://fred.stlouisfed.org) (Federal Reserve Economic Data).
- **Series concept:** “Stock Market Capitalization to GDP” (annual, from the World Bank).
- **FRED series ID pattern:** `DDDM01{COUNTRY_CODE}156NWDB`  
  Example: USA → `DDDM01USA156NWDB`.

---

## How to get the data (this repo)

### 1. Get a FRED API key

1. Go to [https://fredaccount.stlouisfed.org/apikeys](https://fredaccount.stlouisfed.org/apikeys).
2. Sign in or create a free account.
3. Create an API key and copy it.

### 2. Set the API key

**Option A – Environment variable**

```bash
export FRED_API_KEY="your_key_here"
```

**Option B – `.env` in project root**

Create or edit `etf/.env`:

```
FRED_API_KEY=your_key_here
```

The script `buffet_ind/1_fetch_buffet_ind.py` will load this file if present (no extra library).

### 3. Fetch from FRED

From the project root (`etf/`):

```bash
uv run python fetch_buffet_ind.py
```

- **Output:** `data/buffet-ind.csv`.
- **Default range:** 2004–2020 (configurable via `YEAR_COLUMNS` in the script).
- **Columns written by fetch:** `country`, `country_code.source`, then one column per year (`2004`, `2005`, …).

The script uses a fixed list of countries and builds the FRED series ID as `DDDM01{CODE}156NWDB` (see `SERIES` in `fetch_buffet_ind.py`).

### 4. Optional: normalize columns for analysis

Downstream code (e.g. `buffet_etf_lead_analysis.py`) expects:

- `country_code` – 3-letter code (USA, CNA, JPA, …).
- `country_name` – optional (e.g. Thai or English labels).
- `country_code.source` – e.g. `USA.DDDM01USA156NWDB`.
- Year columns: `2004`, `2005`, … with numeric values.

If your CSV has a single “country” column (e.g. English name or `"CODE Name"`), you can:

- Manually rename columns and set `country_code` from the same codes used in `fetch_buffet_ind.py` (`SERIES`), or
- Use `parse_buffet_ind.py`, which expects the first column to be like `"CODE Name"` (e.g. `USA สหรัฐอเมริกา`) and splits it into `country_code` and `country_thai`, then overwrites `data/buffet-ind.csv`.

---

## File roles

| File | Role |
|------|------|
| `buffet_ind/1_fetch_buffet_ind.py` | Calls FRED API, writes `data/buffet-ind.csv` (normalized format: country_code, country_name, country_code.source, year columns). |
| `buffet_ind/2_buffet_etf_lead_analysis.py` | Analyzes correlation between Buffett indicator and next-year ETF returns. |
| `data/buffet-ind.csv` | Input for `buffet_ind/2_buffet_etf_lead_analysis.py` and charts. |

---

## Adding more countries or years

- **Countries:** Edit `SERIES` in `fetch_buffet_ind.py`. The FRED series ID must follow `DDDM01{CODE}156NWDB`. Check [FRED](https://fred.stlouisfed.org) for available series (search “Stock Market Capitalization to GDP” or “DDDM01”).
- **Years:** Change `YEAR_COLUMNS` in `fetch_buffet_ind.py` and the `observation_start` / `observation_end` in `fetch_series()`.

---

## References

- FRED: [https://fred.stlouisfed.org](https://fred.stlouisfed.org)
- API key signup: [https://fredaccount.stlouisfed.org/apikeys](https://fredaccount.stlouisfed.org/apikeys)
- Example series (USA): [DDDM01USA156NWDB](https://fred.stlouisfed.org/series/DDDM01USA156NWDB)
