# ETF Performance Comparison Dashboard

Interactive web dashboard to compare ETF performance with customizable time periods and group filtering.

## Features

- 📊 **Interactive Charts**: Plotly-based visualization with hover details
- ⏱️ **Period Selection**: Compare performance over 7 days, 1 month, 6 months, 1 year, or 3 years
- 👁️ **Show/Hide Groups**: Toggle visibility of ETF groups (Commodity, Momentum, World regions)
- 🔄 **Browser Session Storage**: Your preferences (period, visible groups) are saved in browser session
- 💾 **Smart Caching**: Data is cached locally to reduce API calls (refreshes daily)
- 📉 **Data Optimization**: Automatically optimizes data points for large date ranges
- ⚠️ **Error Handling**: Shows errors for tickers that fail to load

## Installation

1. Create virtual environment (if not exists):
```bash
uv venv
```

2. Install dependencies:
```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

Or if using standard pip:
```bash
pip install -r requirements.txt
```

## Usage

1. Activate virtual environment:
```bash
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Start the dashboard:
```bash
python etf_comparison.py
```

2. Open your browser and navigate to:
```
http://127.0.0.1:8050
```

3. Use the controls:
   - **Period Selector**: Choose time period (default: 7 days)
   - **Group Checkboxes**: Show/hide entire groups of ETFs
   - **Legend**: Click on legend items to show/hide individual ETFs

## Data Source

- Uses `yfinance` library to fetch data from Yahoo Finance
- Data is cached in `cache/` directory (one file per ticker/period combination)
- Cache is refreshed daily automatically

## Project Structure

```
investment/
├── etf.yaml                 # ETF configuration (tickers, names, groups)
├── etf_comparison.py        # Main Dash application
├── etf_data_fetcher.py      # Data fetching and caching logic
├── requirements.txt         # Python dependencies
├── cache/                   # Cached data (auto-generated)
└── README.md               # This file
```

## Notes

- First run may take longer as it fetches data for all ETFs
- Subsequent runs are faster due to caching
- Cache files are stored per ticker and period combination
- Browser session storage persists your preferences during the session
