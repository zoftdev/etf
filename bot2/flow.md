# Daily Evaluation Flow

## Overview

This document describes the flow of daily bot evaluation where the simulator asks the bot once per day, the bot evaluates all symbols using the decision module, and selects top-scoring opportunities.

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  SIMULATOR (Once Per Day)                                    │
│                                                               │
│  For each trading day:                                        │
│    1. Advance to next trading day                            │
│    2. Call bot.evaluate_daily(as_of_date, tickers)          │
│    3. Receive list of buy/sell signals                       │
│    4. Execute trades                                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  BOT (Daily Evaluation)                                      │
│                                                               │
│  evaluate_daily(as_of_date, tickers):                        │
│    1. Read data from fetcher (up to as_of_date)             │
│       ⚠️  NO FUTURE DATA - only data <= as_of_date           │
│                                                               │
│    2. For each ticker in tickers:                           │
│       a. Get historical data from fetcher                    │
│          (sliced to as_of_date, no look-ahead)               │
│       b. Call decision.score(ticker, data, as_of_date)       │
│       c. Collect: (ticker, score, action)                   │
│                                                               │
│    3. Sort results by score (descending)                     │
│                                                               │
│    4. Select top N opportunities:                            │
│       - Filter by minimum score threshold                   │
│       - Apply bot-specific filters (risk, position limits)    │
│       - Return list of (ticker, action, score)              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  DECISION (Score Generation)                                 │
│                                                               │
│  score(ticker, data, as_of_date) -> float:                   │
│    1. Analyze data up to as_of_date                          │
│       ⚠️  NO LOOK-AHEAD - only use data <= as_of_date       │
│                                                               │
│    2. Calculate technical indicators                         │
│    3. Detect patterns (dips, breakouts, etc.)              │
│    4. Generate score:                                         │
│       - Score range: -1.0 to 1.0                            │
│       - -1.0 = strong SELL signal                            │
│       - 0.0 = HOLD (no signal)                               │
│       - 1.0 = strong BUY signal                              │
│       - Higher score = better opportunity                    │
│                                                               │
│    5. Return score (float, normalized to -1.0 to 1.0)        │
└─────────────────────────────────────────────────────────────┘
```
 
## Key Principles

### 1. No Look-Ahead
- **Fetcher**: Only returns data up to `as_of_date`
- **Decision**: Only analyzes data where `index <= as_of_date`
- **Bot**: Passes `as_of_date` to all components

### 2. Score-Based Selection
- **Decision returns score**: Float value normalized to -1.0 to 1.0
  - **-1.0** = strong SELL signal
  - **0.0** = HOLD (no signal)
  - **1.0** = strong BUY signal
- **Bot sorts by score**: Best opportunities first (highest scores)
- **Bot filters top N**: Selects highest-scoring opportunities

### 3. Daily Evaluation
- **Once per day**: Simulator calls bot once per trading day
- **All symbols evaluated**: Bot evaluates all tickers in one pass
- **Batch processing**: Efficient evaluation of multiple symbols

## Example Flow

### Day 1 (2024-01-15)

```
Simulator: "Bot, evaluate all tickers as of 2024-01-15"

Bot:
  1. Fetch data for SPY (up to 2024-01-15)
  2. Call decision.score("SPY", data, 2024-01-15) → score: 8.5
  3. Fetch data for QQQ (up to 2024-01-15)
  4. Call decision.score("QQQ", data, 2024-01-15) → score: 6.2
  5. Fetch data for DIA (up to 2024-01-15)
  6. Call decision.score("DIA", data, 2024-01-15) → score: 3.1
  
  Sort: [SPY: 8.5, QQQ: 6.2, DIA: 3.1]
  Select top 2: [SPY: BUY, QQQ: BUY]

Bot returns: [
  {"ticker": "SPY", "action": "BUY", "score": 8.5},
  {"ticker": "QQQ", "action": "BUY", "score": 6.2}
]

Simulator: Execute BUY for SPY and QQQ
```

### Day 2 (2024-01-16)

```
Simulator: "Bot, evaluate all tickers as of 2024-01-16"

Bot:
  1. Fetch data for SPY (up to 2024-01-16) ← includes 2024-01-16 data
  2. Call decision.score("SPY", data, 2024-01-16) → score: 7.8
  3. Fetch data for QQQ (up to 2024-01-16)
  4. Call decision.score("QQQ", data, 2024-01-16) → score: 4.5
  5. Fetch data for DIA (up to 2024-01-16)
  6. Call decision.score("DIA", data, 2024-01-16) → score: 9.2
  
  Sort: [DIA: 9.2, SPY: 7.8, QQQ: 4.5]
  Select top 2: [DIA: BUY, SPY: BUY]
  (SPY already in position, may hold or add)

Bot returns: [
  {"ticker": "DIA", "action": "BUY", "score": 9.2},
  {"ticker": "SPY", "action": "BUY", "score": 7.8}
]

Simulator: Execute BUY for DIA, maintain SPY position
```

## Exit Decisions

### Overview

Exit decisions are handled during the daily evaluation process. The bot evaluates all tickers each day, including those with open positions, and determines whether to exit based on decision scores and bot-specific exit rules.

### Exit Flow

```
┌─────────────────────────────────────────────────────────────┐
│  BOT (Daily Evaluation - Exit Handling)                      │
│                                                               │
│  evaluate_daily(as_of_date, tickers):                       │
│                                                               │
│  1. Evaluate all tickers (including open positions)          │
│     - Call decision.score() for each ticker                 │
│                                                               │
│  2. Check existing positions:                                │
│     For each open position:                                  │
│     a. Get current score from decision                       │
│     b. Apply exit rules:                                     │
│        - Decision score < sell_threshold → SELL            │
│        - Bot-specific exit rules (time, profit, loss)        │
│        - Position ranking falls below top N → SELL        │
│                                                               │
│  3. Combine entry and exit signals:                         │
│     - New BUY signals (from top N)                         │
│     - SELL signals (from existing positions)                 │
│                                                               │
│  4. Return unified signal list                               │
└─────────────────────────────────────────────────────────────┘
```

### Exit Decision Methods

#### Method 1: Decision Score-Based Exit

- **Decision returns negative score** → SELL signal
- Bot checks if score falls below sell_threshold
- If position exists and score indicates exit → SELL

Example:
```
Position: SPY (held since 2024-01-15)
Day 5 (2024-01-20):
  - decision.score("SPY") → -0.8 (negative = exit signal)
  - Bot: score < sell_threshold (-0.3) → SELL SPY
```

#### Method 2: Ranking-Based Exit

- Bot maintains top N positions
- If held position falls out of top N → SELL
- Replaced by higher-scoring opportunity

Example:
```
Current positions: [SPY: 8.5, QQQ: 6.2]
Day 3 evaluation:
  Scores: [DIA: 9.2, SPY: 7.8, QQQ: 4.5, IWM: 5.1]
  Top 2: [DIA: 9.2, SPY: 7.8]
  QQQ falls out of top 2 → SELL QQQ
  DIA enters top 2 → BUY DIA
```

#### Method 3: Bot-Specific Exit Rules

- **Time-based**: Max hold days exceeded
- **Profit target**: Exit when profit target reached
- **Stop loss**: Exit when stop loss hit
- **Structure-based**: SMC exit conditions (e.g., structure break)

Example:
```
Position: SPY (entry: $400, current: $420)
Bot rules:
  - Profit target: 5% → SELL (5% profit reached)
  - Max hold: 10 days → SELL (if held 10+ days)
  - Stop loss: -3% → HOLD (no stop loss hit)
```

### Complete Daily Evaluation Flow with Exits

```
Day 1 (2024-01-15):
  Bot evaluates all tickers
  Scores: [SPY: 8.5, QQQ: 6.2, DIA: 3.1]
  Top 2: [SPY: BUY, QQQ: BUY]
  No existing positions → Execute BUY for SPY and QQQ

Day 2 (2024-01-16):
  Bot evaluates all tickers (including SPY, QQQ)
  Scores: [DIA: 9.2, SPY: 7.8, QQQ: 4.5]
  Top 2: [DIA: BUY, SPY: BUY]
  SPY still in top 2 → HOLD SPY
  QQQ falls out of top 2 → SELL QQQ
  DIA enters top 2 → BUY DIA

Day 3 (2024-01-17):
  Bot evaluates all tickers
  Scores: [SPY: 6.5, DIA: 5.2, QQQ: -3.1]
  Top 2: [SPY: BUY, DIA: BUY]
  SPY still in top 2 → HOLD SPY
  DIA still in top 2 → HOLD DIA
  (QQQ has negative score but not in position)

Day 4 (2024-01-18):
  Bot evaluates all tickers
  Scores: [SPY: 2.1, DIA: -4.5, QQQ: 8.2]
  Top 2: [QQQ: 8.2, SPY: 2.1]
  DIA score < sell_threshold (-3.0) → SELL DIA
  SPY still in top 2 → HOLD SPY
  QQQ re-enters top 2 → BUY QQQ
```

### Exit Decision Priority

1. **Bot-specific exit rules** (profit target, stop loss, max hold days)
2. **Decision score < sell_threshold** (strong SELL signal from decision)
3. **Ranking-based exit** (position falls out of top N)
4. **Decision score degradation** (significant drop from entry score)

### Exit Signal Generation

```
For each existing position:
  1. Get decision score for ticker
  2. Check bot exit rules:
     - Profit target reached? → SELL
     - Stop loss hit? → SELL
     - Max hold days exceeded? → SELL
  3. Check decision score:
     - Score < sell_threshold? → SELL
  4. Check ranking:
     - Position in top N? → HOLD
     - Position out of top N? → SELL (to make room)
  5. Return SELL signal if any condition met
```

### Key Points

- **Exits evaluated daily**: Same daily evaluation process checks both entry and exit
- **Decision scores can indicate exits**: Negative scores or scores below threshold signal exit
- **Bot applies exit rules**: Time-based, profit target, stop loss rules enforced by bot
- **Ranking-based exits**: Positions that fall out of top N may be exited to make room
- **All tickers evaluated**: Including those with open positions
- **Unified signal list**: Exit signals combined with entry signals in daily response

## Data Flow Constraints

```
┌─────────────┐
│  Fetcher    │
│             │
│  Returns:   │
│  data where │
│  date <=    │
│  as_of_date │
└──────┬──────┘
       │
       │ Historical data only
       │
       ▼
┌─────────────┐
│  Decision   │
│             │
│  Analyzes:  │
│  - Only     │
│    data <=  │
│    as_of_   │
│    date     │
│  - Returns  │
│    score    │
└──────┬──────┘
       │
       │ Score per ticker
       │
       ▼
┌─────────────┐
│  Bot        │
│             │
│  Actions:   │
│  1. Collect │
│     scores  │
│  2. Sort    │
│  3. Select  │
│     top N   │
└──────┬──────┘
       │
       │ Top opportunities
       │
       ▼
┌─────────────┐
│  Simulator  │
│             │
│  Executes:  │
│  - BUY      │
│  - SELL     │
│  - HOLD     │
└─────────────┘
```
