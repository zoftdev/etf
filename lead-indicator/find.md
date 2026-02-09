# Lead Indicator Strategy: Forecasting Country ETF Bearish Periods

## Goal

Identify **leading indicators** that predict when a country's stock market will enter a bearish phase (e.g., Thailand THD declining ~15% in 2022-2024). In the long run, stock indices track GDP and P/E ratios mean-revert — so we can detect overvaluation or deteriorating fundamentals **before** the decline happens.

## Scope

- 27 single-country ETFs from `data/etf-v3.yaml`
- 20 years of daily price data in `data/etf_price.csv` (2005-2026)
- Bearish = drawdown >= 15% within 12 months

---

## Indicator Tiers

### Tier 1 — Strong evidence, free API, easy to automate

| # | Indicator | Source | API / Code | Why It Works |
|---|-----------|--------|------------|--------------|
| 1 | **Buffett Indicator** (Market Cap / GDP) | World Bank | `wbgapi` — code `CM.MKT.LCAP.GD.ZS` | A 2022 European academic study found it forecasts 83% of 10-year returns across 14 developed countries. Buffett himself called it "probably the best single measure of where valuations stand." When ratio > historical avg, future returns tend to be lower. |
| 2 | **GDP Growth Rate** | World Bank | `wbgapi` — code `NY.GDP.MKTP.KD.ZG` | Declining GDP growth precedes market declines. Thailand averaged only 1.9% growth in the decade before its 2023 crash. Falling GDP for 3+ consecutive years = strong bearish signal. |
| 3 | **Inflation / CPI** | World Bank | `wbgapi` — code `FP.CPI.TOTL.ZG` | Inflation > 5% squeezes corporate margins and triggers central bank rate hikes. Thailand's 2022 inflation surge (energy + food prices) preceded the equity decline. |
| 4 | **US Yield Curve** (10Y - 2Y spread) | FRED | `fredapi` — series `T10Y2Y` | Every yield curve inversion since WWII has been followed by a recession within 6-18 months. US recessions propagate globally — especially to EM countries dependent on dollar funding. Daily data available. |
| 5 | **Price vs 200-day SMA** | Existing price CSV | Computed from `data/etf_price.csv` | Simple trend-following: price below SMA(200) = bearish regime. Already proven in the project's `indicator-simulator`. Reuse `compute_sma()`. |

### Tier 2 — Good evidence, moderate data effort

| # | Indicator | Source | API / Code | Why It Works |
|---|-----------|--------|------------|--------------|
| 6 | **Current Account / GDP** | World Bank | `wbgapi` — code `BN.CAB.XOKA.GD.ZS` | Persistent current account deficits signal external vulnerability. Countries with deficit > 3% of GDP are more prone to capital flight and currency crises. |
| 7 | **Private Sector Credit / GDP** | World Bank | `wbgapi` — code `FS.AST.PRVT.GD.ZS` | Excessive credit growth precedes financial crises (BIS research). Thailand's high consumer debt (91% of GDP) was a known risk factor before the 2022-2024 decline. |
| 8 | **Currency Weakness vs USD** | yfinance | e.g. `THBUSD=X`, `KRWUSD=X` | Weakening local currency = capital outflow signal. Strong USD (DXY up) is bearish for EM equities. 10%+ YoY depreciation = warning. |
| 9 | **Real Interest Rate** | World Bank | `wbgapi` — code `FR.INR.RINR` | Rising real interest rates are bearish for equities — higher discount rate compresses valuations. Rate hiking cycles often precede equity declines. |
| 10 | **Broad Money / GDP (M2)** | World Bank | `wbgapi` — code `FM.LBL.BMNY.GD.ZS` | Contraction in money supply growth = less liquidity = bearish for risk assets. |

### Tier 3 — Useful but harder to obtain (future enhancement)

| # | Indicator | Source | Issue |
|---|-----------|--------|-------|
| 11 | **PMI** (Purchasing Managers Index) | S&P Global | Best short-term lead indicator (PMI < 50 = contraction). But requires paid subscription — no free API. Could scrape Trading Economics as fallback. |
| 12 | **CAPE / Shiller PE** by country | Siblis Research / Barclays | 10-year cyclically adjusted PE. Strong predictor but no free API for non-US markets. Requires web scraping. |
| 13 | **Foreign Net Capital Flows** | Central bank reports | Net foreign buying/selling of equities. Available for some countries (e.g., SET foreign flow data for Thailand) but no uniform free API across all countries. |

---

## Data Sources Summary

| Source | Package | API Key | Resolution | Coverage |
|--------|---------|---------|-----------|----------|
| **World Bank** | `wbgapi` | None needed | Annual | 200+ countries, 17,500+ indicators |
| **FRED** | `fredapi` | Free key from fred.stlouisfed.org | Daily/Monthly | US macro (yield curve, M2, DXY, Fed Funds) |
| **yfinance** | `yfinance` | None needed | Daily | ETF prices, trailing PE, currency pairs |
| **Existing CSV** | pandas | N/A | Daily | 59 ETFs, 2005-2026 |

### World Bank Indicator Codes Reference

| Indicator | WB Code | Coverage |
|-----------|---------|----------|
| GDP growth (annual %) | `NY.GDP.MKTP.KD.ZG` | 200+ countries |
| CPI inflation (annual %) | `FP.CPI.TOTL.ZG` | 190+ countries |
| Current account / GDP | `BN.CAB.XOKA.GD.ZS` | 180+ countries |
| Real interest rate | `FR.INR.RINR` | 150+ countries |
| Domestic credit / GDP | `FS.AST.PRVT.GD.ZS` | 180+ countries |
| Broad money / GDP | `FM.LBL.BMNY.GD.ZS` | 170+ countries |
| **Market cap / GDP** (Buffett) | `CM.MKT.LCAP.GD.ZS` | 80+ countries |

---

## Country ETF → ISO Mapping (27 countries)

| ETF Ticker(s) | Country | ISO3 | Currency Pair |
|---|---|---|---|
| THD | Thailand | THA | THBUSD=X |
| EWJ | Japan | JPN | JPYUSD=X |
| MCHI, FXI | China | CHN | CNYUSD=X |
| EWT | Taiwan | TWN | TWDUSD=X |
| EWY | South Korea | KOR | KRWUSD=X |
| INDA, EPI | India | IND | INRUSD=X |
| VNM | Vietnam | VNM | VNDUSD=X |
| EIDO | Indonesia | IDN | IDRUSD=X |
| EWS | Singapore | SGP | SGDUSD=X |
| EWA | Australia | AUS | AUDUSD=X |
| EWG | Germany | DEU | EURUSD=X |
| EWU | United Kingdom | GBR | GBPUSD=X |
| EWQ | France | FRA | EURUSD=X |
| EWL | Switzerland | CHE | CHFUSD=X |
| EWN | Netherlands | NLD | EURUSD=X |
| EWI | Italy | ITA | EURUSD=X |
| EWP | Spain | ESP | EURUSD=X |
| TUR | Turkey | TUR | TRYUSD=X |
| EWC | Canada | CAN | CADUSD=X |
| EWW | Mexico | MEX | MXNUSD=X |
| EWZ | Brazil | BRA | BRLUSD=X |
| ECH | Chile | CHL | CLPUSD=X |
| ARGT | Argentina | ARG | ARSUSD=X |
| KSA | Saudi Arabia | SAU | SARUSD=X |
| EIS | Israel | ISR | ILSUSD=X |
| EZA | South Africa | ZAF | ZARUSD=X |
| UAE | UAE | ARE | AEDUSD=X |

---

## Scoring Methodology

### Per-Indicator Signal
Each indicator produces a **z-score** relative to the country's own history (not cross-country comparison — research confirms each country should be compared to its own historical norms).

```
z = (current_value - rolling_mean) / rolling_std
```

- Rolling window: 10 years for annual data, 200 days for daily data
- Signal: z > 1.5 = bearish, z < -1.5 = bullish, else neutral

### Composite Score
Weighted sum of z-scores, normalized to 0-100 scale:

```
composite = sum(weight_i * z_i) / sum(weight_i)
scaled = normalize_to_0_100(composite)
```

- Tier 1 indicators: weight = 2.0
- Tier 2 indicators: weight = 1.0
- Higher score = more bearish

### Two Resolutions
- **Annual composite** (all indicators including World Bank): for long-term regime identification
- **Monthly composite** (price-based + FRED only): for shorter-term signals (World Bank data has 6-18 month publication lag)

---

## Backtest Methodology

### Bearish Period Definition
- Rolling 12-month forward return < -15% from any peak
- For each month t, compute: `fwd_return = price[t + 12m] / price[t] - 1`

### Evaluation
For each country at each time point, record:
1. Composite score at time t
2. Forward returns at 3, 6, 9, 12 months
3. Whether a bearish period occurred

### Metrics
- **Precision**: when score > threshold, what % actually saw a bearish period?
- **Recall**: of all actual bearish periods, what % had elevated scores?
- **Lead time**: how many months before the drawdown did the score first spike?
- **False positive rate**: bearish signal but market went up
- **Correlation**: Spearman rank correlation between score and forward returns

### Statistical Power
- 27 countries x ~5 bearish events each = ~135 events (pooled)
- Per-country sample is small (~5 events), but pooled analysis provides reasonable statistical power

---

## Thailand Case Study (THD, 2022-2024)

### What Happened
- SET index fell -15.2% in 2023
- THD (iShares MSCI Thailand) declined from ~$80 (2022) to ~$60 (2024)

### Root Causes (Retrospective)
- 2022 inflation surge (energy + food prices post-COVID)
- High consumer debt: 91% of GDP
- Rising interest rates (Bank of Thailand hiked from 0.5% to 2.5%)
- Slow tourism recovery post-COVID
- EV transition threatening auto/parts sector (major Thai export)
- Average GDP growth only 1.9% in the decade to 2023

### Which Indicators Should Have Fired?
| Indicator | Signal | Lead Time |
|---|---|---|
| GDP growth declining | YES — below 2% for years | 2-3 years |
| Inflation spike | YES — surged in 2022 | 6-12 months |
| Private credit/GDP elevated | YES — 91% consumer debt | Long-standing |
| Currency weakening | YES — THB weakened vs USD in 2022 | 6 months |
| Price < SMA200 | YES — broke below in mid-2022 | 0-3 months (lagging) |
| US yield curve inverted | YES — inverted July 2022 | 6-12 months |

### Validation Goal
Run the composite scoring engine on Thailand 2015-2024 and verify:
- Composite score was elevated (>70) before mid-2022
- Score peaked before or at the start of the decline
- Score identified the bearish setup at least 3-6 months in advance

---

## Implementation Files

```
lead-indicator/
├── find.md                       # This strategy document
├── country_mapping.yaml          # ETF ticker → ISO3 code + currency pairs
├── lead_indicator_config.yaml    # Indicator weights, thresholds, backtest params
├── macro_data_fetcher.py         # Fetch macro data (World Bank, FRED, yfinance)
├── lead_indicator_engine.py      # Compute z-scores + composite bearish score
├── backtest_lead_signals.py      # Backtest: did indicators predict bearish periods?
├── cache/                        # Cached API responses (gitignored)
└── results/                      # Output charts + YAML (gitignored)
```

## Implementation Order

1. **YAML configs** — `country_mapping.yaml`, `lead_indicator_config.yaml`
2. **Data fetcher** — `macro_data_fetcher.py` (World Bank first, then FRED, then currency)
3. **Scoring engine** — `lead_indicator_engine.py` (Tier 1 first, then add Tier 2)
4. **Backtest** — `backtest_lead_signals.py` (Thailand first, then all countries)
5. **Validate** — run Thailand case study, review charts, iterate thresholds

## New Dependencies

```
wbgapi>=1.0.0        # World Bank API (no key needed)
fredapi>=0.5.0       # FRED API (free key from fred.stlouisfed.org)
python-dotenv>=1.0.0 # Load FRED_API_KEY from .env
```

---

## Key Design Decisions

1. **Z-scores per country's own history** — don't compare Thailand's PE to Germany's PE; compare to Thailand's own 10-year median
2. **Account for World Bank data lag** — only use data that would have been available at each point in time (no look-ahead bias)
3. **Historical PE proxy** — yfinance only gives current trailing PE, so use price / 10-year rolling average price as crude CAPE proxy for backtesting
4. **Graceful degradation** — if no FRED API key, skip yield curve and run with World Bank + price data only
5. **Reuse existing infrastructure** — load `data/etf_price.csv` for prices, follow `etf_data_fetcher.py` caching patterns

---

## Sources

- [Buffett Indicator - LongtermTrends](https://www.longtermtrends.com/market-cap-to-gdp-the-buffett-indicator/)
- [Buffett Indicator - Wikipedia](https://en.wikipedia.org/wiki/Buffett_indicator)
- [CAPE Ratios by Country - Siblis Research](https://siblisresearch.com/data/cape-ratios-by-country/)
- [CAPE ratio by country - Monevator](https://monevator.com/cape-ratio-by-country/)
- [Leading Economic Indicators - Commons LLC](https://www.commonsllc.com/insights/leading-economic-indicators-for-stock-market)
- [MSCI PE Ratio by Country - MacroMicro](https://en.macromicro.me/collections/5739/msci-index-pe-ratio)
- [Market Cap to GDP by Country - Siblis Research](https://siblisresearch.com/data/market-cap-to-gdp-ratios/)
- [Robert Shiller Online Data - Yale](http://www.econ.yale.edu/~shiller/data.htm)
- [PMI - S&P Global](https://www.spglobal.com/market-intelligence/en/solutions/products/pmi)
