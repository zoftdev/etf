Sentiment Scoring  

## Task
Analyze the provided financial market sentiment text and generate a numerical sentiment score from -1.0 to 1.0, where:
- **-1.0 to -0.7**: Strong Sell (very bearish, significant negative outlook)
- **-0.7 to -0.3**: Sell (bearish, negative outlook)
- **-0.3 to 0.3**: Neutral (mixed or balanced outlook)
- **0.3 to 0.7**: Buy (bullish, positive outlook)
- **0.7 to 1.0**: Strong Buy (very bullish, significant positive outlook)
 
## Output Format

Provide your response in the following JSON format:

```json
{
  "score": 0.146,
  "sentiment_label": "neutral",
  "reasoning": "Brief explanation of why this score was assigned"
}
```

Where:
- `score`: Numerical value from -1.0 to 1.0 (use 3 decimal places)
- `sentiment_label`: One of: "strong sell", "sell", "neutral", "buy", "strong buy"
- `reasoning`: 1-2 sentence explanation of the key factors that influenced the score

## Example

**Input Text:**
```
Financial market experts surveyed by ZEW expected the DAX to grow by 5 percent in 2007, with an average closing target of 6,700 points, based on the forecasted year-end closing of approximately 6,400 points in December 2006.
The DAX achieved strong performance in 2006, growing approximately 19 percent from the start of the year and surpassing the psychological 7,000-point barrier, reaching as high as 7,005.34 points.
Experts characterized the market development as healthy and fundamentally sound, driven by strong corporate profits and cost-cutting measures rather than speculative bubbles like the 2000 IT crash.
German stocks were valued reasonably with a price/earnings ratio of approximately 13.9 percent compared to US stocks at 21.2 percent, with the forecast reflecting more modest growth expectations than 2006's exceptional performance.
```

**Output:**
```json
{
  "score": 0.146,
  "sentiment_label": "neutral",
  "reasoning": "Positive factors include strong 2006 performance (19% growth) and healthy market fundamentals, but the forecast for 2007 is modest (5% growth) compared to the exceptional 2006 performance, indicating a more cautious outlook."
}
```

## Instructions

1. Read the entire sentiment text carefully
2. Identify all positive, negative, and neutral indicators
3. Consider the overall tone and context
4. Assign a score that reflects the net sentiment
5. Provide clear reasoning for your score

---
Input :

$input text