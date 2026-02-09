# ETF Sentiment Analysis v3

Automated sentiment analysis for ETFs using web search and LLM scoring.

## Features

- **Multi-strategy search**: Searches using ticker, ETF name, and segment keywords
- **Dual LLM support**: Works with both Claude (Anthropic) and ChatGPT (OpenAI)
- **Structured output**: YAML files matching standardized sentiment schema
- **Batch processing**: Process all ETFs or filter by ticker

## Setup

### 1. Install Dependencies

```bash
cd sentiment_v3
pip install -r requirements.txt
```

### 2. Set API Keys

#### For Claude (Anthropic):
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

#### For ChatGPT (OpenAI):
```bash
export OPENAI_API_KEY="your-api-key-here"
export OPENAI_MODEL="gpt-4-turbo-preview"  # Optional, defaults to gpt-4-turbo-preview
```

## Usage

### Basic Usage (Claude)

```bash
python 1_generate_sentiment.py
```

### Use ChatGPT instead

```bash
python 1_generate_sentiment.py --provider openai
```

### Process specific ETFs

```bash
python 1_generate_sentiment.py --tickers GLD SLV XLK
```

### Limit number of ETFs (for testing)

```bash
python 1_generate_sentiment.py --limit 5
```

### Combine options

```bash
python 1_generate_sentiment.py --provider openai --tickers ARGT --api-key "your-key"
```

## Search Strategies

For each ETF, the system searches using multiple queries:

1. **Ticker + forecast**: `"GLD ETF forecast 2026"`
2. **Ticker + prediction**: `"GLD price prediction"`
3. **Name + forecast**: `"SPDR Gold Shares forecast"`
4. **Segment + ticker**: `"ทองคำ ETF GLD outlook"` (uses segment from config)

This multi-strategy approach helps find more relevant forecasts.

## Output

Results are written to `generate/etf_sentiment_<TICKER>.yaml`:

```yaml
sentiment_data:
- etf: GLD
  name: SPDR Gold Shares
  forecasts:
  - run_date: 2026-02-07
    sentiments:
    - sentiment: "Gold ETF forecast text..."
      source: "Website Name"
      url: "https://..."
      author: "Author Name"
      datetime: "2026-02-07T00:00:00Z"
      sentiment_result:
        llm_result:
          score: 0.65
          sentiment_label: "buy"
          reasoning: "Explanation..."
```

## Sentiment Scale

- **-1.0 to -0.7**: Strong Sell (very bearish)
- **-0.7 to -0.3**: Sell (bearish)
- **-0.3 to 0.3**: Neutral (mixed outlook)
- **0.3 to 0.7**: Buy (bullish)
- **0.7 to 1.0**: Strong Buy (very bullish)

## Configuration Files

- `etf-v3.yaml`: List of ETFs to analyze (70+ ETFs across multiple categories)
- `sentiment-prompt.md`: LLM prompt template for scoring
- `example/etf_sentiment_argt.yaml`: Example output structure

## Web Search Options

By default, the system uses DuckDuckGo search (free, no API key required).

### Alternative Search Methods

You can modify `_web_search_with_claude()` to use:

1. **Google Custom Search API**:
   ```bash
   pip install google-api-python-client
   export GOOGLE_API_KEY="your-key"
   export GOOGLE_CSE_ID="your-cse-id"
   ```

2. **SerpAPI**:
   ```bash
   pip install serpapi
   export SERPAPI_KEY="your-key"
   ```

## Troubleshooting

### No forecasts found

- Check internet connection
- Try different search queries
- Verify the ETF ticker is correct
- Some ETFs may have limited recent coverage

### API rate limits

- Add delays between requests (adjust `time.sleep()` values)
- Process fewer ETFs at once using `--limit`
- Consider using different search providers

### LLM scoring errors

- Check API key is valid
- Ensure sufficient API credits
- Review prompt template in `sentiment-prompt.md`

## Development

See `detail-dev.md` for implementation details and architecture.

## License

Internal use only.
