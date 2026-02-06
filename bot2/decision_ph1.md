# Decision Modules Phase 1: Objectives and Rules

## Overview

This document defines 6 decision modules for the Bot2 system. Each module generates buy/sell signals based on technical indicators using OHLC price data only (no volume required).

All decision modules follow the same interface:
- **Input:** `(ticker, data, as_of_date)` where `data` contains OHLC columns
- **Output:** `score` (float, normalized to -1.0 to 1.0)
  - `-1.0` = strong SELL signal
  - `0.0` = HOLD (no signal)
  - `1.0` = strong BUY signal
- **Constraint:** Only use data where `index <= as_of_date` (no look-ahead)

---

## Decision 1: RSI Momentum

### Objective
Identify overbought/oversold conditions and momentum shifts using Relative Strength Index. Best for swing trading and mean reversion strategies.

### Rules

#### Buy Signals
1. **Oversold Entry:** RSI < 30 → generate buy signal
2. **Oversold Recovery:** RSI crosses above 30 from below → stronger buy signal
3. **Bullish Divergence:** Price makes lower low while RSI makes higher low → strong buy signal
4. **Momentum Shift:** RSI crosses above 50 from below → trend reversal buy signal

#### Sell Signals
1. **Overbought Exit:** RSI > 70 → generate sell signal
2. **Overbought Rejection:** RSI crosses below 70 from above → stronger sell signal
3. **Bearish Divergence:** Price makes higher high while RSI makes lower high → strong sell signal
4. **Momentum Shift:** RSI crosses below 50 from above → trend reversal sell signal

#### Score Generation
- **Strong Buy (0.8-1.0):** RSI < 20 OR bullish divergence detected
- **Buy (0.5-0.8):** RSI < 30 OR RSI crosses above 30
- **Weak Buy (0.2-0.5):** RSI crosses above 50 from below
- **Neutral (0.0):** RSI between 30-70 with no crossovers
- **Weak Sell (-0.2 to -0.5):** RSI crosses below 50 from above
- **Sell (-0.5 to -0.8):** RSI > 70 OR RSI crosses below 70
- **Strong Sell (-0.8 to -1.0):** RSI > 80 OR bearish divergence detected

#### Configuration Parameters
- `rsi_period`: Lookback period (default: 14)
- `oversold_threshold`: RSI level for oversold (default: 30)
- `overbought_threshold`: RSI level for overbought (default: 70)
- `divergence_lookback`: Bars to check for divergence (default: 20)

---

## Decision 2: MACD Trend

### Objective
Identify trend direction and momentum changes using Moving Average Convergence Divergence. Best for trend-following strategies.

### Rules

#### Buy Signals
1. **Bullish Crossover:** MACD line crosses above signal line → buy signal
2. **Zero Line Cross:** MACD crosses above zero → strong buy signal
3. **Bullish Divergence:** Price makes lower low while MACD makes higher low → strong buy signal
4. **Histogram Expansion:** MACD histogram increases (becomes more positive) → momentum buy signal

#### Sell Signals
1. **Bearish Crossover:** MACD line crosses below signal line → sell signal
2. **Zero Line Cross:** MACD crosses below zero → strong sell signal
3. **Bearish Divergence:** Price makes higher high while MACD makes lower high → strong sell signal
4. **Histogram Contraction:** MACD histogram decreases (becomes more negative) → momentum sell signal

#### Score Generation
- **Strong Buy (0.8-1.0):** MACD crosses above zero AND bullish divergence
- **Buy (0.5-0.8):** MACD crosses above signal line OR MACD crosses above zero
- **Weak Buy (0.2-0.5):** MACD above signal line AND histogram expanding
- **Neutral (0.0):** MACD and signal line close together, no clear direction
- **Weak Sell (-0.2 to -0.5):** MACD below signal line AND histogram contracting
- **Sell (-0.5 to -0.8):** MACD crosses below signal line OR MACD crosses below zero
- **Strong Sell (-0.8 to -1.0):** MACD crosses below zero AND bearish divergence

#### Configuration Parameters
- `fast_period`: Fast EMA period (default: 12)
- `slow_period`: Slow EMA period (default: 26)
- `signal_period`: Signal line EMA period (default: 9)
- `divergence_lookback`: Bars to check for divergence (default: 20)

---

## Decision 3: Moving Average Crossover

### Objective
Identify trend direction and momentum using multiple moving averages. Best for trend-following and breakout strategies.

### Rules

#### Buy Signals
1. **Golden Cross:** Fast MA crosses above slow MA → strong buy signal
2. **Price Above MA:** Price crosses above moving average → buy signal
3. **MA Alignment:** Fast MA > Medium MA > Slow MA (all ascending) → trend confirmation buy
4. **Price Bounce:** Price bounces off moving average support → buy signal

#### Sell Signals
1. **Death Cross:** Fast MA crosses below slow MA → strong sell signal
2. **Price Below MA:** Price crosses below moving average → sell signal
3. **MA Alignment:** Fast MA < Medium MA < Slow MA (all descending) → trend confirmation sell
4. **Price Rejection:** Price rejects moving average resistance → sell signal

#### Score Generation
- **Strong Buy (0.8-1.0):** Golden cross detected AND price above all MAs
- **Buy (0.5-0.8):** Price crosses above fast MA OR golden cross
- **Weak Buy (0.2-0.5):** Price above fast MA but below slow MA
- **Neutral (0.0):** Price between MAs, no clear trend
- **Weak Sell (-0.2 to -0.5):** Price below fast MA but above slow MA
- **Sell (-0.5 to -0.8):** Price crosses below fast MA OR death cross
- **Strong Sell (-0.8 to -1.0):** Death cross detected AND price below all MAs

#### Configuration Parameters
- `fast_ma_period`: Fast moving average period (default: 20)
- `slow_ma_period`: Slow moving average period (default: 50)
- `ma_type`: "SMA" or "EMA" (default: "EMA")
- `trend_ma_period`: Optional third MA for trend confirmation (default: 200)

---

## Decision 4: Bollinger Bands Mean Reversion

### Objective
Identify overbought/oversold conditions and volatility breakouts using Bollinger Bands. Best for mean reversion and volatility-based strategies.

### Rules

#### Buy Signals
1. **Lower Band Touch:** Price touches or goes below lower band → oversold buy signal
2. **Lower Band Bounce:** Price bounces from lower band → strong buy signal
3. **Band Squeeze Expansion Up:** Band width expands upward after squeeze → breakout buy signal
4. **Mean Reversion:** Price moves from lower band toward middle band → buy signal

#### Sell Signals
1. **Upper Band Touch:** Price touches or goes above upper band → overbought sell signal
2. **Upper Band Rejection:** Price rejects upper band → strong sell signal
3. **Band Squeeze Expansion Down:** Band width expands downward after squeeze → breakdown sell signal
4. **Mean Reversion:** Price moves from upper band toward middle band → sell signal

#### Score Generation
- **Strong Buy (0.8-1.0):** Price touches lower band AND band width expanding upward
- **Buy (0.5-0.8):** Price touches lower band OR bounces from lower band
- **Weak Buy (0.2-0.5):** Price below middle band but above lower band
- **Neutral (0.0):** Price between bands, normal volatility
- **Weak Sell (-0.2 to -0.5):** Price above middle band but below upper band
- **Sell (-0.5 to -0.8):** Price touches upper band OR rejects upper band
- **Strong Sell (-0.8 to -1.0):** Price touches upper band AND band width expanding downward

#### Configuration Parameters
- `bb_period`: Moving average period (default: 20)
- `bb_std`: Standard deviation multiplier (default: 2.0)
- `squeeze_threshold`: Band width threshold for squeeze detection (default: 0.1)
- `ma_type`: "SMA" or "EMA" (default: "SMA")

---

## Decision 5: Stochastic Oscillator

### Objective
Identify potential reversals and momentum shifts using Stochastic Oscillator. Best for identifying turning points and overbought/oversold conditions.

### Rules

#### Buy Signals
1. **Oversold Crossover:** %K crosses above %D below 20 → oversold reversal buy signal
2. **Oversold Zone:** Both %K and %D below 20 → strong oversold buy signal
3. **Bullish Divergence:** Price makes lower low while Stochastic makes higher low → strong buy signal
4. **Momentum Shift:** %K crosses above %D from oversold zone → buy signal

#### Sell Signals
1. **Overbought Crossover:** %K crosses below %D above 80 → overbought reversal sell signal
2. **Overbought Zone:** Both %K and %D above 80 → strong overbought sell signal
3. **Bearish Divergence:** Price makes higher high while Stochastic makes lower high → strong sell signal
4. **Momentum Shift:** %K crosses below %D from overbought zone → sell signal

#### Score Generation
- **Strong Buy (0.8-1.0):** Both %K and %D below 10 OR bullish divergence
- **Buy (0.5-0.8):** %K crosses above %D below 20 OR both below 20
- **Weak Buy (0.2-0.5):** %K crosses above %D between 20-50
- **Neutral (0.0):** %K and %D between 20-80, no clear signal
- **Weak Sell (-0.2 to -0.5):** %K crosses below %D between 50-80
- **Sell (-0.5 to -0.8):** %K crosses below %D above 80 OR both above 80
- **Strong Sell (-0.8 to -1.0):** Both %K and %D above 90 OR bearish divergence

#### Configuration Parameters
- `stoch_k_period`: %K period (default: 14)
- `stoch_d_period`: %D smoothing period (default: 3)
- `oversold_threshold`: Oversold level (default: 20)
- `overbought_threshold`: Overbought level (default: 80)
- `divergence_lookback`: Bars to check for divergence (default: 20)

---

## Common Rules for All Decision Modules

### Data Constraints
- **No Look-Ahead:** Only use data where `index <= as_of_date`
- **Minimum Data:** Require minimum number of bars before generating signals (typically 50-200 bars depending on indicator)
- **Data Validation:** Check for missing values, handle gaps appropriately

### Score Normalization
- All scores must be normalized to range [-1.0, 1.0]
- Use clamping or sigmoid functions to ensure bounds
- Handle edge cases (division by zero, NaN values)

### Signal Filtering
- **Minimum Score Threshold:** Only return non-zero scores above threshold (e.g., ±0.1)
- **Signal Persistence:** Avoid rapid signal flipping (consider cooldown periods)
- **Trend Context:** Consider overall trend before generating counter-trend signals

### Performance Considerations
- Cache indicator calculations when possible
- Use vectorized operations for efficiency
- Avoid redundant calculations across multiple indicators

---

## Implementation Notes

### Module Structure
Each decision module should:
1. Load configuration from YAML file
2. Validate parameters and set defaults
3. Calculate required indicators
4. Apply rules to generate signals
5. Convert signals to normalized score
6. Return score (float)

### Testing Requirements
- Test with historical data
- Verify no look-ahead bias
- Test edge cases (insufficient data, NaN values, extreme values)
- Validate score ranges are always [-1.0, 1.0]

### Configuration Files
Each decision module should have a corresponding YAML config file:
- `decision_rsi.yaml`
- `decision_macd.yaml`
- `decision_ma_crossover.yaml`
- `decision_bollinger.yaml`
- `decision_stochastic.yaml`
- `decision_composite.yaml`
