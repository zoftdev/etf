#!/usr/bin/env python3
"""
Generate sentiment scores from ETF sentiment data files.

Reads all sentiment YAML files and generates numerical scores from -1 to 1:
- -1 = strong sell
- 0 = neutral
- 1 = strong buy
"""

import yaml
import os
import re
from pathlib import Path
from typing import Dict, List, Any


# Sentiment keywords and their weights
POSITIVE_KEYWORDS = {
    # Strong positive
    'bullish': 0.8, 'rally': 0.8, 'surge': 0.8, 'soar': 0.8, 'strong gains': 0.9,
    'exceptional': 0.9, 'robust': 0.7, 'outperform': 0.8, 'outperforming': 0.8,
    'strong performance': 0.8, 'gains': 0.6, 'growth': 0.6, 'expanding': 0.6,
    'recovery': 0.7, 'rebound': 0.7, 'improving': 0.6, 'optimistic': 0.7,
    'favorable': 0.6, 'positive': 0.5, 'upward': 0.6, 'rising': 0.5,
    'increasing': 0.5, 'accelerating': 0.7, 'momentum': 0.6, 'strength': 0.6,
    'opportunity': 0.5, 'potential': 0.4, 'supportive': 0.5, 'tailwind': 0.6,
    'driving growth': 0.7, 'strong': 0.5, 'healthy': 0.5, 'solid': 0.5,
    'exceeded': 0.6, 'beating': 0.6, 'above expectations': 0.6,
    'double-digit': 0.7, 'significant gains': 0.8, 'substantial': 0.6,
    'resilient': 0.5, 'stable': 0.3, 'maintained': 0.3, 'continued': 0.3,
}

NEGATIVE_KEYWORDS = {
    # Strong negative
    'bearish': -0.8, 'decline': -0.7, 'drop': -0.7, 'fall': -0.7, 'plunge': -0.9,
    'collapse': -0.9, 'crash': -0.9, 'devastating': -0.9, 'worst': -0.8,
    'underperformed': -0.7, 'underperforming': -0.7, 'weak': -0.6, 'weakness': -0.6,
    'slowdown': -0.6, 'slowing': -0.6, 'recession': -0.8, 'crisis': -0.8,
    'headwind': -0.6, 'headwinds': -0.6, 'challenge': -0.5, 'challenges': -0.5,
    'concern': -0.5, 'concerns': -0.5, 'risk': -0.4, 'risks': -0.4,
    'uncertainty': -0.5, 'uncertainties': -0.5, 'volatility': -0.4,
    'pessimistic': -0.7, 'negative': -0.5, 'downward': -0.6, 'falling': -0.5,
    'declining': -0.5, 'decreasing': -0.5, 'deteriorating': -0.7, 'deteriorated': -0.7,
    'pressure': -0.5, 'pressures': -0.5, 'tension': -0.4, 'tensions': -0.4,
    'turmoil': -0.7, 'disruption': -0.6, 'disruptions': -0.6, 'loss': -0.6,
    'losses': -0.6, 'decline': -0.7, 'contraction': -0.7, 'shrinking': -0.6,
    'struggled': -0.6, 'struggling': -0.6, 'difficult': -0.5, 'difficulties': -0.5,
    'below expectations': -0.6, 'disappointing': -0.6, 'disappointment': -0.6,
    'significant decline': -0.8, 'substantial decline': -0.8, 'sharp': -0.7,
    'severe': -0.7, 'major': -0.6, 'significant': -0.5, 'substantial': -0.5,
}

INTENSIFIERS = {
    'very': 1.3, 'extremely': 1.5, 'highly': 1.3, 'significantly': 1.4,
    'substantially': 1.4, 'dramatically': 1.5, 'sharply': 1.4, 'severely': 1.5,
    'exceptionally': 1.4, 'remarkably': 1.3, 'particularly': 1.2, 'especially': 1.2,
    'notably': 1.2, 'considerably': 1.3, 'massively': 1.5, 'tremendously': 1.4,
}

MODERATORS = {
    'modest': 0.7, 'slight': 0.6, 'moderate': 0.8, 'somewhat': 0.8,
    'relatively': 0.9, 'fairly': 0.9, 'reasonably': 0.9, 'marginally': 0.7,
    'limited': 0.6, 'mixed': 0.5, 'uncertain': 0.5,
}


def analyze_sentiment(text: str) -> float:
    """
    Analyze sentiment text and return a score from -1 to 1.
    
    -1 = strong sell
    0 = neutral
    1 = strong buy
    """
    if not text or not text.strip():
        return 0.0
    
    text_lower = text.lower()
    
    # Remove extra whitespace
    text_lower = re.sub(r'\s+', ' ', text_lower)
    
    score = 0.0
    word_count = len(text_lower.split())
    
    # Check for positive keywords
    positive_score = 0.0
    for keyword, weight in POSITIVE_KEYWORDS.items():
        count = text_lower.count(keyword)
        if count > 0:
            positive_score += weight * count
    
    # Check for negative keywords
    negative_score = 0.0
    for keyword, weight in NEGATIVE_KEYWORDS.items():
        count = text_lower.count(keyword)
        if count > 0:
            negative_score += abs(weight) * count
    
    # Apply intensifiers (check words before keywords)
    words = text_lower.split()
    for i, word in enumerate(words):
        if word in INTENSIFIERS:
            # Check next few words for keywords
            for j in range(i + 1, min(i + 4, len(words))):
                next_phrase = ' '.join(words[i:j+1])
                if any(kw in next_phrase for kw in POSITIVE_KEYWORDS.keys()):
                    positive_score *= INTENSIFIERS[word]
                if any(kw in next_phrase for kw in NEGATIVE_KEYWORDS.keys()):
                    negative_score *= INTENSIFIERS[word]
    
    # Apply moderators
    for mod, factor in MODERATORS.items():
        if mod in text_lower:
            positive_score *= factor
            negative_score *= factor
    
    # Calculate net score
    net_score = positive_score - negative_score
    
    # Normalize based on text length (longer texts may have more keywords)
    if word_count > 0:
        normalized_score = net_score / max(word_count / 10, 1)
    else:
        normalized_score = 0.0
    
    # Clamp to [-1, 1] range
    final_score = max(-1.0, min(1.0, normalized_score))
    
    # Apply sigmoid-like function to smooth extreme values
    if abs(final_score) > 0.5:
        final_score = final_score * 0.8 + (0.2 if final_score > 0 else -0.2)
    
    return round(final_score, 3)


def load_sentiment_files(sentiment_dir: Path) -> List[Dict[str, Any]]:
    """Load all sentiment YAML files."""
    sentiment_files = sorted(sentiment_dir.glob('etf_sentiment_*.yaml'))
    all_data = []
    
    for file_path in sentiment_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            all_data.extend(data.get('sentiment_data', []))
    
    return all_data


def generate_scores(sentiment_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate sentiment scores for all ETFs and years."""
    scores_data = {
        'etf_sentiment_scores': []
    }
    
    for etf_data in sentiment_data:
        etf = etf_data['etf']
        name = etf_data['name']
        forecasts = etf_data.get('forecasts', [])
        
        etf_scores = {
            'etf': etf,
            'name': name,
            'scores': []
        }
        
        for forecast in forecasts:
            year = forecast['year']
            forecast_year = forecast['forecast_year']
            sentiment_text = forecast['sentiment']
            
            score = analyze_sentiment(sentiment_text)
            
            etf_scores['scores'].append({
                'year': year,
                'forecast_year': forecast_year,
                'score': score,
                'sentiment_label': get_sentiment_label(score)
            })
        
        # Sort scores by year (descending)
        etf_scores['scores'].sort(key=lambda x: x['year'], reverse=True)
        
        scores_data['etf_sentiment_scores'].append(etf_scores)
    
    # Sort ETFs by ticker
    scores_data['etf_sentiment_scores'].sort(key=lambda x: x['etf'])
    
    return scores_data


def get_sentiment_label(score: float) -> str:
    """Convert score to sentiment label."""
    if score >= 0.7:
        return 'strong buy'
    elif score >= 0.3:
        return 'buy'
    elif score >= -0.3:
        return 'neutral'
    elif score >= -0.7:
        return 'sell'
    else:
        return 'strong sell'


def main():
    """Main function."""
    script_dir = Path(__file__).resolve().parent.parent  # Go up from sentiment/ to root
    sentiment_dir = script_dir / 'sentiment_data'
    output_file = script_dir / 'sentiment' / 'etf_sentiment_score.yaml'
    
    print(f"Loading sentiment files from {sentiment_dir}...")
    sentiment_data = load_sentiment_files(sentiment_dir)
    print(f"Loaded {len(sentiment_data)} ETFs")
    
    print("Generating sentiment scores...")
    scores_data = generate_scores(sentiment_data)
    
    print(f"Writing scores to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(scores_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Print summary
    total_forecasts = sum(len(etf['scores']) for etf in scores_data['etf_sentiment_scores'])
    print(f"\nSummary:")
    print(f"  ETFs processed: {len(scores_data['etf_sentiment_scores'])}")
    print(f"  Total forecasts scored: {total_forecasts}")
    print(f"  Output file: {output_file}")
    
    # Show sample scores
    print("\nSample scores (first ETF, first 5 years):")
    if scores_data['etf_sentiment_scores']:
        first_etf = scores_data['etf_sentiment_scores'][0]
        print(f"  ETF: {first_etf['etf']} - {first_etf['name']}")
        for score_entry in first_etf['scores'][:5]:
            print(f"    {score_entry['year']} → {score_entry['forecast_year']}: "
                  f"{score_entry['score']:.3f} ({score_entry['sentiment_label']})")


if __name__ == '__main__':
    main()
