# ETF Sentiment Scan (v3) — Detail for Dev

## Goal
Produce one sentiment report per ETF: gather recent public forecasts, score with the sentiment spec, write one YAML file per ETF.

## 1. Load config
- Read `sentiment_v3/etf-v3.yaml`, flatten to a list of ETF items (primary ticker + name + segment).
- Resolve output directory (e.g. `sentiment_v3/output/` or from config/env).

## 2. Per-ETF pipeline
For each ETF:
- **Search:** Find recent public forecasts (last 7 days). How (web search API, RSS, fixed sources) is up to the agent. Capture: source, url, author, datetime, raw forecast text.
- **Score:** For each forecast text, call LLM using `sentiment-prompt.md` (replace `$input text` with the text). Parse JSON → score, sentiment_label, reasoning.
- **Write:** One YAML file per ETF (e.g. `output/etf_sentiment_<TICKER>.yaml`) matching the example: `sentiment_data` → etf, name, forecasts (run_date + list of sentiments with `sentiment_result.llm_result`).

## 3. Edge cases
- **No forecasts in window:** Write a file with `forecasts: []` or one “no data” entry so structure stays valid.
- **Search/API failures:** Log and continue with other ETFs; optional retry.

---
Refs: `skill.yaml`, `etf-v3.yaml`, `sentiment-prompt.md`, `example/etf_sentiment_argt.yaml`.
