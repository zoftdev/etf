#!/usr/bin/env python3
"""
Parse data/buffet-ind.csv: split 'country' (CODE Thai) into country_code and country_thai.
Output: same file with columns [country_code, country_thai, country_code.source, 2004, ...]
"""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"  # Go up from analysis/ to root
CSV_PATH = DATA_DIR / "buffet-ind.csv"


def main() -> None:
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    # header was: country, country_code.source, 2004, ...
    # new header: country_code, country_thai, country_code.source, 2004, ...
    new_header = ["country_code", "country_thai", header[1]] + header[2:]

    out_rows = []
    for row in rows:
        if not row:
            continue
        first = row[0].strip()
        # Split on first space: "RUA รัสเซีย" -> RUA, รัสเซีย
        if " " in first:
            code, thai = first.split(" ", 1)
        else:
            code, thai = first, ""
        out_rows.append([code.strip(), thai.strip()] + row[1:])

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(new_header)
        w.writerows(out_rows)
    print(f"Wrote {CSV_PATH} with columns: {new_header[:5]}...")


if __name__ == "__main__":
    main()
