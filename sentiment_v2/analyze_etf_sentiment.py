#!/usr/bin/env python3
"""
Analyze ETF sentiment scores from YAML files and create visualization.
Uses ChatGPT sentiment scores (not sentiment_score: 0.0).
"""

import yaml
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from typing import Dict, List, Tuple
import statistics

def extract_sentiment_scores(yaml_path: Path) -> Tuple[str, str, List[float]]:
    """
    Extract ChatGPT sentiment scores from a YAML file.
    
    Returns:
        Tuple of (etf_symbol, etf_name, list_of_scores)
    """
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if not data or 'sentiment_data' not in data:
        return None, None, []
    
    scores = []
    etf_symbol = None
    etf_name = None
    
    for etf_entry in data['sentiment_data']:
        if 'etf' in etf_entry:
            etf_symbol = etf_entry['etf']
        if 'name' in etf_entry:
            etf_name = etf_entry['name']
        
        if 'forecasts' not in etf_entry:
            continue
            
        for forecast in etf_entry['forecasts']:
            if 'sentiments' not in forecast:
                continue
                
            for sentiment_entry in forecast['sentiments']:
                # Extract ChatGPT sentiment score
                if 'sentiment_result' in sentiment_entry:
                    sentiment_result = sentiment_entry['sentiment_result']
                    if 'chatgpt' in sentiment_result:
                        chatgpt_data = sentiment_result['chatgpt']
                        if 'score' in chatgpt_data:
                            score = chatgpt_data['score']
                            if score is not None:
                                scores.append(float(score))
    
    return etf_symbol, etf_name, scores

def analyze_all_etfs(sentiment_dir: Path) -> pd.DataFrame:
    """Analyze all ETF sentiment files and return DataFrame."""
    yaml_files = sorted(sentiment_dir.glob("etf_sentiment_*.yaml"))
    
    results = []
    
    for yaml_file in yaml_files:
        etf_symbol, etf_name, scores = extract_sentiment_scores(yaml_file)
        
        if etf_symbol and scores:
            avg_score = statistics.mean(scores)
            median_score = statistics.median(scores)
            min_score = min(scores)
            max_score = max(scores)
            count = len(scores)
            
            results.append({
                'symbol': etf_symbol,
                'name': etf_name or '',
                'avg_sentiment': avg_score,
                'median_sentiment': median_score,
                'min_sentiment': min_score,
                'max_sentiment': max_score,
                'sentiment_count': count,
                'scores': scores
            })
    
    df = pd.DataFrame(results)
    return df.sort_values('avg_sentiment', ascending=False)

def create_visualization(df: pd.DataFrame, output_path: Path):
    """Create interactive visualization of ETF sentiment scores."""
    
    # Filter out ETFs with no scores
    df = df[df['sentiment_count'] > 0].copy()
    
    if len(df) == 0:
        print("No sentiment data found!")
        return
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            'ETF Average Sentiment Scores (ChatGPT)',
            'Top 20 ETFs by Sentiment Score'
        ),
        vertical_spacing=0.15,
        row_heights=[0.6, 0.4]
    )
    
    # Color mapping based on sentiment score
    def get_color(score):
        if score >= 0.5:
            return '#2ecc71'  # Green for positive
        elif score >= 0.3:
            return '#f39c12'  # Orange for neutral-positive
        elif score >= 0.15:
            return '#95a5a6'  # Gray for neutral
        else:
            return '#e74c3c'  # Red for negative
    
    colors = [get_color(score) for score in df['avg_sentiment'].tolist()]
    
    # Plot 1: All ETFs sorted by sentiment
    fig.add_trace(
        go.Bar(
            x=df['symbol'].tolist(),
            y=df['avg_sentiment'].tolist(),
            text=[f"{s:.3f}" for s in df['avg_sentiment'].tolist()],
            textposition='outside',
            marker=dict(color=colors),
            name='Average Sentiment',
            hovertemplate='<b>%{x}</b><br>' +
                          'Avg Sentiment: %{y:.3f}<br>' +
                          'Count: %{customdata}<br>' +
                          '<extra></extra>',
            customdata=df['sentiment_count'].tolist()
        ),
        row=1, col=1
    )
    
    # Plot 2: Top 20 ETFs
    top_20 = df.head(20)
    top_colors = [get_color(score) for score in top_20['avg_sentiment'].tolist()]
    
    fig.add_trace(
        go.Bar(
            x=top_20['symbol'].tolist(),
            y=top_20['avg_sentiment'].tolist(),
            text=[f"{s:.3f}" for s in top_20['avg_sentiment'].tolist()],
            textposition='outside',
            marker=dict(color=top_colors),
            name='Top 20 Average Sentiment',
            hovertemplate='<b>%{x}</b><br>' +
                          'Name: %{customdata[0]}<br>' +
                          'Avg Sentiment: %{y:.3f}<br>' +
                          'Count: %{customdata[1]}<br>' +
                          '<extra></extra>',
            customdata=list(zip(top_20['name'].tolist(), top_20['sentiment_count'].tolist()))
        ),
        row=2, col=1
    )
    
    # Update layout
    fig.update_layout(
        title_text='ETF Sentiment Analysis Dashboard',
        height=1200,
        showlegend=False,
        xaxis_title='ETF Symbol',
        yaxis_title='Average Sentiment Score',
        xaxis2_title='ETF Symbol',
        yaxis2_title='Average Sentiment Score',
    )
    
    # Update x-axis for both plots
    fig.update_xaxes(tickangle=45, row=1, col=1)
    fig.update_xaxes(tickangle=45, row=2, col=1)
    
    # Add horizontal reference lines
    fig.add_hline(y=0.5, line_dash="dash", line_color="green", 
                  annotation_text="Positive Threshold (0.5)", row=1, col=1)
    fig.add_hline(y=0.3, line_dash="dash", line_color="orange", 
                  annotation_text="Neutral-Positive (0.3)", row=1, col=1)
    fig.add_hline(y=0.5, line_dash="dash", line_color="green", 
                  annotation_text="Positive Threshold (0.5)", row=2, col=1)
    fig.add_hline(y=0.3, line_dash="dash", line_color="orange", 
                  annotation_text="Neutral-Positive (0.3)", row=2, col=1)
    
    # Save to HTML
    fig.write_html(str(output_path))
    print(f"Visualization saved to: {output_path}")

def print_top_etfs(df: pd.DataFrame, threshold: float = 0.4):
    """Print ETFs with good sentiment scores."""
    df_filtered = df[df['avg_sentiment'] >= threshold].copy()
    
    print(f"\n{'='*80}")
    print(f"ETFs with Good Sentiment Scores (>= {threshold})")
    print(f"{'='*80}")
    print(f"{'Symbol':<10} {'Avg Score':<12} {'Count':<8} {'Name':<50}")
    print(f"{'-'*80}")
    
    for _, row in df_filtered.iterrows():
        print(f"{row['symbol']:<10} {row['avg_sentiment']:<12.3f} {row['sentiment_count']:<8} {row['name'][:48]:<50}")
    
    print(f"\nTotal ETFs with good sentiment: {len(df_filtered)}")
    print(f"Total ETFs analyzed: {len(df)}")

def write_etf_avg_score_yaml(df: pd.DataFrame, output_path: Path) -> None:
    """Write etf_avg_score.yaml (sorted max to min by avg_sentiment)."""
    # df is already sorted descending by avg_sentiment
    records = []
    for _, row in df.iterrows():
        records.append({
            "symbol": row["symbol"],
            "name": row["name"],
            "avg_sentiment": round(float(row["avg_sentiment"]), 4),
            "sentiment_count": int(row["sentiment_count"]),
        })
    data = {"etf_avg_scores": records}
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"YAML saved to: {output_path}")

def main():
    """Main function."""
    script_dir = Path(__file__).parent
    output_dir = script_dir  # save in sentiment_v2/
    output_path = output_dir / "etf_sentiment_analysis.html"
    
    print("Analyzing ETF sentiment scores...")
    df = analyze_all_etfs(script_dir)
    
    if len(df) == 0:
        print("No sentiment data found!")
        return
    
    print(f"\nAnalyzed {len(df)} ETFs")
    print(f"\nTop 10 ETFs by Average Sentiment:")
    print(df[['symbol', 'name', 'avg_sentiment', 'sentiment_count']].head(10).to_string(index=False))
    
    # Print ETFs with good sentiment
    print_top_etfs(df, threshold=0.4)
    
    # Create visualization
    print("\nCreating visualization...")
    create_visualization(df, output_path)
    
    # Save summary CSV
    csv_path = output_dir / "etf_sentiment_summary.csv"
    df[['symbol', 'name', 'avg_sentiment', 'median_sentiment', 'min_sentiment', 'max_sentiment', 'sentiment_count']].to_csv(csv_path, index=False)
    print(f"\nSummary saved to: {csv_path}")

    # Save ETF avg scores YAML (sorted max to min)
    yaml_path = output_dir / "etf_avg_score.yaml"
    write_etf_avg_score_yaml(df, yaml_path)

if __name__ == "__main__":
    main()
