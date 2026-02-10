# Macro forecast — reusable prompts

user will told to check forecast publish in history as YYYY

Back in YYYY, find forecasts and outlooks for ZZZZ, AAAA or the future. Extract:
1. Top 5 countries
2. Top commodity (if none hot, low score or omit)
3. US sector

 - you must not read web content that after target year YYYY
 - ทุก item ใน 3 หมวด (ประเทศ / commodity / US sector) ต้องมี อย่างน้อย 2 independent sources
 - dont look previous year or future file.
**Output:** 

  1. Write generated markdown (`YYYY.md`), include a **Sources** section with named sources and **full links** (same style as the existing generated file, e.g. 2010.md). see example at example_2010.md

  2. Append to forecast.json , see example in example_forecast.json
---

## Main task

Back in **YYYY**, find forecasts and outlooks that targeted next one,two year or fure the future**. Extract and fill:

1. **Top 5 countries** (from those forecasts)
2. **Top commodity** (from those forecasts; if none is clearly “hot”, use low score or omit)
3. **US sector** (from those forecasts)

Fill results into:

- `YYYY.md`
- `forecast.json` — add or update the `"YYYY"` entry using the same schema as existing years

---

## Scoring

- **Score -1..1** for each item. **&lt; 0.3 = not much** — remove or set low; use score to prioritise.
- **Commodity:** if no clear “hot” commodity in that year’s forecasts, give low score or omit the row.

Add a **Score** column (or score field) to:
- Top 5 countries table
- Commodity table
- US sector table

---

## Markdown file (`YYYY.md`) structure
see example_2010.md
note:
- must have score
- **Sources:** include a Sources section with **named sources and full links** (e.g. “IMF, *World Economic Outlook…*” plus URL on next line). Same format as the previously generated year file (e.g. 2010.md).

---

## JSON schema (for `forecast.json`)

Each year key (e.g. `"YYYY"`) has:

- `description`: string (e.g. "Views from YYYY → 2021, 2022 & beyond")
- `countries`: array of `{ "rank", "name", "score", "note" }`
- `commodity`: array of `{ "name", "score", "note" }`
- `us_sector`: array of `{ "name", "score", "note" }`

Root: one key per forecast publication year. Same shape every year.

---
 