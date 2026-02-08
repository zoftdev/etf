# Graph Pattern Encoding for Machine Learning

## Approaches to Encode Graph/Chart Patterns as ML Features

### 1. Raw Time Series
- Feed normalized price values directly (e.g., 30 daily prices → 30 features)
- Simple but loses the "shape" meaning

### 2. Shape-Based Encoding

**Piecewise Aggregate Approximation (PAA)**
- Divide the curve into segments, take the mean of each → reduces dimensionality while keeping shape

**Symbolic Aggregate Approximation (SAX)**
- Convert price series into letters: e.g., `"aabccdd"` → encodes shape as a string
- "S curve up" might become `"aabbcddd"` (flat, rise, flat)

**Shapelets**
- Extract small subsequences that are most discriminative between patterns
- ML learns which sub-shapes matter

### 3. Pattern Labels (Categorical)
- Classify the shape first, then use the label as a categorical feature
- Define patterns: "S-curve up", "V-bottom", "double-top", "flat", "linear-up", etc.
- Use DTW (Dynamic Time Warping) to match curves against template patterns
- Or train a small CNN/LSTM classifier to label patterns first

### 4. Image-Based (CNN Approach)
- Render the chart as a small image (e.g., 64x64 pixels)
- Feed into a CNN — the network learns patterns visually
- Surprisingly effective, captures exactly what humans see

### 5. Feature Engineering
- Encode the shape as computed features:
  - Slope of start/mid/end thirds
  - Curvature (2nd derivative)
  - Volatility
  - Max drawdown
  - Inflection point location (where the S-curve bends)
- e.g., S-curve up → `slope_1=-0.1, slope_2=0.5, slope_3=0.1, curvature=positive`

### Comparison

| Approach | Pros | Cons |
|----------|------|------|
| SAX | Simple, fast, proven | Loses fine detail |
| Feature engineering | Interpretable, compact | Manual design needed |
| CNN on images | Captures everything | Black box, needs more data |
| Pattern labels | Human-readable | Hard to define all patterns |

---

## Research Findings: Pattern Encoding vs SMA/RSI

### Key Results from Research

- **Nature 2025 study**: Deep learning stock predictors often create false positives — look great in backtesting but fail in real markets
- **Pattern recognition accuracy**: 80-86% in training but drops to 47-49% on new data (basically coin flip)
- **Raw price features often outperform technical indicators** in ML models (arxiv 2025)
- **CNN on chart images**: Best results ~92% accuracy on trend direction, but struggles to generalize

### What Actually Works

| Approach | Reality |
|----------|---------|
| SMA/RSI alone | Weak predictors but stable, interpretable |
| Pattern encoding alone | Overfits, poor out-of-sample |
| **Hybrid (indicators + patterns + price)** | **Best results in research** |

### Recommendation: Hybrid Approach

Pattern encoding is **not better than** SMA/RSI — it's a **different signal**. Best approach:

1. **Keep existing indicators** (SMA, RSI, etc.)
2. **Add** shape features (slope of 3 segments, curvature, SAX encoding)
3. Let the ML model decide which features matter

Adding shape as an **extra feature alongside** indicators > replacing indicators with shapes.

### Sources

- [Nature 2025 - Stock market trend prediction via chart analysis](https://www.nature.com/articles/s41599-025-04761-8)
- [arxiv - Stock Chart Pattern Recognition with Deep Learning](https://arxiv.org/pdf/1808.00418)
- [arxiv - Impact of Technical Indicators on ML Models](https://arxiv.org/html/2412.15448v1)
- [PLOS One - Pattern Recognition for Stock Trading](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0255558)
- [JP Morgan - Searching for Patterns in Daily Stock Data](https://www.jpmorgan.com/technology/technology-blog/searching-for-patterns)
- [ResearchGate - Hybrid ML Models for Stock Forecasting](https://www.researchgate.net/publication/390613732_Hybrid_Machine_Learning_Models_for_Long-Term_Stock_Market_Forecasting_Integrating_Technical_Indicators)
