# Architecture: Clear Separation of Responsibilities

## Overview

Three-layer architecture with clear responsibilities:

```
┌─────────────────────────────────────┐
│  1. Simulation (Orchestrator)       │
│     - Calls bot based on time/event │
│     - Manages backtest loop          │
│     - Applies spread_pct            │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  2. Bot (Strategy + Risk Manager)    │
│     - Wraps Decision (interchange) │
│     - Money Management              │
│     - Exit Logic                    │
│     - Position Sizing              │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  3. Decision (Signal Generator)    │
│     - Generate BUY signals          │
│     - Generate SELL signals         │
│     - Pure signal logic only        │
│     - No money management           │
└─────────────────────────────────────┘
```

---

## 1. Simulation (Orchestrator)

**File:** `bot/simulation.py`

**Responsibilities:**
- **Time/Event Management:** Iterate through bars, call bot at correct intervals
- **Trade Execution:** Record entries/exits, apply `spread_pct`
- **Capital Tracking:** Track fund changes across trades
- **Metrics:** Calculate returns, win rate, drawdown

**What it does NOT do:**
- ❌ Generate signals (bot/decision does this)
- ❌ Decide position size (bot does this)
- ❌ Exit logic (bot does this)

**API:**
```python
run_backtest(
    fetcher, tickers, 
    bot=None,  # Bot instance (or None for decision-only)
    decision=None,  # Decision name if no bot
    ...
)
```

**Flow:**
```
For each bar:
  1. If not in position:
     - Call bot.signal_at_idx() or decision.signal_at_idx()
     - If BUY signal: Enter position
  2. If in position:
     - Call bot.should_sell() (or decision.signal_at_idx() for SELL)
     - If SELL signal: Exit position
  3. Apply spread_pct, record trade
```

---

## 2. Bot (Strategy + Risk Manager)

**Files:** `bot/smc/__init__.py`, `bot/smc/config.yaml`

**Responsibilities:**
- **Wrap Decision:** Load and use interchangeable decision module
- **Entry Gating:** Apply bot-specific filters (e.g., SMC structure, liquidity sweep)
- **Exit Logic:** Decide when to sell (structure-based, time-based, TP/SL)
- **Money Management:**
  - Position sizing (`position_size()`)
  - Risk management
  - Capital allocation

**What it does NOT do:**
- ❌ Generate raw signals (decision does this)
- ❌ Manage time/events (simulation does this)

**API:**
```python
class Bot:
    def signal_at_idx(df, idx, decision_signal: bool) -> bool:
        """Entry decision: combines decision signal + bot filters"""
        
    def should_sell(df, idx, entry_price, entry_idx) -> bool:
        """Exit decision: bot-specific exit logic"""
        
    def position_size(available_fund, df, idx) -> float:
        """Money management: how much $ to risk"""
```

**Current Implementation:**
- **SMC Bot:** Stub implementation
  - Entry: Passes through decision signal (future: add SMC filters)
  - Exit: Time/TP/SL fallback (future: structure-based)
  - Position: Configurable % of capital

---

## 3. Decision (Signal Generator)

**Files:** `decision/dip_buy.py`, `decision/dip.yaml`

**Responsibilities:**
- **Generate BUY signals:** When to enter
- **Generate SELL signals:** When to exit (if decision has exit logic)
- **Pure Signal Logic:** Technical indicators, patterns, conditions
- **No Money Management:** No position sizing, no risk rules

**What it does NOT do:**
- ❌ Position sizing
- ❌ Risk management
- ❌ Capital tracking

**API:**
```python
def signal_at_idx(df: pd.DataFrame, idx: int, params) -> bool:
    """Return True for BUY signal at bar idx"""
    # Uses only df.iloc[:idx+1] (no look-ahead)
    
def should_sell_at_idx(df: pd.DataFrame, idx: int, entry_price: float, entry_idx: int, params) -> bool:
    """Return True for SELL signal at bar idx (optional)"""
    # Some decisions may have exit logic
```

**Current Implementation:**
- **dip_buy:** Only BUY signals (no exit logic)
  - Checks: Trend vs SMA, SMA slope, dip condition, min dip threshold
  - Exit handled by bot (SMC) or simulation fallback

**Future Decisions:**
- `momentum_buy`: Momentum-based entry
- `mean_reversion`: Mean reversion entry + exit
- `trend_following`: Trend following with exit rules

---

## Data Flow Example

```
Simulation Loop (bar-by-bar):
  ↓
  [Bar idx=100]
  ↓
  Simulation: "Are we in position?" → No
  ↓
  Simulation: Call bot.signal_at_idx(df, 100, decision_signal)
  ↓
  Bot: Call decision.signal_at_idx(df, 100) → True (BUY signal)
  ↓
  Bot: Apply bot filters → True (passes SMC check)
  ↓
  Bot: Calculate position_size() → $1000
  ↓
  Simulation: Enter position at Open[101] with $1000
  ↓
  [Bar idx=101]
  ↓
  Simulation: "Are we in position?" → Yes
  ↓
  Simulation: Call bot.should_sell(df, 101, entry_price, entry_idx)
  ↓
  Bot: Check exit conditions → False (hold)
  ↓
  [Bar idx=102]
  ↓
  Simulation: Call bot.should_sell(df, 102, entry_price, entry_idx)
  ↓
  Bot: Check exit conditions → True (TP hit)
  ↓
  Simulation: Exit position at Close[102], apply spread_pct, record trade
```

---

## Configuration Files

### `bot/simulation.yaml`
- `spread_pct`: Trading cost
- `fund`: Initial capital
- `periods`: Backtest periods
- `decision`: Decision module name (if no bot)
- `bot`: Bot name (e.g., "smc")

### `bot/smc/config.yaml`
- `decision`: Which decision module to use (interchangeable)
- `hold_days`, `take_profit_pct`, `stop_loss_pct`: Exit rules
- `position_pct`: Money management (% of capital per trade)

### `decision/dip.yaml`
- `trend_days`, `dip_days`, etc.: Signal generation parameters only
- No exit rules (bot handles exit)
- No money management (bot handles sizing)

---

## Benefits of This Architecture

1. **Interchangeable Decisions:** Swap `dip_buy` for `momentum_buy` without changing bot
2. **Reusable Bots:** Same bot can use different decisions
3. **Clear Responsibilities:** Each layer has one job
4. **Testable:** Test decision signals independently from bot logic
5. **Extensible:** Add new decisions or bots without touching simulation

---

## Future Enhancements

1. **Decision with Exit Logic:** Some decisions may generate SELL signals
   - Bot can use decision's exit signal OR bot's own exit logic
   - Priority: Bot exit logic > Decision exit signal

2. **Multiple Decisions:** Bot could combine multiple decision signals
   - Example: Require both `dip_buy` AND `momentum_buy` to agree

3. **Dynamic Position Sizing:** Bot could adjust size based on:
   - Market volatility
   - Account equity
   - Risk per trade
