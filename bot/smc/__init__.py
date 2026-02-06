"""
SMC bot: entry (optionally gated by decision) and exit based on SMC logic (structure SL/TP).
Simulator asks at correct interval (e.g. every bar when in position).
Stub: minimal implementation; full SMC (structure, POI, sweep) to be added per doc/smc.md.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import yaml

SMC_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def load_smc_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load bot/smc/config.yaml: hold_days, take_profit_pct, stop_loss_pct, max_hold_days, decision."""
    path = config_path or SMC_CONFIG_PATH
    out: Dict[str, Any] = {
        "decision": "dip_buy",
        "hold_days": 20,
        "take_profit_pct": 15.0,
        "stop_loss_pct": None,
        "max_hold_days": 20,
    }
    if not path.exists():
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return out
    out["position_pct"] = 100.0
    for key in ("decision", "hold_days", "take_profit_pct", "stop_loss_pct", "max_hold_days", "position_pct"):
        if key not in data:
            continue
        v = data[key]
        if key == "hold_days":
            out["hold_days"] = int(v)
        elif key == "max_hold_days":
            out["max_hold_days"] = int(v) if v is not None else out["hold_days"]
        elif key == "take_profit_pct":
            out["take_profit_pct"] = float(v) if v is not None else None
        elif key == "stop_loss_pct":
            out["stop_loss_pct"] = float(v) if v is not None else None
        elif key == "decision":
            out["decision"] = v
        elif key == "position_pct":
            out["position_pct"] = float(v) if v is not None else 100.0
    return out


class SMCBot:
    """
    Bot: Strategy + Risk Manager + Money Manager.
    
    Responsibilities:
    - Wrap Decision: Uses interchangeable decision module (e.g., dip_buy)
    - Entry Gating: Applies bot-specific filters (SMC structure, liquidity sweep)
    - Exit Logic: Decides when to sell (structure-based, time-based, TP/SL)
    - Money Management: Manages cash/invested state, position sizing, risk management
    
    Current: Stub implementation with time/TP/SL fallback.
    Future: Full SMC logic (BOS/CHoCH, OB, FVG, liquidity sweeps).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, initial_fund: Optional[float] = None) -> None:
        self.config = config or {}
        self._decision = self.config.get("decision", "dip_buy")
        # Money management: bot owns shared cash/invested state across all tickers
        self._cash = float(initial_fund) if initial_fund is not None else None
        self._invested = 0.0  # Total money currently in open positions (across all tickers)
        # Track open positions per ticker: ticker -> position_dollars
        self._open_positions: Dict[str, float] = {}

    def get_cash(self) -> Optional[float]:
        """Get available cash."""
        return self._cash

    def get_invested(self) -> float:
        """Get amount currently invested."""
        return self._invested

    def get_capital(self) -> Optional[float]:
        """Get total capital (cash + invested)."""
        if self._cash is None:
            return None
        return self._cash + self._invested

    def can_enter(self) -> bool:
        """Check if bot has enough cash to enter a position."""
        if self._cash is None:
            return False
        return self._cash > 0

    def position_size(
        self,
        df: pd.DataFrame,
        idx: int,
    ) -> float:
        """
        Money Management: How much $ to use for this trade.
        
        Bot manages its own cash state - simulation doesn't need to pass it.
        Current: Uses config position_pct of available cash.
        Future: Can use risk, structure, volatility, etc.
        
        Returns: Position size in $, guaranteed <= available cash
        """
        if self._cash is None or self._cash <= 0:
            return 0.0
        pct = self.config.get("position_pct") or 100.0
        size = self._cash * (pct / 100.0)
        # Never invest more than available cash
        return max(0.0, min(size, self._cash))

    def enter_position(self, ticker: str, position_dollars: float) -> bool:
        """
        Enter a position for a ticker: move money from cash to invested.
        
        Args:
            ticker: Symbol being traded
            position_dollars: Amount to invest
        
        Returns: True if successful, False if insufficient cash.
        """
        if self._cash is None:
            return False
        if position_dollars <= 0 or position_dollars > self._cash:
            return False
        self._cash -= position_dollars
        self._invested += position_dollars
        # Track position for this ticker
        self._open_positions[ticker] = self._open_positions.get(ticker, 0.0) + position_dollars
        return True

    def exit_position(self, ticker: str, position_dollars: float, return_dollars: float) -> None:
        """
        Exit a position for a ticker: move money from invested back to cash, plus profit/loss.
        
        Args:
            ticker: Symbol being traded
            position_dollars: Amount that was invested
            return_dollars: Profit/loss from the trade
        """
        if self._invested < position_dollars:
            # Safety check: shouldn't happen, but handle gracefully
            position_dollars = self._invested
        self._invested -= position_dollars
        if self._cash is not None:
            # Return capital + profit/loss
            self._cash += position_dollars + return_dollars
        # Remove or reduce position for this ticker
        if ticker in self._open_positions:
            self._open_positions[ticker] -= position_dollars
            if self._open_positions[ticker] <= 0:
                del self._open_positions[ticker]

    def cancel_position(self, ticker: str, position_dollars: float) -> None:
        """
        Cancel an unpaired position for a ticker: return invested capital to cash (no profit/loss).
        
        Args:
            ticker: Symbol being traded
            position_dollars: Amount that was invested
        """
        if self._invested < position_dollars:
            position_dollars = self._invested
        self._invested -= position_dollars
        if self._cash is not None:
            self._cash += position_dollars
        # Remove or reduce position for this ticker
        if ticker in self._open_positions:
            self._open_positions[ticker] -= position_dollars
            if self._open_positions[ticker] <= 0:
                del self._open_positions[ticker]
    
    def get_open_positions(self) -> Dict[str, float]:
        """Get all open positions by ticker."""
        return self._open_positions.copy()

    def signal_at_idx(
        self,
        df: pd.DataFrame,
        idx: int,
        decision_signal: bool,
    ) -> bool:
        """
        Entry Decision: Combines decision signal + bot filters.
        
        Current: Passes through decision_signal (no bot filters yet).
        Future: Require SMC conditions (sweep + OB + decision_signal).
        """
        return decision_signal

    def should_sell(
        self,
        df: pd.DataFrame,
        idx: int,
        entry_price: float,
        entry_idx: int,
    ) -> bool:
        """
        Exit Decision: Bot-specific exit logic.
        
        Current: Time-based (hold_days/max_hold_days), TP, SL fallback.
        Future: Structure-based (SL at OB low, TP at liquidity).
        
        Called by simulation at correct interval (every bar when in position).
        """
        close = df["Close"].iloc[idx] if "Close" in df.columns else entry_price
        hold_elapsed = idx - entry_idx
        max_hold = self.config.get("max_hold_days") or self.config.get("hold_days")
        if max_hold is not None and hold_elapsed >= max_hold:
            return True
        tp = self.config.get("take_profit_pct")
        if tp is not None and close >= entry_price * (1.0 + tp / 100.0):
            return True
        sl = self.config.get("stop_loss_pct")
        if sl is not None and sl < 0 and close <= entry_price * (1.0 + sl / 100.0):
            return True
        return False


def create_bot(
    config: Optional[Dict[str, Any]] = None,
    config_path: Optional[Path] = None,
    initial_fund: Optional[float] = None,
) -> SMCBot:
    """Factory for SMC bot instance. Config from bot/smc/config.yaml if config_path not given."""
    if config is None:
        config = load_smc_config(config_path)
    return SMCBot(config=config, initial_fund=initial_fund)
