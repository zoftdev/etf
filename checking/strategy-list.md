# Strategy ideas to test (ETF universe)

Goal: create a shortlist of **10 strategies** to prototype in this repo, where each strategy includes a clear set of **simulation parameters (grid)** to sweep.

Assumptions (baseline):
- Use daily data (Close; later add Dividends/Adj Close if available)
- No leverage by default
- Start with **time-weighted equity curve** (like current harness)
- Add optional costs later: fee_bps, slippage_bps

---

## 1) Buy & Hold (baseline)
**What:** Always invested.

**Params to simulate:**
- `lookback_years`: [5, 10, 15, 20]
- (optional) `rebalance`: ["none"]  (single-asset so mostly N/A)
- `fee_bps`: [0, 5, 10]

---

## 2) SMA Crossover (trend following)
**What:** Invest when fast SMA > slow SMA, else cash.

**Params to simulate:**
- `fast_window`: [10, 20, 50, 100]
- `slow_window`: [100, 150, 200, 250]
- `signal_delay_days`: [0, 1] (same-day vs next-day execution)
- `fee_bps`: [0, 5, 10]

---

## 3) EMA Crossover (trend following, faster response)
**What:** Invest when fast EMA > slow EMA.

**Params to simulate:**
- `fast_span`: [10, 20, 50]
- `slow_span`: [100, 150, 200]
- `band_pct`: [0.0, 0.25, 0.5]  (require fast > slow*(1+band)) to reduce whipsaw
- `fee_bps`: [0, 5, 10]

---

## 4) Donchian Breakout (channel breakout)
**What:** Buy when price breaks above N-day high; exit when breaks below M-day low.

**Params to simulate:**
- `entry_window`: [20, 55, 100]
- `exit_window`: [10, 20, 55]
- `use_close`: [True] (later: include high/low if available)
- `fee_bps`: [0, 5, 10]

---

## 5) Bollinger Bands Mean Reversion
**What:** Buy when price is below lower band (oversold), exit at mid/upper.

**Params to simulate:**
- `window`: [20, 50]
- `num_std`: [1.5, 2.0, 2.5]
- `exit_rule`: ["mid", "upper"]
- `max_hold_days`: [None, 20, 60]
- `fee_bps`: [0, 5, 10]

---

## 6) RSI Mean Reversion
**What:** Buy when RSI is low; sell when RSI mean-reverts.

**Params to simulate:**
- `rsi_window`: [7, 14, 21]
- `entry_rsi`: [20, 25, 30]
- `exit_rsi`: [45, 50, 55]
- `max_hold_days`: [None, 10, 30]
- `fee_bps`: [0, 5, 10]

---

## 7) Momentum (time-series momentum / absolute momentum)
**What:** Invest when trailing return over lookback is positive; else cash.

**Params to simulate:**
- `lookback_days`: [63, 126, 252] (3M, 6M, 12M)
- `skip_recent_days`: [0, 5, 21] (avoid short-term reversal)
- `threshold_pct`: [0.0, 1.0, 2.0] (require return > threshold)
- `fee_bps`: [0, 5, 10]

---

## 8) Volatility Targeting (risk control)
**What:** Scale exposure so realized vol ≈ target (cap at 1.0), optionally combine with a trend filter.

**Params to simulate:**
- `vol_lookback_days`: [20, 63, 126]
- `target_vol_ann_pct`: [8, 10, 12, 15]
- `max_leverage`: [1.0] (later test 1.5/2.0)
- `trend_filter`: ["none", "sma_200"]
- `fee_bps`: [0, 5, 10]

---

## 9) Trend Filter + DCA (hybrid)
**What:** DCA contributions, but only buy when long-term trend is up (e.g. price > SMA200).  
Note: DCA is **cash-flow sensitive**; better to report both time-weighted and money-weighted (IRR/XIRR).

**Params to simulate:**
- `trend_window`: [150, 200, 250]
- `contribution_freq`: ["monthly", "weekly"]
- `contribution_amount`: ["normalized"] (e.g. 1 unit per period)
- `execution_day`: ["first_trading_day", "last_trading_day"]
- `fee_bps`: [0, 5, 10]

---

## 10) Protective Put Proxy / Crash Filter (simple regime filter)
**What:** Move to cash when drawdown or volatility spikes (proxy for crash protection), re-enter after recovery.

**Params to simulate:**
- `dd_lookback_days`: [63, 126, 252]
- `dd_threshold_pct`: [-10, -15, -20]  (exit when drawdown < threshold)
- `reentry_rule`: ["new_high", "sma_200", "cooldown"]
- `cooldown_days`: [10, 20, 60] (if reentry_rule=cooldown)
- `fee_bps`: [0, 5, 10]

---

# Notes / Implementation order (suggested)

1. SMA crossover (already implemented) + EMA crossover
2. Momentum (absolute momentum)
3. RSI mean reversion
4. Bollinger mean reversion
5. Donchian breakout
6. Vol targeting (requires fractional exposure / scaling)
7. Crash filter
8. DCA (requires cash-flow accounting + XIRR)

# Common evaluation metrics to compute for every strategy
- CAGR %, Total Return %
- Max Drawdown %
- Volatility (annualized) %, Sharpe
- Win rate of daily returns (optional)
- Turnover / #trades (important once we add fees)
- % time in market
