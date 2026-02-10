#!/usr/bin/env python3
"""
Compare macro forecast (forecast.json) to actual ETF returns.
Uses etf-mapping.json for name -> ticker mapping.
If any forecast symbol is unmappable, write forecast-missing.json (same format as etf-mapping.json)
and exit without running correlation.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = Path(__file__).resolve().parent
FORECAST_DIR = ROOT / "macro-forecast-cursor-auto"
DATA_DIR = ROOT / "data"
FORECAST_JSON = FORECAST_DIR / "forecast.json"
FORECAST_ETF_JSON = WORK_DIR / "etf-mapping.json"
FORECAST_MISSING_JSON = WORK_DIR / "forecast-missing.json"
ETF_PRICE_CSV = DATA_DIR / "etf_price.csv"

CATEGORIES = ("countries", "commodity", "us_sector")


def load_forecast():
    with open(FORECAST_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("$") and isinstance(v, dict)}


def load_mapping():
    with open(FORECAST_ETF_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_etf_tickers():
    with open(ETF_PRICE_CSV, encoding="utf-8") as f:
        header = f.readline()
    return [c.strip() for c in header.split(",") if c.strip()][1:]  # skip Date


def collect_forecast_names(forecast_by_year):
    """Set of (category, name) that appear in forecast."""
    seen = set()
    for year_data in forecast_by_year.values():
        for cat in CATEGORIES:
            for item in year_data.get(cat, []):
                name = item.get("name")
                if name:
                    seen.add((cat, name))
    return seen


def find_unmappable(forecast_names, mapping, available_tickers):
    """
    Return dict same format as etf-mapping.json: only unmappable names with [].
    Unmappable = no mapping, empty list, or no listed ticker present in CSV.
    """
    missing = {"countries": {}, "commodity": {}, "us_sector": {}}
    for cat, name in forecast_names:
        tickers = (mapping.get(cat) or {}).get(name)
        if tickers is None:
            missing[cat][name] = []
            continue
        if not isinstance(tickers, list):
            missing[cat][name] = []
            continue
        valid = [t for t in tickers if t in available_tickers]
        if not valid:
            missing[cat][name] = []
            continue
        # mappable: at least one ticker in CSV; do not add to missing
    # Drop categories with no missing
    return {c: d for c, d in missing.items() if d}


def main():
    if not FORECAST_JSON.exists():
        print(f"Missing {FORECAST_JSON}", file=sys.stderr)
        sys.exit(1)
    if not FORECAST_ETF_JSON.exists():
        print(f"Missing {FORECAST_ETF_JSON}", file=sys.stderr)
        sys.exit(1)
    if not ETF_PRICE_CSV.exists():
        print(f"Missing {ETF_PRICE_CSV}", file=sys.stderr)
        sys.exit(1)

    forecast_by_year = load_forecast()
    mapping = load_mapping()
    available_tickers = set(load_etf_tickers())

    forecast_names = collect_forecast_names(forecast_by_year)
    unmappable = find_unmappable(forecast_names, mapping, available_tickers)

    if unmappable:
        with open(FORECAST_MISSING_JSON, "w", encoding="utf-8") as f:
            json.dump(unmappable, f, indent=2)
        print(f"Unmappable symbols written to {FORECAST_MISSING_JSON}", file=sys.stderr)
        for cat, names in unmappable.items():
            for name in names:
                print(f"  {cat}: {name}", file=sys.stderr)
        sys.exit(1)

    print("All forecast symbols mappable. (Correlation step not yet run.)")


if __name__ == "__main__":
    main()
