#!/usr/bin/env python3
"""
Build data/etf_price_by_country.csv from data/etf_price.csv.
Columns: Date, then country_code (CNA, INA, JPA, ...) matching buffet-ind.csv.
Uses one representative ETF per country from etf-v3 world_* segments.
"""
import csv
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent  # Go up from tools/ to root
DATA_DIR = SCRIPT_DIR / "data"
PRICE_CSV = DATA_DIR / "etf_price.csv"
OUTPUT_CSV = DATA_DIR / "etf_price_by_country.csv"

# country_code -> ticker (first ticker from etf-v3 used in etf_price)
COUNTRY_TICKER = {
    "CNA": "MCHI",   # China
    "INA": "INDA",   # India
    "JPA": "EWJ",    # Japan
    "KRA": "EWY",    # Korea
    "VNA": "VNM",    # Vietnam
    "IDA": "EIDO",   # Indonesia
    "SGA": "EWS",    # Singapore
    "AUA": "EWA",    # Australia
    "DEA": "EWG",    # Germany
    "GBA": "EWU",    # UK
    "FRA": "EWQ",    # France
    "NLA": "EWN",    # Netherlands
    "ITA": "EWI",    # Italy
    "ESA": "EWP",    # Spain
    "TRA": "TUR",    # Turkey
    "CAA": "EWC",    # Canada
    "MXA": "EWW",    # Mexico
    "BRA": "EWZ",    # Brazil
    "ARA": "ARGT",   # Argentina
    "SAA": "KSA",    # Saudi Arabia
    "ZAA": "EZA",    # South Africa
}

# Order of country columns (match buffet-ind order where possible)
COUNTRY_ORDER = [
    "CNA", "INA", "JPA", "KRA", "VNA", "IDA", "SGA", "AUA",
    "DEA", "GBA", "FRA", "NLA", "ITA", "ESA", "TRA",
    "CAA", "MXA", "BRA", "ARA", "SAA", "ZAA",
]


def main() -> None:
    with open(PRICE_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        all_tickers = reader.fieldnames or []

    ticker_to_country = {t: c for c, t in COUNTRY_TICKER.items()}
    # Which tickers we have in the CSV
    available = set(all_tickers) & set(COUNTRY_TICKER.values())

    out_columns = ["Date"] + [c for c in COUNTRY_ORDER if COUNTRY_TICKER[c] in available]

    out_rows = []
    for r in rows:
        out_row = [r.get("Date", "")]
        for code in out_columns[1:]:
            ticker = COUNTRY_TICKER[code]
            out_row.append(r.get(ticker, ""))
        out_rows.append(out_row)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(out_columns)
        w.writerows(out_rows)
    print(f"Wrote {OUTPUT_CSV} with columns: {out_columns}")


if __name__ == "__main__":
    main()
