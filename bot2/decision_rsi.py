"""
RSI Decision Module
Generates buy/sell signals based on Relative Strength Index (RSI)
"""
import yaml
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime


class RSIDecision:
    """RSI-based decision module for generating trading signals"""
    
    def __init__(self, config_path: str):
        """
        Initialize RSI Decision module
        
        Args:
            config_path: Path to YAML config file (e.g., decision_rsi_low.yaml)
        """
        self.config = self._load_config(config_path)
        self.rsi_period = self.config.get('rsi_period', 14)
        self.oversold_threshold = self.config.get('oversold_threshold', 30)
        self.overbought_threshold = self.config.get('overbought_threshold', 70)
        self.strong_oversold = self.config.get('strong_oversold', 20)
        self.strong_overbought = self.config.get('strong_overbought', 80)
        self.divergence_lookback = self.config.get('divergence_lookback', 20)
        self.min_score_threshold = self.config.get('min_score_threshold', 0.1)
        self.enable_divergence = self.config.get('enable_divergence', True)
        self.enable_momentum_shift = self.config.get('enable_momentum_shift', True)
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI)
        
        Args:
            prices: Series of closing prices
            period: RSI period (default: 14)
        
        Returns:
            Series of RSI values
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _detect_divergence(self, prices: pd.Series, rsi: pd.Series, 
                          lookback: int, current_idx: int) -> Tuple[bool, bool]:
        """
        Detect bullish and bearish divergences
        
        Returns:
            (bullish_divergence, bearish_divergence)
        """
        if not self.enable_divergence or current_idx < lookback:
            return False, False
        
        # Get recent price and RSI data
        price_window = prices.iloc[max(0, current_idx - lookback):current_idx + 1]
        rsi_window = rsi.iloc[max(0, current_idx - lookback):current_idx + 1]
        
        if len(price_window) < 5 or len(rsi_window) < 5:
            return False, False
        
        # Find recent lows and highs
        price_lows = price_window.nsmallest(2)
        price_highs = price_window.nlargest(2)
        
        if len(price_lows) < 2 or len(price_highs) < 2:
            return False, False
        
        # Bullish divergence: price makes lower low, RSI makes higher low
        if price_lows.iloc[-1] < price_lows.iloc[0]:
            rsi_at_lows = rsi_window.loc[price_lows.index]
            if len(rsi_at_lows) >= 2:
                if rsi_at_lows.iloc[-1] > rsi_at_lows.iloc[0]:
                    return True, False
        
        # Bearish divergence: price makes higher high, RSI makes lower high
        if price_highs.iloc[-1] > price_highs.iloc[0]:
            rsi_at_highs = rsi_window.loc[price_highs.index]
            if len(rsi_at_highs) >= 2:
                if rsi_at_highs.iloc[-1] < rsi_at_highs.iloc[0]:
                    return False, True
        
        return False, False
    
    def _detect_momentum_shift(self, rsi: pd.Series, current_idx: int) -> Tuple[bool, bool]:
        """
        Detect momentum shifts (RSI crossing 50)
        
        Returns:
            (bullish_shift, bearish_shift)
        """
        if not self.enable_momentum_shift or current_idx < 1:
            return False, False
        
        current_rsi = rsi.iloc[current_idx]
        prev_rsi = rsi.iloc[current_idx - 1]
        
        # Bullish shift: RSI crosses above 50
        if prev_rsi < 50 and current_rsi >= 50:
            return True, False
        
        # Bearish shift: RSI crosses below 50
        if prev_rsi > 50 and current_rsi <= 50:
            return False, True
        
        return False, False
    
    def score(self, ticker: str, data: pd.DataFrame, as_of_date: Optional[pd.Timestamp] = None) -> float:
        """
        Generate trading score based on RSI
        
        Args:
            ticker: Ticker symbol
            data: DataFrame with OHLC data (must have 'Close' column)
            as_of_date: Date to evaluate as of (only use data <= this date)
        
        Returns:
            Score from -1.0 (strong sell) to 1.0 (strong buy)
        """
        # Filter data to as_of_date (no look-ahead)
        if as_of_date is not None:
            data = data[data.index <= as_of_date].copy()
        
        if len(data) < self.rsi_period + 1:
            return 0.0
        
        # Ensure we have Close column
        if 'Close' not in data.columns:
            return 0.0
        
        prices = data['Close']
        current_idx = len(data) - 1
        
        # Calculate RSI
        rsi = self._calculate_rsi(prices, self.rsi_period)
        current_rsi = rsi.iloc[current_idx]
        
        # Handle NaN values
        if pd.isna(current_rsi):
            return 0.0
        
        # Detect divergences
        bullish_div, bearish_div = self._detect_divergence(prices, rsi, self.divergence_lookback, current_idx)
        
        # Detect momentum shifts
        bullish_shift, bearish_shift = self._detect_momentum_shift(rsi, current_idx)
        
        # Check for RSI crossovers
        prev_rsi = rsi.iloc[current_idx - 1] if current_idx > 0 else current_rsi
        rsi_crossed_above_oversold = prev_rsi < self.oversold_threshold and current_rsi >= self.oversold_threshold
        rsi_crossed_below_overbought = prev_rsi > self.overbought_threshold and current_rsi <= self.overbought_threshold
        
        # Generate score based on rules
        score = 0.0
        
        # Strong Buy signals (0.8-1.0)
        if current_rsi < self.strong_oversold or bullish_div:
            score = 0.9
        # Buy signals (0.5-0.8)
        elif current_rsi < self.oversold_threshold or rsi_crossed_above_oversold:
            score = 0.65
        # Weak Buy signals (0.2-0.5)
        elif bullish_shift:
            score = 0.35
        # Strong Sell signals (-0.8 to -1.0)
        elif current_rsi > self.strong_overbought or bearish_div:
            score = -0.9
        # Sell signals (-0.5 to -0.8)
        elif current_rsi > self.overbought_threshold or rsi_crossed_below_overbought:
            score = -0.65
        # Weak Sell signals (-0.2 to -0.5)
        elif bearish_shift:
            score = -0.35
        # Neutral (0.0)
        else:
            score = 0.0
        
        # Apply minimum score threshold
        if abs(score) < self.min_score_threshold:
            return 0.0
        
        # Clamp to [-1.0, 1.0]
        return max(-1.0, min(1.0, score))
    
    def calculate_rsi_series(self, data: pd.DataFrame, as_of_date: Optional[pd.Timestamp] = None) -> pd.Series:
        """
        Calculate RSI series for visualization
        
        Args:
            data: DataFrame with OHLC data
            as_of_date: Date to evaluate as of
        
        Returns:
            Series of RSI values
        """
        if as_of_date is not None:
            data = data[data.index <= as_of_date].copy()
        
        if 'Close' not in data.columns or len(data) < self.rsi_period + 1:
            return pd.Series(dtype=float)
        
        prices = data['Close']
        return self._calculate_rsi(prices, self.rsi_period)
