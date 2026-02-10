# Strategy: What the Recommendation Helps & Buy/Sell Rules

## What the Recommendation Helps

The macro forecast's **US sector** recommendations provide a **sector rotation signal** with:

- **77% hit rate** (27 of 35 picks had positive Oct-to-Oct returns)
- **37% "great" rate** (13 picks returned >15%)
- Only **9% terrible** (3 picks lost >10%)
- **+15.7% average return per pick** across 13 years

### What it gets RIGHT

| Signal | Example Years | What Happened |
|---|---|---|
| Tech dominance | 2010-2017, 2019 | XLK consistently recommended, returned +8% to +35% per year |
| Energy cycle timing | 2020-2021 | Called XLE reopening (+110% in 2020, +64% in 2021) |
| Defensive rotation | 2022 | Added XLV when market was crashing |
| Reopening trade | 2020 | XLI+XLY+XLE (all three returned +40% to +110%) |

### What it gets WRONG

| Signal | Year | What Happened |
|---|---|---|
| Dropped Tech too early | 2018 | Sold XLK, held only XLF+XLE, missed tech rebound |
| Financials timing | 2019, 2021 | XLF lost -15% and -14% in those hold periods |
| Country recommendations | All years | BRIC overweight destroyed value (China, Brazil, Russia) |

### What it does NOT help with

- **Country/EM allocation** -- GDP growth forecasts do not predict stock returns
- **Commodity timing** -- Oil (USO) too volatile, -71% max drawdown
- **Short-term timing** -- Yearly rebalance, no intra-year signals

---

## Buy/Sell Strategy

### Rule Set

```
WHEN: October each year (when new macro forecasts are published)
DO:
  1. Read us_sector recommendations from forecast.json for current year
  2. Map sector names to ETFs via etf-mapping.json
  3. SELL any current holdings NOT in this year's recommendation
  4. BUY any new ETFs IN this year's recommendation
  5. REBALANCE to score-weighted (or equal-weight) allocation
  6. HOLD until next October
```

### Concrete Actions Year by Year

```
Oct 2010: BUY  XLK, XLV                          (start portfolio)
Oct 2011: HOLD XLK, XLV                          (no changes)
Oct 2012: HOLD XLK, XLV                          (no changes)
Oct 2013: HOLD XLK, XLV  |  BUY  XLF             (add financials)
Oct 2014: HOLD XLK, XLV, XLF                     (no changes)
Oct 2015: HOLD XLK, XLV  |  BUY  XLY  | SELL XLF (swap fin for cons.disc)
Oct 2016: HOLD XLK       |  BUY  XLF, XLE | SELL XLV, XLY
Oct 2017: HOLD XLK, XLF, XLE                     (no changes)
Oct 2018: HOLD XLF, XLE  |  SELL XLK              (drop tech -- bad call!)
Oct 2019: HOLD XLF       |  BUY  XLK, XLV | SELL XLE
Oct 2020: BUY  XLI, XLE, XLY | SELL XLK, XLF, XLV (full rotation)
Oct 2021: HOLD XLE, XLI  |  BUY  XLF  | SELL XLY
Oct 2022: HOLD XLE       |  BUY  XLV, XLY | SELL XLF, XLI
```

### Position Sizing (Score-Weighted)

Each October, allocate portfolio proportional to forecast scores:

```
Example Oct 2020:
  XLI score=0.72  -> weight = 0.72/(0.72+0.68+0.62) = 35.6%
  XLE score=0.68  -> weight = 0.68/(0.72+0.68+0.62) = 33.7%
  XLY score=0.62  -> weight = 0.62/(0.72+0.68+0.62) = 30.7%
```

### Turnover

- Average **2 trades per year** (1 buy, 1 sell)
- 4 years with zero changes (2011, 2012, 2014, 2017)
- 2 years with full rotation (2020, rarely)
- Low turnover = low transaction costs

---

## Risk Profile

| Metric | US-Sector Strategy | B&H Rec Universe |
|---|---|---|
| Annualized Return | **15.73%** | 7.24% |
| Max Drawdown | -34.0% | -34.2% |
| Worst Year | -11.7% (2018) | -14.0% (2022) |
| Best Year | +34.7% (2021) | +25.6% (2019) |
| Positive Years | **11/13 (85%)** | 9/13 (69%) |
| Avg Annual Return | **+15.5%** | +7.4% |

### Risk vs Reward

- **Same downside** as buy-hold (~34% max drawdown)
- **2x the upside** (15.7% vs 7.2% annualized)
- **Better win rate** (85% positive years vs 69%)
- **1 bad year** (2018: dropped XLK too early, only held XLF+XLE)

---

## Summary

The recommendation helps by providing a **yearly sector rotation signal** that:
1. Identifies 2-3 US sector ETFs to hold each year
2. Has 77% hit rate on individual picks
3. Averages +15.7% per pick
4. Requires only ~2 trades per year in October
5. Beats buy-hold by 2x annualized with similar risk

**Critical rule**: Only follow `us_sector` recommendations. Ignore `countries` and `commodity`.
