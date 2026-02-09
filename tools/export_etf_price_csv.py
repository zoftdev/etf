"""
Export 20-year close price of all ETFs from etf.yaml to ./data/etf_price.csv
Uses etf_data_fetcher.ETFDataFetcher.
"""
from pathlib import Path

import pandas as pd

from core.etf_data_fetcher import ETFDataFetcher

YEARS = 20
CALENDAR_DAYS = YEARS * 365 + 60
# Path relative to project root
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "etf_price.csv"


def main():
    fetcher = ETFDataFetcher(yaml_path="config/etf.yaml")
    tickers = list(fetcher.tickers_map.keys())
    if not tickers:
        print("No tickers from etf.yaml.")
        return

    print(f"Fetching {len(tickers)} tickers, {YEARS} years (~{CALENDAR_DAYS} calendar days)...")
    history, errors = fetcher.fetch_history_days(CALENDAR_DAYS, tickers=tickers)
    if errors:
        for t, msg in list(errors.items())[:15]:
            print(f"  {t}: {msg}")
        if len(errors) > 15:
            print(f"  ... and {len(errors) - 15} more")

    # Build wide DataFrame: index=date, columns=ticker, values=Close
    close_series = {}
    for ticker, df in history.items():
        if df is not None and "Close" in df.columns:
            close_series[ticker] = df["Close"]
    if not close_series:
        print("No close data to export.")
        return

    out_df = pd.DataFrame(close_series)
    out_df.index.name = "Date"
    out_path = Path(OUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path)
    print(f"Wrote {out_path.absolute()}")
    print(f"Wrote {out_df.shape[0]} rows x {out_df.shape[1]} tickers -> {out_path.absolute()}")


if __name__ == "__main__":
    main()
