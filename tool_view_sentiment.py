#!/usr/bin/env python3
"""
Sentiment Prediction Visualization Tool
Visualizes ETF prices/returns with sentiment prediction scores to evaluate
if sentiment can predict future performance.

Usage:
    # Analyze all ETFs with sentiment data
    python tool_view_sentiment.py
    
    # Analyze specific ETFs
    python tool_view_sentiment.py --tickers GLD EWG XLK
    
    # Custom output path and years
    python tool_view_sentiment.py --output result/my_sentiment.html --years 15

The tool generates an interactive HTML report showing:
- Price charts with sentiment markers
- Scatter plots of sentiment vs actual returns
- Correlation analysis (correlation coefficient, R²)
- Summary statistics for all ETFs
"""
import sys
from pathlib import Path
import yaml
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np
from typing import Dict, List, Optional, Tuple

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from etf_data_fetcher import ETFDataFetcher


class SentimentViewer:
    """Visualize sentiment predictions vs actual ETF performance"""
    
    def __init__(self, sentiment_score_path: str = "etf_sentiment_score.yaml",
                 sentiment_data_dir: str = "sentiment_data"):
        """
        Initialize sentiment viewer
        
        Args:
            sentiment_score_path: Path to sentiment scores YAML file
            sentiment_data_dir: Directory containing sentiment data YAML files
        """
        self.fetcher = ETFDataFetcher()
        self.sentiment_scores = self._load_sentiment_scores(sentiment_score_path)
        self.sentiment_data_dir = Path(sentiment_data_dir)
        self.sentiment_texts = self._load_sentiment_texts()
        
    def _load_sentiment_scores(self, path: str) -> Dict[str, List[Dict]]:
        """Load sentiment scores from YAML file"""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # Convert to dict keyed by ticker
        scores_dict = {}
        for etf_data in data.get('etf_sentiment_scores', []):
            ticker = etf_data['etf']
            scores_dict[ticker] = etf_data['scores']
        
        return scores_dict
    
    def _load_sentiment_texts(self) -> Dict[str, Dict[Tuple[int, int], str]]:
        """
        Load sentiment text from sentiment_data YAML files
        Returns: {ticker: {(year, forecast_year): sentiment_text}}
        """
        sentiment_texts = {}
        sentiment_files = sorted(self.sentiment_data_dir.glob('etf_sentiment_*.yaml'))
        
        for file_path in sentiment_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                for etf_data in data.get('sentiment_data', []):
                    ticker = etf_data['etf']
                    ticker_texts = {}
                    
                    for forecast in etf_data.get('forecasts', []):
                        year = forecast['year']
                        forecast_year = forecast['forecast_year']
                        sentiment_text = forecast.get('sentiment', '').strip()
                        
                        if sentiment_text:
                            ticker_texts[(year, forecast_year)] = sentiment_text
                    
                    if ticker_texts:
                        sentiment_texts[ticker] = ticker_texts
            except Exception as e:
                print(f"Warning: Could not load sentiment text from {file_path}: {e}")
                continue
        
        return sentiment_texts
    
    def _get_sentiment_text(self, ticker: str, year: int, forecast_year: int) -> Optional[str]:
        """Get sentiment text for a specific ticker, year, and forecast_year"""
        if ticker in self.sentiment_texts:
            return self.sentiment_texts[ticker].get((year, forecast_year))
        return None
    
    def _get_forecast_year_returns(self, ticker: str, price_data: pd.DataFrame, 
                                   forecast_year: int) -> Optional[float]:
        """
        Calculate return using actual price (Nov year-1) to 180d SMA (Sep forecast_year)
        
        Args:
            ticker: ETF ticker
            price_data: DataFrame with price data
            forecast_year: Year being forecasted
        
        Returns:
            Percentage change from Nov (year-1) actual price to Sep (forecast_year) 180d SMA, or None
        """
        if price_data.empty or 'Close' not in price_data.columns:
            return None
        
        # Normalize timezone - convert index to timezone-naive if needed
        price_data = price_data.copy()
        if price_data.index.tz is not None:
            price_data.index = price_data.index.tz_localize(None)
        
        # Calculate 180-day SMA
        sma_180 = price_data['Close'].rolling(window=180, min_periods=1).mean()
        
        # Get November of the year before forecast_year
        prev_year = forecast_year - 1
        nov_start = pd.Timestamp(f'{prev_year}-11-01')
        nov_end = pd.Timestamp(f'{prev_year}-11-30')
        
        # Get September of forecast_year
        sep_start = pd.Timestamp(f'{forecast_year}-09-01')
        sep_end = pd.Timestamp(f'{forecast_year}-09-30')
        
        # Find data points in November (prev_year) - use actual price
        nov_data = price_data[(price_data.index >= nov_start) & (price_data.index <= nov_end)]
        if nov_data.empty:
            return None
        
        # Find data points in September (forecast_year) - use 180d SMA
        sep_data = price_data[(price_data.index >= sep_start) & (price_data.index <= sep_end)]
        if sep_data.empty:
            return None
        
        # Get actual price at the last trading day of November
        nov_date = nov_data.index[-1]
        nov_price = price_data.loc[nov_date, 'Close']
        
        # Get 180d SMA at the last trading day of September
        sep_date = sep_data.index[-1]
        sep_sma = sma_180.loc[sep_date]
        
        if pd.isna(nov_price) or pd.isna(sep_sma) or nov_price == 0:
            return None
        
        # Calculate percentage change
        return ((sep_sma - nov_price) / nov_price) * 100
    
    def _align_sentiment_with_returns(self, ticker: str, price_data: pd.DataFrame) -> pd.DataFrame:
        """
        Align sentiment scores with SMA-based returns (Nov year-1 to Sep forecast_year)
        
        Returns:
            DataFrame with columns: year, forecast_year, sentiment_score, actual_return
        """
        if ticker not in self.sentiment_scores:
            return pd.DataFrame()
        
        scores = self.sentiment_scores[ticker]
        aligned_data = []
        
        for score_entry in scores:
            year = score_entry['year']
            forecast_year = score_entry['forecast_year']
            sentiment_score = score_entry['score']
            
            # Get actual return for the forecast year
            actual_return = self._get_forecast_year_returns(ticker, price_data, forecast_year)
            
            if actual_return is not None:
                aligned_data.append({
                    'year': year,
                    'forecast_year': forecast_year,
                    'sentiment_score': sentiment_score,
                    'actual_return': actual_return,
                    'sentiment_label': score_entry.get('sentiment_label', 'neutral')
                })
        
        if not aligned_data:
            return pd.DataFrame()
        
        return pd.DataFrame(aligned_data)
    
    def _calculate_correlation(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate correlation metrics between sentiment and returns"""
        if df.empty or len(df) < 2:
            return {
                'correlation': 0.0,
                'r_squared': 0.0,
                'mean_sentiment': 0.0,
                'mean_return': 0.0,
                'sentiment_std': 0.0,
                'return_std': 0.0
            }
        
        sentiment = df['sentiment_score'].values
        returns = df['actual_return'].values
        
        # Calculate correlation
        if len(sentiment) > 1 and np.std(sentiment) > 0 and np.std(returns) > 0:
            correlation = np.corrcoef(sentiment, returns)[0, 1]
            r_squared = correlation ** 2
        else:
            correlation = 0.0
            r_squared = 0.0
        
        return {
            'correlation': correlation,
            'r_squared': r_squared,
            'mean_sentiment': float(np.mean(sentiment)),
            'mean_return': float(np.mean(returns)),
            'sentiment_std': float(np.std(sentiment)),
            'return_std': float(np.std(returns)),
            'n_samples': len(df)
        }
    
    def create_figure(self, ticker: str, price_data: pd.DataFrame, 
                      show_correlation: bool = True, max_return: Optional[float] = None) -> go.Figure:
        """
        Create visualization figure for a single ticker
        
        Args:
            ticker: Ticker symbol
            price_data: DataFrame with OHLC data
            show_correlation: Whether to show correlation analysis
        
        Returns:
            Plotly figure
        """
        # Align sentiment with returns
        aligned_df = self._align_sentiment_with_returns(ticker, price_data)
        
        if aligned_df.empty:
            # No aligned data - just show price
            # Normalize timezone
            price_data_display = price_data.copy()
            if price_data_display.index.tz is not None:
                price_data_display.index = price_data_display.index.tz_localize(None)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=price_data_display.index.tolist(),
                y=price_data_display['Close'].tolist(),
                mode='lines',
                name='Price',
                line=dict(color='blue', width=2)
            ))
            fig.update_layout(
                title=f'{ticker} - No Sentiment Data Available',
                xaxis_title="Date",
                yaxis_title="Price ($)",
                height=600
            )
            return fig
        
        # Calculate correlation metrics
        correlation_metrics = self._calculate_correlation(aligned_df)
        
        # Create subplots: price chart, sentiment vs returns scatter, and correlation info
        if show_correlation:
            fig = make_subplots(
                rows=3, cols=1,
                shared_xaxes=False,
                vertical_spacing=0.1,
                row_heights=[0.4, 0.4, 0.2],
                subplot_titles=(
                    f'{ticker} Price Over Time',
                    'Sentiment Score vs Actual Return',
                    'Correlation Analysis'
                ),
                specs=[[{"type": "scatter"}],
                       [{"type": "scatter"}],
                       [{"type": "table"}]]
            )
        else:
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=False,
                vertical_spacing=0.15,
                row_heights=[0.6, 0.4],
                subplot_titles=(
                    f'{ticker} Price Over Time',
                    'Sentiment Score vs Actual Return'
                )
            )
        
        # 1. Price chart with sentiment markers
        # Get price data for years with sentiment
        forecast_years = aligned_df['forecast_year'].unique()
        
        # Normalize timezone for price data display
        price_data_display = price_data.copy()
        if price_data_display.index.tz is not None:
            price_data_display.index = price_data_display.index.tz_localize(None)
        
        # Calculate 180-day SMA
        sma_180 = price_data_display['Close'].rolling(window=180, min_periods=1).mean()
        
        # Price trace
        price_trace = go.Scatter(
            x=price_data_display.index.tolist(),
            y=price_data_display['Close'].tolist(),
            mode='lines',
            name='Price',
            line=dict(color='blue', width=2),
            hovertemplate='<b>Price</b><br>' +
                          'Date: %{x}<br>' +
                          'Price: $%{y:.2f}<br>' +
                          '<extra></extra>'
        )
        fig.add_trace(price_trace, row=1, col=1)
        
        # 180-day SMA trace
        sma_trace = go.Scatter(
            x=price_data_display.index.tolist(),
            y=sma_180.tolist(),
            mode='lines',
            name='180d SMA',
            line=dict(color='orange', width=2, dash='dash'),
            hovertemplate='<b>180d SMA</b><br>' +
                          'Date: %{x}<br>' +
                          'SMA: $%{y:.2f}<br>' +
                          '<extra></extra>'
        )
        fig.add_trace(sma_trace, row=1, col=1)
        
        # Normalize timezone for price data
        price_data_normalized = price_data.copy()
        if price_data_normalized.index.tz is not None:
            price_data_normalized.index = price_data_normalized.index.tz_localize(None)
        
        # Add year lines (vertical lines at start of each forecast year)
        forecast_years = sorted(aligned_df['forecast_year'].unique())
        price_min = price_data_normalized['Close'].min()
        price_max = price_data_normalized['Close'].max()
        price_range = price_max - price_min
        
        for forecast_year in forecast_years:
            year_start = pd.Timestamp(f'{forecast_year}-01-01')
            year_data = price_data_normalized[price_data_normalized.index >= year_start]
            if not year_data.empty:
                marker_date = year_data.index[0]
                
                # Add vertical line
                fig.add_trace(go.Scatter(
                    x=[marker_date, marker_date],
                    y=[price_min, price_max],
                    mode='lines',
                    name=f'{forecast_year}',
                    line=dict(color='lightgray', width=1, dash='dot'),
                    hovertemplate=f'<b>{forecast_year}</b><br>' +
                                  'Forecast Year Start<extra></extra>',
                    showlegend=False
                ), row=1, col=1)
                
                # Add year label at top of line
                fig.add_annotation(
                    x=marker_date,
                    y=price_max - price_range * 0.02,  # Slightly below top
                    text=str(forecast_year),
                    showarrow=False,
                    font=dict(size=10, color='gray'),
                    bgcolor='white',
                    bordercolor='gray',
                    borderwidth=1,
                    borderpad=2,
                    xref='x',
                    yref='y',
                    row=1,
                    col=1
                )
        
        # Add sentiment markers on price chart (at year start)
        for _, row in aligned_df.iterrows():
            year = row['year']
            forecast_year = row['forecast_year']
            sentiment_score = row['sentiment_score']
            actual_return = row['actual_return']
            
            # Get sentiment text
            sentiment_text = self._get_sentiment_text(ticker, year, forecast_year)
            
            # Find first trading day of forecast year
            year_start = pd.Timestamp(f'{forecast_year}-01-01')
            year_data = price_data_normalized[price_data_normalized.index >= year_start]
            if not year_data.empty:
                marker_date = year_data.index[0]
                marker_price = year_data['Close'].iloc[0]
                
                # Color based on sentiment
                if sentiment_score >= 0.3:
                    color = 'green'
                    symbol = 'triangle-up'
                elif sentiment_score <= -0.3:
                    color = 'red'
                    symbol = 'triangle-down'
                else:
                    color = 'gray'
                    symbol = 'circle'
                
                # Build hover template without sentiment text (will show in custom tooltip)
                hovertemplate = (
                    f'<b>Sentiment {forecast_year}</b><br>' +
                    f'Forecast Year: {year} → {forecast_year}<br>' +
                    f'Sentiment Score: {sentiment_score:.3f}<br>' +
                    f'SMA Return (Nov {forecast_year-1} to Sep {forecast_year}): {actual_return:.2f}%<br>' +
                    f'<i>Hold "s" key for sentiment text</i><extra></extra>'
                )
                
                # Store sentiment text in customdata for JavaScript access
                # Format: [sentiment_text, forecast_year]
                sentiment_data = sentiment_text if sentiment_text else ''
                
                fig.add_trace(go.Scatter(
                    x=[marker_date],
                    y=[marker_price],
                    mode='markers',
                    name=f'Sentiment {forecast_year}',
                    marker=dict(
                        symbol=symbol,
                        size=abs(sentiment_score) * 20 + 8,
                        color=color,
                        line=dict(width=2, color='black'),
                        opacity=0.7
                    ),
                    customdata=[[sentiment_data, forecast_year]],
                    hovertemplate=hovertemplate,
                    showlegend=False
                ), row=1, col=1)
        
        # 2. Sentiment vs Returns scatter plot
        # Build custom hover data with sentiment text (stored but not shown in default hover)
        customdata_list = []
        for _, row in aligned_df.iterrows():
            year = row['year']
            forecast_year = row['forecast_year']
            sentiment_text = self._get_sentiment_text(ticker, year, forecast_year)
            sentiment_data = sentiment_text if sentiment_text else ''
            customdata_list.append([year, forecast_year, sentiment_data])
        
        scatter_trace = go.Scatter(
            x=aligned_df['sentiment_score'].tolist(),
            y=aligned_df['actual_return'].tolist(),
            mode='markers+text',
            name='Forecast',
            text=aligned_df['forecast_year'].astype(str).tolist(),
            textposition='top center',
            customdata=customdata_list,
            marker=dict(
                size=10,
                color=aligned_df['sentiment_score'],
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="Sentiment Score", x=1.02),
                line=dict(width=1, color='black'),
                cmin=-1,
                cmax=1
            ),
            hovertemplate='<b>Year %{customdata[1]}</b><br>' +
                          'Forecast: %{customdata[0]} → %{customdata[1]}<br>' +
                          'Sentiment Score: %{x:.3f}<br>' +
                          'SMA Return (Nov %{customdata[0]} to Sep %{customdata[1]}): %{y:.2f}%<br>' +
                          '<i>Hold "s" key for sentiment text</i><extra></extra>'
        )
        fig.add_trace(scatter_trace, row=2, col=1)
        
        # Add trend line
        if len(aligned_df) > 1:
            z = np.polyfit(aligned_df['sentiment_score'], aligned_df['actual_return'], 1)
            p = np.poly1d(z)
            x_trend = np.linspace(aligned_df['sentiment_score'].min(), 
                                 aligned_df['sentiment_score'].max(), 100)
            y_trend = p(x_trend)
            
            trend_trace = go.Scatter(
                x=x_trend.tolist(),
                y=y_trend.tolist(),
                mode='lines',
                name='Trend Line',
                line=dict(color='red', width=2, dash='dash'),
                hovertemplate='Trend Line<extra></extra>'
            )
            fig.add_trace(trend_trace, row=2, col=1)
        
        # Add zero lines
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
        fig.add_vline(x=0, line_dash="dash", line_color="gray", row=2, col=1)
        
        # 3. Correlation table
        if show_correlation:
            correlation_data = [
                ['Metric', 'Value'],
                ['Correlation', f"{correlation_metrics['correlation']:.3f}"],
                ['R²', f"{correlation_metrics['r_squared']:.3f}"],
                ['Mean Sentiment', f"{correlation_metrics['mean_sentiment']:.3f}"],
                ['Mean Return (%)', f"{correlation_metrics['mean_return']:.2f}"],
                ['Samples', f"{correlation_metrics['n_samples']}"]
            ]
            
            table_trace = go.Table(
                header=dict(
                    values=['Metric', 'Value'],
                    fill_color='paleturquoise',
                    align='left',
                    font=dict(size=12, color='black')
                ),
                cells=dict(
                    values=list(zip(*correlation_data[1:])),
                    fill_color='white',
                    align='left',
                    font=dict(size=11)
                )
            )
            fig.add_trace(table_trace, row=3, col=1)
        
        # Update layout
        fig.update_layout(
            title=f'{ticker} - Sentiment Prediction Analysis',
            height=1200 if show_correlation else 800,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        # Update axes
        fig.update_xaxes(title_text="Date", row=1, col=1)
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        
        # Set consistent axis ranges for scatter plot
        # X-axis: always -1 to 1 (sentiment score)
        # Y-axis: symmetric around 0, using max_return if provided
        if max_return is not None:
            y_range = [-abs(max_return), abs(max_return)]
        else:
            # Fallback: use data range if max_return not provided
            y_min = aligned_df['actual_return'].min()
            y_max = aligned_df['actual_return'].max()
            y_abs_max = max(abs(y_min), abs(y_max))
            y_range = [-y_abs_max, y_abs_max]
        
        fig.update_xaxes(
            title_text="Sentiment Score (-1 to 1)", 
            range=[-1, 1],
            row=2, col=1
        )
        fig.update_yaxes(
            title_text="SMA Return (%) - Nov(year-1) to Sep(forecast_year)", 
            range=y_range,
            row=2, col=1
        )
        
        if show_correlation:
            fig.update_xaxes(visible=False, row=3, col=1)
            fig.update_yaxes(visible=False, row=3, col=1)
        
        return fig
    
    def generate_html_report(self, tickers: Optional[List[str]] = None, 
                            output_path: str = "result/sentiment_view.html",
                            years_back: int = 20):
        """
        Generate HTML report with sentiment analysis for multiple tickers
        
        Args:
            tickers: List of tickers to analyze (None = all with sentiment data)
            output_path: Output file path
            years_back: Number of years of history to fetch
        """
        if tickers is None:
            tickers = list(self.sentiment_scores.keys())
        
        print(f"Generating sentiment analysis for {len(tickers)} tickers...")
        print(f"Fetching {years_back} years of history...")
        
        # Fetch historical data
        calendar_days = years_back * 365
        data_results, errors = self.fetcher.fetch_history_days(calendar_days, tickers=tickers)
        
        if errors:
            print(f"Errors fetching data: {len(errors)} tickers")
            for ticker, error in list(errors.items())[:5]:
                print(f"  {ticker}: {error}")
        
        if not data_results:
            print("No data available to visualize")
            return
        
        # Create HTML
        html_parts = []
        html_parts.append("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sentiment Prediction Analysis</title>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
                .container { max-width: 1400px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .ticker-section { margin-bottom: 60px; padding: 20px; background-color: #fafafa; border-radius: 4px; }
                h1 { color: #333; border-bottom: 3px solid #333; padding-bottom: 10px; }
                h2 { color: #555; border-bottom: 2px solid #ddd; padding-bottom: 5px; margin-top: 30px; }
                .summary { background-color: #e8f4f8; padding: 15px; border-radius: 4px; margin-bottom: 20px; }
                .summary h3 { margin-top: 0; }
                .summary-table { width: 100%; border-collapse: collapse; }
                .summary-table th, .summary-table td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
                .summary-table th { background-color: #4CAF50; color: white; }
                #sentiment-tooltip {
                    position: absolute;
                    display: none;
                    background-color: rgba(255, 255, 255, 0.98);
                    border: 2px solid #333;
                    border-radius: 8px;
                    padding: 15px;
                    max-width: 500px;
                    max-height: 400px;
                    overflow-y: auto;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                    z-index: 10000;
                    font-size: 13px;
                    line-height: 1.6;
                    word-wrap: break-word;
                    white-space: pre-wrap;
                }
                #sentiment-tooltip h4 {
                    margin: 0 0 10px 0;
                    color: #333;
                    border-bottom: 1px solid #ddd;
                    padding-bottom: 5px;
                }
                #sentiment-tooltip .sentiment-text {
                    color: #555;
                    margin: 0;
                }
            </style>
        </head>
        <body>
            <div id="sentiment-tooltip">
                <h4>Sentiment Analysis</h4>
                <div class="sentiment-text"></div>
            </div>
            <div class="container">
                <h1>Sentiment Prediction Analysis</h1>
                <p>This report compares sentiment predictions with actual ETF returns to evaluate predictive power.</p>
                <p><strong>Tip:</strong> Hold the "s" key while hovering over sentiment markers to see the full sentiment text.</p>
        """)
        
        # Calculate summary statistics
        summary_data = []
        for ticker in sorted(tickers):
            if ticker not in data_results:
                continue
            
            price_data = data_results[ticker]
            aligned_df = self._align_sentiment_with_returns(ticker, price_data)
            
            if aligned_df.empty:
                continue
            
            correlation_metrics = self._calculate_correlation(aligned_df)
            info = self.fetcher.get_ticker_info(ticker) or {}
            
            summary_data.append({
                'ticker': ticker,
                'name': info.get('name', ticker),
                'correlation': correlation_metrics['correlation'],
                'r_squared': correlation_metrics['r_squared'],
                'samples': correlation_metrics['n_samples']
            })
        
        # Add summary table
        if summary_data:
            html_parts.append('<div class="summary">')
            html_parts.append('<h3>Summary Statistics</h3>')
            html_parts.append('<table class="summary-table">')
            html_parts.append('<tr><th>Ticker</th><th>Name</th><th>Correlation</th><th>R²</th><th>Samples</th></tr>')
            
            # Sort by absolute correlation
            summary_data.sort(key=lambda x: abs(x['correlation']), reverse=True)
            
            for row in summary_data:
                corr_color = 'green' if abs(row['correlation']) > 0.3 else 'orange' if abs(row['correlation']) > 0.1 else 'gray'
                html_parts.append(
                    f"<tr>"
                    f"<td><strong>{row['ticker']}</strong></td>"
                    f"<td>{row['name']}</td>"
                    f"<td style='color: {corr_color};'>{row['correlation']:.3f}</td>"
                    f"<td>{row['r_squared']:.3f}</td>"
                    f"<td>{row['samples']}</td>"
                    f"</tr>"
                )
            
            html_parts.append('</table>')
            html_parts.append('</div>')
        
        # Calculate maximum absolute return across all ETFs for consistent scaling
        all_returns = []
        for ticker in sorted(tickers):
            if ticker not in data_results:
                continue
            price_data = data_results[ticker]
            aligned_df = self._align_sentiment_with_returns(ticker, price_data)
            if not aligned_df.empty:
                all_returns.extend(aligned_df['actual_return'].abs().tolist())
        
        # Calculate max absolute return, add 10% padding
        max_abs_return = max(all_returns) if all_returns else 50.0
        max_abs_return = max_abs_return * 1.1  # Add 10% padding
        
        # Generate figures for each ticker
        for ticker in sorted(tickers):
            if ticker not in data_results:
                continue
            
            price_data = data_results[ticker]
            aligned_df = self._align_sentiment_with_returns(ticker, price_data)
            
            if aligned_df.empty:
                print(f"Skipping {ticker}: No aligned sentiment data")
                continue
            
            print(f"Generating chart for {ticker}...")
            fig = self.create_figure(ticker, price_data, show_correlation=True, max_return=max_abs_return)
            
            info = self.fetcher.get_ticker_info(ticker) or {}
            ticker_name = info.get('name', ticker)
            
            html_parts.append(f'<div class="ticker-section">')
            html_parts.append(f'<h2>{ticker} - {ticker_name}</h2>')
            html_parts.append(fig.to_html(include_plotlyjs=False, div_id=f"plot-{ticker}"))
            html_parts.append('</div>')
        
        html_parts.append("""
            </div>
            <script>
                // Custom sentiment tooltip functionality
                const sentimentTooltip = document.getElementById('sentiment-tooltip');
                const sentimentTextDiv = sentimentTooltip.querySelector('.sentiment-text');
                let sKeyPressed = false;
                let currentHoverData = null;
                
                // Track "s" key state
                document.addEventListener('keydown', function(e) {
                    if (e.key === 's') {
                        sKeyPressed = true;
                        if (currentHoverData) {
                            showSentimentTooltip(currentHoverData);
                        }
                    }
                });
                
                document.addEventListener('keyup', function(e) {
                    if (e.key === 's') {
                        sKeyPressed = false;
                        hideSentimentTooltip();
                    }
                });
                
                function showSentimentTooltip(data) {
                    if (!data || !data.sentiment) return;
                    
                    const year = data.year || data.forecastYear || '';
                    sentimentTextDiv.textContent = data.sentiment;
                    sentimentTooltip.querySelector('h4').textContent = `Sentiment Analysis${year ? ' - ' + year : ''}`;
                    
                    sentimentTooltip.style.display = 'block';
                    updateTooltipPosition(data.event);
                }
                
                function hideSentimentTooltip() {
                    sentimentTooltip.style.display = 'none';
                    currentHoverData = null;
                }
                
                function updateTooltipPosition(event) {
                    if (!event) return;
                    
                    const x = event.clientX + 15;
                    const y = event.clientY + 15;
                    
                    sentimentTooltip.style.left = x + 'px';
                    sentimentTooltip.style.top = y + 'px';
                    
                    // Keep tooltip within viewport
                    const rect = sentimentTooltip.getBoundingClientRect();
                    if (rect.right > window.innerWidth) {
                        sentimentTooltip.style.left = (event.clientX - rect.width - 15) + 'px';
                    }
                    if (rect.bottom > window.innerHeight) {
                        sentimentTooltip.style.top = (event.clientY - rect.height - 15) + 'px';
                    }
                }
                
                // Attach event listeners to all Plotly graphs
                window.addEventListener('load', function() {
                    // Find all Plotly graph containers
                    const plotlyContainers = document.querySelectorAll('.js-plotly-plot');
                    
                    plotlyContainers.forEach(function(container) {
                        const plotDiv = container.querySelector('.plotly');
                        if (!plotDiv) return;
                        
                        // Listen for hover events
                        plotDiv.on('plotly_hover', function(data) {
                            if (!sKeyPressed) return;
                            
                            const point = data.points[0];
                            if (!point || !point.customdata) return;
                            
                            // Extract sentiment data from customdata
                            // Format: [sentiment_text, forecast_year] or [year, forecast_year, sentiment_text]
                            let sentimentText = '';
                            let forecastYear = '';
                            
                            if (Array.isArray(point.customdata)) {
                                if (point.customdata.length === 2) {
                                    // Price chart markers: [sentiment_text, forecast_year]
                                    sentimentText = point.customdata[0] || '';
                                    forecastYear = point.customdata[1] || '';
                                } else if (point.customdata.length >= 3) {
                                    // Scatter plot: [year, forecast_year, sentiment_text]
                                    sentimentText = point.customdata[2] || '';
                                    forecastYear = point.customdata[1] || '';
                                }
                            }
                            
                            if (sentimentText) {
                                currentHoverData = {
                                    sentiment: sentimentText,
                                    forecastYear: forecastYear,
                                    event: data.event
                                };
                                showSentimentTooltip(currentHoverData);
                            }
                        });
                        
                        plotDiv.on('plotly_unhover', function() {
                            if (!sKeyPressed) {
                                hideSentimentTooltip();
                            }
                        });
                        
                        // Also handle mouse move to update position
                        plotDiv.on('plotly_hover', function(data) {
                            if (sKeyPressed && currentHoverData) {
                                updateTooltipPosition(data.event);
                            }
                        });
                    });
                });
            </script>
        </body></html>""")
        
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
    
    parser = argparse.ArgumentParser(description='Visualize sentiment predictions vs ETF performance')
    parser.add_argument('--tickers', type=str, nargs='+', default=None,
                       help='Tickers to analyze (default: all with sentiment data)')
    parser.add_argument('--output', type=str, default='result/sentiment_view.html',
                       help='Output HTML file path')
    parser.add_argument('--years', type=int, default=20,
                       help='Years of history to fetch (default: 20)')
    
    args = parser.parse_args()
    
    viewer = SentimentViewer()
    viewer.generate_html_report(tickers=args.tickers, output_path=args.output, years_back=args.years)


if __name__ == '__main__':
    main()
