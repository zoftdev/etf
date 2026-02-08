"""
Core RSI/SMA indicator backtesting engine.
No look-ahead: signals at bar t use only data up to and including t.
Metrics format aligned with dip_buy_backtest.py.
"""
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pandas as pd


def compute_sma(close: pd.Series, period: int) -> pd.Series:
    """Simple moving average of close prices."""
    return close.rolling(window=period, min_periods=period).mean()


def compute_rsi(close: pd.Series, period: int) -> pd.Series:
    """RSI using Wilder's smoothing (alpha = 1/period). Pure pandas, no TA-lib."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def generate_sma_signals(df: pd.DataFrame, sma_period: int) -> pd.Series:
    """
    Buy when price crosses above SMA(N), sell when price crosses below SMA(N).
    Returns: 1 = buy, -1 = sell, 0 = hold.
    """
    close = df["Close"]
    sma = compute_sma(close, sma_period)
    prev_close = close.shift(1)
    prev_sma = sma.shift(1)
    # Cross above: close > sma and prev_close <= prev_sma
    buy = (close > sma) & (prev_close <= prev_sma)
    # Cross below: close < sma and prev_close >= prev_sma
    sell = (close < sma) & (prev_close >= prev_sma)
    out = pd.Series(0, index=df.index, dtype=int)
    out.loc[buy] = 1
    out.loc[sell] = -1
    return out


def generate_rsi_signals(
    df: pd.DataFrame,
    rsi_period: int,
    rsi_buy_threshold: float,
    rsi_sell_threshold: float,
) -> pd.Series:
    """
    Buy when RSI drops below buy_threshold, sell when RSI rises above sell_threshold.
    Returns: 1 = buy, -1 = sell, 0 = hold.
    """
    close = df["Close"]
    rsi = compute_rsi(close, rsi_period)
    out = pd.Series(0, index=df.index, dtype=int)
    out.loc[rsi < rsi_buy_threshold] = 1
    out.loc[rsi > rsi_sell_threshold] = -1
    return out


def generate_combined_signals(
    df: pd.DataFrame,
    rsi_period: int,
    rsi_buy_threshold: float,
    rsi_sell_threshold: float,
    sma_period: int,
) -> pd.Series:
    """
    Buy when RSI < buy_threshold AND price > SMA (trend confirmation).
    Sell when RSI > sell_threshold OR price < SMA.
    Returns: 1 = buy, -1 = sell, 0 = hold.
    """
    close = df["Close"]
    rsi = compute_rsi(close, rsi_period)
    sma = compute_sma(close, sma_period)
    buy_cond = (rsi < rsi_buy_threshold) & (close > sma)
    sell_cond = (rsi > rsi_sell_threshold) | (close < sma)
    out = pd.Series(0, index=df.index, dtype=int)
    out.loc[buy_cond] = 1
    out.loc[sell_cond] = -1
    return out


def run_backtest(
    df: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 10000.0,
) -> Dict[str, Any]:
    """
    Walk-forward backtest: no look-ahead.
    - Buy signal at bar t -> enter at Open of bar t+1.
    - Sell signal at bar t -> exit at Close of bar t (if in position).
    Returns dict: total_return_pct, n_trades, win_rate, max_drawdown_pct, sharpe_ratio, trades_list.
    """
    if "Open" not in df.columns:
        df = df.copy()
        df["Open"] = df["Close"]

    close = df["Close"].values
    open_ = df["Open"].values
    dates = df.index
    n = len(df)
    sig = signals.reindex(df.index).fillna(0).astype(int).values

    trades: List[Dict[str, Any]] = []
    in_position = False
    entry_idx = -1
    entry_price = 0.0

    for i in range(n):
        if in_position:
            if sig[i] == -1:
                exit_price = close[i]
                ret_pct = (exit_price / entry_price - 1.0) * 100.0
                trades.append({
                    "entry_date": dates[entry_idx],
                    "exit_date": dates[i],
                    "entry_price": float(entry_price),
                    "exit_price": float(exit_price),
                    "return_pct": float(ret_pct),
                    "exit_reason": "signal",
                })
                in_position = False
            continue

        if sig[i] == 1 and i + 1 < n:
            entry_price = open_[i + 1]
            entry_idx = i + 1
            in_position = True

    if in_position and entry_idx < n:
        exit_idx = n - 1
        exit_price = close[exit_idx]
        ret_pct = (exit_price / entry_price - 1.0) * 100.0
        trades.append({
            "entry_date": dates[entry_idx],
            "exit_date": dates[exit_idx],
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "return_pct": float(ret_pct),
            "exit_reason": "end",
        })

    equity_curve = pd.Series(dtype=float)
    if trades:
        eq = 1.0
        eq_curve = [1.0]
        eq_dates = [dates[0]]
        for t in trades:
            eq *= 1.0 + t["return_pct"] / 100.0
            eq_curve.append(eq)
            eq_dates.append(t["exit_date"])
        equity_curve = pd.Series(eq_curve, index=eq_dates)

    metrics = backtest_metrics(trades, equity_curve)
    metrics["trades_list"] = trades
    return metrics


def backtest_metrics(
    trades: List[Dict[str, Any]],
    equity_curve: pd.Series,
) -> Dict[str, Any]:
    """Same metric format as dip_buy_backtest.py."""
    if not trades:
        return {
            "total_return_pct": 0.0,
            "n_trades": 0,
            "win_rate": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0,
        }
    returns = [t["return_pct"] for t in trades]
    total_return_pct = (np.prod([1 + r / 100.0 for r in returns]) - 1.0) * 100.0
    wins = sum(1 for r in returns if r > 0)
    run = np.array(returns)
    cum = np.cumprod(1.0 + run / 100.0)
    peak = np.maximum.accumulate(cum)
    dd = (cum / peak - 1.0) * 100.0
    max_dd = float(np.min(dd)) if len(dd) else 0.0
    sharpe_ratio = float(np.mean(run) / (np.std(run) + 1e-12) * np.sqrt(252 / 15)) if len(run) > 1 else 0.0
    return {
        "total_return_pct": total_return_pct,
        "n_trades": len(trades),
        "win_rate": wins / len(trades) * 100.0,
        "max_drawdown_pct": max_dd,
        "sharpe_ratio": sharpe_ratio,
    }
