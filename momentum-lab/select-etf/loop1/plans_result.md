# ETF Selection Results - 5 Plans

| Plan | Focus | n ETFs | Key Difference |
|------|-------|--------|-----------------|
| A | QuantPedia Classic | 13 | โครงสร้างเดิม mainstream |
| B | Low Correlation | 13 | minimize pairwise correlation |
| C | Long Backtest | 13 | มี data 15+ ปี |
| D | Low Expense | 13 | cost-efficient |
| E | Sector Tilt | 15 | เพิ่ม sector ETFs (XLU, XLF) |

### Params Used (`param/default` → optimal-13etf.json)

| Param | Value |
|-------|-------|
| n_long | 5 |
| n_short | 1 |
| short_weight | 0.2 |
| mom_periods_days | [21, 63, 126, 189, 252] |
| corr_short_days | 10 |
| spread_pct | 0.15 |

### Backtest (n_long=5, spread=0.15%)

| Plan | Mom CAGR | Mom Sharpe | Mom MaxDD |
|------|----------|------------|-----------|
| A QuantPedia | 11.53% | 0.87 | -25.2% |
| D Low Expense | 11.84% | 0.82 | -34.7% |
| C Long Backtest | 11.28% | 0.80 | -29.0% |
| E Sector Tilt | 10.37% | 0.76 | -21.5% |
| B Low Corr | 8.84% | 0.67 | -25.8% |

---

## A_QuantPedia_Classic

| # | Ticker |
|---|--------|
| 1 | SPY |
| 2 | IWM |
| 3 | EFA |
| 4 | EEM |
| 5 | IYR |
| 6 | QQQ |
| 7 | LQD |
| 8 | IEF |
| 9 | TIP |
| 10 | GLD |
| 11 | USO |
| 12 | DBC |
| 13 | FXE |

**Total:** 13 ETFs

## B_Low_Correlation

| # | Ticker |
|---|--------|
| 1 | SPY |
| 2 | EFA |
| 3 | IYR |
| 4 | EEM |
| 5 | TLT |
| 6 | IEF |
| 7 | USO |
| 8 | GLD |
| 9 | UUP |
| 10 | FXE |
| 11 | DBC |
| 12 | TIP |
| 13 | SLV |

**Total:** 13 ETFs

## C_Long_Backtest

| # | Ticker |
|---|--------|
| 1 | SPY |
| 2 | QQQ |
| 3 | IWM |
| 4 | EFA |
| 5 | EEM |
| 6 | VEU |
| 7 | TLT |
| 8 | IEF |
| 9 | LQD |
| 10 | GLD |
| 11 | SLV |
| 12 | USO |
| 13 | FXE |

**Total:** 13 ETFs

## D_Low_Expense

| # | Ticker |
|---|--------|
| 1 | SPY |
| 2 | QQQ |
| 3 | IWM |
| 4 | EFA |
| 5 | EEM |
| 6 | TLT |
| 7 | IEF |
| 8 | LQD |
| 9 | GLD |
| 10 | SLV |
| 11 | USO |
| 12 | IYR |
| 13 | VTV |

**Total:** 13 ETFs

## E_Sector_Tilt

| # | Ticker |
|---|--------|
| 1 | SPY |
| 2 | QQQ |
| 3 | IWM |
| 4 | IYR |
| 5 | EFA |
| 6 | EEM |
| 7 | TLT |
| 8 | IEF |
| 9 | LQD |
| 10 | TIP |
| 11 | GLD |
| 12 | USO |
| 13 | DBC |
| 14 | XLU |
| 15 | XLF |

**Total:** 15 ETFs
