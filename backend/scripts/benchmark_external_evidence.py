#!/usr/bin/env python3
"""Write stable JSON and CSV comparisons for normalized external evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import benchmark_source  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=BACKEND / "data" / "grn.sqlite3")
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        sources = [row[0] for row in conn.execute(
            "SELECT DISTINCT source_name FROM regulatory_evidence ORDER BY source_name"
        )]
        report = [benchmark_source(conn, source) for source in sources]
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    fields = ["source", "species", "records", "unique_pairs", "new_pairs", "conflicts", "internal_conflicts",
              "total_new_pairs", "total_overlaps", "signed_agreements", "signed_conflicts"]
    with args.csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for source in report:
            for species, values in source["by_species"].items():
                writer.writerow({
                    "source": source["source"], "species": species, **values,
                    "total_new_pairs": source["new_pairs"],
                    "total_overlaps": source["overlapping_pairs"],
                    "signed_agreements": source["signed_agreements"],
                    "signed_conflicts": source["signed_conflicts"],
                })
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
