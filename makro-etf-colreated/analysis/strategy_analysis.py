#!/usr/bin/env python3
"""
Explore multiple strategies to beat buy-hold using macro forecast recommendations.
Strategies tested:
  1. Equal-weight all recommendations (baseline "recommend")
  2. Score-weighted allocation
  3. Top-N highest-scored picks only
  4. Score threshold filter (only score >= X)
  5. Category-only (only countries / only commodity / only us_sector)
  6. Rebalance timing (Jan, Apr, Jul, Oct, Dec)
  7. Concentrated top-3
  8. US-sector only (score-weighted)
  9. Inverse/contrarian: equal-weight tickers NOT in recommendation
  10. Mixed: top half by score, score-weighted
"""
import json
from pathlib import Path

import pandas as pd
import numpy as np
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = Path(__file__).resolve().parent
FORECAST_JSON = ROOT / "macro-forecast-cursor-auto" / "forecast.json"
ETF_MAPPING_JSON = WORK_DIR / "etf-mapping.json"
ETF_PRICE_CSV = ROOT / "data" / "etf_price.csv"

CATEGORIES = ("countries", "commodity", "us_sector")
INITIAL_CAPITAL = 1_000_000

# ─── loaders ───
def load_forecast():
    with open(FORECAST_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("$") and isinstance(v, dict)}

def load_mapping():
    with open(ETF_MAPPING_JSON, encoding="utf-8") as f:
        return json.load(f)

# ─── helpers ───
def last_td(df, year, month):
    mask = (df.index.year == year) & (df.index.month == month)
    if not mask.any():
        return None
    return df.index[mask][-1]

def last_td_year(df, year):
    mask = df.index.year == year
    if not mask.any():
        return None
    return df.index[mask][-1]

def get_scored_tickers(forecast_year_data, mapping, available, categories=CATEGORIES):
    """Return list of (ticker, score) for this year's recommendations."""
    out = []
    for cat in categories:
        for item in forecast_year_data.get(cat, []):
            name = item.get("name")
            score = item.get("score", 0.5)
            if not name:
                continue
            mapped = (mapping.get(cat) or {}).get(name)
            if isinstance(mapped, list):
                for t in mapped:
                    if t in available:
                        out.append((t, score))
    # deduplicate: keep highest score per ticker
    best = {}
    for t, s in out:
        if t not in best or s > best[t]:
            best[t] = s
    return list(best.items())

def valid_at_date(prices, ticker_score_list, date):
    """Filter to tickers with valid prices at date."""
    return [(t, s) for t, s in ticker_score_list
            if t in prices.columns and pd.notna(prices.loc[date, t]) and prices.loc[date, t] > 0]


# ─── strategy runners ───
def run_strategy(prices, forecast_by_year, mapping, available,
                 start_year, stop_order, end_date, capital,
                 weight_fn, picker_fn=None, rebalance_month=10,
                 categories=CATEGORIES):
    """
    Generic strategy runner with daily series for accurate drawdown/per-year stats.
    """
    rebalance_dates = []
    for y in range(start_year, stop_order + 1):
        d = last_td(prices, y, rebalance_month)
        if d is not None:
            rebalance_dates.append(d)
    if not rebalance_dates:
        return None, [], []

    t0 = rebalance_dates[0]
    year0 = t0.year

    scored = get_scored_tickers(forecast_by_year.get(str(year0), {}), mapping, available, categories)
    scored = valid_at_date(prices, scored, t0)
    if picker_fn:
        scored = picker_fn(scored)
    if not scored:
        return None, [], []

    weights = weight_fn(scored)
    tickers = list(weights.keys())
    shares = {t: (capital * weights[t]) / prices.loc[t0, t] for t in tickers}
    current_tickers = tickers

    # Build daily series from t0 to end_date
    mask = (prices.index >= t0) & (prices.index <= end_date)
    daily_dates = prices.index[mask]
    series = []
    rebal_set = set(rebalance_dates[1:])  # skip first, already allocated

    for d in daily_dates:
        value = sum(shares.get(t, 0) * prices.loc[d, t]
                    for t in current_tickers
                    if t in prices.columns and pd.notna(prices.loc[d, t]))
        if pd.isna(value) or value <= 0:
            continue
        series.append((d, value))

        if d in rebal_set:
            y = d.year
            scored = get_scored_tickers(forecast_by_year.get(str(y), {}), mapping, available, categories)
            scored = valid_at_date(prices, scored, d)
            if picker_fn:
                scored = picker_fn(scored)
            if not scored:
                continue
            weights = weight_fn(scored)
            tickers = list(weights.keys())
            shares = {t: (value * weights[t]) / prices.loc[d, t] for t in tickers}
            current_tickers = tickers

    final_val = series[-1][1] if series else None
    return final_val, current_tickers, series


# ─── weight functions ───
def equal_weight(scored):
    n = len(scored)
    return {t: 1.0 / n for t, s in scored}

def score_weight(scored):
    total = sum(s for _, s in scored)
    if total == 0:
        return equal_weight(scored)
    return {t: s / total for t, s in scored}

def score_sq_weight(scored):
    total = sum(s ** 2 for _, s in scored)
    if total == 0:
        return equal_weight(scored)
    return {t: (s ** 2) / total for t, s in scored}

# ─── picker functions ───
def top_n(n):
    def fn(scored):
        scored_sorted = sorted(scored, key=lambda x: x[1], reverse=True)
        return scored_sorted[:n]
    return fn

def score_threshold(thresh):
    def fn(scored):
        filtered = [(t, s) for t, s in scored if s >= thresh]
        return filtered if filtered else scored[:1]  # fallback to best
    return fn


# ─── buy-hold ───
def run_buy_hold(prices, all_tickers, start_date, end_date, capital):
    row_start = prices.loc[prices.index <= start_date]
    if row_start.empty:
        return None, [], {}
    t0 = row_start.index[-1]
    valid = [t for t in all_tickers
             if t in prices.columns and pd.notna(prices.loc[t0, t]) and prices.loc[t0, t] > 0]
    if not valid:
        return None, [], {}
    n = len(valid)
    w = 1.0 / n
    shares = {t: (capital * w) / prices.loc[t0, t] for t in valid}
    # Daily series
    mask = (prices.index >= t0) & (prices.index <= end_date)
    daily_dates = prices.index[mask]
    series = []
    for d in daily_dates:
        v = sum(shares[t] * prices.loc[d, t] for t in valid
                if t in prices.columns and pd.notna(prices.loc[d, t]))
        series.append((d, v))
    final_val = series[-1][1] if series else None
    return final_val, valid, series


def portfolio_at_dates(prices, shares, tickers, dates):
    out = []
    for d in dates:
        if d not in prices.index:
            row = prices.loc[prices.index <= d]
            if row.empty:
                continue
            d = row.index[-1]
        v = sum(shares[t] * prices.loc[d, t]
                for t in tickers
                if t in prices.columns and pd.notna(prices.loc[d, t]))
        out.append((d, v))
    return out


def annualized_return(capital, final, years):
    if capital <= 0 or final is None or final <= 0:
        return None
    return (final / capital) ** (1.0 / years) - 1


def max_drawdown(series):
    if not series or len(series) < 2:
        return 0
    vals = [v for _, v in series]
    peak = vals[0]
    dd = 0
    for v in vals:
        if v > peak:
            peak = v
        dd = min(dd, (v - peak) / peak)
    return dd


# ─── main ───
def main():
    prices = pd.read_csv(ETF_PRICE_CSV, index_col=0, parse_dates=True)
    if prices.index.tz is None:
        prices.index = pd.to_datetime(prices.index)
    all_tickers = [c for c in prices.columns if c.strip()]
    available = set(all_tickers)

    forecast_by_year = load_forecast()
    mapping = load_mapping()

    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2010)
    ap.add_argument("--stop-order", type=int, default=2022)
    ap.add_argument("--end", type=int, default=2023, help="Benchmark end year (default: 1 year after last recommendation)")
    ap.add_argument("--capital", type=float, default=INITIAL_CAPITAL)
    args = ap.parse_args()

    start_year = args.start
    stop_order = args.stop_order
    bench_end_year = args.end
    capital = args.capital

    start_date = last_td(prices, start_year, 10)
    end_date = last_td_year(prices, bench_end_year)
    if start_date is None or end_date is None:
        print("No price data for start/end")
        return

    years = (end_date - start_date).days / 365.25

    # Collect all tickers that ever appear in recommendations (the investable universe)
    rec_universe = set()
    for yr, fdata in forecast_by_year.items():
        for cat in CATEGORIES:
            for item in fdata.get(cat, []):
                name = item.get("name")
                if not name:
                    continue
                mapped = (mapping.get(cat) or {}).get(name)
                if isinstance(mapped, list):
                    for t in mapped:
                        if t in available:
                            rec_universe.add(t)
    rec_universe_list = sorted(rec_universe)

    # Buy-hold baselines
    bh_all_val, bh_all_tickers, bh_all_series = run_buy_hold(prices, all_tickers, start_date, end_date, capital)
    bh_rec_val, bh_rec_tickers, bh_rec_series = run_buy_hold(prices, rec_universe_list, start_date, end_date, capital)

    print(f"Recommendation universe: {rec_universe_list} ({len(rec_universe_list)} tickers)")
    print(f"All ETFs in CSV: {len(all_tickers)} tickers")
    print()

    # ─── define strategies ───
    # Each entry: (name, run_kwargs, meta) where meta stores categories for reporting
    strategy_defs = [
        ("EqWt All Recs",       dict(weight_fn=equal_weight), CATEGORIES),
        ("Score-Wt All Recs",   dict(weight_fn=score_weight), CATEGORIES),
        ("Score²-Wt All Recs",  dict(weight_fn=score_sq_weight), CATEGORIES),
        ("Top-3 Score-Wt",      dict(weight_fn=score_weight, picker_fn=top_n(3)), CATEGORIES),
        ("Top-5 Score-Wt",      dict(weight_fn=score_weight, picker_fn=top_n(5)), CATEGORIES),
        ("Top-5 EqWt",          dict(weight_fn=equal_weight, picker_fn=top_n(5)), CATEGORIES),
        ("Thresh>=0.7 ScWt",    dict(weight_fn=score_weight, picker_fn=score_threshold(0.7)), CATEGORIES),
        ("Thresh>=0.8 ScWt",    dict(weight_fn=score_weight, picker_fn=score_threshold(0.8)), CATEGORIES),
        ("US-Sector Only ScWt", dict(weight_fn=score_weight), ("us_sector",)),
        ("US-Sector Only EqWt", dict(weight_fn=equal_weight), ("us_sector",)),
        ("Countries Only ScWt", dict(weight_fn=score_weight), ("countries",)),
        ("Commodity Only ScWt", dict(weight_fn=score_weight), ("commodity",)),
        ("US-Sect+Commod ScWt", dict(weight_fn=score_weight), ("us_sector", "commodity")),
        ("All ScWt Jan Rebal",  dict(weight_fn=score_weight, rebalance_month=1), CATEGORIES),
        ("All ScWt Dec Rebal",  dict(weight_fn=score_weight, rebalance_month=12), CATEGORIES),
        ("Top-3 EqWt",          dict(weight_fn=equal_weight, picker_fn=top_n(3)), CATEGORIES),
    ]

    # ─── run all ───
    results = []
    strat_cats = {}  # name -> categories tuple

    for name, kwargs, cats in strategy_defs:
        strat_cats[name] = cats
        rebal_m = kwargs.pop("rebalance_month", 10)
        val, tickers, series = run_strategy(
            prices, forecast_by_year, mapping, available,
            start_year, stop_order, end_date, capital,
            categories=cats, rebalance_month=rebal_m,
            **kwargs,
        )
        ann = annualized_return(capital, val, years)
        dd = max_drawdown(series)
        results.append((name, val, ann, dd, len(tickers), series))

    # ─── print summary ───
    def print_row(name, val, ann, dd, n, beat_label):
        if val is None:
            print(f"{name:<30} {'N/A':>14}")
            return
        ret = ((val / capital) - 1) * 100
        print(f"{name:<30} {val:>14,.0f} {ret:>8.1f}% {ann*100:>7.2f}% {dd*100:>7.1f}%  {n:>5}  {beat_label}")

    print("=" * 115)
    print(f"{'Strategy':<30} {'Final $':>14} {'Total %':>9} {'Ann %':>8} {'MaxDD%':>8} {'#ETFs':>6}  Beat B&H?")
    print("-" * 115)

    # Two buy-hold baselines
    bh_all_ann = annualized_return(capital, bh_all_val, years)
    bh_all_dd = max_drawdown(bh_all_series)
    bh_rec_ann = annualized_return(capital, bh_rec_val, years)
    bh_rec_dd = max_drawdown(bh_rec_series)

    print_row("B&H ALL 60 ETFs", bh_all_val, bh_all_ann, bh_all_dd, len(bh_all_tickers), "ref")
    print_row("B&H Rec Universe (17 ETFs)", bh_rec_val, bh_rec_ann, bh_rec_dd, len(bh_rec_tickers), "BASELINE")
    print("-" * 115)

    # Use rec-universe buy-hold as the real baseline
    bh_val = bh_rec_val

    winners = []
    for name, val, ann, dd, n, series in results:
        if val is None:
            print(f"{name:<30} {'N/A':>14}")
            continue
        beat = "YES" if val and val > bh_val else "no"
        if val and val > bh_val:
            winners.append((name, val, ann, dd))
        print_row(name, val, ann, dd, n, beat)

    print("=" * 115)

    if winners:
        print(f"\n>>> {len(winners)} strategies beat B&H Rec Universe:")
        for name, val, ann, dd in sorted(winners, key=lambda x: -x[1]):
            excess = val - bh_val
            print(f"    {name}: +${excess:,.0f} excess  ({ann*100:.2f}% ann, {dd*100:.1f}% maxDD)")
    else:
        print("\n>>> No strategy beat B&H Rec Universe on total return.")
        print("    Closest strategies:")
        ranked = sorted(results, key=lambda x: x[1] if x[1] else 0, reverse=True)
        for name, val, ann, dd, n, _ in ranked[:5]:
            if val:
                gap = bh_val - val
                print(f"    {name}: ${val:,.0f} (gap: -${gap:,.0f})")

    # ─── per-year breakdown ───
    print("\n\n=== Per-Year Return Breakdown (Jan-Dec) ===")
    top_strats = sorted(results, key=lambda x: x[1] if x[1] else 0, reverse=True)[:3]
    all_for_yearly = [
        ("B&H All60", bh_all_val, bh_all_ann, bh_all_dd, len(bh_all_tickers), bh_all_series),
        ("B&H Rec17", bh_rec_val, bh_rec_ann, bh_rec_dd, len(bh_rec_tickers), bh_rec_series),
    ] + top_strats

    header = f"{'Year':<6}"
    for r in all_for_yearly:
        header += f" {r[0]:>20}"
    print(header)
    print("-" * (6 + 21 * len(all_for_yearly)))

    def year_return(series, y):
        pts = [(d, v) for d, v in series if d.year == y]
        if len(pts) >= 2:
            return (pts[-1][1] / pts[0][1] - 1) * 100
        return None

    for y in range(start_year, bench_end_year + 1):
        row = f"{y:<6}"
        for name, val, ann, dd, n, series in all_for_yearly:
            yr = year_return(series, y)
            if yr is not None:
                row += f" {yr:>19.1f}%"
            else:
                row += f" {'--':>20}"
        print(row)

    # ─── yearly allocation detail for winning strategies ───
    if winners:
        print("\n\n=== Yearly Allocation Detail (winning strategies) ===")
        for wname, _, _, _ in winners:
            cats = strat_cats.get(wname, CATEGORIES)
            print(f"\n--- {wname} (categories: {', '.join(cats)}) ---")
            for y in range(start_year, stop_order + 1):
                fdata = forecast_by_year.get(str(y), {})
                scored = get_scored_tickers(fdata, mapping, available, cats)
                scored_sorted = sorted(scored, key=lambda x: -x[1])
                tlist = ", ".join(f"{t}({s:.2f})" for t, s in scored_sorted)
                print(f"  {y}: {tlist}")

    # ─── chart (weekly sampling for manageable file size) ───
    def weekly_sample(series):
        if not series:
            return [], []
        sampled = [series[0]]
        for d, v in series[1:]:
            if (d - sampled[-1][0]).days >= 5:
                sampled.append((d, v))
        if series[-1] != sampled[-1]:
            sampled.append(series[-1])
        return [d.strftime("%Y-%m-%d") for d, _ in sampled], [v for _, v in sampled]

    fig = go.Figure()
    if bh_all_series:
        xd, yd = weekly_sample(bh_all_series)
        fig.add_trace(go.Scatter(
            x=xd, y=yd,
            mode="lines", name=f"B&H All 60 ETFs (${bh_all_val:,.0f})",
            line=dict(color="#1f77b4", width=2, dash="dash"),
        ))
    if bh_rec_series:
        xd, yd = weekly_sample(bh_rec_series)
        fig.add_trace(go.Scatter(
            x=xd, y=yd,
            mode="lines", name=f"B&H Rec Universe 17 ETFs (${bh_rec_val:,.0f})",
            line=dict(color="#1f77b4", width=3),
        ))

    colors = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
              "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8",
              "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94", "#f7b6d2"]

    for i, (name, val, ann, dd, n, series) in enumerate(results):
        if not series:
            continue
        xd, yd = weekly_sample(series)
        fig.add_trace(go.Scatter(
            x=xd, y=yd,
            mode="lines",
            name=f"{name} (${val:,.0f})" if val else name,
            line=dict(color=colors[i % len(colors)], width=1.5),
            visible="legendonly" if val and val < bh_val * 0.9 else True,
        ))

    fig.update_layout(
        title="Strategy Comparison: Can Macro Forecasts Beat Buy-and-Hold?",
        xaxis_title="Date", yaxis_title="Portfolio Value ($)",
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, font=dict(size=10)),
        template="plotly_white",
        height=700,
    )
    out_html = WORK_DIR / "strategy_analysis.html"
    fig.write_html(str(out_html))
    print(f"\nChart saved: {out_html}")


if __name__ == "__main__":
    main()
