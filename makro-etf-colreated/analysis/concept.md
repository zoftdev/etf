# Concept: Beating Buy-and-Hold with Macro Forecast Recommendations

## Question

Can publicly available macro-economic forecasts (IMF WEO, World Bank GEP, commodity outlooks, sector analyst reports) be used to construct an ETF portfolio that **outperforms** a simple buy-and-hold strategy?

## Data Pipeline

```
Macro Reports (IMF, World Bank, analyst)
        |
        v
forecast.json          -- per-year scored recommendations
        |               (countries, commodities, US sectors)
        v
etf-mapping.json       -- maps recommendation names to ETF tickers
        |
        v
etf_price.csv          -- daily close prices for 60 ETFs (2005-2026)
        |
        v
Strategy Engine        -- test multiple allocation strategies
        |
        v
Benchmark Result       -- compare vs buy-and-hold on same universe
```

## Core Hypothesis

Macro forecasts provide directional signals with conviction scores (0-1). If these scores contain predictive value, a strategy that **weights allocations by score** and **selects by category** should beat equal-weight buy-and-hold of the same ETF universe.

## Investable Universe

17 ETFs mapped from forecast recommendations:

| Category | Tickers |
|---|---|
| Countries | MCHI, FXI (China), INDA (India), EWZ (Brazil), EIDO (Indonesia), ERUS (Russia), VEA (US/Dev) |
| Commodity | USO (Oil), XLE (Energy), GLD (Gold), SLV (Silver), DBA (Agriculture) |
| US Sector | XLK (Tech), XLV (Healthcare), XLF (Financials), XLY (Cons. Disc.), XLI (Industrials) |

## Benchmark Design

- **Baseline**: Buy-and-hold equal-weight of 17 recommendation-mapped ETFs
- **Fair comparison**: Same investable universe, different weighting/selection
- **Period**: Oct 2010 (first recommendation) through Dec 2022 (last recommendation year)
- **Initial capital**: $1,000,000
- **Rebalance**: Annually in October (when forecasts are typically published)

## Key Insight

The forecast has **three independent signal categories** (countries, commodity, us_sector). Not all categories may add value. The analysis decomposes the signal to find which category combinations and weighting schemes produce alpha.
