# Strategy research / implementation log

Purpose: track what strategies have been implemented / tested so we **don’t duplicate** work when we iterate overnight.

## Implemented (single-asset / per-ETF backtest)
- buy_hold
- sma_crossover (variants: fast/slow)
- ema_crossover (variants: fast/slow/band)
- momentum_absolute (variants: lookback/skip/threshold)
- rsi_mean_reversion (variants: window/entry/exit/max_hold)
- bollinger_mean_reversion (variants: window/std/exit_rule/max_hold)
- donchian_breakout (variants: entry_window/exit_window)
- vol_targeting (variants: vol_lookback/target_vol/trend_filter)
- crash_filter_drawdown (variants: dd_lookback/dd_threshold/reentry/cooldown)
- trend_filter_sma (proxy for DCA gating; variants: trend_window)
- macd_signal_crossover (variants: fast/slow/signal/zero_filter)
- keltner_breakout (variants: ema_window/atr_window/atr_mult/exit_rule; uses OHLC when available)
- stochrsi_mean_reversion (variants: rsi_window/stoch_window/smooth_k/smooth_d/entry/exit/max_hold)

## Not implemented yet (candidates)
(keep adding here; when implemented, move to the section above)
- MACD signal-line crossover (trend)  ← prepared spec in checking/new-strategies-to-add.md
- Keltner channel breakout (needs OHLC for proper ATR)  ← prepared spec in checking/new-strategies-to-add.md
- Stochastic RSI mean reversion  ← prepared spec in checking/new-strategies-to-add.md
- Williams %R mean reversion
- Adaptive moving average (KAMA) trend filter

## Multi-asset strategies (future)
These require a **portfolio-level** backtest (choose between multiple ETFs), not per-ticker.
- Dual Momentum / GEM
- VAA / DAA / PAA (canary universe)
