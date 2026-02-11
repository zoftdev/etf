"""One-off: fetch Yahoo Finance OHLCV for given ticker(s) on a specific date.
Usage: uv run python tools/check_date_yahoo.py 2013-12-31 EWG EWGS
"""
import sys
from datetime import datetime

import pandas as pd
import yfinance as yf

def main():
    if len(sys.argv) < 3:
        print("Usage: check_date_yahoo.py YYYY-MM-DD TICKER [TICKER ...]", file=sys.stderr)
        sys.exit(1)
    date_str = sys.argv[1]
    tickers = [t.strip().upper() for t in sys.argv[2:] if t.strip()]
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"Invalid date: {date_str}", file=sys.stderr)
        sys.exit(1)
    from datetime import timedelta
    start = target.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=2)

    print(f"Yahoo Finance: {date_str}")
    print("-" * 60)
    for ticker in tickers:
        hist = yf.download(ticker, start=start, end=end, progress=False, threads=False, auto_adjust=False)
        if hist.empty:
            print(f"  {ticker}: NO DATA")
            continue
        # Single ticker: columns are Open, High, Low, Close; multi: MultiIndex
        if isinstance(hist.columns, pd.MultiIndex):
            hist = hist.copy()
            hist.columns = hist.columns.get_level_values(0)
        # Keep only row(s) for target date
        try:
            dates = hist.index.date
        except AttributeError:
            dates = pd.to_datetime(hist.index).date
        row = hist.loc[dates == target.date()]
        if row.empty:
            print(f"  {ticker}: NO ROW for {date_str} (market may be closed or no data)")
            continue
        r = row.iloc[0]
        o = r.get("Open", getattr(r, "Open", None))
        h = r.get("High", getattr(r, "High", None))
        l_ = r.get("Low", getattr(r, "Low", None))
        c = r.get("Close", getattr(r, "Close", None))
        adj = r.get("Adj Close", getattr(r, "Adj Close", c))
        vol = r.get("Volume", getattr(r, "Volume", 0))
        print(f"  {ticker}: Open={o} High={h} Low={l_} Close={c} Adj Close={adj} Volume={vol}")
    print("-" * 60)

if __name__ == "__main__":
    main()
