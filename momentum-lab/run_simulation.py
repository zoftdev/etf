#!/usr/bin/env python3
"""
QuantPedia ETF Asset Momentum Strategy Simulation

Ref: https://quantpedia.com/refining-etf-asset-momentum-strategy/

Strategy:
- Long: Top 4 ETFs by avg(3,6,9,12-month momentum), equal weight
- Short: Bottom 1 ETF at 30% weight, only when 20-day corr > 250-day corr (correlation filter)
- Rebalance monthly

Benchmark: Equal-weight buy-hold all 13 ETFs

13 ETFs (same as research):
  Stock: SPY, IWM, EFA, EEM, IYR, QQQ
  Bond: LQD, IEF, TIP
  Commodity: GLD, USO, DBC
  Currency: FXE

Usage:
  cd ~/clawd/workspace/etf
  uv run python momentum-lab/run_simulation.py [--spread 0.15]
  # spread: transaction cost % per rebalance (default 0.15)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

# 13 ETFs from QuantPedia research
ETFS = [
    "SPY", "IWM", "EFA", "EEM", "IYR", "QQQ",  # stock
    "LQD", "IEF", "TIP",                        # bond
    "GLD", "USO", "DBC",                       # commodity
    "FXE",                                     # currency
]

# Strategy params (from research)
MOM_PERIODS_DAYS = (63, 126, 189, 252)  # 3, 6, 9, 12 months
CORR_SHORT_DAYS = 20
CORR_LONG_DAYS = 250
N_LONG = 4
N_SHORT = 1
SHORT_WEIGHT = 0.30  # 30% additional short hedge (when corr filter active)
LONG_WEIGHT = 1.0    # 100% in longs (4 × 25% each)

# result/ at etf project root (../ from momentum-lab)
OUT_DIR = Path(__file__).resolve().parent.parent / "result"
LOOKBACK_YEARS = 20

# Transaction cost: spread per rebalance (round-trip, as decimal e.g. 0.0015 = 0.15%)
SPREAD_PCT = 0.15  # default 0.15%


def fetch_prices(tickers: list[str], years: int) -> pd.DataFrame:
    """Fetch adjusted close prices for tickers. Returns DataFrame index=date, columns=tickers."""
    days = years * 365 + 60
    end = pd.Timestamp.now().normalize()
    start = end - pd.Timedelta(days=days)
    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False, threads=True)
    if len(tickers) == 1:
        df = data[["Close"]].rename(columns={"Close": tickers[0]})
    elif isinstance(data.columns, pd.MultiIndex):
        # yfinance: level 0 = Price (Close, Open, ...), level 1 = Ticker
        df = data.xs("Close", axis=1, level=0).copy()
    else:
        df = data[["Close"]].copy() if "Close" in data.columns else data.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df.sort_index().dropna(how="all")
    return df


def momentum_rank(prices: pd.DataFrame, date: pd.Timestamp, periods: tuple[int, ...]) -> pd.Series:
    """Rank ETFs by average momentum over periods (higher = winner). Uses price at date (exclusive of day)."""
    idx = prices.index.get_indexer([date], method="ffill")[0]
    if idx < max(periods) + 5:
        return pd.Series(dtype=float)

    moms = []
    for p in periods:
        if idx - p - 1 < 0:
            continue
        p0 = prices.iloc[idx - p - 1]  # start of period (exclude today)
        p1 = prices.iloc[idx - 1]       # end of period (day before today)
        ret = (p1 / p0 - 1.0)
        moms.append(ret)
    if not moms:
        return pd.Series(dtype=float)
    avg_mom = pd.concat(moms, axis=1).mean(axis=1)
    return avg_mom


def avg_correlation_ratio(returns: pd.DataFrame, date: pd.Timestamp) -> float | None:
    """
    Ratio of avg short-term (20d) correlation to avg long-term (250d) correlation.
    Returns None if insufficient data.
    """
    idx = returns.index.get_indexer([date], method="ffill")[0]
    if idx < CORR_LONG_DAYS + 5:
        return None
    # Use returns up to (and excluding) date
    r = returns.iloc[:idx]
    if len(r) < CORR_LONG_DAYS:
        return None
    r_short = r.tail(CORR_SHORT_DAYS)
    r_long = r.tail(CORR_LONG_DAYS)
    corr_short = r_short.corr().values
    corr_long = r_long.corr().values
    # Average correlation (excluding diagonal)
    n = corr_short.shape[0]
    mask = ~np.eye(n, dtype=bool)
    avg_short = np.nanmean(corr_short[mask])
    avg_long = np.nanmean(corr_long[mask])
    if np.isnan(avg_long) or avg_long <= 0:
        return None
    return avg_short / avg_long


def last_trading_day_of_month(prices: pd.DataFrame, year: int, month: int) -> pd.Timestamp | None:
    """Last trading day in (year, month)."""
    mask = (prices.index.year == year) & (prices.index.month == month)
    if not mask.any():
        return None
    return prices.index[mask][-1]


def run_momentum_strategy(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    spread_pct: float = 0.0,
    trades_log: list[dict] | None = None,
) -> pd.Series:
    """Run QuantPedia long-short selective hedge strategy. Returns equity curve (index=date).
    If trades_log is provided, append rebalance records: {date, ticker, side, weight_pct}."""
    dates = prices.index
    start_idx = max(MOM_PERIODS_DAYS) + CORR_LONG_DAYS + 10
    if len(dates) <= start_idx:
        return pd.Series(dtype=float)

    # Build rebalance dates (monthly, last trading day)
    seen = set()
    rebal_dates = []
    for d in dates:
        key = (d.year, d.month)
        if key in seen:
            continue
        last = last_trading_day_of_month(prices, d.year, d.month)
        if last is not None and last <= d:
            rebal_dates.append(last)
            seen.add(key)
    rebal_dates = sorted(set(rebal_dates))
    # Filter to dates we have data for
    rebal_dates = [d for d in rebal_dates if d >= dates[start_idx]]

    if not rebal_dates:
        return pd.Series(dtype=float)

    equity = pd.Series(index=dates, dtype=float)
    first_rebal = rebal_dates[0]
    idx_first = dates.get_indexer([first_rebal], method="ffill")[0]
    equity.iloc[:idx_first] = np.nan
    equity.iloc[idx_first] = 1.0

    # Track previous holdings for turnover-based spread (only pay on changed positions)
    long_tickers_prev: list[str] = []
    short_ticker_prev: str | None = None

    # Process each period between rebalance dates (incl. last period to end)
    periods = list(zip(rebal_dates[:-1], rebal_dates[1:])) + [(rebal_dates[-1], dates[-1])]

    for d_prev, d_curr in periods:
        idx_prev = dates.get_indexer([d_prev], method="ffill")[0]
        idx_curr = dates.get_indexer([d_curr], method="ffill")[0]
        if idx_curr <= idx_prev:
            continue

        # Rebalance at d_prev (decide holdings for period d_prev -> d_curr)
        mom = momentum_rank(prices, d_prev, MOM_PERIODS_DAYS)
        valid = mom.dropna()
        long_tickers = list(valid.nlargest(N_LONG).index) if len(valid) >= N_LONG else list(valid.index)
        corr_ratio = avg_correlation_ratio(returns, d_prev)
        short_ticker = None
        if corr_ratio is not None and corr_ratio > 1.0 and len(valid) >= N_SHORT:
            short_ticker = valid.nsmallest(N_SHORT).index[0]

        # Log buy/sell
        if trades_log is not None:
            w_long = (LONG_WEIGHT / len(long_tickers)) * 100 if long_tickers else 0
            for t in long_tickers:
                trades_log.append({"date": d_prev, "ticker": t, "side": "LONG", "weight_pct": w_long})
            if short_ticker:
                trades_log.append({"date": d_prev, "ticker": short_ticker, "side": "SHORT", "weight_pct": SHORT_WEIGHT * 100})

        # Spread cost: only on turnover (changed positions). Same ETF = no trade = no cost.
        if spread_pct > 0:
            w_long = LONG_WEIGHT / len(long_tickers) if long_tickers else 0
            old_weights = {t: LONG_WEIGHT / len(long_tickers_prev) for t in long_tickers_prev} if long_tickers_prev else {}
            if short_ticker_prev:
                old_weights[short_ticker_prev] = old_weights.get(short_ticker_prev, 0) + SHORT_WEIGHT
            new_weights = {t: w_long for t in long_tickers}
            if short_ticker:
                new_weights[short_ticker] = new_weights.get(short_ticker, 0) + SHORT_WEIGHT
            all_tickers = set(old_weights.keys()) | set(new_weights.keys())
            turnover = sum(abs(new_weights.get(t, 0) - old_weights.get(t, 0)) for t in all_tickers)
            prev_eq = equity.iloc[idx_prev]
            if pd.notna(prev_eq) and prev_eq > 0 and turnover > 0:
                equity.iloc[idx_prev] = prev_eq * (1.0 - spread_pct / 100.0 * turnover)

        long_tickers_prev = long_tickers
        short_ticker_prev = short_ticker

        # Daily returns for period
        for j in range(idx_prev + 1, min(idx_curr + 1, len(dates))):
            d = dates[j]
            ret = returns.loc[d]
            port_ret = 0.0
            if long_tickers:
                w_long = LONG_WEIGHT / len(long_tickers)
                for t in long_tickers:
                    if t in ret.index and pd.notna(ret[t]):
                        port_ret += w_long * ret[t]
            if short_ticker and short_ticker in ret.index and pd.notna(ret[short_ticker]):
                port_ret -= SHORT_WEIGHT * ret[short_ticker]
            prev_eq = equity.iloc[j - 1]
            if pd.notna(prev_eq) and prev_eq > 0:
                equity.iloc[j] = prev_eq * (1.0 + port_ret)
            else:
                equity.iloc[j] = np.nan

    equity = equity.ffill()
    return equity


def run_buy_hold(prices: pd.DataFrame, returns: pd.DataFrame, start_date: pd.Timestamp | None = None) -> pd.Series:
    """True buy-hold: equal initial investment in all ETFs, let positions drift."""
    valid_cols = [c for c in prices.columns if prices[c].notna().any()]
    if not valid_cols:
        return pd.Series(dtype=float)
    if start_date is not None:
        idx = prices.index.get_indexer([start_date], method="ffill")[0]
    else:
        idx = 0
    # Normalize each ETF price to 1.0 at start → portfolio = mean of individual growth
    start_prices = prices[valid_cols].iloc[idx]
    equity = (prices[valid_cols] / start_prices).mean(axis=1)
    equity.iloc[:idx] = np.nan
    return equity


def compute_metrics(equity: pd.Series) -> dict:
    """CAGR, Sharpe, MaxDD from equity curve."""
    eq = equity.dropna()
    eq = eq[eq > 0]
    if len(eq) < 2:
        return {}
    start, end = eq.index[0], eq.index[-1]
    years = (end - start).days / 365.25
    if years <= 0:
        return {}
    total_ret = eq.iloc[-1] / eq.iloc[0] - 1.0
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / years) - 1.0
    daily = eq.pct_change().dropna()
    if len(daily) > 5 and daily.std() > 0:
        sharpe = (daily.mean() * 252) / (daily.std() * np.sqrt(252))
    else:
        sharpe = np.nan
    peak = eq.cummax()
    mdd = (eq / peak - 1.0).min()
    return {
        "cagr_pct": cagr * 100,
        "sharpe": float(sharpe) if np.isfinite(sharpe) else np.nan,
        "max_drawdown_pct": mdd * 100,
        "total_return_pct": total_ret * 100,
        "years": years,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="QuantPedia ETF Momentum Strategy Simulation")
    parser.add_argument("--spread", type=float, default=SPREAD_PCT,
                        help="Transaction cost %% per rebalance (default: %(default)s)")
    args = parser.parse_args()
    spread = args.spread

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    print("Fetching 13 ETFs from Yahoo Finance...")
    prices = fetch_prices(ETFS, LOOKBACK_YEARS)
    if prices.empty or len(prices) < 300:
        print("Insufficient price data. Abort.")
        return

    # Align: common dates, forward-fill then drop leading NaN
    prices = prices.dropna(how="all").ffill().bfill()
    returns = prices.pct_change()
    valid = returns.dropna(how="all").first_valid_index()
    if valid is None:
        print("No valid returns. Abort.")
        return

    print(f"Data range: {prices.index[0].date()} to {prices.index[-1].date()} ({len(prices)} days)")

    # Run all 3: momentum spread 0, momentum spread 0.15, buy-hold
    trades_log: list[dict] = []
    print("Running momentum (spread=0%)...")
    eq_mom_0 = run_momentum_strategy(prices, returns, spread_pct=0.0, trades_log=trades_log)
    print(f"Running momentum (spread={spread}%)...")
    eq_mom_015 = run_momentum_strategy(prices, returns, spread_pct=spread)
    first_valid = eq_mom_0.dropna().index[0] if eq_mom_0.notna().any() else None
    print("Running buy-hold benchmark...")
    eq_bh = run_buy_hold(prices, returns, start_date=first_valid)

    # Align end dates
    common = eq_mom_0.dropna().index.union(eq_mom_015.dropna().index).union(eq_bh.dropna().index)
    common = common.sort_values()
    eq_mom_0 = eq_mom_0.reindex(common).ffill()
    eq_mom_015 = eq_mom_015.reindex(common).ffill()
    eq_bh = eq_bh.reindex(common).ffill()

    m_mom_0 = compute_metrics(eq_mom_0)
    m_mom_015 = compute_metrics(eq_mom_015)
    m_bh = compute_metrics(eq_bh)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\nMomentum (spread=0%):")
    print(f"  CAGR:       {m_mom_0.get('cagr_pct', 0):.2f}%")
    print(f"  Sharpe:     {m_mom_0.get('sharpe', 0):.2f}")
    print(f"  Max DD:     {m_mom_0.get('max_drawdown_pct', 0):.2f}%")
    print(f"\nMomentum (spread={spread}%):")
    print(f"  CAGR:       {m_mom_015.get('cagr_pct', 0):.2f}%")
    print(f"  Sharpe:     {m_mom_015.get('sharpe', 0):.2f}")
    print(f"  Max DD:     {m_mom_015.get('max_drawdown_pct', 0):.2f}%")
    print(f"\nBuy-Hold (Equal Weight 13 ETFs):")
    print(f"  CAGR:       {m_bh.get('cagr_pct', 0):.2f}%")
    print(f"  Sharpe:     {m_bh.get('sharpe', 0):.2f}")
    print(f"  Max DD:     {m_bh.get('max_drawdown_pct', 0):.2f}%")

    # Save equity curves
    spread_label = f"momentum_spread{str(spread).replace('.', '')}"
    out_df = pd.DataFrame({
        "momentum_spread0": eq_mom_0,
        spread_label: eq_mom_015,
        "buy_hold": eq_bh,
    })
    out_csv = OUT_DIR / "equity_curves.csv"
    out_df.to_csv(out_csv)
    print(f"\nSaved {out_csv}")

    # Save metrics
    metrics_df = pd.DataFrame([
        {"strategy": "momentum_spread0", **m_mom_0},
        {"strategy": spread_label, **m_mom_015},
        {"strategy": "buy_hold", **m_bh},
    ])
    metrics_csv = OUT_DIR / "metrics.csv"
    metrics_df.to_csv(metrics_csv, index=False)
    print(f"Saved {metrics_csv}")

    # Save buy/sell log
    trades_df = pd.DataFrame(trades_log)
    if not trades_df.empty:
        trades_df["date"] = pd.to_datetime(trades_df["date"]).dt.strftime("%Y-%m-%d")
    trades_csv = OUT_DIR / "buysell_log.csv"
    trades_df.to_csv(trades_csv, index=False)
    print(f"Saved {trades_csv} ({len(trades_df)} rows)")

    # Plotly chart
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("Plotly not installed; skip HTML.")
        return

    fig = go.Figure()
    dates_str = out_df.index.astype(str).tolist()
    fig.add_trace(go.Scatter(
        x=dates_str,
        y=out_df["momentum_spread0"].tolist(),
        name="Momentum (spread=0%)",
        line=dict(color="#1f77b4", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=dates_str,
        y=out_df[spread_label].tolist(),
        name=f"Momentum (spread={spread}%)",
        line=dict(color="#2ca02c", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=dates_str,
        y=out_df["buy_hold"].tolist(),
        name="Buy-Hold (Equal Weight)",
        line=dict(color="#ff7f0e", width=2),
    ))
    fig.update_layout(
        title=f"QuantPedia ETF Momentum vs Buy-Hold (13 ETFs) — spread 0% vs {spread}%",
        xaxis_title="Date",
        yaxis_title="Equity (start=1)",
        hovermode="x unified",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        template="plotly_white",
        height=500,
    )
    html_path = OUT_DIR / "momentum_vs_buyhold.html"
    fig.write_html(str(html_path))
    print(f"Saved {html_path}")


if __name__ == "__main__":
    main()
