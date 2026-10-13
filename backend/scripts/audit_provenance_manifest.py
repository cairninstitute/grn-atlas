#!/usr/bin/env python3
"""Report source labels present in the atlas but absent from its manifest."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import provenance  # noqa: E402


def database_source_labels(conn: sqlite3.Connection) -> set[str]:
    labels: set[str] = set()
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for (raw_sources,) in conn.execute("SELECT sources FROM interactions"):
        try:
            labels.update(str(value) for value in json.loads(raw_sources or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    if "perturbation_observations" in tables:
        labels.update(
            row[0] for row in conn.execute(
                "SELECT DISTINCT dataset_label FROM perturbation_observations "
                "WHERE dataset_label IS NOT NULL"
            )
        )
    if "regulatory_evidence" in tables:
        labels.update(
            row[0] for row in conn.execute(
                "SELECT DISTINCT source_name FROM regulatory_evidence WHERE source_name IS NOT NULL"
            )
        )
    return labels


def audit(conn: sqlite3.Connection) -> dict:
    labels = sorted(database_source_labels(conn))
    mapped = provenance.source_label_map()
    return {
        "database_labels": labels,
        "mapped": {label: mapped[label] for label in labels if label in mapped},
        "unmapped": [label for label in labels if label not in mapped],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=BACKEND / "data" / "grn.sqlite3")
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        result = audit(conn)
    print(json.dumps(result, indent=2))
    return 1 if result["unmapped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
