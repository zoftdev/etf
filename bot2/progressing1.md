# Progress Report #1 - Decision Module Development

**Date:** February 6, 2026  
**Status:** Phase 1 Complete - RSI Decision Module & Visualization Tool

---

## Overview

Development of the Bot2 decision module system focusing on technical indicators for ETF trading signals. The first phase implements RSI (Relative Strength Index) decision logic with visualization capabilities.

---

## Files Created

### Documentation
- **`decision_ph1.md`** - Defines 6 decision modules with objectives and rules:
  - RSI Momentum
  - MACD Trend
  - Moving Average Crossover
  - Bollinger Bands Mean Reversion
  - Stochastic Oscillator
  - Multi-Indicator Composite

### Configuration Files
- **`decision_rsi_low.yaml`** - Low sensitivity RSI config (period: 7, oversold: 30, overbought: 70)
- **`decision_rsi_mid.yaml`** - Medium sensitivity RSI config (period: 14, oversold: 30, overbought: 70)
- **`decision_rsi_high.yaml`** - High sensitivity RSI config (period: 21, oversold: 20, overbought: 80)
- **`tool_conf.yaml`** - Visualization tool configuration (decision module, period, tickers, display options)

### Implementation Files
- **`decision_rsi.py`** - RSI decision module implementation:
  - Calculates RSI from OHLC data (no volume required)
  - Detects bullish/bearish divergences
  - Detects momentum shifts (RSI crossing 50)
  - Generates normalized scores (-1.0 to 1.0)
  - Strictly follows "no look-ahead" principle

- **`2_tool_view_decision.py`** - Decision visualization tool:
  - Loads ETF data from `etf.yaml`
  - Fetches historical OHLC data via `ETFDataFetcher`
  - Calculates decision scores for each date
  - Generates interactive HTML reports with Plotly charts
  - Displays price charts, RSI subplot, buy/sell signals

---

## Key Features Implemented

### 1. RSI Decision Module (`decision_rsi.py`)
- **RSI Calculation**: Standard RSI formula using price changes
- **Divergence Detection**: Identifies bullish/bearish divergences between price and RSI
- **Momentum Shifts**: Detects RSI crossing above/below 50
- **Score Generation**: Normalized score from -1.0 (strong SELL) to 1.0 (strong BUY)
- **No Look-Ahead**: Only uses historical data up to `as_of_date`

### 2. Visualization Tool (`2_tool_view_decision.py`)
- **Multi-Ticker Support**: Processes multiple ETFs from `etf.yaml`
- **Interactive Charts**: Plotly-based HTML reports
- **Price Display**: Line chart showing Close prices
- **RSI Subplot**: Separate RSI chart with threshold lines (30/70)
- **Signal Markers**: Visual buy (green) and sell (red) markers on price chart
- **Configurable**: YAML-based configuration for easy customization

### 3. Configuration System
- **Decision Configs**: YAML files for RSI parameters (period, thresholds, weights)
- **Tool Config**: Centralized visualization settings
- **Flexible**: Easy to switch between low/mid/high sensitivity RSI

---

## Issues Encountered & Resolved

### Issue 1: Python Environment
**Problem:** `python` command not found  
**Solution:** Use `python3` or `uv run python3` for execution

### Issue 2: Module Import Errors
**Problem:** `ModuleNotFoundError: No module named 'pandas'`  
**Solution:** Use `uv run python3` to ensure virtual environment activation

### Issue 3: HTML Template Rendering
**Problem:** `KeyError: ' font-family'` in f-string template  
**Solution:** Escaped CSS curly braces in HTML template (e.g., `{{ font-family: ... }}`)

### Issue 4: Timezone Comparison Error
**Problem:** `TypeError: Invalid comparison between dtype=datetime64[ns, America/New_York] and Timestamp`  
**Solution:** Convert both index and target date to string format for comparison

### Issue 5: Plotly Binary Encoding Bug ⚠️ **CRITICAL FIX**
**Problem:** Close prices showing index positions (43) instead of actual values ($27.82)  
**Root Cause:** Plotly's binary encoding (`bdata`) corrupts numpy arrays and pandas Series when serializing to HTML  
**Solution:** Convert all data to plain Python lists using `.tolist()` before passing to Plotly:
```python
# Before (broken):
y=data['Close'].values  # numpy array → corrupted in HTML

# After (fixed):
y=data['Close'].tolist()  # plain list → correct values in HTML
```
**Files Fixed:**
- Price trace: `x=data.index.tolist()`, `y=data['Close'].tolist()`
- RSI trace: `x=rsi_series.index.tolist()`, `y=rsi_series.tolist()`
- Threshold lines: `x=rsi_dates` (already list)

---

## Current State

### Working Features ✅
- RSI calculation and decision scoring
- Data fetching from yfinance with caching
- HTML report generation with Plotly
- Multi-ticker visualization (currently limited to 3: EWZ, SPY, QQQ)
- Buy/sell signal markers
- RSI subplot with threshold lines
- Configuration via YAML files

### Configuration
- **Decision Module:** `rsi_mid` (14-period RSI)
- **Period:** 6 months
- **Tickers:** EWZ, SPY, QQQ (limited to 3 symbols)
- **Display Options:** RSI subplot enabled, signals enabled, thresholds enabled

### Output
- **Report Location:** `result/decision_view.html`
- **Format:** Interactive Plotly HTML chart
- **Content:** Price charts + RSI subplot + signal markers for each ticker

---

## Testing & Verification

### Verified Data Accuracy
- EWZ Close price on Oct 10, 2025: **$27.82** ✅
- SPY prices: ~$632 range ✅
- QQQ prices: ~$571 range ✅
- HTML output now contains correct price values (verified)

### Test Commands
```bash
# Run visualization tool
cd /home/zoftdev/clawd/workspace/etf
uv run python bot2/2_tool_view_decision.py

# Output: result/decision_view.html
```

---

## Architecture Compliance

### Bot2 Architecture ✅
- **Decision Layer:** Pure signal generator (no trading logic)
- **Score Range:** -1.0 to 1.0 (normalized)
- **No Look-Ahead:** Only uses historical data up to evaluation date
- **Modular:** Separate config files for different sensitivities

### Data Requirements ✅
- **OHLC Only:** No volume data required (as specified)
- **Historical Data:** Fetched via `ETFDataFetcher` with caching
- **Time Series:** Properly handles timezone-aware timestamps

---

## Next Steps / Pending Items

### Immediate
1. ✅ **FIXED:** Plotly binary encoding issue (index values instead of prices)
2. ⏳ **PENDING:** Implement candlestick charts for better volatility visualization
   - User feedback: "price is going up linear not like real data"
   - Solution: Switch from line charts to candlestick charts

### Phase 2: Additional Decision Modules
- MACD Trend Decision (`decision_macd.py`)
- Moving Average Crossover (`decision_ma_crossover.py`)
- Bollinger Bands Mean Reversion (`decision_bollinger.py`)
- Stochastic Oscillator (`decision_stochastic.py`)
- Multi-Indicator Composite (`decision_composite.py`)

### Phase 3: Integration
- Integrate decision modules with Bot layer
- Simulator integration for backtesting
- Performance metrics and evaluation

---

## Technical Notes

### Dependencies
- `pandas` - Data manipulation
- `plotly` - Interactive charts
- `pyyaml` - Configuration parsing
- `yfinance` - ETF data fetching
- `numpy` - Numerical operations

### Python Environment
- Using `uv` for dependency management
- Virtual environment: `.venv` or `venv`
- Python version: 3.8+ (compatible with `Tuple` type hints)

### File Structure
```
bot2/
├── ARCHITECTURE.md          # Bot2 architecture documentation
├── flow.md                   # Daily evaluation flow
├── decision_ph1.md          # Decision module specifications
├── decision_rsi.py          # RSI decision implementation
├── decision_rsi_low.yaml    # Low sensitivity config
├── decision_rsi_mid.yaml    # Medium sensitivity config
├── decision_rsi_high.yaml   # High sensitivity config
├── 2_tool_view_decision.py    # Visualization tool
└── tool_conf.yaml           # Tool configuration
```

---

## Lessons Learned

1. **Plotly Binary Encoding:** Always use `.tolist()` for pandas/numpy data when writing to HTML to avoid binary encoding corruption
2. **Timezone Handling:** Convert datetime comparisons to string format to avoid timezone issues
3. **Environment Management:** Use `uv run` to ensure proper virtual environment activation
4. **Configuration First:** YAML-based configs make it easy to test different parameters without code changes

---

## Summary

Phase 1 is complete with a working RSI decision module and visualization tool. The critical Plotly binary encoding bug has been fixed, and the system now correctly displays actual price values. The foundation is set for implementing the remaining 5 decision modules in Phase 2.

**Status:** ✅ Ready for Phase 2 development
