# ETF Sentiment Search Documentation

## Overview

This document describes the workflow for searching and collecting ETF forecast sentiments from 2025 documents that predict 2026 performance. The process systematically searches for 10-20 sources per ETF, extracts relevant forecast information, and structures it into YAML format.

## Workflow

### Step 1: Generate ETF List

**Script:** `generate_etf_list.py`

**Purpose:** Extract ETF names and related search terms from `etf.yaml` and create a CSV file for processing.

**Input:** `../etf.yaml` (root directory)

**Output:** `etf-list.csv` (format: `ETF Name|Search Term`)

**Process:**
1. Reads ETF definitions from `etf.yaml`
2. Extracts ETF names and associated categories/countries/sectors
3. Translates Thai terms to English for search queries
4. Creates CSV with format: `name|related_search`

**Example Output:**
```
iShares Gold Trust|Gold
SPDR S&P 500 ETF Trust|US Market
iShares MSCI China|China
```

### Step 2: Search and Process Forecasts

**Script:** `process_results.py`

**Purpose:** Process each ETF from the list, search for forecasts, and generate YAML output files.

**Input:** 
- `etf-list.csv` (list of ETFs to process)
- `../etf.yaml` (for ticker lookup)
- Hardcoded search results in the script

**Output:**
- `etf_sentiment_{ticker}.yaml` (one file per ETF)
- `done.csv` (processed ETFs)

**Process:**

1. **Read Next ETF**
   - Reads the first line from `etf-list.csv`
   - Extracts ETF name and search term

2. **Find Ticker**
   - Looks up ticker symbol from `etf.yaml` using ETF name
   - Handles nested structures (commodities, world regions, US sectors)

3. **Get Search Results**
   - Retrieves pre-collected search results for the ticker
   - Results are hardcoded in the script (collected via `web_search` tool)
   - Each ETF has 10-20 search results

4. **Filter and Parse**
   - Filters results for documents published in 2025 or early 2026 (Jan-Feb)
   - Only includes documents that explicitly mention 2026 forecasts
   - Extracts: title, snippet, URL, date, source

5. **Generate YAML**
   - Creates YAML file matching `etf_sentiment_ewg_example.yaml` format
   - Structure:
     ```yaml
     etf:
       name: "ETF Name"
       ticker: "TICKER"
     sentiments:
       - sentiment: "Forecast text..."
         source: "source_name"
         author: ""
         date: "2025-12-31"
         sentiment_score: 0.0
     ```

6. **Update CSV Files**
   - Removes processed line from `etf-list.csv`
   - Appends to `done.csv`

## File Structure

```
sentiment_v2/
├── generate_etf_list.py          # Step 1: Generate ETF list CSV
├── process_results.py            # Step 2: Process forecasts
├── etf-list.csv                  # Queue of ETFs to process
├── done.csv                      # Processed ETFs
├── etf_sentiment_ewg_example.yaml # Example output format
├── etf_sentiment_*.yaml          # Generated sentiment files (one per ETF)
└── sentiment-searc.md           # This documentation
```

## Search Criteria

### Date Filtering
- **Primary:** Documents published in 2025
- **Secondary:** Early 2026 documents (January-February) that explicitly mention 2026 forecasts
- **Requirement:** Must contain "2026" in title or snippet

### Content Requirements
- Must be forecast/prediction content (not just current analysis)
- Should mention specific ETF or sector
- Include price targets, outlook, or performance predictions

### Search Strategy
- 10-20 searches per ETF using variations:
  - `{ETF Name} {Ticker} forecast 2026 2025`
  - `{ETF Name} 2026 price prediction 2025`
  - `{ETF Name} 2026 outlook investment 2025`
  - `{ETF Name} 2026 forecast analysis 2025`
  - `{Sector/Country} ETF 2026 forecast 2025`
  - And similar variations

## Data Collection Process

### Manual Collection (Current Method)
1. Use `web_search` tool to search for each ETF
2. Collect 10-20 relevant results per ETF
3. Extract: title, URL, snippet, date
4. Hardcode results into `process_results.py` as `{ticker}_search_results` list
5. Add `elif ticker == '{TICKER}':` condition to route to results

### Result Structure
```python
{ticker}_search_results = [
    {
        'title': 'Article Title',
        'url': 'https://example.com/article',
        'snippet': 'Forecast text mentioning 2026...',
        'date': '2025-12-31'
    },
    # ... 10-20 more results
]
```

## YAML Output Format

Each generated YAML file follows this structure:

```yaml
etf:
  name: "ETF Full Name"
  ticker: "TICKER"
sentiments:
  - sentiment: "Forecast text extracted from search results (max 1000 chars)"
    source: "extracted_source_name"
    author: ""
    date: "2025-12-31"
    sentiment_score: 0.0
  # ... more sentiment entries
```

### Source Extraction
- Extracts domain name from URL (e.g., `morningstar.com` from `https://www.morningstar.com/...`)
- Removes common prefixes (`www.`, `finance.`, etc.)

## Usage

### Initial Setup
```bash
# Generate ETF list from etf.yaml
python3 generate_etf_list.py
```

### Process ETFs
```bash
# Process one ETF at a time (for verification)
python3 process_results.py

# Continue until list is empty
# Script automatically processes next ETF each run
```

### Check Status
```bash
# Count remaining ETFs
wc -l etf-list.csv

# Count processed ETFs
wc -l done.csv

# Count generated YAML files
ls -1 etf_sentiment_*.yaml | wc -l
```

## Notes

- **Ticker Lookup:** The script handles various YAML structures:
  - Commodities (specific/broad)
  - World regions (nested: asia_pacific.etfs, etc.)
  - US sectors (items list)
  - Momentum ETFs (items list)

- **Date Filtering:** Lenient approach includes early 2026 documents (Jan-Feb) if they explicitly mention 2026 forecasts

- **CSV Management:** Lines are moved (not copied) from `etf-list.csv` to `done.csv` to track progress

- **Error Handling:** Script warns if ticker not found but continues processing

## Completion Status

- **Total ETFs:** 53
- **Processed:** 53 (all complete)
- **Remaining:** 0

All ETFs have been processed and sentiment YAML files generated.
