# dont read this file it a temp /draft


## Decision 6: Multi-Indicator Composite

### Objective
Combine multiple indicators to generate more reliable signals. Reduces false signals by requiring confirmation from multiple sources. Best for robust trading strategies.

### Rules

#### Indicator Combination
Uses a weighted combination of:
1. **RSI** (weight: 0.25) - Momentum
2. **MACD** (weight: 0.25) - Trend and momentum
3. **Moving Average Crossover** (weight: 0.20) - Trend direction
4. **Bollinger Bands** (weight: 0.15) - Volatility and mean reversion
5. **Stochastic Oscillator** (weight: 0.15) - Momentum and reversals

#### Buy Signals
Requires at least 3 out of 5 indicators to agree:
1. **Strong Consensus:** 4-5 indicators bullish → strong buy signal
2. **Moderate Consensus:** 3 indicators bullish → buy signal
3. **Trend Confirmation:** MACD + MA both bullish → trend buy signal
4. **Momentum Confirmation:** RSI + Stochastic both bullish → momentum buy signal

#### Sell Signals
Requires at least 3 out of 5 indicators to agree:
1. **Strong Consensus:** 4-5 indicators bearish → strong sell signal
2. **Moderate Consensus:** 3 indicators bearish → sell signal
3. **Trend Confirmation:** MACD + MA both bearish → trend sell signal
4. **Momentum Confirmation:** RSI + Stochastic both bearish → momentum sell signal

#### Score Generation
- Calculate individual scores from each indicator (normalized to -1.0 to 1.0)
- Apply weights and sum: `composite_score = Σ(weight_i × score_i)`
- Apply consensus multiplier:
  - **5 indicators agree:** Multiply by 1.2 (strong signal)
  - **4 indicators agree:** Multiply by 1.1 (moderate signal)
  - **3 indicators agree:** Multiply by 1.0 (normal signal)
  - **2 indicators agree:** Multiply by 0.5 (weak signal, reduce score)
  - **1 indicator agrees:** Multiply by 0.0 (no consensus, neutral)
- Clamp final score to [-1.0, 1.0]

#### Configuration Parameters
- `rsi_period`: RSI lookback (default: 14)
- `macd_fast`: MACD fast period (default: 12)
- `macd_slow`: MACD slow period (default: 26)
- `macd_signal`: MACD signal period (default: 9)
- `ma_fast`: Fast MA period (default: 20)
- `ma_slow`: Slow MA period (default: 50)
- `bb_period`: Bollinger Bands period (default: 20)
- `bb_std`: Bollinger Bands std multiplier (default: 2.0)
- `stoch_k`: Stochastic %K period (default: 14)
- `stoch_d`: Stochastic %D period (default: 3)
- `consensus_threshold`: Minimum indicators needed to agree (default: 3)
- `weights`: Dictionary of weights for each indicator (default: as above)

---
