#!/usr/bin/env python3
"""Search for ETF forecasts from 2025 predicting 2026"""

import csv
import yaml
import re
from pathlib import Path
from datetime import datetime
from web_search import web_search

def get_ticker_from_yaml(etf_name, yaml_path):
    """Find ticker symbol for ETF name from etf.yaml"""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    etfs = data.get('etfs', {})
    
    # Search through all categories
    for category in etfs.values():
        if isinstance(category, dict):
            # Check specific items
            if 'specific' in category:
                for item in category['specific']:
                    if item.get('name') == etf_name:
                        return item.get('ticker', '')
            # Check broad items
            if 'broad' in category:
                for item in category['broad']:
                    if item.get('name') == etf_name:
                        return item.get('ticker', '')
            # Check items list
            if 'items' in category:
                for item in category['items']:
                    if item.get('name') == etf_name:
                        return item.get('ticker', '')
            # Check etfs list (for world ETFs)
            if 'etfs' in category:
                for item in category['etfs']:
                    if item.get('name') == etf_name:
                        tickers = item.get('tickers', [])
                        return tickers[0] if tickers else ''
    
    return ''

def search_forecasts(etf_name, ticker, search_term, num_sources=15):
    """Search for forecasts about the ETF"""
    queries = [
        f"{etf_name} {ticker} forecast 2026",
        f"{etf_name} {ticker} prediction 2026",
        f"{etf_name} {ticker} outlook 2026",
        f"{ticker} ETF forecast 2026",
        f"{ticker} ETF prediction 2026",
        f"{search_term} ETF forecast 2026",
        f"{search_term} ETF prediction 2026",
        f"{etf_name} 2026 price target",
        f"{ticker} 2026 target price",
        f"{etf_name} 2026 outlook",
        f"{ticker} 2026 forecast analysis",
        f"{search_term} market forecast 2026",
        f"{etf_name} investment outlook 2026",
        f"{ticker} ETF 2026 forecast",
        f"{search_term} ETF 2026 prediction",
    ]
    
    all_results = []
    seen_urls = set()
    
    # Search with queries, limiting to 2025 dates
    for query in queries[:num_sources]:
        search_query = f"{query} site:*.com OR site:*.org filetype:pdf OR filetype:html"
        try:
            results = web_search(search_query)
            if results:
                for result in results:
                    url = result.get('url', '')
                    if url and url not in seen_urls:
                        # Check if result mentions 2025 or 2026
                        snippet = result.get('snippet', '') + ' ' + result.get('title', '')
                        if '2025' in snippet or '2026' in snippet:
                            seen_urls.add(url)
                            all_results.append({
                                'title': result.get('title', ''),
                                'url': url,
                                'snippet': result.get('snippet', ''),
                                'date': extract_date(result.get('date', ''), snippet)
                            })
        except Exception as e:
            print(f"Error searching with query '{query}': {e}")
            continue
    
    return all_results

def extract_date(date_str, snippet):
    """Extract date from string, prefer 2025 dates"""
    if not date_str and not snippet:
        return None
    
    text = (date_str or '') + ' ' + (snippet or '')
    
    # Look for 2025 dates
    patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+2025',
        r'(\d{1,2})/(\d{1,2})/2025',
        r'2025-(\d{2})-(\d{2})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                if 'January' in match.group(0) or 'February' in match.group(0):
                    # Parse month name format
                    date_str = match.group(0)
                    return parse_date_string(date_str)
                else:
                    return match.group(0)
            except:
                continue
    
    # Default to 2025-01-01 if we found 2025 mention
    if '2025' in text:
        return '2025-01-01'
    
    return None

def parse_date_string(date_str):
    """Parse various date formats"""
    # Try common formats
    formats = [
        '%Y-%m-%d',
        '%B %d, %Y',
        '%m/%d/%Y',
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except:
            continue
    
    return date_str

def create_yaml_output(etf_name, ticker, forecasts):
    """Create YAML structure matching the example format"""
    # Filter forecasts to only 2025 documents predicting 2026
    filtered_forecasts = []
    
    for forecast in forecasts:
        date = forecast.get('date', '')
        snippet = forecast.get('snippet', '') + ' ' + forecast.get('title', '')
        
        # Check if it's from 2025 and mentions 2026
        if date and '2025' in date and ('2026' in snippet or 'forecast' in snippet.lower() or 'prediction' in snippet.lower()):
            filtered_forecasts.append({
                'year': 2025,
                'forecast_year': 2026,
                'sentiments': [{
                    'sentiment': forecast.get('snippet', '')[:500],  # Limit length
                    'source': extract_source(forecast.get('url', '')),
                    'author': '',  # Would need to extract from content
                    'date': date if date else '2025-01-01',
                    'sentiment_score': 0.0
                }]
            })
    
    if not filtered_forecasts:
        # Create empty structure if no forecasts found
        filtered_forecasts = [{
            'year': 2025,
            'forecast_year': 2026,
            'sentiments': []
        }]
    
    return {
        'sentiment_data': [{
            'etf': ticker,
            'name': etf_name,
            'forecasts': filtered_forecasts
        }]
    }

def extract_source(url):
    """Extract source name from URL"""
    if not url:
        return 'Unknown'
    
    # Remove protocol
    url = url.replace('https://', '').replace('http://', '')
    # Get domain
    domain = url.split('/')[0]
    # Remove www.
    domain = domain.replace('www.', '')
    # Get main domain name
    parts = domain.split('.')
    if len(parts) >= 2:
        return parts[-2].capitalize()
    return domain.capitalize()

def process_first_line():
    """Process the first line from etf-list.csv"""
    workspace_root = Path(__file__).parent.parent
    csv_path = workspace_root / 'sentiment_v2' / 'etf-list.csv'
    done_csv_path = workspace_root / 'sentiment_v2' / 'done.csv'
    yaml_path = workspace_root / 'etf.yaml'
    
    # Read CSV
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        lines = list(reader)
    
    if not lines:
        print("CSV file is empty!")
        return
    
    # Get first line
    first_line = lines[0]
    etf_name, search_term = first_line[0].split('|')
    
    print(f"Processing: {etf_name} | {search_term}")
    
    # Get ticker
    ticker = get_ticker_from_yaml(etf_name, yaml_path)
    if not ticker:
        print(f"Warning: Could not find ticker for {etf_name}")
        ticker = etf_name.split()[-1]  # Fallback
    
    print(f"Ticker: {ticker}")
    
    # Search for forecasts
    print("Searching for forecasts...")
    forecasts = search_forecasts(etf_name, ticker, search_term, num_sources=15)
    print(f"Found {len(forecasts)} results")
    
    # Create YAML output
    yaml_data = create_yaml_output(etf_name, ticker, forecasts)
    
    # Write YAML file
    output_file = workspace_root / 'sentiment_v2' / f'etf_sentiment_{ticker.lower()}.yaml'
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(yaml_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    print(f"Written to: {output_file}")
    
    # Move line to done.csv
    remaining_lines = lines[1:]
    
    # Update etf-list.csv
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(remaining_lines)
    
    # Append to done.csv
    done_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(done_csv_path, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(first_line)
    
    print(f"Moved line to done.csv")
    print(f"Remaining lines in CSV: {len(remaining_lines)}")

if __name__ == '__main__':
    process_first_line()
