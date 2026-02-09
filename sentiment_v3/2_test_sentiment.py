#!/usr/bin/env python3
"""
Quick test script for ETF Sentiment Analysis
Tests the system with a single ETF without requiring web search
"""

import yaml
from pathlib import Path
from datetime import datetime

# Mock forecast data for testing
MOCK_FORECASTS = {
    "ARGT": [
        {
            "sentiment": "Global X MSCI Argentina ETF (ARGT) shows strong bearish outlook. Analysts forecast a -30.22% decline to $62.98 in the next 30 days. The 12-month price target is $71.36, representing a -20.93% downside from current levels.",
            "source": "Stockscan",
            "url": "https://stockscan.io/stocks/ARGT/forecast",
            "author": "Market Analyst",
            "datetime": "2026-02-07T00:00:00Z"
        }
    ],
    "GLD": [
        {
            "sentiment": "SPDR Gold Shares (GLD) expected to rise 8% in Q1 2026 as investors seek safe-haven assets amid market uncertainty. Technical indicators suggest bullish momentum with price targets around $195-200.",
            "source": "Gold Market Research",
            "url": "https://example.com/gold-forecast",
            "author": "Gold Analyst",
            "datetime": "2026-02-07T00:00:00Z"
        }
    ],
    "XLK": [
        {
            "sentiment": "Technology Select Sector SPDR (XLK) maintains neutral outlook. While AI stocks show strength, concerns about valuations and interest rates create mixed signals. Analysts suggest range-bound trading between $200-215.",
            "source": "Tech Market Watch",
            "url": "https://example.com/tech-forecast",
            "author": "Tech Analyst",
            "datetime": "2026-02-07T00:00:00Z"
        }
    ]
}


def test_with_mock_data(ticker: str = "ARGT", provider: str = "anthropic"):
    """Test the sentiment analysis with mock data (no web search required)."""
    print(f"Testing ETF Sentiment Analysis with {ticker}")
    print(f"Provider: {provider}")
    print("="*60)

    import importlib.util
    spec = importlib.util.spec_from_file_location("generate_sentiment", Path(__file__).parent / "1_generate_sentiment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ETFSentimentAnalyzer = module.ETFSentimentAnalyzer

    # Initialize analyzer
    analyzer = ETFSentimentAnalyzer(provider=provider)

    # Load ETF config
    etf_list = analyzer.load_etf_config()
    etf = next((e for e in etf_list if e['ticker'] == ticker), None)

    if not etf:
        print(f"Error: ETF {ticker} not found in config")
        return

    print(f"\nETF: {etf['ticker']} - {etf['name']}")
    print(f"Category: {etf['category']} | Segment: {etf['segment']}")

    # Get mock forecasts
    forecasts = MOCK_FORECASTS.get(ticker, [])

    if not forecasts:
        print(f"\nNo mock data available for {ticker}")
        print("Available tickers with mock data:", list(MOCK_FORECASTS.keys()))
        return

    print(f"\nProcessing {len(forecasts)} mock forecast(s)...")

    # Score each forecast
    scored_forecasts = []
    for i, forecast in enumerate(forecasts, 1):
        print(f"\n[{i}/{len(forecasts)}] Scoring forecast...")
        print(f"  Source: {forecast['source']}")
        print(f"  Text: {forecast['sentiment'][:100]}...")

        sentiment_result = analyzer.score_sentiment(forecast['sentiment'])

        print(f"  Score: {sentiment_result['score']}")
        print(f"  Label: {sentiment_result['sentiment_label']}")
        print(f"  Reasoning: {sentiment_result['reasoning']}")

        scored_forecast = {
            'sentiment': forecast['sentiment'],
            'source': forecast['source'],
            'url': forecast['url'],
            'author': forecast['author'],
            'datetime': forecast['datetime'],
            'sentiment_result': {
                'llm_result': sentiment_result
            }
        }

        scored_forecasts.append(scored_forecast)

    # Write output
    print(f"\nWriting output...")
    analyzer.write_output(etf, scored_forecasts)

    print(f"\n✓ Test completed successfully!")
    print(f"Check output file: generate/etf_sentiment_{ticker.lower()}.yaml")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Test ETF Sentiment Analysis')
    parser.add_argument('--ticker', default='ARGT', help='ETF ticker to test')
    parser.add_argument('--provider', default='anthropic', choices=['anthropic', 'openai'],
                        help='LLM provider')

    args = parser.parse_args()

    test_with_mock_data(ticker=args.ticker, provider=args.provider)
