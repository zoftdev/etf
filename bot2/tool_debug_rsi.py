"""
RSI Debug Tool
Text-based output to verify buy/sell signals are in correct RSI zones
"""
import sys
from pathlib import Path
import yaml
import pandas as pd
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.etf_data_fetcher import ETFDataFetcher
from bot2.decision_rsi import RSIDecision


class RSIDebugger:
    """Debug RSI decision signals and verify they're in correct zones"""
    
    def __init__(self, tool_config_path: str = "bot2/tool_conf.yaml"):
        """
        Initialize RSI debugger
        
        Args:
            tool_config_path: Path to tool configuration file
        """
        self.tool_config = self._load_config(tool_config_path)
        self.fetcher = ETFDataFetcher()
        
        # Load decision module (RSI mid)
        decision_name = self.tool_config.get('decision', 'rsi_mid')
        bot2_dir = Path(__file__).parent
        decision_config_path = str(bot2_dir / f"decision_{decision_name}.yaml")
        self.decision = RSIDecision(decision_config_path)
        
        # Get thresholds from decision config
        self.oversold_threshold = self.decision.oversold_threshold
        self.overbought_threshold = self.decision.overbought_threshold
        self.strong_oversold = self.decision.strong_oversold
        self.strong_overbought = self.decision.strong_overbought
        
        # Visualization settings
        self.viz_config = self.tool_config.get('visualization', {})
        self.period = self.viz_config.get('period', '6m')
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _get_tickers_to_display(self) -> list:
        """Get list of tickers to display based on config"""
        tickers_config = self.viz_config.get('tickers', [])
        groups_config = self.viz_config.get('groups', [])
        
        if tickers_config:
            return tickers_config
        
        if groups_config:
            # Get tickers from specified groups
            all_groups = self.fetcher.get_tickers_by_group()
            tickers = []
            for group in groups_config:
                if group in all_groups:
                    tickers.extend(all_groups[group])
            return tickers if tickers else list(self.fetcher.tickers_map.keys())
        
        # Default: all tickers
        return list(self.fetcher.tickers_map.keys())
    
    def _get_signal_type(self, score: float) -> str:
        """Get signal type description"""
        abs_score = abs(score)
        if score > 0:
            if abs_score >= 0.8:
                return "STRONG BUY"
            elif abs_score >= 0.5:
                return "BUY"
            else:
                return "WEAK BUY"
        elif score < 0:
            if abs_score >= 0.8:
                return "STRONG SELL"
            elif abs_score >= 0.5:
                return "SELL"
            else:
                return "WEAK SELL"
        else:
            return "NEUTRAL"
    
    def _verify_signal(self, rsi: float, score: float) -> tuple[bool, str]:
        """
        Verify that signal is in correct RSI zone
        
        Returns:
            (is_valid, message)
        """
        signal_type = self._get_signal_type(score)
        
        if score > 0:  # Buy signal
            # Buy signals should occur when RSI is low (oversold)
            if rsi < self.oversold_threshold:
                return True, "✓ Valid (RSI in oversold zone)"
            elif rsi < 50:
                return True, "✓ Valid (RSI below 50, momentum building)"
            else:
                return False, f"✗ INVALID (RSI={rsi:.2f} >= {self.oversold_threshold}, should be oversold for buy)"
        
        elif score < 0:  # Sell signal
            # Sell signals should occur when RSI is high (overbought)
            if rsi > self.overbought_threshold:
                return True, "✓ Valid (RSI in overbought zone)"
            elif rsi > 50:
                return True, "✓ Valid (RSI above 50, momentum weakening)"
            else:
                return False, f"✗ INVALID (RSI={rsi:.2f} <= {self.overbought_threshold}, should be overbought for sell)"
        
        else:  # Neutral
            return True, "✓ Neutral (no signal)"
    
    def debug_ticker(self, ticker: str) -> dict:
        """
        Debug a single ticker
        
        Returns:
            Dictionary with debug results
        """
        print(f"\n{'='*80}")
        print(f"DEBUGGING: {ticker}")
        print(f"{'='*80}")
        
        # Fetch data
        print(f"Fetching {self.period} data...")
        data_dict, _ = self.fetcher.fetch_data(self.period, [ticker])
        
        if ticker not in data_dict:
            print(f"ERROR: No data found for {ticker}")
            return {'ticker': ticker, 'error': 'No data'}
        
        data = data_dict[ticker]
        print(f"Data points: {len(data)}")
        print(f"Date range: {data.index[0]} to {data.index[-1]}")
        
        # Calculate RSI series
        rsi_series = self.decision.calculate_rsi_series(data)
        
        # Calculate scores for each date
        print(f"\nRSI Parameters:")
        print(f"  Period: {self.decision.rsi_period}")
        print(f"  Oversold threshold: {self.oversold_threshold}")
        print(f"  Overbought threshold: {self.overbought_threshold}")
        print(f"  Strong oversold: {self.strong_oversold}")
        print(f"  Strong overbought: {self.strong_overbought}")
        
        # Find signals
        signals = []
        violations = []
        
        print(f"\n{'Date':<12} {'Price':<10} {'RSI':<8} {'Score':<8} {'Signal':<15} {'Verification':<50}")
        print(f"{'-'*80}")
        
        for date in data.index:
            # Get RSI value for this date
            if date in rsi_series.index:
                rsi_value = rsi_series.loc[date]
            else:
                continue  # Skip if no RSI value
            
            # Calculate score
            score = self.decision.score(ticker, data, date)
            
            # Skip neutral signals
            if abs(score) < 0.01:
                continue
            
            # Verify signal
            is_valid, verification_msg = self._verify_signal(rsi_value, score)
            signal_type = self._get_signal_type(score)
            
            # Format date
            date_str = date.strftime('%Y-%m-%d') if isinstance(date, pd.Timestamp) else str(date)
            
            # Print signal
            print(f"{date_str:<12} ${data.loc[date, 'Close']:<9.2f} {rsi_value:<8.2f} {score:<8.2f} {signal_type:<15} {verification_msg}")
            
            signals.append({
                'date': date,
                'price': data.loc[date, 'Close'],
                'rsi': rsi_value,
                'score': score,
                'signal_type': signal_type,
                'is_valid': is_valid,
                'verification': verification_msg
            })
            
            if not is_valid:
                violations.append({
                    'date': date,
                    'price': data.loc[date, 'Close'],
                    'rsi': rsi_value,
                    'score': score,
                    'signal_type': signal_type,
                    'verification': verification_msg
                })
        
        # Summary
        print(f"\n{'='*80}")
        print(f"SUMMARY for {ticker}:")
        print(f"  Total signals: {len(signals)}")
        buy_signals = [s for s in signals if s['score'] > 0]
        sell_signals = [s for s in signals if s['score'] < 0]
        print(f"  Buy signals: {len(buy_signals)}")
        print(f"  Sell signals: {len(sell_signals)}")
        print(f"  Valid signals: {sum(1 for s in signals if s['is_valid'])}")
        print(f"  Invalid signals (violations): {len(violations)}")
        
        if violations:
            print(f"\n⚠️  VIOLATIONS FOUND:")
            for v in violations:
                date_str = v['date'].strftime('%Y-%m-%d') if isinstance(v['date'], pd.Timestamp) else str(v['date'])
                print(f"  {date_str}: {v['signal_type']} (RSI={v['rsi']:.2f}, Score={v['score']:.2f}) - {v['verification']}")
        else:
            print(f"\n✓ All signals are in correct RSI zones!")
        
        return {
            'ticker': ticker,
            'total_signals': len(signals),
            'buy_signals': len(buy_signals),
            'sell_signals': len(sell_signals),
            'valid_signals': sum(1 for s in signals if s['is_valid']),
            'violations': len(violations),
            'violation_details': violations
        }
    
    def run(self):
        """Run debugger for all configured tickers"""
        tickers = self._get_tickers_to_display()
        
        print(f"RSI Debug Tool")
        print(f"Decision module: {self.tool_config.get('decision', 'rsi_mid')}")
        print(f"Period: {self.period}")
        print(f"Tickers to debug: {', '.join(tickers)}")
        
        results = []
        for ticker in tickers:
            result = self.debug_ticker(ticker)
            results.append(result)
        
        # Overall summary
        print(f"\n{'='*80}")
        print(f"OVERALL SUMMARY")
        print(f"{'='*80}")
        total_signals = sum(r.get('total_signals', 0) for r in results)
        total_violations = sum(r.get('violations', 0) for r in results)
        print(f"Total signals across all tickers: {total_signals}")
        print(f"Total violations: {total_violations}")
        
        if total_violations == 0:
            print(f"\n✓ All signals verified! No violations found.")
        else:
            print(f"\n⚠️  Found {total_violations} violations. Review the details above.")


def main():
    """Main entry point"""
    debugger = RSIDebugger()
    debugger.run()


if __name__ == "__main__":
    main()
