"""
Decision Visualization Tool
Visualizes ETF prices with decision signals (RSI, buy/sell markers)
"""
import sys
from pathlib import Path
import yaml
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from etf_data_fetcher import ETFDataFetcher
from bot2.decision_rsi import RSIDecision


def _process_ticker_worker(args_tuple):
    """
    Worker function for parallel processing of a single ticker
    Must be a standalone function (not a method) for ProcessPoolExecutor
    
    Args:
        args_tuple: Tuple of (ticker, data, decision_config_path, viz_settings, decision_name)
                   where data is a pandas DataFrame (will be pickled automatically)
    
    Returns:
        Tuple of (ticker, html_parts, error_message)
    """
    ticker, data, decision_config_path, viz_settings, decision_name = args_tuple
    
    try:
        # Recreate decision module in worker process
        decision = RSIDecision(decision_config_path)
        
        # Extract visualization settings
        show_rsi = viz_settings.get('show_rsi', True)
        show_signals = viz_settings.get('show_signals', True)
        show_rsi_thresholds = viz_settings.get('show_rsi_thresholds', True)
        signal_markers = viz_settings.get('signal_markers', {})
        buy_color = signal_markers.get('buy_color', 'green')
        sell_color = signal_markers.get('sell_color', 'red')
        buy_size = signal_markers.get('buy_size', 10)
        sell_size = signal_markers.get('sell_size', 10)
        oversold_line = viz_settings.get('oversold_line', 30)
        overbought_line = viz_settings.get('overbought_line', 70)
        
        if data is None or data.empty:
            return (ticker, None, "Empty data")
        
        # Calculate RSI
        rsi_series = decision.calculate_rsi_series(data)
        
        # Calculate scores for each date
        scores = []
        for date in data.index:
            score = decision.score(ticker, data, date)
            scores.append(score)
        scores_series = pd.Series(scores, index=data.index)
        
        # Determine subplot layout
        if show_rsi:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.1,
                row_heights=[0.7, 0.3],
                subplot_titles=(f'{ticker} Price & Signals', 'RSI')
            )
        else:
            fig = go.Figure()
        
        # Price chart
        price_trace = go.Scatter(
            x=data.index.tolist(),
            y=data['Close'].tolist(),
            mode='lines',
            name='Close',
            line=dict(color='blue', width=2),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                          'Date: %{x}<br>' +
                          'Price: $%{y:.2f}<br>' +
                          '<extra></extra>'
        )
        
        if show_rsi:
            fig.add_trace(price_trace, row=1, col=1)
        else:
            fig.add_trace(price_trace)
        
        # Add buy/sell signals
        if show_signals:
            buy_dates = []
            buy_prices = []
            sell_dates = []
            sell_prices = []
            
            for date, score in scores_series.items():
                if score > 0:
                    buy_dates.append(date)
                    buy_prices.append(data.loc[date, 'Close'])
                elif score < 0:
                    sell_dates.append(date)
                    sell_prices.append(data.loc[date, 'Close'])
            
            # Buy signals
            if buy_dates:
                buy_trace = go.Scatter(
                    x=buy_dates,
                    y=buy_prices,
                    mode='markers',
                    name='Buy Signal',
                    marker=dict(
                        symbol='triangle-up',
                        size=buy_size,
                        color=buy_color,
                        line=dict(width=1, color='darkgreen')
                    ),
                    hovertemplate='<b>Buy Signal</b><br>' +
                                  'Date: %{x}<br>' +
                                  'Price: $%{y:.2f}<br>' +
                                  '<extra></extra>'
                )
                if show_rsi:
                    fig.add_trace(buy_trace, row=1, col=1)
                else:
                    fig.add_trace(buy_trace)
            
            # Sell signals
            if sell_dates:
                sell_trace = go.Scatter(
                    x=sell_dates,
                    y=sell_prices,
                    mode='markers',
                    name='Sell Signal',
                    marker=dict(
                        symbol='triangle-down',
                        size=sell_size,
                        color=sell_color,
                        line=dict(width=1, color='darkred')
                    ),
                    hovertemplate='<b>Sell Signal</b><br>' +
                                  'Date: %{x}<br>' +
                                  'Price: ${y:.2f}<br>' +
                                  '<extra></extra>'
                )
                if show_rsi:
                    fig.add_trace(sell_trace, row=1, col=1)
                else:
                    fig.add_trace(sell_trace)
        
        # RSI subplot
        if show_rsi and len(rsi_series) > 0:
            rsi_trace = go.Scatter(
                x=rsi_series.index.tolist(),
                y=rsi_series.tolist(),
                mode='lines',
                name='RSI',
                line=dict(color='purple', width=2),
                hovertemplate='<b>RSI</b><br>' +
                              'Date: %{x}<br>' +
                              'RSI: %{y:.2f}<br>' +
                              '<extra></extra>'
            )
            fig.add_trace(rsi_trace, row=2, col=1)
            
            # RSI threshold lines
            if show_rsi_thresholds:
                rsi_dates = rsi_series.index.tolist()
                oversold_trace = go.Scatter(
                    x=rsi_dates,
                    y=[oversold_line] * len(rsi_series),
                    mode='lines',
                    name=f'Oversold ({oversold_line})',
                    line=dict(color='green', width=1, dash='dash'),
                    showlegend=True
                )
                overbought_trace = go.Scatter(
                    x=rsi_dates,
                    y=[overbought_line] * len(rsi_series),
                    mode='lines',
                    name=f'Overbought ({overbought_line})',
                    line=dict(color='red', width=1, dash='dash'),
                    showlegend=True
                )
                fig.add_trace(oversold_trace, row=2, col=1)
                fig.add_trace(overbought_trace, row=2, col=1)
            
            # RSI y-axis range
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
        
        # Update layout
        fig.update_layout(
            title=f'{ticker} - Decision Signals ({decision_name})',
            xaxis_title="Date",
            yaxis_title="Price ($)",
            hovermode='x unified',
            height=800 if show_rsi else 600,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        if show_rsi:
            fig.update_xaxes(title_text="Date", row=2, col=1)
            fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        
        # Generate HTML parts
        html_parts = []
        html_parts.append(f'<div class="ticker-section">')
        html_parts.append(f'<h2>{ticker}</h2>')
        html_parts.append(fig.to_html(include_plotlyjs=False, div_id=f"plot-{ticker}"))
        html_parts.append('</div>')
        
        return (ticker, html_parts, None)
        
    except Exception as e:
        return (ticker, None, str(e))


class DecisionViewer:
    """Visualize decision signals on ETF charts"""
    
    def __init__(self, tool_config_path: str = "bot2/tool_conf.yaml"):
        """
        Initialize decision viewer
        
        Args:
            tool_config_path: Path to tool configuration file
        """
        self.tool_config = self._load_config(tool_config_path)
        self.fetcher = ETFDataFetcher()
        
        # Load decision module
        decision_name = self.tool_config.get('decision', 'rsi_mid')
        # Resolve config path relative to bot2 directory
        bot2_dir = Path(__file__).parent
        decision_config_path = str(bot2_dir / f"decision_{decision_name}.yaml")
        self.decision = RSIDecision(decision_config_path)
        
        # Visualization settings
        self.viz_config = self.tool_config.get('visualization', {})
        self.period = self.viz_config.get('period', '6m')
        self.show_rsi = self.viz_config.get('show_rsi', True)
        self.show_signals = self.viz_config.get('show_signals', True)
        self.show_rsi_thresholds = self.viz_config.get('show_rsi_thresholds', True)
        
        # Signal marker settings
        signal_markers = self.viz_config.get('signal_markers', {})
        self.buy_color = signal_markers.get('buy_color', 'green')
        self.sell_color = signal_markers.get('sell_color', 'red')
        self.buy_size = signal_markers.get('buy_size', 10)
        self.sell_size = signal_markers.get('sell_size', 10)
        
        # RSI thresholds
        self.oversold_line = self.viz_config.get('oversold_line', 30)
        self.overbought_line = self.viz_config.get('overbought_line', 70)
    
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
    
    def _get_signal_color(self, score: float) -> tuple[str, float]:
        """
        Get color and size for signal marker based on score
        
        Returns:
            (color, size)
        """
        abs_score = abs(score)
        if score > 0:
            # Buy signal
            if abs_score >= 0.8:
                return (self.buy_color, self.buy_size * 1.5)
            elif abs_score >= 0.5:
                return (self.buy_color, self.buy_size)
            else:
                return (self.buy_color, self.buy_size * 0.7)
        elif score < 0:
            # Sell signal
            if abs_score >= 0.8:
                return (self.sell_color, self.sell_size * 1.5)
            elif abs_score >= 0.5:
                return (self.sell_color, self.sell_size)
            else:
                return (self.sell_color, self.sell_size * 0.7)
        else:
            return ('gray', 5)
    
    def create_figure(self, ticker: str, data: pd.DataFrame) -> go.Figure:
        """
        Create visualization figure for a single ticker
        
        Args:
            ticker: Ticker symbol
            data: DataFrame with OHLC data
        
        Returns:
            Plotly figure
        """
        # Calculate RSI
        rsi_series = self.decision.calculate_rsi_series(data)
        
        # Calculate scores for each date
        scores = []
        for date in data.index:
            score = self.decision.score(ticker, data, date)
            scores.append(score)
        scores_series = pd.Series(scores, index=data.index)
        
        # Determine subplot layout
        if self.show_rsi:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.1,
                row_heights=[0.7, 0.3],
                subplot_titles=(f'{ticker} Price & Signals', 'RSI')
            )
        else:
            fig = go.Figure()
        
        # Price chart (candlestick or line)
        # Must use .tolist() - Plotly binary encoding corrupts numpy/pandas data
        price_trace = go.Scatter(
            x=data.index.tolist(),
            y=data['Close'].tolist(),
            mode='lines',
            name='Close',
            line=dict(color='blue', width=2),
            hovertemplate='<b>%{fullData.name}</b><br>' +
                          'Date: %{x}<br>' +
                          'Price: $%{y:.2f}<br>' +
                          '<extra></extra>'
        )
        
        if self.show_rsi:
            fig.add_trace(price_trace, row=1, col=1)
        else:
            fig.add_trace(price_trace)
        
        # Add buy/sell signals
        if self.show_signals:
            buy_dates = []
            buy_prices = []
            buy_scores = []
            sell_dates = []
            sell_prices = []
            sell_scores = []
            
            for date, score in scores_series.items():
                if score > 0:
                    buy_dates.append(date)
                    buy_prices.append(data.loc[date, 'Close'])
                    buy_scores.append(score)
                elif score < 0:
                    sell_dates.append(date)
                    sell_prices.append(data.loc[date, 'Close'])
                    sell_scores.append(score)
            
            # Buy signals
            if buy_dates:
                buy_trace = go.Scatter(
                    x=buy_dates,
                    y=buy_prices,
                    mode='markers',
                    name='Buy Signal',
                    marker=dict(
                        symbol='triangle-up',
                        size=self.buy_size,
                        color=self.buy_color,
                        line=dict(width=1, color='darkgreen')
                    ),
                    hovertemplate='<b>Buy Signal</b><br>' +
                                  'Date: %{x}<br>' +
                                  'Price: $%{y:.2f}<br>' +
                                  '<extra></extra>'
                )
                if self.show_rsi:
                    fig.add_trace(buy_trace, row=1, col=1)
                else:
                    fig.add_trace(buy_trace)
            
            # Sell signals
            if sell_dates:
                sell_trace = go.Scatter(
                    x=sell_dates,
                    y=sell_prices,
                    mode='markers',
                    name='Sell Signal',
                    marker=dict(
                        symbol='triangle-down',
                        size=self.sell_size,
                        color=self.sell_color,
                        line=dict(width=1, color='darkred')
                    ),
                    hovertemplate='<b>Sell Signal</b><br>' +
                                  'Date: %{x}<br>' +
                                  'Price: ${y:.2f}<br>' +
                                  '<extra></extra>'
                )
                if self.show_rsi:
                    fig.add_trace(sell_trace, row=1, col=1)
                else:
                    fig.add_trace(sell_trace)
        
        # RSI subplot
        if self.show_rsi and len(rsi_series) > 0:
            rsi_trace = go.Scatter(
                x=rsi_series.index.tolist(),
                y=rsi_series.tolist(),
                mode='lines',
                name='RSI',
                line=dict(color='purple', width=2),
                hovertemplate='<b>RSI</b><br>' +
                              'Date: %{x}<br>' +
                              'RSI: %{y:.2f}<br>' +
                              '<extra></extra>'
            )
            fig.add_trace(rsi_trace, row=2, col=1)
            
            # RSI threshold lines
            if self.show_rsi_thresholds:
                rsi_dates = rsi_series.index.tolist()
                oversold_trace = go.Scatter(
                    x=rsi_dates,
                    y=[self.oversold_line] * len(rsi_series),
                    mode='lines',
                    name=f'Oversold ({self.oversold_line})',
                    line=dict(color='green', width=1, dash='dash'),
                    showlegend=True
                )
                overbought_trace = go.Scatter(
                    x=rsi_dates,
                    y=[self.overbought_line] * len(rsi_series),
                    mode='lines',
                    name=f'Overbought ({self.overbought_line})',
                    line=dict(color='red', width=1, dash='dash'),
                    showlegend=True
                )
                fig.add_trace(oversold_trace, row=2, col=1)
                fig.add_trace(overbought_trace, row=2, col=1)
            
            # RSI y-axis range
            fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
        
        # Update layout
        fig.update_layout(
            title=f'{ticker} - Decision Signals ({self.tool_config.get("decision", "rsi_mid")})',
            xaxis_title="Date",
            yaxis_title="Price ($)",
            hovermode='x unified',
            height=800 if self.show_rsi else 600,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        if self.show_rsi:
            fig.update_xaxes(title_text="Date", row=2, col=1)
            fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        
        return fig
    
    def generate_html_report(self, output_path: str = "result/decision_view.html"):
        """
        Generate HTML report with all tickers
        
        Args:
            output_path: Output file path
        """
        tickers = self._get_tickers_to_display()
        
        print(f"Generating decision visualization for {len(tickers)} tickers...")
        print(f"Period: {self.period}")
        print(f"Decision: {self.tool_config.get('decision', 'rsi_mid')}")
        
        # Fetch data
        data_results, errors = self.fetcher.fetch_data(period=self.period, tickers=tickers)
        
        if errors:
            print(f"Errors fetching data: {len(errors)} tickers")
            for ticker, error in list(errors.items())[:5]:
                print(f"  {ticker}: {error}")
        
        if not data_results:
            print("No data available to visualize")
            return
        
        # Create HTML with multiple figures
        html_parts = []
        html_parts.append(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Decision Signals Visualization</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .ticker-section {{ margin-bottom: 40px; }}
                h2 {{ color: #333; border-bottom: 2px solid #333; padding-bottom: 5px; }}
            </style>
        </head>
        <body>
            <h1>Decision Signals Visualization</h1>
            <p><strong>Decision:</strong> {self.tool_config.get('decision', 'rsi_mid')}</p>
            <p><strong>Period:</strong> {self.period}</p>
            <p><strong>Tickers:</strong> {len(tickers)}</p>
            <hr>
        """)
        
        # Prepare data for parallel processing
        # Convert DataFrames to dicts for pickling
        decision_name = self.tool_config.get('decision', 'rsi_mid')
        bot2_dir = Path(__file__).parent
        decision_config_path = str(bot2_dir / f"decision_{decision_name}.yaml")
        
        # Prepare arguments for worker function
        worker_args = []
        for ticker, data in data_results.items():
            if data is None or data.empty:
                continue
            # Pass DataFrame directly - ProcessPoolExecutor will pickle it automatically
            worker_args.append((
                ticker,
                data,
                decision_config_path,
                self.viz_config,
                decision_name
            ))
        
        # Process tickers in parallel
        ticker_html_map = {}
        max_workers = min(len(worker_args), 8)  # Limit to 8 workers
        
        print(f"Processing {len(worker_args)} tickers in parallel (max {max_workers} workers)...")
        
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(_process_ticker_worker, args): args[0]
                for args in worker_args
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    result_ticker, ticker_parts, error = future.result()
                    if error:
                        print(f"Error processing {result_ticker}: {error}")
                    elif ticker_parts:
                        ticker_html_map[result_ticker] = ticker_parts
                        print(f"Completed {result_ticker}")
                except Exception as e:
                    print(f"Exception processing {ticker}: {e}")
        
        # Sort tickers and add HTML parts in order
        for ticker in sorted(ticker_html_map.keys()):
            html_parts.extend(ticker_html_map[ticker])
        
        html_parts.append("</body></html>")
        
        # Write HTML file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))
        
        print(f"\nReport generated: {output_file.absolute()}")
        print(f"Open in browser to view: file://{output_file.absolute()}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Visualize decision signals on ETF charts')
    parser.add_argument('--config', type=str, default='bot2/tool_conf.yaml',
                       help='Path to tool configuration file')
    parser.add_argument('--output', type=str, default='result/decision_view.html',
                       help='Output HTML file path')
    
    args = parser.parse_args()
    
    viewer = DecisionViewer(args.config)
    viewer.generate_html_report(args.output)


if __name__ == '__main__':
    main()
