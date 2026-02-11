# Prompt: ETF Selection - 5 Plans

อ่าน `select-etf.md` แล้วจัดทำการเลือก โดยสร้างแนวคิดที่แตกต่าง สัก 5 แบบเขียนเป็น 5 plan โดยยังคงใจความสอดคล้องกับ `select-etf.md` แต่เลือก focus ต่างกันหรือมองต่างกัน

แล้วดำเนินหา etf ของแต่ละ plan บันทึกให้เรียบร้อย

ทำแบบอัตโนมัติจนจบ

---

## สิ่งที่ให้ทำเพิ่ม (ตัดสินใจเอง)

1. **สร้าง `plans.md`** — เขียน 5 plans พร้อม focus, n_etfs, เกณฑ์แต่ละแบบ
2. **สร้าง `run_select_plans.py`** — script ดึง metadata (yfinance: AUM, volume, ER, age), ดึงราคา 20y, คำนวณ correlation (สำหรับ Plan B), เลือก ETFs ตามแต่ละ plan
3. **รัน script** → `plans_result.json`, `plans_result.md`, `plan_*_*.json` แยก config แต่ละ plan
4. **สร้าง `batch_5plans.json`** — batch config สำหรับ run_batch.py
5. **รัน backtest** — `uv run python momentum-lab/run_batch.py ... batch_5plans.json --name 5plans`
6. **เพิ่มผล backtest** ใน `plans_result.md` (CAGR, Sharpe, MaxDD)
7. **อัปเดต `select-etf.md`** — เช็คถูก Next Steps ที่เสร็จแล้ว
8. **สร้าง `README.md`** — อธิบาย workflow และวิธีรัน
