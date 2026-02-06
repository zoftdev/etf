# Bot2 Architecture: Roles and Responsibilities

## Overview

Bot2 is a clean rewrite of the bot system with clear separation of concerns. The system consists of three distinct layers, each with well-defined responsibilities and boundaries.

```
┌─────────────────────────────────────────┐
│  1. Simulator (Orchestrator)             │
│     - Time/event management              │
│     - Trade execution                    │
│     - Results collection                  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  2. Bot (Strategy + Risk Manager)        │
│     - Wraps Decision module              │
│     - Money management                    │
│     - Entry/exit gating                  │
│     - Position sizing                    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  3. Decision (Signal Generator)         │
│     - Generate BUY signals                │
│     - Generate SELL signals (optional)   │
│     - Pure signal logic                  │
└─────────────────────────────────────────┘
```

---

## 1. Simulator (Orchestrator)

### Role
The Simulator is the top-level orchestrator that manages the backtesting workflow. It controls the flow of time, executes trades, and collects results.

### Responsibilities

#### Time and Event Management
- Iterate through historical data bar-by-bar
- Maintain simulation state (current bar index, dates, periods)
- Handle multiple tickers and time periods
- Enforce simulation boundaries (start/end dates, period limits)

#### Trade Execution
- Execute entry trades when signals are received
- Execute exit trades when conditions are met
- Apply trading costs (spread, commissions)
- Record trade details (entry/exit prices, dates, returns)

#### Capital Tracking
- Track initial capital
- Monitor capital changes across trades
- Ensure capital consistency (no negative balances)
- Calculate final capital and returns

#### Results Collection
- Aggregate trades across all tickers and periods
- Calculate performance metrics (total return, win rate, drawdown)
- Generate charts and visualizations
- Export results to files

### What Simulator Does NOT Do
- ❌ Generate trading signals (Bot/Decision does this)
- ❌ Decide position sizes (Bot does this)
- ❌ Determine exit conditions (Bot does this)
- ❌ Manage cash/invested state (Bot does this)
 

### Key Principles
- **No Look-Ahead:** Simulator only uses data up to current bar index
- **Deterministic:** Same inputs produce same outputs
- **Stateless:** Simulator doesn't maintain trading state (Bot does)
- **Orchestration Only:** Simulator coordinates, doesn't decide

---

## 2. Bot (Strategy + Risk Manager)

### Role
The Bot is the strategy and risk management layer. It wraps a Decision module, applies its own filters and logic, and manages capital allocation.

### Responsibilities

#### Decision Module Wrapping
- Load and instantiate Decision module (interchangeable)
- Call Decision to get raw signals
- Apply bot-specific filters on top of Decision signals
- Combine multiple Decision signals if needed

#### Entry Gating
- Apply bot-specific entry filters (e.g., SMC structure, liquidity sweep)
- Check market conditions before entry
- Validate entry signals from Decision
- Gate entries based on bot state (e.g., max positions, cooldown periods)

#### Exit Logic
- When get sale signal from decisioner
- Apply exit rules (time-based, profit target, stop loss, structure-based)
- Handle forced exits (end of period, max hold time)
- Cancel unpaired positions when needed

#### Money Management
- **Cash State:** Track available cash across all tickers
- **Invested State:** Track total invested capital across all positions
- **Position Sizing:** Calculate how much capital to allocate per trade
- **Risk Management:** Ensure no over-investment, prevent negative balances
- **Capital Allocation:** Manage shared capital pool across multiple tickers

#### Position Tracking
- Track open positions per ticker
- Monitor position sizes and entry prices
- Calculate position values and returns

### What Bot Does NOT Do
- ❌ Generate raw signals (Decision does this)
- ❌ Manage time/events (Simulator does this)
- ❌ Execute trades (Simulator does this)
- ❌ Calculate metrics (Simulator does this)

### Key Principles
- **Stateful:** Bot maintains cash/invested state across all tickers
- **Interchangeable Decisions:** Can swap Decision modules without changing Bot
- **Capital Pool:** Single cash pool shared across all tickers
- **Risk First:** Bot enforces risk rules before executing trades
 

---

## 3. Decision (Signal Generator)

### Role
The Decision module is a pure signal generator. It analyzes market data and produces BUY/SELL signals based on technical conditions.

### Responsibilities

#### Signal Generation
- **BUY Signals:** Determine when market conditions favor entry
- **SELL Signals:** Determine when market conditions favor exit (optional)
- Analyze technical indicators, patterns, and conditions
- Apply signal filters (trend, momentum, mean reversion, etc.)

#### Technical Analysis
- Calculate indicators (SMA, EMA, RSI, MACD, etc.)
- Detect patterns (dips, breakouts, reversals, etc.)
- Apply filters (trend direction, volatility, volume, etc.)
- Combine multiple conditions into signals

#### Configuration
- Load parameters from YAML config files
- Expose configurable parameters (lookback periods, thresholds, etc.)
- Support parameter validation and defaults

### What Decision Does NOT Do
- ❌ Position sizing (Bot does this)
- ❌ Risk management (Bot does this)
- ❌ Capital tracking (Bot does this)
- ❌ Exit timing (Bot handles this, though Decision can suggest)
 
### Key Principles
- **Pure Logic:** No side effects, no state (except internal caching for performance)
- **No Look-Ahead:** Only uses data up to current bar index
- **Stateless:** Same inputs produce same outputs
- **Interchangeable:** Can be swapped without changing Bot/Simulator
 

---

## Configuration Hierarchy

### Simulator Config
- Simulation parameters (periods, initial fund, spread)
- Which Bot to use
- Output settings (charts, reports)

### Bot Config
- Which Decision module to use
- Bot-specific parameters (position sizing, exit rules)
- Risk management settings

### Decision Config
- Signal generation parameters (lookback periods, thresholds)
- Technical indicator settings
- Filter conditions

---
 

## Implementation Notes
 
### State Management
- **Simulator:** Stateless (doesn't maintain trading state)
- **Bot:** Stateful (maintains cash/invested state across all tickers)
- **Decision:** Stateless (pure signal generation, no state)

  
