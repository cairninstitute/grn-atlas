#!/usr/bin/env python3
"""Load the public IC4R MSU/RAP-DB rice identifier crosswalk as aliases."""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import sqlite3
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DB = BACKEND / "data" / "grn.sqlite3"
URL = "https://download.cncb.ac.cn/bigd/GEN/IC4R-2018/2-Locus-Mapping/5-IC4R-MSU-RAP-DB-Locus-Mapping.csv.gz"


def load(conn: sqlite3.Connection) -> dict:
    request = urllib.request.Request(URL, headers={"User-Agent": "grn-atlas/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        text = gzip.decompress(response.read()).decode("utf-8", "replace")
    rice_ids = {row[0] for row in conn.execute("SELECT id FROM genes WHERE species='rice'")}
    rows = []
    input_rows = 0
    for record in csv.reader(io.StringIO(text)):
        input_rows += 1
        if len(record) < 3:
            continue
        _, msu_id, rap_id = (value.strip() for value in record[:3])
        if msu_id not in rice_ids or not rap_id or rap_id == "NA":
            continue
        rows.append((msu_id, rap_id, "IC4R MSU-RAP-DB crosswalk"))
    conn.execute("DELETE FROM gene_aliases WHERE source='IC4R MSU-RAP-DB crosswalk'")
    conn.executemany(
        "INSERT OR IGNORE INTO gene_aliases (gene_id,alias,source) VALUES (?,?,?)", rows
    )
    conn.commit()
    return {"input_rows": input_rows, "mapped_aliases": len(rows), "source_url": URL}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        result = load(conn)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
