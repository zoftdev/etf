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
    
    def _extract_tickers(self) -> Dict[str, dict]:
        """
        Extract all tickers from YAML structure
        Returns: {ticker: {name, group, category, ...}}
        """
        tickers_map = {}
        
        # Commodity ETFs
        if 'commodity' in self.etf_data.get('etfs', {}):
            commodity = self.etf_data['etfs']['commodity']
            
            # Specific commodities
            if 'specific' in commodity:
                for item in commodity['specific']:
                    ticker = item.get('ticker')
                    if ticker:
                        tickers_map[ticker] = {
                            'name': item.get('name', ticker),
                            'group': 'Commodity',
                            'category': item.get('category', ''),
                            'description': item.get('description', '')
                        }
            
            # Broad commodities
            if 'broad' in commodity:
                for item in commodity['broad']:
                    ticker = item.get('ticker')
                    if ticker:
                        tickers_map[ticker] = {
                            'name': item.get('name', ticker),
                            'group': 'Commodity',
                            'category': 'Broad',
                            'description': item.get('description', '')
                        }
        
        # Momentum ETFs
        if 'momentum' in self.etf_data.get('etfs', {}):
            for item in self.etf_data['etfs']['momentum']:
                ticker = item.get('ticker')
                if ticker:
                    tickers_map[ticker] = {
                        'name': item.get('name', ticker),
                        'group': 'Momentum',
                        'category': '',
                        'description': item.get('description', '')
                    }
        
        # World ETFs
        if 'world' in self.etf_data.get('etfs', {}):
            world = self.etf_data['etfs']['world']
            
            # Asia Pacific
            if 'asia_pacific' in world:
                for item in world['asia_pacific'].get('etfs', []):
                    tickers = item.get('tickers', [])
                    for ticker in tickers:
                        tickers_map[ticker] = {
                            'name': item.get('name', ticker),
                            'group': 'World - Asia Pacific',
                            'category': item.get('country', ''),
                            'description': item.get('description', '')
                        }
            
            # Europe
            if 'europe' in world:
                for item in world['europe'].get('etfs', []):
                    tickers = item.get('tickers', [])
                    for ticker in tickers:
                        tickers_map[ticker] = {
                            'name': item.get('name', ticker),
                            'group': 'World - Europe',
                            'category': item.get('country', ''),
                            'description': item.get('description', '')
                        }
            
            # Americas
            if 'americas' in world:
                for item in world['americas'].get('etfs', []):
                    tickers = item.get('tickers', [])
                    for ticker in tickers:
                        tickers_map[ticker] = {
                            'name': item.get('name', ticker),
                            'group': 'World - Americas',
                            'category': item.get('country', ''),
                            'description': item.get('description', '')
                        }
            
            # Middle East & Africa
            if 'middle_east_africa' in world:
                for item in world['middle_east_africa'].get('etfs', []):
                    tickers = item.get('tickers', [])
                    for ticker in tickers:
                        tickers_map[ticker] = {
                            'name': item.get('name', ticker),
                            'group': 'World - Middle East & Africa',
                            'category': item.get('country', ''),
                            'description': item.get('description', '')
                        }
            
            # Broad Market
            if 'broad_market' in world:
                for item in world['broad_market'].get('etfs', []):
                    tickers = item.get('tickers', [])
                    for ticker in tickers:
                        tickers_map[ticker] = {
                            'name': item.get('name', ticker),
                            'group': 'World - Broad Market',
                            'category': item.get('region', ''),
                            'description': item.get('description', '')
                        }
        
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
            
            ticker_obj = yf.Ticker(ticker)
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
