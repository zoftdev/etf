# ETF Sentiment Scan (v3)

## Purpose
Produce one sentiment report per ETF: gather recent public forecasts for each ETF, score them with a consistent sentiment scale, and write structured output files.

## Inputs

- **ETF list:** `sentiment_v3/etf-v3.yaml`  
  Use this as the list of ETFs to process. Structure: categories (e.g. commodity, momentum, world regions, US sectors), each with items that have `tickers`, `segment`, `name`, `description`. Treat each item as one “ETF” (use primary ticker when multiple).

- **Output shape:** `sentiment_v3/example/`  
  The example file there shows the expected structure of each report: one file per ETF, with sentiment_data, etf ticker, name, forecasts (run_date, list of sentiments with source/url/author/datetime, and sentiment_result containing the scored LLM output).

- **Sentiment scoring spec:** `sentiment_v3/sentiment-prompt.md`  
  Use this to define how to score text: scale -1.0 to 1.0, labels (strong sell / sell / neutral / buy / strong buy), and the required output shape (score, sentiment_label, reasoning). The agent should use this spec when deriving scores from forecast text (e.g. via an LLM or equivalent).

- **Output directory:** The directory where generated report files are written (e.g. a “generate” or output folder). The agent decides the exact path and naming; each ETF must get its own file matching the example structure.

## Process (high level)

1. **One ETF at a time**  
   Iterate over each ETF from the list. For each:
   - Identify the ETF (primary ticker, name, segment as needed).
   - Search for **recent public forecasts** about that ETF that were published **within the last 7 days** (from today). How you search (sources, queries, APIs) is up to the agent.
   - For each relevant forecast text:
     - Record provenance: source, url, author, datetime (when available).
     - Run **sentiment scoring** according to `sentiment-prompt.md`: produce score, sentiment_label, and reasoning.
     - Store the raw sentiment text plus the scored result in the structure shown in the example (under forecasts → sentiments → sentiment_result.llm_result or equivalent).
   - Attach a run_date (e.g. today) to the forecast block.
   - Write **one output file per ETF** into the output directory, following the example format.

2. **No forecasts found**  
   If for an ETF there are no public forecasts within the time window, the agent may either skip that ETF, write a file with empty or minimal forecasts, or document “no data” in the file—design this behavior as appropriate.

## Constraints and freedoms

- **Do** keep output structure and semantics aligned with the example and with the sentiment scale and labels in `sentiment-prompt.md`.
- **Do** process ETFs one by one so that each report is self-contained and can be generated or re-run independently.


read detail-dev.md for more detail
