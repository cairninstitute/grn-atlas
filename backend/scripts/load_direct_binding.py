#!/usr/bin/env python3
"""Load direct TF-binding data (ChIP-seq / DAP-seq) into the GRN Atlas.

Reads pre-processed TF-target TSVs from backend/data/direct_binding/ and:
  1. Stores evidence in regulatory_evidence table (for provenance tracking)
  2. Promotes edges to the interactions table (for network queries)

Usage:
    python backend/scripts/load_direct_binding.py [--db backend/data/grn.sqlite3]
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from external_evidence import begin_import, finish_import, gene_resolver, replace_source_evidence  # noqa: E402

DB = BACKEND / "data" / "grn.sqlite3"
BINDING_DIR = BACKEND / "data" / "direct_binding"
MULTI_EVIDENCE_BOOST = 0.05
DEFAULT_CONFIDENCE = 0.50


def parse_species(filename: str) -> str:
    """Extract species from '<source>_<species>.tsv'."""
    return filename.rsplit(".", 1)[0].rsplit("_", 1)[-1]


def parse_source_label(filename: str) -> str:
    """Extract source label from '<source>_<species>.tsv'."""
    return filename.rsplit(".", 1)[0].rsplit("_", 1)[0]


def load_tsv(path: Path, resolve, species: str) -> tuple[list[dict], Counter]:
    stats: Counter = Counter()
    rows = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for record in reader:
            stats["input_rows"] += 1
            tf_symbol = record["tf_symbol"].strip()
            target_raw = record["target_id"].strip()
            source = record["source"].strip()
            accession = record.get("accession", "").strip()
            try:
                confidence = float(record["confidence"])
            except (ValueError, KeyError):
                confidence = DEFAULT_CONFIDENCE

            tf_id = resolve(tf_symbol)
            if not tf_id:
                stats["tf_unresolved"] += 1
                continue
            stats["tf_resolved"] += 1

            target_id = resolve(target_raw)
            if not target_id:
                stats["target_unresolved"] += 1
                continue
            stats["target_resolved"] += 1

            if tf_id == target_id:
                stats["self_loops"] += 1
                continue

            record_key = f"{source}|{accession}|{tf_id}|{target_id}"
            rows.append({
                "species": species,
                "source_id": tf_id,
                "target_id": target_id,
                "relation_type": "regulation",
                "evidence_layer": "direct_unsigned",
                "directness": "binding",
                "record_key": record_key,
                "confidence": confidence,
                "context": {},
                "metadata": {"accession": accession, "source": source},
            })
            stats["evidence_rows"] += 1
    return rows, stats


def promote_to_interactions(conn: sqlite3.Connection, evidence_rows: list[dict]) -> Counter:
    stats: Counter = Counter()
    pairs: dict[tuple[str, str], tuple[float, set[str]]] = {}
    for row in evidence_rows:
        key = (row["source_id"], row["target_id"])
        source_label = row["metadata"]["source"]
        if key not in pairs:
            pairs[key] = (row["confidence"], {source_label})
        else:
            best_conf, labels = pairs[key]
            labels.add(source_label)
            pairs[key] = (max(best_conf, row["confidence"]), labels)

    for (tf_id, target_id), (confidence, source_labels) in pairs.items():
        existing = conn.execute(
            "SELECT sources, confidence FROM interactions WHERE source_id=? AND target_id=?",
            (tf_id, target_id),
        ).fetchone()

        if existing:
            sources = json.loads(existing[0])
            added = False
            for label in source_labels:
                if label not in sources:
                    sources.append(label)
                    added = True
            if added:
                new_conf = min(existing[1] + MULTI_EVIDENCE_BOOST, 0.95)
                conn.execute(
                    "UPDATE interactions SET sources=?, confidence=? "
                    "WHERE source_id=? AND target_id=?",
                    (json.dumps(sorted(sources)), round(new_conf, 4), tf_id, target_id),
                )
                stats["edges_updated"] += 1
            else:
                stats["edges_unchanged"] += 1
        else:
            conn.execute(
                "INSERT OR IGNORE INTO interactions "
                "(source_id, target_id, regulation_type, confidence, sources, pmids, "
                " sign, sign_evidence) "
                "VALUES (?, ?, 'regulation', ?, ?, '[]', NULL, 'unknown')",
                (tf_id, target_id, round(confidence, 4),
                 json.dumps(sorted(source_labels))),
            )
            stats["edges_new"] += 1
    stats["pairs_total"] = len(pairs)
    return stats


def load(conn: sqlite3.Connection) -> dict:
    if not BINDING_DIR.is_dir():
        print(f"No directory at {BINDING_DIR}, nothing to load.")
        return {}

    tsv_files = sorted(BINDING_DIR.glob("*.tsv"))
    if not tsv_files:
        print(f"No TSV files in {BINDING_DIR}.")
        return {}

    all_evidence: list[dict] = []
    stats: Counter = Counter()
    per_file: dict[str, dict] = {}

    for path in tsv_files:
        species = parse_species(path.name)
        source_label = parse_source_label(path.name)
        resolve = gene_resolver(conn, species)

        rows, file_stats = load_tsv(path, resolve, species)
        all_evidence.extend(rows)
        stats.update(file_stats)
        stats["files"] += 1
        per_file[path.name] = dict(file_stats)
        print(f"  {path.name}: {file_stats['evidence_rows']} edges "
              f"({file_stats['tf_unresolved']} TFs unresolved, "
              f"{file_stats['target_unresolved']} targets unresolved)")

    if not all_evidence:
        print("No evidence rows produced from any file.")
        return dict(stats)

    # Store evidence via external_evidence helpers
    source_name = "DirectBinding"
    version = "batch"
    run_id = begin_import(conn, source_name, version, str(BINDING_DIR), None)
    stats["stored"] = replace_source_evidence(
        conn, source_name, version, run_id, all_evidence,
    )

    # Promote edges to interactions table
    promo_stats = promote_to_interactions(conn, all_evidence)
    stats.update(promo_stats)

    finish_import(conn, run_id, dict(stats))

    print(f"\n  Evidence stored: {stats['stored']:,}")
    print(f"  Interaction pairs: {promo_stats['pairs_total']:,} "
          f"(new: {promo_stats['edges_new']:,}, "
          f"updated: {promo_stats['edges_updated']:,}, "
          f"unchanged: {promo_stats['edges_unchanged']:,})")

    result = dict(stats)
    result["per_file"] = per_file
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        result = load(conn)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
