"""strategy_backtest_lib.py

Small, importable backtest utilities for ETF strategy comparison.

Design goals:
- keep logic reusable by multiple scripts (single-run dashboard, batch runner)
- time-weighted equity curve metrics (CAGR, MDD, vol, Sharpe)
- strategy functions return an equity curve indexed by date

No fees/slippage yet (will be added later).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd


def safe_close(df: pd.DataFrame) -> pd.Series | None:
    if df is None or df.empty or "Close" not in df.columns:
        return None
    close = df.sort_index()["Close"].dropna()
    if close.empty or len(close) < 2:
        return None
    close = close[~close.index.duplicated(keep="last")]
    if len(close) < 2:
        return None
    return close


def equity_from_returns(returns: pd.Series) -> pd.Series:
    returns = returns.fillna(0.0)
    equity = (1.0 + returns).cumprod()
    if len(equity) > 0:
        equity.iloc[0] = 1.0
    return equity


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return float(dd.min())


def compute_metrics(equity: pd.Series) -> dict:
    if equity is None or equity.empty or len(equity) < 2:
        return {}

    equity = equity.dropna()
    if len(equity) < 2:
        return {}

    start_date = equity.index[0]
    end_date = equity.index[-1]
    years = (end_date - start_date).days / 365.25
    if years <= 0:
        return {}

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)

    daily_ret = equity.pct_change().dropna()
    if len(daily_ret) > 5 and daily_ret.std(ddof=0) > 0:
        vol_ann = float(daily_ret.std(ddof=0) * np.sqrt(252))
        sharpe = float((daily_ret.mean() * 252) / (daily_ret.std(ddof=0) * np.sqrt(252)))
    else:
        vol_ann = np.nan
        sharpe = np.nan

    mdd = max_drawdown(equity)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "years": float(years),
        "total_return_pct": total_return * 100.0,
        "cagr_pct": cagr * 100.0,
        "max_drawdown_pct": mdd * 100.0,
        "vol_ann_pct": vol_ann * 100.0 if np.isfinite(vol_ann) else np.nan,
        "sharpe": sharpe,
    }


StrategyFn = Callable[[pd.Series], pd.Series]


@dataclass(frozen=True)
class Strategy:
    key: str
    name: str
    fn: StrategyFn


def strat_buy_hold(close: pd.Series) -> pd.Series:
    close = close.dropna()
    equity = close / float(close.iloc[0])
    if len(equity) > 0:
        equity.iloc[0] = 1.0
    return equity


def strat_sma_crossover(close: pd.Series, fast: int = 50, slow: int = 200) -> pd.Series:
    close = close.dropna()
    if len(close) < slow + 5:
        return strat_buy_hold(close)

    sma_fast = close.rolling(fast).mean()
    sma_slow = close.rolling(slow).mean()
    position = (sma_fast > sma_slow).astype(float)

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = position.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def available_strategies() -> dict[str, Strategy]:
    # As we implement more strategies, add them here.
    return {
        "buy_hold": Strategy("buy_hold", "Buy & Hold", strat_buy_hold),
        "sma_50_200": Strategy(
            "sma_50_200",
            "SMA Crossover (50/200)",
            lambda close: strat_sma_crossover(close, fast=50, slow=200),
        ),
    }
