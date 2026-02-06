# Sentiment Data for ETF Backtesting

## Overview

This directory contains historical sentiment forecasts for 10 popular ETFs, designed for backtesting trading strategies. Each file contains year-by-year forecasts that were made at the time, predicting the sentiment and outlook for the following year.

## Purpose

The sentiment data captures historical market forecasts and outlooks for each ETF, allowing backtesting systems to:
- Evaluate how sentiment predictions correlated with actual performance
- Test trading strategies based on sentiment analysis
- Understand market expectations at different points in time
- Generate sentiment scores from historical forecast text

## File Structure

Each ETF has a corresponding YAML file named `etf_sentiment_{TICKER}.yaml` (e.g., `etf_sentiment_gld.yaml`).

### YAML Structure

```yaml
sentiment_data:
  - etf: TICKER
    name: Full ETF Name
    forecasts:
      - year: YYYY
        forecast_year: YYYY+1
        sentiment: |
          Multi-line paragraph summarizing
          market forecasts and outlook for
          the forecast year, based on
          news and analysis from the year
          of the forecast.
```

### Fields Explained

- **etf**: ETF ticker symbol (e.g., "GLD", "VEA", "XLK")
- **name**: Full name of the ETF (e.g., "SPDR Gold Shares")
- **forecasts**: List of forecast entries, sorted by year (descending)
  - **year**: The year when the forecast was made (e.g., 2024)
  - **forecast_year**: The year being forecasted (typically year + 1, e.g., 2025)
  - **sentiment**: A 4-line maximum paragraph summarizing:
    - Market outlook and predictions
    - Key factors driving the forecast
    - Economic conditions and trends
    - Risks and opportunities

## Available ETFs

The sentiment data covers 10 ETFs:

1. **GLD** - SPDR Gold Shares (Commodity)
2. **MTUM** - iShares MSCI USA Momentum Factor (Momentum)
3. **MCHI** - iShares MSCI China (Asia Pacific)
4. **EWJ** - iShares MSCI Japan (Asia Pacific)
5. **EWY** - iShares MSCI South Korea (Asia Pacific)
6. **EWG** - iShares MSCI Germany (Europe)
7. **EWZ** - iShares MSCI Brazil (Americas)
8. **VWO** - Vanguard FTSE Emerging Markets (Broad Market)
9. **VEA** - Vanguard FTSE Developed Markets (Broad Market)
10. **XLK** - SPDR Technology Select Sector ETF (US Sector)

## Historical Coverage

Most ETFs have approximately 20 years of historical forecasts (2004-2024, forecasting 2005-2025), except:
- **GLD**: 7 years of forecasts (2018-2024, forecasting 2019-2025)

## Data Sources

The sentiment data is derived from:
- Real historical news articles and market analysis
- IMF World Economic Outlook reports
- Financial institution forecasts (Forrester, Gartner, Deloitte, etc.)
- Market research reports
- Year-end predictions and outlooks

For country/region ETFs, searches used descriptive terms (e.g., "Developed Markets" for VEA, "Emerging Markets" for VWO, "Technology sector" for XLK) rather than just ticker symbols to capture broader market sentiment.

## Usage for Backtesting

### Example: Reading Sentiment Data

```python
import yaml

# Load sentiment data
with open('sentiment_data/etf_sentiment_gld.yaml', 'r') as f:
    data = yaml.safe_load(f)

# Access forecasts
etf_data = data['sentiment_data'][0]
ticker = etf_data['etf']  # "GLD"
name = etf_data['name']   # "SPDR Gold Shares"

# Iterate through forecasts
for forecast in etf_data['forecasts']:
    year = forecast['year']              # Year of forecast
    forecast_year = forecast['forecast_year']  # Year being forecasted
    sentiment_text = forecast['sentiment']    # Forecast paragraph
    
    # Use sentiment_text to generate sentiment score
    # Compare with actual performance in forecast_year
```

### Generating Sentiment Scores

The `sentiment` field contains natural language text that can be processed to generate numerical sentiment scores:

1. **Text Analysis**: Use NLP techniques (sentiment analysis, keyword extraction)
2. **Score Generation**: Convert text to numerical scores (e.g., -1 to +1, or 0 to 100)
3. **Backtesting**: Compare sentiment scores with actual ETF returns in the forecast year

### Example Workflow

```python
# 1. Extract sentiment for a specific year
forecast_2024 = next(f for f in forecasts if f['year'] == 2024)
sentiment_2024 = forecast_2024['sentiment']

# 2. Generate sentiment score (example using simple keyword matching)
positive_keywords = ['bullish', 'growth', 'strong', 'optimistic', 'rally']
negative_keywords = ['bearish', 'decline', 'weak', 'pessimistic', 'recession']

positive_count = sum(1 for word in positive_keywords if word in sentiment_2024.lower())
negative_count = sum(1 for word in negative_keywords if word in sentiment_2024.lower())

sentiment_score = (positive_count - negative_count) / max(len(positive_keywords), len(negative_keywords))

# 3. Compare with actual returns in 2025
actual_return_2025 = get_actual_return('GLD', 2025)
correlation = analyze_correlation(sentiment_score, actual_return_2025)
```

## Data Quality Notes

- **Multi-line Format**: Sentiment paragraphs use YAML literal block scalar (`|`) for readability
- **Historical Accuracy**: Data reflects actual forecasts made at the time, not retrospective analysis
- **Coverage**: Some years may have more detailed forecasts than others depending on available sources
- **Language**: All sentiment text is in English
- **Consistency**: Each forecast follows a similar structure and length (approximately 4 lines)

## Maintenance

When adding new forecasts:
1. Maintain the YAML structure
2. Use the custom YAML representer for multi-line strings (see update scripts)
3. Sort forecasts by year (descending)
4. Keep sentiment paragraphs to approximately 4 lines
5. Use real historical data sources, not fabricated content

## Related Files

- `etf_short.yaml`: Source list of 10 ETFs
- `update_*_historical.py`: Scripts used to generate/update sentiment files
- Backtesting scripts: Use this sentiment data to test trading strategies
