"""
Append one ETF's Close price as a new column to data/etf_price.csv (incremental).
Usage: uv run python tools/append_etf_price_column.py ERUS
"""
import sys
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "etf_price.csv"


def main():
    if len(sys.argv) < 2:
        print("Usage: append_etf_price_column.py TICKER", file=sys.stderr)
        sys.exit(1)
    ticker = sys.argv[1].strip().upper()
    if not ticker:
        sys.exit(1)

    if not CSV_PATH.exists():
        print(f"Missing {CSV_PATH}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(CSV_PATH, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True)
    if ticker in df.columns:
        print(f"{ticker} already in CSV, skipping.")
        return

    start = df.index.min().to_pydatetime()
    end = df.index.max().to_pydatetime()
    print(f"Fetching {ticker} from {start.date()} to {end.date()}...")
    hist = yf.download(ticker, start=start, end=end, progress=False, threads=False, auto_adjust=False)
    if hist.empty:
        print(f"No data for {ticker}", file=sys.stderr)
        sys.exit(1)

    if isinstance(hist.columns, pd.MultiIndex):
        close = hist["Close"].copy()
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
    else:
        close = hist["Close"].copy() if "Close" in hist.columns else hist.iloc[:, 0]
    close.name = ticker
    close.index = pd.to_datetime(close.index)
    if close.index.tz is None:
        close.index = close.index.tz_localize("UTC")
    # Align by calendar date (CSV often has 05:00 UTC, yfinance has midnight)
    close_dates = close.index.normalize()
    close = close[~close_dates.duplicated(keep="last")]
    close.index = close.index.normalize()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df_dates = df.index.normalize()
    merged = df.copy()
    merged[ticker] = df_dates.map(close)
    merged.to_csv(CSV_PATH)
    non_null = merged[ticker].notna().sum()
    print(f"Appended {ticker}: {non_null} non-null rows. Wrote {CSV_PATH}")


if __name__ == "__main__":
    main()
