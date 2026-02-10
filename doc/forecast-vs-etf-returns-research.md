# Why forecast.json “top countries” did not deliver good ETF price growth

## What the data shows

**Forecast** (`macro-forecast-cursor-auto/forecast.json`): China, India, Brazil, Indonesia, Russia are consistently ranked top (high scores) from 2010 onward.

**ETF mapping** (`makro-etf-colreated/etf-mapping.json`): China→MCHI/FXI, India→INDA, Brazil→EWZ, Indonesia→EIDO, Russia→ERUS.

**Actual total returns (same period: start 2013 → Feb 2026)** from `data/etf_price.csv`:

| ETF  | Country   | Return (2013→2026) | vs developed |
|------|-----------|--------------------|---------------|
| VEA  | Developed ex-US | **+182%** | benchmark |
| EFA  | Developed ex-US | **+163%** | benchmark |
| INDA | India     | +129%             | underperformed |
| MCHI | China     | +60%              | large underperformance |
| FXI  | China     | +30%              | large underperformance |
| EWZ  | Brazil    | +22%              | large underperformance |
| EIDO | Indonesia | **-24%**          | negative |
| ERUS | Russia    | **-99.9%**        | effectively wiped out |

So: **only India was close to developed markets**. China, Brazil, Indonesia, and Russia did **not** deliver “good” ETF price growth; Indonesia and Russia were very bad.

---

## Why macro “top country” forecasts ≠ good ETF returns

### 1. GDP growth ≠ equity returns (well documented)

- There is **no reliable positive link** between a country’s GDP (or per‑capita income) growth and its **stock market returns**.
- In EM, correlation between real per‑capita GDP growth and stock returns is weak (~0.17); in developed markets it can be **negative** (~-0.31).
- What **does** correlate with returns is **earnings per share (EPS) growth**, not GDP. Many EMs had positive GDP growth but **negative real EPS growth** over long periods.
- So “China / India / Brazil will grow fast” is a statement about **economy**, not about **listed equity performance** in USD.

Sources: academic work on GDP vs equity returns (e.g. SSRN 1707483); Evidence Investor “GDP growth and emerging market returns”.

### 2. What the forecast actually measured

- The forecast is built from **macro/geopolitical outlooks** (e.g. GEP, BRIC, “top economy by 2050”) — i.e. **growth of the economy**, not of listed companies.
- It was **not** built from:
  - earnings growth,
  - shareholder payouts,
  - or relative valuation (P/E, etc.).

So by construction it aligns with “who will grow GDP,” not “whose **equity** will outperform.”

### 3. Country-specific reasons (why each underperformed)

- **China (MCHI, FXI)**  
  - Listed market is a subset of the economy; state-owned and inefficient capital allocation; regulatory crackdowns (tech, property); governance and disclosure issues.  
  - Result: GDP kept growing, but **listed Chinese equities in USD** underperformed developed markets (and even negative 10‑year returns in some windows).

- **Brazil (EWZ)**  
  - Political volatility, commodity dependence, currency (BRL), corruption and governance.  
  - Economy can be “top by 2050” in macro reports while **equity** returns in USD are modest or poor.

- **Indonesia (EIDO)**  
  - Single-country EM, commodity-linked, currency (IDR), smaller and less liquid market.  
  - **Negative** total return over the period in the CSV.

- **Russia (ERUS)**  
  - War and sanctions; fund effectively collapsed (price → ~0.03).  
  - Macro “top country” view had no scenario for this.

- **India (INDA)**  
  - Only one that came close to developed-market returns in this comparison; still a bit below VEA/EFA but in the same ballpark.

### 4. Valuation and timing

- In 2010–2012, EM and “BRIC” were **already priced for strong growth**. If that growth was in the price, future returns can be low or negative even if GDP keeps growing.
- So “good macro outlook” + “already expensive” → **poor subsequent returns**.

### 5. Currency and listing

- `etf_price.csv` is in **USD**. Local-currency gains can be offset or reversed by FX (e.g. BRL, IDR, RUB).
- ETF returns reflect **listed, tradeable** companies. In China, much growth is in SOEs, unlisted firms, or sectors that did not translate into listed equity performance.

---

## Summary

| Question | Answer |
|----------|--------|
| Does `forecast.json` say China and top countries should be good? | Yes — for **macro / GDP** growth. |
| Did those countries’ ETFs in `etf_price.csv` deliver good price growth? | **No.** Only India was close; China/Brazil underperformed; Indonesia and Russia were very bad. |
| Why? | (1) **GDP ≠ equity returns**; (2) forecast is macro, not earnings/valuation; (3) governance, regulation, politics, currency; (4) Russia: war/sanctions; (5) EM was often already priced for growth. |

**Takeaway:** Using “top country” macro rankings from `forecast.json` as a direct input to **equity** allocation (e.g. equal-weight those country ETFs) is not supported by the data: it would have underperformed a simple developed-market (e.g. VEA/EFA) buy‑and‑hold over this period. For equity, earnings, valuation, and governance matter more than headline GDP rankings.
