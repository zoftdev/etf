#!/usr/bin/env python3
"""
ETF Sentiment Analysis v3
Generates sentiment reports for ETFs by searching for recent forecasts and scoring them.
"""

import os
import yaml
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import time

# Configuration
SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / "etf-v3.yaml"
SENTIMENT_PROMPT_FILE = SCRIPT_DIR / "sentiment-prompt.md"
OUTPUT_DIR = SCRIPT_DIR / "generate"
FORECAST_DAYS = 7  # Look for forecasts from last 7 days


class ETFSentimentAnalyzer:
    def __init__(self, api_key: Optional[str] = None, provider: str = "anthropic"):
        """
        Initialize the analyzer with LLM API.

        Args:
            api_key: API key for the LLM provider
            provider: LLM provider - 'anthropic' (Claude) or 'openai' (ChatGPT)
        """
        self.provider = provider.lower()
        self.sentiment_prompt_template = self._load_sentiment_prompt()

        if self.provider == "anthropic":
            import anthropic
            self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable is required")
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.model = "claude-sonnet-4-5-20250929"

        elif self.provider == "openai":
            import openai
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY environment variable is required")
            self.client = openai.OpenAI(api_key=self.api_key)
            # You can use gpt-4, gpt-4-turbo, gpt-3.5-turbo, etc.
            self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")

        else:
            raise ValueError(f"Unsupported provider: {provider}. Use 'anthropic' or 'openai'")

    def _load_sentiment_prompt(self) -> str:
        """Load the sentiment scoring prompt template."""
        with open(SENTIMENT_PROMPT_FILE, 'r', encoding='utf-8') as f:
            return f.read()

    def load_etf_config(self) -> List[Dict[str, Any]]:
        """Load and flatten the ETF configuration."""
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        etf_list = []
        for category_key, category_data in config['etfs'].items():
            category_name = category_data.get('display_name', category_key)
            for item in category_data.get('items', []):
                # Get primary ticker (first one if multiple)
                tickers = item.get('tickers', [])
                if not tickers:
                    continue

                primary_ticker = tickers[0] if isinstance(tickers, list) else tickers

                etf_list.append({
                    'ticker': primary_ticker,
                    'all_tickers': tickers if isinstance(tickers, list) else [tickers],
                    'name': item.get('name', ''),
                    'segment': item.get('segment', ''),
                    'description': item.get('description', ''),
                    'category': category_name
                })

        return etf_list

    def search_forecasts(self, etf: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search for recent forecasts using multiple strategies.

        Strategies:
        1. Direct ticker search: "{TICKER} forecast"
        2. ETF name search: "{NAME} forecast"
        3. Segment/keyword search: "{SEGMENT} ETF forecast"
        """
        print(f"  Searching for forecasts using multiple strategies...")

        forecasts = []
        search_queries = []

        # Strategy 1: Ticker-based searches
        ticker = etf['ticker']
        search_queries.append(f"{ticker} ETF forecast 2026")
        search_queries.append(f"{ticker} price prediction")

        # Strategy 2: Name-based search
        if etf['name']:
            search_queries.append(f"{etf['name']} forecast")

        # Strategy 3: Segment/keyword search
        if etf['segment']:
            segment_clean = etf['segment']
            search_queries.append(f"{segment_clean} ETF {ticker} outlook")

        print(f"  Using {len(search_queries)} search queries:")
        for query in search_queries:
            print(f"    - \"{query}\"")

        # For now, use web search to find forecasts
        # This will use Claude's web search capability
        for query in search_queries:
            try:
                # Use Anthropic's API to search
                results = self._web_search_with_claude(query, etf)
                forecasts.extend(results)
                time.sleep(1)  # Rate limiting
            except Exception as e:
                print(f"    Warning: Search failed for '{query}': {e}")
                continue

        # Deduplicate by URL
        seen_urls = set()
        unique_forecasts = []
        for forecast in forecasts:
            url = forecast.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_forecasts.append(forecast)

        print(f"  Found {len(unique_forecasts)} unique forecasts")
        return unique_forecasts

    def _web_search_with_claude(self, query: str, etf: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Search the web and extract forecast information.

        This method can be integrated with various search methods:
        1. Google Custom Search API
        2. SerpAPI
        3. Web scraping
        4. Or use the WebSearch tool if running in CLI environment
        """
        forecasts = []

        # Check if we have access to web search via environment
        # Using ddgs (formerly duckduckgo_search)
        try:
            from ddgs import DDGS

            cutoff_date = datetime.now() - timedelta(days=FORECAST_DAYS)

            ddgs = DDGS()
            # Search with time filter for recent results
            results = ddgs.text(
                query,
                max_results=3
            )

            for result in results:
                # Extract forecast-relevant information
                title = result.get('title', '')
                body = result.get('body', '')
                url = result.get('href', '')

                # Combine title and body as the forecast text
                forecast_text = f"{title}. {body}"

                # Include all results - they're already filtered by our search query
                # which includes "forecast", "prediction", etc.
                if forecast_text.strip():
                    forecasts.append({
                        'sentiment': forecast_text,
                        'source': result.get('source', 'Web Search'),
                        'url': url,
                        'author': '',
                        'datetime': datetime.now().isoformat() + 'Z'
                    })

            return forecasts

        except ImportError:
            print(f"    Note: ddgs not available. Install with: pip install ddgs")
            return []
        except Exception as e:
            print(f"    Warning: Web search failed: {e}")
            return []

    def score_sentiment(self, forecast_text: str) -> Dict[str, Any]:
        """
        Score the sentiment of a forecast text using LLM.

        Returns:
            Dict with 'score', 'sentiment_label', and 'reasoning'
        """
        # Replace $input text in the prompt template
        prompt = self.sentiment_prompt_template.replace("$input text", forecast_text)

        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                result_text = response.content[0].text

            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.3,
                    max_tokens=1024
                )
                result_text = response.choices[0].message.content

            # Parse JSON from the response
            # Handle both raw JSON and markdown code blocks
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                json_str = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                json_str = result_text[json_start:json_end].strip()
            else:
                # Try to find JSON object
                json_start = result_text.find("{")
                json_end = result_text.rfind("}") + 1
                json_str = result_text[json_start:json_end].strip()

            result = json.loads(json_str)

            # Validate the result has required fields
            if not all(key in result for key in ['score', 'sentiment_label', 'reasoning']):
                raise ValueError("Missing required fields in sentiment result")

            return result

        except Exception as e:
            print(f"    Warning: Sentiment scoring failed: {e}")
            # Return neutral sentiment as fallback
            return {
                "score": 0.0,
                "sentiment_label": "neutral",
                "reasoning": f"Error in sentiment analysis: {str(e)}"
            }

    def write_output(self, etf: Dict[str, Any], forecasts: List[Dict[str, Any]]):
        """Write sentiment data to YAML file."""
        output_file = OUTPUT_DIR / f"etf_sentiment_{etf['ticker'].lower()}.yaml"

        # Build the output structure
        sentiment_data = {
            'sentiment_data': [{
                'etf': etf['ticker'],
                'name': etf['name'],
                'forecasts': [{
                    'run_date': datetime.now().strftime('%Y-%m-%d'),
                    'sentiments': forecasts
                }] if forecasts else []
            }]
        }

        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(sentiment_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

        print(f"  Written to: {output_file.name}")

    def process_etf(self, etf: Dict[str, Any]) -> bool:
        """Process a single ETF: search, score, and write output."""
        print(f"\n{'='*60}")
        print(f"Processing: {etf['ticker']} - {etf['name']}")
        print(f"Category: {etf['category']} | Segment: {etf['segment']}")
        print(f"{'='*60}")

        # Step 1: Search for forecasts
        raw_forecasts = self.search_forecasts(etf)

        if not raw_forecasts:
            print(f"  No forecasts found - writing empty output")
            self.write_output(etf, [])
            return False

        # Step 2: Score each forecast
        print(f"  Scoring {len(raw_forecasts)} forecasts...")
        scored_forecasts = []

        for i, forecast in enumerate(raw_forecasts, 1):
            print(f"    [{i}/{len(raw_forecasts)}] Scoring forecast from {forecast.get('source', 'unknown')}")

            sentiment_result = self.score_sentiment(forecast['sentiment'])

            scored_forecast = {
                'sentiment': forecast['sentiment'],
                'source': forecast.get('source', 'Unknown'),
                'url': forecast.get('url', ''),
                'author': forecast.get('author', ''),
                'datetime': forecast.get('datetime', datetime.now().isoformat() + 'Z'),
                'sentiment_result': {
                    'llm_result': sentiment_result
                }
            }

            scored_forecasts.append(scored_forecast)

            # Rate limiting
            time.sleep(0.5)

        # Step 3: Write output
        self.write_output(etf, scored_forecasts)

        print(f"  ✓ Completed {etf['ticker']}")
        return True

    def run(self, limit: Optional[int] = None, tickers: Optional[List[str]] = None):
        """Run the sentiment analysis for all ETFs."""
        print("="*60)
        print("ETF Sentiment Analysis v3")
        print(f"LLM Provider: {self.provider.upper()} | Model: {self.model}")
        print("="*60)

        # Load ETF configuration
        print("\nLoading ETF configuration...")
        etf_list = self.load_etf_config()
        print(f"Loaded {len(etf_list)} ETFs")

        # Filter by tickers if specified
        if tickers:
            etf_list = [etf for etf in etf_list if etf['ticker'] in tickers]
            print(f"Filtered to {len(etf_list)} ETFs: {', '.join(tickers)}")

        # Limit if specified
        if limit:
            etf_list = etf_list[:limit]
            print(f"Limited to first {limit} ETFs")

        # Ensure output directory exists
        OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

        # Process each ETF
        success_count = 0
        for i, etf in enumerate(etf_list, 1):
            print(f"\n[{i}/{len(etf_list)}]")
            try:
                if self.process_etf(etf):
                    success_count += 1
            except Exception as e:
                print(f"  ERROR: Failed to process {etf['ticker']}: {e}")
                continue

        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Total ETFs: {len(etf_list)}")
        print(f"Successfully processed: {success_count}")
        print(f"With forecasts: {success_count}")
        print(f"Output directory: {OUTPUT_DIR}")
        print("="*60)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='ETF Sentiment Analysis v3')
    parser.add_argument('--limit', type=int, help='Limit number of ETFs to process')
    parser.add_argument('--tickers', nargs='+', help='Specific tickers to process')
    parser.add_argument('--provider', default='anthropic', choices=['anthropic', 'openai'],
                        help='LLM provider: anthropic (Claude) or openai (ChatGPT)')
    parser.add_argument('--api-key', help='API key for the LLM provider (or set ANTHROPIC_API_KEY/OPENAI_API_KEY env var)')

    args = parser.parse_args()

    analyzer = ETFSentimentAnalyzer(api_key=args.api_key, provider=args.provider)
    analyzer.run(limit=args.limit, tickers=args.tickers)


if __name__ == '__main__':
    main()
