#!/usr/bin/env python3
"""
Fetch Buffett Indicator (Stock Market Cap to GDP) from FRED and write data/buffet-ind.csv.
Requires FRED_API_KEY in environment. Get a free key: https://fredaccount.stlouisfed.org/apikeys

Output format: country_code, country_name, country_code.source, 2004, 2005, ...
- country_code: 3-letter code (USA, CNA, JPA, ...)
- country_name: Empty by default (can be filled manually if needed)
- country_code.source: e.g., "USA.DDDM01USA156NWDB"
- Year columns: Numeric values for each year
"""
import csv
import os
import urllib.request
import json
from pathlib import Path

# Load .env from project root if present (no extra dependency)
_env = Path(__file__).resolve().parent / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
OUTPUT_PATH = str(Path(__file__).resolve().parent.parent / "data" / "buffet-ind.csv")
YEAR_COLUMNS = [str(y) for y in range(2004, 2021)]

# country, country label, FRED series_id (DDDM01 = market cap to GDP)
SERIES = [
    ("United States", "USA"),
    ("China", "CNA"),
    ("Japan", "JPA"),
    ("India", "INA"),
    ("United Kingdom", "GBA"),
    ("Republic of Korea", "KRA"),
    ("Germany", "DEA"),
    ("France", "FRA"),
    ("Canada", "CAA"),
    ("Australia", "AUA"),
    ("Brazil", "BRA"),
    ("Mexico", "MXA"),
    ("Indonesia", "IDA"),
    ("South Africa", "ZAA"),
    ("Turkey", "TRA"),
    ("Viet Nam", "VNA"),
    ("Philippines", "PHA"),
    ("Singapore", "SGA"),
    ("Hong Kong SAR", "HKA"),
    ("Spain", "ESA"),
    ("Italy", "ITA"),
    ("Poland", "PLA"),
    ("Saudi Arabia", "SAA"),
    ("Egypt", "EGA"),
    ("Argentina", "ARA"),
    ("Greece", "GRA"),
    ("Russian Federation", "RUA"),
    ("Qatar", "QAA"),
    ("Nigeria", "NGA"),
    ("Netherlands", "NLA"),
    ("Czech Republic", "CZA"),
    ("Bangladesh", "BDA"),
    ("Kenya", "KEA"),
    ("Iran", "IRA"),
    ("Mauritius", "MUA"),
]


def fetch_series(series_id: str, api_key: str) -> dict[str, str]:
    """Fetch observations for one FRED series. Returns {date: value}."""
    url = (
        f"{FRED_BASE}?series_id={series_id}&api_key={api_key}&file_type=json"
        f"&observation_start=2004-01-01&observation_end=2020-12-31&sort_order=asc"
    )
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read().decode())
    out = {}
    for ob in data.get("observations", []):
        date = ob.get("date", "")
        value = ob.get("value", "")
        if date and value != ".":
            year = date[:4]
            out[year] = value
    return out


def main() -> None:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print("Set FRED_API_KEY. Get a free key: https://fredaccount.stlouisfed.org/apikeys")
        return

    rows = []
    for country, code in SERIES:
        series_id = f"DDDM01{code}156NWDB"
        country_code_source = f"{code}.{series_id}"
        try:
            obs = fetch_series(series_id, api_key)
        except Exception as e:
            print(f"Skip {country} ({series_id}): {e}")
            obs = {}
        # Output parsed format: country_code, country_name, country_code.source, year columns
        # country_name is empty by default (can be filled manually if needed)
        row = [code, "", country_code_source]
        for y in YEAR_COLUMNS:
            row.append(obs.get(y, ""))
        rows.append(row)

    header = ["country_code", "country_name", "country_code.source"] + YEAR_COLUMNS
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
