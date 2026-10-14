#!/usr/bin/env python3
"""Load reviewed non-transcriptional control edges from a JSON manifest."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import gene_resolver  # noqa: E402
from multilayer_control import replace_source  # noqa: E402


def load(conn: sqlite3.Connection, path: Path) -> dict:
    manifest = json.loads(path.read_text())
    source = manifest["source"]
    rows = []
    skipped = 0
    resolvers = {}
    for record in manifest.get("edges", []):
        if record.get("review_status") != "approved":
            skipped += 1
            continue
        species = record["species"]
        resolve = resolvers.setdefault(species, gene_resolver(conn, species))
        source_id, target_id = resolve(record["source_gene"]), resolve(record["target_gene"])
        if not source_id or not target_id:
            skipped += 1
            continue
        rows.append({**record, "source_id": source_id, "target_id": target_id})
    return {"stored": replace_source(conn, source, rows), "skipped": skipped, "source": source}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--db", type=Path, default=BACKEND / "data" / "grn.sqlite3")
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        result = load(conn, args.manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
