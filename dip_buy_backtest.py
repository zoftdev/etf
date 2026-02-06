"""
Backtest Dip-Buy strategy for ETFs from etf.yaml.
No look-ahead: on signal date only data up to that date is used.
Defaults loaded from dip_default.yaml when present.
"""
from __future__ import annotations

import itertools
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import pandas as pd
import numpy as np
import yaml

from etf_data_fetcher import ETFDataFetcher

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "dip_default.yaml"
SIM_CONFIG_PATH = Path(__file__).resolve().parent / "dip-sim.yaml"


@dataclass
class DipBuyParams:
    trend_days: int = 200
    dip_days: int = 7
    slope_lookback_days: int = 20
    use_slope_filter: bool = True
    min_dip_pct: float = 0.0


@dataclass
class ExitRules:
    hold_days: int = 15
    take_profit_pct: Optional[float] = None  # e.g. 5.0
    stop_loss_pct: Optional[float] = None    # e.g. -3.0
    spread_pct: float = 0.0                   # round-trip cost: sell-buy diff, e.g. 0.15 = 0.15%


def _parse_start_date(value: Optional[str]) -> Optional[pd.Timestamp]:
    """Parse sim_start_date string (YYYY-MM-DD) to timezone-aware timestamp for comparison with df.index."""
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts
    except Exception:
        return None


def load_dip_defaults(config_path: Optional[Path] = None) -> Tuple[DipBuyParams, ExitRules, Optional[pd.Timestamp]]:
    """Load default DipBuyParams, ExitRules and optional sim_start_date from dip_default.yaml."""
    path = config_path or DEFAULT_CONFIG_PATH
    dip_buy = DipBuyParams()
    exit_rules = ExitRules()
    sim_start_date: Optional[pd.Timestamp] = None
    if not path.exists():
        return dip_buy, exit_rules, sim_start_date
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return dip_buy, exit_rules, sim_start_date
    sim_start_date = _parse_start_date(data.get("sim_start_date"))
    db = data.get("dip_buy") or {}
    if isinstance(db, dict):
        dip_buy = DipBuyParams(
            trend_days=int(db.get("trend_days", dip_buy.trend_days)),
            dip_days=int(db.get("dip_days", dip_buy.dip_days)),
            slope_lookback_days=int(db.get("slope_lookback_days", dip_buy.slope_lookback_days)),
            use_slope_filter=bool(db.get("use_slope_filter", dip_buy.use_slope_filter)),
            min_dip_pct=float(db.get("min_dip_pct", dip_buy.min_dip_pct)),
        )
    er = data.get("exit_rules") or {}
    if isinstance(er, dict):
        tp = er.get("take_profit_pct")
        sl = er.get("stop_loss_pct")
        exit_rules = ExitRules(
            hold_days=int(er.get("hold_days", exit_rules.hold_days)),
            take_profit_pct=float(tp) if tp is not None else None,
            stop_loss_pct=float(sl) if sl is not None else None,
            spread_pct=float(er.get("spread_pct", exit_rules.spread_pct)),
        )
    return dip_buy, exit_rules, sim_start_date


def load_dip_sim_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load grid lists from dip-sim.yaml. Returns dict with grid_exit, grid_dip, small_grid (or empty)."""
    path = config_path or SIM_CONFIG_PATH
    out: Dict[str, Any] = {"grid_exit": {}, "grid_dip": {}, "small_grid": None}
    if not path.exists():
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return out
    out["grid_exit"] = data.get("grid_exit") or {}
    out["grid_dip"] = data.get("grid_dip") or {}
    out["small_grid"] = data.get("small_grid")
    return out


def _series_up_to(df: pd.DataFrame, end_idx: int) -> pd.Series:
    """Close series up to and including end_idx (iloc)."""
    return df["Close"].iloc[: end_idx + 1]


def is_dip_buy_signal_at_idx(
    df: pd.DataFrame,
    idx: int,
    params: DipBuyParams,
) -> bool:
    """
    Check if at index `idx` (0-based) the dip-buy conditions are met.
    Uses only data from row 0 to idx (inclusive). No look-ahead.
    """
    close = _series_up_to(df, idx)
    t = params.trend_days
    d = params.dip_days
    s = params.slope_lookback_days

    if len(close) < max(t + s + 1, d + 1):
        return False

    sma = close.rolling(window=t).mean()
    sma_today = sma.iloc[-1]
    price_today = close.iloc[-1]

    if pd.isna(sma_today) or sma_today <= 0:
        return False

    trend_vs_sma_pct = (price_today / sma_today - 1.0) * 100.0
    if trend_vs_sma_pct <= 0:
        return False

    if params.use_slope_filter:
        sma_prev = sma.iloc[-1 - s] if (len(sma) >= s + 1) else np.nan
        if pd.isna(sma_prev) or sma_prev <= 0:
            return False
        sma_slope_pct = (sma_today / sma_prev - 1.0) * 100.0
        if sma_slope_pct <= 0:
            return False

    dip_ref = close.iloc[-1 - d]
    if dip_ref is None or pd.isna(dip_ref) or dip_ref <= 0:
        return False
    dip_pct = (price_today / dip_ref - 1.0) * 100.0
    if dip_pct >= 0:
        return False
    if params.min_dip_pct > 0 and dip_pct > -params.min_dip_pct:
        return False

    return True


def run_single_backtest(
    df: pd.DataFrame,
    params: DipBuyParams,
    exit_rules: ExitRules,
    sim_start_date: Optional[Union[pd.Timestamp, str]] = None,
    sim_end_date: Optional[Union[pd.Timestamp, str]] = None,
) -> Tuple[List[Dict[str, Any]], pd.Series]:
    """
    Run backtest on one price frame. No look-ahead.
    - Signal at day idx → enter at Open of day idx+1.
    - Exit: after hold_days, or when take_profit_pct / stop_loss_pct hit (checked at Close).
    - If sim_start_date set: only consider signals on or after that date.
    - If sim_end_date set: only consider new entries on or before that date (exits may occur after).

    Returns:
        trades: list of {entry_date, exit_date, entry_price, exit_price, return_pct, exit_reason}
        equity_curve: series of cumulative return (1.0 at start, then growth per trade)
    """
    if isinstance(sim_start_date, str):
        sim_start_date = _parse_start_date(sim_start_date)
    if isinstance(sim_end_date, str):
        sim_end_date = _parse_start_date(sim_end_date)
    if "Open" not in df.columns:
        df = df.copy()
        df["Open"] = df["Close"]

    close = df["Close"].values
    open_ = df["Open"].values
    dates = df.index
    n = len(df)

    need = max(
        params.trend_days + params.slope_lookback_days + 2,
        params.dip_days + 2,
    )
    if n < need + exit_rules.hold_days + 1:
        return [], pd.Series(dtype=float)

    first_idx = need
    # If sim_start_date is set, start backtest only from that date (still need warmup bars before it)
    if sim_start_date is not None:
        start_ts = pd.Timestamp(sim_start_date)
        # Normalize for comparison: make index and start_ts both naive or both aware
        if hasattr(dates, "tz") and dates.tz is not None:
            if start_ts.tzinfo is None:
                start_ts = start_ts.tz_localize(dates.tz)
        else:
            if start_ts.tzinfo is not None:
                start_ts = start_ts.tz_convert(None)
        mask = dates >= start_ts
        if mask.any():
            first_date_idx = int(np.where(mask)[0][0])
            first_idx = max(need, first_date_idx)

    # When sim_end_date is set, do not open new positions after that date
    end_ts = None
    if sim_end_date is not None:
        end_ts = pd.Timestamp(sim_end_date)
        if hasattr(dates, "tz") and dates.tz is not None and end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize(dates.tz)
        elif (not hasattr(dates, "tz") or dates.tz is None) and end_ts.tzinfo is not None:
            end_ts = end_ts.tz_convert(None)

    trades: List[Dict[str, Any]] = []
    in_position = False
    entry_idx = -1
    entry_price = 0.0

    for idx in range(first_idx, n - 1):
        if in_position:
            hold_elapsed = idx - entry_idx
            exit_price = close[idx]
            hit_tp = (
                exit_rules.take_profit_pct is not None
                and exit_price >= entry_price * (1.0 + exit_rules.take_profit_pct / 100.0)
            )
            hit_sl = (
                exit_rules.stop_loss_pct is not None
                and exit_rules.stop_loss_pct < 0
                and exit_price <= entry_price * (1.0 + exit_rules.stop_loss_pct / 100.0)
            )
            exit_reason = "hold_days"
            if hit_tp:
                exit_reason = "take_profit"
            elif hit_sl:
                exit_reason = "stop_loss"
            elif hold_elapsed >= exit_rules.hold_days:
                exit_reason = "hold_days"

            if exit_reason != "hold_days" or hold_elapsed >= exit_rules.hold_days:
                ret_pct = (exit_price / entry_price - 1.0) * 100.0 - exit_rules.spread_pct
                trades.append({
                    "entry_date": dates[entry_idx],
                    "exit_date": dates[idx],
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "return_pct": float(ret_pct),
                    "exit_reason": exit_reason,
                })
                in_position = False
                continue

        if in_position:
            continue

        # Do not open new position after sim_end_date
        if end_ts is not None and dates[idx] > end_ts:
            continue

        if is_dip_buy_signal_at_idx(df, idx, params):
            entry_price = open_[idx + 1]
            entry_idx = idx + 1
            in_position = True

    if in_position and entry_idx < n:
        exit_idx = min(entry_idx + exit_rules.hold_days, n - 1)
        exit_idx = min(exit_idx, n - 1)
        exit_price = close[exit_idx]
        ret_pct = (exit_price / entry_price - 1.0) * 100.0 - exit_rules.spread_pct
        trades.append({
            "entry_date": dates[entry_idx],
            "exit_date": dates[exit_idx],
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "return_pct": float(ret_pct),
            "exit_reason": "hold_days",
        })

    equity = 1.0
    equity_curve = [1.0]
    eq_dates = [dates[first_idx]]
    for t in trades:
        equity *= 1.0 + t["return_pct"] / 100.0
        equity_curve.append(equity)
        eq_dates.append(t["exit_date"])
    eq_series = pd.Series(equity_curve, index=eq_dates)

    return trades, eq_series


def backtest_metrics(trades: List[Dict], equity_curve: pd.Series) -> Dict[str, float]:
    if not trades:
        return {
            "total_return_pct": 0.0,
            "n_trades": 0,
            "win_rate": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_approx": 0.0,
        }
    returns = [t["return_pct"] for t in trades]
    total_return_pct = (np.prod([1 + r / 100.0 for r in returns]) - 1.0) * 100.0
    wins = sum(1 for r in returns if r > 0)
    run = np.array(returns)
    cum = np.cumprod(1.0 + run / 100.0)
    peak = np.maximum.accumulate(cum)
    dd = (cum / peak - 1.0) * 100.0
    max_dd = float(np.min(dd)) if len(dd) else 0.0
    sharpe_approx = float(np.mean(run) / (np.std(run) + 1e-12) * np.sqrt(252 / 15)) if len(run) > 1 else 0.0
    return {
        "total_return_pct": total_return_pct,
        "n_trades": len(trades),
        "win_rate": wins / len(trades) * 100.0,
        "max_drawdown_pct": max_dd,
        "sharpe_approx": sharpe_approx,
    }


def run_backtest_ticker(
    ticker: str,
    df: pd.DataFrame,
    params: DipBuyParams,
    exit_rules: ExitRules,
    sim_start_date: Optional[Union[pd.Timestamp, str]] = None,
    sim_end_date: Optional[Union[pd.Timestamp, str]] = None,
) -> Dict[str, Any]:
    trades, equity = run_single_backtest(
        df, params, exit_rules,
        sim_start_date=sim_start_date,
        sim_end_date=sim_end_date,
    )
    metrics = backtest_metrics(trades, equity)
    need = max(
        params.trend_days + params.slope_lookback_days + 2,
        params.dip_days + 2,
    )
    # First date when signal can be generated (no look-ahead); respect sim_start_date
    if len(df) <= need:
        backtest_start = None
        backtest_end = None
    else:
        first_idx = need
        if sim_start_date is not None:
            start_ts = _parse_start_date(sim_start_date) if isinstance(sim_start_date, str) else pd.Timestamp(sim_start_date)
            if start_ts is not None:
                dates = df.index
                if hasattr(dates, "tz") and dates.tz is not None and start_ts.tzinfo is None:
                    start_ts = start_ts.tz_localize(dates.tz)
                elif (not hasattr(dates, "tz") or dates.tz is None) and start_ts.tzinfo is not None:
                    start_ts = start_ts.tz_convert(None)
                mask = dates >= start_ts
                if mask.any():
                    first_idx = max(need, int(np.where(mask)[0][0]))
        backtest_start = df.index[first_idx]
        dates = df.index
        last_date = dates[-1]
        if sim_end_date is not None:
            end_ts = _parse_start_date(sim_end_date) if isinstance(sim_end_date, str) else pd.Timestamp(sim_end_date)
            if end_ts is not None:
                if hasattr(dates, "tz") and dates.tz is not None and end_ts.tzinfo is None:
                    end_ts = end_ts.tz_localize(dates.tz)
                elif (not hasattr(dates, "tz") or dates.tz is None) and end_ts.tzinfo is not None:
                    end_ts = end_ts.tz_convert(None)
                mask = dates <= end_ts
                if mask.any():
                    backtest_end = dates[np.where(mask)[0][-1]]
                else:
                    backtest_end = last_date
            else:
                backtest_end = last_date
        else:
            backtest_end = last_date
    return {
        "ticker": ticker,
        "params": params,
        "trades": trades,
        "equity_curve": equity,
        "backtest_start": backtest_start,
        "backtest_end": backtest_end,
        **metrics,
    }


def _ensure_list(val: Any, default: List[Any]) -> List[Any]:
    if val is None:
        return default
    if isinstance(val, list):
        return val
    return default


def small_grid_from_config(sim_config_path: Optional[Path] = None) -> Optional[List[DipBuyParams]]:
    """Build param list from small_grid in dip-sim.yaml. Returns None if missing or invalid."""
    sim = load_dip_sim_config(sim_config_path)
    sg = sim.get("small_grid")
    if not sg or not isinstance(sg, list):
        return None
    out = []
    for item in sg:
        if not isinstance(item, dict):
            continue
        try:
            out.append(DipBuyParams(
                trend_days=int(item.get("trend_days", 200)),
                dip_days=int(item.get("dip_days", 7)),
                slope_lookback_days=int(item.get("slope_lookback_days", 20)),
                use_slope_filter=bool(item.get("use_slope_filter", True)),
                min_dip_pct=float(item.get("min_dip_pct", 0.0)),
            ))
        except (TypeError, ValueError):
            continue
    return out if out else None


def param_grid_reasonable(sim_config_path: Optional[Path] = None) -> List[DipBuyParams]:
    """Reasonable grid for search. Uses grid_dip from dip-sim.yaml when present."""
    sim = load_dip_sim_config(sim_config_path)
    gd = sim.get("grid_dip") or {}
    trend_days_list = _ensure_list(gd.get("trend_days"), [50, 100, 200])
    dip_days_list = _ensure_list(gd.get("dip_days"), [5, 7, 10])
    slope_list = _ensure_list(gd.get("slope_lookback_days"), [10, 20])
    use_slope_list = _ensure_list(gd.get("use_slope_filter"), [True, False])
    min_dip_list = _ensure_list(gd.get("min_dip_pct"), [0.0, 2.0])
    grid = []
    for trend_days in trend_days_list:
        for dip_days in dip_days_list:
            for slope_lookback_days in slope_list:
                for use_slope_filter in use_slope_list:
                    for min_dip_pct in min_dip_list:
                        grid.append(DipBuyParams(
                            trend_days=int(trend_days),
                            dip_days=int(dip_days),
                            slope_lookback_days=int(slope_lookback_days),
                            use_slope_filter=bool(use_slope_filter),
                            min_dip_pct=float(min_dip_pct),
                        ))
    return grid


def exit_rules_grid(spread_pct: float = 0.0, sim_config_path: Optional[Path] = None) -> List[ExitRules]:
    """Grid of exit rules for --grid-exit. Uses grid_exit from dip-sim.yaml when present."""
    sim = load_dip_sim_config(sim_config_path)
    ge = sim.get("grid_exit") or {}
    hold_days_list = _ensure_list(ge.get("hold_days"), [5, 10, 15, 20])
    take_raw = _ensure_list(ge.get("take_profit_pct"), [None, 3.0, 5.0, 8.0, 10.0, 15.0])
    take_profit_list = [None if v is None else float(v) for v in take_raw]
    stop_raw = _ensure_list(ge.get("stop_loss_pct"), [None, -3.0, -5.0])
    stop_loss_list = [None if v is None else float(v) for v in stop_raw]
    grid = []
    for hold_days in hold_days_list:
        for take_profit_pct in take_profit_list:
            for stop_loss_pct in stop_loss_list:
                grid.append(ExitRules(
                    hold_days=int(hold_days),
                    take_profit_pct=take_profit_pct,
                    stop_loss_pct=stop_loss_pct,
                    spread_pct=spread_pct,
                ))
    return grid


def _run_one_dip(
    ticker: str,
    df: pd.DataFrame,
    params: DipBuyParams,
    exit_rules: ExitRules,
    group: str,
    sim_start_date: Optional[Union[pd.Timestamp, str]] = None,
    sim_end_date: Optional[Union[pd.Timestamp, str]] = None,
) -> Dict[str, Any]:
    """Single backtest for grid_search (dip params). Used in parallel."""
    res = run_backtest_ticker(
        ticker, df, params, exit_rules,
        sim_start_date=sim_start_date,
        sim_end_date=sim_end_date,
    )
    res["params_dict"] = {
        "trend_days": params.trend_days,
        "dip_days": params.dip_days,
        "slope_lookback_days": params.slope_lookback_days,
        "use_slope_filter": params.use_slope_filter,
        "min_dip_pct": params.min_dip_pct,
    }
    # In this backtest module, `group` is the raw YAML path key (group_key), e.g. commodity.specific
    res["group_key"] = group
    res["group"] = group
    return res


def grid_search(
    fetcher: ETFDataFetcher,
    tickers: List[str],
    param_list: List[DipBuyParams],
    exit_rules: ExitRules,
    max_trend_days: int = 200,
    max_dip_days: int = 14,
    max_slope_days: int = 30,
    history_calendar_days: Optional[int] = None,
    max_workers: Optional[int] = None,
    sim_start_date: Optional[Union[pd.Timestamp, str]] = None,
    sim_end_date: Optional[Union[pd.Timestamp, str]] = None,
) -> List[Dict[str, Any]]:
    """
    For each ticker, fetch history; for each param set run backtest (in parallel); return list of results.
    If history_calendar_days is set (e.g. 3*365 for 3 years), use that for fetch; else use min needed.
    If sim_start_date is set, backtest only from that date.
    If sim_end_date is set, no new entries after that date (window = start to end).
    """
    if history_calendar_days is not None:
        calendar_days = history_calendar_days
    else:
        need_trading = max(max_trend_days + max_slope_days + 10, max_dip_days + 10)
        calendar_days = fetcher._calendar_days_for_trading_window(need_trading)
    history, errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)

    ticker_infos = {t: (fetcher.get_ticker_info(t) or {}).get("group_key") or (fetcher.get_ticker_info(t) or {}).get("group") or "unknown" for t in tickers}
    tasks: List[Tuple[str, pd.DataFrame, DipBuyParams, str]] = []
    for ticker in tickers:
        if ticker not in history:
            continue
        df = history[ticker]
        if df is None or df.empty or "Close" not in df.columns:
            continue
        df = df.sort_index()
        group = ticker_infos.get(ticker, "unknown")
        for params in param_list:
            if (
                params.trend_days > max_trend_days
                or params.dip_days > max_dip_days
                or params.slope_lookback_days > max_slope_days
            ):
                continue
            tasks.append((ticker, df, params, group))

    workers = max_workers if max_workers is not None else min(32, (os.cpu_count() or 4) * 2)
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(_run_one_dip, t, d, p, exit_rules, g, sim_start_date, sim_end_date): (t, p)
            for t, d, p, g in tasks
        }
        for future in as_completed(future_to_task):
            try:
                results.append(future.result())
            except Exception:
                pass
    return results


def _run_one_exit(
    ticker: str,
    df: pd.DataFrame,
    params: DipBuyParams,
    exit_rules: ExitRules,
    group: str,
    sim_start_date: Optional[Union[pd.Timestamp, str]] = None,
    sim_end_date: Optional[Union[pd.Timestamp, str]] = None,
) -> Dict[str, Any]:
    """Single backtest for grid_search_exit. Used in parallel."""
    res = run_backtest_ticker(
        ticker, df, params, exit_rules,
        sim_start_date=sim_start_date,
        sim_end_date=sim_end_date,
    )
    res["params_dict"] = {
        "trend_days": params.trend_days,
        "dip_days": params.dip_days,
        "slope_lookback_days": params.slope_lookback_days,
        "use_slope_filter": params.use_slope_filter,
        "min_dip_pct": params.min_dip_pct,
    }
    res["exit_dict"] = {
        "exit_hold_days": exit_rules.hold_days,
        "exit_take_profit_pct": exit_rules.take_profit_pct,
        "exit_stop_loss_pct": exit_rules.stop_loss_pct,
    }
    # In this backtest module, `group` is the raw YAML path key (group_key), e.g. commodity.specific
    res["group_key"] = group
    res["group"] = group
    return res


def grid_search_exit(
    fetcher: ETFDataFetcher,
    tickers: List[str],
    params: DipBuyParams,
    exit_rules_list: List[ExitRules],
    max_trend_days: int = 200,
    max_dip_days: int = 14,
    max_slope_days: int = 30,
    history_calendar_days: Optional[int] = None,
    max_workers: Optional[int] = None,
    sim_start_date: Optional[Union[pd.Timestamp, str]] = None,
    sim_end_date: Optional[Union[pd.Timestamp, str]] = None,
) -> List[Dict[str, Any]]:
    """
    For each ticker and each exit_rule, run backtest with single DipBuyParams (in parallel).
    Results include exit_dict (hold_days, take_profit_pct, stop_loss_pct) for summarization.
    If sim_start_date / sim_end_date set, backtest only in that window.
    """
    if history_calendar_days is not None:
        calendar_days = history_calendar_days
    else:
        need_trading = max(max_trend_days + max_slope_days + 10, max_dip_days + 10)
        calendar_days = fetcher._calendar_days_for_trading_window(need_trading)
    history, errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)

    ticker_infos = {t: (fetcher.get_ticker_info(t) or {}).get("group_key") or (fetcher.get_ticker_info(t) or {}).get("group") or "unknown" for t in tickers}
    tasks: List[Tuple[str, pd.DataFrame, ExitRules, str]] = []
    for ticker in tickers:
        if ticker not in history:
            continue
        df = history[ticker]
        if df is None or df.empty or "Close" not in df.columns:
            continue
        df = df.sort_index()
        group = ticker_infos.get(ticker, "unknown")
        for exit_rules in exit_rules_list:
            tasks.append((ticker, df, exit_rules, group))

    workers = max_workers if max_workers is not None else min(32, (os.cpu_count() or 4) * 2)
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {
            executor.submit(_run_one_exit, t, d, params, er, g, sim_start_date, sim_end_date): (t, er)
            for t, d, er, g in tasks
        }
        for future in as_completed(future_to_task):
            try:
                results.append(future.result())
            except Exception:
                pass
    return results


def summarize_by_group(
    results: List[Dict[str, Any]],
    metric: str = "total_return_pct",
) -> pd.DataFrame:
    """
    สรุปค่ากลางต่อกลุ่ม (group): แต่ละกลุ่มใช้ชุดพารามิเตอร์ที่ให้ค่าเฉลี่ย return สูงสุดในกลุ่มนั้น.
    Returns DataFrame: group, n_tickers, mean_return_pct, mean_win_rate, mean_max_dd, best trend_days, dip_days, ...
    """
    if not results:
        return pd.DataFrame()
    rows = []
    for r in results:
        row = {
            "group": r.get("group", "Unknown"),
            "ticker": r["ticker"],
            "total_return_pct": r["total_return_pct"],
            "n_trades": r["n_trades"],
            "win_rate": r["win_rate"],
            "max_drawdown_pct": r["max_drawdown_pct"],
            **r.get("params_dict", {}),
        }
        row.update(r.get("exit_dict") or {})
        rows.append(row)
    df = pd.DataFrame(rows)
    param_cols = ["trend_days", "dip_days", "slope_lookback_days", "use_slope_filter", "min_dip_pct"]
    exit_cols = ["exit_hold_days", "exit_take_profit_pct", "exit_stop_loss_pct"]
    if all(c in df.columns for c in exit_cols):
        param_cols = param_cols + exit_cols
    # For each group, find param set that gives highest mean(metric) in that group
    best_by_group = []
    for group_name, g in df.groupby("group"):
        n_tickers = g["ticker"].nunique()
        # For each param set (unique combination of param_cols), mean return in this group
        by_params = g.groupby(param_cols, dropna=False)[metric].mean().reset_index()
        best_idx = by_params[metric].idxmax()
        best_row = by_params.loc[best_idx]
        # Aggregate stats when using that best param set: take rows with that param set in this group
        mask = pd.Series(True, index=g.index)
        for c in param_cols:
            if c not in g.columns:
                continue
            both_na = g[c].isna() & pd.isna(best_row[c])
            match = (g[c] == best_row[c]) | both_na
            mask = mask & match
        sub = g.loc[mask]
        best_by_group.append({
            "group": group_name,
            "n_tickers": n_tickers,
            "mean_return_pct": round(best_row[metric], 4),
            "mean_win_rate": round(sub["win_rate"].mean(), 2),
            "mean_max_dd_pct": round(sub["max_drawdown_pct"].mean(), 2),
            "mean_n_trades": round(sub["n_trades"].mean(), 1),
            **{c: best_row[c] for c in param_cols},
        })
    out = pd.DataFrame(best_by_group)
    out = out.sort_values("mean_return_pct", ascending=False).reset_index(drop=True)
    return out


def summarize_all_exclude_commodity(
    results: List[Dict[str, Any]],
    metric: str = "total_return_pct",
) -> Optional[pd.DataFrame]:
    """
    สรุปค่ากลางแบบทั้งหมด (exclude Commodity): หนึ่งแถว จากทุกกลุ่มที่ไม่รวม Commodity.
    หาชุดพารามิเตอร์ที่ให้ค่าเฉลี่ย return สูงสุดในกลุ่ม "ทั้งหมดยกเว้น Commodity".
    """
    if not results:
        return None
    def _gkey(r: Dict[str, Any]) -> str:
        return str(r.get("group_key") or r.get("group") or "")

    excluded = [r for r in results if not _gkey(r).lower().startswith("commodity")]
    if not excluded:
        return None
    rows = []
    for r in excluded:
        row = {"group": r.get("group", "Unknown"), "ticker": r["ticker"], "total_return_pct": r["total_return_pct"], "n_trades": r["n_trades"], "win_rate": r["win_rate"], "max_drawdown_pct": r["max_drawdown_pct"], **r.get("params_dict", {})}
        row.update(r.get("exit_dict") or {})
        rows.append(row)
    df = pd.DataFrame(rows)
    param_cols = ["trend_days", "dip_days", "slope_lookback_days", "use_slope_filter", "min_dip_pct"]
    if all(c in df.columns for c in ["exit_hold_days", "exit_take_profit_pct", "exit_stop_loss_pct"]):
        param_cols = param_cols + ["exit_hold_days", "exit_take_profit_pct", "exit_stop_loss_pct"]
    by_params = df.groupby(param_cols, dropna=False)[metric].mean().reset_index()
    best_idx = by_params[metric].idxmax()
    best_row = by_params.loc[best_idx]
    mask = pd.Series(True, index=df.index)
    for c in param_cols:
        if c not in df.columns:
            continue
        both_na = df[c].isna() & pd.isna(best_row[c])
        mask = mask & ((df[c] == best_row[c]) | both_na)
    sub = df.loc[mask]
    row = {
        "group": "All (exclude Commodity)",
        "n_tickers": df["ticker"].nunique(),
        "mean_return_pct": round(best_row[metric], 4),
        "mean_win_rate": round(sub["win_rate"].mean(), 2),
        "mean_max_dd_pct": round(sub["max_drawdown_pct"].mean(), 2),
        "mean_n_trades": round(sub["n_trades"].mean(), 1),
        **{c: best_row[c] for c in param_cols},
    }
    return pd.DataFrame([row])


def _df_to_yaml_friendly(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert DataFrame to list of dicts with NaN -> None and numpy types to Python for YAML."""
    if df is None or df.empty:
        return []
    out = []
    for _, row in df.iterrows():
        d = {}
        for c in df.columns:
            v = row[c]
            if pd.isna(v):
                d[c] = None
            elif hasattr(v, "item"):
                d[c] = v.item()
            else:
                d[c] = v
        out.append(d)
    return out


def build_sim_output_yaml(
    run_meta: Dict[str, Any],
    best_per_ticker: pd.DataFrame,
    best_overall: pd.DataFrame,
    by_group: pd.DataFrame,
    excl_commodity: Optional[pd.DataFrame],
    per_ticker_agg: Optional[pd.DataFrame],
) -> Dict[str, Any]:
    """Build a dict suitable for YAML output so planner can load and compare."""
    return {
        "run": run_meta,
        "best_per_ticker": _df_to_yaml_friendly(best_per_ticker),
        "best_overall": _df_to_yaml_friendly(best_overall),
        "summary_by_group": _df_to_yaml_friendly(by_group),
        "all_exclude_commodity": _df_to_yaml_friendly(excl_commodity) if excl_commodity is not None and not excl_commodity.empty else [],
        "per_ticker_agg": _df_to_yaml_friendly(per_ticker_agg) if per_ticker_agg is not None and not per_ticker_agg.empty else [],
    }


def summarize_best(
    results: List[Dict[str, Any]],
    by_ticker: bool = True,
    metric: str = "total_return_pct",
) -> pd.DataFrame:
    """Best param set per ticker (or overall) by chosen metric. Includes exit_dict columns when present."""
    rows = []
    for r in results:
        row = {
            "ticker": r["ticker"],
            "total_return_pct": r["total_return_pct"],
            "n_trades": r["n_trades"],
            "win_rate": r["win_rate"],
            "max_drawdown_pct": r["max_drawdown_pct"],
            "sharpe_approx": r["sharpe_approx"],
            **r.get("params_dict", {}),
        }
        row.update(r.get("exit_dict") or {})
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if by_ticker:
        idx = df.groupby("ticker")[metric].idxmax()
        return df.loc[idx].sort_values(metric, ascending=False).reset_index(drop=True)
    best_idx = df[metric].idxmax()
    return df.loc[[best_idx]].reset_index(drop=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Dip-Buy backtest + grid search")
    parser.add_argument("--tickers", nargs="*", default=None, help="Tickers to test (default: all from etf.yaml)")
    parser.add_argument("--hold-days", type=int, default=None, help="Override exit_rules.hold_days from config")
    parser.add_argument("--take-profit", type=float, default=None)
    parser.add_argument("--stop-loss", type=float, default=None)
    parser.add_argument("--spread", type=float, default=None, help="Round-trip spread %% (sell-buy diff), e.g. 0.15 = 0.15%%")
    parser.add_argument("--grid", action="store_true", help="Run full grid search (slow)")
    parser.add_argument("--small-grid", action="store_true", help="Small param grid")
    parser.add_argument("--grid-exit", action="store_true", help="Grid over exit rules: hold_days 5,10,15,20; take 3,5,8,10,15; stop None,-3,-5 (spread from config)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tickers (for testing)")
    parser.add_argument("--years", type=float, default=None, help="Backtest history in years (e.g. 3 for 3 years)")
    parser.add_argument("--start-date", type=str, default=None, help="Simulation start date (YYYY-MM-DD), e.g. 2020-01-01")
    parser.add_argument("--config", type=str, default=None, help="Path to dip_default.yaml (default: same dir as script)")
    parser.add_argument("--sim-config", type=str, default=None, help="Path to dip-sim.yaml for grid lists (default: same dir as script)")
    parser.add_argument("--output", "-o", type=str, default=None, help="Write simulation result to YAML (for planner); default: dip_sim_result.yaml")
    args = parser.parse_args()

    default_params, default_exit, config_start_date = load_dip_defaults(Path(args.config) if args.config else None)
    sim_start_date = _parse_start_date(args.start_date) if args.start_date else config_start_date
    sim_config_path = Path(args.sim_config) if args.sim_config else None

    # When both --start-date and --years: backtest window = start_date for `years` years (or until data ends)
    sim_end_date: Optional[pd.Timestamp] = None
    if sim_start_date is not None and args.years is not None and args.years > 0:
        start_ts = pd.Timestamp(sim_start_date)
        if start_ts.tzinfo is not None:
            start_ts = start_ts.tz_localize(None)
        sim_end_date = start_ts + timedelta(days=int(args.years * 365))

    fetcher = ETFDataFetcher()
    tickers = args.tickers or list(fetcher.tickers_map.keys())
    if args.limit:
        tickers = tickers[: args.limit]

    exit_rules = ExitRules(
        hold_days=default_exit.hold_days,
        take_profit_pct=default_exit.take_profit_pct,
        stop_loss_pct=default_exit.stop_loss_pct,
        spread_pct=default_exit.spread_pct,
    )
    if args.hold_days is not None:
        exit_rules = ExitRules(hold_days=args.hold_days, take_profit_pct=exit_rules.take_profit_pct, stop_loss_pct=exit_rules.stop_loss_pct, spread_pct=exit_rules.spread_pct)
    if args.take_profit is not None:
        exit_rules = ExitRules(hold_days=exit_rules.hold_days, take_profit_pct=args.take_profit, stop_loss_pct=exit_rules.stop_loss_pct, spread_pct=exit_rules.spread_pct)
    if args.stop_loss is not None:
        exit_rules = ExitRules(hold_days=exit_rules.hold_days, take_profit_pct=exit_rules.take_profit_pct, stop_loss_pct=args.stop_loss, spread_pct=exit_rules.spread_pct)
    if args.spread is not None:
        exit_rules = ExitRules(hold_days=exit_rules.hold_days, take_profit_pct=exit_rules.take_profit_pct, stop_loss_pct=exit_rules.stop_loss_pct, spread_pct=args.spread)

    # Fetch window: when both start_date and years are set, fetch from start_date to today so the window is covered
    history_days = None
    if args.years is not None and args.years > 0:
        if sim_start_date is not None:
            # Need data from sim_start_date to today (at least)
            today = pd.Timestamp.now().normalize()
            start_ts = pd.Timestamp(sim_start_date).normalize()
            if start_ts.tzinfo is not None:
                start_ts = start_ts.tz_localize(None)
            history_days = max((today - start_ts).days + 60, int(args.years * 365) + 60)
        else:
            history_days = int(args.years * 365) + 60  # calendar days + cushion

    if args.grid_exit:
        exit_rules_list = exit_rules_grid(spread_pct=exit_rules.spread_pct, sim_config_path=sim_config_path)
        results = grid_search_exit(
            fetcher, tickers, default_params, exit_rules_list,
            history_calendar_days=history_days,
            sim_start_date=sim_start_date,
            sim_end_date=sim_end_date,
        )
    elif args.grid or args.small_grid:
        if args.small_grid:
            param_list = small_grid_from_config(sim_config_path) or [
                DipBuyParams(100, 7, 20, True, 0.0),
                DipBuyParams(200, 7, 20, True, 0.0),
                DipBuyParams(200, 5, 20, False, 2.0),
            ]
        else:
            param_list = param_grid_reasonable(sim_config_path)
        results = grid_search(
            fetcher, tickers, param_list, exit_rules,
            history_calendar_days=history_days,
            sim_start_date=sim_start_date,
            sim_end_date=sim_end_date,
        )
    else:
        param_list = [default_params]
        results = grid_search(
            fetcher, tickers, param_list, exit_rules,
            history_calendar_days=history_days,
            sim_start_date=sim_start_date,
            sim_end_date=sim_end_date,
        )

    if not results:
        print("No backtest results.")
        return

    r0 = results[0]
    if r0.get("backtest_start") is not None and r0.get("backtest_end") is not None:
        print(f"Backtest period (example): {r0['backtest_start'].date()} to {r0['backtest_end'].date()}")

    summary = summarize_best(results, by_ticker=True, metric="total_return_pct")
    print("\n--- Best params per ticker (by total_return_pct) ---")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print(summary.to_string())

    overall = summarize_best(results, by_ticker=False, metric="total_return_pct")
    print("\n--- Best single param set (overall) ---")
    print(overall.to_string())

    by_group = summarize_by_group(results, metric="total_return_pct")
    if not by_group.empty:
        print("\n--- สรุปค่ากลางต่อกลุ่ม (เรียงตาม mean return สูงสุด) ---")
        print(by_group.to_string())

    excl_commodity = summarize_all_exclude_commodity(results, metric="total_return_pct")
    if excl_commodity is not None and not excl_commodity.empty:
        print("\n--- ค่ากลางทั้งหมด (exclude Commodity) ---")
        print(excl_commodity.to_string())

    agg = pd.DataFrame([
        {
            "ticker": r["ticker"],
            "total_return_pct": r["total_return_pct"],
            "n_trades": r["n_trades"],
            "win_rate": r["win_rate"],
            "max_drawdown_pct": r["max_drawdown_pct"],
        }
        for r in results
    ])
    if not agg.empty:
        by_ticker_agg = agg.groupby("ticker").agg({
            "total_return_pct": "mean",
            "n_trades": "sum",
            "win_rate": "mean",
            "max_drawdown_pct": "mean",
        }).reset_index()
        print("\n--- Per-ticker aggregate (over param sets) ---")
        print(by_ticker_agg.head(20).to_string())
    else:
        by_ticker_agg = None

    out_path = Path(args.output) if args.output else (Path(__file__).resolve().parent / "dip_sim_result.yaml")
    r0 = results[0]
    backtest_start = r0.get("backtest_start")
    backtest_end = r0.get("backtest_end")
    if backtest_start is not None and hasattr(backtest_start, "isoformat"):
        backtest_start = backtest_start.isoformat()
    if backtest_end is not None and hasattr(backtest_end, "isoformat"):
        backtest_end = backtest_end.isoformat()
    mode = "grid_exit" if args.grid_exit else ("small_grid" if args.small_grid else ("grid" if args.grid else "single"))
    sim_start_str = None
    if sim_start_date is not None:
        sim_start_str = sim_start_date.strftime("%Y-%m-%d") if hasattr(sim_start_date, "strftime") else str(sim_start_date)
    sim_end_str = None
    if sim_end_date is not None:
        sim_end_str = sim_end_date.strftime("%Y-%m-%d") if hasattr(sim_end_date, "strftime") else str(sim_end_date)
    run_meta = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "years": args.years,
        "sim_start_date": sim_start_str,
        "sim_end_date": sim_end_str,
        "backtest_start": backtest_start,
        "backtest_end": backtest_end,
        "n_tickers": len(tickers),
        "exit_rules": {
            "hold_days": exit_rules.hold_days,
            "take_profit_pct": exit_rules.take_profit_pct,
            "stop_loss_pct": exit_rules.stop_loss_pct,
            "spread_pct": exit_rules.spread_pct,
        },
    }
    payload = build_sim_output_yaml(
        run_meta=run_meta,
        best_per_ticker=summary,
        best_overall=overall,
        by_group=by_group if not by_group.empty else pd.DataFrame(),
        excl_commodity=excl_commodity,
        per_ticker_agg=by_ticker_agg.head(20) if by_ticker_agg is not None else None,
    )
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(payload, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"\n--- Result YAML: {out_path} ---")
    except Exception as e:
        print(f"\nWarning: could not write YAML: {e}")


if __name__ == "__main__":
    main()
