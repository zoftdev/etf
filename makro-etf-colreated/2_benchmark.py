#!/usr/bin/env python3
"""
Benchmark: buy-hold (all ETFs, equal weight) vs follow macro recommend (rebalance yearly to that year's list).
Configurable: start_year, stop_order (last year we take a new recommend), benchmark_end_year.
Default test: start=2010, stop_order=2020, benchmark at end of 2025. Initial fund 1M$.
"""
import argparse
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = Path(__file__).resolve().parent
FORECAST_DIR = ROOT / "macro-forecast-cursor-auto"
DATA_DIR = ROOT / "data"
FORECAST_JSON = FORECAST_DIR / "forecast.json"
ETF_MAPPING_JSON = WORK_DIR / "etf-mapping.json"
ETF_PRICE_CSV = DATA_DIR / "etf_price.csv"

CATEGORIES = ("countries", "commodity", "us_sector")
INITIAL_CAPITAL = 1_000_000


def load_forecast():
    with open(FORECAST_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("$") and isinstance(v, dict)}


def load_mapping():
    with open(ETF_MAPPING_JSON, encoding="utf-8") as f:
        return json.load(f)


def get_recommended_tickers_for_year(forecast_year_data, mapping, available_tickers):
    """Return set of tickers that are recommended in this year's forecast (mapped, and present in CSV)."""
    tickers = set()
    for cat in CATEGORIES:
        for item in forecast_year_data.get(cat, []):
            name = item.get("name")
            if not name:
                continue
            mapped = (mapping.get(cat) or {}).get(name)
            if isinstance(mapped, list):
                for t in mapped:
                    if t in available_tickers:
                        tickers.add(t)
    return tickers


def last_trading_day_in_month(df: pd.DataFrame, year: int, month: int):
    """Return the last row index (date) in df that falls in (year, month), or None."""
    mask = (df.index.year == year) & (df.index.month == month)
    if not mask.any():
        return None
    return df.index[mask][-1]


def last_trading_day_in_year(df: pd.DataFrame, year: int):
    """Return the last row index in df for that year, or None."""
    mask = df.index.year == year
    if not mask.any():
        return None
    return df.index[mask][-1]


def run_buy_hold(prices: pd.DataFrame, all_tickers: list, start_date, end_date, capital: float):
    """Equal weight in all_tickers at start_date, hold until end_date. Exclude tickers with NaN at start."""
    row_start = prices.loc[prices.index <= start_date]
    if row_start.empty:
        return None, None, None, None
    t0 = row_start.index[-1]
    valid = [t for t in all_tickers if t in prices.columns and pd.notna(prices.loc[t0, t]) and prices.loc[t0, t] > 0]
    if not valid:
        return None, None, None, None
    n = len(valid)
    weight = 1.0 / n
    shares = {t: (capital * weight) / prices.loc[t0, t] for t in valid}
    row_end = prices.loc[prices.index <= end_date]
    if row_end.empty:
        return None, None, None, None
    t1 = row_end.index[-1]
    value = sum(shares[t] * prices.loc[t1, t] for t in valid if pd.notna(prices.loc[t1, t]))
    return value, valid, shares, None


def buy_hold_values_at_dates(prices: pd.DataFrame, shares: dict, valid: list, dates: list):
    """Portfolio value at each date using fixed shares."""
    out = []
    for d in dates:
        if d not in prices.index:
            row = prices.loc[prices.index <= d]
            if row.empty:
                continue
            d = row.index[-1]
        v = sum(shares[t] * prices.loc[d, t] for t in valid if t in prices.columns and pd.notna(prices.loc[d, t]))
        out.append((d, v))
    return out


def run_recommend(
    prices: pd.DataFrame,
    forecast_by_year: dict,
    mapping: dict,
    available_tickers: set,
    start_year: int,
    stop_order: int,
    end_date,
    capital: float,
):
    """Rebalance at end of Oct each year to that year's recommended list (equal weight). After stop_order hold until end_date.
    Returns (final_value, current_tickers, series) where series is list of (date, value) for chart."""
    rebalance_dates = []
    for y in range(start_year, stop_order + 1):
        d = last_trading_day_in_month(prices, y, 10)
        if d is not None:
            rebalance_dates.append(d)
    if not rebalance_dates:
        return None, [], []

    series = []
    t0 = rebalance_dates[0]
    year0 = t0.year
    tickers = get_recommended_tickers_for_year(
        forecast_by_year.get(str(year0), {}), mapping, available_tickers
    )
    tickers = [t for t in tickers if t in prices.columns and pd.notna(prices.loc[t0, t]) and prices.loc[t0, t] > 0]
    if not tickers:
        return None, [], []

    n = len(tickers)
    weight = 1.0 / n
    shares = {t: (capital * weight) / prices.loc[t0, t] for t in tickers}
    v0 = sum(shares[t] * prices.loc[t0, t] for t in tickers)
    series.append((t0, v0))
    current_tickers = list(tickers)

    for i in range(1, len(rebalance_dates)):
        t_rebal = rebalance_dates[i]
        value = sum(shares.get(t, 0) * prices.loc[t_rebal, t] for t in current_tickers if t in prices.columns and pd.notna(prices.loc[t_rebal, t]))
        if pd.isna(value) or value <= 0:
            continue
        series.append((t_rebal, value))
        y = t_rebal.year
        new_tickers = get_recommended_tickers_for_year(
            forecast_by_year.get(str(y), {}), mapping, available_tickers
        )
        new_tickers = [t for t in new_tickers if t in prices.columns and pd.notna(prices.loc[t_rebal, t]) and prices.loc[t_rebal, t] > 0]
        if not new_tickers:
            continue
        n = len(new_tickers)
        weight = 1.0 / n
        shares = {t: (value * weight) / prices.loc[t_rebal, t] for t in new_tickers}
        current_tickers = new_tickers

    row_end = prices.loc[prices.index <= end_date]
    if row_end.empty:
        return None, current_tickers, series
    t1 = row_end.index[-1]
    value = sum(shares.get(t, 0) * prices.loc[t1, t] for t in current_tickers if t in prices.columns and pd.notna(prices.loc[t1, t]))
    series.append((t1, value))
    return value, current_tickers, series


def main():
    ap = argparse.ArgumentParser(description="Benchmark buy-hold vs macro-recommend")
    ap.add_argument("--start", type=int, default=2010, help="First year we use a report (first rebalance end-Oct this year)")
    ap.add_argument("--stop-order", type=int, default=2020, help="Last year we take a new recommendation (rebalance end-Oct this year)")
    ap.add_argument("--benchmark-end", type=int, default=2025, help="Benchmark portfolio value at end of this year")
    ap.add_argument("--capital", type=float, default=INITIAL_CAPITAL, help="Initial capital in $")
    args = ap.parse_args()

    if not FORECAST_JSON.exists() or not ETF_MAPPING_JSON.exists() or not ETF_PRICE_CSV.exists():
        print("Missing forecast.json, etf-mapping.json, or data/etf_price.csv", file=__import__("sys").stderr)
        raise SystemExit(1)

    prices = pd.read_csv(ETF_PRICE_CSV, index_col=0, parse_dates=True)
    if prices.index.tz is None:
        prices.index = pd.to_datetime(prices.index)
    all_tickers = [c for c in prices.columns if c.strip()]
    available_tickers = set(all_tickers)

    forecast_by_year = load_forecast()
    mapping = load_mapping()

    start_date = last_trading_day_in_month(prices, args.start, 10)
    end_date = last_trading_day_in_year(prices, args.benchmark_end)
    if start_date is None or end_date is None:
        print(f"No price data for start Oct {args.start} or end Dec {args.benchmark_end}", file=__import__("sys").stderr)
        raise SystemExit(1)

    # Buy-hold: equal weight all ETFs at start_date, hold to end_date
    bh_value, bh_tickers, bh_shares, _ = run_buy_hold(prices, all_tickers, start_date, end_date, args.capital)
    # Recommend: rebalance yearly to that year's list
    rec_value, rec_tickers, rec_series = run_recommend(
        prices, forecast_by_year, mapping, available_tickers,
        args.start, args.stop_order, end_date, args.capital,
    )

    # Build chart dates (rebalance points + end)
    chart_dates = []
    for y in range(args.start, args.stop_order + 1):
        d = last_trading_day_in_month(prices, y, 10)
        if d is not None:
            chart_dates.append(d)
    if end_date not in chart_dates:
        chart_dates.append(end_date)
    chart_dates = sorted(set(chart_dates))

    if bh_value is not None and bh_tickers and bh_shares is not None:
        bh_series = buy_hold_values_at_dates(prices, bh_shares, bh_tickers, chart_dates)
    else:
        bh_series = []
    if rec_series:
        rec_dates = [x[0] for x in rec_series]
        rec_vals = [x[1] for x in rec_series]
    else:
        rec_dates, rec_vals = [], []
    if bh_series:
        bh_dates = [x[0] for x in bh_series]
        bh_vals = [x[1] for x in bh_series]
    else:
        bh_dates, bh_vals = [], []

    out_html = WORK_DIR / "benchmark_chart.html"
    fig = go.Figure()
    if bh_dates and bh_vals:
        fig.add_trace(go.Scatter(
            x=[d.strftime("%Y-%m-%d") for d in bh_dates],
            y=[float(v) for v in bh_vals],
            mode="lines+markers",
            name="Buy-hold (all ETFs)",
            line=dict(color="#1f77b4", width=2),
        ))
    if rec_dates and rec_vals:
        fig.add_trace(go.Scatter(
            x=[d.strftime("%Y-%m-%d") for d in rec_dates],
            y=[float(v) for v in rec_vals],
            mode="lines+markers",
            name="Recommend (rebalance to report)",
            line=dict(color="#ff7f0e", width=2),
        ))
    fig.update_layout(
        title=f"Portfolio value: Buy-hold vs Recommend (start={args.start}, stop_order={args.stop_order}, end={args.benchmark_end})",
        xaxis_title="Date",
        yaxis_title="Portfolio value ($)",
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        template="plotly_white",
    )
    fig.write_html(str(out_html))
    print(f"Chart: {out_html}")

    print(f"Config: start={args.start} stop_order={args.stop_order} benchmark_end={args.benchmark_end} capital=${args.capital:,.0f}")
    print(f"Start date: {start_date.date()}  End date: {end_date.date()}")
    print()
    if bh_value is not None:
        bh_ret = (bh_value / args.capital - 1) * 100
        print(f"Buy-hold (all ETFs, n={len(bh_tickers)}): ${bh_value:,.2f}  ({bh_ret:+.2f}%)")
    else:
        print("Buy-hold: no valid allocation")
    if rec_value is not None:
        rec_ret = (rec_value / args.capital - 1) * 100
        print(f"Recommend (rebalance to report, n={len(rec_tickers)}): ${rec_value:,.2f}  ({rec_ret:+.2f}%)")
    else:
        print("Recommend: no valid allocation")
    if bh_value is not None and rec_value is not None:
        diff = rec_value - bh_value
        print(f"Difference (Recommend - Buy-hold): ${diff:+,.2f}")


if __name__ == "__main__":
    main()
