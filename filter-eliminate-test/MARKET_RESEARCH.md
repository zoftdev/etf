# Market Research: ETF Elimination/Filter Strategies

## บริบท

จากผลทดสอบก่อนหน้า:
- Indicator strategies (442 variants) ไม่สามารถชนะ Buy-Hold ในเชิง CAGR
- Macro forecast ชนะเฉพาะ US-Sector แต่ Country recommendations ทำลายมูลค่า
- **แนวคิดใหม่:** แทนที่จะ timing → ตัด ETF ที่แย่ออกจาก universe

---

## 1. Momentum-Based Strategies

### 1.1 Classic Momentum (Jegadeesh & Titman, 1993)
- **แนวคิด:** Buy winners, sell losers
- **ผลวิจัย:** 
  - Top performers ชนะ worst performers อย่างต่อเนื่องใน 3-12 เดือนถัดไป
  - ใช้ได้ข้ามหลาย asset classes (stocks, bonds, commodities, currencies)
- **ข้อจำกัด:** Momentum crashes เกิดขึ้นเป็นครั้งคราว (market panics, high volatility)
- **Relevance:** ★★★★★ ตรงกับ objective มาก - ตัดตัวแพ้ออก

### 1.2 Dual Momentum (Gary Antonacci)
- **แนวคิด:** ผสม Absolute momentum + Relative momentum
  - **Absolute:** ถ้า asset return < 0 → ไป cash
  - **Relative:** เลือก asset ที่ดีกว่าในกลุ่ม
- **ผลวิจัย:**
  - GEM Strategy: +20% ใน 1973-74 bear market (vs S&P -40%)
  - Backtest ตั้งแต่ 1950s แสดง resilience ข้าม market regimes
- **Relevance:** ★★★★☆ ดีมาก แต่ต้อง adapt สำหรับ ETF universe ของเรา

### 1.3 Relative Strength Rotation (Meb Faber)
- **แนวคิด:** Rank ETFs by relative strength → hold top N
- **ผลวิจัย:**
  - 1999-2024: 5.92% annual return, 0.47 Sharpe
  - ชนะ buy-hold ~70% ของทุกปี
  - ตัวอย่างจริง (22 ETFs): 128% return vs SPY -4.7% (2005-2010)
- **Relevance:** ★★★★★ ตรงมาก - เลือก top performers โดยอัตโนมัติ

---

## 2. Trend-Based Filters

### 2.1 200-Day Moving Average Filter
- **แนวคิด:** Hold เฉพาะเมื่อ price > 200 SMA, ไป cash เมื่อ price < 200 SMA
- **ผลวิจัย:**
  - ลด max drawdown จาก 56% → 20%
  - ปัญหา: ใช้กับ tradable ETFs ให้ผลแย่กว่า indices
  - 135+ ปี historical data แสดง consistent positive returns
- **Relevance:** ★★★☆☆ ใช้เป็น filter เสริมได้ แต่ไม่ใช่ main strategy

### 2.2 Death Cross Filter (50/200 SMA)
- **แนวคิด:** ตัดออกเมื่อ 50 SMA < 200 SMA (death cross)
- **ผลวิจัย:**
  - จับ extended uptrends และหลีกเลี่ยง major bear markets
  - False positives: "predicted 9 of the last 2 bear markets"
  - Max drawdown reduced significantly
- **Relevance:** ★★★☆☆ ใช้เป็น safety filter ได้

---

## 3. Risk-Based Elimination

### 3.1 Low Volatility / Minimum Variance
- **แนวคิด:** ตัดตัวที่ volatility สูงออก, เก็บเฉพาะ low-vol
- **ผลวิจัย:**
  - 1991-2021: ชนะ S&P 500 ด้วย risk ต่ำกว่า (margin slim)
  - Trade-off: underperform ใน bull markets
- **Relevance:** ★★★☆☆ ดีสำหรับ risk-adjusted แต่ลด CAGR

### 3.2 Volatility Targeting
- **แนวคิด:** ปรับ allocation ตาม volatility เพื่อรักษา constant vol
- **ผลวิจัย:**
  - ลด tail risk และ extreme losses
  - Improve Sharpe ratio สำหรับ risk assets
- **Relevance:** ★★☆☆☆ ซับซ้อนเกินไป สำหรับ objective ของเรา

---

## 4. Quality-Based Elimination

### 4.1 Quality Factor (Quality Minus Junk)
- **แนวคิด:** ตัด "junk" ออก - companies ที่ unprofitable, high debt, poor management
- **Metrics:** ROE, debt-to-equity, earnings consistency
- **ผลวิจัย:**
  - QMJ strategy: significant risk-adjusted returns across 24 countries
  - Long-only: +2.8% annually vs benchmark
- **Relevance:** ★★☆☆☆ ใช้กับ individual stocks ดีกว่า ETF level

---

## 5. Smart Rebalancing

### 5.1 Transaction Filter Rebalancing (2024 Research)
- **แนวคิด:** Rebalance เฉพาะ trades ที่มี strong signals, skip weak signals
- **ผลวิจัย:**
  - จับ factor premiums ส่วนใหญ่ แต่ลด turnover/costs มาก
- **Relevance:** ★★★☆☆ ใช้ optimize execution ได้

---

## 6. Tactical Asset Allocation

### 6.1 GTAA (Meb Faber)
- **แนวคิด:** 
  - Hold เฉพาะ assets > 10-month MA
  - Rank by momentum → hold top N
- **ผลวิจัย:**
  - GTAA-5: 4.8% annual, Sharpe 0.66
  - GTAA-13: 3.9% annual, Sharpe 0.54
  - Aggressive versions: top 3-6 only → higher return potential
- **Relevance:** ★★★★☆ ใกล้เคียงกับที่เราต้องการ

---

## สรุป: Strategies ที่น่าทดสอบ (Priority Order)

| Priority | Strategy | ทำไมถึงเลือก |
|----------|----------|-------------|
| 1 | **Relative Strength Top-N** | ชนะ B&H 70% ของปี, simple, proven |
| 2 | **Dual Momentum** | ผสม absolute + relative, crash protection |
| 3 | **Momentum + Trend Filter** | ตัดตัวแพ้ + ตัดตัวที่ trend ลง |
| 4 | **Worst-Performer Elimination** | Simple: ตัด bottom X% ทุกปี |
| 5 | **High Drawdown Elimination** | ตัดตัวที่ MaxDD > threshold |
| 6 | **Low Volatility Filter** | ตัดตัว high-vol ออก |

---

## Research Sources

1. Jegadeesh & Titman (1993) - "Returns to Buying Winners and Selling Losers"
2. AQR - "The Case for Momentum Investing"
3. Gary Antonacci - Dual Momentum / Global Equities Momentum
4. Meb Faber - "A Quantitative Approach to Tactical Asset Allocation"
5. Research Affiliates (2024) - "Smart Rebalancing"
6. SSRN papers on relative strength, low volatility, quality factors
