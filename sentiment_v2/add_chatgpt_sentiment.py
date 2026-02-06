#!/usr/bin/env python3
"""
Script to add ChatGPT sentiment analysis to ETF sentiment YAML files.
Reads all YAML files, checks for existing sentiment_result.chatgpt,
and fills missing entries using OpenAI API.
"""

import os
import json
import yaml
import argparse
from pathlib import Path
from openai import OpenAI
from typing import Dict, Any, Optional

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Read the prompt template
PROMPT_TEMPLATE_PATH = Path(__file__).parent / "sentiment-prompt.md"


def load_prompt_template() -> str:
    """Load the sentiment prompt template."""
    with open(PROMPT_TEMPLATE_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def get_chatgpt_sentiment(sentiment_text: str, prompt_template: str) -> Optional[Dict[str, Any]]:
    """
    Call OpenAI API to get sentiment analysis.
    
    Args:
        sentiment_text: The sentiment text to analyze
        prompt_template: The prompt template from sentiment-prompt.md
        
    Returns:
        Dict with score, sentiment_label, and reasoning, or None if error
    """
    # Replace $input text placeholder with actual sentiment text
    prompt = prompt_template.replace("$input text", sentiment_text)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using cost-effective model
            messages=[
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        
        # Validate and return result
        if all(key in result for key in ['score', 'sentiment_label', 'reasoning']):
            return {
                'score': float(result['score']),
                'sentiment_label': result['sentiment_label'],
                'reasoning': result['reasoning']
            }
        else:
            print(f"  Warning: Missing keys in API response: {result}")
            return None
            
    except Exception as e:
        print(f"  Error calling OpenAI API: {e}")
        return None


def has_chatgpt_sentiment(sentiment_entry: Dict[str, Any]) -> bool:
    """Check if sentiment_result.chatgpt already exists."""
    return (
        'sentiment_result' in sentiment_entry and
        isinstance(sentiment_entry['sentiment_result'], dict) and
        'chatgpt' in sentiment_entry['sentiment_result'] and
        isinstance(sentiment_entry['sentiment_result']['chatgpt'], dict) and
        'score' in sentiment_entry['sentiment_result']['chatgpt']
    )


def process_yaml_file(yaml_path: Path, prompt_template: str, limit: int = None) -> tuple:
    """
    Process a single YAML file, adding ChatGPT sentiment where missing.
    
    Args:
        yaml_path: Path to YAML file
        prompt_template: The prompt template
        limit: Maximum number of sentiments to process (None for all)
        
    Returns:
        Tuple of (processed_count, skipped_count)
    """
    print(f"\nProcessing: {yaml_path.name}")
    
    # Load YAML file
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if not data or 'sentiment_data' not in data:
        print(f"  Skipping: Invalid structure")
        return 0, 0
    
    processed = 0
    skipped = 0
    
    # Iterate through all sentiments
    for etf_entry in data['sentiment_data']:
        if 'forecasts' not in etf_entry:
            continue
            
        for forecast in etf_entry['forecasts']:
            if 'sentiments' not in forecast:
                continue
                
            for sentiment_entry in forecast['sentiments']:
                # Check limit
                if limit is not None and processed >= limit:
                    print(f"  Reached limit of {limit}, stopping")
                    break
                
                # Skip if already has ChatGPT sentiment
                if has_chatgpt_sentiment(sentiment_entry):
                    skipped += 1
                    continue
                
                # Get sentiment text
                sentiment_text = sentiment_entry.get('sentiment', '')
                if not sentiment_text:
                    print(f"  Skipping: Empty sentiment text")
                    skipped += 1
                    continue
                
                # Get ChatGPT sentiment
                print(f"  Analyzing sentiment...")
                chatgpt_result = get_chatgpt_sentiment(sentiment_text, prompt_template)
                
                if chatgpt_result:
                    # Initialize sentiment_result if needed
                    if 'sentiment_result' not in sentiment_entry:
                        sentiment_entry['sentiment_result'] = {}
                    
                    # Add ChatGPT result
                    sentiment_entry['sentiment_result']['chatgpt'] = chatgpt_result
                    processed += 1
                    print(f"    ✓ Added: score={chatgpt_result['score']}, label={chatgpt_result['sentiment_label']}")
                else:
                    print(f"    ✗ Failed to get sentiment")
                    skipped += 1
            
            if limit is not None and processed >= limit:
                break
        
        if limit is not None and processed >= limit:
            break
    
    # Save updated YAML file
    if processed > 0:
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"  Saved: {processed} sentiments added, {skipped} skipped")
    else:
        print(f"  No changes: {skipped} skipped")
    
    return processed, skipped


def main():
    """Main function to process all YAML files."""
    parser = argparse.ArgumentParser(
        description='Add ChatGPT sentiment analysis to ETF sentiment YAML files'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Maximum number of sentiments to process per file (default: 10, use 0 for unlimited)'
    )
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent
    yaml_files = sorted(script_dir.glob("etf_sentiment_*.yaml"))
    
    if not yaml_files:
        print("No YAML files found!")
        return
    
    print(f"Found {len(yaml_files)} YAML files")
    if args.limit > 0:
        print(f"Limit: {args.limit} sentiments per file")
    else:
        print("Limit: unlimited (processing all sentiments)")
    
    # Load prompt template
    prompt_template = load_prompt_template()
    
    total_processed = 0
    total_skipped = 0
    
    # Process each file with specified limit (None if limit is 0)
    limit = None if args.limit == 0 else args.limit
    for yaml_file in yaml_files:
        processed, skipped = process_yaml_file(yaml_file, prompt_template, limit=limit)
        total_processed += processed
        total_skipped += skipped
    
    print(f"\n=== Summary ===")
    print(f"Total processed: {total_processed}")
    print(f"Total skipped: {total_skipped}")


if __name__ == "__main__":
    main()
