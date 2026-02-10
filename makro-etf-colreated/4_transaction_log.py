#!/usr/bin/env python3
"""List every transaction in the US-Sector Only (score-weighted) simulation."""
import json
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
prices = pd.read_csv(ROOT / "data" / "etf_price.csv", index_col=0, parse_dates=True)
prices.index = pd.to_datetime(prices.index)

with open(ROOT / "macro-forecast-cursor-auto" / "forecast.json") as f:
    forecast = {k: v for k, v in json.load(f).items() if not k.startswith("$")}
with open(Path(__file__).resolve().parent / "etf-mapping.json") as f:
    mapping = json.load(f)

CAPITAL = 1_000_000
START = 2010
STOP = 2022


def get_sector_tickers(year):
    fdata = forecast.get(str(year), {})
    out = {}
    for item in fdata.get("us_sector", []):
        name = item.get("name")
        score = item.get("score", 0)
        for t in mapping.get("us_sector", {}).get(name, []):
            if t in prices.columns:
                out[t] = max(out.get(t, 0), score)
    return out


def last_td(year, month):
    mask = (prices.index.year == year) & (prices.index.month == month)
    return prices.index[mask][-1] if mask.any() else None


def last_td_year(year):
    mask = prices.index.year == year
    return prices.index[mask][-1] if mask.any() else None


def score_weights(scored):
    total = sum(scored.values())
    return {t: s / total for t, s in scored.items()}


shares = {}
current_tickers = []
portfolio_value = CAPITAL
tx_id = 0

hdr = (
    f"{'#':<4} {'Date':<12} {'Action':<6} {'ETF':<6} "
    f"{'Shares':>10} {'Price':>10} {'Amount($)':>14} {'Portfolio($)':>14}  Note"
)
print(hdr)
print("-" * len(hdr))

for year in range(START, STOP + 1):
    rebal = last_td(year, 10)
    if rebal is None:
        continue
    ds = rebal.strftime("%Y-%m-%d")

    scored = {
        t: s
        for t, s in get_sector_tickers(year).items()
        if pd.notna(prices.loc[rebal, t]) and prices.loc[rebal, t] > 0
    }
    weights = score_weights(scored)
    new_set = set(scored)
    old_set = set(current_tickers)

    # Current value
    if shares:
        portfolio_value = sum(
            shares[t] * prices.loc[rebal, t]
            for t in current_tickers
            if t in prices.columns and pd.notna(prices.loc[rebal, t])
        )

    # SELL
    for t in sorted(current_tickers):
        p = prices.loc[rebal, t]
        if pd.isna(p):
            continue
        amt = shares[t] * p
        note = "EXIT" if t not in new_set else "rebalance-sell"
        tx_id += 1
        print(
            f"{tx_id:<4} {ds:<12} {'SELL':<6} {t:<6} "
            f"{shares[t]:>10.2f} {p:>10.2f} {amt:>14,.2f} {'':>14}  {note}"
        )

    # BUY
    new_shares = {}
    for t in sorted(new_set):
        p = prices.loc[rebal, t]
        if pd.isna(p) or p <= 0:
            continue
        alloc = portfolio_value * weights[t]
        sh = alloc / p
        new_shares[t] = sh
        note = "NEW" if t not in old_set else "rebalance-buy"
        tx_id += 1
        print(
            f"{tx_id:<4} {ds:<12} {'BUY':<6} {t:<6} "
            f"{sh:>10.2f} {p:>10.2f} {alloc:>14,.2f} {portfolio_value:>14,.2f}  {note}"
        )

    shares = new_shares
    current_tickers = sorted(new_set)

    holdings = " ".join(f"{t}({weights[t]*100:.1f}%)" for t in sorted(new_set))
    print(f"     {ds}  >>> Portfolio ${portfolio_value:,.2f}  Holdings: {holdings}")
    print()

# End value
end = last_td_year(2022)
ds = end.strftime("%Y-%m-%d")
final = sum(
    shares[t] * prices.loc[end, t]
    for t in current_tickers
    if t in prices.columns and pd.notna(prices.loc[end, t])
)

print("=" * 80)
print(f"FINAL POSITION at {ds}")
print("-" * 80)
for t in current_tickers:
    p = prices.loc[end, t]
    v = shares[t] * p
    cost_w = weights[t] * portfolio_value  # last rebalance alloc
    ret = (v / cost_w - 1) * 100 if cost_w > 0 else 0
    print(f"  {t}: {shares[t]:>10,.2f} sh x ${p:>8.2f} = ${v:>14,.2f}  (since Oct rebal: {ret:+.1f}%)")
print(f"  TOTAL: ${final:,.2f}")
print(f"  Overall return: {(final / CAPITAL - 1) * 100:+.1f}%")
print(f"  Total transactions: {tx_id}")
