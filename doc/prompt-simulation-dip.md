# Prompt: Backtest Dip-Buy Strategy — ค้นหาพารามิเตอร์ที่กำไร

## วัตถุประสงค์
สร้างสคริปต์/โมดูล backtest กลยุทธ์ Dip-Buy กับ ETF ทั้งหมดจาก `etf.yaml` แล้วไล่หาชุดพารามิเตอร์ที่ให้ผลตอบแทน (หรือ metric หลัก) ดีที่สุด

## ข้อมูลและ Logic ที่ใช้ (อ้างอิงจาก `etf_comparison.py` และ `etf_data_fetcher.py`)

### รายการ ETF
- ดึงรายการ ticker ทั้งหมดจาก `etf.yaml` ผ่าน `ETFDataFetcher` (ใช้ `tickers_map` หรือ `get_tickers_by_group()` แล้วรวมทุก group) — ให้ทำ backtest **ทีละ ticker** หรือรวมเป็นพอร์ตก็ได้ (กำหนดในข้อกำหนดเพิ่ม)

### Logic การเป็น "Dip-Buy candidate" (ต้องผ่านทุกข้อ)
1. **Trend vs SMA > 0**  
   - `trend_vs_sma_pct = (price_today / SMA(trend_days) - 1) * 100`
2. **SMA slope > 0** (ถ้า `use_slope_filter=True`)  
   - `sma_slope_pct = (SMA_today / SMA_today - slope_lookback_days - 1) * 100`
3. **Dip < 0**  
   - `dip_pct = (price_today / price_today - dip_days - 1) * 100`
4. **Min dip** (ถ้า `min_dip_pct > 0`): ต้อง `dip_pct <= -min_dip_pct`

### พารามิเตอร์ที่ต้องไล่หาค่า
| Parameter | ความหมาย | ช่วงที่แนะนำสำหรับ grid/optimize |
|-----------|----------|-----------------------------------|
| `trend_days` | จำนวนวันของ SMA เทรนด์ | เช่น 50, 100, 150, 200 |
| `dip_days` | จำนวนวันย้อนหลังสำหรับคำนวณ Dip | เช่น 3, 5, 7, 10, 14 |
| `slope_lookback_days` | จำนวนวันสำหรับ SMA slope | เช่น 10, 20, 30 |
| `use_slope_filter` | เปิด/ปิดเงื่อนไข SMA slope > 0 | True / False |
| `min_dip_pct` | ขั้นต่ำของความลึกของ dip (%) | เช่น 0, 1, 2, 3 |

### กติกาการเทรด (ให้กำหนดใน backtest)
- **สัญญาณซื้อ**: วันที่ราคาผ่านเงื่อนไข Dip-Buy (ใช้ข้อมูลย้อนหลัง ณ วันนั้นเท่านั้น ไม่ใช้ข้อมูลอนาคต)
- **ออกจากตำแหน่ง**: กำหนดกฎชัดเจน 
   ทำแบบ ถือ 15 วัน เพื่อ ดูผลงานของการ dip เบื้องต้น
   และ simulation กำหนด กำไรหรือขาดทุนตามเป้า % / ตัดขาดทุนที่ -X% ฯลฯ

## งานที่ต้องทำ
1. **Backtest ต่อ ticker**: สำหรับแต่ละ ETF ใน `etf.yaml` รัน backtest กับช่วงเวลาที่มีข้อมูล (ใช้ `ETFDataFetcher.fetch_history_for_windows` หรือ `fetch_history_days` ให้เพียงพอต่อ `trend_days` และ `dip_days` ที่ใหญ่ที่สุด)
2. **ไล่หาพารามิเตอร์ที่กำไร**:  
   - ทำ grid search หรือ optimization  over ชุดพารามิเตอร์ด้านบน (หรือ subset ที่สมเหตุสมผล)  
   - สำหรับแต่ละ ticker (หรือรวมทุก ticker) คำนวณผลตอบแทน/กำไร, สถิติ (เช่น win rate, max drawdown, Sharpe) แล้วสรุปว่าชุด param ไหนให้ผลดี
3. **ผลลัพธ์**:  
   - สร้างตารางหรือรายงานสรุป เช่น (ticker หรือ "all"), ชุดพารามิเตอร์, ผลตอบแทน/กำไร, metric เพิ่มเติมที่ใช้  
   - แนะนำชุดพารามิเตอร์ที่ "ได้กำไร" หรือดีที่สุดต่อ ticker/ต่อพอร์ต ตามที่ออกแบบไว้

## ข้อกำหนดเทคนิค
- ใช้ Python; ใช้ `etf.yaml`, `ETFDataFetcher` และ logic จาก `etf_comparison.py` (screener filter + score) เป็นหลัก
- ห้าม look-ahead bias: ณ วันที่ให้สัญญาณ ใช้ได้แค่ข้อมูลถึงวันนั้น
- ระบุช่วงวันที่ backtest (เช่น เริ่มหลังมีข้อมูลเพียงพอสำหรับ SMA(trend_days) ครั้งแรก)
