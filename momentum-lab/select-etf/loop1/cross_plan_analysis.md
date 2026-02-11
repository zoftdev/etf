# Cross-Plan Analysis: หา Robust Config ที่ดีข้าม 5 Plans

## โจทย์

แต่ละ plan (A-E) มี ETFs ที่ต่างกัน แต่เราต้องการหา **parameter values ที่ทนได้ดีหลายๆ plan** โดยไม่สนว่าจะใช้ plan ไหน

**คำถาม:**
1. ถ้าใช้ value เดียวกันทำทั้ง 5 plans → **Top 5 values ที่ให้ผลดีทั้ง 5 คืออะไร?**
2. ถ้าตัด plan ที่ต่างจากพวกออกไปหนึ่ง → **จะยังเป็น value เดิมไหม?**

---

## วิธีคิด

### Step 1: ระบุ Config Patterns ที่เปรียบเทียบได้

แต่ละ plan รัน batch optimize ด้วย config เดียวกัน (เช่น `F1-n5-sw02-m5`) จึงเปรียบเทียบผลลัพธ์ข้าม plans ได้

Config pattern ที่สำคัญ:
- `n_long` = จำนวน ETFs ที่ long
- `short_weight` (sw) = น้ำหนัก short (0, 0.2, 0.3, 0.4)
- `mom_periods` (m) = จำนวน momentum periods (m4=4 periods, m5=5 periods, m252=252 only)

### Step 2: ดึง Sharpe ของ Config เดียวกันจากทุก Plan

จากไฟล์ `plan_*/results.csv` ดึง `mom0_sharpe` ของแต่ละ config

### Step 3: คำนวณ Avg Sharpe ข้าม Plans

เลือก config ที่ avg Sharpe สูงและ min Sharpe ไม่ต่ำเกินไป (robust)

---

## ผลการวิเคราะห์

### Plans Overview

| Plan | Focus | ETFs | Best Sharpe | Notes |
|------|-------|------|-------------|-------|
| **A** | QuantPedia Classic | 13 (SPY,IWM,EFA,EEM,IYR,QQQ,LQD,IEF,TIP,GLD,USO,DBC,FXE) | 0.87 | Baseline |
| **B** | Low Correlation | 13 (SPY,EFA,IYR,EEM,TLT,IEF,USO,GLD,UUP,FXE,DBC,TIP,SLV) | 0.87 | Sharpe ต่ำกว่า consistently |
| **C** | Long Backtest | 13 (SPY,QQQ,IWM,EFA,EEM,VEU,TLT,IEF,LQD,GLD,SLV,USO,FXE) | 0.86 | |
| **D** | Low Expense | 13 (SPY,QQQ,IWM,EFA,EEM,TLT,IEF,LQD,GLD,SLV,USO,IYR,VTV) | 0.86 | MaxDD สูงกว่า |
| **E** | Sector Tilt | 15 (เพิ่ม XLU,XLF) | 0.83 | MaxDD ต่ำสุด (-21%) |

### Top Configs เปรียบเทียบข้าม Plans

| Config Pattern | n_long | sw | mom | plan_a | plan_b | plan_c | plan_d | plan_e | **Avg** | **Min** |
|----------------|--------|-----|-----|--------|--------|--------|--------|--------|---------|---------|
| **F1-n5-sw02-m5** | 5 | 0.2 | 5 periods | 0.87 | 0.67 | 0.80 | 0.82 | 0.76 | **0.784** | 0.67 |
| **A-n5** | 5 | 0.2 | default | 0.87 | 0.67 | 0.80 | 0.82 | 0.76 | **0.784** | 0.67 |
| **F1-n5-sw02-m4** | 5 | 0.2 | 4 periods | 0.83 | 0.68 | 0.80 | 0.83 | 0.79 | **0.786** | 0.68 |
| **F1-n5-sw02-m252** | 5 | 0.2 | 252 only | 0.83 | 0.69 | 0.82 | 0.84 | 0.74 | **0.784** | 0.69 |
| **F1-n5-sw03-m5** | 5 | 0.3 | 5 periods | 0.85 | 0.64 | 0.80 | 0.81 | 0.72 | **0.764** | 0.64 |
| **F1-n4-sw02-m5** | 4 | 0.2 | 5 periods | 0.80 | 0.70 | 0.72 | 0.74 | 0.74 | **0.740** | 0.70 |

### Sharpe Distribution by Config

```
Config: n_long=5, short_weight=0.2, mom_periods=5
┌─────────┬─────────┬─────────────────────────────────────────┐
│  Plan   │ Sharpe  │ ████████████████████████████████████████│
├─────────┼─────────┼─────────────────────────────────────────┤
│ plan_a  │  0.87   │ ████████████████████████████████████████│
│ plan_d  │  0.82   │ ███████████████████████████████████     │
│ plan_c  │  0.80   │ █████████████████████████████████       │
│ plan_e  │  0.76   │ ████████████████████████████            │
│ plan_b  │  0.67   │ ███████████████████                     │
└─────────┴─────────┴─────────────────────────────────────────┘
```

---

## คำตอบ

### Q1: Top 5 Values ที่ดีทั้ง 5 Plans

**Optimal Robust Config:**

```json
{
  "n_long": 5,
  "n_short": 1,
  "short_weight": 0.2,
  "corr_threshold": 1.0,
  "corr_short_days": 10,
  "mom_periods_days": [21, 63, 126, 189, 252]
}
```

**เหตุผล:**
- `n_long=5` → ปรากฏใน Top configs ของทุก plan (58% ของ top 50 overall)
- `short_weight=0.2` → balance ระหว่าง hedge กับ cost (78% ของ top 50)
- `corr_short_days=10` → responsive กว่า default 20 (98% ของ top 50)
- `mom_periods=5` → รวม 21-day ช่วยจับ short-term momentum

**ผลลัพธ์:**
- Sharpe: 0.67 - 0.87 (avg 0.78) ข้าม 5 plans
- CAGR: 8.8% - 11.5%
- MaxDD: -21% to -35%

---

### Q2: ถ้าตัด Plan ที่ต่างออก?

**Plan B (Low Correlation)** เป็น outlier:
- Sharpe ต่ำกว่าทุก plan อย่างสม่ำเสมอ (~0.67 vs 0.80+)
- ETF selection เน้น low correlation มากเกินไป ทำให้ momentum signal อ่อนลง

**เปรียบเทียบ: 5 Plans vs 4 Plans (ไม่รวม B)**

| Config | Avg (5 plans) | Avg (4 plans, ไม่รวม B) |
|--------|---------------|-------------------------|
| n5, sw0.2, m5 | 0.784 | **0.813** |
| n5, sw0.2, m4 | 0.786 | **0.813** |
| n5, sw0.3, m5 | 0.764 | **0.795** |

**สรุป: Optimal values ยังคงเหมือนเดิม!**

ตัด Plan B ออกไม่เปลี่ยน optimal config เพียงแต่ avg Sharpe สูงขึ้น (0.78 → 0.81)

---

## Insights

### Why Plan B underperforms?

1. **Low correlation ETFs มี momentum signal ที่อ่อนกว่า** - assets ที่ไม่ correlate กันมักมี behavior ต่างกันมาก ทำให้ rank by momentum ไม่ stable

2. **UUP (US Dollar Index)** - currency ETF มี trend persistence ต่ำกว่า equity/commodity

3. **ไม่มี QQQ/IWM** - ขาด US equity momentum leaders

### Robustness Observation

- **n_long=5 robust ข้าม plans** - ไม่ว่า ETF universe จะต่างกัน การถือ 5 ตัวยังคงดีที่สุด
- **short_weight=0.2 > 0.3** - hedge น้อยลงดีกว่าในทุก plan
- **corr_short_days=10** - parameter นี้ robust มาก (98% ของ top 50)

---

## Recommendations

### For Production Use

```json
{
  "n_long": 5,
  "n_short": 1,
  "short_weight": 0.2,
  "corr_threshold": 1.0,
  "corr_short_days": 10,
  "corr_long_days": 250,
  "mom_periods_days": [21, 63, 126, 189, 252]
}
```

### ETF Selection Priority

1. **Plan A (QuantPedia Classic)** - Balanced, proven
2. **Plan E (Sector Tilt)** - Best drawdown protection (-21%)
3. **Plan D (Low Expense)** - Cost efficient
4. **Plan C (Long Backtest)** - Good for validation
5. **Plan B (Low Correlation)** - ใช้สำหรับ diversification study แต่ไม่แนะนำสำหรับ production

---

## Next Steps

1. [ ] ทดสอบ out-of-sample period
2. [ ] Walk-forward optimization
3. [ ] ทดสอบ regime-dependent parameters
4. [ ] สร้าง ensemble ของหลาย plans
