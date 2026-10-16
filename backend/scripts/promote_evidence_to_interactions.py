#!/usr/bin/env python3
"""Promote high-confidence regulatory evidence into the interactions table.

Scans regulatory_evidence for direct binding and signed evidence that isn't
yet in the interactions table, and inserts or updates interactions accordingly.

Sources promoted:
  - ChIP-Atlas: direct unsigned binding (confidence ≥ 0.45)
  - TFLink small-scale: direct unsigned binding
  - CollecTRI: direct signed evidence (sign populated)
  - SIGNOR: direct signed evidence (sign populated)

DirectBinding edges are NOT promoted here — load_direct_binding.py handles
those directly to avoid double-promotion and confidence inflation.

For edges that already exist in interactions, the source label is appended
and confidence is boosted. For new edges, they're inserted with the evidence
source as their source label. Signed sources (CollecTRI, SIGNOR) populate
the sign and sign_evidence columns.

Usage:
    python backend/scripts/promote_evidence_to_interactions.py [--db backend/data/grn.sqlite3]
    python backend/scripts/promote_evidence_to_interactions.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"

PROMOTABLE_SOURCES = {
    "ChIP-Atlas": {"label": "ChIP-Atlas", "min_confidence": 0.45},
    "TFLink small-scale": {"label": "TFLink small-scale", "min_confidence": 0.50},
    "CollecTRI": {"label": "CollecTRI", "min_confidence": 0.50},
    "SIGNOR": {"label": "SIGNOR", "min_confidence": 0.50},
}

SIGNED_SOURCES = {"CollecTRI", "SIGNOR"}

MULTI_EVIDENCE_BOOST = 0.05


def promote(conn: sqlite3.Connection, dry_run: bool = False) -> dict:
    stats = Counter()

    pairs: dict[tuple[str, str], dict] = {}
    for source_name, cfg in PROMOTABLE_SOURCES.items():
        min_conf = cfg["min_confidence"]
        label = cfg["label"]
        rows = conn.execute(
            "SELECT source_id, target_id, relation_type, confidence "
            "FROM regulatory_evidence "
            "WHERE source_name = ? AND COALESCE(confidence, 0.60) >= ?",
            (source_name, min_conf),
        ).fetchall()
        stats[f"evidence_{source_name}"] = len(rows)

        for source_id, target_id, relation, confidence in rows:
            if source_id == target_id:
                continue
            key = (source_id, target_id)
            if key not in pairs:
                pairs[key] = {
                    "relation": relation or "regulation",
                    "confidence": confidence or 0.50,
                    "sources": set(),
                }
            entry = pairs[key]
            entry["sources"].add(label)
            entry["confidence"] = max(entry["confidence"], confidence or 0.50)
            if relation in ("activation", "repression"):
                entry["relation"] = relation

    print(f"Candidate pairs from evidence: {len(pairs):,}")
    stats["candidate_pairs"] = len(pairs)

    new_edges = 0
    updated_edges = 0
    unchanged_edges = 0

    for (src_id, tgt_id), entry in pairs.items():
        existing = conn.execute(
            "SELECT sources, confidence FROM interactions "
            "WHERE source_id = ? AND target_id = ?",
            (src_id, tgt_id),
        ).fetchone()

        if existing:
            old_sources = json.loads(existing[0])
            new_labels = entry["sources"] - set(old_sources)
            if new_labels:
                merged = sorted(set(old_sources) | entry["sources"])
                new_conf = min(existing[1] + MULTI_EVIDENCE_BOOST * len(new_labels), 0.95)
                if not dry_run:
                    conn.execute(
                        "UPDATE interactions SET sources = ?, confidence = ? "
                        "WHERE source_id = ? AND target_id = ?",
                        (json.dumps(merged), round(new_conf, 4), src_id, tgt_id),
                    )
                    if entry["relation"] in ("activation", "repression"):
                        conn.execute(
                            "UPDATE interactions SET sign = ?, sign_evidence = 'measured' "
                            "WHERE source_id = ? AND target_id = ? "
                            "AND sign IS NULL",
                            (entry["relation"], src_id, tgt_id),
                        )
                updated_edges += 1
            else:
                unchanged_edges += 1
        else:
            relation = entry["relation"]
            sign = None
            sign_evidence = "unknown"
            if relation in ("activation", "repression"):
                sign = relation
                sign_evidence = "measured"
            if not dry_run:
                conn.execute(
                    "INSERT OR IGNORE INTO interactions "
                    "(source_id, target_id, regulation_type, confidence, sources, pmids, "
                    " sign, sign_evidence) "
                    "VALUES (?, ?, ?, ?, ?, '[]', ?, ?)",
                    (src_id, tgt_id, relation,
                     round(entry["confidence"], 4),
                     json.dumps(sorted(entry["sources"])),
                     sign, sign_evidence),
                )
            new_edges += 1

    if not dry_run:
        conn.commit()

    stats["new_edges"] = new_edges
    stats["updated_edges"] = updated_edges
    stats["unchanged_edges"] = unchanged_edges
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without modifying the DB")
    args = parser.parse_args()

    with sqlite3.connect(args.db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        result = promote(conn, dry_run=args.dry_run)

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{prefix}Evidence promotion results:")
    print(f"  New edges inserted:    {result['new_edges']:,}")
    print(f"  Existing edges updated: {result['updated_edges']:,}")
    print(f"  Already present:       {result['unchanged_edges']:,}")
    for key, val in sorted(result.items()):
        if key.startswith("evidence_"):
            print(f"  {key}: {val:,}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
