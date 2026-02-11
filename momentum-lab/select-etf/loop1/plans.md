# 5 Plans: ETF Selection for Momentum Strategy

แต่ละ plan ยังคงใช้หลักเกณฑ์พื้นฐานจาก select-etf.md แต่ focus แตกต่างกัน

---

## Plan A: QuantPedia Classic (รักษาโครงสร้างเดิม)

**Focus:** ใกล้เคียงกับ QuantPedia 13 ETFs มากที่สุด — mainstream, ใช้ได้จริง

- จำนวน: **13 ETFs** (เหมือน QuantPedia)
- Asset class: Stock 6, Bond 3, Commodity 3, Currency 1
- ไม่เพิ่ม sector ETFs
- คัดจากรายชื่อ candidates ที่มีใน select-etf.md โดยตรง
- ใช้ default list เป็นฐาน ถ้าผ่าน quantitative filters ก็ใช้เลย

**Output:** รายชื่อ 13 ตัวที่สอดคล้อง QuantPedia structure

---

## Plan B: Low Correlation Priority

**Focus:** ลด correlation ระหว่าง ETFs ให้มากที่สุด เพื่อ diversification ที่ดี

- จำนวน: **13 ETFs**
- ขั้นตอน: จาก candidates ทั้งหมด → fetch returns 5 ปี → คำนวณ pairwise correlation
- เลือก 13 ตัวที่ avg pairwise correlation ต่ำที่สุด (หรือ greedy: เลือกทีละตัวที่ minimize correlation กับ set ที่เลือกแล้ว)
- ยังคงกระจาย asset class อย่างน้อย 2 ตัวต่อ class

**Output:** 13 ETFs ที่ avg correlation ต่ำ

---

## Plan C: Long Backtest Era (15–20 ปี)

**Focus:** เลือก ETFs ที่มี data ย้อนหลังนาน เพื่อ backtest ครบ 15–20 ปี

- จำนวน: **13 ETFs**
- เงื่อนไข: ETF ต้องมีราคาย้อนหลังอย่างน้อย 15 ปี (2010)
- คัดเฉพาะ tickers ที่มี historical data ตั้งแต่ ~2010
- กระจาย asset class ตามสัดส่วน standard

**Output:** 13 ETFs ที่ backtest ได้ยาวนาน

---

## Plan D: Minimize Expense Ratio

**Focus:** ลด cost drag — เลือก ETFs ที่ expense ratio ต่ำในแต่ละ category

- จำนวน: **13 ETFs**
- เงื่อนไข: expense ratio < 0.30% (เข้มงวดกว่า default 0.5%)
- กระจาย asset class ตามสัดส่วน
- ถ้ามีหลายตัวใน category เลือกตัวที่ expense ต่ำสุด

**Output:** 13 ETFs cost-efficient

---

## Plan E: Sector Momentum Tilt (เพิ่ม Sector ETFs)

**Focus:** โอกาส momentum ใน sector — รวม sector ETFs เข้าไป

- จำนวน: **15 ETFs** (มากกว่า default เล็กน้อย)
- โครงสร้าง: US Equity 4, Int'l 2, Bonds 3, Commodities 3, **Sector 2–3** (เช่น XLU, XLF, XLE, XLK)
- Sector ETFs อาจ correlate สูงกับ SPY — ยอมรับ trade-off เพื่อ sector rotation

**Output:** 15 ETFs รวม sector rotation

---

## Summary Table

| Plan | Focus              | n_etfs | Key Difference                          |
|------|--------------------|--------|------------------------------------------|
| A    | QuantPedia Classic | 13     | โครงสร้างเดิม, mainstream                |
| B    | Low Correlation    | 13     | minimize pairwise correlation           |
| C    | Long Backtest      | 13     | ต้องมี data 15+ ปี                       |
| D    | Low Expense        | 13     | ER < 0.30%                              |
| E    | Sector Tilt        | 15     | เพิ่ม sector ETFs                       |
