# หลักการ Simulation Dip-Buy (dip_buy_backtest.py)

## วัตถุประสงค์

Backtest กลยุทธ์ Dip-Buy กับ ETF ทั้งหมดจาก `etf.yaml` เพื่อ:
- หาชุดพารามิเตอร์ที่ให้ผลตอบแทน (หรือ metric หลัก) ดีที่สุด ต่อ ticker / ต่อกลุ่ม / ทั้งพอร์ต
- สรุปค่ากลางต่อกลุ่ม (group) ว่ากลุ่มไหนได้ผลดีกับชุดพารามิเตอร์ใด

---

## ข้อมูลที่ใช้

- **รายการ ETF:** ดึงจาก `etf.yaml` ผ่าน `ETFDataFetcher` (`tickers_map` หรือ `get_tickers_by_group()`)
- **ราคา:** `fetch_history_days(days, tickers)` — จำนวนวันกำหนดได้จาก `--years` (เช่น 3 ปี = 365×3 + 60 วัน) หรือคำนวณจาก window ขั้นต่ำของ indicator
- **กลุ่ม (group):** แต่ละ ticker มี `group` จาก YAML (เช่น Commodity - Specific, Momentum, ภูมิภาคยุโรป) ใช้สำหรับสรุปค่ากลางต่อกลุ่ม

---

## Logic สัญญาณ Dip-Buy (ต้องผ่านทุกข้อ)

ณ วันที่ตรวจสอบ ใช้เฉพาะข้อมูล**ถึงวันนั้น** (ไม่มี look-ahead)

| # | เงื่อนไข | สูตร / ความหมาย |
|---|----------|-------------------|
| 1 | **Trend vs SMA > 0** | `trend_vs_sma_pct = (price_today / SMA(trend_days) - 1) × 100` → ราคาอยู่เหนือเทรนด์ |
| 2 | **SMA slope > 0** (ถ้า `use_slope_filter=True`) | `sma_slope_pct = (SMA_today / SMA_{today - slope_lookback_days} - 1) × 100` → เทรนด์ยังขึ้น |
| 3 | **Dip < 0** | `dip_pct = (price_today / price_{today - dip_days} - 1) × 100` → มีการดึงลง (pullback) |
| 4 | **Min dip** (ถ้า `min_dip_pct > 0`) | ต้อง `dip_pct ≤ -min_dip_pct` (เช่น ต้องดึงลงอย่างน้อย 2%) |

ผ่านครบ → วันที่นั้นเป็น **สัญญาณ Dip-Buy**

---

## พารามิเตอร์กลยุทธ์ (DipBuyParams)

| Parameter | ความหมาย | ค่า default | ช่วงที่ใช้ใน grid |
|-----------|----------|-------------|--------------------|
| `trend_days` | จำนวนวันของ SMA เทรนด์ | 200 | 50, 100, 150, 200 |
| `dip_days` | จำนวนวันย้อนหลังสำหรับคำนวณ Dip | 7 | 3, 5, 7, 10, 14 |
| `slope_lookback_days` | จำนวนวันสำหรับ SMA slope | 20 | 10, 20, 30 |
| `use_slope_filter` | เปิด/ปิดเงื่อนไข SMA slope > 0 | True | True / False |
| `min_dip_pct` | ขั้นต่ำความลึกของ dip (%) | 0 | 0, 1, 2, 3 |

---

## กติกาเข้า–ออก (ExitRules)

### การเข้า
- **สัญญาณที่วัน T** → **ซื้อที่ Open ของวัน T+1** (จำลองว่าเห็นสัญญาณหลังปิดวัน T)

### การออก (ตรวจทุกวัน ถ้าถึงก่อนครบ hold_days ก็ออก)
1. **ถือครบ `hold_days`** (default 15 วัน) → ขายที่ Close วันนั้น  
2. **Take profit:** ถ้า `take_profit_pct` กำหนด และ Close ≥ entry × (1 + take_profit_pct/100) → ออกที่ Close  
3. **Stop loss:** ถ้า `stop_loss_pct` กำหนด (ค่าติดลบ) และ Close ≤ entry × (1 + stop_loss_pct/100) → ออกที่ Close  

### ต้นทุนรอบเทรด (spread)
- `spread_pct`: ผลต่างขาย–ซื้อ (round-trip) เป็น %  
- Return ต่อรอบ: `return_pct = (exit_price/entry_price - 1)×100 - spread_pct`  
- ตัวอย่าง: `spread_pct = 0.15` → ลบ 0.15% จาก return ทุกรอบ  

---

## ข้อกำหนดเทคนิค

- **ไม่มี look-ahead:** ณ วันที่ให้สัญญาณ ใช้ได้แค่ข้อมูลถึงวันนั้น (Close, SMA ฯลฯ คำนวณจากอดีตเท่านั้น)  
- **ช่วง backtest:** เริ่มนับจากวันแรกที่คำนวณ indicator ได้ครบ (หลังมีข้อมูลอย่างน้อย `max(trend_days + slope_lookback_days + 2, dip_days + 2)` วัน)  

---

## การรัน Simulation

### โหมดพารามิเตอร์
- **ไม่ใส่ grid:** ใช้ชุดพารามิเตอร์เดียว (trend_days=200, dip_days=7, slope_lookback_days=20, use_slope_filter=True, min_dip_pct=0)  
- **`--small-grid`:** ไล่ 3 ชุดพารามิเตอร์  
- **`--grid`:** ไล่ชุดเต็มจาก `param_grid_reasonable()`  

### ขั้นตอน
1. โหลด tickers จาก `etf.yaml` (หรือจาก `--tickers` / `--limit`)  
2. ดึงราคาย้อนหลังตาม `--years` หรือ window ขั้นต่ำ  
3. สำหรับแต่ละ (ticker × ชุดพารามิเตอร์): รัน backtest → ได้ total_return_pct, n_trades, win_rate, max_drawdown_pct, sharpe_approx  
4. แต่ละผลแนบ `group` จาก `get_ticker_info(ticker)`  

---

## ผลลัพธ์ที่แสดง

1. **Backtest period** — ช่วงวันที่ backtest (ตัวอย่าง)  
2. **Best params per ticker** — แต่ละ ticker ชุดพารามิเตอร์ที่ให้ total_return_pct สูงสุด  
3. **Best single param set (overall)** — คู่ (ticker, param) เดียวที่ให้ return สูงสุดทั้งพอร์ต  
4. **สรุปค่ากลางต่อกลุ่ม** — แต่ละ group: ชุดพารามิเตอร์ที่ให้**ค่าเฉลี่ย return สูงสุด**ในกลุ่มนั้น + mean return, mean win rate, mean max dd, จำนวน ticker  
5. **Per-ticker aggregate** — สรุปเฉลี่ย/รวมต่อ ticker (ทุกชุดพารามิเตอร์) แสดง 20 ticker แรก  

---

## เมตริกที่คำนวณ

- **total_return_pct:** ผลตอบแทนรวม (%) จากผลคูณ (1 + return_i/100) ทุกรอบ  
- **n_trades:** จำนวนรอบซื้อ–ขาย  
- **win_rate:** % รอบที่ return_pct > 0  
- **max_drawdown_pct:** ขาดทุนจากจุดสูงสุดมากสุด (%) ของ equity curve  
- **sharpe_approx:** ประมาณ Sharpe จาก return ต่อรอบ (ปรับตามความถี่)  

---

## CLI หลัก

```bash
uv run python dip_buy_backtest.py --years 3                    # 3 ปี, ชุด param เดียว
uv run python dip_buy_backtest.py --years 3 --small-grid       # 3 ปี, ไล่ 3 ชุด
uv run python dip_buy_backtest.py --years 3 --grid             # 3 ปี, grid เต็ม
uv run python dip_buy_backtest.py --years 3 --spread 0.15      # ใส่ spread 0.15%
uv run python dip_buy_backtest.py --hold-days 20 --limit 10   # ถือ 20 วัน, ทดสอบ 10 ticker
```

| อาร์กิวเมนต์ | ความหมาย | Default |
|--------------|----------|---------|
| `--years` | จำนวนปีย้อนหลัง (calendar days) | ไม่ใช้ (ใช้ window ขั้นต่ำ) |
| `--hold-days` | จำนวนวันถือก่อนออก | 15 |
| `--take-profit` | กำไรเป้า % (ออกที่ Close) | ไม่ใช้ |
| `--stop-loss` | ขาดทุนตัด % (ค่าติดลบ) | ไม่ใช้ |
| `--spread` | ต้นทุนรอบเทรด % (sell-buy diff) | 0 |
| `--small-grid` | ไล่ 3 ชุดพารามิเตอร์ | ปิด |
| `--grid` | ไล่ชุดพารามิเตอร์เต็ม | ปิด |
| `--limit` | จำกัดจำนวน ticker (ทดสอบ) | ไม่จำกัด |
| `--tickers` | ระบุ ticker เป็นรายการ | ทุก ticker ใน etf.yaml |
