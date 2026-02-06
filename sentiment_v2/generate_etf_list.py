#!/usr/bin/env python3
"""Generate ETF list CSV from etf.yaml"""

import yaml
import csv
from pathlib import Path

# Translation mapping: Thai to English
THAI_TO_ENGLISH = {
    # Commodities
    'ทองคำ': 'Gold',
    'เงิน': 'Silver',
    'น้ำมันดิบ': 'Crude Oil',
    'ก๊าซธรรมชาติ': 'Natural Gas',
    'สินค้าเกษตร': 'Agriculture',
    
    # Countries - Asia Pacific
    'จีน': 'China',
    'อินเดีย': 'India',
    'ญี่ปุ่น': 'Japan',
    'ไต้หวัน': 'Taiwan',
    'เกาหลีใต้': 'South Korea',
    'ไทย': 'Thailand',
    'เวียดนาม': 'Vietnam',
    'อินโดนีเซีย': 'Indonesia',
    'สิงคโปร์': 'Singapore',
    'ออสเตรเลีย': 'Australia',
    
    # Countries - Europe
    'เยอรมนี': 'Germany',
    'อังกฤษ': 'United Kingdom',
    'ฝรั่งเศส': 'France',
    'สวิตเซอร์แลนด์': 'Switzerland',
    'เนเธอร์แลนด์': 'Netherlands',
    'อิตาลี': 'Italy',
    'สเปน': 'Spain',
    'ตุรกี': 'Turkey',
    
    # Countries - Americas
    'แคนาดา': 'Canada',
    'เม็กซิโก': 'Mexico',
    'บราซิล': 'Brazil',
    'ชิลี': 'Chile',
    'อาร์เจนตินา': 'Argentina',
    
    # Countries - Middle East & Africa
    'ซาอุดีอาระเบีย': 'Saudi Arabia',
    'อิสราเอล': 'Israel',
    'แอฟริกาใต้': 'South Africa',
    'สหรัฐอาหรับเอมิเรตส์': 'UAE',
    
    # Regions
    'ทั่วโลก (ไม่รวมเมกา)': 'International ex-US',
}

def translate_to_english(term):
    """Translate Thai term to English, or return as-is if already English"""
    return THAI_TO_ENGLISH.get(term, term)

def extract_etf_list(yaml_path):
    """Extract ETF names and related search terms from etf.yaml"""
    etf_list = []
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    etfs = data.get('etfs', {})
    
    # Commodity ETFs
    if 'commodity' in etfs:
        commodity = etfs['commodity']
        
        # Specific commodities
        if 'specific' in commodity:
            for item in commodity['specific']:
                ticker = item.get('ticker', '')
                name = item.get('name', '')
                category = item.get('category', '')
                if name and ticker:
                    search_term = translate_to_english(category) if category else name
                    etf_list.append(f"{name}|{search_term}")
        
        # Broad commodities
        if 'broad' in commodity:
            for item in commodity['broad']:
                ticker = item.get('ticker', '')
                name = item.get('name', '')
                if name and ticker:
                    etf_list.append(f"{name}|commodity")
    
    # Momentum ETFs
    if 'momentum' in etfs:
        momentum = etfs['momentum']
        if 'items' in momentum:
            for item in momentum['items']:
                ticker = item.get('ticker', '')
                name = item.get('name', '')
                if name and ticker:
                    etf_list.append(f"{name}|momentum")
    
    # World ETFs
    if 'world' in etfs:
        world = etfs['world']
        
        # Asia Pacific
        if 'asia_pacific' in world:
            for item in world['asia_pacific'].get('etfs', []):
                country = item.get('country', '')
                name = item.get('name', '')
                tickers = item.get('tickers', [])
                if name and tickers:
                    search_term = translate_to_english(country) if country else name
                    etf_list.append(f"{name}|{search_term}")
        
        # Europe
        if 'europe' in world:
            for item in world['europe'].get('etfs', []):
                country = item.get('country', '')
                name = item.get('name', '')
                tickers = item.get('tickers', [])
                if name and tickers:
                    search_term = translate_to_english(country) if country else name
                    etf_list.append(f"{name}|{search_term}")
        
        # Americas
        if 'americas' in world:
            for item in world['americas'].get('etfs', []):
                country = item.get('country', '')
                name = item.get('name', '')
                tickers = item.get('tickers', [])
                if name and tickers:
                    search_term = translate_to_english(country) if country else name
                    etf_list.append(f"{name}|{search_term}")
        
        # Middle East & Africa
        if 'middle_east_africa' in world:
            for item in world['middle_east_africa'].get('etfs', []):
                country = item.get('country', '')
                name = item.get('name', '')
                tickers = item.get('tickers', [])
                if name and tickers:
                    search_term = translate_to_english(country) if country else name
                    etf_list.append(f"{name}|{search_term}")
        
        # Broad Market
        if 'broad_market' in world:
            for item in world['broad_market'].get('etfs', []):
                region = item.get('region', '')
                name = item.get('name', '')
                tickers = item.get('tickers', [])
                if name and tickers:
                    search_term = translate_to_english(region) if region else name
                    etf_list.append(f"{name}|{search_term}")
    
    # US Sectors
    if 'us_sectors' in etfs:
        sectors = etfs['us_sectors']
        if 'items' in sectors:
            for item in sectors['items']:
                sector = item.get('sector', '')
                name = item.get('name', '')
                ticker = item.get('ticker', '')
                if name and ticker:
                    search_term = sector if sector else name
                    etf_list.append(f"{name}|{search_term}")
    
    return etf_list

def main():
    workspace_root = Path(__file__).parent.parent
    yaml_path = workspace_root / 'etf.yaml'
    csv_path = workspace_root / 'sentiment_v2' / 'etf-list.csv'
    
    etf_list = extract_etf_list(yaml_path)
    
    # Write to CSV
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for etf_entry in etf_list:
            writer.writerow([etf_entry])
    
    print(f"Generated {len(etf_list)} ETF entries in {csv_path}")
    return etf_list

if __name__ == '__main__':
    main()
