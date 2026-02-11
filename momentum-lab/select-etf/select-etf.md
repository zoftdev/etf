# ETF Selection Criteria for Momentum Strategy

## Why 13 ETFs? (QuantPedia Approach)

QuantPedia เลือก 13 ETFs เป็น **mainstream multi-asset approach** เพื่อ:
- กระจายข้าม asset class ที่มี low correlation
- ลด overall portfolio volatility
- ให้ momentum strategy rotate ไปยัง asset ที่ทำผลงานดีในแต่ละช่วง

```
DEFAULT_ETFS = [
    "SPY", "IWM", "EFA", "EEM", "IYR", "QQQ",  # stock (6)
    "LQD", "IEF", "TIP",                        # bond (3)
    "GLD", "USO", "DBC",                        # commodity (3)
    "FXE",                                      # currency (1)
]
```

---

## Selection Criteria

### 1. Quantitative Filters (พื้นฐาน)

| เกณฑ์ | ค่าแนะนำ | เหตุผล |
|-------|----------|--------|
| **AUM (Assets)** | > $500M - $1B | Liquidity, ไม่ถูก liquidate |
| **Volume เฉลี่ย** | > 500K shares/day | เข้าออกง่าย, spread แคบ |
| **อายุ ETF** | > 5 ปี | มี track record, ผ่านหลาย market cycle |
| **Expense Ratio** | < 0.5% | ลด drag on return |

### 2. Asset Class Diversification

สูตร: **เลือก 2-3 ETFs ต่อ asset class หลัก**

| Asset Class | สัดส่วน | ตัวอย่าง ETFs |
|-------------|---------|---------------|
| **US Equity** | 3-4 ตัว | SPY, QQQ, IWM, IYR |
| **Int'l Equity** | 2 ตัว | EFA (developed), EEM (emerging) |
| **Bonds** | 2-3 ตัว | TLT/IEF (treasury), LQD (corporate), TIP (inflation) |
| **Commodities** | 2-3 ตัว | GLD, DBC, USO |
| **Alternatives** | 0-2 ตัว | VNQ (REIT), FXE (currency) |

### 3. Correlation-based Selection

**เป้าหมาย:** avg pairwise correlation < 0.5 ภายในกลุ่ม

วิธีคำนวณ:
1. ดึง historical returns 3-5 ปี
2. คำนวณ correlation matrix
3. เลือก ETFs ที่ไม่ correlate สูงเกินไปกับตัวอื่นๆ

### 4. Exclusion Rules

| ไม่เลือก | เหตุผล |
|----------|--------|
| Leveraged ETFs (2x, 3x) | เสื่อมค่า, ไม่เหมาะ hold ระยะยาว |
| Inverse ETFs | เสื่อมค่า, ไม่เหมาะ hold ระยะยาว |
| Sector แคบเกินไป | volatility สูง, idiosyncratic risk |
| ETF อายุ < 5 ปี | ไม่มี track record ผ่าน crisis |

---

## Decision Points

### จำนวน ETFs
- **10-15 ตัว:** แบบ QuantPedia, manageable
- **20-30 ตัว:** กระจายมากขึ้น แต่ dilute momentum signal

### Market Focus
- **US only:** ง่ายกว่า, data ดีกว่า
- **Global:** diversify แต่ซับซ้อนขึ้น

### รวม Sector ETFs?
- **ข้อดี:** momentum works well on sectors
- **ข้อเสีย:** correlate สูงกับ SPY, อาจ overweight equity

### Backtest Period
- **15-20 ปี:** จำกัดเฉพาะ ETFs เก่า (SPY, QQQ, EFA...)
- **5-10 ปี:** มี ETFs ใหม่ให้เลือกมากกว่า

---

## Potential ETF Candidates

### Equity - US
| Ticker | Name | Category |
|--------|------|----------|
| SPY | S&P 500 | Large-cap |
| QQQ | Nasdaq 100 | Tech/Growth |
| IWM | Russell 2000 | Small-cap |
| IYR | US Real Estate | REIT |
| VTV | Value | Factor |
| MTUM | Momentum | Factor |

### Equity - International
| Ticker | Name | Category |
|--------|------|----------|
| EFA | EAFE | Developed ex-US |
| EEM | Emerging Markets | Emerging |
| VEU | All-World ex-US | Global |

### Bonds
| Ticker | Name | Category |
|--------|------|----------|
| TLT | 20+ Year Treasury | Long duration |
| IEF | 7-10 Year Treasury | Medium duration |
| LQD | Investment Grade Corp | Corporate |
| TIP | TIPS | Inflation-protected |
| HYG | High Yield | Junk bonds |

### Commodities
| Ticker | Name | Category |
|--------|------|----------|
| GLD | Gold | Precious metal |
| SLV | Silver | Precious metal |
| USO | Oil | Energy |
| DBC | Commodity Index | Broad commodity |

### Currency / Alternatives
| Ticker | Name | Category |
|--------|------|----------|
| FXE | Euro | Currency |
| UUP | US Dollar Index | Currency |

---

## Next Steps

1. [x] สร้าง script คัดกรอง ETFs อัตโนมัติ (AUM, volume, age) → `run_select_plans.py`
2. [x] คำนวณ correlation matrix ของ candidates → Plan B
3. [x] เลือก final list 13-20 ETFs → 5 plans ใน `plans.md` / `plans_result.md`
4. [ ] Backtest เปรียบเทียบกับ QuantPedia 13 ETFs
