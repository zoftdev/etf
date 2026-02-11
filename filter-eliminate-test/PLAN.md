# Plan: ETF Elimination/Filter Strategies Test

## Objective

ทดสอบว่าการ **"Buy-Hold แต่ตัดตัวแย่ออก"** สามารถชนะ pure Buy-Hold ได้หรือไม่

---

## Strategies to Implement

### Strategy 1: Relative Strength Top-N
```
Logic:
1. คำนวณ 12-month return ของแต่ละ ETF
2. Rank ETFs by return
3. Hold เฉพาะ Top N (N = 10, 15, 20, 30)
4. Equal-weight allocation
5. Rebalance annually (Oct)

Variants:
- lookback: 6m, 12m
- top_n: 10, 15, 20, 30
- rebalance: monthly, quarterly, annually
```

### Strategy 2: Dual Momentum
```
Logic:
1. Absolute momentum: ETF return > 0 (or > T-Bill rate)
2. Relative momentum: Rank by 12m return
3. Hold Top N ที่ผ่าน absolute threshold
4. ถ้าไม่มีตัวผ่าน → ไป cash (หรือ skip)

Variants:
- absolute_threshold: 0%, 2%, 5%
- lookback: 6m, 12m
- top_n: 10, 15, 20
```

### Strategy 3: Trend Filter Elimination
```
Logic:
1. ตัด ETFs ที่ price < 200 SMA ออก
2. Buy-hold เฉพาะตัวที่ผ่าน filter
3. Re-evaluate annually/quarterly

Variants:
- ma_period: 100, 150, 200
- min_days_above: 0, 30, 60
```

### Strategy 4: Worst-Performer Elimination
```
Logic:
1. คำนวณ trailing 1-year return
2. ตัด bottom X% ออก
3. Buy-hold ที่เหลือ

Variants:
- eliminate_pct: 10%, 20%, 30%, 50%
- lookback: 6m, 12m, 3y
```

### Strategy 5: High Drawdown Elimination
```
Logic:
1. คำนวณ Max Drawdown ย้อนหลัง 3 ปี
2. ตัด ETFs ที่ MaxDD > threshold ออก
3. Buy-hold ที่เหลือ

Variants:
- max_dd_threshold: -30%, -40%, -50%, -60%
- lookback: 2y, 3y, 5y
```

### Strategy 6: Combined Score
```
Logic:
1. คำนวณ score = w1*Return + w2*Sharpe - w3*MaxDD
2. ตัด bottom X% by score
3. Buy-hold top performers

Variants:
- weights: various combinations
- eliminate_pct: 20%, 30%, 50%
```

---

## File Structure

```
filter-eliminate-test/
├── MARKET_RESEARCH.md      # ✅ Done
├── PLAN.md                 # ✅ This file
├── config.py               # Parameters and constants
├── data_loader.py          # Load ETF price data
├── utils.py                # Common utilities
│
├── strategies/
│   ├── __init__.py
│   ├── base.py             # Base strategy class
│   ├── relative_strength.py
│   ├── dual_momentum.py
│   ├── trend_filter.py
│   ├── worst_performer.py
│   ├── high_drawdown.py
│   └── combined_score.py
│
├── backtest/
│   ├── __init__.py
│   ├── engine.py           # Backtest engine
│   └── metrics.py          # Performance metrics
│
├── run_single.py           # Run single strategy
├── run_all.py              # Run all experiments
├── run_grid.py             # Run parameter grid
│
└── results/                # Generated results
    ├── summary.csv
    ├── by_strategy/
    └── charts/
```

---

## Backtest Parameters

```python
# Time period
START_DATE = "2005-01-01"
END_DATE = "2025-12-31"
PURE_BACKTEST_END = "2022-12-31"  # For fair comparison

# Initial capital
INITIAL_CAPITAL = 1_000_000

# Rebalance frequency
DEFAULT_REBALANCE = "annual"  # monthly, quarterly, annual

# Costs (optional)
TRANSACTION_COST = 0.001  # 0.1% per trade
SLIPPAGE = 0.0005  # 0.05%

# Benchmark
BENCHMARK = "SPY"
BASELINE = "Buy-Hold All ETFs"
```

---

## Metrics to Track

| Metric | Description |
|--------|-------------|
| Total Return | Final value / Initial |
| CAGR | Compound Annual Growth Rate |
| Sharpe Ratio | Risk-adjusted return |
| Sortino Ratio | Downside risk-adjusted |
| Max Drawdown | Worst peak-to-trough |
| Win Rate vs B&H | % of years beating buy-hold |
| # ETFs Held | Average number of ETFs per period |
| Turnover | Annual turnover rate |

---

## Baseline Comparisons

1. **Buy-Hold All 60 ETFs** - Equal-weight all ETFs
2. **Buy-Hold Top Universe** - เหมือน makro-etf test (17 ETFs)
3. **SPY Only** - Simple S&P 500

---

## Expected Output

### Per Strategy
- `results/{strategy_name}_summary.csv` - Overall metrics
- `results/{strategy_name}_by_year.csv` - Year-by-year breakdown
- `results/{strategy_name}_holdings.csv` - What was held when
- `results/{strategy_name}_chart.html` - Equity curve

### Aggregate
- `results/all_strategies_comparison.csv` - Side-by-side comparison
- `results/best_variants.csv` - Top 10 performing variants
- `results/comparison_chart.html` - All equity curves

---

## Execution Order

1. [ ] Implement `config.py` + `data_loader.py`
2. [ ] Implement `backtest/engine.py` + `backtest/metrics.py`
3. [ ] Implement `strategies/base.py`
4. [ ] Implement strategies one by one:
   - [ ] relative_strength.py
   - [ ] dual_momentum.py
   - [ ] trend_filter.py
   - [ ] worst_performer.py
   - [ ] high_drawdown.py
   - [ ] combined_score.py
5. [ ] Implement `run_single.py`
6. [ ] Run individual strategy tests
7. [ ] Implement `run_grid.py` for parameter sweep
8. [ ] Run full grid test
9. [ ] Analyze results, write summary

---

## Success Criteria

Strategy ถือว่า "ชนะ" ถ้า:
- CAGR > Buy-Hold All (5.94%)
- หรือ Sharpe > Buy-Hold All (0.388) พร้อม CAGR ไม่ต่ำกว่า 80% ของ baseline
- Win Rate vs B&H > 50% ของทุกปี

Bonus:
- Max Drawdown < Buy-Hold (-60.66%)
- Lower turnover = ดีกว่า (practical implementation)
