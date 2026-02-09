"""
Decision Module: Pure Signal Generator.

Responsibilities:
- Generate BUY signals: When to enter based on technical conditions
- Generate SELL signals: When to exit (optional, if decision has exit logic)
- Pure signal logic: Technical indicators, patterns, conditions only
- No money management: No position sizing, no risk rules

Current: dip_buy only generates BUY signals (exit handled by bot).
Future: Some decisions may generate SELL signals too.

Reads params from decision/dip.yaml; reuses logic from dip_buy_backtest.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import pandas as pd

from backtest.dip_buy_backtest import DipBuyParams, is_dip_buy_signal_at_idx

if TYPE_CHECKING:
    from core.etf_data_fetcher import ETFDataFetcher

# Default: decision/dip.yaml next to this file
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "dip.yaml"


def load_params(config_path: Optional[Path] = None) -> DipBuyParams:
    """Load DipBuyParams from decision/dip.yaml (only dip_buy section; no exit_rules)."""
    path = config_path or DEFAULT_CONFIG_PATH
    params = DipBuyParams()
    if not path.exists():
        return params
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return params
    db = data.get("dip_buy") or {}
    if not isinstance(db, dict):
        return params
    return DipBuyParams(
        trend_days=int(db.get("trend_days", params.trend_days)),
        dip_days=int(db.get("dip_days", params.dip_days)),
        slope_lookback_days=int(db.get("slope_lookback_days", params.slope_lookback_days)),
        use_slope_filter=bool(db.get("use_slope_filter", params.use_slope_filter)),
        min_dip_pct=float(db.get("min_dip_pct", params.min_dip_pct)),
    )


def signal_at_idx(df: pd.DataFrame, idx: int, params: DipBuyParams) -> bool:
    """
    Generate BUY signal: Returns True if dip-buy conditions met at bar idx.
    
    Uses only df.iloc[:idx+1] (no look-ahead).
    Reuses dip_buy_backtest.is_dip_buy_signal_at_idx.
    
    Note: This decision only generates BUY signals. Exit is handled by bot.
    Future decisions may also implement should_sell_at_idx() for SELL signals.
    """
    return is_dip_buy_signal_at_idx(df, idx, params)


def evaluate(
    ticker: str,
    fetcher: "ETFDataFetcher",
    as_of_date: Optional[datetime] = None,
    params: Optional[DipBuyParams] = None,
) -> bool:
    """
    Generate BUY signal: Fetch history, optionally slice to as_of_date, return signal at last bar.
    
    This is a convenience method for live evaluation. For backtesting, use signal_at_idx().
    Exit is handled by bot, not by decision.
    """
    if params is None:
        params = load_params()
    trend_days = params.trend_days
    dip_days = params.dip_days
    slope_lookback_days = params.slope_lookback_days
    history, errors = fetcher.fetch_history_for_windows(
        [ticker],
        trend_window_days=trend_days,
        dip_window_days=dip_days,
        slope_lookback_days=slope_lookback_days,
    )
    if ticker not in history or history[ticker] is None or history[ticker].empty:
        return False
    df = history[ticker].sort_index()
    if as_of_date is not None:
        try:
            ts = pd.Timestamp(as_of_date)
            if ts.tzinfo is None and df.index.tz is not None:
                ts = ts.tz_localize(df.index.tz)
            elif ts.tzinfo is not None and df.index.tz is None:
                ts = ts.tz_localize(None)
            df = df[df.index <= ts]
        except Exception:
            pass
    if df.empty or "Close" not in df.columns:
        return False
    return signal_at_idx(df, len(df) - 1, params)
