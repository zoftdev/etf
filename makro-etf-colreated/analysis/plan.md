# Plan: Strategy Analysis for Beating Buy-and-Hold

## Phase 1: Data Preparation

1. Load `forecast.json` (2010-2022, 13 years of recommendations)
2. Load `etf-mapping.json` (maps names to tickers)
3. Load `etf_price.csv` (daily closes, 60 ETFs)
4. Build the recommendation universe (17 unique tickers across all years)

## Phase 2: Baseline Construction

- **B&H All 60 ETFs**: Equal-weight all tickers in CSV (reference only)
- **B&H Rec Universe (17 ETFs)**: Equal-weight only mapped tickers (true baseline)
- Both buy at first rebalance date (Oct 2010), hold until benchmark end

## Phase 3: Strategy Matrix (16 strategies tested)

### A. Weighting Variants (all categories, Oct rebalance)
| # | Strategy | Logic |
|---|---|---|
| 1 | EqWt All Recs | 1/N across all recommended tickers |
| 2 | Score-Wt All Recs | Weight proportional to forecast score |
| 3 | Score^2-Wt All Recs | Weight proportional to score squared (more concentrated) |

### B. Concentration Variants
| # | Strategy | Logic |
|---|---|---|
| 4 | Top-3 Score-Wt | Only 3 highest-scored picks, score-weighted |
| 5 | Top-5 Score-Wt | Only 5 highest-scored picks, score-weighted |
| 6 | Top-5 EqWt | Only 5 highest-scored picks, equal-weight |
| 16 | Top-3 EqWt | Only 3 highest-scored picks, equal-weight |

### C. Threshold Filters
| # | Strategy | Logic |
|---|---|---|
| 7 | Thresh >= 0.7 | Only picks with score >= 0.7, score-weighted |
| 8 | Thresh >= 0.8 | Only picks with score >= 0.8, score-weighted |

### D. Category Isolation
| # | Strategy | Logic |
|---|---|---|
| 9 | US-Sector Only ScWt | Only us_sector recommendations, score-weighted |
| 10 | US-Sector Only EqWt | Only us_sector recommendations, equal-weight |
| 11 | Countries Only ScWt | Only country recommendations, score-weighted |
| 12 | Commodity Only ScWt | Only commodity recommendations, score-weighted |
| 13 | US-Sect + Commod ScWt | Exclude countries, score-weighted |

### E. Rebalance Timing
| # | Strategy | Logic |
|---|---|---|
| 14 | All ScWt Jan Rebal | Score-weighted, rebalance in January |
| 15 | All ScWt Dec Rebal | Score-weighted, rebalance in December |

## Phase 4: Metrics

For each strategy compute:
- **Final portfolio value** ($)
- **Total return** (%)
- **Annualized return** (CAGR %)
- **Max drawdown** (%)
- **Per-year return** (Jan-Dec, for year-over-year comparison)
- **Beat B&H?** (vs Rec Universe baseline)

## Phase 5: Analysis & Output

1. Summary table ranking all strategies
2. Per-year return breakdown (B&H vs top strategies)
3. Yearly allocation detail for winning strategies
4. Interactive Plotly chart (strategy_analysis.html)

## Validation Checks

- [x] Apples-to-apples: B&H baseline uses same 17-ticker universe
- [x] Test at `--end 2022` (pure in-sample with recommendations)
- [x] Test at `--end 2023` (1-year out-of-sample hold)
- [x] Test at `--end 2025` (3-year out-of-sample hold)
- [x] Daily series for accurate max drawdown calculation
