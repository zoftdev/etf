"""
ETF Data Fetcher with Caching
Fetches historical ETF data and caches it to reduce API calls
"""
import os
import pickle
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed


class ETFDataFetcher:
    """Fetches and caches ETF data with optimization for large date ranges"""
    
    def __init__(self, yaml_path: str = "etf.yaml", cache_dir: str = "cache"):
        self.yaml_path = yaml_path
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.etf_data = self._load_yaml()
        self.tickers_map = self._extract_tickers()
        
    def _load_yaml(self) -> dict:
        """Load ETF configuration from YAML file"""
        with open(self.yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _format_group_name(self, key: str) -> str:
        """Format a YAML key into a readable group name"""
        # Replace underscores with spaces and capitalize words
        return key.replace('_', ' ').title()
    
    def _get_group_display_name(self, path_parts: List[str]) -> Optional[str]:
        """
        Get display name for a group path by traversing the YAML structure
        Checks for 'name' or 'display_name' fields at each level
        """
        current_node = self.etf_data.get('etfs', {})
        
        for part in path_parts:
            if isinstance(current_node, dict) and part in current_node:
                current_node = current_node[part]
            else:
                return None
        
        # Check for name or display_name at this level
        if isinstance(current_node, dict):
            return current_node.get('display_name') or current_node.get('name')
        
        return None
    
    def _build_group_path(self, path_parts: List[str]) -> str:
        """
        Build group name from path parts
        Uses name/display_name from YAML if available, otherwise formats key names
        """
        if not path_parts:
            return "Unknown"
        
        # Try to get display name for the full path
        display_name = self._get_group_display_name(path_parts)
        if display_name:
            return display_name
        
        # Build from individual path parts
        group_parts = []
        current_node = self.etf_data.get('etfs', {})
        
        for part in path_parts:
            if isinstance(current_node, dict) and part in current_node:
                # Check for name/display_name at this level
                if isinstance(current_node[part], dict):
                    part_display = current_node[part].get('display_name') or current_node[part].get('name')
                    if part_display:
                        group_parts.append(part_display)
                    else:
                        group_parts.append(self._format_group_name(part))
                else:
                    group_parts.append(self._format_group_name(part))
                
                current_node = current_node[part]
            else:
                group_parts.append(self._format_group_name(part))
        
        # Join with separator, but only if multiple parts
        if len(group_parts) == 1:
            return group_parts[0]
        return ' - '.join(group_parts)
    
    def _get_market_from_path(self, path_parts: List[str]) -> Optional[str]:
        """
        Get market/exchange suffix from parent nodes in the path
        Checks for 'market' field in parent groups
        """
        current_node = self.etf_data.get('etfs', {})
        
        for part in path_parts:
            if isinstance(current_node, dict) and part in current_node:
                current_node = current_node[part]
                # Check for market at this level
                if isinstance(current_node, dict):
                    market = current_node.get('market') or current_node.get('exchange')
                    if market:
                        return market
            else:
                break
        
        return None
    
    def _extract_tickers_recursive(self, node: dict, path_parts: List[str], tickers_map: Dict[str, dict], parent_market: Optional[str] = None) -> None:
        """
        Recursively extract tickers from YAML structure
        Handles all group structures dynamically
        """
        if not isinstance(node, dict):
            return
        
        # Check for market at current node level (can override parent)
        # Priority: node market > parent market
        market = node.get('market') or node.get('exchange') or parent_market
        
        # Check if this node has a 'ticker' or 'tickers' field (it's an ETF item)
        if 'ticker' in node or 'tickers' in node:
            # Build group name from path (excluding 'etfs' and 'items' if present)
            filtered_path = [p for p in path_parts if p not in ['etfs', 'items']]
            group_name = self._build_group_path(filtered_path)
            
            # Extract tickers (single or multiple)
            tickers = []
            if 'ticker' in node:
                tickers.append(node['ticker'])
            elif 'tickers' in node:
                tickers = node['tickers'] if isinstance(node['tickers'], list) else [node['tickers']]
            
            # Extract metadata
            name = node.get('name', '')
            category = node.get('category', '') or node.get('sector', '') or node.get('country', '') or node.get('region', '') or node.get('index', '')
            description = node.get('description', '')
            
            # Add each ticker to the map
            for ticker in tickers:
                if ticker:  # Only add non-empty tickers
                    tickers_map[ticker] = {
                        'name': name or ticker,
                        'group': group_name,
                        'category': category,
                        'description': description,
                        'market': market  # Store market for API calls (can be None, str, or empty string)
                    }
            return
        
        # Check if this is a list of items
        if isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    self._extract_tickers_recursive(item, path_parts, tickers_map, parent_market)
            return
        
        # Recursively process nested dictionaries
        for key, value in node.items():
            # Skip metadata fields that aren't part of the structure
            # But we still need to traverse through 'name' fields to get to 'etfs' lists
            if key in ['display_name', 'market', 'exchange']:
                continue
            
            new_path = path_parts + [key]
            
            # Determine market to pass down: check value's market first, then use current market
            current_market = market  # Start with current level's market
            if isinstance(value, dict):
                # If nested dict has its own market, use it; otherwise inherit
                current_market = value.get('market') or value.get('exchange') or market
            
            if isinstance(value, list):
                # List of items - process each item with current path and market
                # Use current market (from parent) for all items in the list
                for item in value:
                    if isinstance(item, dict):
                        # Each item can override market, but defaults to current market
                        # Use market from current node level (which may have been set from parent)
                        item_market = item.get('market') or item.get('exchange') or market
                        self._extract_tickers_recursive(item, new_path, tickers_map, item_market)
            elif isinstance(value, dict):
                # Nested dictionary - check for market in the dict, otherwise use current market
                nested_market = value.get('market') or value.get('exchange') or market
                self._extract_tickers_recursive(value, new_path, tickers_map, nested_market)
    
    def _extract_tickers(self) -> Dict[str, dict]:
        """
        Extract all tickers from YAML structure dynamically
        Returns: {ticker: {name, group, category, market, ...}}
        """
        tickers_map = {}
        etfs_data = self.etf_data.get('etfs', {})
        
        # Start recursive extraction from the 'etfs' root
        self._extract_tickers_recursive(etfs_data, [], tickers_map, None)
        
        return tickers_map
    
    def _get_cache_path(self, ticker: str, period: str) -> Path:
        """Get cache file path for a ticker and period"""
        return self.cache_dir / f"{ticker}_{period}.pkl"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cache file exists and is less than 24 hours old"""
        if not cache_path.exists():
            return False
        
        # Check file modification time
        file_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age = datetime.now() - file_time
        
        # Cache is valid if less than 24 hours old
        return age < timedelta(hours=24)
    
    def _period_to_days(self, period: str) -> int:
        """Convert period string to number of days"""
        period_map = {
            '7d': 7,
            '1m': 30,
            '6m': 180,
            '1y': 365,
            '3y': 1095
        }
        return period_map.get(period, 7)
    
    def _optimize_data_points(self, df: pd.DataFrame, max_points: int = 500) -> pd.DataFrame:
        """
        Optimize data points for large datasets
        If data has more than max_points, downsample intelligently
        """
        if len(df) <= max_points:
            return df
        
        # Calculate sampling interval
        interval = len(df) // max_points
        
        # Downsample: take every Nth row
        # For very large datasets, we can use resample, but for simplicity, use iloc
        indices = list(range(0, len(df), interval))
        if indices[-1] != len(df) - 1:
            indices.append(len(df) - 1)  # Always include last point
        
        return df.iloc[indices].copy()
    
    def _get_yfinance_ticker(self, ticker: str) -> str:
        """
        Get the yfinance-compatible ticker symbol
        Appends market suffix if needed (e.g., .BK for Bangkok Stock Exchange)
        """
        ticker_info = self.tickers_map.get(ticker)
        if ticker_info and ticker_info.get('market'):
            market = ticker_info['market']
            # If market suffix doesn't start with '.', add it
            if not market.startswith('.'):
                return f"{ticker}.{market}"
            return f"{ticker}{market}"
        return ticker
    
    def _fetch_ticker_data(self, ticker: str, period: str) -> Tuple[str, Optional[pd.DataFrame], Optional[str]]:
        """
        Fetch data for a single ticker
        Returns: (ticker, dataframe, error_message)
        """
        cache_path = self._get_cache_path(ticker, period)
        
        # Check cache first
        if self._is_cache_valid(cache_path):
            try:
                with open(cache_path, 'rb') as f:
                    cached_data = pickle.load(f)
                    return ticker, cached_data, None
            except Exception as e:
                # If cache read fails, continue to fetch
                pass
        
        # Fetch from API
        try:
            days = self._period_to_days(period)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get yfinance-compatible ticker (with market suffix if needed)
            yf_ticker = self._get_yfinance_ticker(ticker)
            ticker_obj = yf.Ticker(yf_ticker)
            df = ticker_obj.history(start=start_date, end=end_date)
            
            if df.empty:
                return ticker, None, f"No data available for {ticker}"
            
            # Optimize data points
            df = self._optimize_data_points(df)
            
            # Calculate percentage change from first value
            if len(df) > 0:
                first_close = df['Close'].iloc[0]
                df['pct_change'] = ((df['Close'] - first_close) / first_close) * 100
            
            # Save to cache
            try:
                with open(cache_path, 'wb') as f:
                    pickle.dump(df, f)
            except Exception as e:
                # Cache write failure is not critical
                pass
            
            return ticker, df, None
            
        except Exception as e:
            return ticker, None, f"Error fetching {ticker}: {str(e)}"
    
    def fetch_data(self, period: str = '7d', tickers: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple tickers in parallel
        Returns: {ticker: dataframe} and errors are logged
        """
        if tickers is None:
            tickers = list(self.tickers_map.keys())
        
        results = {}
        errors = {}
        
        # Fetch in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_ticker = {
                executor.submit(self._fetch_ticker_data, ticker, period): ticker
                for ticker in tickers
            }
            
            for future in as_completed(future_to_ticker):
                ticker, df, error = future.result()
                if error:
                    errors[ticker] = error
                elif df is not None:
                    results[ticker] = df
        
        return results, errors
    
    def get_tickers_by_group(self) -> Dict[str, List[str]]:
        """Get tickers grouped by their category"""
        groups = {}
        for ticker, info in self.tickers_map.items():
            group = info['group']
            if group not in groups:
                groups[group] = []
            groups[group].append(ticker)
        return groups
    
    def get_ticker_info(self, ticker: str) -> Optional[dict]:
        """Get metadata for a ticker"""
        return self.tickers_map.get(ticker)
