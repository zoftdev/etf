# ETF Selection - 5 Plans

เลือก ETFs ตามแนวทาง select-etf.md แต่ focus ต่างกัน 5 แบบ

## โครงสร้าง

| ไฟล์ | คำอธิบาย |
|------|----------|
| `select-etf.md` | เกณฑ์และหลักการเลือก ETF |
| `plans.md` | 5 plans แต่ละแบบ focus ต่างกัน |
| `run_select_plans.py` | Script ดึงข้อมูลและเลือก ETF ตามแต่ละ plan |
| `plans_result.md` | ผลลัพธ์ ETF ของทั้ง 5 plans |
| `plan_*_*.json` | Config แต่ละ plan สำหรับ simulate |
| `batch_5plans.json` | Batch config สำหรับ backtest ทั้ง 5 plans |

## การรัน

```bash
# เลือก ETFs ตาม 5 plans (ดึง metadata + price จาก yfinance)
uv run python momentum-lab/select-etf/run_select_plans.py

# Backtest เปรียบเทียบทั้ง 5 plans (ใช้ param/default)
uv run python momentum-lab/run_batch.py momentum-lab/select-etf/loop1/batch_5plans.json -o momentum-lab/select-etf/loop1 --name loop1
```

## สรุป 5 Plans

| Plan | Focus | n ETFs |
|------|-------|--------|
| A | QuantPedia Classic | 13 |
| B | Low Correlation | 13 |
| C | Long Backtest (15y data) | 13 |
| D | Low Expense | 13 |
| E | Sector Tilt (+XLU, XLF) | 15 |
