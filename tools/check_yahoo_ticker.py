"""
Check if ticker(s) have data on Yahoo Finance before adding to etf_price / config.
Usage: uv run python tools/check_yahoo_ticker.py ERUS
       uv run python tools/check_yahoo_ticker.py ERUS RSX GLD
"""
import sys
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

# Default window: ~5 years back from today
END = datetime.now()
START = END - timedelta(days=5 * 365 + 60)


def main():
    if len(sys.argv) < 2:
        print("Usage: check_yahoo_ticker.py TICKER [TICKER ...]", file=sys.stderr)
        sys.exit(1)
    tickers = [t.strip().upper() for t in sys.argv[1:] if t.strip()]
    if not tickers:
        sys.exit(1)

    print(f"Yahoo Finance check: {START.date()} → {END.date()}")
    print("-" * 60)
    all_ok = True
    for ticker in tickers:
        hist = yf.download(ticker, start=START, end=END, progress=False, threads=False, auto_adjust=False)
        if hist.empty:
            print(f"  {ticker}: NO DATA (empty)")
            all_ok = False
            continue
        if isinstance(hist.columns, pd.MultiIndex):
            close = hist["Close"]
            valid = close.iloc[:, 0].dropna() if close.ndim > 1 else close.dropna()
        else:
            valid = hist["Close"].dropna() if "Close" in hist.columns else pd.Series(dtype=float)

        if len(valid) == 0:
            print(f"  {ticker}: NO DATA")
            all_ok = False
            continue
        start_d = valid.index.min()
        end_d = valid.index.max()
        n = len(valid)
        sample = valid.iloc[-1] if len(valid) else None
        print(f"  {ticker}: OK  rows={n}  {start_d} → {end_d}  (last Close={sample})")
    print("-" * 60)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
