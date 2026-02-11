#!/usr/bin/env python3
"""
QuantPedia ETF Asset Momentum Strategy Simulation

Strategy:
- Long: Top 4 ETFs by avg(3,6,9,12-month momentum), equal weight
- Short: Bottom 1 ETF at 30% weight, only when 20-day corr > 250-day corr
- Rebalance monthly
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
import yfinance as yf

OUT_DIR = Path(__file__).resolve().parent.parent / "result" / "momentum-lab"

# Default 13 ETFs from QuantPedia research
DEFAULT_ETFS = [
    "SPY", "IWM", "EFA", "EEM", "IYR", "QQQ",  # stock
    "LQD", "IEF", "TIP",                        # bond
    "GLD", "USO", "DBC",                        # commodity
    "FXE",                                     # currency
]


@dataclass
class Config:
    """Configurable parameters for optimization and variant runs."""

    # ETF selection & output
    etfs: list[str] = field(default_factory=lambda: list(DEFAULT_ETFS))
    group_name: str = "from-research"

    # Strategy rules
    n_long: int = 4
    n_short: int = 1
    long_weight: float = 1.0
    short_weight: float = 0.30
    corr_threshold: float = 1.0  # activate short when 20d_corr/250d_corr > this

    # Momentum lookback (days): 3, 6, 9, 12 months
    mom_periods_days: tuple[int, ...] = (63, 126, 189, 252)

    # Correlation filter
    corr_short_days: int = 20
    corr_long_days: int = 250

    # Cost & data
    spread_pct: float = 0.15
    lookback_years: int = 20

    def result_dir(self) -> Path:
        return OUT_DIR / self.group_name


def default_config() -> Config:
    """Default config (QuantPedia research params)."""
    return Config()


# Backward-compat
ETFS = DEFAULT_ETFS
ETF_GROUP_NAME = "from-research"
MOM_PERIODS_DAYS = (63, 126, 189, 252)
CORR_SHORT_DAYS = 20
CORR_LONG_DAYS = 250
N_LONG = 4
N_SHORT = 1
SHORT_WEIGHT = 0.30
LONG_WEIGHT = 1.0
LOOKBACK_YEARS = 20
SPREAD_PCT = 0.15


class SimResult(NamedTuple):
    eq_mom_0: pd.Series
    eq_mom_015: pd.Series
    eq_bh: pd.Series
    out_df: pd.DataFrame
    trades_log: list[dict]
    trade_log: list[dict]
    trades_summary: list[dict]
    holdings_history: list[dict]
    prices: pd.DataFrame
    first_valid: pd.Timestamp | None
    spread: float
    spread_label: str
    metrics: dict
    config: Config

    def to_summary_dict(self) -> dict:
        """JSON-serializable summary for caller. Includes momentum + benchmark."""
        def _safe(v):
            if v is None or isinstance(v, (int, str, bool)):
                return v
            if isinstance(v, float):
                return float(v) if np.isfinite(v) else None
            return v

        m0 = self.metrics.get("mom_0", {})
        m15 = self.metrics.get("mom_015", {})
        bh = self.metrics.get("bh", {})

        return {
            "config": {
                "group_name": self.config.group_name,
                "etfs": self.config.etfs,
                "n_long": self.config.n_long,
                "n_short": self.config.n_short,
                "spread_pct": self.config.spread_pct,
            },
            "momentum_spread0": {k: _safe(v) for k, v in m0.items()},
            "momentum_spread": {k: _safe(v) for k, v in m15.items()},
            "benchmark": {k: _safe(v) for k, v in bh.items()},
            "data_range": {
                "start": str(self.prices.index[0].date()) if len(self.prices) else None,
                "end": str(self.prices.index[-1].date()) if len(self.prices) else None,
                "days": len(self.prices),
            },
        }

    def to_summary_json(self, indent: int = 2) -> str:
        """Return JSON string summary for caller."""
        return json.dumps(self.to_summary_dict(), indent=indent, ensure_ascii=False)


def fetch_prices(tickers: list[str], years: int) -> pd.DataFrame:
    """Fetch adjusted close prices for tickers."""
    days = years * 365 + 60
    end = pd.Timestamp.now().normalize()
    start = end - pd.Timedelta(days=days)
    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False, threads=True)
    if len(tickers) == 1:
        df = data[["Close"]].rename(columns={"Close": tickers[0]})
    elif isinstance(data.columns, pd.MultiIndex):
        df = data.xs("Close", axis=1, level=0).copy()
    else:
        df = data[["Close"]].copy() if "Close" in data.columns else data.copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df.sort_index().dropna(how="all")
    return df


def momentum_rank(prices: pd.DataFrame, date: pd.Timestamp, periods: tuple[int, ...]) -> pd.Series:
    """Rank ETFs by average momentum over periods."""
    idx = prices.index.get_indexer([date], method="ffill")[0]
    if idx < max(periods) + 5:
        return pd.Series(dtype=float)
    moms = []
    for p in periods:
        if idx - p - 1 < 0:
            continue
        p0 = prices.iloc[idx - p - 1]
        p1 = prices.iloc[idx - 1]
        ret = (p1 / p0 - 1.0)
        moms.append(ret)
    if not moms:
        return pd.Series(dtype=float)
    avg_mom = pd.concat(moms, axis=1).mean(axis=1)
    return avg_mom


def avg_correlation_ratio(
    returns: pd.DataFrame,
    date: pd.Timestamp,
    corr_short_days: int = 20,
    corr_long_days: int = 250,
) -> float | None:
    """Ratio of avg short-term to long-term correlation."""
    idx = returns.index.get_indexer([date], method="ffill")[0]
    if idx < corr_long_days + 5:
        return None
    r = returns.iloc[:idx]
    if len(r) < corr_long_days:
        return None
    r_short = r.tail(corr_short_days)
    r_long = r.tail(corr_long_days)
    corr_short = r_short.corr().values
    corr_long = r_long.corr().values
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
    config: Config,
    spread_pct: float | None = None,
    trades_log: list[dict] | None = None,
    trade_log: list[dict] | None = None,
    trades_summary: list[dict] | None = None,
    holdings_history: list[dict] | None = None,
) -> pd.Series:
    """Run QuantPedia long-short strategy. Returns equity curve."""
    spread = config.spread_pct if spread_pct is None else spread_pct
    mom_periods = config.mom_periods_days
    corr_short = config.corr_short_days
    corr_long = config.corr_long_days
    n_long = config.n_long
    n_short = config.n_short
    long_w = config.long_weight
    short_w = config.short_weight
    corr_thresh = config.corr_threshold

    dates = prices.index
    start_idx = max(mom_periods) + corr_long + 10
    if len(dates) <= start_idx:
        return pd.Series(dtype=float)

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
    rebal_dates = [d for d in rebal_dates if d >= dates[start_idx]]

    if not rebal_dates:
        return pd.Series(dtype=float)

    equity = pd.Series(index=dates, dtype=float)
    first_rebal = rebal_dates[0]
    idx_first = dates.get_indexer([first_rebal], method="ffill")[0]
    equity.iloc[:idx_first] = np.nan
    equity.iloc[idx_first] = 1.0

    long_tickers_prev: list[str] = []
    short_ticker_prev: str | None = None
    entry_tracker: dict[str, tuple[pd.Timestamp, float, str]] = {}
    periods = list(zip(rebal_dates[:-1], rebal_dates[1:])) + [(rebal_dates[-1], dates[-1])]

    for d_prev, d_curr in periods:
        idx_prev = dates.get_indexer([d_prev], method="ffill")[0]
        idx_curr = dates.get_indexer([d_curr], method="ffill")[0]
        if idx_curr <= idx_prev:
            continue

        mom = momentum_rank(prices, d_prev, mom_periods)
        valid = mom.dropna()
        long_tickers = list(valid.nlargest(n_long).index) if len(valid) >= n_long else list(valid.index)
        corr_ratio = avg_correlation_ratio(returns, d_prev, corr_short, corr_long)
        short_ticker = None
        if n_short > 0 and corr_ratio is not None and corr_ratio > corr_thresh and len(valid) >= n_short:
            short_ticker = valid.nsmallest(n_short).index[0]

        prev_longs = set(long_tickers_prev)
        prev_shorts = {short_ticker_prev} if short_ticker_prev else set()
        new_longs = set(long_tickers)
        new_shorts = {short_ticker} if short_ticker else set()
        exits = list((prev_longs - new_longs) | (prev_shorts - new_shorts))
        entries = list((new_longs - prev_longs) | (new_shorts - prev_shorts))

        exit_price = prices.loc[d_prev] if d_prev in prices.index else None
        sell_pnl_parts: list[str] = []
        exits_detail: list[dict] = []
        for t in exits:
            if t in entry_tracker and exit_price is not None and t in exit_price and pd.notna(exit_price[t]):
                entry_date, entry_price, side = entry_tracker[t]
                if entry_price and entry_price > 0:
                    if side == "LONG":
                        pnl = (exit_price[t] / entry_price - 1.0) * 100
                    else:
                        pnl = (entry_price / exit_price[t] - 1.0) * 100
                    win = "✓" if pnl > 0 else "✗"
                    sell_pnl_parts.append(f"{t}:{win}{pnl:.1f}%")
                    exits_detail.append({
                        "ticker": t,
                        "buy_date": entry_date,
                        "buy_price": entry_price,
                        "sell_date": d_prev,
                        "sell_price": float(exit_price[t]),
                        "pnl_pct": pnl,
                    })

        if trades_log is not None:
            w_long = (long_w / len(long_tickers)) * 100 if long_tickers else 0
            for t in long_tickers:
                trades_log.append({"date": d_prev, "ticker": t, "side": "LONG", "weight_pct": w_long})
            if short_ticker:
                trades_log.append({"date": d_prev, "ticker": short_ticker, "side": "SHORT", "weight_pct": short_w * 100})

        if trade_log is not None:
            w_long = (long_w / len(long_tickers)) * 100 if long_tickers else 0
            for ed in exits_detail:
                t = ed["ticker"]
                _, _, side = entry_tracker.get(t, (None, None, "LONG"))
                w = (short_w * 100) if side == "SHORT" else w_long
                entry_date = ed.get("buy_date")
                trade_log.append({
                    "date": d_prev, "ticker": t, "action": "SELL", "side": side,
                    "weight_pct": w, "pnl_pct": round(ed["pnl_pct"], 2),
                    "entry_date": pd.Timestamp(entry_date).strftime("%Y-%m-%d") if entry_date else "",
                })
            for t in entries:
                side = "SHORT" if t in new_shorts else "LONG"
                w = (short_w * 100) if t in new_shorts else w_long
                trade_log.append({
                    "date": d_prev, "ticker": t, "action": "BUY", "side": side,
                    "weight_pct": w, "pnl_pct": "", "entry_date": "",
                })

        if holdings_history is not None:
            holdings_history.append({
                "date": d_prev,
                "longs": list(new_longs),
                "short": short_ticker,
                "entries": list(entries),
                "exits": list(exits),
                "exits_detail": exits_detail,
            })

        if trades_summary is not None and exit_price is not None:
            buy_syms = ",".join(sorted(new_longs))
            if new_shorts:
                buy_syms += f" | short:{','.join(new_shorts)}"
            sell_syms = ",".join(sorted(exits)) if exits else ""
            sell_pnl_str = " ".join(sell_pnl_parts) if sell_pnl_parts else ""
            trades_summary.append({
                "date": d_prev, "buy": buy_syms or "-",
                "sell": sell_syms or "-", "sell_pnl_pct": sell_pnl_str or "-",
            })

        for t in exits:
            entry_tracker.pop(t, None)
        if exit_price is not None:
            for t in entries:
                if t in exit_price.index and pd.notna(exit_price[t]) and exit_price[t] > 0:
                    side = "SHORT" if t in new_shorts else "LONG"
                    entry_tracker[t] = (d_prev, float(exit_price[t]), side)

        if spread > 0:
            w_long = long_w / len(long_tickers) if long_tickers else 0
            old_weights = {t: long_w / len(long_tickers_prev) for t in long_tickers_prev} if long_tickers_prev else {}
            if short_ticker_prev:
                old_weights[short_ticker_prev] = old_weights.get(short_ticker_prev, 0) + short_w
            new_weights = {t: w_long for t in long_tickers}
            if short_ticker:
                new_weights[short_ticker] = new_weights.get(short_ticker, 0) + short_w
            all_tickers = set(old_weights.keys()) | set(new_weights.keys())
            turnover = sum(abs(new_weights.get(t, 0) - old_weights.get(t, 0)) for t in all_tickers)
            prev_eq = equity.iloc[idx_prev]
            if pd.notna(prev_eq) and prev_eq > 0 and turnover > 0:
                equity.iloc[idx_prev] = prev_eq * (1.0 - spread / 100.0 * turnover)

        long_tickers_prev = long_tickers
        short_ticker_prev = short_ticker

        for j in range(idx_prev + 1, min(idx_curr + 1, len(dates))):
            d = dates[j]
            ret = returns.loc[d]
            port_ret = 0.0
            if long_tickers:
                w_long = long_w / len(long_tickers)
                for t in long_tickers:
                    if t in ret.index and pd.notna(ret[t]):
                        port_ret += w_long * ret[t]
            if short_ticker and short_ticker in ret.index and pd.notna(ret[short_ticker]):
                port_ret -= short_w * ret[short_ticker]
            prev_eq = equity.iloc[j - 1]
            if pd.notna(prev_eq) and prev_eq > 0:
                equity.iloc[j] = prev_eq * (1.0 + port_ret)
            else:
                equity.iloc[j] = np.nan

    return equity.ffill()


def run_buy_hold(prices: pd.DataFrame, returns: pd.DataFrame, start_date: pd.Timestamp | None = None) -> pd.Series:
    """Equal-weight buy-hold all ETFs."""
    valid_cols = [c for c in prices.columns if prices[c].notna().any()]
    if not valid_cols:
        return pd.Series(dtype=float)
    if start_date is not None:
        idx = prices.index.get_indexer([start_date], method="ffill")[0]
    else:
        idx = 0
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


def run_simulation(
    config: Config | None = None,
    *,
    spread: float | None = None,
    show_trades: bool = False,
) -> SimResult:
    """Run full simulation. Returns SimResult."""
    cfg = config or default_config()
    if spread is not None:
        cfg = Config(**{**cfg.__dict__, "spread_pct": spread})

    trades_log: list[dict] = []
    trade_log: list[dict] = []
    trades_summary: list[dict] = []
    holdings_history: list[dict] = []

    prices = fetch_prices(cfg.etfs, cfg.lookback_years)
    if prices.empty or len(prices) < 300:
        raise ValueError("Insufficient price data")
    prices = prices.dropna(how="all").ffill().bfill()
    returns = prices.pct_change()
    valid = returns.dropna(how="all").first_valid_index()
    if valid is None:
        raise ValueError("No valid returns")

    eq_mom_0 = run_momentum_strategy(
        prices, returns, cfg, spread_pct=0.0,
        trades_log=trades_log,
        trade_log=trade_log,
        trades_summary=trades_summary,
        holdings_history=holdings_history,
    )
    eq_mom_015 = run_momentum_strategy(
        prices, returns, cfg,
        trades_log=[], trade_log=[], trades_summary=[], holdings_history=[],
    )
    first_valid = eq_mom_0.dropna().index[0] if eq_mom_0.notna().any() else None
    eq_bh = run_buy_hold(prices, returns, start_date=first_valid)

    common = eq_mom_0.dropna().index.union(eq_mom_015.dropna().index).union(eq_bh.dropna().index)
    common = common.sort_values()
    eq_mom_0 = eq_mom_0.reindex(common).ffill()
    eq_mom_015 = eq_mom_015.reindex(common).ffill()
    eq_bh = eq_bh.reindex(common).ffill()

    spread_label = f"momentum_spread{str(cfg.spread_pct).replace('.', '')}"
    out_df = pd.DataFrame({
        "momentum_spread0": eq_mom_0,
        spread_label: eq_mom_015,
        "buy_hold": eq_bh,
    })

    m_mom_0 = compute_metrics(eq_mom_0)
    m_mom_015 = compute_metrics(eq_mom_015)
    m_bh = compute_metrics(eq_bh)
    metrics = {"mom_0": m_mom_0, "mom_015": m_mom_015, "bh": m_bh}

    return SimResult(
        eq_mom_0=eq_mom_0,
        eq_mom_015=eq_mom_015,
        eq_bh=eq_bh,
        out_df=out_df,
        trades_log=trades_log,
        trade_log=trade_log,
        trades_summary=trades_summary or [],
        holdings_history=holdings_history,
        prices=prices,
        first_valid=first_valid,
        spread=cfg.spread_pct,
        spread_label=spread_label,
        metrics=metrics,
        config=cfg,
    )
