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


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


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


def strat_ema_crossover(close: pd.Series, fast: int = 20, slow: int = 200, band_pct: float = 0.0) -> pd.Series:
    """EMA crossover with optional band to reduce whipsaw.

    position=1 when ema_fast > ema_slow*(1+band_pct/100)
    band_pct is in percent (e.g. 0.5 means 0.5%).
    """
    close = close.dropna()
    if len(close) < slow + 5:
        return strat_buy_hold(close)

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()

    thresh = ema_slow * (1.0 + band_pct / 100.0)
    position = (ema_fast > thresh).astype(float)

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = position.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def strat_momentum(close: pd.Series, lookback_days: int = 252, skip_recent_days: int = 21, threshold_pct: float = 0.0) -> pd.Series:
    """Time-series (absolute) momentum.

    position=1 when trailing return over lookback_days (ending skip_recent_days ago)
    is > threshold_pct.

    Example defaults: lookback=252, skip=21, threshold=0.
    """
    close = close.dropna()
    if len(close) < lookback_days + skip_recent_days + 5:
        return strat_buy_hold(close)

    shifted = close.shift(skip_recent_days)
    mom = shifted / shifted.shift(lookback_days) - 1.0
    position = (mom > (threshold_pct / 100.0)).astype(float)

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = position.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def _rsi_wilder(close: pd.Series, window: int = 14) -> pd.Series:
    """Wilder RSI (EMA-smoothed gains/losses)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def strat_rsi_mean_reversion(
    close: pd.Series,
    rsi_window: int = 14,
    entry_rsi: float = 30.0,
    exit_rsi: float = 50.0,
    max_hold_days: int | None = None,
) -> pd.Series:
    """RSI mean reversion (long-only).

    Rule:
    - enter long when RSI < entry_rsi
    - exit to cash when RSI > exit_rsi
    - optional: force exit after max_hold_days in position
    """
    close = close.dropna()
    if len(close) < rsi_window + 10:
        return strat_buy_hold(close)

    rsi = _rsi_wilder(close, window=rsi_window)

    # build position statefully
    pos = pd.Series(0.0, index=close.index)
    in_pos = False
    hold = 0
    for i in range(len(close)):
        v = rsi.iloc[i]
        if in_pos:
            hold += 1

        if not np.isfinite(v):
            pos.iloc[i] = 1.0 if in_pos else 0.0
            continue

        if (not in_pos) and (v < entry_rsi):
            in_pos = True
            hold = 0
        elif in_pos and (v > exit_rsi):
            in_pos = False
            hold = 0
        elif in_pos and (max_hold_days is not None) and (hold >= max_hold_days):
            in_pos = False
            hold = 0

        pos.iloc[i] = 1.0 if in_pos else 0.0

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = pos.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def strat_donchian(close: pd.Series, entry_window: int = 55, exit_window: int = 20) -> pd.Series:
    """Donchian breakout (close-only approximation).

    - enter when close > rolling max over entry_window (excluding today)
    - exit when close < rolling min over exit_window (excluding today)
    """
    close = close.dropna()
    if len(close) < max(entry_window, exit_window) + 10:
        return strat_buy_hold(close)

    hh = close.shift(1).rolling(entry_window).max()
    ll = close.shift(1).rolling(exit_window).min()

    pos = pd.Series(0.0, index=close.index)
    in_pos = False
    for i in range(len(close)):
        c = close.iloc[i]
        hi = hh.iloc[i]
        lo = ll.iloc[i]
        if np.isfinite(hi) and (not in_pos) and (c > hi):
            in_pos = True
        elif np.isfinite(lo) and in_pos and (c < lo):
            in_pos = False
        pos.iloc[i] = 1.0 if in_pos else 0.0

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = pos.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def strat_bollinger_mean_reversion(
    close: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
    exit_rule: str = "mid",  # mid|upper
    max_hold_days: int | None = None,
) -> pd.Series:
    """Bollinger mean reversion (long-only).

    Enter when close < lower band.
    Exit when close > mid band (or upper band), or after max_hold_days.
    """
    close = close.dropna()
    if len(close) < window + 10:
        return strat_buy_hold(close)

    mid = close.rolling(window).mean()
    sd = close.rolling(window).std(ddof=0)
    upper = mid + num_std * sd
    lower = mid - num_std * sd

    pos = pd.Series(0.0, index=close.index)
    in_pos = False
    hold = 0

    for i in range(len(close)):
        c = close.iloc[i]
        if in_pos:
            hold += 1

        lo = lower.iloc[i]
        m = mid.iloc[i]
        up = upper.iloc[i]

        if not in_pos and np.isfinite(lo) and (c < lo):
            in_pos = True
            hold = 0
        elif in_pos:
            if (max_hold_days is not None) and (hold >= max_hold_days):
                in_pos = False
                hold = 0
            else:
                if exit_rule == "upper":
                    if np.isfinite(up) and (c > up):
                        in_pos = False
                        hold = 0
                else:  # mid
                    if np.isfinite(m) and (c > m):
                        in_pos = False
                        hold = 0

        pos.iloc[i] = 1.0 if in_pos else 0.0

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = pos.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def strat_vol_targeting(
    close: pd.Series,
    vol_lookback_days: int = 63,
    target_vol_ann_pct: float = 10.0,
    trend_filter: str = "none",  # none|sma_200
    trend_window: int = 200,
    max_leverage: float = 1.0,
) -> pd.Series:
    """Volatility targeting (long-only) with optional trend filter.

    Exposure = min(max_leverage, target_vol / realized_vol).
    If trend_filter=sma_200 and close < SMA(trend_window) => exposure=0.
    """
    close = close.dropna()
    if len(close) < max(vol_lookback_days, trend_window) + 10:
        return strat_buy_hold(close)

    daily_ret = close.pct_change().fillna(0.0)
    vol = daily_ret.rolling(vol_lookback_days).std(ddof=0) * np.sqrt(252)
    target = target_vol_ann_pct / 100.0
    exp = (target / vol).clip(upper=max_leverage)
    exp = exp.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    if trend_filter == "sma_200":
        sma = close.rolling(trend_window).mean()
        exp = exp.where(close >= sma, 0.0)

    strat_ret = exp.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def strat_trend_filter(close: pd.Series, trend_window: int = 200) -> pd.Series:
    """Simple trend filter: in market when close >= SMA(trend_window)."""
    close = close.dropna()
    if len(close) < trend_window + 10:
        return strat_buy_hold(close)

    sma = close.rolling(trend_window).mean()
    pos = (close >= sma).astype(float).fillna(0.0)

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = pos.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def strat_crash_filter_drawdown(
    close: pd.Series,
    dd_lookback_days: int = 126,
    dd_threshold_pct: float = -15.0,
    reentry_rule: str = "sma_200",  # sma_200|new_high|cooldown
    cooldown_days: int = 20,
    sma_window: int = 200,
) -> pd.Series:
    """Simple crash filter using drawdown vs rolling peak.

    Compute drawdown over dd_lookback window. If dd < threshold => go to cash.
    Re-enter depending on rule.
    """
    close = close.dropna()
    if len(close) < max(dd_lookback_days, sma_window) + 20:
        return strat_buy_hold(close)

    rolling_peak = close.rolling(dd_lookback_days).max()
    dd = close / rolling_peak - 1.0

    sma = close.rolling(sma_window).mean()

    pos = pd.Series(0.0, index=close.index)
    in_pos = True
    cd = 0

    for i in range(len(close)):
        if not in_pos:
            cd += 1

        d = dd.iloc[i]
        if np.isfinite(d) and in_pos and (d < (dd_threshold_pct / 100.0)):
            in_pos = False
            cd = 0

        if not in_pos:
            if reentry_rule == "cooldown":
                if cd >= cooldown_days:
                    in_pos = True
                    cd = 0
            elif reentry_rule == "new_high":
                pk = rolling_peak.iloc[i]
                if np.isfinite(pk) and close.iloc[i] >= pk:
                    in_pos = True
                    cd = 0
            else:  # sma_200
                sm = sma.iloc[i]
                if np.isfinite(sm) and close.iloc[i] >= sm:
                    in_pos = True
                    cd = 0

        pos.iloc[i] = 1.0 if in_pos else 0.0

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = pos.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def strat_macd_crossover(
    close: pd.Series,
    fast_span: int = 12,
    slow_span: int = 26,
    signal_span: int = 9,
    use_zero_filter: bool = False,
) -> pd.Series:
    """MACD signal-line crossover (long-only).

    Enter when MACD crosses above Signal; exit when crosses below.
    Optional: if use_zero_filter, only allow longs when MACD > 0.
    """
    close = close.dropna()
    if len(close) < max(slow_span, fast_span, signal_span) + 10:
        return strat_buy_hold(close)

    macd = _ema(close, span=fast_span) - _ema(close, span=slow_span)
    signal = _ema(macd, span=signal_span)

    long_cond = macd > signal
    if use_zero_filter:
        long_cond = long_cond & (macd > 0)

    pos = long_cond.astype(float).fillna(0.0)
    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = pos.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def _atr_wilder(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """Wilder ATR using OHLC when available; close-only fallback if not."""
    df = df.sort_index()
    if all(c in df.columns for c in ["High", "Low", "Close"]):
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        close = df["Close"].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                (high - low).abs(),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
    else:
        close = df["Close"].astype(float)
        tr = close.diff().abs()

    atr = tr.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    return atr


def strat_keltner_breakout(
    df: pd.DataFrame,
    ema_window: int = 20,
    atr_window: int = 10,
    atr_mult: float = 2.0,
    exit_rule: str = "mid",  # mid|lower
) -> pd.Series:
    """Keltner channel breakout (long-only).

    Enter when Close > Upper (EMA + atr_mult*ATR).
    Exit when Close < Mid (EMA) or Close < Lower depending on exit_rule.
    """
    if df is None or df.empty or "Close" not in df.columns:
        return pd.Series(dtype=float)

    df = df.sort_index()
    close = df["Close"].dropna().astype(float)
    if len(close) < max(ema_window, atr_window) + 10:
        return strat_buy_hold(close)

    # Align df to close index (drop days without close)
    df2 = df.loc[close.index]

    mid = _ema(close, span=ema_window)
    atr = _atr_wilder(df2, window=atr_window)
    upper = mid + atr_mult * atr
    lower = mid - atr_mult * atr

    pos = pd.Series(0.0, index=close.index)
    in_pos = False

    for i in range(len(close)):
        c = close.iloc[i]
        up = upper.iloc[i]
        md = mid.iloc[i]
        lo = lower.iloc[i]

        if (not in_pos) and np.isfinite(up) and (c > up):
            in_pos = True
        elif in_pos:
            if exit_rule == "lower":
                if np.isfinite(lo) and (c < lo):
                    in_pos = False
            else:  # mid
                if np.isfinite(md) and (c < md):
                    in_pos = False

        pos.iloc[i] = 1.0 if in_pos else 0.0

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = pos.shift(1).fillna(0.0) * daily_ret
    equity = equity_from_returns(strat_ret)
    equity.index = close.index
    return equity


def strat_stochrsi_mean_reversion(
    close: pd.Series,
    rsi_window: int = 14,
    stoch_window: int = 14,
    smooth_k: int = 1,
    smooth_d: int = 1,
    entry: float = 0.2,
    exit: float = 0.8,
    max_hold_days: int | None = None,
) -> pd.Series:
    """StochRSI mean reversion (long-only).

    Compute RSI (Wilder), then StochRSI in [0,1], optionally smooth %K and %D.
    Enter when %D < entry, exit when %D > exit; optional max_hold.
    """
    close = close.dropna()
    if len(close) < max(rsi_window + stoch_window, 50) + 10:
        return strat_buy_hold(close)

    rsi = _rsi_wilder(close, window=rsi_window)
    rsi_min = rsi.rolling(stoch_window).min()
    rsi_max = rsi.rolling(stoch_window).max()
    denom = (rsi_max - rsi_min)
    stoch = (rsi - rsi_min) / denom
    stoch = stoch.replace([np.inf, -np.inf], np.nan)

    k = stoch.rolling(smooth_k).mean() if smooth_k > 1 else stoch
    d = k.rolling(smooth_d).mean() if smooth_d > 1 else k

    pos = pd.Series(0.0, index=close.index)
    in_pos = False
    hold = 0

    for i in range(len(close)):
        v = d.iloc[i]
        if in_pos:
            hold += 1

        if not np.isfinite(v):
            pos.iloc[i] = 1.0 if in_pos else 0.0
            continue

        if (not in_pos) and (v < entry):
            in_pos = True
            hold = 0
        elif in_pos and (v > exit):
            in_pos = False
            hold = 0
        elif in_pos and (max_hold_days is not None) and (hold >= max_hold_days):
            in_pos = False
            hold = 0

        pos.iloc[i] = 1.0 if in_pos else 0.0

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = pos.shift(1).fillna(0.0) * daily_ret
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
        "ema_20_200": Strategy(
            "ema_20_200",
            "EMA Crossover (20/200)",
            lambda close: strat_ema_crossover(close, fast=20, slow=200, band_pct=0.0),
        ),
        "mom_252_skip21": Strategy(
            "mom_252_skip21",
            "Momentum (252d, skip 21d)",
            lambda close: strat_momentum(close, lookback_days=252, skip_recent_days=21, threshold_pct=0.0),
        ),
        "rsi_14_30_50": Strategy(
            "rsi_14_30_50",
            "RSI Mean Reversion (14, entry 30, exit 50)",
            lambda close: strat_rsi_mean_reversion(close, rsi_window=14, entry_rsi=30.0, exit_rsi=50.0, max_hold_days=None),
        ),
        "boll_20_2_mid": Strategy(
            "boll_20_2_mid",
            "Bollinger MR (20, 2.0, exit=mid)",
            lambda close: strat_bollinger_mean_reversion(close, window=20, num_std=2.0, exit_rule="mid", max_hold_days=None),
        ),
        "donch_55_20": Strategy(
            "donch_55_20",
            "Donchian Breakout (55/20)",
            lambda close: strat_donchian(close, entry_window=55, exit_window=20),
        ),
        "vol_tgt_10_sma": Strategy(
            "vol_tgt_10_sma",
            "Vol Target 10% (63d, trend=sma200)",
            lambda close: strat_vol_targeting(close, vol_lookback_days=63, target_vol_ann_pct=10.0, trend_filter="sma_200", trend_window=200, max_leverage=1.0),
        ),
        "crash_dd_126_-15_sma": Strategy(
            "crash_dd_126_-15_sma",
            "Crash Filter (dd126<-15%, reentry=sma200)",
            lambda close: strat_crash_filter_drawdown(close, dd_lookback_days=126, dd_threshold_pct=-15.0, reentry_rule="sma_200", cooldown_days=20, sma_window=200),
        ),
        "macd_12_26_9_zf0": Strategy(
            "macd_12_26_9_zf0",
            "MACD (12/26/9) zero_filter=False",
            lambda close: strat_macd_crossover(close, fast_span=12, slow_span=26, signal_span=9, use_zero_filter=False),
        ),
        "kelt_20_10_m2p0_xmid": Strategy(
            "kelt_20_10_m2p0_xmid",
            "Keltner Breakout (ema20 atr10 x2.0 exit=mid)",
            # available_strategies() is used by scripts that are close-only; Keltner needs OHLC.
            # We provide a close-only fallback DataFrame with Close column.
            lambda close: strat_keltner_breakout(close.to_frame(name="Close"), ema_window=20, atr_window=10, atr_mult=2.0, exit_rule="mid"),
        ),
        "stochrsi_r14_s14_k3_d3_e0p2_x0p8_mhN": Strategy(
            "stochrsi_r14_s14_k3_d3_e0p2_x0p8_mhN",
            "StochRSI MR (rsi14 stoch14 k3 d3 entry<0.2 exit>0.8)",
            lambda close: strat_stochrsi_mean_reversion(close, rsi_window=14, stoch_window=14, smooth_k=3, smooth_d=3, entry=0.2, exit=0.8, max_hold_days=None),
        ),
    }
