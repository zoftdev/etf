"""
Backtest Dip-Buy strategy for ETFs from etf.yaml.
No look-ahead: on signal date only data up to that date is used.
Defaults loaded from dip_default.yaml when present.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import numpy as np
import yaml

from etf_data_fetcher import ETFDataFetcher

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "dip_default.yaml"


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


def load_dip_defaults(config_path: Optional[Path] = None) -> Tuple[DipBuyParams, ExitRules]:
    """Load default DipBuyParams and ExitRules from dip_default.yaml. Missing file or keys use code defaults."""
    path = config_path or DEFAULT_CONFIG_PATH
    dip_buy = DipBuyParams()
    exit_rules = ExitRules()
    if not path.exists():
        return dip_buy, exit_rules
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return dip_buy, exit_rules
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
    return dip_buy, exit_rules


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
) -> Tuple[List[Dict[str, Any]], pd.Series]:
    """
    Run backtest on one price frame. No look-ahead.
    - Signal at day idx → enter at Open of day idx+1.
    - Exit: after hold_days, or when take_profit_pct / stop_loss_pct hit (checked at Close).

    Returns:
        trades: list of {entry_date, exit_date, entry_price, exit_price, return_pct, exit_reason}
        equity_curve: series of cumulative return (1.0 at start, then growth per trade)
    """
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

    trades: List[Dict[str, Any]] = []
    first_idx = need
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
) -> Dict[str, Any]:
    trades, equity = run_single_backtest(df, params, exit_rules)
    metrics = backtest_metrics(trades, equity)
    need = max(
        params.trend_days + params.slope_lookback_days + 2,
        params.dip_days + 2,
    )
    # First date when signal can be generated (no look-ahead)
    backtest_start = df.index[need] if len(df) > need else None
    backtest_end = df.index[-1] if len(df) else None
    return {
        "ticker": ticker,
        "params": params,
        "trades": trades,
        "equity_curve": equity,
        "backtest_start": backtest_start,
        "backtest_end": backtest_end,
        **metrics,
    }


def param_grid_reasonable() -> List[DipBuyParams]:
    """Reasonable grid for search (subset to keep runtime manageable)."""
    grid = []
    for trend_days in [50, 100, 200]:
        for dip_days in [5, 7, 10]:
            for slope_lookback_days in [10, 20]:
                for use_slope_filter in [True, False]:
                    for min_dip_pct in [0.0, 2.0]:
                        grid.append(DipBuyParams(
                            trend_days=trend_days,
                            dip_days=dip_days,
                            slope_lookback_days=slope_lookback_days,
                            use_slope_filter=use_slope_filter,
                            min_dip_pct=min_dip_pct,
                        ))
    return grid


def exit_rules_grid(spread_pct: float = 0.0) -> List[ExitRules]:
    """Grid of exit rules for --grid-exit. hold_days 5,10,...; take 3,5,8,10,15; stop included. No spread variation."""
    hold_days_list = [5, 10, 15, 20]
    take_profit_list = [3.0, 5.0, 8.0, 10.0, 15.0]  # and None for no TP
    stop_loss_list = [None, -3.0, -5.0]
    grid = []
    for hold_days in hold_days_list:
        for take_profit_pct in [None] + take_profit_list:
            for stop_loss_pct in stop_loss_list:
                grid.append(ExitRules(
                    hold_days=hold_days,
                    take_profit_pct=take_profit_pct,
                    stop_loss_pct=stop_loss_pct,
                    spread_pct=spread_pct,
                ))
    return grid


def grid_search(
    fetcher: ETFDataFetcher,
    tickers: List[str],
    param_list: List[DipBuyParams],
    exit_rules: ExitRules,
    max_trend_days: int = 200,
    max_dip_days: int = 14,
    max_slope_days: int = 30,
    history_calendar_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    For each ticker, fetch history; for each param set run backtest; return list of results.
    If history_calendar_days is set (e.g. 3*365 for 3 years), use that for fetch; else use min needed.
    """
    if history_calendar_days is not None:
        calendar_days = history_calendar_days
    else:
        need_trading = max(max_trend_days + max_slope_days + 10, max_dip_days + 10)
        calendar_days = fetcher._calendar_days_for_trading_window(need_trading)
    history, errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)

    results: List[Dict[str, Any]] = []
    for ticker in tickers:
        if ticker not in history:
            continue
        df = history[ticker]
        if df is None or df.empty or "Close" not in df.columns:
            continue
        df = df.sort_index()
        for params in param_list:
            if (
                params.trend_days > max_trend_days
                or params.dip_days > max_dip_days
                or params.slope_lookback_days > max_slope_days
            ):
                continue
            res = run_backtest_ticker(ticker, df, params, exit_rules)
            res["params_dict"] = {
                "trend_days": params.trend_days,
                "dip_days": params.dip_days,
                "slope_lookback_days": params.slope_lookback_days,
                "use_slope_filter": params.use_slope_filter,
                "min_dip_pct": params.min_dip_pct,
            }
            info = fetcher.get_ticker_info(ticker)
            res["group"] = (info.get("group") or "Unknown") if info else "Unknown"
            results.append(res)
    return results


def grid_search_exit(
    fetcher: ETFDataFetcher,
    tickers: List[str],
    params: DipBuyParams,
    exit_rules_list: List[ExitRules],
    max_trend_days: int = 200,
    max_dip_days: int = 14,
    max_slope_days: int = 30,
    history_calendar_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    For each ticker and each exit_rule, run backtest with single DipBuyParams.
    Results include exit_dict (hold_days, take_profit_pct, stop_loss_pct) for summarization.
    """
    if history_calendar_days is not None:
        calendar_days = history_calendar_days
    else:
        need_trading = max(max_trend_days + max_slope_days + 10, max_dip_days + 10)
        calendar_days = fetcher._calendar_days_for_trading_window(need_trading)
    history, errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)

    results: List[Dict[str, Any]] = []
    for ticker in tickers:
        if ticker not in history:
            continue
        df = history[ticker]
        if df is None or df.empty or "Close" not in df.columns:
            continue
        df = df.sort_index()
        for exit_rules in exit_rules_list:
            res = run_backtest_ticker(ticker, df, params, exit_rules)
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
            info = fetcher.get_ticker_info(ticker)
            res["group"] = (info.get("group") or "Unknown") if info else "Unknown"
            results.append(res)
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
    excluded = [r for r in results if "commodity" not in (r.get("group") or "").lower()]
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
    parser.add_argument("--config", type=str, default=None, help="Path to dip_default.yaml (default: same dir as script)")
    args = parser.parse_args()

    default_params, default_exit = load_dip_defaults(Path(args.config) if args.config else None)

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

    history_days = None
    if args.years is not None and args.years > 0:
        history_days = int(args.years * 365) + 60  # calendar days + cushion

    if args.grid_exit:
        exit_rules_list = exit_rules_grid(spread_pct=exit_rules.spread_pct)
        results = grid_search_exit(
            fetcher, tickers, default_params, exit_rules_list,
            history_calendar_days=history_days,
        )
    elif args.grid or args.small_grid:
        if args.small_grid:
            param_list = [
                DipBuyParams(100, 7, 20, True, 0.0),
                DipBuyParams(200, 7, 20, True, 0.0),
                DipBuyParams(200, 5, 20, False, 2.0),
            ]
        else:
            param_list = param_grid_reasonable()
        results = grid_search(
            fetcher, tickers, param_list, exit_rules,
            history_calendar_days=history_days,
        )
    else:
        param_list = [default_params]
        results = grid_search(
            fetcher, tickers, param_list, exit_rules,
            history_calendar_days=history_days,
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


if __name__ == "__main__":
    main()
