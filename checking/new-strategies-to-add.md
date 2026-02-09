# New strategy candidates (next additions)

These are **single-asset / per-ETF** strategies that fit our current harness (one ticker at a time).

When adding, follow existing pattern:
- implement `strat_*` in `checking/strategy_backtest_lib.py`
- add a default key in `available_strategies()` (one canonical config)
- add variant grid entries in `checking/tool_run_variants_grid.py` (param sweep)

---

## A) MACD Trend (signal-line crossover)
**Rule (long-only):**
- MACD line = EMA(fast) - EMA(slow)
- Signal line = EMA(signal) of MACD line
- Enter when MACD crosses above Signal
- Exit when MACD crosses below Signal

**Params to sweep:**
- `fast_span`: [8, 12, 16]
- `slow_span`: [20, 26, 35]
- `signal_span`: [5, 9, 12]
- (optional) `use_zero_filter`: [False, True]  (only take longs when MACD > 0)

**Variant key format:**
- `macd_{fast}_{slow}_{signal}_zf{0|1}`

---

## B) Keltner Channel Breakout
**Definition:**
- Mid = EMA(window)
- Band = ATR(window_atr) * multiplier
- Upper = Mid + Band, Lower = Mid - Band

**Rule (breakout, long-only):**
- Enter when Close > Upper
- Exit when Close < Mid  (or Close < Lower if you want slower exits)

**Params to sweep:**
- `ema_window`: [20, 50]
- `atr_window`: [10, 20]
- `atr_mult`: [1.5, 2.0, 2.5]
- `exit_rule`: ["mid", "lower"]

**Variant key format:**
- `kelt_{emaW}_{atrW}_m{mult}_x{exit}` (mult with p e.g. 2p0)

**Note:** ATR requires High/Low/Close. If we only have Close, approximate TR using abs(close-close.shift(1)) (less ideal). Better: fetch OHLC if available.

---

## C) Stochastic RSI Mean Reversion
**Rule (long-only):**
- Compute RSI(window)
- StochRSI = (RSI - min(RSI, stoch_window)) / (max(RSI, stoch_window) - min(...))
- Enter when StochRSI < entry (oversold)
- Exit when StochRSI > exit (reversion)

**Params to sweep:**
- `rsi_window`: [14]
- `stoch_window`: [14, 21]
- `smooth_k`: [1, 3]
- `smooth_d`: [1, 3]
- `entry`: [0.1, 0.2]
- `exit`: [0.8, 0.9]
- `max_hold_days`: [None, 10, 30]

**Variant key format:**
- `stochrsi_r{rsi}_s{stoch}_k{K}_d{D}_e{entry}_x{exit}_mh{N|days}`
