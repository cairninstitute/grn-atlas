#!/usr/bin/env python3
"""Load TFLink small-scale TF-target experiments as direct unsigned evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import urllib.request
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import begin_import, finish_import, gene_resolver, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
BASE = "https://cdn.netbiol.org/tflink/download_files/TFLink_{organism}_interactions_SS_simpleFormat_v1.0.tsv"
SPECIES = {"Homo_sapiens": "human", "Mus_musculus": "mouse"}
SOURCE = "TFLink small-scale"
VERSION = "1.0"


def parse_pmids(raw: str) -> list[str]:
    return [token for token in (raw or "").split(";") if token.isdigit()]


def load(conn: sqlite3.Connection) -> dict:
    rows_by_key, stats = {}, Counter()
    for organism, species in SPECIES.items():
        url = BASE.format(organism=organism)
        resolver = gene_resolver(conn, species)
        request = urllib.request.Request(url, headers={"User-Agent": "grn-atlas/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response:
            reader = csv.DictReader((line.decode("utf-8", "replace") for line in response), delimiter="\t")
            for record in reader:
                stats["input"] += 1
                source_id = resolver(record.get("Name.TF")) or resolver(record.get("NCBI.GeneID.TF"))
                target_id = resolver(record.get("Name.Target")) or resolver(record.get("NCBI.GeneID.Target"))
                if not source_id or not target_id or source_id == target_id:
                    stats["unmapped_or_self"] += 1
                    continue
                key = f"{species}|{source_id}|{target_id}"
                row = rows_by_key.setdefault(key, {
                    "species": species, "source_id": source_id, "target_id": target_id,
                    "relation_type": "regulation", "evidence_layer": "direct_unsigned",
                    "directness": "direct", "record_key": key, "confidence": 0.72,
                    "pmids": [], "metadata": {"methods": [], "upstream_sources": []},
                })
                row["pmids"].extend(parse_pmids(record.get("PubmedID", "")))
                row["metadata"]["methods"].extend(filter(None, record.get("Detection.method", "").split(";")))
                row["metadata"]["upstream_sources"].extend(filter(None, record.get("Source.database", "").split(";")))
    for row in rows_by_key.values():
        row["pmids"] = sorted(set(row["pmids"]))
        row["metadata"]["methods"] = sorted(set(row["metadata"]["methods"]))
        row["metadata"]["upstream_sources"] = sorted(set(row["metadata"]["upstream_sources"]))
    run_id = begin_import(conn, SOURCE, VERSION, "https://tflink.net/download/", None)
    stats["stored"] = replace_source_evidence(conn, SOURCE, VERSION, run_id, rows_by_key.values())
    finish_import(conn, run_id, dict(stats))
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        result = load(conn)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
