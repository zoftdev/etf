# Results: Macro Forecast vs Buy-and-Hold

## Summary (--end 2022, pure recommendation period)

```
Strategy                              Final $   Total %    Ann %   MaxDD%  #ETFs  Beat B&H?
-------------------------------------------------------------------------------------------------------------------
B&H ALL 60 ETFs                     1,831,884     83.2%    5.10%   -34.2%     47  ref
B&H Rec Universe (17 ETFs)          2,340,443    134.0%    7.24%   -34.2%     14  BASELINE
-------------------------------------------------------------------------------------------------------------------
US-Sector Only ScWt                 5,916,541    491.7%   15.73%   -34.0%      3  YES
US-Sector Only EqWt                 5,616,893    461.7%   15.24%   -33.8%      3  YES
US-Sect+Commod ScWt                 2,407,525    140.8%    7.49%   -41.1%      7  YES
-------------------------------------------------------------------------------------------------------------------
EqWt All Recs                       1,749,349     74.9%    4.70%   -36.2%     13  no
Score-Wt All Recs                   1,729,042     72.9%    4.60%   -38.0%     13  no
Countries Only ScWt                 1,140,932     14.1%    1.09%   -40.4%      6  no
Top-3 Score-Wt                        650,157    -35.0%   -3.48%   -58.5%      3  no
```

## Winners (consistent across all time windows)

| Strategy | End 2022 | End 2023 | End 2025 | Verdict |
|---|---|---|---|---|
| **US-Sector Only ScWt** | $5.92M (15.73%) | $6.64M (15.46%) | $8.18M (14.85%) | Strong winner |
| **US-Sector Only EqWt** | $5.62M (15.24%) | $6.33M (15.05%) | $7.82M (14.51%) | Strong winner |
| **US-Sect+Commod ScWt** | $2.41M (7.49%) | $2.56M (7.41%) | $3.80M (9.20%) | Marginal winner |

## Per-Year Return Breakdown (2010-2022)

```
Year    B&H All60    B&H Rec17    US-Sect ScWt   US-Sect EqWt
2010       5.2%         6.9%          2.9%           2.7%
2011     -12.0%        -5.0%          5.3%           6.4%     <-- sectors avoided EM crash
2012      12.1%         7.5%         14.6%          14.8%
2013       7.3%         8.6%         29.1%          30.7%     <-- XLK heavy
2014       2.6%         5.4%         19.7%          20.2%
2015      -7.6%        -5.8%          2.8%           2.5%     <-- sectors avoided EM/commodity crash
2016       9.5%        13.0%         16.0%          15.1%
2017      22.8%        19.5%         18.8%          17.2%
2018     -10.8%        -7.7%        -11.7%         -12.4%     <-- only loss year (XLF+XLE)
2019      23.1%        25.6%         22.3%          21.6%
2020      11.7%        12.8%         22.2%          21.1%     <-- reopening call (XLI, XLY)
2021      16.9%        23.0%         34.7%          34.9%     <-- XLE energy surge
2022     -13.3%       -14.0%         13.5%          10.3%     <-- XLV defensive + XLE
```

## Winning Strategy Allocations

### US-Sector Only ScWt (best performer)

Holds 2-3 US sector ETFs each year, score-weighted:

```
2010-2012: XLK + XLV (tech + healthcare)
2013-2014: XLK + XLF + XLV (added financials)
2015:      XLK + XLY + XLV (swapped financials for consumer disc.)
2016-2017: XLK + XLF + XLE (added energy)
2018:      XLF + XLE (no tech -- worst year)
2019:      XLK + XLF + XLV (back to tech)
2020:      XLI + XLE + XLY (reopening plays)
2021:      XLE + XLF + XLI (energy + value rotation)
2022:      XLV + XLY + XLE (defensive + energy)
```

## Key Findings

### 1. Country recommendations destroyed value
- Countries Only: +14% total over 12 years (1.09% ann) -- dramatically below baseline
- The forecasts consistently overweighted BRIC/EM countries (China, India, Brazil, Russia)
- GDP growth != stock market returns, especially for EM equities
- EM underperformed US/DM massively during 2010-2022

### 2. US sector rotation calls added significant alpha
- US-Sector Only: +492% total (15.73% ann) vs baseline +134% (7.24% ann)
- The forecasts correctly identified: Tech dominance (2010-2017, 2019), Energy surge (2021-2022), defensive positioning (2022)
- Only 2-3 ETFs held per year, yet beat 17-ETF buy-hold by 2x+ annually

### 3. Score-weighting slightly helps
- US-Sector ScWt ($5.92M) > US-Sector EqWt ($5.62M)
- Suggests the conviction score has marginal predictive value within categories
- Difference is small, so either approach works

### 4. More concentration != better (with all categories)
- Top-3 and Top-5 across all categories performed worst (-23% to -35%)
- Because highest scores are always country ETFs (China 0.95, India 0.90) which underperformed
- Concentration only works within the right category (us_sector)

### 5. Commodity is neutral-to-negative
- Commodity Only: +59% (3.88% ann) -- below baseline
- USO (oil) had extreme volatility (-71% maxDD)
- Adding commodity to US-sector dilutes returns

### 6. Rebalance timing matters little
- Jan/Oct/Dec rebalance: all within ~1.5% annualized of each other
- The category selection is the dominant factor, not timing

## Conclusion

The macro forecasts contain **strong predictive signal for US sector rotation** but **negative signal for country/EM allocation**. The optimal strategy is:

1. **Use only `us_sector` recommendations** from forecast.json
2. **Ignore countries and commodities**
3. **Score-weight or equal-weight** (both work, score-weight slightly better)
4. **Rebalance annually** in October
5. **Hold 2-3 sector ETFs** per year

This produces ~15% annualized returns vs ~7% for buy-hold, with similar max drawdown (~34%).
