"""
Backtest runner for bot/decision. No look-ahead.
Supports decision-only (dip_buy + fallback exit) and optional bot (SMC) with mechanic to ask at correct interval.
Config: bot/simulation.yaml (spread_pct, periods, decision, bot). Exit params in bot/smc/config.yaml when using SMC.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import yaml

from core.etf_data_fetcher import ETFDataFetcher

try:
    import plotly.graph_objects as go
    _HAS_PLOTLY = True
except ImportError:
    _HAS_PLOTLY = False

# Default config next to this file
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "simulation.yaml"


def _parse_date(value: Optional[str]) -> Optional[pd.Timestamp]:
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


def load_simulation_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load bot/simulation.yaml: spread_pct, fund, periods, decision, bot. Exit params are in bot/smc/config.yaml."""
    path = config_path or DEFAULT_CONFIG_PATH
    out: Dict[str, Any] = {
        "spread_pct": 0.0,
        "fund": 10000.0,
        "periods": None,
        "decision": "dip_buy",
        "bot": None,
    }
    if not path.exists():
        return out
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return out
    if "spread_pct" in data:
        out["spread_pct"] = float(data["spread_pct"])
    if "fund" in data and data["fund"] is not None:
        out["fund"] = float(data["fund"])
    if "periods" in data and isinstance(data["periods"], list) and len(data["periods"]) > 0:
        out["periods"] = [
            {"name": p.get("name", ""), "start_date": p.get("start_date"), "end_date": p.get("end_date")}
            for p in data["periods"]
            if isinstance(p, dict)
        ]
    if "decision" in data:
        out["decision"] = data["decision"]
    if "bot" in data:
        out["bot"] = data["bot"]
    return out


def _run_single_backtest_decision_only(
    df: pd.DataFrame,
    signal_at_idx_fn,
    params_need_bars: int,
    hold_days: int,
    take_profit_pct: Optional[float],
    stop_loss_pct: Optional[float],
    spread_pct: float,
    start_ts: Optional[pd.Timestamp] = None,
    end_ts: Optional[pd.Timestamp] = None,
    bot=None,
    fund: Optional[float] = None,
    ticker: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], pd.Series, Optional[float]]:
    """
    Simulation orchestrator: manages backtest loop, calls bot/decision at each bar.
    
    Responsibilities:
    - Time/event management: iterate bars, call bot/decision at correct intervals
    - Trade execution: record entries/exits, apply spread_pct
    - Capital tracking: track fund changes across trades
    
    Entry: Calls bot.signal_at_idx() or decision.signal_at_idx() for BUY signals.
    Exit: Calls bot.should_sell() when in position (or fallback hold_days/TP/SL if no bot).
    Position sizing: Calls bot.position_size() if bot provided, else uses 100% of capital.
    
    Entry at Open of bar idx+1; exit at Close. No look-ahead.
    """
    if "Open" not in df.columns:
        df = df.copy()
        df["Open"] = df["Close"]
    close = df["Close"].values
    open_ = df["Open"].values
    dates = df.index
    n = len(df)
    if n < params_need_bars + hold_days + 2:
        return [], pd.Series(dtype=float), fund
    first_idx = params_need_bars
    if start_ts is not None:
        mask = dates >= start_ts
        if mask.any():
            first_idx = max(params_need_bars, int(np.where(mask)[0][0]))
    trades: List[Dict[str, Any]] = []
    in_position = False
    entry_idx = -1
    entry_price = 0.0
    position_dollars = 0.0
    
    for idx in range(first_idx, n - 1):
        if in_position:
            # Check if we're past the period end - if so, cancel the position
            if end_ts is not None and dates[idx] > end_ts:
                # Cancel position: bot returns invested capital to cash
                if bot is not None:
                    ticker_for_bot = ticker or "unknown"
                    bot.cancel_position(ticker_for_bot, position_dollars)
                in_position = False
                continue
            hold_elapsed = idx - entry_idx
            exit_price = float(close[idx])
            if bot is not None:
                sell = bot.should_sell(df, idx, entry_price, entry_idx)
                exit_reason = "smc"
            else:
                hit_tp = (
                    take_profit_pct is not None
                    and exit_price >= entry_price * (1.0 + take_profit_pct / 100.0)
                )
                hit_sl = (
                    stop_loss_pct is not None
                    and stop_loss_pct < 0
                    and exit_price <= entry_price * (1.0 + stop_loss_pct / 100.0)
                )
                exit_reason = "hold_days"
                if hit_tp:
                    exit_reason = "take_profit"
                elif hit_sl:
                    exit_reason = "stop_loss"
                elif hold_elapsed >= hold_days:
                    exit_reason = "hold_days"
                sell = exit_reason != "hold_days" or hold_elapsed >= hold_days
            if sell:
                ret_pct = (exit_price / entry_price - 1.0) * 100.0 - spread_pct
                if bot is not None and position_dollars > 0:
                    # Calculate return: position value after price change minus spread
                    return_dollars = position_dollars * ((exit_price / entry_price - 1.0) - spread_pct / 100.0)
                    # Bot manages money: exit position (pass ticker for tracking)
                    ticker_for_bot = ticker or "unknown"
                    bot.exit_position(ticker_for_bot, position_dollars, return_dollars)
                    # Safety check: cash should never be negative
                    cash_after = bot.get_cash()
                    if cash_after is not None and cash_after < -0.01:  # Allow small floating point errors
                        raise ValueError(
                            f"Cash went negative after exit! Cash: ${cash_after:.2f}, "
                            f"Position: ${position_dollars:.2f}, Return: ${return_dollars:.2f}, "
                            f"Entry: {dates[entry_idx]}, Exit: {dates[idx]}"
                        )
                    trade = {
                        "entry_date": dates[entry_idx],
                        "exit_date": dates[idx],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "return_pct": ret_pct,
                        "exit_reason": exit_reason,
                        "position_dollars": position_dollars,
                        "return_dollars": return_dollars,
                    }
                elif fund is not None and position_dollars > 0:
                    # Decision-only mode: track manually (no bot money management)
                    return_dollars = position_dollars * ((exit_price / entry_price - 1.0) - spread_pct / 100.0)
                    trade = {
                        "entry_date": dates[entry_idx],
                        "exit_date": dates[idx],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "return_pct": ret_pct,
                        "exit_reason": exit_reason,
                        "position_dollars": position_dollars,
                        "return_dollars": return_dollars,
                    }
                else:
                    trade = {
                        "entry_date": dates[entry_idx],
                        "exit_date": dates[idx],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "return_pct": ret_pct,
                        "exit_reason": exit_reason,
                    }
                trades.append(trade)
                in_position = False
            continue
        if end_ts is not None and dates[idx] > end_ts:
            continue
        decision_signal = signal_at_idx_fn(df, idx)
        if bot is not None:
            entry_signal = bot.signal_at_idx(df, idx, decision_signal)
        else:
            entry_signal = decision_signal
        if entry_signal:
            entry_price = float(open_[idx + 1])
            entry_idx = idx + 1
            
            # Bot manages money: ask bot for position size and check if can enter
            if bot is not None:
                # Safety check: cash should never be negative before entry
                cash_before = bot.get_cash()
                if cash_before is not None and cash_before < -0.01:  # Allow small floating point errors
                    raise ValueError(
                        f"Cash is negative before entry! Cash: ${cash_before:.2f}, "
                        f"Date: {dates[idx]}, Entry signal at idx: {idx}"
                    )
                if not bot.can_enter():
                    # Bot says no cash available, skip this entry
                    continue
                # Bot decides position size based on its internal cash state
                position_dollars = bot.position_size(df, idx)
                if position_dollars > 0:
                    # Bot enters position (manages cash/invested internally, tracks by ticker)
                    ticker_for_bot = ticker or "unknown"
                    if bot.enter_position(ticker_for_bot, position_dollars):
                        # Safety check: cash should never be negative after entry
                        cash_after = bot.get_cash()
                        if cash_after is not None and cash_after < -0.01:  # Allow small floating point errors
                            raise ValueError(
                                f"Cash went negative after entry! Cash before: ${cash_before:.2f}, "
                                f"Cash after: ${cash_after:.2f}, Position: ${position_dollars:.2f}, "
                                f"Ticker: {ticker_for_bot}, Date: {dates[idx]}, Entry at idx: {idx}"
                            )
                        in_position = True
                    else:
                        # Bot rejected entry (insufficient cash), skip
                        continue
                else:
                    # Bot returned 0 position size, skip
                    continue
            elif fund is not None:
                # Decision-only mode: use all fund (simple fallback)
                position_dollars = fund
                in_position = True
            else:
                position_dollars = 0.0
                in_position = True
    # If simulation ends while still in position, cancel the last buy without pair
    # Bot manages money: cancel position (pass ticker for tracking)
    if in_position and bot is not None:
        ticker_for_bot = ticker or "unknown"
        bot.cancel_position(ticker_for_bot, position_dollars)
        # Safety check: cash should never be negative after cancel
        cash_after = bot.get_cash()
        if cash_after is not None and cash_after < -0.01:  # Allow small floating point errors
            raise ValueError(
                f"Cash went negative after cancel! Cash: ${cash_after:.2f}, "
                f"Position: ${position_dollars:.2f}, Entry: {dates[entry_idx]}"
            )
    
    equity = 1.0
    equity_curve = [1.0]
    eq_dates = [dates[first_idx]]
    for t in trades:
        equity *= 1.0 + t["return_pct"] / 100.0
        equity_curve.append(equity)
        eq_dates.append(t["exit_date"])
    # Return final capital from bot if available, otherwise from fund tracking
    final_capital = None
    if bot is not None:
        final_capital = bot.get_capital()
        # Final safety check: cash and capital should never be negative
        cash_final = bot.get_cash()
        invested_final = bot.get_invested()
        if cash_final is not None and cash_final < -0.01:  # Allow small floating point errors
            raise ValueError(
                f"Final cash is negative! Cash: ${cash_final:.2f}, "
                f"Invested: ${invested_final:.2f}, Capital: ${final_capital:.2f}"
            )
        if final_capital is not None and final_capital < -0.01:
            raise ValueError(
                f"Final capital is negative! Cash: ${cash_final:.2f}, "
                f"Invested: ${invested_final:.2f}, Capital: ${final_capital:.2f}"
            )
    elif fund is not None:
        # Decision-only mode: calculate from trades
        final_capital = float(fund)
        for t in trades:
            if "return_dollars" in t:
                final_capital += t["return_dollars"]
        # Safety check for decision-only mode
        if final_capital < -0.01:
            raise ValueError(f"Final capital is negative in decision-only mode! Capital: ${final_capital:.2f}")
    
    return trades, pd.Series(equity_curve, index=eq_dates), final_capital


def _sanitize_filename(s: str) -> str:
    """Replace chars unsafe for filenames."""
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in s)


def _trade_return_dollars(t: Dict[str, Any], initial_fund: Optional[float]) -> float:
    """Return dollar PnL for a trade; use return_dollars if present else estimate from return_pct."""
    if t.get("return_dollars") is not None:
        return float(t["return_dollars"])
    fund = initial_fund if initial_fund is not None else 10000.0
    return fund * (float(t["return_pct"]) / 100.0)


def _accumulated_profit_series(
    df: pd.DataFrame,
    trades: List[Dict[str, Any]],
    initial_fund: Optional[float],
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Return (dates, accumulated profit $) at each bar date. Profit = sum of return_dollars for trades exited by that date."""
    if not trades:
        return df.index, np.zeros(len(df))
    cum = 0.0
    dates = []
    values = []
    sorted_exits = sorted(
        [(t["exit_date"], _trade_return_dollars(t, initial_fund)) for t in trades],
        key=lambda x: x[0],
    )
    j = 0
    for d in df.index:
        while j < len(sorted_exits) and sorted_exits[j][0] <= d:
            cum += sorted_exits[j][1]
            j += 1
        dates.append(d)
        values.append(cum)
    return pd.DatetimeIndex(dates), np.array(values)


def _build_simulation_figure(
    ticker: str,
    period_name: str,
    df: pd.DataFrame,
    trades: List[Dict[str, Any]],
    initial_fund: Optional[float] = None,
    profit_axis_range: Optional[tuple[float, float]] = None,
) -> "go.Figure":
    """Build one Plotly figure: price line, buy/sell points, lines connecting each trade, and accumulated profit overlay."""
    fig = go.Figure()
    if df.empty or "Close" not in df.columns:
        return fig
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Close"].values,
            mode="lines",
            name="Price",
            line=dict(color="rgb(80,120,180)", width=1.5),
        )
    )
    # Accumulated profit overlay (secondary y-axis)
    acc_dates, acc_profit = _accumulated_profit_series(df, trades, initial_fund)
    if len(acc_dates) > 0:
        fig.add_trace(
            go.Scatter(
                x=acc_dates,
                y=acc_profit,
                mode="lines",
                name="Accumulated profit ($)",
                line=dict(color="rgb(40,160,80)", width=1.5),
                yaxis="y2",
            )
        )
    if trades:
        # Only show completed trades (must have both entry and exit)
        completed_trades = [t for t in trades if "entry_date" in t and "exit_date" in t]
        
        if completed_trades:
            entry_dates = [t["entry_date"] for t in completed_trades]
            entry_prices = [t["entry_price"] for t in completed_trades]
            exit_dates = [t["exit_date"] for t in completed_trades]
            exit_prices = [t["exit_price"] for t in completed_trades]
            fig.add_trace(
                go.Scatter(
                    x=entry_dates,
                    y=entry_prices,
                    mode="markers",
                    name="Buy",
                    marker=dict(symbol="triangle-up", size=12, color="green", line=dict(width=1, color="darkgreen")),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=exit_dates,
                    y=exit_prices,
                    mode="markers",
                    name="Sell",
                    marker=dict(symbol="triangle-down", size=12, color="red", line=dict(width=1, color="darkred")),
                )
            )
            # Draw connecting lines only for completed trades
            for i, t in enumerate(completed_trades):
                fig.add_trace(
                    go.Scatter(
                        x=[t["entry_date"], t["exit_date"]],
                        y=[t["entry_price"], t["exit_price"]],
                        mode="lines",
                        name=f"Trade {i+1}" if len(completed_trades) <= 10 else None,
                        line=dict(dash="dash", color="rgba(100,100,100,0.6)", width=1),
                        showlegend=len(completed_trades) <= 10,
                    )
                )
        
        # Show unpaired buys (if any) without sell marker or connecting line
        unpaired_buys = [t for t in trades if "entry_date" in t and "exit_date" not in t]
        if unpaired_buys:
            unpaired_entry_dates = [t["entry_date"] for t in unpaired_buys]
            unpaired_entry_prices = [t["entry_price"] for t in unpaired_buys]
            fig.add_trace(
                go.Scatter(
                    x=unpaired_entry_dates,
                    y=unpaired_entry_prices,
                    mode="markers",
                    name="Buy (unpaired)",
                    marker=dict(symbol="triangle-up", size=12, color="orange", line=dict(width=1, color="darkorange")),
                )
            )
    layout_kw: Dict[str, Any] = {
        "title": f"{ticker} — {period_name} (buy/sell and trade lines)",
        "xaxis_title": "Date",
        "yaxis_title": "Price",
        "hovermode": "x unified",
        "template": "plotly_white",
        "autosize": True,
    }
    if len(acc_dates) > 0:
        layout_kw["yaxis2"] = dict(
            title="Accumulated profit ($)",
            overlaying="y",
            side="right",
            showgrid=False,
        )
        if profit_axis_range is not None:
            layout_kw["yaxis2"]["range"] = [float(profit_axis_range[0]), float(profit_axis_range[1])]
    fig.update_layout(**layout_kw)
    return fig


def _build_all_symbol_fund_figure(
    chart_items: List[tuple],
    initial_fund: float,
    fund_axis_range: Optional[tuple[float, float]] = None,
    bot=None,
) -> Optional["go.Figure"]:
    """
    Fund chart: shows cash and invest lines over time, with individual buy/sell points.
    Each point shows symbol, % gain/loss, and profit on hover.
    """
    # Collect all trades with full details
    all_events: List[Dict[str, Any]] = []
    all_dates: List[pd.Timestamp] = []
    
    for ticker, period_name, _df, trades in chart_items:
        if not _df.empty:
            all_dates.extend(_df.index.tolist())
        for t in trades:
            # Entry event
            position_dollars = t.get("position_dollars", 0.0)
            if position_dollars == 0.0 and initial_fund is not None:
                # Estimate from return_pct if position_dollars not available
                return_pct = t.get("return_pct", 0.0)
                return_dollars = t.get("return_dollars")
                if return_dollars is not None:
                    # Reverse calculate: return_dollars = position * (return_pct/100)
                    position_dollars = abs(return_dollars / (return_pct / 100.0)) if return_pct != 0 else initial_fund
                else:
                    position_dollars = initial_fund
            
            all_events.append({
                "date": t["entry_date"],
                "type": "buy",
                "ticker": ticker,
                "period_name": period_name,
                "price": t["entry_price"],
                "position_dollars": position_dollars,
                "return_pct": None,  # Not known at entry
                "return_dollars": None,
            })
            
            # Exit event
            return_dollars = t.get("return_dollars")
            if return_dollars is None:
                return_dollars = _trade_return_dollars(t, initial_fund)
            
            all_events.append({
                "date": t["exit_date"],
                "type": "sell",
                "ticker": ticker,
                "period_name": period_name,
                "price": t["exit_price"],
                "position_dollars": position_dollars,
                "return_pct": t.get("return_pct", 0.0),
                "return_dollars": return_dollars,
            })
    
    if not all_events and not all_dates:
        return None
    
    # Sort events chronologically
    all_events.sort(key=lambda x: x["date"])
    
    # Build cash and invest timeline
    # If bot provided, use bot's actual state (it manages shared fund pool)
    # Otherwise reconstruct from trades (for decision-only mode)
    if bot is not None:
        cash = bot.get_cash() or initial_fund
        invest = bot.get_invested()
        # Bot already has the final state, but we need to show timeline
        # So we'll still reconstruct from trades, but use bot's state as validation
    else:
        cash = initial_fund
        invest = 0.0
    
    timeline_dates = []
    timeline_cash = []
    timeline_invest = []
    
    # Start point (before any trades)
    if all_events:
        timeline_dates.append(all_events[0]["date"])
        timeline_cash.append(cash)
        timeline_invest.append(invest)
    
    # Process each event chronologically
    # Track open positions by ticker to match buys with sells correctly
    open_positions_by_ticker: Dict[str, List[Dict[str, Any]]] = {}  # ticker -> list of open positions
    
    for event in all_events:
        if event["type"] == "buy":
            # Buy: cash decreases, invest increases
            # Only buy if we have enough cash
            if cash >= event["position_dollars"]:
                cash -= event["position_dollars"]
                invest += event["position_dollars"]
                # Track this open position
                ticker = event["ticker"]
                if ticker not in open_positions_by_ticker:
                    open_positions_by_ticker[ticker] = []
                open_positions_by_ticker[ticker].append({
                    "position_dollars": event["position_dollars"],
                    "entry_date": event["date"],
                })
            # Always add to timeline (even if skipped) to show cash state
        elif event["type"] == "sell":
            # Find matching buy for this sell (FIFO: first buy for this ticker)
            ticker = event["ticker"]
            matching_pos = None
            if ticker in open_positions_by_ticker and len(open_positions_by_ticker[ticker]) > 0:
                matching_pos = open_positions_by_ticker[ticker].pop(0)  # FIFO
            
            if matching_pos:
                position_dollars = matching_pos["position_dollars"]
                # Sell: invest decreases, cash increases by (position + return)
                if invest >= position_dollars:
                    invest -= position_dollars
                    cash += position_dollars + event["return_dollars"]
                else:
                    # Safety: if invest is less than expected, adjust
                    actual_invest = min(invest, position_dollars)
                    invest -= actual_invest
                    cash += actual_invest + event["return_dollars"]
            else:
                # No matching buy found - this can happen if buy was skipped due to insufficient cash
                # In this case, we shouldn't process the sell, or process it as if we had the position
                # For now, skip the sell to avoid negative cash
                continue
        
        # Safety check: cash should never go negative
        if cash < -0.01:  # Allow small floating point errors
            raise ValueError(
                f"Cash went negative in fund chart! Cash: ${cash:.2f}, Invest: ${invest:.2f}, "
                f"Event: {event['type']} {event['ticker']} at {event['date']}, "
                f"Position: ${event.get('position_dollars', 0):.2f}"
            )
        
        timeline_dates.append(event["date"])
        # Safety check: cash should never be negative
        if cash < -0.01:  # Allow small floating point errors
            raise ValueError(
                f"Cash went negative in fund chart! Cash: ${cash:.2f}, Invest: ${invest:.2f}, "
                f"Event: {event['type']} {event['ticker']} at {event['date']}, "
                f"Position: ${event.get('position_dollars', 0):.2f}"
            )
        timeline_cash.append(max(0.0, cash))  # Ensure cash is never negative in display
        timeline_invest.append(invest)
    
    # Add end point if we have date range and events ended before max date
    if all_dates and timeline_dates:
        dr = pd.DatetimeIndex(all_dates)
        if timeline_dates[-1] < dr.max():
            timeline_dates.append(dr.max())
            timeline_cash.append(cash)
            timeline_invest.append(invest)
    elif not timeline_dates and all_dates:
        # No events, just show flat lines
        dr = pd.DatetimeIndex(all_dates)
        timeline_dates = [dr.min(), dr.max()]
        timeline_cash = [initial_fund, initial_fund]
        timeline_invest = [0.0, 0.0]
    
    # Final validation: check all cash values are non-negative
    min_cash = min(timeline_cash) if timeline_cash else initial_fund
    if min_cash < -0.01:  # Allow small floating point errors
        raise ValueError(
            f"Fund chart has negative cash! Min cash: ${min_cash:.2f}, "
            f"Initial fund: ${initial_fund:.2f}, Events: {len(all_events)}"
        )
    
    fig = go.Figure()
    
    # Calculate total capital (cash + invest) for stacked line
    timeline_total = [c + i for c, i in zip(timeline_cash, timeline_invest)]
    
    # Cash line (no markers)
    fig.add_trace(
        go.Scatter(
            x=timeline_dates,
            y=timeline_cash,
            mode="lines",
            name="Cash",
            line=dict(color="rgb(60,100,180)", width=2),
        )
    )
    
    # Invest line (no markers)
    fig.add_trace(
        go.Scatter(
            x=timeline_dates,
            y=timeline_invest,
            mode="lines",
            name="Invest",
            line=dict(color="rgb(40,160,80)", width=2),
        )
    )
    
    # Stacked line: Cash + Invest (total capital)
    fig.add_trace(
        go.Scatter(
            x=timeline_dates,
            y=timeline_total,
            mode="lines",
            name="Total (Cash+Invest)",
            line=dict(color="rgb(120,80,200)", width=2, dash="dot"),
        )
    )
    
    # Group events by date to merge same-day events
    events_by_date: Dict[pd.Timestamp, Dict[str, Any]] = {}
    for event in all_events:
        event_date = event["date"]
        if event_date not in events_by_date:
            events_by_date[event_date] = {
                "buys": [],
                "sells": [],
            }
        if event["type"] == "buy":
            events_by_date[event_date]["buys"].append(event)
        elif event["type"] == "sell":
            events_by_date[event_date]["sells"].append(event)
    
    # Process events chronologically to calculate total capital at each merged date
    temp_cash = initial_fund
    temp_invest = 0.0
    merged_dates = []
    merged_totals = []
    merged_hover_texts = []
    processed_dates = set()
    
    for event in all_events:
        event_date = event["date"]
        
        # Skip if we already processed this date
        if event_date in processed_dates:
            # Apply the event but don't add marker again
            if event["type"] == "buy":
                temp_cash -= event["position_dollars"]
                temp_invest += event["position_dollars"]
            elif event["type"] == "sell":
                temp_invest -= event["position_dollars"]
                temp_cash += event["position_dollars"] + event["return_dollars"]
            continue
        
        # First time seeing this date - process all events on this date
        merged_info = events_by_date[event_date]
        processed_dates.add(event_date)
        
        # Calculate total capital before processing events on this date
        total_before = temp_cash + temp_invest
        
        # Process all buys on this date
        for buy_event in merged_info["buys"]:
            temp_cash -= buy_event["position_dollars"]
            temp_invest += buy_event["position_dollars"]
        
        # Process all sells on this date
        for sell_event in merged_info["sells"]:
            temp_invest -= sell_event["position_dollars"]
            temp_cash += sell_event["position_dollars"] + sell_event["return_dollars"]
        
        # Calculate total capital after processing all events on this date
        total_after = temp_cash + temp_invest
        
        # Add marker at the date (use total_after, or total_before if only buys)
        if merged_info["sells"]:
            # Has sells - show total after
            merged_dates.append(event_date)
            merged_totals.append(total_after)
        elif merged_info["buys"]:
            # Only buys - show total before (before cash is moved to invest)
            merged_dates.append(event_date)
            merged_totals.append(total_before)
        
        # Build combined hover text
        hover_parts = []
        if merged_info["buys"]:
            buy_count = len(merged_info["buys"])
            total_buy_amount = sum(b["position_dollars"] for b in merged_info["buys"])
            tickers_buy = ", ".join(sorted(set(b["ticker"] for b in merged_info["buys"])))
            hover_parts.append(f"<b>BUY ({buy_count})</b><br>{tickers_buy}<br>Total: ${total_buy_amount:.2f}")
        
        if merged_info["sells"]:
            sell_count = len(merged_info["sells"])
            total_return = sum(s["return_dollars"] for s in merged_info["sells"])
            tickers_sell = ", ".join(sorted(set(s["ticker"] for s in merged_info["sells"])))
            hover_parts.append(f"<b>SELL ({sell_count})</b><br>{tickers_sell}<br>Total Return: ${total_return:+.2f}")
        
        if hover_parts:
            merged_hover_texts.append("<br>".join(hover_parts))
    
    # Add merged markers on stacked line (total capital)
    if merged_dates:
        fig.add_trace(
            go.Scatter(
                x=merged_dates,
                y=merged_totals,
                mode="markers",
                name="Events",
                marker=dict(
                    symbol="diamond",
                    size=10,
                    color="orange",
                    line=dict(width=1.5, color="darkorange"),
                ),
                text=merged_hover_texts,
                hoverinfo="text+x+y",
            )
        )
    
    fig.update_layout(
        title="Fund — all-symbol (Cash & Invest)",
        xaxis_title="Date",
        yaxis_title="Amount ($)",
        hovermode="closest",
        template="plotly_white",
        autosize=True,
    )
    # Don't apply fund_axis_range here - cash and invest have different scales
    return fig


def write_simulation_charts_single_html(
    chart_items: List[tuple],
    output_path: Path,
    initial_fund: Optional[float] = None,
    bot=None,
) -> None:
    """
    Write one HTML with all simulation charts; dropdown to click and show which chart to display.
    chart_items: list of (ticker, period_name, df, trades).
    Adds "Fund — all-symbol" (fund change) as first option.
    Always writes a file: full charts when possible, otherwise a stub explaining why.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not _HAS_PLOTLY:
        output_path.write_text(
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Simulation charts</title></head><body>"
            "<p>Charts require plotly. Install with: <code>pip install plotly</code></p></body></html>",
            encoding="utf-8",
        )
        return
    if not chart_items:
        output_path.write_text(
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Simulation charts</title></head><body>"
            "<p>No chart data (no ticker/period results from backtest).</p></body></html>",
            encoding="utf-8",
        )
        return
    fund = initial_fund if initial_fund is not None else 10000.0
    parts: List[str] = []
    list_items: List[str] = []
    chart_index = 0

    # Compute global $-range for per-ETF charts only (exclude fund chart).
    # Same scale for all per-symbol accumulated profit overlay (y2, dollars).
    max_abs_change = 0.0
    for _ticker, _period_name, _df, _trades in chart_items:
        if _df is None or getattr(_df, "empty", True):
            continue
        _acc_dates, _acc_profit = _accumulated_profit_series(_df, _trades, fund)
        if len(_acc_profit) > 0:
            max_abs_change = max(max_abs_change, float(np.max(np.abs(_acc_profit))))
    if max_abs_change <= 0:
        max_abs_change = 1.0
    profit_axis_range = (-max_abs_change, max_abs_change)

    # Plotly config for responsive charts
    plotly_config = {"responsive": True, "displayModeBar": True}
    
    # 1) Fund change (all-symbol) chart first (auto-scales, not included in consistent range)
    # If bot provided, use bot's actual cash state; otherwise reconstruct from trades
    fund_fig = _build_all_symbol_fund_figure(chart_items, fund, bot=bot)
    if fund_fig is not None:
        label = "Fund — all-symbol"
        list_items.append(
            f'<li class="chart-item{" active" if chart_index == 0 else ""}" data-index="{chart_index}">{label}</li>'
        )
        frag = fund_fig.to_html(full_html=False, include_plotlyjs=True, config=plotly_config)
        # Mark first chart as active so initial resize logic works
        parts.append(
            f'<div id="chart_wrapper_{chart_index}" class="chart-wrapper active" style="display:block;">{frag}</div>'
        )
        chart_index += 1

    # 2) Per-symbol charts
    for ticker, period_name, df, trades in chart_items:
        if df.empty or "Close" not in df.columns:
            continue
        fig = _build_simulation_figure(
            ticker,
            period_name,
            df,
            trades,
            initial_fund=fund,
            profit_axis_range=profit_axis_range,
        )
        label = f"{ticker} — {period_name}"
        is_first = chart_index == 0 and fund_fig is None
        list_items.append(
            f'<li class="chart-item{" active" if is_first else ""}" data-index="{chart_index}">{label}</li>'
        )
        frag = fig.to_html(full_html=False, include_plotlyjs=False, config=plotly_config)
        visible = "block" if is_first else "none"
        wrapper_cls = "chart-wrapper active" if is_first else "chart-wrapper"
        parts.append(
            f'<div id="chart_wrapper_{chart_index}" class="{wrapper_cls}" style="display:{visible};">{frag}</div>'
        )
        chart_index += 1
    if not parts:
        return
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Simulation charts</title>
  <style>
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; height: 100%; overflow: hidden; }}
    body {{ font-family: sans-serif; display: flex; }}
    .sidebar {{ width: 250px; background: #f5f5f5; border-right: 1px solid #ddd; overflow-y: auto; height: 100vh; flex-shrink: 0; }}
    .sidebar h3 {{ margin: 12px; padding: 0; font-size: 14px; color: #333; }}
    .chart-list {{ list-style: none; margin: 0; padding: 0; }}
    .chart-item {{ padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #e0e0e0; font-size: 13px; }}
    .chart-item:hover {{ background: #e8e8e8; }}
    .chart-item.active {{ background: #4a90e2; color: white; }}
    .chart-container {{ flex: 1; height: 100vh; position: relative; overflow: hidden; }}
    .chart-wrapper {{ width: 100%; height: 100%; display: none; position: absolute; top: 0; left: 0; }}
    .chart-wrapper.active {{ display: block; }}
    .chart-wrapper > div {{ width: 100% !important; height: 100% !important; }}
    .chart-wrapper .js-plotly-plot {{ width: 100% !important; height: 100% !important; }}
  </style>
</head>
<body>
  <div class="sidebar">
    <h3>Charts</h3>
    <ul class="chart-list">
      {chr(10).join(list_items)}
    </ul>
  </div>
  <div class="chart-container">
    {chr(10).join(parts)}
  </div>
  <script>
    var _activeChartIdx = null;

    function _resizePlotlyWithin(wrapperEl) {{
      if (!wrapperEl || !window.Plotly) return;
      var plotDiv = wrapperEl.querySelector(".js-plotly-plot");
      if (!plotDiv) return;
      // Defer resize to next frame so layout has updated (fixes “updates only after scroll”).
      window.requestAnimationFrame(function() {{
        try {{
          window.Plotly.Plots.resize(plotDiv);
        }} catch (e) {{}}
      }});
    }}

    function switchChart(idx) {{
      if (_activeChartIdx === idx) return;
      _activeChartIdx = idx;

      // Update active state in list
      document.querySelectorAll(".chart-item").forEach(function(el) {{
        var i = parseInt(el.getAttribute("data-index") || "-1", 10);
        if (i === idx) el.classList.add("active");
        else el.classList.remove("active");
      }});

      // Show/hide charts
      var activeWrapper = null;
      document.querySelectorAll(".chart-wrapper").forEach(function(el) {{
        var id = el.id || "";
        var m = id.match(/chart_wrapper_(\d+)/);
        var i = m ? parseInt(m[1], 10) : -1;
        if (i === idx) {{
          el.style.display = "block";
          el.classList.add("active");
          activeWrapper = el;
        }} else {{
          el.style.display = "none";
          el.classList.remove("active");
        }}
      }});

      _resizePlotlyWithin(activeWrapper);
    }}

    function bindFastHoverSwitching() {{
      var list = document.querySelector(".chart-list");
      if (!list) return;

      // Switch as mouse moves over items (more reliable than inline onmouseover).
      list.addEventListener("mousemove", function(ev) {{
        var item = ev.target && ev.target.closest ? ev.target.closest(".chart-item") : null;
        if (!item) return;
        var idx = parseInt(item.getAttribute("data-index") || "-1", 10);
        if (idx >= 0) switchChart(idx);
      }});

      // Also allow click (useful on touchpads/mobile).
      list.addEventListener("click", function(ev) {{
        var item = ev.target && ev.target.closest ? ev.target.closest(".chart-item") : null;
        if (!item) return;
        var idx = parseInt(item.getAttribute("data-index") || "-1", 10);
        if (idx >= 0) switchChart(idx);
      }});
    }}

    // Initial selection + initial resize after load
    window.addEventListener("load", function() {{
      bindFastHoverSwitching();
      // Ensure we have an active chart index
      var firstActive = document.querySelector(".chart-item.active") || document.querySelector(".chart-item");
      var idx = firstActive ? parseInt(firstActive.getAttribute("data-index") || "0", 10) : 0;
      switchChart(isNaN(idx) ? 0 : idx);
      // Keep plots responsive on window resize
      window.addEventListener("resize", function() {{
        var wrapper = document.querySelector(".chart-wrapper.active");
        _resizePlotlyWithin(wrapper);
      }});
    }});
  </script>
</body>
</html>"""
    output_path.write_text(html, encoding="utf-8")


def backtest_metrics(trades: List[Dict], equity_curve: pd.Series) -> Dict[str, float]:
    """Compute total_return_pct, n_trades, win_rate, max_drawdown_pct, sharpe_approx."""
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


def run_backtest(
    fetcher: ETFDataFetcher,
    tickers: List[str],
    start_date: Optional[Union[str, pd.Timestamp]] = None,
    end_date: Optional[Union[str, pd.Timestamp]] = None,
    periods: Optional[List[Dict[str, Any]]] = None,
    spread_pct: Optional[float] = None,
    hold_days: Optional[int] = None,
    take_profit_pct: Optional[float] = None,
    stop_loss_pct: Optional[float] = None,
    decision: Optional[str] = None,
    bot: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Simulation Orchestrator: Run backtest per ticker (and per period if periods given).
    
    Architecture:
    1. Simulation: Calls bot/decision based on time/event (bar-by-bar loop)
    2. Bot: Wraps decision + money management + exit logic (if bot provided)
    3. Decision: Generates BUY/SELL signals (pure signal logic)
    
    Flow:
    - If bot provided: Calls bot.signal_at_idx() for entry, bot.should_sell() for exit
    - If decision-only: Calls decision.signal_at_idx() for entry, fallback exit (hold_days/TP/SL)
    - Applies spread_pct to all trades
    - Tracks capital if fund is set
    
    Returns list of dicts: ticker, period_name (if periods), trades, equity_curve, metrics.
    """
    config = load_simulation_config(config_path)
    if spread_pct is None:
        spread_pct = config["spread_pct"]
    fund = config.get("fund")
    if decision is None:
        decision = config["decision"]
    if bot is None:
        bot = config["bot"]
    if periods is None:
        periods = config["periods"]
    # Exit params: from SMC config when bot=smc, else defaults for decision-only fallback
    if bot == "smc":
        from bot.smc import load_smc_config
        smc_cfg = load_smc_config()
        hold_days = hold_days if hold_days is not None else smc_cfg["hold_days"]
        take_profit_pct = take_profit_pct if take_profit_pct is not None else smc_cfg["take_profit_pct"]
        stop_loss_pct = stop_loss_pct if stop_loss_pct is not None else smc_cfg["stop_loss_pct"]
    else:
        hold_days = hold_days if hold_days is not None else 20
        take_profit_pct = take_profit_pct if take_profit_pct is not None else 15.0
        stop_loss_pct = stop_loss_pct if stop_loss_pct is not None else None

    # Resolve decision module (entry signal only)
    if decision == "dip_buy":
        from decision.dip_buy import load_params, signal_at_idx
        dip_params = load_params(Path(__file__).resolve().parent.parent / "decision" / "dip.yaml")
        need_bars = max(
            dip_params.trend_days + dip_params.slope_lookback_days + 2,
            dip_params.dip_days + 2,
        )

        def _signal(df: pd.DataFrame, idx: int) -> bool:
            return signal_at_idx(df, idx, dip_params)
    else:
        raise ValueError(f"Unknown decision: {decision}")

    # Optional bot (e.g. SMC): asked at each bar for entry (signal_at_idx) and exit (should_sell)
    bot_instance = None
    if bot == "smc":
        from bot.smc import create_bot
        bot_instance = create_bot(initial_fund=fund)  # loads bot/smc/config.yaml, initializes with fund

    start_ts = _parse_date(start_date) if isinstance(start_date, str) else start_date
    end_ts = _parse_date(end_date) if isinstance(end_date, str) else end_date

    if not periods:
        periods = [{"name": "default", "start_date": start_date, "end_date": end_date}]

    results: List[Dict[str, Any]] = []
    chart_items: List[tuple] = []
    result_dir = Path(__file__).resolve().parent.parent / "result"
    calendar_days = fetcher._calendar_days_for_trading_window(
        max(need_bars, hold_days) + 60
    )
    history, errors = fetcher.fetch_history_days(calendar_days, tickers=tickers)

    for ticker in tickers:
        if ticker not in history or history[ticker] is None or history[ticker].empty:
            continue
        df = history[ticker].sort_index()
        if "Close" not in df.columns:
            continue
        for period in periods:
            p_start = _parse_date(period.get("start_date")) if period.get("start_date") else start_ts
            p_end = _parse_date(period.get("end_date")) if period.get("end_date") else end_ts
            trades, equity, final_capital = _run_single_backtest_decision_only(
                df,
                _signal,
                need_bars,
                hold_days,
                take_profit_pct,
                stop_loss_pct,
                spread_pct,
                start_ts=p_start,
                end_ts=p_end,
                bot=bot_instance,
                fund=fund,
                ticker=ticker,
            )
            metrics = backtest_metrics(trades, equity)
            period_name = period.get("name", "default")
            out = {
                "ticker": ticker,
                "period_name": period_name,
                "trades": trades,
                "equity_curve": equity,
                **metrics,
            }
            if fund is not None:
                out["fund"] = fund
                out["final_capital"] = final_capital
            results.append(out)
            # Collect for single HTML (dropdown to show one chart at a time)
            df_slice = df.copy()
            if p_start is not None:
                df_slice = df_slice[df_slice.index >= p_start]
            if p_end is not None:
                df_slice = df_slice[df_slice.index <= p_end]
            if not df_slice.empty:
                chart_items.append((ticker, period_name, df_slice, trades))
    write_simulation_charts_single_html(
        chart_items,
        result_dir / "simulation_charts.html",
        initial_fund=fund,
        bot=bot_instance,  # Pass bot so fund chart can use actual cash state
    )
    return results


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Bot simulation backtest")
    parser.add_argument("--tickers", nargs="*", default=None, help="Tickers (default: all from etf.yaml)")
    parser.add_argument("--config", type=str, default=None, help="Path to simulation.yaml")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tickers")
    args = parser.parse_args()
    config_path = Path(args.config) if args.config else None
    fetcher = ETFDataFetcher()
    tickers = args.tickers or list(fetcher.tickers_map.keys())
    if args.limit:
        tickers = tickers[: args.limit]
    results = run_backtest(fetcher, tickers, config_path=config_path)
    result_dir = Path(__file__).resolve().parent.parent / "result"
    for r in results:
        line = f"{r['ticker']} ({r['period_name']}): n_trades={r['n_trades']} total_return_pct={r['total_return_pct']:.2f} win_rate={r['win_rate']:.1f}"
        if r.get("fund") is not None and r.get("final_capital") is not None:
            line += f" fund=${r['fund']:.0f} final_capital=${r['final_capital']:.2f}"
        print(line)
    print(f"Charts: {result_dir}/simulation_charts.html")


if __name__ == "__main__":
    main()
